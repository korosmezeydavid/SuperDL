# -*- coding: utf-8 -*-
"""Az országút harcosa (teljes kalandkönyv) gráf-integritása és lefutása.

Ellenőrzi, hogy a csomópont-gráf lezárt (nincs lógó cél), a győzelem
elérhető, és tetszőleges döntéssor rendben véget ér – így egy jövőbeni
szerkesztés nem tör el észrevétlenül egy útvonalat.
"""
import importlib
from collections import deque

import pytest

BASE = "modules_src.jatekok.jatekok_mod.jatekok"
H = pytest.importorskip(BASE + ".harcos_kaland")

# a ("call") műveletek dinamikus céljai (kockás mini-játékok / párbaj)
_CALL = {"race": [(3, 1100), (0, 2700)], "duel4560": [(2, 400)]}


def _targets(ops):
    outs = []
    for op in ops:
        if isinstance(op, str):
            continue
        f = op[0]
        if f == "g":
            outs.append((op[1], op[2]))
        elif f in ("luck", "skill_gt"):
            outs += [op[1], op[2]]
        elif f == "armor":
            outs.append(op[1])
        elif f in ("chance", "chance_gt"):
            outs += [op[3], op[4]]
        elif f == "af":
            outs += [op[4], op[5]]
        elif f == "if":
            outs += _targets(op[4])
        elif f == "ask":
            outs += [cel for _, cel, _ in op[2]]
        elif f == "cmbV":
            outs.append(op[8])
            if op[9][0] != "end":
                outs.append(op[9])
        elif f == "cmbP":
            outs.append(op[7])
            if op[8][0] != "end":
                outs.append(op[8])
        elif f == "call":
            outs += _CALL.get(op[1], [])
    return [t for t in outs if isinstance(t, tuple) and len(t) == 2
            and isinstance(t[0], int)]


def test_graf_lezart_nincs_logo_cel():
    N = H.N
    hianyzo = set()
    for key, ops in N.items():
        for t in _targets(ops):
            if t not in N:
                hianyzo.add(t)
    assert not hianyzo, f"Lógó célok: {sorted(hianyzo)}"


def test_gyozelem_elerheto():
    N = H.N
    start, win = (0, 50), (3, 4000)
    seen = {start}
    q = deque([start])
    while q:
        for t in _targets(N.get(q.popleft(), [])):
            if t not in seen:
                seen.add(t)
                q.append(t)
    assert win in seen, "A győzelem (Új Reménybe visszatérés) nem érhető el!"
    # a győztes csomópont valóban a küldetés teljesítésével zár
    veg = " ".join(o for o in N[win] if isinstance(o, str)) + \
        " ".join(o[1] for o in N[win] if isinstance(o, tuple) and o[0] == "end")
    assert "Teljesítetted a küldetést" in veg


class _Bot:
    """Végigjátszik egy adott konstans döntéssel, majd nemet mond az újrára."""
    def __init__(self, valasz):
        self.valasz = valasz

    def __call__(self, kerdes):
        if "újrajátszod" in kerdes.lower():
            return "nem"
        return self.valasz


def _vegigjatszik(valasz):
    class Ctx:
        def __init__(s):
            s.utolso = ""

        def mond(s, x):
            s.utolso = x
            return ("m", x)

        def kerdez(s, x):
            return ("k", x)

        def vege(s, x=""):
            s.utolso = x
            return ("v", x)
    ctx = Ctx()
    bot = _Bot(valasz)
    gen = H.jatek_harcos(ctx)
    val = gen.send(None)
    lepes = 0
    while True:
        lepes += 1
        assert lepes < 20000, "A kaland nem ért véget (végtelen ciklus?)"
        if val[0] == "k":
            try:
                val = gen.send(bot(val[1]))
            except StopIteration:
                return ctx.utolso
        else:
            try:
                val = gen.send(None)
            except StopIteration:
                return ctx.utolso


@pytest.mark.parametrize("valasz", ["1", "2", "3"])
def test_barmilyen_dontessor_rendben_veget_er(valasz):
    veg = _vegigjatszik(valasz)
    assert "Köszönöm a játékot" in veg


def test_bevezeto_felturteti_a_szerzoket():
    class Ctx:
        def mond(s, x):
            return ("m", x)

        def kerdez(s, x):
            return ("k", x)

        def vege(s, x=""):
            return ("v", x)
    gen = H.jatek_harcos(Ctx())
    elso = gen.send(None)[1]
    assert "Ian Livingstone" in elso
    assert "Földi János" in elso
