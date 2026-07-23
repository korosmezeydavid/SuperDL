# -*- coding: utf-8 -*-
"""Kaland / egyéb retró játékok: Csata, Országút harcosa, Allah szakálla,
Zongora, Szindbád.

A Szindbád felnőtt hangvételű (a felület 18+ figyelmeztetéssel indítja), de
tiszta, mindenki számára vállalható szöveggel. Az Allah szakálla az eredeti
témát követi, tényszerű narrációval."""
import random

from ._util import igen, szam, kever


# ====================================================================== CSATA
def jatek_csata(ctx):
    yield ctx.mond(
        "CSATA. Török sereg ostromolja a várat. Te lősz az ostromlókra, ők "
        "visszalőnek. Védd meg a várat! Nyomj Entert a lövéshez.")
    while True:
        var, torok = 10, 10
        while var > 0 and torok > 0:
            yield ctx.kerdez("Tölts és tüzelj – Enter!")
            reszek = []
            if random.random() < 0.6:
                kar = random.randint(1, 3)
                torok -= kar
                reszek.append(f"Találtál! A török sereg {kar} egységet veszít.")
            else:
                reszek.append("A lövésed mellé megy.")
            if torok > 0:
                if random.random() < 0.5:
                    kar = random.randint(1, 3)
                    var -= kar
                    reszek.append(f"Az ágyúik eltalálják a várfalat, {kar} "
                                  "sérülés.")
                else:
                    reszek.append("Az ő lövésük is mellé csap.")
            reszek.append(f"Vár: {max(0, var)}, török sereg: {max(0, torok)}.")
            yield ctx.mond(" ".join(reszek))
        if torok <= 0 and var > 0:
            yield ctx.mond("Megvédted a várat a török sereg elől! Győzelem!")
        elif var <= 0 and torok > 0:
            yield ctx.mond("A törökök áttörtek és elfoglalták a várat. Elestél.")
        else:
            yield ctx.mond("Mindketten kimerültetek – döntetlen, a vár még áll.")
        v = yield ctx.kerdez("Új csata? (igen/nem)")
        if not igen(v, False):
            break
    yield ctx.vege("Köszönöm a játékot!")


# ========================================================== ORSZÁGÚT HARCOSA
_HARCOS = {
    "start": {
        "szoveg": "Új Remény városának tanácsa elé állsz. A világjárvány után "
                  "a civilizáció romokban; a túlélők megerősített kisvárosokban "
                  "élnek. A tanács rád bízza a küldetést: vigyél gabonát és "
                  "vetőmagot San Angelóba, és hozz érte tízezer liter benzint. "
                  "A járműved egy felfegyverzett Dodge Interceptor.",
        "valasztasok": [("1", "Azonnal útnak indulsz", "orszagut"),
                        ("2", "Előbb átvizsgálod a járművet", "atvizsgal")]},
    "atvizsgal": {
        "szoveg": "Alaposan ellenőrzöd a páncélzatot és a géppuskákat. "
                  "Mindent rendben találsz, és tele tankkal vágsz neki.",
        "valasztasok": [("1", "Irány az országút", "orszagut")]},
    "orszagut": {
        "szoveg": "A poros úton egy felborult teherautó torlaszolja el az "
                  "utat. A romok mögött mozgást látsz – lehet csapda is.",
        "valasztasok": [("1", "Áttörsz teljes sebességgel", "attores"),
                        ("2", "Kikerülöd a homokdűnék felé", "dune")]},
    "attores": {
        "szoveg": "A motor felbőg, a páncél állja a lövéseket, és átszakítod a "
                  "torlaszt! A banditák a porban maradnak mögötted.",
        "valasztasok": [("1", "Tovább San Angelo felé", "celba")]},
    "dune": {
        "szoveg": "A dűnék között a homok megfogja a kerekeket, és időt "
                  "veszítesz, de elkerülöd a tűzharcot.",
        "valasztasok": [("1", "Visszakapaszkodsz az útra", "celba")]},
    "celba": {
        "szoveg": "Napnyugtára megérkezel San Angelóba. Leadod a gabonát és a "
                  "vetőmagot, és cserébe megkapod a tízezer liter benzint. Új "
                  "Remény városa átvészeli a telet – a küldetés sikerült. HŐS "
                  "lettél az országúton!",
        "valasztasok": []},
}


