# -*- coding: utf-8 -*-
"""Új kis játékok: Varázsgömb (figyelem) és Ki nevet a végén (tábla)."""
import importlib
import re

import pytest

BASE = "modules_src.jatekok.jatekok_mod"
JR = pytest.importorskip(BASE + ".jatekok")
U = importlib.import_module(BASE + ".jatekok._util")
TABLA = importlib.import_module(BASE + ".jatekok.tabla")
SZOJATEK = importlib.import_module(BASE + ".jatekok.szojatek")
KAT = importlib.import_module(BASE + ".katalogus")


def test_regiszter_es_katalogus():
    for kulcs in ("varazsgomb", "kinevet", "egyszo"):
        assert kulcs in JR.REGISZTER
        assert any(j.kulcs == kulcs for j in KAT.RETRO)


# ---- Egy szó mint száz ----
def test_egyszo_okos_jatekos_pontot_szerez():
    meg2szo = {m: s for s, m in SZOJATEK._SZOTAR}
    abc2szo = {" ".join(sorted(s.lower())): s for s, m in SZOJATEK._SZOTAR}
    allap = {"korok": 0}

    def bot(k, ki):
        kl = k.lower()
        if "következő szó" in kl:
            allap["korok"] += 1
            return "igen" if allap["korok"] < 4 else "nem"
        if "mi a szó" in kl:
            for typ, p in reversed(ki):
                if typ == "mond" and "A meghatározás:" in p:
                    m = p.split("A meghatározás:", 1)[1].rsplit(
                        " A szó", 1)[0].strip()
                    return meg2szo.get(m, "feladom")
                if typ == "mond" and "ábécérendben" in p:
                    bet = p.split("következnek:", 1)[1].rsplit(
                        " A szó", 1)[0].strip().rstrip(".")
                    return abc2szo.get(bet, "feladom")
            return "feladom"
        return ""
    ki = U.lejatsz(JR.REGISZTER["egyszo"], bot, max_lepes=20000)
    assert ki[-1][0] == "vege"
    # a helyes tippekért fortuna jár, tehát a végösszeg pozitív
    veg = [p for t, p in ki if "végeredménye" in p]
    assert veg and "0 fortuna" not in veg[0]


def test_egyszo_feladas_es_betu_segitseg():
    def bot(k, ki):
        kl = k.lower()
        if "következő szó" in kl:
            return "nem"
        if "mi a szó" in kl:
            bot.c = getattr(bot, "c", 0) + 1
            return "segítség" if bot.c < 4 else "feladom"
        return ""
    ki = U.lejatsz(JR.REGISZTER["egyszo"], bot, max_lepes=20000)
    assert ki[-1][0] == "vege"
    assert any("Adok egy betűt" in p for _, p in ki)


# ---- Varázsgömb ----
def test_varazsgomb_figyelmes_jatekos_tokeleteset_er_el():
    SZAVAK = ["egy", "ketto", "harom", "negy", "ot", "hat", "het", "nyolc",
              "kilenc", "tiz"]
    allap = {"szo": 0, "szamlalt": None}

    def bot(k, ki):
        kl = k.lower()
        if "szó:" in kl:
            allap["szo"] += 1
            return SZAVAK[allap["szo"] - 1]
        if "fordulatszám" in kl:
            return "12"
        if "felkészültél" in kl:
            return "igen"
        if "játszunk még" in kl:
            return "nem"
        if "hányszor mondtam" in kl:
            if allap["szamlalt"] is None:
                cnt = {w: 0 for w in SZAVAK}
                start = False
                for typ, p in ki:
                    if typ == "mond" and "forog a varázsgömb" in p:
                        start = True
                        continue
                    if typ == "mond" and "Gondold át" in p:
                        break
                    if start and typ == "mond" and p in cnt:
                        cnt[p] += 1
                allap["szamlalt"] = cnt
            m = re.search(r"hogy (.+?)\?", k)   # pontos szó a kérdésből
            if m and m.group(1) in allap["szamlalt"]:
                return str(allap["szamlalt"][m.group(1)])
            return "0"
        return ""
    ki = U.lejatsz(JR.REGISZTER["varazsgomb"], bot, max_lepes=20000)
    assert ki[-1][0] == "vege"
    assert any("Kiváló eredmény" in p for _, p in ki)


# ---- Ki nevet a végén ----
def _kinevet_bot(k, ki):
    kl = k.lower()
    if "még egyet" in kl:
        return "nem"
    if "melyik bábuddal" in kl:
        m = re.search(r"\(([\d, ]+)", k)
        if m:
            for tok in m.group(1).split(","):
                if tok.strip().isdigit():
                    return tok.strip()
    return "1"


def test_kinevet_veget_er_es_van_gyoztes():
    ki = U.lejatsz(JR.REGISZTER["kinevet"], _kinevet_bot, max_lepes=300000)
    assert ki and ki[-1][0] == "vege"
    txt = " ".join(p for _, p in ki)
    assert ("NYERTÉL" in txt) or ("én nyertem" in txt)


def test_kinevet_utes_visszakuldi_a_babut():
    g = {"J": [None, None, None, None], "G": [None, None, None, None]}
    # a gép 1. bábuja a 25. lépésnél áll: abs = (20+25-1)%40 = 4
    g["G"][0] = 25
    # a játékos 2. bábuja a 4. lépésnél (abs 3); egy 1-es dobással az 5.-re
    # lép, ahol abs = (0+5-1)%40 = 4 -> ütés
    g["J"][1] = 4
    assert TABLA._abs_mezo("G", g["G"][0]) == 4
    cel, utes = TABLA._lep(g, "J", 1, 1)
    assert cel == 5
    assert utes == 1                     # a gép 1. bábuját ütöttük
    assert g["G"][0] is None             # visszakerült a bázisra


def test_kinevet_bazisrol_csak_egy_vagy_hat():
    g = {"J": [None, None, None, None], "G": [None, None, None, None]}
    assert TABLA._legal(g, "J", 3) == []          # 3-mal nem lehet kilépni
    assert TABLA._legal(g, "J", 1) == [0, 1, 2, 3]
    assert TABLA._legal(g, "J", 6) == [0, 1, 2, 3]
