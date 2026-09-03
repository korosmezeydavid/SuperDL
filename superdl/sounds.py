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
    # MK5: a seedelés SAJÁT hangot kap. Eddig a készre töltött torrent
    # ugyanazt a „done" hangot szólaltatta meg, mint a lezárult letöltés –
    # holott az egyik VÉGET ért, a másik még fut és sávszélességet használ.
    # Vakon a hang az egyetlen különbség: szándékosan NEM felfutó (nem
    # lezárás), hanem egy visszatérő, nyitva hagyott kvint.
    "seed":    [(659, 0.09), (523, 0.09), (659, 0.11)],
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


# ---- ismeretlen méretű letöltés (MK8, az MK5 maradéka) -----------------
#
# Ha a szerver nem mondja meg a méretet, NINCS százalék – tehát nincs mihez
# kötni a hangmagasságot, és a `ProgressBeeper` néma marad. Vakon épp ilyenkor
# van a LEGKEVESEBB visszajelzés: se csík, se szám, se hang.
#
# A megoldás nem a hangmagasság, hanem a RITMUS: adatmennyiséghez kötött,
# AZONOS magasságú kattanás. Nem azt mondja meg, hol tartunk (azt nem tudjuk),
# hanem azt, hogy HALAD — és a sűrűsége érzékelteti, milyen gyorsan.

ADAG = 4 * 1024 * 1024                     # 4 MB-onként egy kattanás
_TIK_FREKVENCIA = 660.0


def tick() -> None:
    """Egyetlen halk kattanás – „még megy". Magassága ÁLLANDÓ: itt nincs
    előrehaladás, amit közölhetnénk, és egy emelkedő hang azt hazudná."""
    if not _progress["enabled"] or winsound is None:
        return
    f = SOUND_DIR / "tick.wav"
    try:
        if not f.exists():
            SOUND_DIR.mkdir(parents=True, exist_ok=True)
            data = _tone(_TIK_FREKVENCIA, 0.045,
                         amp=_progress["amp"] * 0.6)
            with wave.open(str(f), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(RATE)
                w.writeframes(data)
        winsound.PlaySound(str(f), winsound.SND_FILENAME
                           | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass


class MennyisegBeeper:
    """Ismeretlen méretű letöltés hangja: adagonként EGY kattanás.

    A `ProgressBeeper` párja arra az esetre, amikor nincs százalék. Nem a
    haladás MÉRTÉKÉT mondja (azt nem tudjuk), hanem azt, hogy VAN haladás —
    és ha elhallgat, az önmagában információ: elakadt."""

    def __init__(self, adag: int = ADAG):
        self.adag = max(1, int(adag))
        self._last = -1

    def reset(self) -> None:
        self._last = -1

    def update(self, letoltve: float) -> None:
        q = int(letoltve) // self.adag
        if q != self._last:
            elso = self._last < 0
            self._last = q
            # az ELSŐ hívásnál nem szólunk: az indulást a „start" earcon
            # már bemondta, és két hang egymás után zavaró
            if not elso and q > 0:
                tick()


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


def play_startup() -> None:
    """Az INDULÓ SZIGNÁL lejátszása (aszinkron). Sorrend: a felhasználó saját
    fájlja (~/.superdl/sounds/startup.wav), különben a BEÉPÍTETT szignál
    (superdl/startup.wav), végül egy kellemes szintetizált akkord. FÜGGETLEN a
    teljes némítástól – ez HANG, nem beszéd (Farkas kérése: némítva is legyen jel)."""
    if winsound is None:
        return
    try:
        user = SOUND_DIR / "startup.wav"                 # a felhasználó felülírhatja
        bundled = Path(__file__).resolve().parent / "startup.wav"
        f = None
        if user.is_file():
            f = user
        elif bundled.is_file():
            f = bundled
        else:                                            # szintetizált tartalék
            SOUND_DIR.mkdir(parents=True, exist_ok=True)
            f = SOUND_DIR / "startup_default.wav"
            if not f.exists():
                data = b"".join(_tone(fr, du) for fr, du in
                                [(523, 0.14), (659, 0.14), (784, 0.24)])  # C–E–G
                with wave.open(str(f), "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(RATE)
                    w.writeframes(data)
        if f and f.is_file():
            winsound.PlaySound(str(f), winsound.SND_FILENAME
                               | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass
