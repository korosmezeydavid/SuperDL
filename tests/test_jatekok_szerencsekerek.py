# -*- coding: utf-8 -*-
"""Szerencsekerék (SAJÁT, kerék-és-szó játék) tesztjei. A tiszta segéd-
függvényeket közvetlenül ellenőrizzük; a teljes partit egy-egy bot játssza:
egy „megfejtő" ember (ismert rejtvényre), és egy passzív ember a gép ellen."""
import importlib
import random

import pytest

BASE = "modules_src.jatekok.jatekok_mod"
JR = pytest.importorskip(BASE + ".jatekok")
U = importlib.import_module(BASE + ".jatekok._util")
S = importlib.import_module(BASE + ".jatekok.sajat")
KAT = importlib.import_module(BASE + ".katalogus")


# ---- tiszta segédfüggvények

def test_szk_maganhangzo():
    assert S._szk_maganhangzo("a") and S._szk_maganhangzo("á")
    assert S._szk_maganhangzo("ő") and S._szk_maganhangzo("ü")
    assert not S._szk_maganhangzo("b")
    assert not S._szk_maganhangzo("sz")      # nem egy betű


def test_szk_elofordul_es_egyezik():
    assert S._szk_elofordul("Lecsó", "l") == 1     # kis/nagybetű nem számít
    assert S._szk_elofordul("Lecsó", "c") == 1
    assert S._szk_elofordul("Lecsó", "ó") == 1
    assert S._szk_elofordul("Lecsó", "o") == 0     # ékezet SZÁMÍT a magánhangzónál
    assert S._szk_egyezik("lecso", "Lecsó")        # megfejtés: laza (ékezet/kis-nagy)
    assert S._szk_egyezik("  Ki korán kel aranyat lel ", "Ki korán kel aranyat lel")
    assert not S._szk_egyezik("valami más", "Lecsó")


def test_szk_tabla_es_kerek():
    assert "üres" in S._szk_tabla("Ló", set())
    t = S._szk_tabla("Ló", {"l"})
    assert "L" in t and "üres" in t              # az L felfedve, az Ó még rejtve
    # a kerék érvényes mezőt ad
    for _ in range(50):
        m = S._szk_porget()
        assert m[0] in ("penz", "csod", "passz")
        if m[0] == "penz":
            assert m[1] in S._SZK_MEZOK
    assert S._szk_gep_massalhangzo(set()) == "t"   # a leggyakoribb elöl


# ---- teljes parti: ember megfejti (ismert rejtvény)

def test_szerencsekerek_ember_megfejt(monkeypatch):
    monkeypatch.setattr(S, "_szk_valaszt", lambda r: ("Étel és ital", "Lecsó"))

    def bot(k, ki):
        kl = k.lower()
        if "hány játékos" in kl:
            return "1"
        if "játékos neve" in kl:
            return "Anna"
        if "mit lépsz" in kl:
            return "M"
        if "teljes megfejtést" in kl:
            return "Lecsó"
        return ""

    ki = U.lejatsz(JR.REGISZTER["szerencsekerek"], bot, max_lepes=200000)
    assert ki[-1][0] == "vege"
    txt = "\n".join(p for _, p in ki if isinstance(p, str))
    assert "SZERENCSEKERÉK" in txt.upper()
    assert "Anna megfejtette a rejtvényt: Lecsó" in txt
    assert "győztes: Anna" in txt
    # szólt-e hang (a főcím + effektek „effekt" parancsként jelennek meg)
    assert any(t == "effekt" for t, _ in ki)


# ---- teljes parti: passzív ember a gép ellen (a gép old meg)

def test_szerencsekerek_gep_ellen_lezarul():
    random.seed(20260802)

    def bot(k, ki):
        kl = k.lower()
        if "hány játékos" in kl:
            return "1"
        if "játékos neve" in kl:
            return "Én"
        if "mit lépsz" in kl:
            return "P"
        if "mássalhangzót" in kl:
            return "s"
        return ""

    ki = U.lejatsz(JR.REGISZTER["szerencsekerek"], bot, max_lepes=400000)
    assert ki[-1][0] == "vege"
    txt = "\n".join(p for _, p in ki if isinstance(p, str))
    assert "Vége a játéknak!" in txt and "győztes" in txt.lower()


def test_szerencsekerek_a_katalogusban_sajat():
    assert JR.van("szerencsekerek")
    j = KAT.keres("szerencsekerek")
    assert j is not None and j.retro is False
    assert "Szerencsekerék" == j.nev


def test_effekt_a_szerencsekerek_hang_mappat_is_nezi():
    """A konzol _effekt-je a bekötött szerencsekerek_hang mappát is keresi
    (WAV/MP3), nem csak a milliomos_hang-ot."""
    import inspect
    JK = importlib.import_module(BASE + ".jatekkonzol")
    src = inspect.getsource(JK.JatekKonzol._effekt)
    assert "szerencsekerek_hang" in src
    assert ".mp3" in src
