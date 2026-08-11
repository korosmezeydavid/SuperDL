# -*- coding: utf-8 -*-
"""Ország-Város ONLINE host-motor (OrszagVarosHost) tesztjei – fejetlen.

A szótárt a `custom` paraméterrel vezéreljük (nincs fájl/kép-hozzáférés), így a
pontozás determinisztikus. A betű-rögzítés first-come, a pontozás alappont +
egyediségi bónusz."""
import importlib

BASE = "modules_src.jatekok.jatekok_mod"
OVO = importlib.import_module(BASE + ".orszagvaros_online")

# saját, biztosan-egyedi „szótári" szavak (nincsenek a beépített készletben)
CUSTOM = {"orszag": ["Bumbaland", "Barvia"]}


def _host():
    return OVO.OrszagVarosHost(["A", "B"], kulcsok=["orszag"], custom=CUSTOM)


def test_betu_rogzit_first_come():
    h = _host()
    h.kor_indit()
    assert h.fazis == "betuzes"
    assert h.betu_rogzit("Béla") is True       # 'b'
    assert h.betu == "b" and h.fazis == "iras"
    assert h.betu_rogzit("Cica") is False       # már van betű – eldobjuk
    assert h.betu == "b"


def test_ertekel_szotari_egyedi_es_duplikalt():
    h = _host()
    h.kor_indit()
    h.betu_rogzit("b")
    # mindketten ugyanazt a SZÓTÁRI szót írják → base 2, duplikált (nincs bónusz)
    h.valasz_be("A", {"orszag": "Bumbaland"})
    h.valasz_be("B", {"orszag": "Bumbaland"})
    e = h.ertekel()
    assert e["korpont"] == {"A": 2, "B": 2}
    assert h.osszpont == {"A": 2, "B": 2}


def test_ertekel_szotari_egyedi_bonusz():
    h = _host()
    h.kor_indit()
    h.betu_rogzit("b")
    h.valasz_be("A", {"orszag": "Bumbaland"})   # szótári + egyedi → 2+2=4
    h.valasz_be("B", {"orszag": "Barvia"})       # szótári + egyedi → 4
    e = h.ertekel()
    assert e["korpont"] == {"A": 4, "B": 4}


def test_ertekel_elfogadott_rosszbetu_ures():
    h = _host()
    h.kor_indit()
    h.betu_rogzit("b")
    h.valasz_be("A", {"orszag": "Bxqzland"})     # jó betű, nincs szótárban → 1, egyedi → 3
    h.valasz_be("B", {"orszag": "Anglia"})        # rossz betű → 0
    e = h.ertekel()
    assert e["korpont"]["A"] == 3
    assert e["korpont"]["B"] == 0
    assert e["detail"]["A"]["orszag"]["allapot"] == "elfogad"
    assert e["detail"]["B"]["orszag"]["allapot"] == "rosszbetu"


def test_ures_valasz_nulla():
    h = _host()
    h.kor_indit()
    h.betu_rogzit("b")
    h.valasz_be("A", {"orszag": ""})
    h.valasz_be("B", {})                          # nem adott meg semmit
    e = h.ertekel()
    assert e["korpont"] == {"A": 0, "B": 0}


def test_tobb_kor_osszead():
    h = _host()
    for _ in range(3):
        h.kor_indit()
        h.betu_rogzit("b")
        h.valasz_be("A", {"orszag": "Bumbaland"})   # 4 (egyedi szótári)
        h.valasz_be("B", {"orszag": "Anglia"})       # 0
        h.ertekel()
    assert h.osszpont["A"] == 12 and h.osszpont["B"] == 0
    assert h.kor == 3


def test_tobb_kategoria_es_allapot_publikus():
    # csak custom szavakra építünk (nincs beépített-szótár-függőség)
    h = OVO.OrszagVarosHost(["A", "B"], kulcsok=["orszag", "varos"],
                            custom={"orszag": ["Bumbaland"],
                                    "varos": ["Bxvaros", "Byvaros"]})
    h.kor_indit()
    h.betu_rogzit("b")
    # orszag: mindketten Bumbaland → duplikált (base 2, nincs bónusz)
    # varos: A Bxvaros, B Byvaros → mindkettő szótári + egyedi (4)
    h.valasz_be("A", {"orszag": "Bumbaland", "varos": "Bxvaros"})
    h.valasz_be("B", {"orszag": "Bumbaland", "varos": "Byvaros"})
    e = h.ertekel()
    assert e["korpont"]["A"] == 6      # 2 (dup orszag) + 4 (egyedi varos)
    assert e["korpont"]["B"] == 6
    a = h.allapot_publikus("kész")
    assert a["fazis"] == "eredmeny" and a["betu"] == "b"
    assert a["kategoria_nevek"]["orszag"] == "Ország"
    assert a["osszpont"]["A"] == 6
