# -*- coding: utf-8 -*-
"""Figyelem- és koncentrációjátékok.

Varázsgömb (Schuck Antal, 1988): tíz szót „helyezel a varázsgömbbe", a gömb
véletlen sorrendben felvillantja őket, neked pedig arra kell figyelned,
melyik szó hányszor bukkan elő. A forgás után a gép mindegyik szóról
megkérdezi, hányszor mondta. Tisztán fül után játszható.

A gépi kódot nem másoltuk; a viselkedést a portolási sablon szellemében
írtuk újra, tiszta, felolvasható magyar szöveggel.
"""
import random

from ._util import igen, szam


_MIN_VILLANAS = 10
_MAX_VILLANAS = 40


def jatek_varazsgomb(ctx):
    yield ctx.mond(
        "Varázsgömb – memóriajáték. Itt van előtted egy varázsgömb: tíz "
        "különböző szót kell belehelyezned. Aztán te határozod meg, hányszor "
        "forduljon a gömb. Forgás közben a belehelyezett szavak közül egyszerre "
        "egy előbukkan – arra kell nagyon figyelned, melyik szó hányszor fordul "
        "elő. A végén mindegyik szóról megkérdezem, hányszor mondtam. Kellemes "
        "koncentrálást kívánok!")
    while True:
        szavak = []
        yield ctx.mond("Helyezd el a szavakat! Tíz különböző szót kérek, "
                       "egyesével.")
        while len(szavak) < 10:
            v = yield ctx.kerdez(f"{len(szavak) + 1}. szó:")
            sz = (v or "").strip()
            if not sz:
                yield ctx.mond("Üres szót nem fogadok el – találj ki egy szót!")
                continue
            if sz.lower() in (x.lower() for x in szavak):
                yield ctx.mond("Ezt a szót már belehelyezted – találj ki egy "
                               "újat!")
                continue
            szavak.append(sz)
        yield ctx.mond("Hányszor forduljon a varázsgömb? (Fül után "
                       f"{_MIN_VILLANAS} és {_MAX_VILLANAS} között ajánlott.)")
        while True:
            v = yield ctx.kerdez("A fordulatszám:")
            b = szam(v, _MIN_VILLANAS, _MAX_VILLANAS)
            if b is None:
                yield ctx.mond(f"{_MIN_VILLANAS} és {_MAX_VILLANAS} közötti "
                               "számot kérek.")
                continue
            break
        v = yield ctx.kerdez("Felkészültél már a játékra? (igen/nem)")
        if not igen(v, True):
            yield ctx.mond("Rendben, akkor most jól figyelj – forog a "
                           "varázsgömb!")
        else:
            yield ctx.mond("Jól figyelj – forog a varázsgömb!")
        # forgás: minden villanásnál egy véletlen szó, a gyakoriságot számoljuk
        db = [0] * 10
        for _ in range(b):
            i = random.randrange(10)
            db[i] += 1
            yield ctx.mond(szavak[i])
        yield ctx.mond("Gondold át még egyszer! Ha kellőképpen figyeltél, "
                       "akkor könnyen felelhetsz.")
        talalat = 0
        for i, sz in enumerate(szavak):
            while True:
                v = yield ctx.kerdez(f"Hányszor mondtam azt, hogy {sz}?")
                tipp = szam(v, 0, b)
                if tipp is None:
                    yield ctx.mond("Egy számot kérek (0 vagy több).")
                    continue
                break
            if tipp == db[i]:
                talalat += 1
                yield ctx.mond("Jó tipp!")
            else:
                yield ctx.mond(f"Rossz tipp! A helyes szám: {db[i]}.")
        rossz = 10 - talalat
        yield ctx.mond("Kiértékelés.")
        yield ctx.mond(f"{talalat} jó tipped volt.")
        if rossz:
            yield ctx.mond(f"{rossz} alkalommal rosszul tippeltél.")
        if talalat == 10:
            yield ctx.mond("Kiváló eredmény! Tíz jutalompont illet meg. "
                           "Gratulálok!")
        elif talalat >= 7:
            yield ctx.mond("Jó eredmény! Öt jutalompont illet meg. Dicséretet "
                           "érdemelsz.")
        elif talalat >= 4:
            yield ctx.mond("Közepes eredmény. Kis gyakorlással viheted "
                           "valamire!")
        else:
            yield ctx.mond("Gyenge eredmény. Kis gyakorlással viheted "
                           "valamire!")
        v = yield ctx.kerdez("Játszunk még egyet? (igen/nem)")
        if not igen(v, False):
            break
    yield ctx.vege("A viszontlátásra!")
