"""Hangszín-szabályzó: NEVESÍTETT hangszínek + EGY erősség-csúszka.

⚠️ MIÉRT ÍGY. A forma Stolmár Barbival egyeztetve született (2026-09-21/23):
„ha a kombinált listamezőben kiválasztjuk a nekünk kellő hangszínt, pl egy
csúszkával lehetne a mértékén állítani". Vakon egy tíz-sávos grafikus
kiegyenlítő használhatatlan: tíz csúszka, mindegyiken egy szám, és semmi nem
mondja meg, mit HALLASZ tőle. Egy nyilazható lista megnevezett hangszínekkel
és EGY csúszka a mértékére: ez elmondható, megjegyezhető, és egy gombnyomással
visszavonható.

A szűrés az ffmpeg `-af` láncával, DEKÓDOLÁSKOR történik (nem a Pythonban),
tehát nem terheli a gépet és minden forrásra hat.

A sávok alakja: (középfrekvencia Hz, szélesség oktávban, alap-erősítés dB).
Az erősség-csúszka ezt a dB-t szorozza: 100% = a táblában lévő érték.
"""

PROFILOK = [
    ("eredeti", "Eredeti hang",
     "Semmilyen szűrés. Ezt hallod a lemezen.", []),
    ("beszed", "Beszéd – érthetőbb",
     "Hangoskönyvhöz, podcasthoz: kevesebb dübörgés, kiemelt beszédsáv.",
     [(120.0, 2.0, -4.0), (2500.0, 1.2, 5.0), (5000.0, 1.0, 2.0)]),
    ("basszus", "Basszus – erősebb mély",
     "Teltebb, dobosabb hang. Kis hangszórón és fülhallgatón segít a legtöbbet.",
     [(70.0, 1.0, 7.0), (160.0, 1.0, 3.0)]),
    ("magas", "Magas – csengőbb",
     "Levegősebb, tisztább felső hangok. Tompa felvételhez.",
     [(6000.0, 1.2, 4.0), (11000.0, 1.0, 5.0)]),
    ("meleg", "Meleg – lágyabb",
     "Kellemesebb, kevésbé éles hang. Hosszú hallgatáshoz, ha fáraszt a felső.",
     [(250.0, 1.0, 3.0), (3500.0, 1.5, -4.0)]),
    ("halk", "Halk hallgatás – kiegyenlített",
     "Éjszakára: a halk részeket felhozza, a hangosakat visszafogja, "
     "így nem kell a hangerőt állítgatni.",
     [(90.0, 1.0, 4.0), (3000.0, 1.2, 3.0)], "acompressor=ratio=4:attack=20"
     ":release=300:makeup=1.5"),
]

ALAP_PROFIL = "eredeti"
ALAP_EROSSEG = 100          # százalék


def _bejegyzes(azonosito: str):
    for p in PROFILOK:
        if p[0] == azonosito:
            return p
    return PROFILOK[0]


def nevek() -> list:
    """A listamezőbe való feliratok, a PROFILOK sorrendjében."""
    return [p[1] for p in PROFILOK]


def azonositok() -> list:
    return [p[0] for p in PROFILOK]


def nev(azonosito: str) -> str:
    return _bejegyzes(azonosito)[1]


def leiras(azonosito: str) -> str:
    return _bejegyzes(azonosito)[2]


def index(azonosito: str) -> int:
    for i, p in enumerate(PROFILOK):
        if p[0] == azonosito:
            return i
    return 0


def _szam(x: float) -> str:
    """dB/frekvencia szövegesen, pont tizedesjellel — az ffmpeg a rendszer
    tizedesvesszőjét NEM érti, a magyar Windows viszont azt adná."""
    return ("%.3f" % float(x)).rstrip("0").rstrip(".") or "0"


def szuro(azonosito: str, erosseg: int = ALAP_EROSSEG) -> str:
    """A profil ffmpeg `-af` szűrőlánca, vagy üres szöveg, ha nincs szűrés.

    `erosseg` 0 és 100 között: a tábla dB-értékeit szorozza. Nullánál tehát
    minden profil ugyanaz, mint az „Eredeti hang" — ez szándékos: a csúszka
    ALJA mindig a visszaút.

    ⚠️ A „Halk hallgatás" tömörítője (acompressor) NEM skálázódik a
    csúszkával, csak be- vagy kikapcsol vele: a tömörítés félig alkalmazva
    nem „félannyi", hanem másképp szól, és ezt vakon nem lehetne kihallani."""
    p = _bejegyzes(azonosito)
    arany = max(0, min(100, int(erosseg))) / 100.0
    if arany <= 0:
        return ""
    tagok = []
    emel = 0.0
    for freq, szelesseg, db in p[3]:
        g = db * arany
        if abs(g) < 0.05:
            continue
        emel = max(emel, g)
        tagok.append("equalizer=f=%s:width_type=o:w=%s:g=%s"
                     % (_szam(freq), _szam(szelesseg), _szam(g)))
    extra = p[4] if len(p) > 4 else ""
    if extra:
        tagok.append(extra)
    if tagok and emel > 0.5:
        # ⚠️ TORZÍTÁS-VÉDELEM. Egy +7 dB-es basszuskiemelés egy amúgy is
        # hangosra masterelt számon TÚLVEZÉRLI a jelet, és az nem „erősebb
        # mély", hanem recsegés. A limiter csak a csúcsokat fogja vissza;
        # halk felvételen semmit nem csinál. Enélkül a hangszínválasztás
        # néhány számnál rontana a hangon, és a felhasználó joggal hinné,
        # hogy elromlott a lejátszó.
        tagok.append("alimiter=limit=0.94:level=disabled")
    return ",".join(tagok)


def mondat(azonosito: str, erosseg: int) -> str:
    """Amit a program kimond a beállításról. Az „Eredeti hang" és a nulla
    erősség KÜLÖN mondatot kap: ott a százalék félrevezető lenne."""
    p = _bejegyzes(azonosito)
    if not p[3] or int(erosseg) <= 0:
        return "Eredeti hang, szűrés nélkül."
    return "%s, %d százalék." % (p[1], max(0, min(100, int(erosseg))))
