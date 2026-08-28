# -*- coding: utf-8 -*-
"""Kvíz / oktató retró játékok: Állatismeret, Főváros, Atomvadász, Braille,
Morse, Szókitaláló, Számtan tanár, Memória, Memory, Billentyűzet verseny.

A válaszokat lazán vetjük össze (kis/nagybetű és ékezet nem számít), hogy
vakon, gyors gépeléssel is jól használható legyen.
"""
import random
import re

from ._util import igen, szam, valaszt, kever, egyezik, ekezet_nelkul


# ============================================================== ÁLLATISMERET
_ALLAT = {
    "oroszlán": ("Afrika", "ragadozó", "emlős"),
    "zebra": ("Afrika", "növényevő", "emlős"),
    "elefánt": ("Afrika", "növényevő", "emlős"),
    "zsiráf": ("Afrika", "növényevő", "emlős"),
    "gepárd": ("Afrika", "ragadozó", "emlős"),
    "teve": ("Ázsia", "növényevő", "emlős"),
    "tigris": ("Ázsia", "ragadozó", "emlős"),
    "panda": ("Ázsia", "növényevő", "emlős"),
    "kenguru": ("Ausztrália", "növényevő", "emlős"),
    "koala": ("Ausztrália", "növényevő", "emlős"),
    "medve": ("Európa", "mindenevő", "emlős"),
    "róka": ("Európa", "mindenevő", "emlős"),
    "farkas": ("Európa", "ragadozó", "emlős"),
    "jaguár": ("Amerika", "ragadozó", "emlős"),
    "cápa": ("világ", "ragadozó", "hal"),
    "delfin": ("világ", "ragadozó", "emlős"),
    "bálna": ("világ", "ragadozó", "emlős"),
    "csótány": ("világ", "mindenevő", "rovar"),
    "bolha": ("világ", "ragadozó", "rovar"),
    "patkány": ("világ", "mindenevő", "emlős"),
}


def jatek_allatism(ctx):
    v = yield ctx.kerdez("Hány kérdést kérsz? (például 5)")
    db = szam(v, 1, 100) or 5
    allatok = list(_ALLAT)
    jo = 0
    for i in range(db):
        a = valaszt(allatok)
        kont, tap, oszt = _ALLAT[a]
        tip = random.randint(1, 3)
        if tip == 1:
            v = yield ctx.kerdez(f"{i + 1}. Melyik földrészen él a(z) {a}? "
                                 "(ha több helyen: világ)")
            ok, helyes = egyezik(v, kont), kont
        elif tip == 2:
            v = yield ctx.kerdez(f"{i + 1}. Mivel táplálkozik a(z) {a}? "
                                 "(növényevő / ragadozó / mindenevő)")
            ok, helyes = egyezik(v, tap), tap
        else:
            v = yield ctx.kerdez(f"{i + 1}. Hová tartozik a(z) {a}? "
                                 "(emlős / hal / rovar)")
            ok, helyes = egyezik(v, oszt), oszt
        if ok:
            jo += 1
            yield ctx.mond("Helyes!")
        else:
            yield ctx.mond(f"Nem, a helyes válasz: {helyes}.")
    yield ctx.mond(f"Vége. {jo} helyes válasz {db}-ből.")
    yield ctx.vege("Köszönöm a játékot!")


# ==================================================================== FŐVÁROS
_FOVAROS = {
    "Magyarország": ("Budapest", ()),
    "Ausztria": ("Bécs", ("Wien",)),
    "Németország": ("Berlin", ()),
    "Franciaország": ("Párizs", ("Paris",)),
    "Anglia": ("London", ()),
    "Olaszország": ("Róma", ("Roma", "Rome")),
    "Spanyolország": ("Madrid", ()),
    "Oroszország": ("Moszkva", ("Moscow",)),
    "Japán": ("Tokió", ("Tokyo",)),
    "Kína": ("Peking", ("Beijing",)),
    "Görögország": ("Athén", ("Athen",)),
    "Csehország": ("Prága", ("Praha", "Prague")),
    "Lengyelország": ("Varsó", ("Warszawa",)),
    "Románia": ("Bukarest", ()),
    "Ukrajna": ("Kijev", ("Kiev", "Kyiv")),
    "Dánia": ("Koppenhága", ("Kobenhavn",)),
    "Norvégia": ("Oslo", ()),
    "Finnország": ("Helsinki", ()),
    "Bulgária": ("Szófia", ("Sofia",)),
    "Írország": ("Dublin", ()),
    "Kuba": ("Havanna", ("Havana",)),
    "Nepál": ("Katmandu", ("Kathmandu",)),
}


