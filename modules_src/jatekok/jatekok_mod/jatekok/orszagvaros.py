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

from ._util import ekezet_nelkul, igen, szam


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


# --- PLUSZ (bővített módú) kategóriák seed-listái ---------------------------
# (a szótár bővíthető a „Tanítás" fülön; ami nincs a listában, azt a jó betű
#  esetén a gép elhiszi – 1 pont)
_HIRESEK_NYERS = (
    "Ady", "Arany", "Beethoven", "Bartók", "Chaplin", "Curie", "Darwin",
    "Deák", "Edison", "Einstein", "Freud", "Gagarin", "Gandhi", "Hemingway",
    "Homérosz", "Ibsen", "Jókai", "Kolumbusz", "Kossuth", "Leonardo", "Liszt",
    "Madách", "Mozart", "Napóleon", "Newton", "Orwell", "Petőfi", "Puskás",
    "Rembrandt", "Shakespeare", "Széchenyi", "Tolsztoj", "Verne", "Washington",
    "Zrínyi",
)
_ALLATOK_NYERS = (
    "antilop", "birka", "cica", "csiga", "delfin", "elefánt", "farkas",
    "galamb", "hangya", "iguána", "jaguár", "kutya", "lajhár", "majom",
    "medve", "nyúl", "oroszlán", "párduc", "róka", "sas", "strucc", "teve",
    "tigris", "veréb", "vidra", "zebra", "zsiráf",
)
_TARGYAK_NYERS = (
    "asztal", "bögre", "ceruza", "doboz", "ernyő", "fésű", "gyertya", "izzó",
    "kalapács", "lámpa", "mécses", "nadrág", "olló", "pohár", "radír", "seprű",
    "szék", "tányér", "toll", "üveg", "váza", "villa",
)
_NOVENYEK_NYERS = (
    "akác", "babér", "cédrus", "dália", "eperfa", "fenyő", "gyöngyvirág",
    "hárs", "ibolya", "jázmin", "kaktusz", "liliom", "muskátli", "nárcisz",
    "orgona", "pipacs", "rózsa", "sás", "tulipán", "uborka", "viola", "zsálya",
)
_MARKAK_NYERS = (
    "Adidas", "BMW", "Coca-Cola", "Danone", "Ford", "Google", "Honda", "IBM",
    "Jaguar", "Kodak", "Lego", "Microsoft", "Nike", "Opel", "Peugeot",
    "Renault", "Samsung", "Toyota", "Volvo", "Zara",
)
_HEGYEK_NYERS = (
    "Alpok", "Bükk", "Csóványos", "Etna", "Fuji", "Gerecse", "Himalája",
    "Kékes", "Mátra", "Olimposz", "Pilis", "Tátra", "Urál", "Vezúv", "Zengő",
)
_FOLYOK_NYERS = (
    "Amazonas", "Bodrog", "Duna", "Garam", "Hernád", "Ipoly", "Jangce",
    "Kongó", "Maros", "Nílus", "Ohio", "Rajna", "Sió", "Tisza", "Volga",
    "Zala", "Zagyva",
)


def _norm_keszlet(nyers):
    return frozenset(ekezet_nelkul(x) for x in nyers)


_ORSZAGOK = _norm_keszlet(_ORSZAGOK_NYERS)
_VAROSOK = _norm_keszlet(_VAROSOK_NYERS)
_FIUK = _norm_keszlet(_FIUK_NYERS)
_LANYOK = _norm_keszlet(_LANYOK_NYERS)

