# -*- coding: utf-8 -*-
"""Ár szerinti rendezésnél az a szám hangozzon el ELŐSZÖR, ami szerint a
lista rendezve van (Petrus József, 2026-09-27: „összekutyulódtak")."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "modules_src", "akciok"))

from akciok_mod.termek import Termek  # noqa: E402


def _elso_ar(sor: str) -> int:
    import re
    return int(re.search(r"(\d+) forint", sor).group(1))


def test_arrendben_a_kartyas_ar_all_elol_ha_az_olcsobb():
    t = Termek("Lidl", "Joghurt", ar=499, kartyas_ar=299,
               kartya_nev="Lidl Plus-szal")
    assert t.sor(True, True) == \
        "Joghurt, Lidl Plus-szal 299 forint, Lidl, kártya nélkül 499 forint"


def test_arrendben_a_hallott_elso_arak_novekvoek():
    termekek = [Termek("Lidl", "Joghurt A", ar=499, kartyas_ar=299),
                Termek("Penny", "Joghurt B", ar=350),
                Termek("Spar", "Joghurt C", ar=320, kartyas_ar=400),
                Termek("Aldi", "Joghurt D", kartyas_ar=310)]
    termekek.sort(key=lambda t: (t.legjobb_ar() is None, t.legjobb_ar() or 0))
    elsok = [_elso_ar(t.sor(True, True)) for t in termekek]
    assert elsok == sorted(elsok) == [299, 310, 320, 350]


def test_mas_rendezesnel_a_sor_valtozatlan():
    t = Termek("Lidl", "Joghurt", ar=499, kartyas_ar=299,
               kartya_nev="Lidl Plus-szal")
    assert t.sor(True) == \
        "Joghurt, 499 forint, Lidl, Lidl Plus-szal 299 forint"
    assert t.sor(True, False) == t.sor(True)
