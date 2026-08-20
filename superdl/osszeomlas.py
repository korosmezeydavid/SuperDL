# -*- coding: utf-8 -*-
"""ÖSSZEOMLÁS-NAPLÓ: ha a program „csak úgy kilép”, maradjon nyoma.

Miért kell: egy felhasználó azt jelezte, hogy a médiakonvertálóban, amikor a
fájlválasztóban megnyit egy könyvtárat, a program KILÉP. Ilyenkor nem Python-
hiba történik (azt elkapnánk és kimondanánk), hanem a folyamat natívan
összeomlik – tipikusan egy külső, a Windows fájlválasztójába beépülő
bővítmény (kodek-csomag, felhő-szinkron, vírusirtó) miatt. Ezt eddig
semmiből nem lehetett kideríteni: a program eltűnt, és kész.

A `faulthandler` pont ilyenkor segít: a natív összeomlás pillanatában kiírja,
melyik Python-sornál járt a program. Ebből kiderül, hogy a saját kódunkban
vagy egy külső rétegben (pl. a fájlválasztó megnyitásában) történt-e a baj.

A napló a felhasználó gépén marad, és NEM tartalmaz személyes adatot: csak
függvény- és fájlneveket a mi kódunkból.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

NAPLO = Path.home() / ".superdl" / "osszeomlas.log"
_fajl = None


def bekapcsol() -> bool:
    """Indításkor hívjuk. Igaz, ha sikerült bekapcsolni."""
    global _fajl
    if _fajl is not None:
        return True
    try:
        import faulthandler
        NAPLO.parent.mkdir(parents=True, exist_ok=True)
        # „a" mód: a korábbi összeomlások is megmaradnak, hogy össze lehessen
        # hasonlítani őket
        _fajl = open(NAPLO, "a", encoding="utf-8", errors="replace")
        _fajl.write("\n=== SuperDL indult: %s (verzió: %s) ===\n"
                    % (time.strftime("%Y-%m-%d %H:%M:%S"), _verzio()))
        _fajl.flush()
        faulthandler.enable(file=_fajl, all_threads=True)
        return True
    except Exception:
        _fajl = None
        return False


def _verzio() -> str:
    try:
        from . import __version__
        return str(__version__)
    except Exception:
        return "ismeretlen"


def jegyzet(szoveg: str) -> None:
    """Nyom hagyása a naplóban KOCKÁZATOS művelet előtt.

    Így ha a program pont ott omlik össze, a napló utolsó sorából kiderül,
    mit csinált éppen – akkor is, ha a natív hiba nem hagy Python-vermet."""
    if _fajl is None:
        return
    try:
        _fajl.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), szoveg))
        _fajl.flush()
        os.fsync(_fajl.fileno())        # összeomláskor is legyen kiírva
    except Exception:
        pass


def naplo_szoveg(sorok: int = 200) -> str:
    """A napló vége – a diagnosztikai ablakhoz és a hibajelentéshez."""
    try:
        with open(NAPLO, encoding="utf-8", errors="replace") as f:
            tartalom = f.readlines()
    except OSError:
        return ""
    return "".join(tartalom[-int(sorok):])


def volt_osszeomlas() -> bool:
    """Van-e a naplóban natív összeomlás nyoma? (A faulthandler ezt a fejlécet
    írja ki.)"""
    sz = naplo_szoveg(400)
    return ("Windows fatal exception" in sz or "Fatal Python error" in sz
            or "Current thread" in sz)