def jatek_fovaros(ctx):
    v = yield ctx.kerdez("Hány kérdést kérsz? (például 5)")
    db = szam(v, 1, 100) or 5
    orszagok = list(_FOVAROS)
    jo = 0
    for i in range(db):
        o = valaszt(orszagok)
        fo, al = _FOVAROS[o]
        v = yield ctx.kerdez(f"{i + 1}. Mi {o} fővárosa?")
        if egyezik(v, fo, al):
            jo += 1
            yield ctx.mond("Helyes!")
        else:
            yield ctx.mond(f"Nem, {o} fővárosa {fo}.")
    yield ctx.mond(f"Vége. {jo} helyes válasz {db}-ből.")
    yield ctx.vege("Köszönöm a játékot!")


# ================================================================= ATOMVADÁSZ
_MOLEK = [
    ("szén-dioxid", ["C", "O", "O"]),
    ("szén-monoxid", ["C", "O"]),
    ("víz", ["H", "H", "O"]),
    ("metán", ["C", "H", "H", "H", "H"]),
    ("ammónia", ["N", "H", "H", "H"]),
]
_ATOMSZAVAK = ["malac", "kukac", "pocok", "pillangó", "vakond", "asztal",
               "cirok", "juhar", "hattyú", "borona", "kolomp", "harang",
               "csónak", "torony", "iskola"]


def jatek_atomvad(ctx):
    yield ctx.mond(
        "ATOMVADÁSZ. Egy molekula nevét mondom, és a benne lévő atomok "
        "vegyjeleit kell megtalálnod a szavakban. Megmutatok egy szót, te "
        "pedig megmondod, hányadik betűje a keresett vegyjel, 1-től számolva.")
    while True:
        nev, atomok = valaszt(_MOLEK)
        yield ctx.mond(f"A molekula: {nev}. Atomjai: {', '.join(atomok)}.")
        for jel in dict.fromkeys(atomok):
            j = jel.lower()
            szo = None
            for _ in range(60):
                s = valaszt(_ATOMSZAVAK)
                if j in ekezet_nelkul(s):
                    szo = s
                    break
            if szo is None:
                szo = j + "óra"          # tartalék: garantáltan tartalmazza
            norm = ekezet_nelkul(szo)
            pozok = [i + 1 for i, ch in enumerate(norm) if ch == j]
            v = yield ctx.kerdez(f"A(z) {jel} vegyjelet keresd a szóban: "
                                 f"„{szo}”. Hányadik betűje?")
            n = szam(v, 1, len(szo))
            if n is not None and n in pozok:
                yield ctx.mond(f"Helyes! A(z) {jel} atom megvan.")
            else:
                jok = ", ".join(str(p) for p in pozok)
                yield ctx.mond(f"Nem talált. A(z) {jel} helye a(z) {jok}. betű.")
        yield ctx.mond(f"A(z) {nev} molekula összeállt!")
        v = yield ctx.kerdez("Új molekula? (igen/nem)")
        if not igen(v, False):
            break
    yield ctx.vege("Köszönöm a játékot!")


