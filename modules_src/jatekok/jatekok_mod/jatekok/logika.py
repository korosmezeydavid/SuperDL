# -*- coding: utf-8 -*-
"""Logikai / stratégiai retró játékok: Nim, Mastermind, Torpedó, Teke, Párbaj.

Minden játék generátor-korutin (lásd `_util`). A `yield ctx.kerdez(...)` egy
beírt szöveget ad vissza; a játék azt dolgozza fel.
"""
import random
from collections import Counter

from ._util import igen, szam, valaszt


def _eredmeny(en, gep, mien="Te", ove="A gép"):
    if en > gep:
        return f"{mien} nyert! {en} – {gep}. Gratulálok!"
    if gep > en:
        return f"{ove} nyert. {en} – {gep}. Legközelebb sikerül!"
    return f"Döntetlen: {en} – {gep}."


# ============================================================ NÉGYZET KIRAKÓ
def jatek_nim(ctx):
    yield ctx.mond("NÉGYZET KIRAKÓ. Húsz négyzetet raktok le felváltva, "
                   "körönként egyet, kettőt vagy hármat. Aki az UTOLSÓT, a "
                   "huszadikat rakja le, az VESZÍT.")
    while True:
        maradek = 20
        v = yield ctx.kerdez("Te kezdesz? (igen/nem)")
        te_jossz = igen(v, True)
        while maradek > 0:
            felso = min(3, maradek)
            if te_jossz:
                v = yield ctx.kerdez(
                    f"Még {maradek} négyzet van. Mennyit raksz le? (1-{felso})")
                n = szam(v, 1, felso)
                if n is None:
                    yield ctx.mond(f"Egy és {felso} közötti számot kérek.")
                    continue
                maradek -= n
                yield ctx.mond(f"Leraktál {n}-t. Maradt {maradek}.")
            else:
                n = ((maradek - 1) % 4) or 1     # misère-optimális lépés
                n = min(n, maradek)
                maradek -= n
                yield ctx.mond(f"A gép lerak {n}-t. Maradt {maradek}.")
            if maradek <= 0:
                if te_jossz:
                    yield ctx.mond("Te raktad le az utolsót – sajnos vesztettél.")
                else:
                    yield ctx.mond("A gép rakta le az utolsót – NYERTÉL!")
                break
            te_jossz = not te_jossz
        v = yield ctx.kerdez("Új játék? (igen/nem)")
        if not igen(v, False):
            break
    yield ctx.vege("Köszönöm a játékot!")


# ================================================================ MASTERMIND
_MM_NEV = {"b": "barna", "k": "kék", "p": "piros",
           "z": "zöld", "s": "sárga", "l": "lila"}


def jatek_mastermind(ctx):
    betuk = list(_MM_NEV)
    yield ctx.mond(
        "MASTERMIND. Kitalálandó a gép négy színből álló, sorrendes kódja. "
        "A színek és a betűjük: barna B, kék K, piros P, zöld Z, sárga S, "
        "lila L. Írj négy betűt, például: P K Z B. A fekete pálcika jó szín "
        "jó helyen, a fehér jó szín rossz helyen. Feladás: írj nullát.")
    while True:
        kod = [valaszt(betuk) for _ in range(4)]
        probak = 0
        while True:
            v = yield ctx.kerdez("A tipped (négy szín betűje):")
            t = (v or "").strip().lower().replace(" ", "")
            if t == "0":
                yield ctx.mond("Feladtad. A kód: "
                               + ", ".join(_MM_NEV[c] for c in kod) + ".")
                break
            t = [c for c in t if c in _MM_NEV]
            if len(t) != 4:
                yield ctx.mond("Négy érvényes színbetűt kérek: B, K, P, Z, S, L.")
                continue
            probak += 1
            fekete = sum(1 for a, b in zip(t, kod) if a == b)
            kozos = sum((Counter(kod) & Counter(t)).values())
            feher = kozos - fekete
            if fekete == 4:
                yield ctx.mond(
                    f"Négy fekete – KITALÁLTAD {probak} próbából! Gratulálok!")
                break
            yield ctx.mond(f"{fekete} fekete és {feher} fehér.")
        v = yield ctx.kerdez("Új játék? (igen/nem)")
        if not igen(v, False):
            break
    yield ctx.vege("Köszönöm a játékot!")


# =================================================================== TORPEDÓ
def _koord(v):
    """„C 7" → (oszlop 0-9, sor 0-9). Hibánál None."""
    t = (v or "").strip().lower()
    if not t or t[0] < "a" or t[0] > "j":
        return None
    osz = ord(t[0]) - ord("a")
    szam_resz = "".join(ch for ch in t[1:] if ch.isdigit())
    if not szam_resz:
        return None
    sor = int(szam_resz)
    if sor < 1 or sor > 10:
        return None
    return (osz, sor - 1)


