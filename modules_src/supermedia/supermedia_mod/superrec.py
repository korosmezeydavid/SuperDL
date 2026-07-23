"""Super Recorder – felvevő-motor (It.1: egyszerű felvevő).

A BASS felvevő-rétegére épül (a `superm_audio` már tartalmazza a BASS-betöltőt
és a Record*-deklarációkat), de NEM élő monitorra, hanem FÁJLBA rögzít: egy valódi
RECORDPROC-callback gyűjti a 16 bites PCM-darabokat a memóriába, közben kiszámolja
a CSÚCSSZINTET (akadálymentes szintmérőhöz). A mentés WAV-ba közvetlen, MP3-ba (és a
normalizálás/fade/csend-vágás) a Core-beli ffmpeg-gel offline történik.

Akadálymentes-first: a felület (superrecwin) ezt a motort vezérli, mindent
KIMONDVA – nincs vizuális hullámforma.
"""

import array
import ctypes as C
import os
import subprocess
import tempfile
import threading
import wave
from pathlib import Path

from . import superm_audio as A      # a BASS-betöltő + Record*-deklarációk
from superdl import ffmpeg as ffmpeg_mod   # megosztott ffmpeg a Core-ból
from superdl import mediaexport            # atomikus export (.part→ellenőrzés)


def input_devices() -> list:
    """A felvevő (mikrofon/bemenet) eszközök: [(index, név), …]."""
    return A.record_devices()


def write_wav_bytes(path: str, pcm: bytes, freq: int, channels: int):
    """Nyers 16 bites PCM kiírása WAV-ba."""
    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(freq)
        w.writeframes(pcm)


def write_wav_from_pcm_file(path: str, pcm_path: str, freq: int, channels: int,
                            chunk: int = 4 << 20) -> None:
    """WAV írása egy LEMEZEN lévő nyers PCM fájlból, DARABONKÉNT másolva.

    Így egy több órás felvétel sem kerül egyszerre a memóriába (a régi út a
    teljes hangot bytes-ként tartotta). [Herman Tibi REC-P0-02]"""
    if not pcm_path or not os.path.exists(pcm_path):
        raise RuntimeError("Nincs rögzített hanganyag a mentéshez.")
    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(freq)
        with open(pcm_path, "rb") as f:
            while True:
                block = f.read(chunk)
                if not block:
                    break
                w.writeframes(block)


def save_pcm_file(path: str, pcm_path: str, freq: int, channels: int, **kw) -> str:
    """A `save_pcm` STREAMELT párja: a forrás egy LEMEZEN lévő nyers PCM fájl,
    így egy több órás felvétel sem kerül a memóriába. [REC-P0-02]"""
    return save_pcm(path, b"", freq, channels, pcm_file=pcm_path, **kw)