# ==================================================================== BRAILLE
#
# A MAGYAR Braille-ábécé – nem az angol! A kettő NEM ugyanaz, és pont a
# leggyakrabban gyakorolt betűknél tér el:
#
#     z  =  1 2 6      (az angolban 1 3 5 6)
#     q  =  1 2 3 4 6  (az angolban 1 2 3 4 5)
#
# Korábban az angol tábla volt beépítve, ékezetes betűk nélkül – vagyis a
# játék ROSSZ értékeket tanított. [felhasználói jelzés, 2026-08-24]
#
# FORRÁS – két, egymástól független hiteles forrás, amelyek MINDENBEN egyeznek:
#   • a liblouis magyar tábla (`hu-chardefs.cti`, `hu-hu-g1.ctb`), amit az
#     INFOALAP gondoz, és amit az NVDA képernyőolvasó is használ;
#   • a magyar Braille-ábécé nyilvános táblája (lexiq.hu), Unicode
#     Braille-jelekkel – a jeleket pontszámokra váltva minden érték egyezik.
#
# A dz és a dzs NEM külön jel: két, illetve három cellával íródik (d+z,
# d+zs), ezért nincs a táblában.

# alapbetűk (az a–p és az r–y a nemzetközivel azonos; a q és a z MAGYAR)
_BRAILLE_ALAP = {
    "a": "1", "b": "12", "c": "14", "d": "145", "e": "15", "f": "124",
    "g": "1245", "h": "125", "i": "24", "j": "245", "k": "13", "l": "123",
    "m": "134", "n": "1345", "o": "135", "p": "1234", "q": "12346",
    "r": "1235", "s": "234", "t": "2345", "u": "136", "v": "1236",
    "w": "2456", "x": "1346", "y": "13456", "z": "126",
}

# ékezetes magánhangzók – ezek a magyar pontírás sajátjai
_BRAILLE_EKEZETES = {
    "á": "4", "é": "16", "í": "34", "ó": "246", "ö": "12345",
    "ő": "12456", "ú": "346", "ü": "12356", "ű": "23456",
}

# kétjegyű mássalhangzók – MINDEGYIK EGYETLEN cellával íródik
_BRAILLE_KETJEGYU = {
    "cs": "146", "gy": "1456", "ly": "456", "ny": "1246",
    "sz": "156", "ty": "1256", "zs": "345",
}

_BRAILLE = dict(_BRAILLE_ALAP)
_BRAILLE.update(_BRAILLE_EKEZETES)
_BRAILLE.update(_BRAILLE_KETJEGYU)

_BRAILLE_KESZLETEK = (
    ("alapbetűk (a-tól z-ig)", _BRAILLE_ALAP),
    ("ékezetes magánhangzók", _BRAILLE_EKEZETES),
    ("kétjegyű mássalhangzók", _BRAILLE_KETJEGYU),
    ("a teljes magyar ábécé", _BRAILLE),
)


def _pontok(s):
    return "".join(sorted(ch for ch in (s or "") if ch in "123456"))


def braille_jel(pontok: str) -> str:
    """A pontszámokból Unicode Braille-jel (⠵), hogy a Braille-kijelzőn és a
    képernyőn is látszódjon, amiről szó van."""
    kod = 0
    for ch in _pontok(pontok):
        kod |= 1 << (int(ch) - 1)
    return chr(0x2800 + kod)


