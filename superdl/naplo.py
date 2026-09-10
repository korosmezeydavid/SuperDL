# -*- coding: utf-8 -*-
"""ALKALMAZÁS-NAPLÓ: ami eddig a semmibe ment.

**Miért kellett.** A program tele van `_log.exception(...)` hívásokkal —
köztük PONT ott, ahol egy letöltés elhasal (`manager._run_job`). Csakhogy a
`logging`-hoz SOHA nem volt hozzárendelve kezelő: se fájl, se konzol. Vagyis
minden ilyen sor a semmibe íródott. A program szorgalmasan naplózott egy nem
létező naplóba.

Ez Karcsi jelentésénél derült ki (2026-09-09). Ő azt írta: „nem tudod meg,
hogy a hiba miért keletkezett". Igaza volt, és a helyzet rosszabb volt, mint
gondoltuk: nem arról volt szó, hogy a hibát nem KÜLDJÜK el — arról, hogy
sehol nem is JEGYEZTÜK FEL. A hibajelentés azért volt hiányos, mert nem volt
mit csatolnia.

**Mi ez, és mi NEM.** Ez a modul a Python-oldali eseményeket és kivételeket
gyűjti. A natív összeomlás (amikor a folyamat maga hal meg, Python-hiba
nélkül) továbbra is az `osszeomlas.py` dolga, a `faulthandler`-rel — a kettő
más jelenséget fog meg, ezért maradnak külön fájlban.

**Amit ide írunk, azt a felhasználó elküldi nekünk**, tehát ugyanaz a
szabály, mint a diagnosztikánál: személyes adat és titok nem való bele. A
`diagnostics` a beillesztés előtt még egyszer maszkol is.
"""

from __future__ import annotations

import logging
import logging.handlers
import platform
import sys
import threading
import time
from pathlib import Path

FAJL = Path.home() / ".superdl" / "naplo.txt"
# 2 MB × 3 fájl: elég ahhoz, hogy egy tegnapi hiba is meglegyen, de nem nő
# a végtelenségig a felhasználó gépén.
MERET = 2 * 1024 * 1024
PELDANYOK = 2

_bekapcsolva = False
_lock = threading.Lock()


def bekapcsol() -> bool:
    """Indításkor hívandó. Igaz, ha sikerült.

    Kétszer hívva nem csinál semmit: két kezelő mindent kétszer írna le, és
    a napló feleannyi időt fogna át — észrevétlenül."""
    global _bekapcsolva
    with _lock:
        if _bekapcsolva:
            return True
        try:
            FAJL.parent.mkdir(parents=True, exist_ok=True)
            kezelo = logging.handlers.RotatingFileHandler(
                FAJL, maxBytes=MERET, backupCount=PELDANYOK,
                encoding="utf-8", errors="replace")
            kezelo.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"))
            gyoker = logging.getLogger()
            # A GYÖKÉRRE csak a figyelmeztetéstől fölfelé: a yt-dlp és a
            # requests INFO-szinten annyit beszél, hogy percek alatt
            # kiforgatná a naplóból a mi sorainkat — vagyis pont azt tüntetné
            # el, amiért az egészet csináljuk.
            gyoker.setLevel(logging.WARNING)
            gyoker.addHandler(kezelo)
            # A SAJÁT naplónk INFO-tól: a „hálózat elment, várakozás" típusú
            # sorok nem hibák, de egy hibajelentésnél ezek mondják el, mi
            # vezetett odáig.
            sajat = logging.getLogger("superdl")
            sajat.setLevel(logging.INFO)
            _bekapcsolva = True
            _fejlec()
            _kivetelek_elkapasa()
            return True
        except Exception:
            return False


def _fejlec() -> None:
    """Minden indulás elején egy elválasztó sor. Enélkül nem lehet megmondani,
    hogy két bejegyzés ugyanabból a munkamenetből való-e — a hibakeresésnél
    pedig épp ez a legfontosabb kérdés."""
    try:
        from . import __version__
        verzio = str(__version__)
    except Exception:
        verzio = "ismeretlen"
    logging.getLogger("superdl").info(
        "=== SuperDL %s indult · %s · Python %s ===",
        verzio, platform.platform(), platform.python_version())


def _kivetelek_elkapasa() -> None:
    """Az ELKAPATLAN kivételek is a naplóba kerüljenek — a háttérszálakéi is.

    ⚠️ A `threading.excepthook` külön kell: a `sys.excepthook` CSAK a fő
    szálra vonatkozik. A letöltéseink viszont mind háttérszálon futnak, tehát
    pont az a hiba maradt volna néma, amiért az egészet csináljuk."""
    elozo = sys.excepthook

    def fo_szal(tipus, ertek, verem):
        try:
            logging.getLogger("superdl").critical(
                "ELKAPATLAN KIVÉTEL (fő szál)", exc_info=(tipus, ertek, verem))
        except Exception:
            pass
        elozo(tipus, ertek, verem)

    sys.excepthook = fo_szal

    elozo_szal = threading.excepthook

    def hatter_szal(args):
        try:
            logging.getLogger("superdl").critical(
                "ELKAPATLAN KIVÉTEL (%s szál)",
                getattr(args.thread, "name", "?"),
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        except Exception:
            pass
        elozo_szal(args)

    threading.excepthook = hatter_szal


def jegyez(szoveg: str, *args) -> None:
    """Rövid bejegyzés a naplóba. A hívónak nem kell logger-t szereznie."""
    try:
        logging.getLogger("superdl").info(szoveg, *args)
    except Exception:
        pass


def utolso_sorok(sorok: int = 300) -> str:
    """A napló vége — a hibajelentéshez.

    Csak az AKTUÁLIS fájlt olvassuk, a forgatott példányokat nem: a
    hibajelentés akkor hasznos, ha elolvasható, nem akkor, ha teljes."""
    try:
        with open(FAJL, encoding="utf-8", errors="replace") as f:
            tartalom = f.readlines()
    except OSError:
        return ""
    return "".join(tartalom[-int(sorok):])


def meret() -> int:
    """A napló mérete bájtban (0, ha még nincs)."""
    try:
        return FAJL.stat().st_size
    except OSError:
        return 0


def torol() -> bool:
    """A napló ürítése — ha a felhasználó ezt kéri. A forgatott példányokat is."""
    ok = True
    for p in [FAJL] + [FAJL.with_name(FAJL.name + ".%d" % i)
                       for i in range(1, PELDANYOK + 1)]:
        try:
            if p.exists():
                p.unlink()
        except OSError:
            ok = False
    if ok:
        jegyez("A naplót a felhasználó törölte (%s)",
               time.strftime("%Y-%m-%d %H:%M:%S"))
    return ok