def jatek_torpedo(ctx):
    yield ctx.mond(
        "TORPEDÓ. Tíz és tíz mezős rácson négy X rejtőzik. Az oszlopok A-tól "
        "J-ig, a sorok 1-től 10-ig. Írd be a tipped, például: C 7. Találd "
        "meg mind a négyet!")
    while True:
        cellak = set()
        while len(cellak) < 4:
            cellak.add((random.randint(0, 9), random.randint(0, 9)))
        talalt, tippelt, probak = set(), set(), 0
        while len(talalt) < 4:
            v = yield ctx.kerdez("Tipp (oszlopbetű és sorszám):")
            cella = _koord(v)
            if cella is None:
                yield ctx.mond("Érvényes koordinátát kérek, például: C 7.")
                continue
            if cella in tippelt:
                yield ctx.mond("Ezt már kérdezted.")
                continue
            tippelt.add(cella)
            probak += 1
            if cella in cellak:
                talalt.add(cella)
                if len(talalt) < 4:
                    yield ctx.mond(f"TALÁLAT! Megvan {len(talalt)} a négyből.")
            else:
                yield ctx.mond("Nem talált – itt üres a víz.")
        yield ctx.mond(f"Mind a négy X megvan, {probak} próbából! Ügyes vagy!")
        v = yield ctx.kerdez("Új játék? (igen/nem)")
        if not igen(v, False):
            break
    yield ctx.vege("Köszönöm a játékot!")


# ====================================================================== TEKE
def _teke_gurit():
    p = 3 if random.random() < 0.35 else 0                 # a király
    p += sum(1 for _ in range(8) if random.random() < 0.45)  # a nyolc szolga
    return p


def jatek_teke(ctx):
    v = yield ctx.kerdez("Hány menetes legyen a játék? (például 5)")
    menet = szam(v, 1, 50) or 5
    yield ctx.mond(
        f"TEVE-PARKI TEKEPARTI, {menet} menet. Kilenc bábu áll: középen a "
        "király 3 pontot ér, a nyolc szolga egyet-egyet. Ellenfeled Frédi.")
    en = fredi = 0
    for m in range(1, menet + 1):
        yield ctx.kerdez(f"{m}. menet – nyomj Entert a gurításhoz!")
        p = _teke_gurit()
        en += p
        yield ctx.mond(f"Gurítottál {p} pontnyit. Összesen: {en}.")
        pf = _teke_gurit()
        fredi += pf
        yield ctx.mond(f"Frédi {pf} pontot gurít. Neki összesen: {fredi}.")
    yield ctx.mond(_eredmeny(en, fredi, "Te", "Frédi"))
    yield ctx.vege("Köszönöm a játékot!")


# ===================================================================== PÁRBAJ
def jatek_parbaj(ctx):
    v = yield ctx.kerdez("Hány pontig játsszunk? (egy találat 2 pont; például 6)")
    cel = szam(v, 2, 100) or 6
    yield ctx.mond(
        "PÁRBAJ. Négy pozíció van, egytől négyig. Először elhelyezed a "
        "bábudat, aztán lősz az ellenfélére. Minden találat 2 pont.")
    en = ellen = 0
    while en < cel and ellen < cel:
        v = yield ctx.kerdez("Hová állsz? (1-4)")
        allas = szam(v, 1, 4)
        if allas is None:
            yield ctx.mond("Egy és négy közötti pozíciót kérek.")
            continue
        gep_allas = random.randint(1, 4)
        v = yield ctx.kerdez("Hová lősz? (1-4)")
        loves = szam(v, 1, 4)
        if loves is None:
            yield ctx.mond("Egy és négy közötti pozíciót kérek.")
            continue
        gep_loves = random.randint(1, 4)
        reszek = []
        if loves == gep_allas:
            en += 2
            reszek.append("Telibe találtad!")
        else:
            reszek.append("Mellé lőttél.")
        if gep_loves == allas:
            ellen += 2
            reszek.append("Az ellenfél is eltalált téged.")
        else:
            reszek.append("Az ellenfél melléd lőtt.")
        yield ctx.mond(" ".join(reszek)
                       + f" Állás: te {en} – ellenfél {ellen}.")
    yield ctx.mond(_eredmeny(en, ellen, "Te", "Az ellenfél"))
    yield ctx.vege("Köszönöm a játékot!")
