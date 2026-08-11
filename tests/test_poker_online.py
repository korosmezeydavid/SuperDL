# -*- coding: utf-8 -*-
"""Póker online HOST-motor (PokerHost) tesztjei – fejetlen, pure-Python.

A kéz-értékelőt közvetlenül, a tétkör/csere/leleplezés logikát a kezek/pakli
determinisztikus beállításával ellenőrizzük."""
import importlib

import pytest

BASE = "modules_src.jatekok.jatekok_mod"
PO = importlib.import_module(BASE + ".poker_online")


# ------------------------------------------------------------------ kéz-értékelő
def test_poker_ertek_rangsor():
    szinsor = [("pikk", "10"), ("pikk", "bubi"), ("pikk", "dáma"),
               ("pikk", "király"), ("pikk", "ász")]
    negy = [("pikk", "7"), ("kör", "7"), ("káró", "7"), ("treff", "7"),
            ("pikk", "2")]
    full = [("pikk", "7"), ("kör", "7"), ("káró", "7"), ("treff", "2"),
            ("pikk", "2")]
    floss = [("pikk", "2"), ("pikk", "5"), ("pikk", "9"), ("pikk", "bubi"),
             ("pikk", "király")]
    sor = [("pikk", "5"), ("kör", "6"), ("káró", "7"), ("treff", "8"),
           ("pikk", "9")]
    wheel = [("pikk", "ász"), ("kör", "2"), ("káró", "3"), ("treff", "4"),
             ("pikk", "5")]
    par = [("pikk", "8"), ("kör", "8"), ("káró", "2"), ("treff", "5"),
           ("pikk", "király")]
    magas = [("pikk", "2"), ("kör", "5"), ("káró", "8"), ("treff", "bubi"),
             ("pikk", "király")]
    assert PO.poker_ertek(szinsor)[0] == 8
    assert PO.poker_ertek(negy)[0] == 7
    assert PO.poker_ertek(full)[0] == 6
    assert PO.poker_ertek(floss)[0] == 5
    assert PO.poker_ertek(sor)[0] == 4
    assert PO.poker_ertek(wheel) == (4, [5])          # ász-alsó sor teteje 5
    assert PO.poker_ertek(par)[0] == 1
    assert PO.poker_ertek(magas)[0] == 0
    assert PO.poker_ertek(par) > PO.poker_ertek(magas)


# ------------------------------------------------------------------ osztás
def test_osztas_ante_es_kezek():
    h = PO.PokerHost(["A", "B"], kezdo_zseton=200, ante=10)
    assert h.fazis == "tet1" and h.pot == 20          # 2 × ante
    assert h.zseton["A"] == 190 and h.zseton["B"] == 190
    assert len(h.kez("A")) == 5 and len(h.kez("B")) == 5
    assert h.soron == "A"
    a = h.allapot_publikus()
    assert a["lapszamok"] == {"A": 5, "B": 5}
    assert "kezek" not in a                            # privát kéz nincs a publikusban


# ------------------------------------------------------------------ tétkör
def test_check_around_zar_a_cserere():
    h = PO.PokerHost(["A", "B"])
    h.akcio("A", "megad")                              # check (tet_szint 0)
    assert h.soron == "B" and h.fazis == "tet1"
    h.akcio("B", "megad")                              # check → tétkör zárul
    assert h.fazis == "csere"


def test_emel_majd_megad():
    h = PO.PokerHost(["A", "B"], kezdo_zseton=200, ante=10)
    h.akcio("A", "emel")                               # nyit 20
    assert h.tet_szint == 20 and h.soron == "B"
    h.akcio("B", "megad")                              # call 20 → zárul
    assert h.fazis == "csere"
    assert h.pot == 20 + 20 + 20                       # ante + A20 + B20
    assert h.zseton["A"] == 170 and h.zseton["B"] == 170


def test_bedob_egy_marad_viszi_a_potot():
    h = PO.PokerHost(["A", "B"], kezdo_zseton=200, ante=10)
    h.akcio("A", "dob")                                # A fold → B viszi
    assert h.fazis == "vege" and h.gyoztes == ["B"]
    assert h.zseton["B"] == 190 + 20                   # ante vissza + A ante


# ------------------------------------------------------------------ csere
def test_csere_lapokat_pototol():
    h = PO.PokerHost(["A", "B"])
    h.akcio("A", "megad")
    h.akcio("B", "megad")                              # → csere fázis
    assert h.fazis == "csere" and h.soron == "A"
    regi = list(h.kez("A"))
    h.akcio("A", "csere", {"indexek": [0, 1]})         # 2 lap csere
    assert len(h.kez("A")) == 5
    assert h.soron == "B"
    h.akcio("B", "csere", {"indexek": []})             # B nem cserél → tet2
    assert h.fazis == "tet2"


# ------------------------------------------------------------------ leleplezés
def test_leleplezes_jobb_kez_nyer():
    h = PO.PokerHost(["A", "B"])
    h.kezek["A"] = [("pikk", "2"), ("pikk", "5"), ("pikk", "9"),
                    ("pikk", "bubi"), ("pikk", "király")]     # SZÍN
    h.kezek["B"] = [("pikk", "8"), ("kör", "8"), ("káró", "2"),
                    ("treff", "5"), ("pikk", "10")]           # EGY PÁR
    h.statusz = {"A": "jatszik", "B": "jatszik"}
    h.pot = 100
    h.zseton = {"A": 0, "B": 0}
    h._leleplezes()
    assert h.fazis == "vege" and h.gyoztes == ["A"]
    assert h.zseton["A"] == 100 and h.zseton["B"] == 0
    a = h.allapot_publikus()
    assert a["leleplezes_nev"]["A"] == "SZÍN (flöss)"


def test_leleplezes_dontetlen_oszt():
    h = PO.PokerHost(["A", "B"])
    h.kezek["A"] = [("pikk", "8"), ("kör", "8"), ("káró", "2"),
                    ("treff", "5"), ("pikk", "király")]
    h.kezek["B"] = [("treff", "8"), ("káró", "8"), ("pikk", "2"),
                    ("kör", "5"), ("treff", "király")]         # ugyanaz az érték
    h.statusz = {"A": "jatszik", "B": "jatszik"}
    h.pot = 100
    h.zseton = {"A": 0, "B": 0}
    h._leleplezes()
    assert set(h.gyoztes) == {"A", "B"}
    assert h.zseton["A"] == 50 and h.zseton["B"] == 50         # osztott pot


# ------------------------------------------------------------------ teljes leosztás
def test_teljes_leosztas_veget_er():
    import random
    random.seed(4)
    h = PO.PokerHost(["A", "B", "C"], kezdo_zseton=200, ante=10)
    guard = 0
    while h.fazis != "vege" and guard < 200:
        guard += 1
        ki = h.soron
        if not ki:
            break
        if h.fazis == "csere":
            h.akcio(ki, "csere", {"indexek": []})      # senki sem cserél
        else:
            h.akcio(ki, "megad")                       # mindenki checkel/megad
    assert h.fazis == "vege"
    assert h.gyoztes and all(g in h.jatekosok for g in h.gyoztes)
    # a pot teljesen kiosztva (a zsetonok összege állandó)
    assert sum(h.zseton.values()) == 3 * 200
