# -*- coding: utf-8 -*-
"""Címjegyzék – az E-MAIL CÍM átírása.

Szabó Zsolt Jenő jelezte (2026-09-12): a szerkesztésben csak a név volt
átírható. A cím a bejegyzés kulcsa, ezért a megváltoztatása nem egyszerű
mezőírás – ezek a tesztek azt őrzik, hogy közben ne keletkezzen duplikátum,
és ne vesszen el a becenév meg a gyakoriság.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "modules_src" / "mail"))

import pytest                                   # noqa: E402
from mail_mod import mail_core as MC            # noqa: E402


@pytest.fixture
def cimjegyzek(tmp_path, monkeypatch):
    """Saját, üres címjegyzék-fájl – a felhasználóét nem bántjuk."""
    monkeypatch.setattr(MC, "_CIMJEGYZEK_FILE", tmp_path / "contacts.json")
    return tmp_path


def _felvesz(email, nev, becenev="", db=1):
    MC.cimjegyzek_frissit(email, nev)
    if becenev:
        MC.cimjegyzek_becenev(email, becenev)
    if db > 1:
        lista = MC.cimjegyzek_betolt()
        for c in lista:
            if c["email"] == email.lower():
                c["db"] = db
        MC.cimjegyzek_ment(lista)


def _keres(email):
    for c in MC.cimjegyzek_betolt():
        if c["email"] == email.lower():
            return c
    return None


# ---------------------------------------------------------------- alap

def test_az_email_cim_atirhato(cimjegyzek):
    """A bejelentett eset: Tóth Lászlónak megváltozik a címe, a neve nem."""
    _felvesz("szakember83@gmail.com", "Tóth László")
    baj = MC.cimjegyzek_atir("szakember83@gmail.com", "toth.laszlo@pelda.hu",
                             "Tóth László")
    assert baj == ""
    assert _keres("szakember83@gmail.com") is None      # a régi eltűnt
    uj = _keres("toth.laszlo@pelda.hu")
    assert uj and uj["nev"] == "Tóth László"


def test_a_becenev_es_a_gyakorisag_megmarad(cimjegyzek):
    """Törlés-és-újrafelvétel helyett ÁTÍRÁS: nem veszik el, amit tudunk róla."""
    _felvesz("regi@pelda.hu", "Nagy Éva", becenev="évi", db=17)
    assert MC.cimjegyzek_atir("regi@pelda.hu", "uj@pelda.hu") == ""
    uj = _keres("uj@pelda.hu")
    assert uj["becenev"] == "évi"
    assert uj["db"] == 17
    assert uj["nev"] == "Nagy Éva"


def test_csak_a_nev_valtozik(cimjegyzek):
    _felvesz("a@pelda.hu", "Régi Név")
    assert MC.cimjegyzek_atir("a@pelda.hu", "a@pelda.hu", "Új Név") == ""
    assert _keres("a@pelda.hu")["nev"] == "Új Név"


def test_a_becenev_kulon_atirhato_es_torolheto(cimjegyzek):
    _felvesz("a@pelda.hu", "Valaki", becenev="doki")
    MC.cimjegyzek_atir("a@pelda.hu", "a@pelda.hu", "Valaki", "")
    assert _keres("a@pelda.hu")["becenev"] == ""


# ---------------------------------------------------------------- védelem

def test_ervenytelen_cimet_nem_fogad_el(cimjegyzek):
    _felvesz("a@pelda.hu", "Valaki")
    baj = MC.cimjegyzek_atir("a@pelda.hu", "ez nem cím")
    assert "nem érvényes" in baj
    assert _keres("a@pelda.hu") is not None            # semmi nem változott


def test_nem_letezo_bejegyzesre_ertheto_hibat_ad(cimjegyzek):
    baj = MC.cimjegyzek_atir("nincs@pelda.hu", "uj@pelda.hu")
    assert "nem találom" in baj


def test_utkozo_cimnel_osszevonas_tortenik(cimjegyzek):
    """Ha az új cím már szerepel, NEM lesz belőle két bejegyzés."""
    _felvesz("regi@pelda.hu", "Tóth László", db=5)
    _felvesz("uj@pelda.hu", "", becenev="laci", db=3)
    assert MC.cimjegyzek_atir("regi@pelda.hu", "uj@pelda.hu",
                              "Tóth László") == ""
    lista = MC.cimjegyzek_betolt()
    assert len(lista) == 1
    c = lista[0]
    assert c["email"] == "uj@pelda.hu"
    assert c["nev"] == "Tóth László"
    assert c["db"] == 8                 # a két számláló összeadódott
    assert c["becenev"] == "laci"       # a másik bejegyzés becenevét megtartjuk


def test_a_nagybetus_cim_is_ugyanaz(cimjegyzek):
    _felvesz("a@pelda.hu", "Valaki")
    assert MC.cimjegyzek_atir("a@pelda.hu", "UJ@Pelda.HU", "Valaki") == ""
    assert _keres("uj@pelda.hu") is not None


def test_az_atirt_cim_megtalalhato_keresessel(cimjegyzek):
    """A keresés (és így a levélírás címkiegészítője) az új címet látja."""
    _felvesz("regi@pelda.hu", "Tóth László", becenev="laci")
    MC.cimjegyzek_atir("regi@pelda.hu", "toth@uj.hu", "Tóth László", "laci")
    talalat = MC.cimjegyzek_kereses("laci")
    assert talalat and talalat[0]["email"] == "toth@uj.hu"
    assert MC.cimjegyzek_kereses("regi@pelda.hu") == []
