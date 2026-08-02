# -*- coding: utf-8 -*-
"""Két új RETRÓ port tesztjei: KOCKAPÓKER (dice-poker) és TOTÓ – 8 bites
jingle-kkel. A kéz-értékelő tiszta függvényt közvetlenül ellenőrizzük, a teljes
partikat egy-egy bot játssza végig."""
import importlib

import pytest

BASE = "modules_src.jatekok.jatekok_mod"
JR = pytest.importorskip(BASE + ".jatekok")
U = importlib.import_module(BASE + ".jatekok._util")
HL = importlib.import_module(BASE + ".jatekok.homelab")
KAT = importlib.import_module(BASE + ".katalogus")


# ==================================================================== KÉZ-ÉRTÉK

def test_kockapoker_kez_ertekeles():
    e = HL._kockapoker_ertek
    assert e([3, 3, 3, 3, 3])[0] == 100          # öt egyforma (póker)
    assert e([5, 5, 5, 5, 1])[0] == 80           # négy egyforma
    assert e([2, 3, 4, 5, 6])[0] == 70           # nagy sor
    assert e([4, 4, 4, 2, 2])[0] == 60           # full
    assert e([1, 2, 3, 4, 5])[0] == 50           # kis sor
    assert e([6, 6, 6, 1, 2])[0] == 40           # három egyforma
    assert e([6, 6, 2, 2, 3])[0] == 30           # két pár
    assert e([6, 6, 1, 2, 3])[0] == 20           # egy pár
    assert e([1, 2, 3, 4, 6])[0] == 5            # semmi
    # az erőssorrend monoton
    assert (e([3, 3, 3, 3, 3])[0] > e([5, 5, 5, 5, 1])[0] > e([2, 3, 4, 5, 6])[0]
            > e([4, 4, 4, 2, 2])[0] > e([1, 2, 3, 4, 5])[0])


def test_jinglek_frekvencia_hossz_parok():
    """A 8 bites jingle-k (frekvencia_Hz, hossz_ms) párokból állnak."""
    for j in (HL._JINGLE_START, HL._JINGLE_GYOZ, HL._JINGLE_VESZT,
              HL._JINGLE_JO, HL._JINGLE_ROSSZ):
        assert j and all(len(t) == 2 and t[0] > 0 and t[1] > 0 for t in j)


# ==================================================================== KOCKAPÓKER

class _KpBot:
    def __call__(self, k, ki):
        kl = k.lower()
        if "szabályokat" in kl:
            return "N"
        if "hány menet" in kl:
            return "1"
        if "melyeket dobod" in kl:
            return "állok"                       # megtartom az első dobást
        return ""


def test_kockapoker_lejatszik():
    ki = U.lejatsz(JR.REGISZTER["kockapoker"], _KpBot())
    assert ki[-1][0] == "vege"
    txt = "\n".join(p for _, p in ki if isinstance(p, str))
    assert "KOCKAPÓKER" in txt.upper()
    assert ("A kezed:" in txt) and ("Az én kezem:" in txt)
    assert any(s in txt for s in ("Megnyerted", "Én nyertem", "Döntetlen"))
    # szólt-e 8 bites hang (a jingle-k „hang" parancsként jelennek meg)
    assert any(t == "hang" for t, _ in ki)


# ======================================================================= TOTÓ

class _TotoBot:
    def __call__(self, k, ki):
        kl = k.lower()
        if "tipposzlopot" in kl:
            return ""                            # Enter a kezdéshez
        if "mérkőzés tippje" in kl:
            return "1"
        return ""


def test_toto_lejatszik_es_szamol():
    ki = U.lejatsz(JR.REGISZTER["totozzon"], _TotoBot())
    assert ki[-1][0] == "vege"
    txt = "\n".join(p for _, p in ki if isinstance(p, str))
    assert "TOTÓ" in txt.upper()
    assert "A találataid száma:" in txt
    assert "A hivatalos végeredmények:" in txt
    assert any(t == "hang" for t, _ in ki)


def test_toto_ervenytelen_tipp_visszautasitva():
    def bot(k, ki):
        kl = k.lower()
        if "tipposzlopot" in kl:
            return ""
        if "mérkőzés tippje" in kl:
            if not getattr(bot, "hibazott", False):
                bot.hibazott = True
                return "9"                       # érvénytelen → elutasítva
            return "x"
        return ""
    ki = U.lejatsz(JR.REGISZTER["totozzon"], bot)
    txt = "\n".join(p for _, p in ki if isinstance(p, str))
    assert "Egyértelmű választ kérek" in txt


# ---- katalógus / regiszter

def test_uj_ket_jatek_a_katalogusban():
    for kulcs in ("kockapoker", "totozzon"):
        assert JR.van(kulcs)
        j = KAT.keres(kulcs)
        assert j is not None and j.retro is True
        # ismeretlen szerző → tisztességes felirat
        assert "Modernizálta Kőrösmezey Dávid" in KAT.attribucio_szoveg(j)
