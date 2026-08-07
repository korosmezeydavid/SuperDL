# -*- coding: utf-8 -*-
"""Táblás társasjátékok a gép ellen.

Ki nevet a végén (Kisvarga Zsolt nyomán): mindkét félnek négy bábuja van,
kockával lépkedtek körbe a pályán, majd haza a bázisra. Egyessel vagy
hatossal léphetsz ki a bázisról; hatosnál újra dobsz. Ha egy ellenfél
bábujára lépsz, azt leütöd, és visszakerül a bázisára. Aki mind a négy
bábuját hazajuttatja, nyer.

A vak-barát változatban a pálya mezői és a bábuk számozottak, a gép minden
lépését felolvassa, az állásod bármikor lekérheted. A gépi kódot nem
másoltuk; a viselkedést a portolási sablon szellemében írtuk újra.
"""
import random

from ._util import igen, szam


_PALYA = 40            # a közös körpálya hossza
_HAZA = 44             # ennyi lépés után otthon van a bábu (41-44 a célház)
_START = {"J": 0, "G": 20}     # a játékos és a gép belépő mezője a pályán


def _kinevet_uj():
    # minden bábu: None = bázison, egyébként lépésszám (1.._HAZA-1), >=_HAZA = otthon
    return {"J": [None, None, None, None], "G": [None, None, None, None]}


def _abs_mezo(oldal, lepes):
    """A pálya abszolút mezője (0.._PALYA-1), ha a bábu a közös pályán van
    (1.._PALYA), különben None (bázis vagy célház)."""
    if lepes is None or lepes < 1 or lepes > _PALYA:
        return None
    return (_START[oldal] + lepes - 1) % _PALYA


def _kesz(babu):
    return babu is not None and babu >= _HAZA


def _lephet(g, oldal, i, dobas):
    """Visszaadja a bábu új lépésszámát, ha léphet vele; különben None."""
    babuk = g[oldal]
    b = babuk[i]
    if _kesz(b):
        return None
    if b is None:                      # bázison
        if dobas in (1, 6):
            cel = 1
        else:
            return None
    else:
        cel = b + dobas
        if cel > _HAZA:                # nem lépheti túl pontosan a célházat
            return None
    # saját bábu nem állhat ugyanott (pályán vagy célházban)
    for j, mas in enumerate(babuk):
        if j != i and mas is not None and not _kesz(mas) and mas == cel:
            return None
    return cel


def _legal(g, oldal, dobas):
    return [i for i in range(4) if _lephet(g, oldal, i, dobas) is not None]


def _lep(g, oldal, i, dobas):
    """Lépteti a bábut; visszaad egy leírást és hogy volt-e ütés."""
    cel = _lephet(g, oldal, i, dobas)
    g[oldal][i] = cel
    utes = None
    absm = _abs_mezo(oldal, cel)
    if absm is not None:
        ellen = "G" if oldal == "J" else "J"
        for j, mas in enumerate(g[ellen]):
            if _abs_mezo(ellen, mas) == absm:
                g[ellen][j] = None
                utes = j + 1
    return cel, utes


def _nyert(g, oldal):
    return all(_kesz(b) for b in g[oldal])


def _allas_szoveg(g, oldal):
    nevek = {"J": "A te bábuid", "G": "A gép bábui"}
    reszek = []
    for i, b in enumerate(g[oldal], 1):
        if b is None:
            hol = "bázison"
        elif _kesz(b):
            hol = "otthon"
        elif b > _PALYA:
            hol = f"a célházban ({b - _PALYA}.)"
        else:
            hol = f"a(z) {b}. mezőn"
        reszek.append(f"{i}. bábu: {hol}")
    return nevek[oldal] + ": " + ", ".join(reszek) + "."


def _gep_valaszt(g, dobas, legal):
    """Egyszerű gép-heurisztika: előbb ütés, majd kilépés, majd a "
    leghátrébb lévő bábu léptetése (hogy ne maradjon le)."""
    # ütés?
    legjobb_utes, legjobb_i = -1, None
    for i in legal:
        cel = _lephet(g, "G", i, dobas)
        absm = _abs_mezo("G", cel)
        if absm is None:
            continue
        for mas in g["J"]:
            if _abs_mezo("J", mas) == absm:
                if cel > legjobb_utes:
                    legjobb_utes, legjobb_i = cel, i
    if legjobb_i is not None:
        return legjobb_i
    # kilépés a bázisról?
    for i in legal:
        if g["G"][i] is None:
            return i
    # egyébként a leghátrébb (legkisebb lépésszámú) bábu
    return min(legal, key=lambda i: g["G"][i])


