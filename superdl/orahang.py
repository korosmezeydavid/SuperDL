"""Beszélő óra HANGRÉTEGE: eSpeak-hangváltozatok + SORBA ÁLLÍTOTT bemondás.

MIÉRT KÜLÖN A `selfvoice`-TÓL. A `selfvoice.speak()` a letöltési üzenetekre
készült, és ott HELYESEN viselkedik: az új bemondás LEÁLLÍTJA az előzőt
(`_speak_espeak` → `terminate()`), hogy a hang ne torlódjon. Az óránál és
főleg a PÁRHUZAMOS IDŐZÍTŐKNÉL ez katasztrófa: két egyszerre lejáró időzítő
közül az elsőt a második félbevágná, és a felhasználó a fontosabbat nem
hallaná meg. Ezért itt SOR van: a bemondások egymás UTÁN mennek.

MÉRT TÉNYEK (2026-09-20, a repó saját bin/espeak-ng.exe-jével):
  • a 22 kiválasztott változat mind KÜLÖNBÖZŐ hangot ad (WAV-lenyomatok
    egyenként eltérnek) – a `hu+<változat>` alak működik;
  • ⚠️ a NEM LÉTEZŐ változat NEM hiba: az eSpeak rc=0-val, NÉMÁN visszaesik
    az alaphangra. Ezért a változat nevét MI ellenőrizzük a `!v` mappából –
    az eSpeak-re hagyatkozni néma hibát jelentene;
  • egy tipikus bemondás („A pontos idő tizenegy óra húsz perc") ~2,5 mp.
"""

from __future__ import annotations

import logging
import os
import queue
import subprocess
import threading
import time
from pathlib import Path

_log = logging.getLogger("superdl.orahang")
_NOWIN = 0x08000000 if os.name == "nt" else 0

# Dávid válogatása (2026-09-19): napi szinten használt, magyarul jól szóló
# eSpeak-változatok. A mappában mind a 22 ott van a repó bin/-jében.
# (név a !v mappában, felolvasható címke)
KESZLET: list[tuple[str, str]] = [
    ("", "eSpeak magyar – alap"),
    ("robert", "Robert (férfi)"),
    ("rob", "Rob (férfi)"),
    ("max", "Max (férfi)"),
    ("Michael", "Michael (férfi)"),
    ("Denis", "Denis (férfi)"),
    ("Diogo", "Diogo (férfi)"),
    ("michel", "Michel (férfi)"),
    ("boris", "Boris (férfi)"),
    ("klatt2", "Klatt 2 (gépies)"),
    ("m1", "Férfi 1"), ("m2", "Férfi 2"), ("m3", "Férfi 3"), ("m4", "Férfi 4"),
    ("m5", "Férfi 5"), ("m6", "Férfi 6"), ("m7", "Férfi 7"), ("m8", "Férfi 8"),
    ("f1", "Női 1"), ("f2", "Női 2"), ("f3", "Női 3"), ("f4", "Női 4"),
    ("f5", "Női 5"),
]
ALAP_VALTOZAT = "f1"

# a sor felső határa: ennél több várakozó bemondásnál az ÚJ, nem sürgős
# bemondást eldobjuk. Öt bemondás ~12 mp beszéd; ennél hosszabb torlódás
# már nem információ, hanem zaj.
SOR_MAX = 5


def valtozatok_mappa() -> Path | None:
    """A `!v` mappa a beépített eSpeak mellett, vagy None."""
    from . import selfvoice
    _, data = selfvoice._espeak_paths()
    if not data:
        return None
    d = Path(data) / "voices" / "!v"
    return d if d.is_dir() else None


def letezo_valtozatok() -> set[str]:
    """A TÉNYLEGESEN meglévő változatnevek (kisbetűsítve az összevetéshez).
    Az üres név (alaphang) mindig érvényes."""
    d = valtozatok_mappa()
    if d is None:
        return set()
    try:
        return {f.name.lower() for f in d.iterdir() if f.is_file()}
    except OSError:
        return set()


def ervenyes(valtozat: str) -> bool:
    """Van-e ilyen nevű eSpeak-változat? Üres név = alaphang = érvényes.
    ⚠️ Ez a NÉMA VISSZAESÉS elleni védelem: az eSpeak magától nem szól."""
    if not valtozat:
        return True
    van = letezo_valtozatok()
    if not van:                    # nincs mappa (pl. teszt) – ne akadályozzunk
        return True
    return valtozat.lower() in van


def keszlet(mind: bool = False) -> list[tuple[str, str]]:
    """A hangválasztóba kínált lista. `mind=False`: Dávid 22-es készlete,
    csak azok, amik tényleg megvannak. `mind=True`: a mappa ÖSSZES változata
    (a készlet elöl, a többi utána, ábécérendben)."""
    van = letezo_valtozatok()
    alap = [(n, c) for n, c in KESZLET if not n or not van or n.lower() in van]
    if not mind:
        return alap
    benne = {n.lower() for n, _ in alap}
    d = valtozatok_mappa()
    tobbi = []
    if d is not None:
        try:
            tobbi = sorted((f.name for f in d.iterdir()
                            if f.is_file() and f.name.lower() not in benne),
                           key=str.lower)
        except OSError:
            tobbi = []
    return alap + [(n, n) for n in tobbi]


def cimke(valtozat: str) -> str:
    """A változat felolvasható neve (ismeretlennél maga a név)."""
    for n, c in KESZLET:
        if n == valtozat:
            return c
    return valtozat or "alap"


