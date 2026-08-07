# -*- coding: utf-8 -*-
"""Mancala-család: Maya (MAJA) és Awari.

Két klasszikus, körökre osztott gödörjáték a gép ellen, teljesen
akadálymentesen: a gép minden lépését felolvassa, az állás bármikor
lekérdezhető, képernyő nem kell hozzá.

- Maya: Márkus Norbert homelabos programja nyomán. A szerző eleve
  képernyő nélküli használatra tervezte (a gép mindig közli a lépéseit) –
  vak-first klasszikus. Hat-hat tál hat-hat golyóval, gyűjtőbe vetve; ütés
  nincs, a cél több golyót gyűjteni. A tál számának megfelelő vetéssel a
  gyűjtőbe érve újra te jössz.
- Awari (Oware): a hagyományos ütős mancala. Két sor hat gödör, mindkét
  végén raktár; a saját üres gödrödbe érő utolsó maggal leütöd a szemközti
  gödröt. Aki több magot gyűjt, nyer.

A gépi kódot NEM másoltuk; a szabályok és a viselkedés újraírt változata a
portolási sablon szellemében készült.
"""
import random

from ._util import igen, szam


# ======================================================================
#  MAYA  (MAJA) – Márkus Norbert
# ======================================================================
# Az egyszerűsített, ütés nélküli maya-vetés egy 13 cellás körpályán megy:
#   [saját 6 tál (6→1), saját gyűjtő, ellenfél 6 tál (6→1)]  – az ellenfél
#   gyűjtőjét kihagyva. A tál számának megfelelő maggal épp a gyűjtőbe érve
#   újra a soros játékos jön.

def _maja_uj():
    return {"A": [0, 6, 6, 6, 6, 6, 6], "B": [0, 6, 6, 6, 6, 6, 6],
            "SA": 0, "SB": 0}


def _maja_cellak(oldal):
    if oldal == "A":
        return [("A", 6), ("A", 5), ("A", 4), ("A", 3), ("A", 2), ("A", 1),
                ("S", "A"), ("B", 6), ("B", 5), ("B", 4), ("B", 3), ("B", 2),
                ("B", 1)]
    return [("B", 6), ("B", 5), ("B", 4), ("B", 3), ("B", 2), ("B", 1),
            ("S", "B"), ("A", 6), ("A", 5), ("A", 4), ("A", 3), ("A", 2),
            ("A", 1)]


def _maja_inc(g, cella):
    if cella[0] == "S":
        g["S" + cella[1]] += 1
    else:
        g[cella[0]][cella[1]] += 1


def _maja_vet(g, oldal, n):
    """Elveti az oldal n. taljanak golyoit. True, ha a gyujtoben ert veget
    (ujra a soros jatekos jon)."""
    cellak = _maja_cellak(oldal)
    sajat_gyujto = ("S", oldal)
    start = 7 - n            # a tal utani cella indexe
    x = g[oldal][n]
    g[oldal][n] = 0
    utolso = None
    for k in range(x):
        cella = cellak[(start + k) % 13]
        _maja_inc(g, cella)
        utolso = cella
    return utolso == sajat_gyujto


def _maja_ures(g, oldal):
    return sum(g[oldal][1:7]) == 0


def _maja_gep_valaszt(g):
    b = g["B"]
    for r in range(1, 7):          # lands exactly in store -> extra turn
        if b[r] == r:
            return r
    for r in range(1, 7):          # goes past the store
        if b[r] > r:
            return r
    tele = [r for r in range(1, 7) if b[r] > 0]
    return random.choice(tele) if tele else 0


def _maja_allas(g):
    a = " ".join(str(g["A"][r]) for r in range(1, 7))
    b = " ".join(str(g["B"][r]) for r in range(1, 7))
    return (f"A tálaid (1-6): {a}. Gyűjtőd: {g['SA']}. "
            f"A gép táljai (1-6): {b}. A gép gyűjtője: {g['SB']}.")


def _maja_vege(ctx, g, ki_ures):
    # a lépni nem tudó (üres) fél begyűjti az ellenfél maradékát a saját
    # gyűjtőjébe (az eredeti szabály szerint)
    if ki_ures == "A":
        g["SA"] += sum(g["B"][1:7])
        for r in range(1, 7):
            g["B"][r] = 0
        elozo = "Elfogytak a golyóid, tehát a játéknak vége."
    else:
        g["SB"] += sum(g["A"][1:7])
        for r in range(1, 7):
            g["A"][r] = 0
        elozo = "A gép golyói elfogytak, a játéknak vége."
    yield ctx.mond(elozo)
    yield ctx.mond(f"Neked {g['SA']} golyód van, a gépnek pedig {g['SB']}.")
    if g["SA"] > g["SB"]:
        yield ctx.mond("Nyertél! Gratulálok.")
    elif g["SB"] > g["SA"]:
        yield ctx.mond("Én nyertem. Legközelebb több szerencsét!")
    else:
        yield ctx.mond("Döntetlen.")


