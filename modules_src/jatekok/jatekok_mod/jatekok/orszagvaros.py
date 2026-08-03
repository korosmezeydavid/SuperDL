# -*- coding: utf-8 -*-
"""Ország-Város-Fiú-Lány – Mezei Géza ötlete alapján.

A gép „megpörgeti az ábécét", a játékos pedig Enterrel megállítja egy betűn.
Arra a betűre a játékos megnevez egy ORSZÁGOT, egy VÁROST, egy FIÚ- és egy
LÁNY-nevet. A gép ellenőrzi a kezdőbetűt: amit a beépített szótárban is ismer,
az két pont; amit nem talál, de a helyes betűvel kezdődik, azt elhiszi a
játékosnak (egy pont). Több játékos felváltva; a hangot a konzol adja.

A gép csak olyan betűn állhat meg, amelyre MIND A NÉGY kategóriában van
válasz – így a játékos mindig tud érvényeset mondani.
"""
import random

from ._util import ekezet_nelkul, szam


# --- ORSZÁGOK -------------------------------------------------------------
_ORSZAGOK_NYERS = (
    "Afganisztán", "Albánia", "Algéria", "Andorra", "Angola", "Argentína",
    "Ausztria", "Ausztrália", "Azerbajdzsán", "Belgium", "Bosznia",
    "Brazília", "Bulgária", "Bhután", "Bolívia", "Chile", "Ciprus",
    "Csehország", "Csád", "Dánia", "Dél-Afrika", "Dominika", "Ecuador",
    "Egyiptom", "Elefántcsontpart", "Eritrea", "Észtország", "Etiópia",
    "Fehéroroszország", "Fidzsi", "Finnország", "Franciaország", "Gabon",
    "Ghána", "Görögország", "Grúzia", "Guatemala", "Guyana", "Haiti",
    "Hollandia", "Honduras", "Horvátország", "India", "Indonézia", "Irak",
    "Irán", "Izland", "Izrael", "Japán", "Jamaica", "Jemen", "Jordánia",
    "Kambodzsa", "Kamerun", "Kanada", "Katar", "Kazahsztán", "Kenya",
    "Kína", "Kolumbia", "Kongó", "Kuba", "Kuvait", "Laosz", "Lengyelország",
    "Lettország", "Libanon", "Libéria", "Líbia", "Litvánia", "Luxemburg",
    "Macedónia", "Madagaszkár", "Magyarország", "Malajzia", "Mali", "Málta",
    "Marokkó", "Mexikó", "Moldova", "Monaco", "Mongólia", "Montenegró",
    "Mozambik", "Namíbia", "Németország", "Nepál", "Nicaragua", "Nigéria",
    "Norvégia", "Olaszország", "Omán", "Oroszország", "Pakisztán", "Panama",
    "Paraguay", "Peru", "Portugália", "Románia", "Ruanda", "Spanyolország",
    "Svájc", "Svédország", "Szenegál", "Szerbia", "Szíria", "Szlovákia",
    "Szlovénia", "Szomália", "Szudán", "Tajvan", "Tanzánia", "Thaiföld",
    "Törökország", "Tunézia", "Ukrajna", "Uruguay", "Venezuela", "Vietnam",
    "Zambia", "Zimbabwe",
)

# --- VÁROSOK (magyar + világ) --------------------------------------------
_VAROSOK_NYERS = (
    "Amszterdam", "Ankara", "Athén", "Aachen", "Bécs", "Berlin", "Budapest",
    "Barcelona", "Belgrád", "Bordeaux", "Bréma", "Cegléd", "Chicago",
    "Debrecen", "Dublin", "Dunaújváros", "Eger", "Esztergom", "Edinburgh",
    "Firenze", "Frankfurt", "Genf", "Győr", "Gyula", "Graz", "Hamburg",
    "Helsinki", "Hódmezővásárhely", "Isztambul", "Innsbruck", "Jászberény",
    "Kairó", "Kecskemét", "Koppenhága", "Kolozsvár", "Kaposvár", "London",
    "Lisszabon", "Lyon", "Miskolc", "Madrid", "München", "Milánó", "Moszkva",
    "Nyíregyháza", "Nápoly", "Oslo", "Oxford", "Pécs", "Párizs", "Prága",
    "Pozsony", "Riga", "Róma", "Rotterdam", "Salgótarján", "Szeged",
    "Szolnok", "Székesfehérvár", "Sopron", "Stockholm", "Sydney", "Tokió",
    "Tatabánya", "Toronto", "Torino", "Utrecht", "Ungvár", "Vác", "Varsó",
    "Velence", "Veszprém", "Washington", "Zürich", "Zalaegerszeg", "Zágráb",
)

