# -*- coding: utf-8 -*-
"""BraiLab PC hang: a hosszú szöveg is megszólal (Turai László jelzése, 2026-10-01).

A BraiLab TTS_StartSay legfeljebb 511 karaktert fogad el; hosszabbra „-10”-et
ad és néma marad. Ezért a Kő-papír-olló (és a Szerencsekerék, az Ország-Város)
leírása F8-ra „A BraiLab hang nem szólalt meg”-et mondott. Most a motor
darabolva mondja el. A teszt a valódi host nélkül, egy hamis hosttal fut.
"""
import time

import pytest

BASE = "modules_src.jatekok.jatekok_mod"
B = pytest.importorskip(BASE + ".brailab")
KAT = pytest.importorskip(BASE + ".katalogus")

HATAR = 511          # a valódi motor határa (élőben mérve)


def _normal(s):
    return " ".join(s.split())


def test_rovid_szoveg_egy_darab():
    assert B.darabol("  Kő,  papír,\n olló. ") == ["Kő, papír, olló."]
    assert B.darabol("") == []
    assert B.darabol(None) == []


@pytest.mark.parametrize("szoveg", [
    "Ez egy mondat. " * 80,
    "alma, " * 300,
    "x" * 1500,
    "árvíztűrő tükörfúrógép " * 60,
])
def test_darabok_a_hatar_alatt_es_semmi_nem_vesz_el(szoveg):
    d = B.darabol(szoveg)
    assert len(d) > 1
    assert all(0 < len(x) <= B.MAX_KARAKTER < HATAR for x in d)
    assert _normal(" ".join(d)).replace(" ", "") == _normal(szoveg).replace(" ", "")


def test_mondathataron_vag():
    szoveg = ("Első mondat, ami elég hosszú. " * 20).strip()
    for x in B.darabol(szoveg)[:-1]:
        assert x.endswith(".")


def test_minden_jatekleiras_kimondhato():
    for j in tuple(KAT.SAJAT):
        teljes = f"{j.nev}. {j.leiras}"
        assert all(len(x) <= B.MAX_KARAKTER for x in B.darabol(teljes)), j.nev


class _HamisHost:
    """A valódi host viselkedése: 511 karakter fölött ERR -10."""

    def __init__(self):
        self.mondott = []
        self.stop = 0

    def __call__(self, sor):
        if sor.startswith("SPEAK"):
            szoveg = sor.split(" ", 1)[1]
            if len(szoveg) > HATAR:
                return "ERR -10"
            self.mondott.append(szoveg)
            return "OK"
        if sor == "STOP":
            self.stop += 1
        return "OK"


def _motor(monkeypatch, host):
    m = B.BrailabMotor()
    monkeypatch.setattr(m, "_indit_zarban", lambda: True)
    monkeypatch.setattr(m, "_fut", lambda: True)
    monkeypatch.setattr(m, "_parancs", host)
    monkeypatch.setattr(B, "becsult_hossz", lambda s, t=4: 0.05)
    return m


def test_kpo_leirasa_megszolal_darabolva(monkeypatch):
    host = _HamisHost()
    m = _motor(monkeypatch, host)
    kpo = [j for j in KAT.SAJAT if j.kulcs == "kpo"][0]
    teljes = f"{kpo.nev}. {kpo.leiras}"
    assert len(teljes) > HATAR            # ez volt a hiba oka
    hossz = m.mond(teljes)
    assert hossz > 0
    veg = time.monotonic() + 3
    while len(host.mondott) < len(B.darabol(teljes)) and time.monotonic() < veg:
        time.sleep(0.02)
    assert host.mondott == B.darabol(teljes)


def test_leallitas_utan_a_maradek_nem_szol(monkeypatch):
    host = _HamisHost()
    m = _motor(monkeypatch, host)
    monkeypatch.setattr(B, "becsult_hossz", lambda s, t=4: 0.5)
    m.mond("Mondat. " * 200)
    assert len(host.mondott) == 1
    m.stop()
    time.sleep(0.8)
    assert len(host.mondott) == 1


def test_hiba_oka_kiderul(monkeypatch):
    m = _motor(monkeypatch, lambda sor: "ERR -10" if sor.startswith("SPEAK") else "OK")
    monkeypatch.setattr(m, "_zarj", lambda: None)
    assert m.mond("szia") == 0.0
    assert "-10" in m.hiba
