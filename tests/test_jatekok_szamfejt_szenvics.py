# -*- coding: utf-8 -*-
"""Két új RETRÓ port tesztjei: SZÁMFEJTŐ és SZENDVICSPARTI (Kisvarga Zsolt).

A játékokat egy-egy „okos" bot játssza végig: a Számfejtőnél a kihirdetett négy
számból gyárt érvényes variációkat (és egy ismétlést a hibapont-ág tesztjéhez),
a Szendvicspartinál végigugorja a rövid távot."""
import importlib
import re

import pytest

BASE = "modules_src.jatekok.jatekok_mod"
JR = pytest.importorskip(BASE + ".jatekok")
U = importlib.import_module(BASE + ".jatekok._util")
KAT = importlib.import_module(BASE + ".katalogus")


# ==================================================================== SZÁMFEJTŐ

class _SzamfejtBot:
    def __init__(self):
        self.n = 0

    def __call__(self, k, ki):
        kl = k.lower()
        if "játékszabály" in kl:
            return "N"
        if "variáció" in kl:
            szamok = []
            for _, p in ki:
                if "A négy szám:" in p:
                    seg = p.split("A négy szám:")[1].split("Ezt")[0]
                    szamok = re.findall(r"\d", seg)
                    break
            if len(szamok) < 4:
                return "kész"
            a, b, c, _d = szamok
            self.n += 1
            if self.n == 1:
                return a + b + c            # érvényes
            if self.n == 2:
                return a + c + b            # érvényes, más sorrend
            if self.n == 3:
                return b + a + c            # érvényes
            if self.n == 4:
                return a + b + c            # ISMÉTLÉS → hibapont
            return "kész"
        return ""


def test_szamfejt_kisvarga_lejatszik_es_hibapont():
    ki = U.lejatsz(JR.REGISZTER["szamfejt"], _SzamfejtBot())
    assert ki[-1][0] == "vege"
    txt = "\n".join(p for _, p in ki)
    assert "SZÁMFEJTŐ" in txt.upper()
    assert "hibapont jár" in txt            # az ismétlést bünteti
    assert "Eredményhirdetés" in txt
    # 3 jó variáció = 9 pont, 1 hibapont → 9 - 6 = 3
    assert "A végső pontszámod: 3." in txt


def test_szamfejt_ervenytelen_bevitel_visszautasitva():
    """Nem háromjegyű / a négyen kívüli / ismétlődő számjegyű bevitel elutasítva."""
    def bot(k, ki):
        kl = k.lower()
        if "játékszabály" in kl:
            return "N"
        if "variáció" in kl:
            if not getattr(bot, "lepett", False):
                bot.lepett = True
                return "12"                 # csak kétjegyű → elutasítva
            return "kész"
        return ""
    ki = U.lejatsz(JR.REGISZTER["szamfejt"], bot)
    txt = "\n".join(p for _, p in ki)
    assert "háromjegyű" in txt


# ================================================================ SZENDVICSPARTI

class _SzenvicsBot:
    def __init__(self):
        self.kert_allast = False

    def __call__(self, k, ki):
        kl = k.lower()
        if "utóneved" in kl:
            return "Teszt"
        if "ismertetőt" in kl:
            return "N"
        if "fokozatán állítani" in kl:
            return "N"
        if "hány méter" in kl:
            return "60"
        if "ugrasz" in kl:
            if not self.kert_allast:
                self.kert_allast = True
                return "?"                  # egyszer az állást kérjük
            return "U"
        return ""


def test_szenvics_kisvarga_vegigjatszik():
    ki = U.lejatsz(JR.REGISZTER["szenvics"], _SzenvicsBot())
    assert ki[-1][0] == "vege"
    txt = "\n".join(p for _, p in ki)
    assert "SZENDVICSPARTI" in txt.upper()
    assert "szendvics" in txt.lower()
    assert "méter van hátra" in txt         # a ? = állás működik
    assert ("GYŐZTÉL" in txt) or ("most én nyertem" in txt)


# ---- katalógus / szerző

def test_uj_jatekok_kisvarga_zsolttal():
    for kulcs in ("szamfejt", "szenvics"):
        assert JR.van(kulcs)
        j = KAT.keres(kulcs)
        assert j is not None and j.retro is True
        assert "Kisvarga Zsolt" in KAT.attribucio_szoveg(j)