# --- FIÚ nevek ------------------------------------------------------------
_FIUK_NYERS = (
    "Ábel", "Ádám", "Ákos", "Aladár", "Albert", "András", "Antal", "Attila",
    "Balázs", "Barnabás", "Bence", "Bertalan", "Béla", "Bálint", "Csaba",
    "Dániel", "Dávid", "Dénes", "Dezső", "Domonkos", "Ede", "Elemér",
    "Endre", "Ernő", "Ervin", "Ferenc", "Fülöp", "Gábor", "Gergely", "Géza",
    "Győző", "Gyula", "Hunor", "Huba", "Imre", "István", "Iván", "Ignác",
    "János", "József", "Jenő", "Jónás", "Kálmán", "Károly", "Kristóf",
    "Krisztián", "Konrád", "László", "Levente", "Lajos", "Lóránt", "Lőrinc",
    "Márk", "Márton", "Máté", "Mihály", "Miklós", "Mátyás", "Nándor",
    "Norbert", "Olivér", "Ottó", "Ödön", "Örs", "Pál", "Péter", "Patrik",
    "Rezső", "Richárd", "Róbert", "Roland", "Sándor", "Sebestyén", "Simon",
    "Szabolcs", "Szilárd", "Tamás", "Tibor", "Tivadar", "Ubul", "Vazul",
    "Viktor", "Vilmos", "Vince", "Zsigmond", "Zoltán", "Zsolt", "Zénó",
)

# --- LÁNY nevek -----------------------------------------------------------
_LANYOK_NYERS = (
    "Adél", "Ágnes", "Aliz", "Anna", "Anikó", "Anett", "Beáta", "Bernadett",
    "Bianka", "Blanka", "Borbála", "Brigitta", "Cecília", "Csilla", "Dalma",
    "Dóra", "Dorottya", "Diána", "Edit", "Emese", "Emma", "Erika",
    "Erzsébet", "Eszter", "Éva", "Fanni", "Flóra", "Franciska", "Gabriella",
    "Gizella", "Gyöngyi", "Györgyi", "Hajnalka", "Hanna", "Henrietta",
    "Ibolya", "Ildikó", "Ilona", "Irén", "Izabella", "Janka", "Judit",
    "Julianna", "Júlia", "Katalin", "Kinga", "Klára", "Krisztina", "Laura",
    "Lilla", "Lívia", "Luca", "Magdolna", "Margit", "Mária", "Márta",
    "Melinda", "Mónika", "Nóra", "Noémi", "Nikolett", "Orsolya", "Otília",
    "Piroska", "Petra", "Réka", "Rita", "Rozália", "Sára", "Szilvia",
    "Sarolta", "Tímea", "Tünde", "Teréz", "Ulrika", "Valéria", "Vanda",
    "Vera", "Viktória", "Virág", "Zita", "Zsófia", "Zsuzsanna", "Zsanett",
)


def _norm_keszlet(nyers):
    return frozenset(ekezet_nelkul(x) for x in nyers)


_ORSZAGOK = _norm_keszlet(_ORSZAGOK_NYERS)
_VAROSOK = _norm_keszlet(_VAROSOK_NYERS)
_FIUK = _norm_keszlet(_FIUK_NYERS)
_LANYOK = _norm_keszlet(_LANYOK_NYERS)

_KATEGORIAK = (
    ("egy ORSZÁGOT", _ORSZAGOK),
    ("egy VÁROST", _VAROSOK),
    ("egy FIÚ nevet", _FIUK),
    ("egy LÁNY nevet", _LANYOK),
)


def _elso_betuk(keszlet):
    return {sz[0] for sz in keszlet if sz}


# csak olyan betűre állhat meg a gép, amelyre MIND A NÉGY kategóriában van
# válasz – így a játékos garantáltan tud érvényeset mondani
_BETUK = sorted(_elso_betuk(_ORSZAGOK) & _elso_betuk(_VAROSOK)
                & _elso_betuk(_FIUK) & _elso_betuk(_LANYOK))


def _ertekel(valasz, betu, keszlet):
    """Egy válasz elbírálása. Visszaad: (állapot, pont).
    'ismer' = a szótárban is szerepel (2 pont); 'elfogad' = jó betű, de nincs a
    listámban, elhiszem (1 pont); 'rosszbetu' = más betűvel kezdődik (0);
    'ures' = nem mondott semmit (0)."""
    v = ekezet_nelkul(valasz)
    if not v:
        return "ures", 0
    if v[0] != betu:
        return "rosszbetu", 0
    if v in keszlet:
        return "ismer", 2
    return "elfogad", 1


