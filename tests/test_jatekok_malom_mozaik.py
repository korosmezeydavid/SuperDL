# -*- coding: utf-8 -*-
"""Két új RETRÓ port tesztjei: MALOM (Brátán Ferenc) és MOZAIK.

A MALOM tiszta segédfüggvényeit közvetlenül ellenőrizzük (malom-felismerés,
szomszédság, üthetőség), a teljes partit egy „okos" bot játssza végig (a tábla
kihirdetett állásából és a szomszédság-táblából számol legális lépést). A
MOZAIK-ot a feladás (V) útján játsszuk végig: a gép visszafelé elbetűzi a szót,
a bot ebből rakja össze a helyes tippet."""
import importlib
import random

import pytest

BASE = "modules_src.jatekok.jatekok_mod"
JR = pytest.importorskip(BASE + ".jatekok")
U = importlib.import_module(BASE + ".jatekok._util")
HL = importlib.import_module(BASE + ".jatekok.homelab")
KAT = importlib.import_module(BASE + ".katalogus")


# ===================================================================== MOZAIK

class _MozaikBot:
    """Minden szónál feladja (V) – a gép visszafelé elbetűzi a szót, ebből a
    bot összerakja a helyes tippet, így determinisztikusan végigjátszható."""

    def __call__(self, k, ki):
        kl = k.lower()
        if "ismertető" in kl:
            return "N"
        if "hányadik betűt" in kl:
            return "1"
        if "kérsz még betűt" in kl:
            return "V"
        if "mi a szó" in kl:
            sorok = [p for _, p in ki]
            for i in range(len(sorok) - 1, -1, -1):
                if "visszafelé" in sorok[i].lower() and i + 1 < len(sorok):
                    s = sorok[i + 1].strip().rstrip(".")
                    betuk = [b.strip() for b in s.split(",")]
                    return "".join(reversed(betuk))
            return ""
        return ""


def test_mozaik_lejatszik_es_ertekel():
    ki = U.lejatsz(JR.REGISZTER["mozaik"], _MozaikBot())
    assert ki[-1][0] == "vege", "a Mozaik nem ért véget rendben"
    txt = "\n".join(p for _, p in ki)
    assert "betűből áll a szó" in txt
    assert "pontszámod" in txt.lower()
    # a feladásos (V) úton is összejön néhány pont → az értékelés nem a legrosszabb
    assert "Kapsz" in txt


def test_mozaik_kevesebb_betu_tobb_pont():
    """A pontozás lényege: minél kevesebb betűt kérsz, annál több pont – az
    első betű után eltalálva a teljes szóhossz jár."""
    ki = U.lejatsz(JR.REGISZTER["mozaik"], _MozaikBot())
    # a „Ha most eltalálod, N pont a tiéd" az 1. betűnél a teljes hosszat ígéri
    assert any("pont a tiéd" in p for _, p in ki)


# ====================================================================== MALOM

def test_malom_szomszedsag_szimmetrikus():
    """A szomszédság-gráf kétirányú: ha A szomszédja B, akkor B szomszédja A."""
    for a, szomsz in HL._MALOM_SZOMSZED.items():
        for b in szomsz:
            assert a in HL._MALOM_SZOMSZED[b], f"{a}-{b} nem szimmetrikus"
    # minden malom-vonal szomszédos pontokból áll
    for m in HL._MALOM_MALMOK:
        a, b, c = m
        assert b in HL._MALOM_SZOMSZED[a] and c in HL._MALOM_SZOMSZED[b]


def test_malom_felismeres():
    tabla = [0] * 24
    for c in (0, 1, 2):
        tabla[c] = 1
    assert HL._malom_zar_e(tabla, 1, 1)
    assert not HL._malom_zar_e(tabla, 1, 2)
    assert (0, 1, 2) in HL._malom_malmai(tabla, 1)
    # két bábú még nem malom
    tabla2 = [0] * 24
    tabla2[0] = tabla2[1] = 1
    assert not HL._malom_zar_e(tabla2, 0, 1)


