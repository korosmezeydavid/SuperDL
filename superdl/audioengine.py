"""Streaming hangmotor: az ffmpeg dekódolja a forrást (élő stream vagy
fájl), a sounddevice pedig megszólaltatja. Sample-szintű hangerő- és
szünet-vezérlés. Ezzel az élő internetes rádió is megbízhatóan szól, amit a
beépített wx.media lejátszó nem tudott.

A hangerőt menet közben, a hangmintákra alkalmazzuk (numpy), így nincs
szükség a stream újraindítására.
"""

import os
import subprocess
import threading
import time

from .ffmpeg import ensure_ffmpeg, find_ffmpeg

RATE = 44100
CHANNELS = 2


def _ffmpeg_exe(progress=None) -> str | None:
    p = find_ffmpeg()
    if not p:
        d = ensure_ffmpeg(progress)
        p = find_ffmpeg() if d else None
    if not p:
        return None
    if p.lower().endswith("ffmpeg.exe"):
        return p
    return os.path.join(p, "ffmpeg.exe")


class Player:
    """Egy időben egy forrást játszik. A `on_state(szöveg)` visszahívás az
    állapotváltozásokat jelzi (lejátszás / vége / hiba)."""

    def __init__(self):
        self._proc = None
        self._thread = None
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._volume = 0.7
        self._lock = threading.Lock()
        self.on_state = None
        self.title = ""
        self._played = 0           # eddig megszólaltatott PCM-bájtok száma
        self._url = ""             # az aktuális forrás (a seek-hez)
        self._start_offset = 0.0   # a lejátszás kezdő-időpontja (seek után)
        # LEJÁTSZÁS-GENERÁCIÓ: minden play() új generációt kap; a régi _feed szál
        # a SAJÁT stop_eventjét és generációját figyeli, és csak akkor küld
        # állapotot, ha a generációja még az aktuális. Enélkül a gyors stop+play
        # (pl. seek) után a régi szál a KÖZÖS self._stop új, üres eseményét látná,
        # és HAMIS „vége"/„hiba"-t küldene az ÚJ lejátszásra (a felolvasóban ez
        # állította le a felirat-narrációt tekeréskor). [Herman Tibor: AUDIO-03]
        self._generation = 0

    # ---- állapot ------------------------------------------------------

    @property
    def volume(self) -> float:
        return self._volume

    def set_volume(self, v: float) -> None:
        self._volume = max(0.0, min(1.0, v))

    def is_active(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def is_paused(self) -> bool:
        return self._paused.is_set()

    def position(self) -> float:
        """A pillanatnyi lejátszási pozíció másodpercben (a ténylegesen
        megszólaltatott hangminták + a seek-kezdőpont alapján; szünetben
        nem nő)."""
        return self._start_offset + self._played / (RATE * CHANNELS * 2)

    # ---- vezérlés -----------------------------------------------------

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    def toggle_pause(self) -> bool:
        """Visszaadja: True, ha most szünetel."""
        if self._paused.is_set():
            self._paused.clear()
        else:
            self._paused.set()
        return self._paused.is_set()

    def seek(self, pos: float) -> None:
        """Ugrás a megadott időpontra (a forrást a `-ss`-szel újraindítja)."""
        if self._url:
            self.play(self._url, self.title, start=max(0.0, pos))

    def relative_seek(self, delta: float) -> None:
        """Léptetés az aktuális pozícióhoz képest (finomhangoláshoz)."""
        self.seek(max(0.0, self.position() + delta))

    def stop(self) -> None:
        self._stop.set()
        self._paused.clear()
        with self._lock:
            p, self._proc = self._proc, None
        if p:
            try:
                p.kill()
            except Exception:
                pass

    def play(self, url: str, title: str = "", progress=None,
             start: float = 0.0, audio_track: int | None = None) -> None:
        """A megadott forrás lejátszása (az előzőt leállítja). `start`>0 esetén
        onnan kezd (seek, az ffmpeg `-ss`-ével). `audio_track` megadva a több
        hangsávos adásból azt a sávot játssza (pl. hangalámondás)."""
        self.stop()
        self.title = title or url
        self._url = url
        ff = _ffmpeg_exe(progress)
        if not ff:
            self._emit("hiba: az ffmpeg nem érhető el")
            return
        self._stop = threading.Event()
        self._generation += 1
        gen = self._generation
        self._paused.clear()
        self._played = 0
        self._start_offset = max(0.0, float(start))
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        cmd = [ff, "-nostdin"]
        if self._start_offset > 0:
            cmd += ["-ss", f"{self._start_offset:.3f}"]
        cmd += ["-i", url]
        if audio_track is not None:
            cmd += ["-map", f"0:a:{int(audio_track)}"]
        cmd += ["-f", "s16le", "-ar", str(RATE),
                "-ac", str(CHANNELS), "-loglevel", "quiet", "-"]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    creationflags=flags)
        except Exception as e:
            self._emit(f"hiba: {e}")
            return
        with self._lock:
            self._proc = proc
        self._thread = threading.Thread(
            target=self._feed, args=(proc, self._stop, gen), daemon=True)
        self._thread.start()

    # ---- belső --------------------------------------------------------

    def _emit_gen(self, gen: int, text: str) -> None:
        """Állapot kiadása CSAK akkor, ha a hívó szál generációja még az aktuális
        – így a régi (leváltott) lejátszószál nem küld HAMIS állapotot az újra."""
        if gen == self._generation:
            self._emit(text)

    def _emit(self, text: str) -> None:
        if self.on_state:
            try:
                self.on_state(text)
            except Exception:
                pass

    def _feed(self, proc, stop_event, gen) -> None:
        # FONTOS: a szál KIZÁRÓLAG a saját `stop_event`-jét figyeli (nem a közös
        # self._stop-ot), és `gen`-en át küld állapotot – így egy leváltott régi
        # szál nem küld HAMIS állapotot az új lejátszásra. [Herman Tibor AUDIO-03]
        import numpy as np
        import sounddevice as sd
        try:
            stream = sd.RawOutputStream(samplerate=RATE, channels=CHANNELS,
                                        dtype="int16", blocksize=2048)
            stream.start()
        except Exception as e:
            self._emit_gen(gen, f"hiba: nincs hangkimenet ({e})")
            return
        self._emit_gen(gen, "lejátszás")
        started = False
        failed = False
        err_msg = ""
        try:
            while not stop_event.is_set():
                if self._paused.is_set():
                    time.sleep(0.05)
                    continue
                raw = proc.stdout.read(4096)
                if not raw:
                    break
                started = True
                if gen == self._generation:      # a pozíciót csak az AKTUÁLIS
                    self._played += len(raw)      # lejátszás számolja
                v = self._volume
                if v >= 0.999:
                    stream.write(raw)
                else:
                    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
                    stream.write((a * v).astype(np.int16).tobytes())
        except Exception as exc:
            failed = True
            err_msg = str(exc)
        finally:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        if not stop_event.is_set():
            if failed and started:
                self._emit_gen(gen, f"hiba: lejátszás megszakadt – {err_msg}")
            elif failed:
                self._emit_gen(gen, "hiba: a forrás nem játszható le")
            else:
                self._emit_gen(gen, "vége" if started else
                               "hiba: a forrás nem játszható le")
