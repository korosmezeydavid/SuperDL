# -*- coding: utf-8 -*-
"""Ország-Város-Fiú-Lány (Mezei Géza ötlete, SAJÁT szójáték) tesztjei.

A tiszta elbírálót közvetlenül, a teljes partit kényszerített betűvel (a
véletlen pörgést 'g'-re rögzítve) és fix válaszokkal ellenőrizzük."""
import importlib

import pytest

BASE = "modules_src.jatekok.jatekok_mod"
JR = pytest.importorskip(BASE + ".jatekok")
U = importlib.import_module(BASE + ".jatekok._util")
OV = importlib.import_module(BASE + ".jatekok.orszagvaros")
KAT = importlib.import_module(BASE + ".katalogus")


# ---- tiszta elbíráló -----------------------------------------------------

def test_ertekel_negy_eset():
    assert OV._ertekel("Görögország", "g", OV._ORSZAGOK) == ("ismer", 2)
    assert OV._ertekel("Gizmó", "g", OV._ORSZAGOK) == ("elfogad", 1)
    assert OV._ertekel("Anglia", "g", OV._ORSZAGOK) == ("rosszbetu", 0)
    assert OV._ertekel("", "g", OV._ORSZAGOK) == ("ures", 0)


def test_ertekel_ekezet_es_kisbetu_nem_szamit():
    # a 'g' betűre az ismert városok közt ott a Genf; kisbetűvel/ékezet nélkül is
    assert OV._ertekel("genf", "g", OV._VAROSOK)[0] == "ismer"


# ---- landolható betűk: mind a négy kategóriában van válasz ----------------

def test_betuk_mindegyikere_van_negy_kategoria():
    assert OV._BETUK, "üres a landolható betűk halmaza"
    assert "g" in OV._BETUK
    for b in OV._BETUK:
        for _, keszlet in OV._KATEGORIAK:
            assert any(sz.startswith(b) for sz in keszlet), \
                f"a(z) {b} betűre hiányzik válasz valamelyik kategóriában"


# ---- regisztráció + katalógus --------------------------------------------

def test_regisztralva_es_katalogusban():
    assert "orszagvaros" in JR.REGISZTER
    j = KAT.keres("orszagvaros")
    assert j is not None and j.retro is False
    assert "Mezei Géza" in j.leiras


# ---- teljes parti kényszerített 'g' betűvel -------------------------------

def _forced_g(monkeypatch):
    monkeypatch.setattr(OV.random, "choice", lambda seq: "g")


def test_teljes_parti_negy_talalattal_nyolc_pont(monkeypatch):
    _forced_g(monkeypatch)
    valaszok = ["1", "", "1", "",                     # 1 játékos, 1 kör, pörgetés
                "Görögország", "Genf", "Géza", "Gizella"]
    ki = U.lejatsz(OV.jatek_orszagvaros, valaszok)
    szov = U.szoveg(ki)
    assert "Megállt a(z) G betűn" in szov
    assert "8 pont" in szov
    assert "győztes" in szov.lower()


def test_teljes_parti_ures_valaszok_nulla_pont(monkeypatch):
    _forced_g(monkeypatch)
    valaszok = ["1", "", "1", "", "", "", "", ""]
    ki = U.lejatsz(OV.jatek_orszagvaros, valaszok)
    szov = U.szoveg(ki)
    assert "0 pont" in szov                # a kör 0 pont
    assert ki[-1][0] == "vege"             # rendben véget ér
