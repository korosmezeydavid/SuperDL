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


def save_pcm(path: str, pcm: bytes, freq: int, channels: int, *,
             normalize: bool = False, fade_ms: int = 0,
             trim_silence: bool = False, progress=None) -> str:
    """A felvevő ÉS a szerkesztő KÖZÖS mentője. A kiterjesztés dönt a formátumról
    (.wav/.mp3). Ha nincs utófeldolgozás ÉS WAV a cél → közvetlen írás; különben
    a Core ffmpeg-jével (normalizálás=EBU R128 loudnorm, fade=afade, csend-vágás=
    silenceremove az elejéről/végéről). Visszaadja a tényleges utat."""
    if not pcm:
        raise RuntimeError("Nincs hanganyag a mentéshez.")
    ext = Path(path).suffix.lower()
    want_mp3 = ext == ".mp3"
    if not (want_mp3 or normalize or fade_ms > 0 or trim_silence):
        write_wav_bytes(path, pcm, freq, channels)
        return path

    tmp = Path(tempfile.gettempdir()) / f"superrec_{os.getpid()}_{id(pcm)}.wav"
    write_wav_bytes(str(tmp), pcm, freq, channels)
    ff = ffmpeg_mod.find_ffmpeg()
    if not ff:
        ff_dir = ffmpeg_mod.ensure_ffmpeg(progress)
        ff = ffmpeg_mod.find_ffmpeg() if ff_dir else None
    if not ff:
        if not want_mp3:
            write_wav_bytes(path, pcm, freq, channels)
            tmp.unlink(missing_ok=True)
            return path
        tmp.unlink(missing_ok=True)
        raise RuntimeError("Az ffmpeg nem érhető el a feldolgozáshoz/MP3-hoz.")

    dur = len(pcm) / (freq * channels * 2) if (freq and channels) else 0.0
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

    cmd = [ff, "-y", "-i", str(tmp)]
    if filters:
        cmd += ["-af", ",".join(filters)]
    if want_mp3:
        cmd += ["-c:a", "libmp3lame", "-b:a", "256k"]
    cmd += [path]
    flags = 0x08000000 if os.name == "nt" else 0
    try:
        subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, creationflags=flags, check=True)
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


def decode_to_pcm(path: str, freq: int = 44100, channels: int = 2,
                  progress=None) -> bytes:
    """Tetszőleges hangfájl (WAV/MP3/M4A/…) dekódolása nyers 16 bites PCM-mé a
    Core ffmpeg-jével (a szerkesztőbe töltéshez)."""
    ff = ffmpeg_mod.find_ffmpeg()
    if not ff:
        ff_dir = ffmpeg_mod.ensure_ffmpeg(progress)
        ff = ffmpeg_mod.find_ffmpeg() if ff_dir else None
    if not ff:
        raise RuntimeError("Az ffmpeg nem érhető el a megnyitáshoz.")
    flags = 0x08000000 if os.name == "nt" else 0
    cmd = [ff, "-v", "error", "-i", path, "-f", "s16le",
           "-acodec", "pcm_s16le", "-ar", str(freq), "-ac", str(channels), "-"]
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
        self._chunks: list[bytes] = []
        self._bytes = 0
        self._lock = threading.Lock()
        self._paused = False
        self.recording = False
        self.peak = 0.0               # utolsó csúcs (0..1), a szintmérőhöz
        self.clipped = False          # volt-e telítés (csúcs ~1.0)

    # ---- felvétel ----------------------------------------------------

    def _callback(self, handle, buffer, length, user):
        if not self._paused and length:
            data = C.string_at(buffer, length)
            with self._lock:
                self._chunks.append(data)
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
        b = A._lib()
        if self.device not in A._rec_inited:
            if not b.BASS_RecordInit(self.device):
                if b.BASS_ErrorGetCode() != 14:        # 14 = már inicializálva
                    raise A.BassError(
                        "A felvevő eszköz nem indítható (kód "
                        f"{b.BASS_ErrorGetCode()}). Van csatlakoztatott mikrofon?")
            A._rec_inited.add(self.device)
        b.BASS_RecordSetDevice(self.device if self.device >= 0 else 0)
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

    def reset(self):
        """A felvett anyag eldobása (új felvételhez)."""
        self.stop()
        with self._lock:
            self._chunks = []
            self._bytes = 0
        self.peak = 0.0
        self.clipped = False

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

    def pcm_bytes(self) -> bytes:
        with self._lock:
            return b"".join(self._chunks)

    def _write_wav(self, path: str):
        write_wav_bytes(path, self.pcm_bytes(), self.freq, self.channels)

    def save(self, path: str, *, normalize: bool = False, fade_ms: int = 0,
             trim_silence: bool = False, progress=None) -> str:
        """A felvétel mentése (a közös `save_pcm`-en át)."""
        if not self.has_audio():
            raise RuntimeError("Nincs felvett hang a mentéshez.")
        return save_pcm(path, self.pcm_bytes(), self.freq, self.channels,
                        normalize=normalize, fade_ms=fade_ms,
                        trim_silence=trim_silence, progress=progress)