def jatek_harcos(ctx):
    yield ctx.mond("ORSZÁGÚT HARCOSA. Választásos kalandkönyv a járvány utáni "
                   "világban. A döntéseidet a felkínált számmal hozod meg.")
    while True:
        node = "start"
        while True:
            n = _HARCOS[node]
            yield ctx.mond(n["szoveg"])
            val = n["valasztasok"]
            if not val:
                break
            keret = "Mit teszel? " + "  ".join(f"{k}: {szo}." for k, szo, _ in val)
            v = yield ctx.kerdez(keret)
            t = (v or "").strip().lower()
            cel = None
            for k, szo, c in val:
                if t == k or (t and t == szo.lower()):
                    cel = c
                    break
            if cel is None:
                yield ctx.mond("Nem értem – az első utat választom helyetted.")
                cel = val[0][2]
            node = cel
        v = yield ctx.kerdez("Újrajátszod a kalandot? (igen/nem)")
        if not igen(v, False):
            break
    yield ctx.vege("Köszönöm a játékot!")


# =============================================================== ALLAH SZAKÁLLA
def jatek_allah(ctx):
    yield ctx.mond(
        "ALLAH SZAKÁLLA. Az „Allah szakálla” nevű terrorszervezet időzített "
        "atombombát rejtett egy százemeletes szálloda egyik szobájába. Minden "
        "emeleten tíz szoba van. Sugárzásmérővel kell megtalálnod a bombát, "
        "mielőtt lejár az idő. Tizenkét próbálkozásod van.")
    while True:
        cel_e, cel_sz = random.randint(1, 100), random.randint(1, 10)
        maxprob, talalt, p = 12, False, 0
        while p < maxprob and not talalt:
            v = yield ctx.kerdez(f"{p + 1}. próbálkozás. Melyik emelet? (1-100)")
            e = szam(v, 1, 100)
            if e is None:
                yield ctx.mond("1 és 100 közötti emeletet kérek.")
                continue
            v = yield ctx.kerdez("Melyik szoba? (1-10)")
            sz = szam(v, 1, 10)
            if sz is None:
                yield ctx.mond("1 és 10 közötti szobát kérek.")
                continue
            p += 1
            if e == cel_e and sz == cel_sz:
                yield ctx.mond(f"Megtaláltad és hatástalanítottad a bombát a "
                               f"{cel_e}. emelet {cel_sz}. szobájában! "
                               "Megmentetted a várost!")
                talalt = True
                break
            tav = abs(e - cel_e) + abs(sz - cel_sz)
            szint = ("Nagyon erős" if tav <= 3 else "Erős" if tav <= 8
                     else "Közepes" if tav <= 20 else "Gyenge")
            yield ctx.mond(f"{szint} sugárzást mér a műszer – minél erősebb, "
                           "annál közelebb vagy.")
        if not talalt:
            yield ctx.mond(f"Lejárt az idő. A bomba a {cel_e}. emelet {cel_sz}. "
                           "szobájában volt. Legközelebb gyorsabban kell "
                           "keresned!")
        v = yield ctx.kerdez("Új játék? (igen/nem)")
        if not igen(v, False):
            break
    yield ctx.vege("Köszönöm a játékot!")


# ==================================================================== ZONGORA
_HANGOK = {"c": 261.63, "cisz": 277.18, "d": 293.66, "disz": 311.13,
           "e": 329.63, "f": 349.23, "fisz": 369.99, "g": 392.00,
           "gisz": 415.30, "a": 440.00, "b": 466.16, "h": 493.88,
           "c2": 523.25}


