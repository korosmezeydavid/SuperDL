"""Apró hanghatások (earconok) az eseményekhez.

A hangokat a program MAGA állítja elő: rövid, burkológörbével ellátott
szinusz-hangokból szintetizálja, WAV-ba írja a ~/.superdl/sounds mappába,
és a Windows beépített winsound moduljával játssza le – aszinkron, hogy ne
akassza a felületet. Nincs külső függőség, és nem kell hangfájlt csomagolni.

Earconok:
  results – találati lista megjelenése (két felfutó hang)
  start   – letöltés indul (egy lágy hang)
  done    – letöltés kész (kellemes felfutó kvint)
  error   – hiba (mély, leszálló hang)
"""

import math
import struct
import threading
import wave
from pathlib import Path

try:
    import winsound
except ImportError:
    winsound = None

SOUND_DIR = Path.home() / ".superdl" / "sounds"
RATE = 44100

# eseményenként (frekvencia Hz, hossz másodperc) szekvenciák
EARCONS = {
    "results": [(880, 0.07), (1319, 0.10)],
    "start":   [(587, 0.10)],
    "done":    [(784, 0.08), (1047, 0.13)],
    "error":   [(440, 0.12), (311, 0.18)],
}

_ready = False
_lock = threading.Lock()


def _tone(freq: float, dur: float, amp: float = 0.35) -> bytes:
    n = int(RATE * dur)
    att, rel = int(0.01 * RATE), int(0.03 * RATE)
    out = bytearray()
    for i in range(n):
        env = 1.0
        if i < att:
            env = i / att
        elif i > n - rel:
            env = max(0.0, (n - i) / rel)
        s = math.sin(2 * math.pi * freq * i / RATE) * env * amp
        out += struct.pack("<h", int(s * 32767))
    return bytes(out)


# ---- százalék-pittyegés (hosszú folyamatokhoz) --------------------------
# minden lépésnél (alapból 2%) egy eggyel MAGASABB rövid hang, 0→100% között
_progress = {"enabled": True, "amp": 0.30, "step": 2}


def set_progress(enabled=None, amp=None, step=None) -> None:
    """A pittyegés testreszabása (a beállítási fülről). Az amplitúdó vagy a
    lépésköz változásakor a gyorsítótár-WAV-okat töröljük, hogy újragenerálódjanak."""
    clear = False
    if enabled is not None:
        _progress["enabled"] = bool(enabled)
    if amp is not None and abs(float(amp) - _progress["amp"]) > 1e-3:
        _progress["amp"] = max(0.0, min(1.0, float(amp)))
        clear = True
    if step is not None and int(step) != _progress["step"]:
        _progress["step"] = max(1, min(20, int(step)))
    if clear:
        try:
            for f in SOUND_DIR.glob("prog_*.wav"):
                f.unlink()
        except OSError:
            pass


def progress_enabled() -> bool:
    return bool(_progress["enabled"])


def _progress_freq(step_idx: int) -> float:
    # 0..50 lépés -> kb. 440..1340 Hz, monoton emelkedő
    return 440.0 + (max(0, min(50, step_idx)) / 50.0) * 900.0


def progress_beep(percent: float) -> None:
    """Egy rövid hang, amelynek magassága a százalékhoz kötött (magasabb =
    előrébb). Csak akkor szól, ha a pittyegés be van kapcsolva."""
    if not _progress["enabled"] or winsound is None:
        return
    idx = max(0, min(50, int(percent) // 2))
    f = SOUND_DIR / f"prog_{idx:02d}.wav"
    try:
        if not f.exists():
            SOUND_DIR.mkdir(parents=True, exist_ok=True)
            data = _tone(_progress_freq(idx), 0.06, amp=_progress["amp"])
            with wave.open(str(f), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(RATE)
                w.writeframes(data)
        winsound.PlaySound(str(f), winsound.SND_FILENAME
                           | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass


class ProgressBeeper:
    """Állapotkövető: csak akkor pittyeg, amikor a százalék átlép egy
    `step` (alapból 2) határt – így 0→100% alatt kb. 50 emelkedő hang szól."""

    def __init__(self, step: int | None = None):
        self.step = step or _progress["step"]
        self._last = -1

    def reset(self) -> None:
        self._last = -1

    def update(self, percent: float) -> None:
        q = int(percent) // max(1, self.step)
        if q != self._last:
            self._last = q
            progress_beep(q * self.step)


def _ensure() -> None:
    SOUND_DIR.mkdir(parents=True, exist_ok=True)
    for name, seq in EARCONS.items():
        f = SOUND_DIR / f"{name}.wav"
        if f.exists():
            continue
        data = b"".join(_tone(fr, du) for fr, du in seq)
        with wave.open(str(f), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(data)


def play(name: str) -> None:
    """A megadott earcon lejátszása (aszinkron). Ismeretlen név vagy hiányzó
    winsound esetén csendben nem csinál semmit."""
    global _ready
    if winsound is None or name not in EARCONS:
        return
    try:
        with _lock:
            if not _ready:
                _ensure()
                _ready = True
        f = SOUND_DIR / f"{name}.wav"
        if f.exists():
            winsound.PlaySound(str(f), winsound.SND_FILENAME
                               | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass
