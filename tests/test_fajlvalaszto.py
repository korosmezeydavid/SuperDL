# -*- coding: utf-8 -*-
"""A BEÉPÍTETT fájlválasztó – a Windows fájlválasztójától független böngészés.

Hibajelentés (Miki, 2026-08-20): „Ha beállítom az összes fájlt és megnyitok egy
könyvtárat, kilép a programból.” A rendszer fájlválasztójába idegen
bővítmények épülnek be (kodek-csomagok, felhő-szinkron, vírusirtó); ha azok
egyike elszáll, viszi az egész programot, és ezt Pythonból NEM lehet elkapni.
Ez a választó semmilyen rendszerbővítményt nem használ.
"""

import os

import pytest

from superdl import fajlvalaszto as FV


@pytest.fixture
def peldamappa(tmp_path):
    (tmp_path / "zene").mkdir()
    (tmp_path / "Videok").mkdir()
    (tmp_path / ".rejtett").mkdir()
    (tmp_path / "dal.mp3").write_bytes(b"x")
    (tmp_path / "Masik.APE").write_bytes(b"x")
    (tmp_path / "jegyzet.txt").write_text("szia", encoding="utf-8")
    (tmp_path / ".rejtett_fajl").write_text("x", encoding="utf-8")
    return tmp_path


def test_mappak_es_fajlok_abecében(peldamappa):
    mappak, fajlok = FV.tartalom(str(peldamappa))
    assert mappak == ["Videok", "zene"], "ábécében, kis/nagybetűtől függetlenül"
    assert fajlok == ["dal.mp3", "jegyzet.txt", "Masik.APE"]


def test_a_rejtett_elemeket_kihagyjuk(peldamappa):
    mappak, fajlok = FV.tartalom(str(peldamappa))
    assert ".rejtett" not in mappak
    assert ".rejtett_fajl" not in fajlok


def test_kiterjesztes_szures_kis_nagybetutol_fuggetlen(peldamappa):
    _mappak, fajlok = FV.tartalom(str(peldamappa), (".mp3", ".ape"))
    assert fajlok == ["dal.mp3", "Masik.APE"], "az .APE is médiafájl"


def test_nem_letezo_mappa_nem_szall_el(tmp_path):
    assert FV.tartalom(str(tmp_path / "nincs_ilyen")) == ([], [])


def test_hozzaferhetetlen_mappa_nem_szall_el():
    """Egy rendszermappa miatt ne álljon meg a böngészés."""
    assert isinstance(FV.tartalom("C:\\System Volume Information"), tuple)


def test_gepeles_szerinti_szures():
    nevek = ["Dal.mp3", "hangoskonyv.m4b", "Zene.flac"]
    assert FV.szuro(nevek, "ne") == ["Zene.flac"]
    assert FV.szuro(nevek, "n") == ["hangoskonyv.m4b", "Zene.flac"]
    assert FV.szuro(nevek, "DAL") == ["Dal.mp3"]
    assert FV.szuro(nevek, "") == nevek
    assert FV.szuro(nevek, "   ") == nevek


def test_gyorshelyek_letezo_mappak():
    helyek = FV.gyorshelyek()
    assert helyek, "legalább a saját mappa mindig van"
    for nev, ut in helyek:
        assert nev and os.path.isdir(ut), "%s (%s) nem létezik" % (nev, ut)


def test_meret_szoveg():
    assert "bájt" in FV._meret_szoveg(512)
    assert "megabájt" in FV._meret_szoveg(5 * 1024 ** 2)