def jatek_kinevet(ctx):
    yield ctx.mond(
        "Ki nevet a végén – a gép ellen. Négy-négy bábutok van, a cél mind a "
        "négyet körbevinni a pályán és hazajuttatni a bázisra. Egyessel vagy "
        "hatossal léphetsz ki a bázisról, hatosnál újra dobsz. Ha egy gépbábura "
        "lépsz, leütöd, és az visszamegy a bázisára. A pálya negyven mezős. Az "
        "állásod bármikor lekérheted: írd be, hogy állás.")
    while True:
        g = _kinevet_uj()
        soros = "J" if random.random() < 0.5 else "G"
        yield ctx.mond("Te kezdesz." if soros == "J" else "A gép kezd.")
        biztonsag = 0
        while True:
            biztonsag += 1
            if biztonsag > 20000:
                yield ctx.mond("A játszma nagyon elhúzódott – döntetlennek "
                               "veszem.")
                break
            if _nyert(g, "J"):
                yield ctx.mond("Mind a négy bábud hazaért – NYERTÉL! "
                               "Gratulálok!")
                break
            if _nyert(g, "G"):
                yield ctx.mond("A gép mind a négy bábuját hazajuttatta – én "
                               "nyertem. Legközelebb több szerencsét!")
                break
            if soros == "J":
                dobas = random.randint(1, 6)
                yield ctx.mond(f"Dobtál: {dobas}.")
                legal = _legal(g, "J", dobas)
                if not legal:
                    yield ctx.mond("Ezzel a dobással nem tudsz lépni.")
                    if dobas != 6:
                        soros = "G"
                    continue
                if len(legal) == 1:
                    valasztott = legal[0]
                    yield ctx.mond(f"Csak a(z) {valasztott + 1}. bábuddal "
                                   "léphetsz.")
                else:
                    valasztott = None
                    while valasztott is None:
                        felsorol = ", ".join(str(i + 1) for i in legal)
                        v = yield ctx.kerdez(f"Melyik bábuddal lépsz? "
                                             f"({felsorol}, vagy: állás)")
                        t = (v or "").strip().lower()
                        if t.startswith("áll") or t.startswith("all"):
                            yield ctx.mond(_allas_szoveg(g, "J"))
                            yield ctx.mond(_allas_szoveg(g, "G"))
                            continue
                        n = szam(t, 1, 4)
                        if n is None or (n - 1) not in legal:
                            yield ctx.mond("Ezzel a bábuval nem léphetsz.")
                            continue
                        valasztott = n - 1
                cel, utes = _lep(g, "J", valasztott, dobas)
                uz = f"A(z) {valasztott + 1}. bábud lépett."
                if utes:
                    uz += f" Leütötted a gép {utes}. bábuját!"
                if _kesz(g["J"][valasztott]):
                    uz += " Ez a bábu hazaért!"
                yield ctx.mond(uz)
                if dobas != 6:
                    soros = "G"
            else:
                dobas = random.randint(1, 6)
                legal = _legal(g, "G", dobas)
                if not legal:
                    yield ctx.mond(f"A gép {dobas}-t dobott, de nem tud lépni.")
                    if dobas != 6:
                        soros = "J"
                    continue
                i = _gep_valaszt(g, dobas, legal)
                cel, utes = _lep(g, "G", i, dobas)
                uz = f"A gép {dobas}-t dobott, és a(z) {i + 1}. bábujával lép."
                if utes:
                    uz += f" Leütötte a(z) {utes}. bábudat!"
                if _kesz(g["G"][i]):
                    uz += " Ez a gépbábu hazaért!"
                yield ctx.mond(uz)
                if dobas != 6:
                    soros = "J"
        v = yield ctx.kerdez("Játsszunk még egyet? (igen/nem)")
        if not igen(v, False):
            break
    yield ctx.vege("Köszönöm a játékot!")
