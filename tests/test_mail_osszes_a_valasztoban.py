# -*- coding: utf-8 -*-
"""Super Mail MK1–MK3: az Összes bejövő a fiók-választóban, folyamatos
figyelés és az új-levél hang.

Felhasználói kérés (2026-08-17):
  1. „az összes bejövő ne a mappáknál legyen, hanem a fiók-választónál:
     összes bejövő, email 1, email 2, satöbbi”;
  2. „ha az összes bejövőn vagy, folyamatosan figyelődjenek az emailek
     állítható periodicitással – az F5 nyilván felülír mindent”;
  3. „legyen egy kis pici hang… akinek nincs beállítva email-érkeztető hang, az
     is kapjon hangos visszajelzést… átállítható saját hangokra és ki is
     kapcsolható”.

Rögzített döntés: az Összes bejövő a MAPPALISTÁBÓL TELJESEN KIKERÜL.
"""

import sys

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import hangok as H              # noqa: E402
from mail_mod import mail_core as MC          # noqa: E402
from mail_mod import mailwin as MW            # noqa: E402


class _Keret:
    """A MailFrame vizsgált metódusai, wx-ablak nélkül."""

    _osszes_a_valasztoban = MW.MailFrame._osszes_a_valasztoban
    _valaszto_index = MW.MailFrame._valaszto_index
    _uj_levelek_szama = MW.MailFrame._uj_levelek_szama

    def __init__(self, fiokok):
        self._fiokok = list(fiokok)


# --------------------------------------------------------------- MK1

def test_az_osszes_bejovo_csak_tobb_fioknal():
    assert _Keret([]) ._osszes_a_valasztoban() is False
    assert _Keret([{"email": "a@x.hu"}])._osszes_a_valasztoban() is False
    assert _Keret([{"email": "a@x.hu"},
                   {"email": "b@y.hu"}])._osszes_a_valasztoban() is True


def test_a_valaszto_sorszamai_eltolodnak_az_osszes_bejovovel():
    """Az első hely az Összes bejövőé, tehát a fiókok EGGYEL odébb vannak.
    Ha ezt elszámoljuk, rossz fiókot nyit meg a program."""
    tobb = _Keret([{"email": "a@x.hu"}, {"email": "b@y.hu"}])
    assert tobb._valaszto_index(0) == 1 and tobb._valaszto_index(1) == 2
    egy = _Keret([{"email": "a@x.hu"}])
    assert egy._valaszto_index(0) == 0


def test_a_mappalistabol_kikerult_az_al_mappa():
    """A felhasználóval egyeztetett döntés: egy funkció EGY helyen legyen."""
    assert not hasattr(MW.MailFrame, "_mappakkal_osszes")
    assert hasattr(MW.MailFrame, "_osszes_nezet")


def test_az_al_mappa_neve_megmaradt_a_nezet_jelolesere():
    """A `MC.OSSZES_MAPPA` továbbra is jelöli az egyesített NÉZETET (a
    `_mappa` mezőben), csak már nem a mappalistában szerepel."""
    assert MC.OSSZES_MAPPA and MC.OSSZES_NEV


# --------------------------------------------------------------- MK2

def _lev(cim, uid, mappa="INBOX"):
    return {"_fiok": {"email": cim}, "_mappa": mappa, "uid": uid}


def test_az_elso_betoltes_meg_nem_uj_level():
    """Induláskor a teli postaláda NEM száz új levél – az a kiindulási alap."""
    k = _Keret([])
    assert k._uj_levelek_szama([_lev("a@x.hu", 1), _lev("a@x.hu", 2)]) == 0


def test_a_valoban_uj_leveleket_szamolja():
    k = _Keret([])
    alap = [_lev("a@x.hu", 1)]
    k._uj_levelek_szama(alap)
    assert k._uj_levelek_szama(alap + [_lev("b@y.hu", 5)]) == 1
    assert k._uj_levelek_szama(alap + [_lev("b@y.hu", 5)]) == 0


def test_az_azonos_uid_kulon_fiokban_ket_kulon_level():
    """Két fiókban lehet ugyanaz az azonosító – ne olvadjanak össze."""
    k = _Keret([])
    k._uj_levelek_szama([_lev("a@x.hu", 1)])
    assert k._uj_levelek_szama([_lev("a@x.hu", 1), _lev("b@y.hu", 1)]) == 1


def test_a_torolt_level_nem_szamit_ujnak():
    k = _Keret([])
    k._uj_levelek_szama([_lev("a@x.hu", 1), _lev("a@x.hu", 2)])
    assert k._uj_levelek_szama([_lev("a@x.hu", 1)]) == 0


def test_az_uj_beallitasok_alapertekei():
    alap = MC._ALTALANOS_ALAP
    assert alap["osszes_perc"] == 3, "3 perc az ajánlott alapérték"
    assert alap["indulo_osszes"] is True
    assert alap["ertesito_hang_be"] is True
    assert alap["ertesito_hang_fajl"] == ""


# --------------------------------------------------------------- MK3

def test_az_uj_level_hang_rovid_es_ervenyes(monkeypatch, tmp_path):
    """Ez ÉRTESÍTÉS, nem ébresztő: legyen rövid."""
    import wave
    monkeypatch.setattr(H, "_MAPPA", tmp_path)
    ut = H.uj_level_hang_fajl()
    with wave.open(str(ut), "rb") as w:
        hossz = w.getnframes() / w.getframerate()
    assert 0.1 < hossz < 0.5, "a jelzés rövid legyen (%.2f mp)" % hossz
    assert w.getnchannels() == 1


def test_az_uj_level_hang_kulonbozik_a_lista_szel_hangtol(monkeypatch, tmp_path):
    """Ne lehessen összetéveszteni: más esemény, más hang."""
    monkeypatch.setattr(H, "_MAPPA", tmp_path)
    assert H.uj_level_hang_fajl().read_bytes() != H.hang_fajl(True).read_bytes()


def test_a_hang_sosem_dob_hibat(monkeypatch):
    monkeypatch.setattr(H, "uj_level_hang_fajl",
                        lambda: (_ for _ in ()).throw(OSError("nincs")))
    assert H.uj_level("C:/nincs_ilyen_sem.wav") is False
