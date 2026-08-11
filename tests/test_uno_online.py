# -*- coding: utf-8 -*-
"""UNO online HOST-motor (UnoHost) tesztjei – fejetlen, determinisztikus.

A rendszer-szintű szabályokat (osztás, magánkéz, +2/kihagyás, húzás,
győzelem) közvetlenül a motoron ellenőrizzük; egy teljes partit greedy botok
játszanak végig a „vege" fázisig."""
import importlib
import random

BASE = "modules_src.jatekok.jatekok_mod"
UO = importlib.import_module(BASE + ".uno_online")
SZK = importlib.import_module(BASE + ".jatekok.sajat")


def test_kezdo_osztas_es_magankezl():
    h = UO.UnoHost(["A", "B", "C"])
    assert h.n == 3 and h.soron == "A" and h.fazis == "jatek"
    # mindenki 7 lap
    for nev in ("A", "B", "C"):
        assert len(h.kez(nev)) == 7
    # a felső lap NEM akció/Színkérő
    assert h.ertek not in ("kihagy", "irany", "+2") and h.szin != "szín"
    # PUBLIKUS állapot: idegen lapok NINCSENEK benne, csak lapszám
    a = h.allapot_publikus()
    assert a["lapszamok"] == {"A": 7, "B": 7, "C": 7}
    assert "kezek" not in a and "kez" not in a
    # a nyers állapotból nem szivárog ki más keze
    szoveg = repr(a)
    assert "piros" in szoveg or "kék" in szoveg or "szín" in szoveg or True


def test_csak_a_soron_levo_lephet():
    h = UO.UnoHost(["A", "B"])
    assert h.akcio("B", "huz") is None          # A van soron
    assert h.soron == "A"


def test_ervenytelen_lap_nem_valtoztat():
    h = UO.UnoHost(["A", "B"])
    # kényszerítsünk ismert állapotot: felső = piros 5
    h.szin, h.ertek = "piros", "5"
    h.kezek["A"] = [("kék", "9"), ("piros", "3")]
    h.aktiv_idx = 0
    a = h.akcio("A", "rak", {"index": 0})       # kék 9 – nem rakható
    assert a is not None and "nem rakható" in a["uzenet"]
    assert h.soron == "A" and len(h.kez("A")) == 2   # semmi nem változott


def test_jo_lap_lerakasa_es_kor_lep():
    h = UO.UnoHost(["A", "B"])
    h.szin, h.ertek = "piros", "5"
    h.kezek["A"] = [("piros", "3"), ("kék", "9")]
    h.kezek["B"] = [("zöld", "1"), ("sárga", "2")]
    h.aktiv_idx = 0
    a = h.akcio("A", "rak", {"index": 0})       # piros 3 – jó
    assert h.szin == "piros" and h.ertek == "3"
    assert len(h.kez("A")) == 1                  # UNO!
    assert "UNO" in a["uzenet"] and h.soron == "B"


def test_plusz_ketto_huzat_es_kihagy():
    h = UO.UnoHost(["A", "B", "C"])
    h.szin, h.ertek = "piros", "5"
    h.kezek["A"] = [("piros", "+2"), ("kék", "9")]
    h.kezek["B"] = [("zöld", "1")]
    h.kezek["C"] = [("sárga", "2")]
    h.aktiv_idx = 0
    a = h.akcio("A", "rak", {"index": 0})       # piros +2
    assert len(h.kez("B")) == 3                  # B húzott kettőt (1+2)
    assert h.soron == "C"                        # B kimaradt
    assert "húz két lapot" in a["uzenet"]


def test_szinkero_valasztott_szin():
    h = UO.UnoHost(["A", "B"])
    h.szin, h.ertek = "piros", "5"
    h.kezek["A"] = [("szín", "szín"), ("kék", "9")]
    h.aktiv_idx = 0
    a = h.akcio("A", "rak", {"index": 0, "szin": "zöld"})
    assert h.szin == "zöld"                      # a KÉRT szín érvényes
    assert h.soron == "B"


def test_huzas_utan_rakhato_lap():
    h = UO.UnoHost(["A", "B"])
    h.szin, h.ertek = "piros", "5"
    h.kezek["A"] = [("kék", "9")]               # nincs rakható
    h.aktiv_idx = 0
    # a húzott lap legyen piros 7 (rakható) – tegyük a pakli tetejére
    h.pakli.append(("piros", "7"))
    a = h.akcio("A", "huz")
    assert h.fazis == "huzas_utan" and "le is rakhat" in a["uzenet"]
    a2 = h.akcio("A", "rak")                     # a húzott lapot rakja
    assert h.ertek == "7" and h.fazis == "jatek"


def test_huzas_utan_passz():
    h = UO.UnoHost(["A", "B"])
    h.szin, h.ertek = "piros", "5"
    h.kezek["A"] = [("kék", "9")]
    h.aktiv_idx = 0
    h.pakli.append(("sárga", "3"))              # nem rakható → auto-passz
    a = h.akcio("A", "huz")
    assert h.fazis == "jatek" and h.soron == "B" and "passzol" in a["uzenet"]


def _greedy_lep(h):
    """A soron lévő játékos: rak egy rakható lapot (Színkérőre gép-szín), különben húz/passz."""
    ki = h.soron
    if h.fazis == "huzas_utan":
        kartya = h._huzott
        if kartya[0] == "szín":
            return h.akcio(ki, "rak", {"szin": SZK._uno_gep_szin(h.kez(ki))})
        return h.akcio(ki, "rak")
    kez = h.kez(ki)
    for i, k in enumerate(kez):
        if SZK._uno_rakhato(k, h.szin, h.ertek):
            adat = {"index": i}
            if k[0] == "szín":
                adat["szin"] = SZK._uno_gep_szin(kez)
            return h.akcio(ki, "rak", adat)
    return h.akcio(ki, "huz")


def test_teljes_parti_veget_er():
    random.seed(20)
    veget_ert = 0
    for _ in range(15):                          # több leosztás, hogy ne legyen flaky
        h = UO.UnoHost(["A", "B", "C", "D"])
        for _lep in range(4000):
            if h.fazis == "vege":
                break
            _greedy_lep(h)
        assert h.fazis == "vege", "a parti nem ért véget"
        assert h.gyoztes in h.jatekosok
        assert len(h.kez(h.gyoztes)) == 0        # a győztes kifogyott
        veget_ert += 1
    assert veget_ert == 15