# --- kategória-regiszter: klasszikus 4 + bővíthető extrák -------------------
KATEGORIA_NEVEK = {
    "orszag": "Ország", "varos": "Város", "fiu": "Fiú név", "lany": "Lány név",
    "hiresember": "Híres ember", "allat": "Állat", "targy": "Tárgy",
    "noveny": "Növény", "marka": "Márka", "hegy": "Hegy", "folyo": "Folyó",
}
_CIMKE = {
    "orszag": "egy ORSZÁGOT", "varos": "egy VÁROST", "fiu": "egy FIÚ nevet",
    "lany": "egy LÁNY nevet", "hiresember": "egy HÍRES EMBERT",
    "allat": "egy ÁLLATOT", "targy": "egy TÁRGYAT", "noveny": "egy NÖVÉNYT",
    "marka": "egy MÁRKÁT", "hegy": "egy HEGYET", "folyo": "egy FOLYÓT",
}
_BUILTIN_NYERS = {
    "orszag": _ORSZAGOK_NYERS, "varos": _VAROSOK_NYERS, "fiu": _FIUK_NYERS,
    "lany": _LANYOK_NYERS, "hiresember": _HIRESEK_NYERS, "allat": _ALLATOK_NYERS,
    "targy": _TARGYAK_NYERS, "noveny": _NOVENYEK_NYERS, "marka": _MARKAK_NYERS,
    "hegy": _HEGYEK_NYERS, "folyo": _FOLYOK_NYERS,
}

# --- BŐVÍTÉS: további szavak minden kategóriához (gazdagabb szótár; a Tanítás
#     fülön tovább bővíthető) ---
_TOBB = {
    "varos": (
        "Ajka", "Baja", "Békéscsaba", "Csongrád", "Dombóvár", "Érd",
        "Gödöllő", "Gyöngyös", "Hatvan", "Kazincbarcika", "Keszthely",
        "Komárom", "Mohács", "Nagykanizsa", "Ózd", "Orosháza", "Paks",
        "Siófok", "Szekszárd", "Szentendre", "Szombathely", "Tata", "Zirc",
        "Peking", "Szöul", "Delhi", "Dubaj", "Kijev", "Lima", "Manila",
        "Ottawa", "Havanna", "Nairobi", "Bangkok", "Brüsszel", "Nizza",
        "Marseille",
    ),
    "fiu": (
        "Adorján", "Ágoston", "Benedek", "Botond", "Csongor", "Dominik",
        "Emil", "Frigyes", "Gáspár", "Gellért", "Henrik", "Hugó", "Ince",
        "Jákob", "Kornél", "Kázmér", "Lehel", "Manó", "Noel", "Oszkár",
        "Pongrác", "Rajmund", "Rudolf", "Soma", "Szilveszter", "Tobiás",
        "Vendel", "Zalán", "Zsombor", "Bendegúz", "Csanád",
    ),
    "lany": (
        "Abigél", "Amália", "Boglárka", "Bella", "Csenge", "Dorina", "Enikő",
        "Etelka", "Fruzsina", "Gréta", "Hédi", "Hortenzia", "Ilka", "Jolán",
        "Kamilla", "Karolina", "Kitti", "Lea", "Lenke", "Nelli", "Olga",
        "Panna", "Rebeka", "Regina", "Szonja", "Tekla", "Vivien", "Zsuzsa",
        "Emőke", "Villő",
    ),
    "hiresember": (
        "Bach", "Camus", "Dosztojevszkij", "Galilei", "Goethe", "Kafka",
        "Kepler", "Lincoln", "Marx", "Mendel", "Nobel", "Pasteur", "Picasso",
        "Raffaello", "Rubik", "Tesla", "Verdi", "Wagner", "Zola", "Cervantes",
        "Puskin", "Semmelweis", "Munkácsy", "Bolyai",
    ),
    "allat": (
        "bagoly", "béka", "denevér", "egér", "fecske", "gólya", "gorilla",
        "hiúz", "kacsa", "koala", "leopárd", "lepke", "mókus", "ökör", "panda",
        "pillangó", "sün", "szúnyog", "tehén", "ürge", "vaddisznó", "varjú",
        "zerge", "kígyó", "tücsök", "holló",
    ),
    "targy": (
        "ágy", "bicikli", "csésze", "esernyő", "gomb", "hátizsák", "kanál",
        "kefe", "kés", "könyv", "kulcs", "mérleg", "párna", "rádió",
        "szemüveg", "szőnyeg", "tükör", "tál", "vödör", "óra", "telefon",
        "cipő", "gyűrű",
    ),
    "noveny": (
        "boróka", "bükk", "ciprus", "csalán", "dohány", "gyömbér", "hanga",
        "komló", "len", "moha", "nefelejcs", "nyírfa", "páfrány", "petúnia",
        "repce", "som", "tölgy", "zab", "búza", "kökény", "mák", "szegfű",
    ),
    "marka": (
        "Apple", "Audi", "Bosch", "Chevrolet", "Dell", "Electrolux", "Fiat",
        "Gucci", "Hyundai", "Intel", "Lenovo", "Mercedes", "Nokia", "Oracle",
        "Philips", "Sony", "Suzuki", "Visa", "Xerox", "Yamaha", "Puma",
        "Reebok", "Siemens",
    ),
    "hegy": (
        "Andok", "Börzsöny", "Cserhát", "Dolomitok", "Everest", "Kaukázus",
        "Kárpátok", "Kilimandzsáró", "Pireneusok", "Sínai", "Ararát", "Bakony",
        "Mecsek", "Vértes",
    ),
    "folyo": (
        "Colorado", "Dráva", "Elba", "Ganga", "Indus", "Jordán", "Körös",
        "Léna", "Mississippi", "Mura", "Ob", "Pó", "Rába", "Szajna", "Temze",
        "Zambézi", "Séd", "Bega", "Kraszna",
    ),
}
for _k, _tpl in _TOBB.items():
    _BUILTIN_NYERS[_k] = tuple(_BUILTIN_NYERS[_k]) + _tpl

