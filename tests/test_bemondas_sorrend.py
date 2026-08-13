# -*- coding: utf-8 -*-
"""A BEMONDÁS-SORREND szabálya (2026-08-13, Laci P2P-jelzéséből).

A modulok `_speak/_say/_mondd` segédeiben KÖTELEZŐ sorrend:
  1) ELŐSZÖR a KÉPERNYŐOLVASÓ (screenreader.speak) – mert képernyőolvasó-módban
     a Core a saját hangot NÉMÍTJA (muted=True) ÉPP AZÉRT, hogy az olvasó
     beszéljen. Ha a némítás-ellenőrzés előrébb lenne, a bemondás NÉMA maradna
     (ez okozta, hogy a P2P-nél az F8 nem mondott semmit).
  2) csak UTÁNA a `muted` vizsgálat és a beépített (eSpeak/SAPI) hang.

Ez a teszt forrás-szinten őrzi a sorrendet minden modulban."""
import pathlib
import re

GYOKER = pathlib.Path(__file__).resolve().parent.parent / "modules_src"


def test_a_kepernyoolvaso_megelozi_a_nemitas_ellenorzest():
    hibas = []
    for p in GYOKER.rglob("*.py"):
        s = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"speak\([^)]*force=True", s):
            elott = s[max(0, m.start() - 1400):m.start()]
            sr = elott.rfind("screenreader")
            muted = elott.rfind('getattr(sv, "muted"')
            # a `rfind` a hívás ELŐTTI szövegben keres: a HELYES sorrendben a
            # screenreader ELŐBB van, a muted-ellenőrzés KÖZELEBB a híváshoz
            if sr < 0:
                hibas.append("%s:%d – nincs képernyőolvasó-próbálkozás"
                             % (p.name, s[:m.start()].count("\n") + 1))
            elif 0 <= muted < sr:
                hibas.append("%s:%d – a némítás-ellenőrzés MEGELŐZI a "
                             "képernyőolvasót" % (p.name,
                                                  s[:m.start()].count("\n") + 1))
    assert not hibas, "Rossz bemondás-sorrend:\n" + "\n".join(hibas)
