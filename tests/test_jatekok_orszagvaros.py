# -*- coding: utf-8 -*-
"""Ország-Város-Fiú-Lány (Mezei Géza ötlete, bővítés: Kőrösmezey Anita Wildcath).

A tiszta elbírálót és a bővíthető szótárt közvetlenül, a teljes partikat a
teszt-hajtóval (az abcstop a soron következő „választ", a megállított betűt
adja vissza) ellenőrizzük."""
import importlib

import pytest

BASE = "modules_src.jatekok.jatekok_mod"
JR = pytest.importorskip(BASE + ".jatekok")
U = importlib.import_module(BASE + ".jatekok._util")
OV = importlib.import_module(BASE + ".jatekok.orszagvaros")
KAT = importlib.import_module(BASE + ".katalogus")


def _sztr(ki):
    # a hang-parancsok payloadja LISTA – csak a szöveges kimenetet fűzzük össze
    return "\n".join(p for _, p in ki if isinstance(p, str))


# ---- tiszta elbíráló -----------------------------------------------------

def test_ertekel_negy_eset():
    assert OV._ertekel("Görögország", "g", OV._ORSZAGOK) == ("ismer", 2)
    assert OV._ertekel("Gizmó", "g", OV._ORSZAGOK) == ("elfogad", 1)
    assert OV._ertekel("Anglia", "g", OV._ORSZAGOK) == ("rosszbetu", 0)
    assert OV._ertekel("", "g", OV._ORSZAGOK) == ("ures", 0)


def test_ertekel_ekezet_es_kisbetu_nem_szamit():
    assert OV._ertekel("genf", "g", OV._VAROSOK)[0] == "ismer"


def test_betuk_mind_a_negy_klasszikus_kategoriaban():
    assert OV._BETUK and "g" in OV._BETUK
    alap = (OV._ORSZAGOK, OV._VAROSOK, OV._FIUK, OV._LANYOK)
    for b in OV._BETUK:
        for kesz in alap:
            assert any(sz.startswith(b) for sz in kesz)


# ---- bővíthető (tanított) szótár -----------------------------------------

def test_keszlet_beepitett_es_tanitott_szavakat_is_tartalmaz():
    k = OV.keszlet("marka", {"marka": ["Xiaomi"]})
    assert "adidas" in k                 # beépített (Adidas normalizálva)
    assert "xiaomi" in k                 # tanított szó is bekerül


def test_kategoria_regiszter_teljes():
    assert set(OV.ALAP_KULCSOK) | set(OV.EXTRA_KULCSOK) == set(OV.KATEGORIA_NEVEK)
    assert set(OV._CIMKE) == set(OV.KATEGORIA_NEVEK)
    assert set(OV._BUILTIN_NYERS) == set(OV.KATEGORIA_NEVEK)


# ---- regisztráció + katalógus --------------------------------------------

def test_regisztralva_es_katalogusban():
    assert "orszagvaros" in JR.REGISZTER
    j = KAT.keres("orszagvaros")
    assert j is not None and j.retro is False
    assert "Mezei Géza" in j.leiras


# ---- teljes parti (klasszikus mód) ---------------------------------------

def test_klasszikus_parti_negy_talalattal_nyolc_pont():
    valaszok = ["1", "",              # 1 játékos, név
                "n",                  # klasszikus (nem bővített)
                "1",                  # 1 kör
                "i",                  # abcstop indul
                "g",                  # a megállított betű
                "Görögország", "Genf", "Géza", "Gizella"]
    ki = U.lejatsz(OV.jatek_orszagvaros, valaszok)
    szov = _sztr(ki)
    assert "Megállt a(z) G betűn" in szov
    assert "8 pont" in szov
    assert "győztes" in szov.lower()


def test_ekezetes_betu_normalizalodik():
    valaszok = ["1", "", "n", "1", "i", "á", "Ausztria", "", "", ""]
    ki = U.lejatsz(OV.jatek_orszagvaros, valaszok)
    szov = _sztr(ki)
    assert "Megállt a(z) Á betűn" in szov
    assert "Ismerem" in szov                # Ausztria az 'a' szótárban


def test_ures_valaszok_nulla_pont():
    valaszok = ["1", "", "n", "1", "i", "g", "", "", "", ""]
    ki = U.lejatsz(OV.jatek_orszagvaros, valaszok)
    szov = _sztr(ki)
    assert "0 pont" in szov
    assert ki[-1][0] == "vege"


# ---- bővített mód: plusz kategóriák kérdezése és pontozása ----------------

def test_bovitett_mod_allattal_tiz_pont():
    valaszok = ["1", "",              # 1 játékos, név
                "i",                  # BŐVÍTETT mód
                "n", "i", "n", "n", "n", "n", "n",   # csak az Állat legyen benne
                "1",                  # 1 kör
                "i",                  # abcstop indul
                "k",                  # a megállított betű
                "Kanada", "Kairó", "Károly", "Katalin", "kutya"]
    ki = U.lejatsz(OV.jatek_orszagvaros, valaszok)
    szov = _sztr(ki)
    assert "Állat mehet?" in szov           # a plusz kategóriát megkérdezte
    assert "5 szó" in szov                  # 4 klasszikus + Állat
    assert "10 pont" in szov                # 5 ismert válasz, egyenként 2 pont