ALAP_KULCSOK = ("orszag", "varos", "fiu", "lany")
EXTRA_KULCSOK = ("hiresember", "allat", "targy", "noveny", "marka", "hegy",
                 "folyo")


def custom_path():
    from superdl import store
    return store.CONFIG_DIR / "orszagvaros_szotar.json"


def load_custom():
    """A felhasználó által TANÍTOTT szavak: {kategória-kulcs: [szavak]}.
    Nem tartalmaz személyes adatot – csak szavak/nevek, közkinccsé tehető."""
    try:
        from superdl import store
        d = store.load_json(custom_path(), {})
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_custom(d):
    from superdl import store
    store.save_json(custom_path(), d)


def keszlet(kulcs, custom=None):
    """Egy kategória normalizált szó-halmaza: BEÉPÍTETT + a TANÍTOTT szavak."""
    if custom is None:
        custom = load_custom()
    szavak = (list(_BUILTIN_NYERS.get(kulcs, ()))
              + list(custom.get(kulcs, []) or []))
    return frozenset(ekezet_nelkul(w) for w in szavak if str(w).strip())


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
    """A gép SOROLJA az ábécét (másodpercenként egy betű), a játékos a
    szóközzel/Enterrel megállítja – ott áll meg, SOHA nem a gép dönt.

    FONTOS: közvetlenül a sorolás ELŐTT NINCS hosszú kommentár – különben a
    képernyőolvasó a kommentárt és az első betűket egymásra torlasztaná
    (kezdő „kapkodás"). Helyette egy rövid i/n kérdés; „i" (vagy Enter) után
    AZONNAL, kommentár nélkül indul a sorolás."""
    while True:
        v = yield ctx.kerdez("Elindítsam az ábécét? (i vagy Enter = igen; utána "
                             "a SZÓKÖZ vagy az ENTER állítja meg)")
        if igen(v, True) is not False:       # üres/„i"/igen → indul; csak „n" vár
            break
        yield ctx.mond("Rendben, várok – szólj, ha kezdhetjük.")
    betu = yield ctx.abcstop(1000)
    return (betu or "a")


