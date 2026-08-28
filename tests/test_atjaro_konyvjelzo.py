# -*- coding: utf-8 -*-
"""Átjáró – a könyvjelző-szinkron „ez a könyv nincs a telefonon” hibája.

Felhasználói hibajelzés (2026-08-24): „áttöltődik a könyv szépen az átjáróból,
de a könyvjelző szinkron mégis hibára fut, azt mondja ez a könyv nincs a
telefonon; valamint a telefonra átmentett könyvjelző is ezt mondja”.

Három ok volt, mindhárom ide van tesztelve:

  1. a PC→telefon könyvjelző a TELJES windowsos utat küldte `bookPath`-ként
     (C:\\...\\konyv.epub), miközben a telefon a FÁJLNÉV alapján párosít –
     így a telefonon soha nem talált rá a könyvre;
  2. a telefon-könyvek nyilvántartását a szinkron FELÜLÍRTA a telefonon
     megnyitott könyvek listájával, tehát az imént átküldött, de még meg nem
     nyitott könyv „eltűnt” belőle;
  3. a sikeres könyv-küldés egyáltalán NEM vette fel a könyvet a
     nyilvántartásba – a Könyvolvasó ezért kérdezte meg újra és újra.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "modules_src/atjaro")
from atjaro_mod import atjaro_core as AC          # noqa: E402


@pytest.fixture(autouse=True)
def _sajat_adatmappa(tmp_path, monkeypatch):
    """A nyilvántartás a felhasználó SAJÁT adatfájlja – a teszt SOHA nem
    nyúlhat hozzá, ezért a modul-szintű útvonalat a tmp mappára állítjuk."""
    monkeypatch.setattr(AC, "_TELEFON_KONYVEK_FILE",
                        Path(tmp_path) / "atjaro_telefon_konyvek.json")
    yield


# ------------------------------------------------- 1. a küldött könyvjelző

def test_a_konyvjelzo_fajlnevet_kuld_nem_teljes_utat():
    ki = AC.pc_konyvjelzo_androidra([
        {"book": r"C:\Users\valaki\Documents\Az országút harcosa.epub",
         "title": "Az országút harcosa", "char": 1234},
    ])
    assert len(ki) == 1
    assert ki[0]["bookPath"] == "az országút harcosa.epub", \
        "a telefon a fájlnév alapján párosít, nem a windowsos út alapján"
    assert "\\" not in ki[0]["bookPath"] and ":" not in ki[0]["bookPath"]


def test_a_teljes_pc_ut_azert_megmarad():
    """Visszafelé (telefon→PC) kelleni fog, ezért külön mezőben visszük."""
    ut = r"C:\Users\valaki\Documents\Az országút harcosa.epub"
    ki = AC.pc_konyvjelzo_androidra([{"book": ut, "title": "x", "char": 1}])
    assert ki[0]["pcPath"] == ut


def test_ut_nelkuli_konyvjelzo_nem_dol_el():
    ki = AC.pc_konyvjelzo_androidra([{"book": "", "title": "névtelen"}])
    assert isinstance(ki, list)


# ------------------------------------------------- 2. a nyilvántartás bővül

def test_a_hozzaadas_megtartja_a_regieket():
    AC.telefon_konyvek_ment(["régi könyv.epub"])
    AC.telefon_konyvek_hozzaad([r"D:\hangoskonyvek\új könyv.mp3"])
    megvan = AC.telefon_konyvek_betolt()
    assert "régi könyv.epub" in megvan, "a szinkron nem törölheti a korábbiakat"
    assert "új könyv.mp3" in megvan


def test_a_hozzaadas_fajlnevre_es_kisbetusre_normalizal():
    AC.telefon_konyvek_hozzaad([r"C:\valahol\NAGYBETŰS Könyv.EPUB"])
    assert "nagybetűs könyv.epub" in AC.telefon_konyvek_betolt()


def test_a_hozzaadas_nem_duplaz_es_az_ureset_kihagyja():
    AC.telefon_konyvek_hozzaad(["a.epub", "a.epub", "", "   ", None])
    assert sorted(AC.telefon_konyvek_betolt()) == ["a.epub"]


def test_a_hozzaadas_visszaadja_a_teljes_keszletet():
    AC.telefon_konyvek_ment(["egy.epub"])
    eredmeny = AC.telefon_konyvek_hozzaad(["ketto.epub"])
    assert eredmeny == {"egy.epub", "ketto.epub"}


# ------------------------------------------------- 3. a küldött mappa fájljai

def test_a_mappa_fajljai_ugyanazt_gyujti_amit_a_kuldes(tmp_path):
    """A nyilvántartásba PONTOSAN az kerüljön, ami tényleg átment."""
    konyv = tmp_path / "Egy hangoskönyv"
    (konyv / "1. kötet").mkdir(parents=True)
    (konyv / "01.mp3").write_bytes(b"x")
    (konyv / "1. kötet" / "02.mp3").write_bytes(b"x")
    (konyv / "borító.jpg").write_bytes(b"x")          # nem hangfájl

    nevek = {os.path.basename(u) for u in AC.mappa_fajljai(str(konyv))}
    assert nevek == {"01.mp3", "02.mp3"}, \
        "az almappák is kellenek, a nem-hangfájl viszont nem"


def test_a_mappa_fajljai_ures_mappara_ures_lista(tmp_path):
    ures = tmp_path / "semmi"
    ures.mkdir()
    assert AC.mappa_fajljai(str(ures)) == []


def test_az_atkuldott_hangoskonyv_utan_megvan_minden_resz(tmp_path):
    """A végponttól végpontig tartó eset: mappa-küldés → nyilvántartás →
    a Könyvolvasó már nem mondja, hogy nincs a telefonon."""
    konyv = tmp_path / "Hangoskönyv"
    konyv.mkdir()
    (konyv / "01. rész.mp3").write_bytes(b"x")
    (konyv / "02. rész.mp3").write_bytes(b"x")

    AC.telefon_konyvek_hozzaad(AC.mappa_fajljai(str(konyv)))
    tel = AC.telefon_konyvek_betolt()
    assert "01. rész.mp3" in tel and "02. rész.mp3" in tel