def jatek_braille(ctx):
    yield ctx.mond("Braille gyakorlat a MAGYAR pontírás szerint. "
                   "Figyelem: a magyar ábécé néhány betűnél eltér az "
                   "angoltól – a z például 1, 2, 6.")
    v = yield ctx.kerdez(
        "Mit gyakorolsz? 1 = alapbetűk, 2 = ékezetes magánhangzók, "
        "3 = kétjegyű mássalhangzók, 4 = a teljes ábécé")
    keszlet_nev, keszlet = _BRAILLE_KESZLETEK[(szam(v, 1, 4) or 1) - 1]
    v = yield ctx.kerdez("Hány kérdést kérsz? (például 5)")
    db = szam(v, 1, 50) or 5
    v = yield ctx.kerdez("Mód: 1 = betűből pontok, 2 = pontokból betű")
    mod = szam(v, 1, 2) or 1
    yield ctx.mond("Gyakorlás: %s, %d kérdés." % (keszlet_nev, db))
    betuk = list(keszlet)
    jo = 0
    for i in range(db):
        b = valaszt(betuk)
        pontok = keszlet[b]
        if mod == 1:
            v = yield ctx.kerdez(
                f"{i + 1}. Milyen pontokból áll a(z) „{b}”? "
                "(a pontszámok, például 1 3 5)")
            if _pontok(v) == _pontok(pontok):
                jo += 1
                yield ctx.mond("Helyes!")
            else:
                yield ctx.mond("Nem. A(z) %s pontjai: %s. %s"
                               % (b, " ".join(pontok), braille_jel(pontok)))
        else:
            v = yield ctx.kerdez(f"{i + 1}. Melyik betű ez a pontkombináció: "
                                 f"{' '.join(pontok)}?")
            if egyezik(v, b):
                jo += 1
                yield ctx.mond("Helyes!")
            else:
                yield ctx.mond("Nem. Ez a(z) %s. %s" % (b, braille_jel(pontok)))
    yield ctx.mond(f"Vége. {jo} helyes válasz {db}-ből.")
    yield ctx.vege("Köszönöm a játékot!")


# ====================================================================== MORSE
_MORSE = {
    "a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".", "f": "..-.",
    "g": "--.", "h": "....", "i": "..", "j": ".---", "k": "-.-", "l": ".-..",
    "m": "--", "n": "-.", "o": "---", "p": ".--.", "q": "--.-", "r": ".-.",
    "s": "...", "t": "-", "u": "..-", "v": "...-", "w": ".--", "x": "-..-",
    "y": "-.--", "z": "--..",
}


def jatek_morse(ctx):
    v = yield ctx.kerdez(
        "Mit szeretnél? 1 = Morse-kód gyakorlása, 2 = szöveg lemorzézása")
    mod = szam(v, 1, 2) or 1
    if mod == 2:
        while True:
            v = yield ctx.kerdez("Írj be egy szót vagy mondatot (lemorzézom):")
            t = ekezet_nelkul(v)
            jelek = []
            for ch in t:
                if ch == " ":
                    jelek.append("/")
                elif ch in _MORSE:
                    jelek.append(_MORSE[ch])
            yield ctx.mond("Morze: " + "   ".join(jelek) if jelek
                           else "Ebben nincs mit morzézni.")
            v = yield ctx.kerdez("Újabb szöveg? (igen/nem)")
            if not igen(v, False):
                break
        yield ctx.vege("Köszönöm a játékot!")
        return
    v = yield ctx.kerdez("Hány kérdést kérsz? (például 5)")
    db = szam(v, 1, 50) or 5
    betuk = list(_MORSE)
    jo = 0
    for i in range(db):
        b = valaszt(betuk)
        v = yield ctx.kerdez(f"{i + 1}. Mi a Morse-kódja a(z) „{b}” betűnek? "
                             "(pont = ponttal, vonás = kötőjellel)")
        t = (v or "").strip().replace("·", ".").replace("–", "-").replace(" ", "")
        if t == _MORSE[b]:
            jo += 1
            yield ctx.mond("Helyes!")
        else:
            yield ctx.mond(f"Nem. A(z) {b} kódja: {_MORSE[b]}.")
    yield ctx.mond(f"Vége. {jo} helyes válasz {db}-ből.")
    yield ctx.vege("Köszönöm a játékot!")


# ================================================================ SZÓKITALÁLÓ
_FOGALMAK = [
    ("alma", ["gyümölcs", "kerek", "piros vagy zöld", "a fán terem"]),
    ("oroszlán", ["állat", "ragadozó", "Afrikában él", "sörénye van"]),
    ("kalapács", ["szerszám", "nyele van", "vasból a feje", "szöget versz vele"]),
    ("teve", ["állat", "növényevő", "sivatagban él", "púpja van"]),
    ("görögdinnye", ["gyümölcs", "nagy és kerek", "zöld a héja",
                     "piros a belseje"]),
    ("zsiráf", ["állat", "növényevő", "Afrikában él", "hosszú a nyaka"]),
    ("uborka", ["zöldség", "hosszúkás", "zöld", "savanyítani szokták"]),
]