def jatek_maja(ctx):
    yield ctx.mond(
        "Maya játék. A hagyományos golyós mayát játsszuk a gép ellen. "
        "Neked is, a gépnek is hat tálad van, mindegyikben hat golyóval, és "
        "egy gyűjtőd. Kiválasztod az egyik tálad számát (1-től 6-ig, az 1-es "
        "van a gyűjtődhöz legközelebb), a benne lévő golyókat pedig sorban "
        "elosztjuk a gyűjtőd, majd a gép táljai felé. Ha az utolsó golyó épp "
        "a gyűjtődbe kerül, újra te jössz. Nincs ütés: az nyer, aki több "
        "golyót gyűjt. Az állásod bármikor lekérheted, ha beírod: állás.")
    while True:
        g = _maja_uj()
        soros = "A" if random.random() < 0.5 else "B"
        yield ctx.mond("Te kezdesz." if soros == "A" else "Én kezdek.")
        while True:
            if _maja_ures(g, soros):
                yield from _maja_vege(ctx, g, soros)
                break
            if soros == "A":
                yield ctx.mond(_maja_allas(g))
                v = yield ctx.kerdez("Melyik tálad? (1-6, vagy: állás)")
                t = (v or "").strip().lower()
                if t.startswith("áll") or t.startswith("all"):
                    yield ctx.mond(_maja_allas(g))
                    continue
                n = szam(t, 1, 6)
                if n is None:
                    yield ctx.mond("1 és 6 közötti tálszámot kérek.")
                    continue
                if g["A"][n] == 0:
                    yield ctx.mond("Ebben a tálban nincs semmi!")
                    continue
                ujra = _maja_vet(g, "A", n)
                yield ctx.mond(f"A {n}. táladat elvetetted. " + _maja_allas(g))
                if ujra:
                    yield ctx.mond("Az utolsó golyó a gyűjtődbe került – újra "
                                   "te jössz!")
                else:
                    soros = "B"
            else:
                n = _maja_gep_valaszt(g)
                if n == 0:
                    yield from _maja_vege(ctx, g, "B")
                    break
                ujra = _maja_vet(g, "B", n)
                yield ctx.mond(f"Én a {n}. tálamat vetem el. " + _maja_allas(g))
                if ujra:
                    yield ctx.mond("Az utolsó golyóm a gyűjtőmbe került – újra "
                                   "én jövök!")
                else:
                    soros = "A"
        v = yield ctx.kerdez("Játsszunk még egyet? (igen/nem)")
        if not igen(v, False):
            break
    yield ctx.vege("Köszönöm a játékot!")


# ======================================================================
#  AWARI  (Oware) – ütős mancala
# ======================================================================
# Tábla: B[0..13]. Játékos gödrei 0-5, raktára 6. Gép gödrei 7-12, raktára 13.
# Vetés az óramutatóval szemben, mind a 14 cellába. Ha az utolsó mag a saját
# üres gödrödbe kerül és a szemközti gödör nem üres, leütöd (a szemközti +1
# mag a raktáradba). Cél a többség (a 36 magból 19).

_JATEKOS_RAKTAR = 6
_GEP_RAKTAR = 13


def _awari_uj(mod):
    b = [0] * 14
    if mod == 2:                       # véletlen kiosztás
        for i in list(range(0, 6)) + list(range(7, 13)):
            b[i] = random.randint(2, 5)
    else:                              # standard: minden gödör 3
        for i in list(range(0, 6)) + list(range(7, 13)):
            b[i] = 3
    return b


def _awari_lep(b, m, raktar):
    """Elveti a b[m] gödröt, üt, ha lehet. Módosítja b-t; visszaadja az
    utolsó cella indexét."""
    p = b[m]
    b[m] = 0
    while p > 0:
        m = (m + 1) % 14
        b[m] += 1
        p -= 1
    # ütés: üres (most 1) saját oldali gödörbe érve a szemközti leütése
    if m not in (_JATEKOS_RAKTAR, _GEP_RAKTAR) and b[m] == 1:
        szemben = 12 - m
        if 0 <= szemben <= 12 and szemben not in (_JATEKOS_RAKTAR,) and \
                b[szemben] != 0:
            b[raktar] += b[szemben] + 1
            b[m] = 0
            b[szemben] = 0
    return m


def _awari_gep_godrok(b):
    return [i for i in range(7, 13) if b[i] > 0]


def _awari_jatekos_godrok(b):
    return [i for i in range(0, 6) if b[i] > 0]


