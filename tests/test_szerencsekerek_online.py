# -*- coding: utf-8 -*-
"""Online Szerencsekerék – a HOST-oldali állapotgép (OnlineHost) tesztjei.

A rejtvényt és a pörgetést rögzítjük (monkeypatch), így determinisztikus."""
import importlib

import pytest

pytest.importorskip("wx")               # a modul wx-et importál a UI miatt
BASE = "modules_src.jatekok.jatekok_mod"
OL = importlib.import_module(BASE + ".szerencsekerek_online")
SZK = importlib.import_module(BASE + ".jatekok.sajat")


def _host(monkeypatch, megoldas="ALMA", korok=1, jatekosok=("A", "B")):
    monkeypatch.setattr(SZK, "_szk_valaszt", lambda r: ("Teszt", megoldas))
    return OL.OnlineHost(list(jatekosok), korok=korok)


def test_kezdo_allapot(monkeypatch):
    h = _host(monkeypatch)
    a = h.allapot()
    assert a["fazis"] == "jatek" and a["kor"] == 1 and a["soron"] == "A"
    assert a["bank"] == {"A": 0, "B": 0}
    assert a["tabla"]                       # van tábla-szöveg


def test_nem_soron_levo_akcioja_ervenytelen(monkeypatch):
    h = _host(monkeypatch)
    assert h.akcio("B", "porget") is None   # A van soron


def test_porget_majd_jo_betu_penzt_ad(monkeypatch):
    h = _host(monkeypatch)
    monkeypatch.setattr(SZK, "_szk_porget", lambda: ("penz", 100))
    a = h.akcio("A", "porget")
    assert a["utolso_porgetes"] == 100 and a["soron"] == "A"
    a = h.akcio("A", "betu", "l")           # ALMA-ban 1 db L
    assert h.korpenz["A"] == 100 and a["soron"] == "A"
    assert "l" in h.felfedett


def test_rossz_betu_a_kovetkezore_lep(monkeypatch):
    h = _host(monkeypatch)
    monkeypatch.setattr(SZK, "_szk_porget", lambda: ("penz", 100))
    h.akcio("A", "porget")
    a = h.akcio("A", "betu", "z")           # nincs ALMA-ban
    assert a["soron"] == "B"


def test_csod_elveszi_a_penzt_es_lep(monkeypatch):
    h = _host(monkeypatch)
    monkeypatch.setattr(SZK, "_szk_porget", lambda: ("csod",))
    a = h.akcio("A", "porget")
    assert a["soron"] == "B" and h.korpenz["A"] == 0


def test_maganhangzora_is_lehet_tippelni(monkeypatch):
    # ÚJ szabály: nincs magánhangzó-VÉTEL – a magánhangzóra ugyanúgy TIPPELSZ,
    # mint a mássalhangzóra (pörgetés után, az érték a darabszámmal szorzódik).
    h = _host(monkeypatch)               # megoldás ALMA – 2 db 'a'
    monkeypatch.setattr(SZK, "_szk_porget", lambda: ("penz", 100))
    h.akcio("A", "porget")
    a = h.akcio("A", "betu", "a")        # 2 db 'a' × 100 = 200, felfedve, jöhet újra
    assert "a" in h.felfedett
    assert h.korpenz["A"] == 200 and a["soron"] == "A"


def test_maganhangzo_akcio_mar_nincs(monkeypatch):
    # a régi „venni" akció megszűnt: ismeretlen tipus → None (nincs hatás)
    h = _host(monkeypatch)
    monkeypatch.setattr(SZK, "_szk_porget", lambda: ("penz", 100))
    h.akcio("A", "porget")
    assert h.akcio("A", "maganhangzo", "a") is None
    assert "a" not in h.felfedett


def test_megfejtes_nyer_es_vege(monkeypatch):
    h = _host(monkeypatch)
    monkeypatch.setattr(SZK, "_szk_porget", lambda: ("penz", 100))
    h.akcio("A", "porget")
    h.akcio("A", "betu", "l")               # korpenz 100
    a = h.akcio("A", "megfejt", "alma")     # ékezet/kisbetű nem számít
    assert a["fazis"] == "vege"
    assert h.bank["A"] == 100
    assert "győztes" in a["uzenet"].lower()


def test_ablak_es_indithato():
    # az online a Szerencsekeréken BELÜL van (lapfül), nincs külön játék
    assert hasattr(OL, "SzerencseAblak") and hasattr(OL, "OnlinePanel")
    KON = importlib.import_module(BASE + ".jatekkonzol")
    assert KON.indithato("szerencsekerek") is True
    KAT = importlib.import_module(BASE + ".katalogus")
    assert KAT.keres("szerencsekerek_online") is None      # már nincs külön
