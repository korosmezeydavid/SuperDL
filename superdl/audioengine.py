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

    def play(self, url: str, title: str = "", progress=None) -> None:
        """A megadott forrás lejátszása az elejétől (az előzőt leállítja)."""
        self.stop()
        self.title = title or url
        ff = _ffmpeg_exe(progress)
        if not ff:
            self._emit("hiba: az ffmpeg nem érhető el")
            return
        self._stop = threading.Event()
        self._paused.clear()
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        cmd = [ff, "-nostdin", "-i", url, "-f", "s16le", "-ar", str(RATE),
               "-ac", str(CHANNELS), "-loglevel", "quiet", "-"]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    creationflags=flags)
        except Exception as e:
            self._emit(f"hiba: {e}")
            return
        with self._lock:
            self._proc = proc
        self._thread = threading.Thread(target=self._feed, args=(proc,),
                                        daemon=True)
        self._thread.start()

    # ---- belső --------------------------------------------------------

    def _emit(self, text: str) -> None:
        if self.on_state:
            try:
                self.on_state(text)
            except Exception:
                pass

    def _feed(self, proc) -> None:
        import numpy as np
        import sounddevice as sd
        try:
            stream = sd.RawOutputStream(samplerate=RATE, channels=CHANNELS,
                                        dtype="int16", blocksize=2048)
            stream.start()
        except Exception as e:
            self._emit(f"hiba: nincs hangkimenet ({e})")
            return
        self._emit("lejátszás")
        started = False
        try:
            while not self._stop.is_set():
                if self._paused.is_set():
                    time.sleep(0.05)
                    continue
                raw = proc.stdout.read(4096)
                if not raw:
                    break
                started = True
                v = self._volume
                if v >= 0.999:
                    stream.write(raw)
                else:
                    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
                    stream.write((a * v).astype(np.int16).tobytes())
        except Exception:
            pass
        finally:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        if not self._stop.is_set():
            self._emit("vége" if started else
                       "hiba: a forrás nem játszható le")