def jatek_zongora(ctx):
    yield ctx.mond(
        "ZONGORA. Írj be hangokat: c, d, e, f, g, a, h, és c2 a felső cé; a "
        "cisz, disz, fisz, gisz, b a félhangok. Több hangot szóközzel is "
        "megadhatsz, például: c d e f g. A „dallam” szóra lejátszok egy kis "
        "dallamot. Kilépés: írd be, hogy kilép.")
    while True:
        v = yield ctx.kerdez("Milyen hangot játsszak?")
        t = (v or "").strip().lower()
        if not t:
            continue
        if t.startswith("kil"):
            break
        if t == "dallam":
            dallam = ["c", "d", "e", "c", "c", "d", "e", "c",
                      "e", "f", "g", "e", "f", "g"]
            yield ctx.hang([(_HANGOK[h], 320) for h in dallam])
            yield ctx.mond("Ez a Testvér Jakab (Frère Jacques) kezdete volt.")
            continue
        hangok, ismeretlen, jatszott = [], [], []
        for jel in t.replace(",", " ").split():
            if jel in _HANGOK:
                hangok.append((_HANGOK[jel], 380))
                jatszott.append(jel)
            else:
                ismeretlen.append(jel)
        if hangok:
            yield ctx.hang(hangok)
            yield ctx.mond("Játszott hangok: " + ", ".join(jatszott) + ".")
        if ismeretlen:
            yield ctx.mond("Ezeket nem ismerem: " + ", ".join(ismeretlen) + ".")
    yield ctx.vege("Köszönöm, hogy zongoráztál!")


# =================================================================== SZINDBÁD
_HOLGYEK = ["Aisha", "Zulejka", "Fatima", "Golnaz", "Perizad",
            "Sirin", "Nadia", "Jázmin"]


def jatek_szindbad(ctx):
    yield ctx.mond(
        "SZINDBÁD. A török szultán hajóját vad vihar tépázza. Te, Szindbád, a "
        "habok közé veted magad, és megmented a süllyedő hajót. Hálából a "
        "szultán a háreméből enged választanod egy hölgyet – de vigyázz, két "
        "választás tiltott!")
    v = yield ctx.kerdez("Mi a neved, hős?")
    nev = (v or "").strip() or "Szindbád"
    while True:
        kevert = kever(_HOLGYEK)[:7]
        # a „legkarcsúbb" és a „legteltebb" a sorrend két vége – ők tiltottak
        tiltott = {0, len(kevert) - 1}
        rangsor = list(range(len(kevert)))
        random.shuffle(rangsor)     # a hölgyek „rangja" (a két szélső tiltott)
        yield ctx.mond(f"{nev}, hét hölgy vonul el előtted. A szultán int: a "
                       "rangsor két szélső hölgyét – a szíve csücskeit – NEM "
                       "választhatod.")
        for i, h in enumerate(kevert, 1):
            yield ctx.mond(f"{i}. hölgy: {h}.")
        v = yield ctx.kerdez(f"Melyik hölgyet választod? (1-{len(kevert)})")
        k = szam(v, 1, len(kevert))
        if k is None:
            yield ctx.mond("Egy érvényes sorszámot kérek.")
            continue
        if rangsor[k - 1] in tiltott:
            yield ctx.mond(f"Jaj, {kevert[k - 1]} a szultán kedvence! Kardot "
                           "rántotok, és párbaj következik.")
            yield ctx.kerdez("Nyomj Entert a párbajhoz!")
            kimenet = random.choice(["gyoz", "veszt", "dontetlen"])
            if kimenet == "gyoz":
                yield ctx.mond("Legyőzted a szultánt párbajban! Tiéd a trón és "
                               "a hála – legendává lettél!")
            elif kimenet == "veszt":
                yield ctx.mond("A szultán jobb kardforgatónak bizonyult – "
                               "ezúttal alulmaradtál, de élsz és tanultál.")
            else:
                yield ctx.mond("A párbaj döntetlen – a szultán megveregeti a "
                               "válladat, és barátságot köttök.")
        else:
            yield ctx.mond(f"Bölcsen döntöttél: {kevert[k - 1]} kezét nyerted "
                           "el, és a szultán áldását adja rátok. Boldog "
                           "befejezés!")
        v = yield ctx.kerdez("Új kaland? (igen/nem)")
        if not igen(v, False):
            break
    yield ctx.vege("Köszönöm a játékot!")