def jatek_orszagvaros(ctx):
    yield ctx.mond(
        "ORSZÁG, VÁROS, FIÚ, LÁNY! Ezt a játékot Mezei Géza álmodta meg, a "
        "bővített kategóriák ötlete pedig Kőrösmezey Anita, Wildcath érdeme – "
        "köszönjük! A gép másodpercenként sorolja az ábécét, te megállítod egy "
        "betűn, és arra a betűre mondasz szavakat. Amit a szótáramban ismerek, "
        "két pont; amit nem találok, de a jó betűvel kezdődik, azt elhiszem "
        "neked: egy pont. A legtöbb pont nyer!")

    custom = load_custom()

    v = yield ctx.kerdez("Hányan játszotok? (1-4)")
    n = szam(v, 1, 4) or 1
    nevek = []
    for i in range(n):
        nv = yield ctx.kerdez(f"A(z) {i + 1}. játékos neve? "
                              f"(Enter = Játékos {i + 1})")
        nevek.append((nv or "").strip() or f"Játékos {i + 1}")

    # klasszikus 4 vagy bővített kategóriák (Kőrösmezey Anita, Wildcath ötlete)
    aktiv_kulcsok = list(ALAP_KULCSOK)
    v = yield ctx.kerdez("Maradjunk a klasszikus 4 kategóriánál, vagy bővítsük "
                         "a lehetőségeket? (Enter = klasszikus, i = bővített)")
    if igen(v, False) is True:
        yield ctx.mond("Bővített mód! Kérdezem a plusz kategóriákat – i = benne "
                       "van, Enter vagy n = kimarad.")
        for kulcs in EXTRA_KULCSOK:
            vv = yield ctx.kerdez(f"{KATEGORIA_NEVEK[kulcs]} mehet? (i/n)")
            if igen(vv, False) is True:
                aktiv_kulcsok.append(kulcs)
        yield ctx.mond("A kategóriák: "
                       + ", ".join(KATEGORIA_NEVEK[k] for k in aktiv_kulcsok)
                       + ". A szótárt a Tanítás fülön bővítheted!")

    aktiv = [(_CIMKE[k], keszlet(k, custom)) for k in aktiv_kulcsok]
    max_kor = 2 * len(aktiv)

    v = yield ctx.kerdez("Hány kört játsszunk? (1-10, Enter = 3)")
    korok = szam(v, 1, 10) or 3
    pontok = [0] * n

    for kor in range(1, korok + 1):
        yield ctx.mond(f"--- {kor}. kör a {korok}-ből ---")
        for i in range(n):
            yield ctx.mond(f"{nevek[i]} következik!")
            betu = yield from _porget(ctx)
            norm = ekezet_nelkul(betu) or "a"      # elbíráláshoz: 'á' → 'a'
            nagy = betu.upper()
            yield ctx.mond(f"Megállt a(z) {nagy} betűn! Most jöhet {len(aktiv)} "
                           "szó.")
            korpont = 0
            for cimke, kesz in aktiv:
                valasz = yield ctx.kerdez(f"{nagy} betűvel mondj {cimke}:")
                allapot, pont = _ertekel(valasz, norm, kesz)
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
            elif korpont == max_kor:
                yield ctx.mond("Telitalálat – minden szó ült!")
            yield ctx.mond(f"{nevek[i]} ebben a körben {korpont} pontot "
                           f"szerzett, összesen {pontok[i]}.")

    sorrend = sorted(range(n), key=lambda i: pontok[i], reverse=True)
    yield ctx.mond("Vége a játéknak! Végeredmény:")
    for hely, i in enumerate(sorrend, 1):
        yield ctx.mond(f"{hely}. hely: {nevek[i]} – {pontok[i]} pont.")
    yield ctx.effekt("taps")                          # tapsvihar a győztesnek
    zaras = ("Köszönet az ötletért Mezei Gézának, a bővítés ötletéért pedig "
             "Kőrösmezey Anita, Wildcathnek!")
    if n > 1 and pontok[sorrend[0]] == pontok[sorrend[1]]:
        yield ctx.vege("Holtverseny az élen! Szép volt mindenkinek. " + zaras)
    else:
        yield ctx.vege(f"A győztes: {nevek[sorrend[0]]}! Gratulálok! " + zaras)