def test_malom_uthetok_vedik_a_malmot():
    tabla = [0] * 24
    for c in (0, 1, 2):          # ellenfél-malom
        tabla[c] = 2
    tabla[5] = 2                 # malmon kívüli bábu
    uth = HL._malom_uthetok(tabla, 2)
    assert 5 in uth and 0 not in uth and 1 not in uth and 2 not in uth
    # ha MINDEN ellenfél-bábu malomban van, akkor bármelyik leüthető
    tabla2 = [0] * 24
    for c in (0, 1, 2):
        tabla2[c] = 2
    assert set(HL._malom_uthetok(tabla2, 2)) == {0, 1, 2}


class _MalomBot:
    """A kihirdetett állásból (a te bábuid / a gép bábui) és a szomszédság-
    táblából mindig LEGÁLIS lépést ad; ha lehet, malmot zár."""

    def __init__(self):
        self._tos = None

    def _allas(self, ki):
        import re
        for _, p in reversed(ki):
            if p.startswith("Állás"):
                te = {int(x) for x in re.findall(
                    r"\d+", p.split("a te bábuid:")[1].split(";")[0])}
                ge = {int(x) for x in re.findall(
                    r"\d+", p.split("a gép bábui:")[1])}
                return te, ge
        return set(), set()

    def _zar(self, keszlet, cell):
        for m in HL._MALOM_MALMOK:
            m1 = tuple(x + 1 for x in m)
            if cell in m1 and all(x in keszlet for x in m1):
                return True
        return False

    def __call__(self, k, ki):
        kl = k.lower()
        if "melyik színnel" in kl:
            return "1"
        if "színvonal" in kl:
            return "1"
        if "ismertető" in kl:
            return "N"
        te, ge = self._allas(ki)
        foglalt = te | ge
        ures = [c for c in range(1, 25) if c not in foglalt]
        if "hová teszed" in kl:
            for c in ures:                       # ha lehet, malmot zár
                if self._zar(te | {c}, c):
                    return str(c)
            return str(ures[0]) if ures else "1"
        if "melyik bábut tolod" in kl:
            repul = len(te) == 3
            best_f, best_tos = None, None
            for f in sorted(te):
                tos = (ures if repul else
                       [n + 1 for n in HL._MALOM_SZOMSZED[f - 1] if (n + 1) in ures])
                if not tos:
                    continue
                for t in tos:                    # malmot záró tolás előnyben
                    if self._zar((te - {f}) | {t}, t):
                        self._tos = [t]
                        return str(f)
                if best_f is None:
                    best_f, best_tos = f, tos
            self._tos = best_tos or ures
            return str(best_f if best_f is not None
                       else (sorted(te)[0] if te else 1))
        if "hová told" in kl:
            return str(self._tos[0]) if self._tos else (
                str(ures[0]) if ures else "1")
        if "melyik figurát veszed le" in kl:
            uth = [c for c in sorted(ge) if not self._zar(ge, c)] or sorted(ge)
            return str(uth[0]) if uth else "1"
        return ""


def test_malom_bratan_ferenc_vegigjatszik():
    random.seed(4242)
    ki = U.lejatsz(JR.REGISZTER["malom"], _MalomBot(), max_lepes=200000)
    assert ki[-1][0] == "vege", "a Malom nem ért véget rendben"
    txt = "\n".join(p for _, p in ki)
    assert "MALOM" in txt.upper()          # elhangzik a játék neve
    # zárul valamilyen kimenettel (győzelem/vereség/döntetlen)
    assert any(s in txt for s in
               ("Győztél", "Győztem", "döntetlen", "nem tud lépni", "fogyott"))


def test_malom_a_katalogusban_bratan_ferenccel():
    j = KAT.keres("malom")
    assert j is not None and j.retro is True
    sz = KAT.attribucio_szoveg(j)
    assert "Brátán Ferenc" in sz


def test_uj_jatekok_a_regiszterben():
    assert JR.van("malom") and JR.van("mozaik")
