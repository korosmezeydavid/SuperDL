# -*- coding: utf-8 -*-
"""Blackjack online HOST-motor (BlackjackHost) tesztjei – fejetlen, pure-Python.

A lap-összeg és az elszámolás determinisztikus (a keverést kikapcsoljuk vagy a
kezeket közvetlenül állítjuk); egy több körös partit egy egyszerű bot játszik."""
import importlib

import pytest

pytest.importorskip("wx")            # a blackjack_online a UI-panel miatt wx-et importál
BASE = "modules_src.jatekok.jatekok_mod"
BJ = importlib.import_module(BASE + ".blackjack_online")


def test_osszeg_asz_lagy_es_kemeny():
    assert BJ.osszeg([("pikk", "ász"), ("kör", "király")]) == 21
    assert BJ.blackjack([("pikk", "ász"), ("kör", "király")])
    # két ász + 9: 11+1+9 = 21 (az egyik ász 1-re vált)
    assert BJ.osszeg([("pikk", "ász"), ("kör", "ász"), ("káró", "9")]) == 21
    # túllépés
    assert BJ.osszeg([("pikk", "király"), ("kör", "dáma"), ("káró", "5")]) == 25


@pytest.fixture
def fix_pakli(monkeypatch):
    # a keverés kikapcsolása → determinisztikus osztás (a pakli végéről oszt)
    monkeypatch.setattr(BJ.random, "shuffle", lambda x: None)


def test_osztas_es_rejtett_oszto(fix_pakli):
    h = BJ.BlackjackHost(["A", "B"], kezdo_zseton=100, tet=10)
    assert h.fazis == "jatek" and h.soron == "A"
    assert len(h.kezek["A"]) == 2 and len(h.kezek["B"]) == 2
    assert h.zseton["A"] == 90 and h.zseton["B"] == 90     # tét levonva
    a = h.allapot_publikus()
    # az osztó MÁSODIK lapja rejtett, az összege nem látszik
    assert a["oszto_lapok"][1] == ["rejtett", "rejtett"]
    assert a["oszto_osszeg"] is None


def test_csak_a_soron_levo_lephet(fix_pakli):
    h = BJ.BlackjackHost(["A", "B"])
    assert h.akcio("B", "hit") is None       # A van soron
    assert h.soron == "A"


def test_hit_bust_lep_tovabb(fix_pakli):
    h = BJ.BlackjackHost(["A", "B"])          # A és B is 20 a fix pakliból
    assert BJ.osszeg(h.kezek["A"]) == 20
    h.akcio("A", "hit")                       # a következő lap 7 → 27, bust
    assert h.statusz["A"] == "bust" and h.soron == "B"


def test_stand_lep_tovabb(fix_pakli):
    h = BJ.BlackjackHost(["A", "B"])
    h.akcio("A", "stand")
    assert h.statusz["A"] == "all" and h.soron == "B"


def test_dupla_levon_es_egy_lap(fix_pakli):
    h = BJ.BlackjackHost(["A", "B"])          # A: 20, zseton 90, tét 10
    h.akcio("A", "dupla")                     # +7 → 27 bust, tét duplázva
    assert h.tet["A"] == 20 and h.zseton["A"] == 80
    assert len(h.kezek["A"]) == 3 and h.statusz["A"] == "bust"
    assert h.soron == "B"


def test_oszto_17ig_huz_es_nyer(fix_pakli):
    h = BJ.BlackjackHost(["A"])
    h.kezek["A"] = [("pikk", "10"), ("kör", "9")]     # 19
    h.statusz["A"] = "all"
    h.tet["A"], h.zseton["A"] = 10, 90
    h.oszto = [("pikk", "5"), ("kör", "2")]           # 7 – húznia kell
    h.oszto_rejtett = True
    h.aktiv_idx, h.fazis = None, "jatek"
    h.pakli = [("káró", "10"), ("káró", "10")]        # két tízes → 7+10=17, megáll
    h._oszto_es_zaras()
    assert BJ.osszeg(h.oszto) >= 17 and h.fazis == "vege"
    assert h.zseton["A"] == 110 and h.eredmeny["A"] == "nyert"   # 19 > 17


def test_blackjack_3_2_kifizet(fix_pakli):
    h = BJ.BlackjackHost(["A"])
    h.kezek["A"] = [("pikk", "ász"), ("kör", "király")]
    h.statusz["A"] = "blackjack"
    h.tet["A"], h.zseton["A"] = 10, 90
    h.oszto = [("pikk", "9"), ("kör", "7")]           # 16, nem blackjack
    h.oszto_rejtett = True
    h.aktiv_idx, h.fazis = None, "jatek"
    h.pakli = [("káró", "2")]                          # 16 < 17 → +2 = 18
    h._oszto_es_zaras()
    assert h.zseton["A"] == 90 + int(10 * 2.5)         # 3:2 → +25 = 115
    assert "BLACKJACK" in h.eredmeny["A"]


def test_oszto_tullepes_mindenki_nyer(fix_pakli):
    h = BJ.BlackjackHost(["A"])
    h.kezek["A"] = [("pikk", "10"), ("kör", "7")]      # 17
    h.statusz["A"] = "all"
    h.tet["A"], h.zseton["A"] = 10, 90
    h.oszto = [("pikk", "10"), ("kör", "6")]           # 16 – húz
    h.oszto_rejtett = True
    h.aktiv_idx, h.fazis = None, "jatek"
    h.pakli = [("káró", "király")]                     # 16 + 10 = 26 → osztó bust
    h._oszto_es_zaras()
    assert BJ.osszeg(h.oszto) > 21
    assert h.zseton["A"] == 110 and h.eredmeny["A"] == "nyert"


def _drive_round(h):
    guard = 0
    while h.fazis == "jatek" and guard < 300:
        guard += 1
        ki = h.soron
        if not ki:
            break
        if BJ.osszeg(h.kezek[ki]) < 17:
            h.akcio(ki, "hit")
        else:
            h.akcio(ki, "stand")
    assert h.fazis == "vege"


def test_tobb_koros_parti_zseton_nem_negativ():
    import random
    random.seed(12)
    h = BJ.BlackjackHost(["A", "B", "C"], kezdo_zseton=100, tet=10)
    korok = 0
    for _ in range(40):
        _drive_round(h)
        for n in h.jatekosok:
            assert h.zseton[n] >= 0            # sosem megy mínuszba
            assert n in h.eredmeny             # mindenki elszámolva
        korok += 1
        if all(h.zseton[n] < h.alap_tet for n in h.jatekosok):
            break
        h.uj_leosztas()
    assert korok >= 1