def jatek_kitalal(ctx):
    yield ctx.mond(
        "SZÓKITALÁLÓ. Egy fogalomra gondolok, és tulajdonságokat árulok el "
        "róla. Találd ki, mire gondolok! Enterrel kérheted a következő "
        "tulajdonságot.")
    pont = 0
    while True:
        nev, tulaj = valaszt(_FOGALMAK)
        talalt = False
        for i, t in enumerate(tulaj):
            v = yield ctx.kerdez(f"{i + 1}. tulajdonság: {t}. Mire gondolok?")
            if egyezik(v, nev):
                pont += 1
                talalt = True
                yield ctx.mond(f"Eltaláltad! {4 - i} pont. Ez a(z) {nev}.")
                break
            if (v or "").strip():
                yield ctx.mond("Nem az. Jön a következő tulajdonság.")
        if not talalt:
            yield ctx.mond(f"Elfogytak a tippek – a megoldás: {nev}.")
        yield ctx.mond(f"Pontod: {pont}.")
        v = yield ctx.kerdez("Új fogalom? (igen/nem)")
        if not igen(v, False):
            break
    yield ctx.vege("Köszönöm a játékot!")


# ================================================================ SZÁMTAN TANÁR
def jatek_szamtan(ctx):
    v = yield ctx.kerdez("Mekkora legyen a legnagyobb szám? (például 20)")
    nagy = szam(v, 2, 10000) or 20
    v = yield ctx.kerdez("Milyen műveletek legyenek? (írd be a jeleket, "
                         "például: + - *   a négy jel: + - * /)")
    muvek = [m for m in "+-*/" if m in (v or "")]
    if not muvek:
        yield ctx.mond("Nem választottál műveletet – akkor minek ébresztettél "
                       "fel? Legyen összeadás.")
        muvek = ["+"]
    v = yield ctx.kerdez("Hány feladatot kérsz? (például 5)")
    db = szam(v, 1, 100) or 5
    jo = 0
    kis = max(2, nagy // 5)
    for i in range(db):
        m = valaszt(muvek)
        if m == "+":
            a, b = random.randint(1, nagy), random.randint(1, nagy)
            q, e = f"{a} meg {b}", a + b
        elif m == "-":
            a, b = random.randint(1, nagy), random.randint(1, nagy)
            if b > a:
                a, b = b, a
            q, e = f"{a} mínusz {b}", a - b
        elif m == "*":
            a, b = random.randint(1, kis), random.randint(1, kis)
            q, e = f"{a} szorozva {b}", a * b
        else:
            b, e = random.randint(1, kis), random.randint(1, kis)
            a = e * b
            q = f"{a} osztva {b}"
        v = yield ctx.kerdez(f"{i + 1}. Mennyi {q}?")
        if szam(v) == e:
            jo += 1
            yield ctx.mond("Helyes!")
        else:
            yield ctx.mond(f"Nem, a helyes eredmény {e}.")
    yield ctx.mond(f"Vége. {jo} helyes válasz {db}-ből.")
    yield ctx.vege("Köszönöm a játékot!")


# =================================================== MEMÓRIA (sorrend-memória)
_MEMSZAVAK = ["ablak", "asztal", "bicikli", "fecske", "galamb", "gomb",
              "gomba", "kard", "kecske", "kefe", "macska", "orgona",
              "sisak", "teve", "zene", "zongora"]


def jatek_memoria(ctx):
    yield ctx.mond(
        "MEMÓRIA. Mondok egy egyre hosszabb sorozatot; írd vissza pontosan, "
        "az elemeket szóközzel vagy vesszővel elválasztva. Egy hiba, és vége.")
    while True:
        sor = []
        szint = 0
        while True:
            szint += 1
            sor.append(valaszt(_MEMSZAVAK))
            yield ctx.mond(f"{szint}. szint. A sorozat: {', '.join(sor)}.")
            v = yield ctx.kerdez("Írd vissza a sorozatot:")
            adott = [ekezet_nelkul(x) for x in re.split(r"[ ,]+", (v or "").strip())
                     if x]
            if adott != [ekezet_nelkul(x) for x in sor]:
                yield ctx.mond(f"Hiba! A helyes sorozat: {', '.join(sor)}. "
                               f"Elért szinted: {szint - 1}.")
                break
            yield ctx.mond("Helyes, jöhet a következő!")
        v = yield ctx.kerdez("Új játék? (igen/nem)")
        if not igen(v, False):
            break
    yield ctx.vege("Köszönöm a játékot!")


# =================================================== MEMORY (párosító memória)
def jatek_memory(ctx):
    szavak = ["alma", "körte", "cica", "kutya", "hal", "madár", "virág", "autó"]
    ertekek = kever(szavak * 2)
    oszlopok = "abcd"
    cellak = {}
    idx = 0
    for s in range(1, 5):
        for o in oszlopok:
            cellak[f"{o}{s}"] = ertekek[idx]
            idx += 1
    felfedve = set()
    yield ctx.mond(
        "MEMORY, párosító. Négyszer négyes rács, nyolc pár. A mezőket "
        "oszlopbetű és sorszám adja, például a1 vagy d4. Válassz két mezőt; "
        "ha párt találsz, felfedve marad.")
    lepes = 0
    while len(felfedve) < 16:
        v = yield ctx.kerdez("Első mező (például b2):")
        e = (v or "").strip().lower()
        if e not in cellak or e in felfedve:
            yield ctx.mond("Érvényes, még rejtett mezőt kérek.")
            continue
        yield ctx.mond(f"{e}: {cellak[e]}.")
        v = yield ctx.kerdez("Második mező:")
        m = (v or "").strip().lower()
        if m not in cellak or m in felfedve or m == e:
            yield ctx.mond("Érvényes, másik rejtett mezőt kérek.")
            continue
        yield ctx.mond(f"{m}: {cellak[m]}.")
        lepes += 1
        if cellak[e] == cellak[m]:
            felfedve.update((e, m))
            yield ctx.mond(f"Pár! Megvan {len(felfedve) // 2} a nyolcból.")
        else:
            yield ctx.mond("Nem pár, próbáld megjegyezni!")
    yield ctx.mond(f"Minden párt megtaláltál, {lepes} lépésből! Ügyes vagy!")
    yield ctx.vege("Köszönöm a játékot!")


# ========================================================= BILLENTYŰZET VERSENY
_PARVER = [
    ("nagy iksz", "X"), ("nagy ipszilon", "Y"), ("nagy zé", "Z"),
    ("nyitó zárójel", "("), ("záró zárójel", ")"), ("csillag", "*"),
    ("perjel", "/"), ("kettőspont", ":"), ("pontosvessző", ";"),
    ("kukac", "@"), ("kettős kereszt", "#"), ("százalék", "%"),
    ("kérdőjel", "?"), ("felkiáltójel", "!"),
]


def jatek_parver(ctx):
    yield ctx.mond(
        "BILLENTYŰZET VERSENY. Bemondok egy jelet; írd be minél gyorsabban a "
        "megfelelő karaktert. Tíz kör lesz.")
    pont = 0
    for i in range(10):
        nev, kar = valaszt(_PARVER)
        v = yield ctx.kerdez(f"{i + 1}. jel: {nev}")
        if (v or "").strip().upper() == kar.upper():
            pont += 1
            yield ctx.mond("Helyes!")
        else:
            yield ctx.mond(f"Nem, ez a jel: {kar}.")
    yield ctx.mond(f"Vége. {pont} helyes 10-ből. "
                   + ("Kiváló reflex!" if pont >= 8 else "Gyakorolj még!"))
    yield ctx.vege("Köszönöm a játékot!")
