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


def _tone(freq: float, dur: float) -> bytes:
    n = int(RATE * dur)
    att, rel = int(0.01 * RATE), int(0.03 * RATE)
    out = bytearray()
    for i in range(n):
        env = 1.0
        if i < att:
            env = i / att
        elif i > n - rel:
            env = max(0.0, (n - i) / rel)
        s = math.sin(2 * math.pi * freq * i / RATE) * env * 0.35
        out += struct.pack("<h", int(s * 32767))
    return bytes(out)


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
