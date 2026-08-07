# -*- coding: utf-8 -*-
"""Maya (MAJA) és Awari mancala-játékok: mechanika + lefutás."""
import importlib
import re

import pytest

BASE = "modules_src.jatekok.jatekok_mod"
JR = pytest.importorskip(BASE + ".jatekok")
U = importlib.import_module(BASE + ".jatekok._util")
M = importlib.import_module(BASE + ".jatekok.mancala")
KAT = importlib.import_module(BASE + ".katalogus")


def _bot(k, ki):
    """Értelmes játékos: az állásból nem üres gödröt/tálat választ."""
    kl = k.lower()
    if "még egyet" in kl or "ismét" in kl or "igen/nem" in kl:
        return "nem"
    if "indulás" in kl:
        return "1"
    # keressük a legutóbbi állás-sort, és válasszunk nem üres tálat/gödröt
    for _, szoveg in reversed(ki):
        m = re.search(r"(?:tálaid|gödreid) \(1-6\): ([\d ]+)", str(szoveg))
        if m:
            szamok = [int(x) for x in m.group(1).split()]
            for i, db in enumerate(szamok, 1):
                if db > 0:
                    return str(i)
            break
    return "1"


def test_regiszterben_es_katalogusban():
    for kulcs in ("maja", "awari"):
        assert kulcs in JR.REGISZTER
        assert any(j.kulcs == kulcs for j in KAT.RETRO)


@pytest.mark.parametrize("kulcs", ["maja", "awari"])
def test_veget_er(kulcs):
    ki = U.lejatsz(JR.REGISZTER[kulcs], _bot, max_lepes=200000)
    assert ki and ki[-1][0] == "vege"


# ---- Maya vetés-mechanika ----
def test_maja_vetes_megorzi_a_golyokat():
    g = M._maja_uj()
    ossz = sum(g["A"][1:7]) + sum(g["B"][1:7]) + g["SA"] + g["SB"]
    assert ossz == 72
    M._maja_vet(g, "A", 3)
    ossz2 = sum(g["A"][1:7]) + sum(g["B"][1:7]) + g["SA"] + g["SB"]
    assert ossz2 == 72, "A vetés nem őrizte meg a golyók számát"


def test_maja_gyujtobe_erve_ujra_jon():
    # az n. tálból pontosan n golyó a gyűjtőbe ér -> extra kör
    g = M._maja_uj()
    g["A"][3] = 3
    assert M._maja_vet(g, "A", 3) is True
    assert g["SA"] == 1


def test_maja_tobbtalas_vetes_nem_gyujto():
    g = M._maja_uj()
    g["A"][2] = 6           # 6 golyó a 2-esből nem a gyűjtőben ér véget
    assert M._maja_vet(g, "A", 2) is False


# ---- Awari ütés-mechanika ----
def test_awari_start_36_mag():
    b = M._awari_uj(1)
    assert sum(b) == 36
    assert all(b[i] == 3 for i in list(range(6)) + list(range(7, 13)))


def test_awari_utes_a_szemkozti_godort_soporri():
    b = [0] * 14
    b[0] = 1            # a 0-ból 1 mag a 1-es üres gödörbe kerül
    b[11] = 4           # szemközti (12-1=11) gépgödörben 4 mag
    # 0-ból indulva az utolsó az 1-es gödörbe kerül (üres volt) -> ütés
    utolso = M._awari_lep(b, 0, M._JATEKOS_RAKTAR)
    assert utolso == 1
    assert b[M._JATEKOS_RAKTAR] == 5, "Az ütés 4+1 magot vitt a raktárba"
    assert b[11] == 0 and b[1] == 0


def test_awari_gep_valaszt_ervenyes_godrot():
    b = M._awari_uj(1)
    gm = M._awari_gep_valaszt(b)
    assert gm in range(7, 13) and b[gm] > 0
