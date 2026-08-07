# -*- coding: utf-8 -*-
"""Az élő tesztelői levél 5 észrevételének javításai (Szerencsekerék)."""
import importlib

import pytest

BASE = "modules_src.jatekok.jatekok_mod"
ONLINE = pytest.importorskip(BASE + ".szerencsekerek_online")
JR = importlib.import_module(BASE + ".jatekok")
U = importlib.import_module(BASE + ".jatekok._util")


def _host(jatekosok, kat="Teszt kategória", meg="alma és körte"):
    return ONLINE.OnlineHost(jatekosok, valaszto=lambda r: (kat, meg))


# ---- 1 + 2: kategória + szószám minden fordulóban ----
def test_fordulo_intro_kategoria_es_szoszam():
    h = _host(["A"])
    intro = h.fordulo_intro()
    assert "Teszt kategória" in intro
    assert "3 szóból áll" in intro          # "alma és körte" = 3 szó
    a = h.allapot("x")
    assert a["szavak"] == 3
    assert a["kategoria"] == "Teszt kategória"


def test_uj_fordulo_uzenet_tartalmazza_a_kategoriat():
    # egy körös játék helyett: kényszerítsük a megfejtést, és nézzük az új
    # forduló üzenetét (2 kör, hogy legyen következő)
    h = ONLINE.OnlineHost(["A"], korok=2,
                          valaszto=lambda r: ("Kat", "alma"))
    a = h.akcio("A", "megfejt", "alma")
    assert "Jön a(z) 2. forduló" in a["uzenet"]
    assert "Kategória:" in a["uzenet"] and "szóból áll" in a["uzenet"]


# ---- 5: már elhangzott betű ----
def test_mar_elhangzott_rossz_betu():
    h = _host(["A"])                         # megoldás: "alma és körte"
    h.utolso_porgetes = 100
    a1 = h.akcio("A", "betu", "b")           # 'b' nincs benne -> tévesztés
    assert "nincs a rejtvényben" in a1["uzenet"]
    assert "b" in h.mondott
    h.utolso_porgetes = 100
    a2 = h.akcio("A", "betu", "b")           # ISMÉT 'b' -> már elhangzott
    assert "már elhangzott" in a2["uzenet"]
    assert "nincs a rejtvényben" not in a2["uzenet"]


def test_mar_elhangzott_helyes_betu():
    h = _host(["A"])
    h.utolso_porgetes = 100
    a1 = h.akcio("A", "betu", "l")           # 'l' benne van (aLma)
    assert "l" in h.felfedett and "l" in h.mondott
    h.utolso_porgetes = 100
    a2 = h.akcio("A", "betu", "l")           # ISMÉT 'l' -> már elhangzott
    assert "már elhangzott" in a2["uzenet"]


def test_uj_fordulonal_a_mondott_nullazodik():
    h = ONLINE.OnlineHost(["A"], korok=2, valaszto=lambda r: ("Kat", "alma"))
    h.utolso_porgetes = 100
    h.akcio("A", "betu", "z")                # rossz betű -> mondott={'z'}
    assert "z" in h.mondott
    h.akcio("A", "megfejt", "alma")          # megfejt -> új forduló
    assert h.mondott == set()                # az új fordulóban nulláról


# ---- 4 + 2 (helyi): a helyi játék ctx.tabla-t ad, és mondja a szószámot ----
def test_helyi_jatek_tablat_es_szoszamot_ad():
    gen = JR.REGISZTER["szerencsekerek"](U.Ctx())
    valaszok = iter(["1", "Teszt", "0"])     # 1 ember, név, 0 gép
    cmds = []
    send = None
    for _ in range(60):
        try:
            cmd = gen.send(send)
        except StopIteration:
            break
        cmds.append(cmd)
        send = None
        if cmd[0] in ("kerdez", "abcstop"):
            send = next(valaszok, "?")       # a beállítás után „?" = tábla
        if any(c[0] == "tabla" for c in cmds) and \
                any(c[0] == "mond" and "szóból áll" in c[1] for c in cmds):
            break
    assert any(c[0] == "tabla" for c in cmds), "nincs ctx.tabla a helyi játékban"
    assert any(c[0] == "mond" and "szóból áll" in c[1] for c in cmds), \
        "a helyi játék nem mondja a szószámot"