def _csalodas():
    """Véletlen csalódott közönség-hang a nullás körre (a Szerencsekerékből)."""
    return random.choice(("boo", "awww", "ooo"))


def _porget(ctx):
    """A gép megpörgeti az ábécét, és megáll egy betűn. Visszaadja a betűt.
    A pörgés a közös kerékpörgés-hang (a hangot a teszt-hajtó átugorja)."""
    betu = random.choice(_BETUK)
    yield ctx.effekt_var("kerekporges")   # a pörgés-hang TELJESEN leszól
    return betu


def jatek_orszagvaros(ctx):
    yield ctx.mond(
        "ORSZÁG, VÁROS, FIÚ, LÁNY! Ezt a játékot Mezei Géza álmodta meg – "
        "köszönjük az ötletet! A gép megpörgeti az ábécét, te pedig Enterrel "
        "megállítod egy betűn. Arra a betűre mondasz egy országot, egy várost, "
        "egy fiú- és egy lánynevet. Amit a szótáramban is ismerek, két pont; "
        "amit nem találok, de a jó betűvel kezdődik, azt elhiszem neked: egy "
        "pont. Aki a végén a legtöbb pontot gyűjti, nyer!")

    v = yield ctx.kerdez("Hányan játszotok? (1-4)")
    n = szam(v, 1, 4) or 1
    nevek = []
    for i in range(n):
        nv = yield ctx.kerdez(f"A(z) {i + 1}. játékos neve? "
                              f"(Enter = Játékos {i + 1})")
        nevek.append((nv or "").strip() or f"Játékos {i + 1}")
    v = yield ctx.kerdez("Hány kört játsszunk? (1-10, Enter = 3)")
    korok = szam(v, 1, 10) or 3
    pontok = [0] * n

    for kor in range(1, korok + 1):
        yield ctx.mond(f"--- {kor}. kör a {korok}-ből ---")
        for i in range(n):
            yield ctx.kerdez(f"{nevek[i]} jön. Nyomj Entert, és megpörgetem "
                             "az ábécét!")
            betu = yield from _porget(ctx)
            nagy = betu.upper()
            yield ctx.mond(f"Megállt a(z) {nagy} betűn! Most jöhet a négy szó.")
            korpont = 0
            for cimke, keszlet in _KATEGORIAK:
                valasz = yield ctx.kerdez(f"{nagy} betűvel mondj {cimke}:")
                allapot, pont = _ertekel(valasz, betu, keszlet)
                korpont += pont
                if allapot == "ismer":
                    yield ctx.mond(f"Ismerem! Két pont. ({valasz.strip()})")
                elif allapot == "elfogad":
                    yield ctx.mond("Ezt nem találom a listámban, de elhiszem "
                                   "neked – egy pont.")
                elif allapot == "rosszbetu":
                    yield ctx.mond(f"Ez nem a(z) {nagy} betűvel kezdődik – "
                                   "nulla pont.")
                else:
                    yield ctx.mond("Kihagytad – nulla pont.")
            pontok[i] += korpont
            if korpont == 0:
                yield ctx.effekt(_csalodas())        # csalódott közönség
            elif korpont == 8:
                yield ctx.mond("Telitalálat – mind a négy szó ült!")
            yield ctx.mond(f"{nevek[i]} ebben a körben {korpont} pontot "
                           f"szerzett, összesen {pontok[i]}.")

    sorrend = sorted(range(n), key=lambda i: pontok[i], reverse=True)
    yield ctx.mond("Vége a játéknak! Végeredmény:")
    for hely, i in enumerate(sorrend, 1):
        yield ctx.mond(f"{hely}. hely: {nevek[i]} – {pontok[i]} pont.")
    yield ctx.effekt("taps")                          # tapsvihar a győztesnek
    if n > 1 and pontok[sorrend[0]] == pontok[sorrend[1]]:
        yield ctx.vege("Holtverseny az élen! Szép volt mindenkinek. "
                       "Köszönjük az ötletet és a közös játékot, Mezei Géza!")
    else:
        yield ctx.vege(f"A győztes: {nevek[sorrend[0]]}! Gratulálok! "
                       "Köszönjük az ötletet és a közös játékot, Mezei Géza!")
