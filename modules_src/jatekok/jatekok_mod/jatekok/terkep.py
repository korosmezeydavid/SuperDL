# -*- coding: utf-8 -*-
"""Térbeli / labirintus retró játékok: Lóugrás verseny (Horse Step) és
Labirintus. Mindkettő tisztán szövegesen, koordinátákkal és irányokkal
játszható – vakon is jól követhető."""
import random

from ._util import igen, szam

_KNIGHT = ((1, 2), (2, 1), (-1, 2), (-2, 1),
           (1, -2), (2, -1), (-1, -2), (-2, -1))


# ============================================================== LÓUGRÁS VERSENY
def _hs_nev(cell):
    x, y = cell
    return f"{chr(ord('a') + y)}{x + 1}"


def _hs_koord(v, N):
    t = (v or "").strip().lower()
    if not t or not ("a" <= t[0] < chr(ord("a") + N)):
        return None
    y = ord(t[0]) - ord("a")
    num = "".join(c for c in t[1:] if c.isdigit())
    if not num:
        return None
    x = int(num) - 1
    if not (0 <= x < N and 0 <= y < N):
        return None
    return (x, y)


def _hs_lepesek(cell, N):
    x, y = cell
    return [(x + dx, y + dy) for dx, dy in _KNIGHT
            if 0 <= x + dx < N and 0 <= y + dy < N]


def _hs_kereszt(N):
    c = N // 2
    t = {(c, c)}
    if N % 2 == 1:
        t |= {(c - 1, c), (c + 1, c), (c, c - 1), (c, c + 1)}
    return t


def jatek_horstep(ctx):
    v = yield ctx.kerdez("Táblaméret: 1 = hétszer hét, 2 = kilencszer kilenc")
    N = 9 if szam(v, 1, 2) == 2 else 7
    tilt = _hs_kereszt(N)
    jatekos, gep = (0, 0), (N - 1, N - 1)
    cel_j, cel_g = (N - 1, 0), (0, N - 1)
    latogatott = {jatekos, gep}
    yield ctx.mond(
        f"LÓUGRÁS VERSENY, {N}-szer {N}-es táblán. Sakkló-lépésekkel haladsz. "
        "A mezőt a sor betűje és az oszlop száma adja, például b3. Te az "
        f"{_hs_nev(jatekos)} sarokból a(z) {_hs_nev(cel_j)} sarokba tartasz, a "
        "gép a másik átlón. A középső keresztre nem lehet lépni, és minden "
        "mező csak egyszer járható. Aki előbb célba ér, nyer.")
    while True:
        legal = [c for c in _hs_lepesek(jatekos, N)
                 if c not in latogatott and c not in tilt]
        if not legal:
            yield ctx.mond("Nincs szabályos lépésed – beszorultál. A gép nyert.")
            break
        v = yield ctx.kerdez(f"A(z) {_hs_nev(jatekos)} mezőn állsz. Hová "
                             "ugrasz? (például b3)")
        cel = _hs_koord(v, N)
        if cel is None or cel not in legal:
            yield ctx.mond("Az nem szabályos lóugrás oda. Próbáld újra.")
            continue
        jatekos = cel
        latogatott.add(cel)
        yield ctx.mond(f"A(z) {_hs_nev(jatekos)} mezőre ugrottál.")
        if jatekos == cel_j:
            yield ctx.mond("Célba értél – NYERTÉL!")
            break
        glegal = [c for c in _hs_lepesek(gep, N)
                  if c not in latogatott and c not in tilt]
        if not glegal:
            yield ctx.mond("A gép beszorult, nem tud lépni – NYERTÉL!")
            break
        glegal.sort(key=lambda c: abs(c[0] - cel_g[0]) + abs(c[1] - cel_g[1]))
        gep = glegal[0]
        latogatott.add(gep)
        yield ctx.mond(f"A gép a(z) {_hs_nev(gep)} mezőre ugrik.")
        if gep == cel_g:
            yield ctx.mond("A gép ért előbb célba – ezúttal a gép nyert!")
            break
    yield ctx.vege("Köszönöm a játékot!")


# ================================================================== LABIRINTUS
def _maze(w, h):
    nyitott = set()
    latog = {(0, 0)}
    stack = [(0, 0)]
    while stack:
        x, y = stack[-1]
        szomsz = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                  if 0 <= x + dx < w and 0 <= y + dy < h
                  and (x + dx, y + dy) not in latog]
        if not szomsz:
            stack.pop()
            continue
        uj = random.choice(szomsz)
        nyitott.add(frozenset({(x, y), uj}))
        latog.add(uj)
        stack.append(uj)
    return nyitott


_IRANY = {"fel": (0, -1), "f": (0, -1), "le": (0, 1), "l": (0, 1),
          "bal": (-1, 0), "b": (-1, 0), "jobb": (1, 0), "j": (1, 0)}


def jatek_labirint(ctx):
    w = h = 5
    nyitott = _maze(w, h)
    x, y = 0, 0
    cel = (w - 1, h - 1)
    lepes = 0
    yield ctx.mond(
        f"LABIRINTUS, {w}-ször {h} mezős. A bal felső sarokból indulsz, a jobb "
        "alsó sarokba kell eljutnod. Irányok: fel, le, bal, jobb (vagy f, l, "
        "b, j). Ha arra fal van, szólok.")
    while (x, y) != cel:
        v = yield ctx.kerdez(f"Merre lépsz? (fel/le/bal/jobb) – {lepes} lépés")
        t = (v or "").strip().lower()
        if t not in _IRANY:
            yield ctx.mond("Fel, le, bal vagy jobb irányt kérek.")
            continue
        dx, dy = _IRANY[t]
        nx, ny = x + dx, y + dy
        if not (0 <= nx < w and 0 <= ny < h):
            yield ctx.mond("Ott a labirintus széle – arra nem mehetsz.")
            continue
        if frozenset({(x, y), (nx, ny)}) not in nyitott:
            yield ctx.mond("Arra fal van.")
            continue
        x, y = nx, ny
        lepes += 1
        if (x, y) == cel:
            yield ctx.mond(f"Kijutottál a labirintusból, {lepes} lépésből! "
                           "Ügyes vagy!")
            break
        yield ctx.mond("Léptél.")
    yield ctx.vege("Köszönöm a játékot!")