def save_pcm(path: str, pcm: bytes, freq: int, channels: int, *,
             normalize: bool = False, fade_ms: int = 0,
             trim_silence: bool = False, out_freq: int = 0,
             mp3_bitrate: str = "256k", progress=None,
             pcm_file: str = "") -> str:
    """A felvevő ÉS a szerkesztő KÖZÖS mentője. A kiterjesztés dönt a formátumról
    (.wav/.mp3). Ha nincs utófeldolgozás, NINCS újramintavételezés ÉS WAV a cél →
    közvetlen írás; különben a Core ffmpeg-jével (normalizálás=EBU R128 loudnorm,
    fade=afade, csend-vágás=silenceremove). `out_freq`>0 esetén a megadott
    MINTAVÉTELRE alakít (0 = a forrás mintavétele marad); MP3-nál a `mp3_bitrate`
    (pl. „192k") a bitráta. Visszaadja a tényleges utat."""
    # A forrás VAGY memóriabeli PCM (szerkesztő), VAGY egy lemezen lévő nyers
    # PCM fájl (felvevő – így a hosszú felvétel nem kerül a memóriába).
    if not pcm and not pcm_file:
        raise RuntimeError("Nincs hanganyag a mentéshez.")
    if pcm_file:
        if not os.path.exists(pcm_file):
            raise RuntimeError("A rögzített hanganyag nem található.")
        nbytes = os.path.getsize(pcm_file)
    else:
        nbytes = len(pcm)
    if nbytes <= 0:
        raise RuntimeError("Nincs hanganyag a mentéshez.")

    def _wav_forras(cel: str) -> None:
        if pcm_file:
            write_wav_from_pcm_file(cel, pcm_file, freq, channels)
        else:
            write_wav_bytes(cel, pcm, freq, channels)

    ext = Path(path).suffix.lower()
    want_mp3 = ext == ".mp3"
    target_freq = int(out_freq) if out_freq else freq
    resample = target_freq != freq
    if not (want_mp3 or normalize or fade_ms > 0 or trim_silence or resample):
        # ATOMIKUSAN a feldolgozás nélküli WAV-nál is: enélkül egy megszakadt
        # írás (lemez megtelt, áramszünet) a MEGLÉVŐ fájlt csonkára cserélte.
        part = mediaexport.part_path(path)
        try:
            _wav_forras(part)
            ok, indok = mediaexport.verify_audio(part)
            if not ok:
                raise RuntimeError(f"A mentett hang nem használható: {indok}. "
                                   "A korábbi fájl érintetlen maradt.")
            mediaexport.commit(part, path)
        except BaseException:
            mediaexport.cleanup(part)
            raise
        return path

    import uuid as _uuid
    tmp = (Path(tempfile.gettempdir())
           / f"superrec_{os.getpid()}_{_uuid.uuid4().hex[:8]}.wav")
    _wav_forras(str(tmp))
    ff = ffmpeg_mod.find_ffmpeg()
    if not ff:
        ff_dir = ffmpeg_mod.ensure_ffmpeg(progress)
        ff = ffmpeg_mod.find_ffmpeg() if ff_dir else None
    if not ff:
        tmp.unlink(missing_ok=True)
        if not want_mp3:
            # NINCS CSENDES DEGRADÁLÁS: idáig csak akkor jutunk, ha KÉRTEK
            # utófeldolgozást (a „semmit sem kértek + WAV" ág fentebb visszatért).
            # Korábban a nyers hangot írtuk ki és SIKERT jelentettünk, így a
            # felhasználó azt hitte, normalizált/csendvágott/48 kHz-es fájlt
            # kapott – pedig egyik kérése sem teljesült. [Herman Tibi REC-P0-03]
            kert = []
            if normalize:
                kert.append("normalizálás")
            if fade_ms > 0:
                kert.append("fel-/lehalkítás")
            if trim_silence:
                kert.append("csend-vágás")
            if resample:
                kert.append(f"átalakítás {target_freq} Hz-re")
            raise RuntimeError(
                "Az ffmpeg nem érhető el, ezért a kért feldolgozás ("
                + ", ".join(kert) + ") NEM végezhető el. A hang NINCS elveszve: "
                "kapcsold ki a feldolgozást, és mentsd nyers WAV-ként, vagy "
                "engedd letölteni az ffmpeg-et.")
        raise RuntimeError("Az ffmpeg nem érhető el a feldolgozáshoz/MP3-hoz.")

    dur = nbytes / (freq * channels * 2) if (freq and channels) else 0.0
    filters = []
    if trim_silence:
        filters.append("silenceremove=start_periods=1:start_silence=0.2:"
                       "start_threshold=-50dB:detection=peak,areverse,"
                       "silenceremove=start_periods=1:start_silence=0.2:"
                       "start_threshold=-50dB:detection=peak,areverse")
    if normalize:
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    if fade_ms > 0:
        sec = fade_ms / 1000.0
        filters.append(f"afade=t=in:st=0:d={sec:.3f}")
        if dur > sec:
            filters.append(f"afade=t=out:st={max(0.0, dur - sec):.3f}:d={sec:.3f}")

    # ATOMIKUS EXPORT: a cél MELLÉ renderelünk, ellenőrizzük, és csak utána
    # lép a helyére. Így egy megszakadt/hibás mentés NEM teszi tönkre a
    # korábbi, jó fájlt. [Herman Tibi AUDIO-P0-04 / EDIT-P1-17]
    part = mediaexport.part_path(path)
    cmd = [ff, "-y", "-i", str(tmp)]
    if filters:
        cmd += ["-af", ",".join(filters)]
    if resample:
        cmd += ["-ar", str(target_freq)]        # a kért MINTAVÉTELRE alakít
    if want_mp3:
        cmd += ["-c:a", "libmp3lame", "-b:a", str(mp3_bitrate)]  # állítható bitráta
    cmd += [part]
    flags = 0x08000000 if os.name == "nt" else 0
    try:
        subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, creationflags=flags, check=True)
        ok, indok = mediaexport.verify_audio(part, mediaexport.ffprobe_for(ff))
        if not ok:
            raise RuntimeError(f"A mentett hang nem használható: {indok}. "
                               "A korábbi fájl érintetlen maradt.")
        mediaexport.commit(part, path)
    except BaseException:
        mediaexport.cleanup(part)               # nem marad félkész fájl
        raise
    finally:
        tmp.unlink(missing_ok=True)
    return path


