# -*- coding: utf-8 -*-
"""iPhone modul – a HALADÁS-JELZÉS ellenőrzése.

A felhasználó jelzése: „konkrétan semmit se jelez… ki kéne dolgozni egy
indikátort ami mutatja is a letöltést, hogy a vak felhasználója tudja hogy halad
a dolog”. Vakon a sáv önmagában semmit nem ér, ezért a lényeg a SZÖVEG: mennyi
kész, mennyi van hátra, és éppen mi megy. Ezt teszteljük.

A becslés kétféle: ha ismerjük a teljes bájtszámot, abból (pontosabb, mert egy
800 MB-os videó nem annyi, mint egy 3 MB-os dal), ha nem, akkor darabszámból.
"""

import sys

import pytest

sys.path.insert(0, "modules_src/iphone")


@pytest.fixture(scope="module")
def Lap():
    """A lapfül OSZTÁLYA – wx-ablak nélkül, mert a mért logika tiszta."""
    import wx                                    # noqa: F401
    from iphone_mod import iphonewin
    return iphonewin._Lap


def _munka(**mit):
    alap = {"cimke": "Mentés", "i": 0, "n": 100, "nev": "", "kesz_bajt": 0,
            "osszes_bajt": 0, "fajl_kesz": 0, "fajl_teljes": 0,
            "kezdet": 0.0, "utolso_mondas": 0.0, "stop": False}
    alap.update(mit)
    return alap


def _idozit(monkeypatch, Lap, most):
    import iphone_mod.iphonewin as W
    monkeypatch.setattr(W.time, "monotonic", lambda: most)


def test_a_becsles_eleinte_hallgat(monkeypatch, Lap):
    """Két másodperc alatt még nincs mit becsülni – ne mondjunk butaságot."""
    _idozit(monkeypatch, Lap, 1.0)
    szoveg, _mp = Lap._hatralevo(_munka(i=1, kezdet=0.0))
    assert szoveg == ""


def test_a_becsles_darabszambol(monkeypatch, Lap):
    """100 elemből 10 megvan 60 másodperc alatt → kb. 9 perc a maradék."""
    _idozit(monkeypatch, Lap, 60.0)
    szoveg, mp = Lap._hatralevo(_munka(i=10, n=100, kezdet=0.0))
    assert "perc" in szoveg
    assert 500 < mp < 560


def test_a_becsles_bajtbol_pontosabb(monkeypatch, Lap):
    """Ha tudjuk a teljes méretet, abból számolunk: egy nagy videó nem annyi,
    mint egy kis dal, a darabszám ilyenkor félrevezetne."""
    _idozit(monkeypatch, Lap, 100.0)
    szoveg, mp = Lap._hatralevo(_munka(i=1, n=2, kezdet=0.0,
                                       osszes_bajt=1000, kesz_bajt=250))
    assert 290 < mp < 310, "750 bájt van hátra 250 bájt / 100 mp tempóval"
    assert "perc" in szoveg


def test_a_rovid_maradekot_nem_percben_mondjuk(monkeypatch, Lap):
    _idozit(monkeypatch, Lap, 10.0)
    szoveg, _mp = Lap._hatralevo(_munka(i=95, n=100, kezdet=0.0))
    assert szoveg == "kevesebb mint egy perc van hátra"


def test_a_nagyon_hosszut_oraban(monkeypatch, Lap):
    _idozit(monkeypatch, Lap, 600.0)
    szoveg, _mp = Lap._hatralevo(_munka(i=1, n=100, kezdet=0.0))
    assert "óra" in szoveg


def test_az_allas_szoveg_a_lenyeget_mondja(monkeypatch, Lap):
    _idozit(monkeypatch, Lap, 120.0)
    m = _munka(i=412, n=691, nev="Bohemian Rhapsody", kezdet=0.0,
               osszes_bajt=1000, kesz_bajt=500)
    sz = Lap._allas_szoveg(Lap, m, reszletes=True)
    assert sz.startswith("412 / 691 kész")
    assert "van hátra" in sz
    assert "most: Bohemian Rhapsody" in sz


def test_a_kis_fajl_szazaleka_nem_erdekel(monkeypatch, Lap):
    """Egy 3 MB-os dalnál a fájlon belüli százalék csak zaj lenne."""
    _idozit(monkeypatch, Lap, 120.0)
    m = _munka(i=5, n=10, kezdet=0.0, fajl_kesz=1 << 20, fajl_teljes=3 << 20)
    assert "százalék" not in Lap._allas_szoveg(Lap, m)


def test_a_nagy_fajl_szazaleka_viszont_igen(monkeypatch, Lap):
    """800 MB-os videónál ez a különbség a „dolgozik” és a „lefagyott” között."""
    _idozit(monkeypatch, Lap, 120.0)
    m = _munka(i=5, n=10, kezdet=0.0, fajl_kesz=400 << 20, fajl_teljes=800 << 20)
    assert "a mostani fájl 50 százaléknál tart" in Lap._allas_szoveg(Lap, m)