class Bemondas:
    """Egy sorba állított bemondás."""

    __slots__ = ("szoveg", "valtozat", "jingle", "surgos")

    def __init__(self, szoveg, valtozat="", jingle=False, surgos=False):
        self.szoveg = szoveg
        self.valtozat = valtozat or ""
        self.jingle = bool(jingle)
        self.surgos = bool(surgos)


class Beszelo:
    """SORBA ÁLLÍTOTT bemondó: egyszerre EGY szöveg szól, a többi vár.

    A `selfvoice`-szal ellentétben SOHA nem vágja félbe az előzőt. A
    `leallit()` az egyetlen kivétel (kilépés, kikapcsolás).
    """

    def __init__(self, *, rate: int = 0, pitch: int = 0, volume: int = 100,
                 kepernyoolvaso: bool = False):
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        self.kepernyoolvaso = bool(kepernyoolvaso)
        self._sor: queue.Queue = queue.Queue()
        self._proc = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._szal = threading.Thread(target=self._fut, daemon=True,
                                      name="superdl-orahang")
        self._szal.start()

    # ---- kívülről hívható ------------------------------------------

    def beallit(self, *, rate=None, pitch=None, volume=None,
                kepernyoolvaso=None) -> None:
        if rate is not None:
            self.rate = max(-10, min(10, int(rate)))
        if pitch is not None:
            self.pitch = max(-10, min(10, int(pitch)))
        if volume is not None:
            self.volume = max(0, min(100, int(volume)))
        if kepernyoolvaso is not None:
            self.kepernyoolvaso = bool(kepernyoolvaso)

    @property
    def varakozok(self) -> int:
        return self._sor.qsize()

    def mond(self, szoveg: str, valtozat: str = "", *, jingle: bool = False,
             surgos: bool = False) -> bool:
        """Bemondás a sor VÉGÉRE. `surgos=True` (időzítő lejárt) akkor is
        bekerül, ha a sor tele van – a periodikus időbemondás nem.
        Visszaad: bekerült-e."""
        if not szoveg or self._stop.is_set():
            return False
        if not surgos and self._sor.qsize() >= SOR_MAX:
            _log.info("a bemondás sora tele (%d), kihagyva: %r",
                      self._sor.qsize(), szoveg[:40])
            return False
        self._sor.put(Bemondas(szoveg, valtozat, jingle, surgos))
        return True

    def leallit(self) -> None:
        """A sor kiürítése és a FUTÓ bemondás megszakítása (kilépéskor)."""
        try:
            while True:
                self._sor.get_nowait()
        except queue.Empty:
            pass
        self._proc_megallit()

    def kikapcsol(self) -> None:
        """Végleges leállítás (a szál kilép)."""
        self._stop.set()
        self.leallit()
        self._sor.put(None)          # a szál felébresztése

    # ---- belül -----------------------------------------------------

    def _proc_megallit(self) -> None:
        with self._lock:
            p, self._proc = self._proc, None
        if p is not None and p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=2)
            except Exception:
                pass

    def _fut(self) -> None:
        while not self._stop.is_set():
            try:
                b = self._sor.get(timeout=0.5)
            except queue.Empty:
                continue
            if b is None:
                break
            try:
                self._egy(b)
            except Exception:
                _log.exception("bemondás közben hiba")

    def _egy(self, b: Bemondas) -> None:
        if b.jingle:
            self._jingle()
        if self.kepernyoolvaso:
            from . import screenreader
            # interrupt=False: a képernyőolvasó SAJÁT sorába fűzzük, nem
            # vágjuk félbe azt, amit épp olvas a felhasználónak
            if screenreader.speak(b.szoveg, False):
                return
            # ha nincs képernyőolvasó, essünk vissza az eSpeakre
        self._espeak(b)

    def _jingle(self) -> None:
        """Rövid, kétszótagú jel a bemondás ELŐTT. NEM óraütés: nem számol,
        mindig ugyanaz. A `sounds` szintetizálja, hangfájl nem kell."""
        from . import sounds
        try:
            sounds.play_ora_jingle()
        except Exception:
            return
        time.sleep(sounds.ORA_JINGLE_HOSSZ + 0.05)   # ne beszéljen bele

    def _espeak(self, b: Bemondas) -> None:
        from . import selfvoice
        exe, data = selfvoice._espeak_paths()
        if not exe:
            return
        valtozat = b.valtozat if ervenyes(b.valtozat) else ""
        if valtozat != b.valtozat:
            # ⚠️ NÉMA VISSZAESÉS HELYETT NAPLÓ: az eSpeak magától rc=0-t adna
            _log.warning("ismeretlen eSpeak-változat: %r – alaphanggal szól",
                         b.valtozat)
        hang = "hu+" + valtozat if valtozat else "hu"
        wpm = max(80, min(320, 175 + self.rate * 12))
        pitch = max(0, min(99, 50 + self.pitch * 4))
        amp = max(0, min(200, int(self.volume * 2)))
        cmd = [exe, "-v", hang, "-s", str(wpm), "-p", str(pitch),
               "-a", str(amp)]
        if data:
            cmd += ["--path", str(Path(data).parent)]
        cmd.append(b.szoveg)
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL,
                                 creationflags=_NOWIN)
        except OSError:
            _log.exception("az eSpeak indítása nem sikerült")
            return
        with self._lock:
            self._proc = p
        try:
            p.wait(timeout=60)       # MEGVÁRJUK: ettől sor ez, nem torlódás
        except Exception:
            self._proc_megallit()
        finally:
            with self._lock:
                if self._proc is p:
                    self._proc = None