def process_pcm(pcm: bytes, freq: int, channels: int, af: str) -> bytes:
    """Nyers 16 bites PCM átengedése egy ffmpeg AUDIO-SZŰRŐN (`-af af`), és a
    feldolgozott PCM visszaadása. A hossz változhat (pl. tempó-effektnél). Üres
    bemenetre/üres szűrőre az eredetit adja vissza. ValueError/RuntimeError hiba
    esetén."""
    if not pcm:
        return pcm
    if not af:
        return pcm
    ff = ffmpeg_mod.find_ffmpeg()
    if not ff:
        ff_dir = ffmpeg_mod.ensure_ffmpeg()
        ff = ffmpeg_mod.find_ffmpeg() if ff_dir else None
    if not ff:
        raise RuntimeError("Az ffmpeg nem érhető el az effekthez.")
    flags = 0x08000000 if os.name == "nt" else 0
    cmd = [ff, "-v", "error",
           "-f", "s16le", "-ar", str(freq), "-ac", str(channels), "-i", "-",
           "-af", af,
           "-f", "s16le", "-ar", str(freq), "-ac", str(channels), "-"]
    r = subprocess.run(cmd, input=pcm, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, creationflags=flags)
    if r.returncode != 0 or not r.stdout:
        msg = (r.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        raise RuntimeError("Az effekt nem alkalmazható"
                           + (f": {msg[-1]}" if msg else "."))
    # a kimenetet mintahatárra (frame) igazítjuk
    fb = channels * 2
    out = r.stdout
    if len(out) % fb:
        out = out[:len(out) - (len(out) % fb)]
    return out


def probe_audio(path: str):
    """A hangfájl NATÍV mintavétele és csatornaszáma (ffprobe-bal), hogy import-
    kor megőrizhessük az eredetit (pl. 48 kHz-et NE alakítsuk 44,1-re). Visszaad:
    (freq, channels), vagy (0, 0) ha nem állapítható meg."""
    ff = ffmpeg_mod.find_ffmpeg()
    if not ff:
        ff_dir = ffmpeg_mod.ensure_ffmpeg()
        ff = ffmpeg_mod.find_ffmpeg() if ff_dir else None
    if not ff:
        return 0, 0
    probe = str(Path(ff).with_name("ffprobe.exe")) if ff.lower().endswith(
        "ffmpeg.exe") else "ffprobe"
    flags = 0x08000000 if os.name == "nt" else 0
    try:
        r = subprocess.run(
            [probe, "-v", "error", "-select_streams", "a:0", "-show_entries",
             "stream=sample_rate,channels", "-of", "csv=p=0", path],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, creationflags=flags, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return 0, 0
    out = (r.stdout or b"").decode("utf-8", "replace").strip().split(",")
    try:
        freq = int(out[0]); ch = int(out[1]) if len(out) > 1 else 2
        return (freq if freq > 0 else 0), (ch if ch > 0 else 2)
    except (ValueError, IndexError):
        return 0, 0


def decode_to_pcm(path: str, freq: int = 44100, channels: int = 2,
                  progress=None) -> bytes:
    """Tetszőleges hangfájl (WAV/MP3/M4A/…) dekódolása nyers 16 bites PCM-mé a
    Core ffmpeg-jével (a szerkesztőbe töltéshez). `freq`=0 esetén a forrás NATÍV
    mintavételét tartja meg (nincs újramintavételezés)."""
    ff = ffmpeg_mod.find_ffmpeg()
    if not ff:
        ff_dir = ffmpeg_mod.ensure_ffmpeg(progress)
        ff = ffmpeg_mod.find_ffmpeg() if ff_dir else None
    if not ff:
        raise RuntimeError("Az ffmpeg nem érhető el a megnyitáshoz.")
    flags = 0x08000000 if os.name == "nt" else 0
    cmd = [ff, "-v", "error", "-i", path, "-f", "s16le",
           "-acodec", "pcm_s16le"]
    if freq:                                  # 0 = natív mintavétel megtartása
        cmd += ["-ar", str(freq)]
    cmd += ["-ac", str(channels), "-"]
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL, creationflags=flags)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError("A fájl nem dekódolható (nem hang, vagy sérült?).")
    return r.stdout


class Recorder:
    """Mikrofonból/bemenetből FÁJLBA rögzít, csúcsszint-méréssel. A felvétel a
    memóriában gyűlik (16 bites PCM), a STOP után menthető WAV-ba vagy MP3-ba,
    opcionális normalizálással/fade-del/csend-vágással."""

    def __init__(self, device: int = -1, freq: int = 44100, channels: int = 2):
        self.device = device          # -1 = alap felvevő eszköz
        self.freq = freq
        self.channels = channels      # 2 = sztereó (ha nem megy, 1 = monó)
        self._h = 0
        self._proc = None             # a RECORDPROC-referenciát ÉLETBEN kell tartani
        # LEMEZ-ALAPÚ rögzítés: a felvétel FOLYAMATOSAN fájlba íródik, a
        # memóriában csak egy kis, ki nem írt puffer marad. Korábban az EGÉSZ
        # felvétel a `_chunks` listában gyűlt: egy órányi 44,1 kHz-es sztereó
        # hang több száz MB, 8 óra pedig biztos MemoryError (és a mentéskor
        # további teljes másolatok készültek). [Herman Tibi REC-P0-01/02]
        self._buf: list[bytes] = []   # csak a még ki nem írt darabok
        self._buf_bytes = 0
        self._bytes = 0               # a felvétel TELJES hossza bájtban
        self._spill = ""              # a nyers PCM ideiglenes fájlja
        self._fh = None               # a megnyitott írási leíró
        self._writer = None           # a kiíró szál
        self._writer_stop = threading.Event()
        self._lock = threading.Lock()
        self._paused = False
        self.recording = False
        self.peak = 0.0               # utolsó csúcs (0..1), a szintmérőhöz
        self.clipped = False          # volt-e telítés (csúcs ~1.0)

    # ---- felvétel ----------------------------------------------------

    # ---- lemez-alapú puffer ------------------------------------------

    def _open_spill(self):
        """A nyers PCM ideiglenes fájljának megnyitása + a kiíró szál indítása."""
        if self._fh is not None:
            return
        import tempfile
        import uuid as _uuid
        self._spill = os.path.join(
            tempfile.gettempdir(),
            f"superrec_{os.getpid()}_{_uuid.uuid4().hex[:8]}.pcm")
        self._fh = open(self._spill, "wb")
        self._writer_stop.clear()
        self._writer = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer.start()

    def _drain(self):
        """A pufferelt darabok kiírása lemezre (a felvevő szálon kívül)."""
        with self._lock:
            chunks, self._buf, self._buf_bytes = self._buf, [], 0
        if chunks and self._fh is not None:
            try:
                self._fh.write(b"".join(chunks))
            except OSError:
                pass          # lemezhiba: a felvétel megy tovább, a mentés jelez

    def _writer_loop(self):
        while not self._writer_stop.wait(0.2):
            self._drain()
        self._drain()         # a leállításkor a maradék is menjen ki

    def _flush(self):
        """Minden ki nem írt adat lemezre kerül (mentés/olvasás előtt)."""
        self._drain()
        if self._fh is not None:
            try:
                self._fh.flush()
            except OSError:
                pass

    def _callback(self, handle, buffer, length, user):
        if not self._paused and length:
            data = C.string_at(buffer, length)
            with self._lock:
                # a visszahívás CSAK pufferel (rövid marad); a lemezre írást a
                # külön kiíró szál végzi → nincs I/O a valós idejű hang-szálon
                self._buf.append(data)
                self._buf_bytes += length
                self._bytes += length
            try:
                arr = array.array("h")
                arr.frombytes(data)
                if arr:
                    pk = max(abs(max(arr)), abs(min(arr))) / 32768.0
                    self.peak = pk
                    if pk >= 0.999:
                        self.clipped = True
            except (ValueError, OverflowError):
                pass
        return 1          # TRUE = folytatódjon a felvétel

    def start(self):
        if self.recording:
            return
        self._open_spill()        # a felvétel lemezre folyik, nem a memóriába
        b = A._lib()
        if self.device not in A._rec_inited:
            if not b.BASS_RecordInit(self.device):
                if b.BASS_ErrorGetCode() != 14:        # 14 = már inicializálva
                    raise A.BassError(
                        "A felvevő eszköz nem indítható (kód "
                        f"{b.BASS_ErrorGetCode()}). Van csatlakoztatott mikrofon?")
            A._rec_inited.add(self.device)
        A.select_record_device(b, self.device)   # -1 = az IGAZI alapértelmezett
        self._proc = A.RECORDPROC(self._callback)
        h = b.BASS_RecordStart(self.freq, self.channels, 0, self._proc, None)
        if not h and self.channels == 2:               # essünk vissza monóra
            self.channels = 1
            h = b.BASS_RecordStart(self.freq, 1, 0, self._proc, None)
        if not h:
            raise A.BassError(f"A felvétel nem indult (kód {b.BASS_ErrorGetCode()}).")
        self._h = h
        self.recording = True
        self._paused = False

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    @property
    def paused(self) -> bool:
        return self._paused

    def stop(self):
        if self._h:
            try:
                A._lib().BASS_ChannelStop(self._h)
            except Exception:
                pass
        self._h = 0
        self.recording = False
        self._paused = False
        self._flush()             # a pufferelt maradék is kerüljön lemezre

    def _close_spill(self):
        """A kiíró szál leállítása és az ideiglenes fájl lezárása/törlése."""
        self._writer_stop.set()
        w, self._writer = self._writer, None
        if w is not None:
            try:
                w.join(timeout=3)
            except Exception:
                pass
        self._drain()
        if self._fh is not None:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None
        if self._spill:
            try:
                if os.path.exists(self._spill):
                    os.remove(self._spill)
            except OSError:
                pass
            self._spill = ""

    def reset(self):
        """A felvett anyag eldobása (új felvételhez)."""
        self.stop()
        self._close_spill()
        with self._lock:
            self._buf = []
            self._buf_bytes = 0
            self._bytes = 0
        self.peak = 0.0
        self.clipped = False

    def close(self):
        """Az erőforrások elengedése (ablak bezárásakor): szál + ideiglenes fájl."""
        self.stop()
        self._close_spill()

    # ---- állapot -----------------------------------------------------

    def duration(self) -> float:
        """A felvett anyag hossza másodpercben."""
        bytes_per_sec = self.freq * self.channels * 2      # 16 bit = 2 byte
        return self._bytes / bytes_per_sec if bytes_per_sec else 0.0

    def has_audio(self) -> bool:
        return self._bytes > 0

    @staticmethod
    def peak_db(peak: float) -> float:
        """A 0..1 csúcsból dBFS (−inf..0). Csendre −90-et ad (nem −inf)."""
        import math
        return 20 * math.log10(peak) if peak > 1e-5 else -90.0

    # ---- mentés ------------------------------------------------------

    def pcm_path(self) -> str:
        """A nyers PCM ideiglenes fájljának útja (a felvétel LEMEZEN van).
        Streamelt mentéshez/olvasáshoz – nem másolja memóriába."""
        self._flush()
        return self._spill

    def pcm_bytes(self) -> bytes:
        """A teljes felvétel bájtokban. FIGYELEM: ez a HOSSZTÓL függő memóriát
        igényel; hosszú felvételnél a `pcm_path()`/`save()` a helyes út."""
        self._flush()
        if not self._spill or not os.path.exists(self._spill):
            return b""
        with open(self._spill, "rb") as f:
            return f.read()

    def _write_wav(self, path: str):
        """WAV írása a lemezen lévő nyers PCM-ből, STREAMELVE (a teljes hang
        nem kerül egyszerre a memóriába)."""
        self._flush()
        write_wav_from_pcm_file(path, self._spill, self.freq, self.channels)

    def save(self, path: str, *, normalize: bool = False, fade_ms: int = 0,
             trim_silence: bool = False, out_freq: int = 0,
             mp3_bitrate: str = "256k", progress=None) -> str:
        """A felvétel mentése. A forrás a LEMEZEN lévő nyers PCM, így egy 8 órás
        felvétel sem kerül teljes egészében a memóriába. [REC-P0-01/02]"""
        if not self.has_audio():
            raise RuntimeError("Nincs felvett hang a mentéshez.")
        return save_pcm_file(path, self.pcm_path(), self.freq, self.channels,
                             normalize=normalize, fade_ms=fade_ms,
                             trim_silence=trim_silence, out_freq=out_freq,
                             mp3_bitrate=mp3_bitrate, progress=progress)