def _awari_gep_valaszt(b):
    """1 lépés előretekintés: a gép azt a lépést választja, amely után a
    legtöbb magja van a raktárában, kivédve az azonnali nagy visszaütést."""
    legjobb, legjobb_ert = None, -999
    for m in _awari_gep_godrok(b):
        pr = b[:]
        _awari_lep(pr, m, _GEP_RAKTAR)
        nyeres = pr[_GEP_RAKTAR] - b[_GEP_RAKTAR]
        # az ellenfél legjobb visszaütése
        ellen = 0
        for jm in _awari_jatekos_godrok(pr):
            pr2 = pr[:]
            _awari_lep(pr2, jm, _JATEKOS_RAKTAR)
            ellen = max(ellen, pr2[_JATEKOS_RAKTAR] - pr[_JATEKOS_RAKTAR])
        ert = nyeres * 2 - ellen + random.random()
        if ert > legjobb_ert:
            legjobb_ert, legjobb = ert, m
    return legjobb


def _awari_allas(b):
    j = " ".join(str(b[i]) for i in range(0, 6))
    g = " ".join(str(b[i]) for i in range(12, 6, -1))
    return (f"A gödreid (1-6): {j}. A raktárad: {b[_JATEKOS_RAKTAR]}. "
            f"A gép gödrei (1-6): {g}. A gép raktára: {b[_GEP_RAKTAR]}.")


def _awari_vege(ctx, b):
    # a maradékot mindenki a saját raktárába söpri
    for i in range(0, 6):
        b[_JATEKOS_RAKTAR] += b[i]
        b[i] = 0
    for i in range(7, 13):
        b[_GEP_RAKTAR] += b[i]
        b[i] = 0
    yield ctx.mond("Vége a játéknak.")
    yield ctx.mond(f"A te pontjaid: {b[_JATEKOS_RAKTAR]}. "
                   f"A gép pontjai: {b[_GEP_RAKTAR]}.")
    if b[_JATEKOS_RAKTAR] > b[_GEP_RAKTAR]:
        yield ctx.mond("Ön nyert! Gratulálok.")
    elif b[_GEP_RAKTAR] > b[_JATEKOS_RAKTAR]:
        d = b[_GEP_RAKTAR] - b[_JATEKOS_RAKTAR]
        yield ctx.mond(f"Én nyertem, {d} ponttal.")
    else:
        yield ctx.mond("Döntetlen.")


def jatek_awari(ctx):
    yield ctx.mond(
        "Awari. A hagyományos ütős mancala a gép ellen. Két sor hat gödör, "
        "mindkét oldalon egy raktárral. Kiválasztod az egyik gödröd számát "
        "(1-től 6-ig), a benne lévő magokat pedig sorban továbbrakjuk a "
        "következő gödrökbe, óramutatóval szemben. Ha az utolsó mag a saját "
        "üres gödrödbe kerül és a vele szemközti gépgödörben van mag, leütöd: "
        "azok a magok a raktáradba kerülnek. Az nyer, aki több magot gyűjt "
        "(a 36 magból a többség 19). Az állásod a: állás szóval kérheted.")
    v = yield ctx.kerdez("Milyen legyen az indulás? 1: standard (minden "
                         "gödör 3 mag), 2: véletlen kiosztás")
    mod = szam(v, 1, 2) or 1
    while True:
        b = _awari_uj(mod)
        while True:
            if b[_JATEKOS_RAKTAR] >= 19 or b[_GEP_RAKTAR] >= 19 or \
                    not _awari_jatekos_godrok(b) or not _awari_gep_godrok(b):
                yield from _awari_vege(ctx, b)
                break
            # a játékos lép
            yield ctx.mond(_awari_allas(b))
            v = yield ctx.kerdez("Mit lépsz? (1-6, vagy: állás)")
            t = (v or "").strip().lower()
            if t.startswith("áll") or t.startswith("all"):
                continue
            n = szam(t, 1, 6)
            if n is None or b[n - 1] == 0:
                yield ctx.mond("Illegális lépés!")
                continue
            _awari_lep(b, n - 1, _JATEKOS_RAKTAR)
            yield ctx.mond("Léptél. " + _awari_allas(b))
            if b[_JATEKOS_RAKTAR] >= 19 or not _awari_gep_godrok(b):
                yield from _awari_vege(ctx, b)
                break
            # a gép lép
            gm = _awari_gep_valaszt(b)
            if gm is None:
                yield from _awari_vege(ctx, b)
                break
            _awari_lep(b, gm, _GEP_RAKTAR)
            yield ctx.mond(f"Az én lépésem: a {gm - 6}. gödröm. "
                           + _awari_allas(b))
        v = yield ctx.kerdez("Ismét? (igen/nem)")
        if not igen(v, False):
            break
    yield ctx.vege("Köszönöm a játékot!")
