# -*- coding: utf-8 -*-
"""Az országút harcosa – teljes elágazó kalandkönyv.

Ian Livingstone Freeway Fighter (magyarul: Az országút harcosa) című
lapozgatós kalandkönyvének hű újraértelmezése. A homelabos BASIC-változatot
Dr. Földi János írta; ez a modul a játék viselkedését (a helyszíneket, a
döntéseket, a szerencse- és ügyességpróbákat, a jármű-tűzharcot és a
kézitusát, valamint a statisztikákat) írja újra tisztán, felolvasható
magyar szöveggel, akadálymentesen. A gépi kódot NEM másoltuk; a
játékmenetet a portolási sablon szellemében implementáltuk újra.

A motor adatvezérelt: a helyszínek egy csomópont-táblában élnek
(overlay, sor) kulccsal, ahogy az eredeti négy overlayben. Egy értelmező
lépteti a történetet, a döntéseknél a játékos számot választ.
"""
import random

# ---- Fighting Fantasy statisztikák és erőforrások alapértékei -------------
# U  = ügyesség, E = életerő, S = szerencse, T = jármű-ügyesség, P = páncél
# UU/EE/SS/TT/PP = a hozzájuk tartozó maximumok (regeneráció felső határa)
# VV = vasszög, OO = olajszóró, GG = gyógyszer, HH = hitel, PK = pótkerék,
# BT = benzinkanna; a többi mező jelző (talált tárgy / megtett esemény).


def _uj_allas():
    g = {}
    g["UU"] = random.randint(1, 6) + 7
    g["EE"] = random.randint(1, 12) + 25
    g["SS"] = random.randint(1, 6) + 7
    g["TT"] = random.randint(1, 6) + 7
    g["PP"] = random.randint(1, 12) + 25
    g["U"], g["E"], g["S"], g["T"], g["P"] = (
        g["UU"], g["EE"], g["SS"], g["TT"], g["PP"])
    g["VV"], g["OO"], g["GG"], g["HH"], g["PK"], g["BT"] = 3, 2, 10, 200, 2, 0
    # jelzők (talált tárgyak, megtett események)
    for jel in ("GC", "FV", "BS", "JS", "SB", "SH", "DV", "LC", "BC", "BK",
                "TG", "GM", "PH", "KG", "DK", "GM"):
        g[jel] = 0
    return g


def _d(n):
    return random.randint(1, n)


def _statsor(g):
    return (f"[Életerő {max(0, g['E'])}, ügyesség {g['U']}, "
            f"szerencse {max(0, g['S'])}, páncél {max(0, g['P'])}, "
            f"gyógyszer {g['GG']}, hitel {g['HH']}]")


# ======================================================================
# Harcrendszerek
# ======================================================================
def _tuzharc(ctx, g, poolvar, skillvar, soff, au, ae, bu, be):
    """Jármű-tűzharc (az eredeti 6200-as rutin szellemében).

    A ``poolvar`` (páncél vagy életerő) a te sérülésmérőd, a ``skillvar``
    (jármű-ügyesség vagy ügyesség) a lövési képességed. Két ellenfél lehet
    (A és B); minden körben megcélzod az egyiket, a másik visszalő.
    """
    pool = g[poolvar]
    skill = g[skillvar] + soff
    while (ae > 0 or be > 0) and pool > 0:
        # célválasztás
        if ae > 0 and be > 0:
            v = yield ctx.kerdez("Melyikre lősz? (1 = az első, 2 a második)")
            cel = "A" if str(v).strip() == "1" else (
                "B" if str(v).strip() == "2" else None)
            if cel is None:
                continue
        elif ae > 0:
            cel = "A"
        else:
            cel = "B"
        au_c = au if cel == "A" else bu
        f = _d(12) + 1 + skill
        a = _d(12) + 1 + au_c
        if a == f:
            yield ctx.mond("Egyikőtök sem talált.")
        elif f > a:
            kar = _d(6)
            if cel == "A":
                ae -= kar
            else:
                be -= kar
            if (cel == "A" and ae < 1) or (cel == "B" and be < 1):
                yield ctx.mond("Kilőtted az egyik támadót!")
            else:
                yield ctx.mond("Eltaláltad az ellenfeledet.")
        else:
            pool -= _d(6)
            skill = max(0, skill - 1)
            yield ctx.mond("Az ellenfél beléd talált!")
            if pool < 1:
                break
        # a másik, még élő ellenfél visszalő
        masik_u = bu if (be > 0 and cel == "A") else (
            au if (ae > 0 and cel == "B") else None)
        masik_el = (be > 0 and cel == "A") or (ae > 0 and cel == "B")
        if masik_el and pool > 0:
            b = _d(12) + 1 + masik_u
            if b <= f:
                yield ctx.mond("A másik mellélőtt.")
            else:
                pool -= _d(6)
                skill = max(0, skill - 1)
                yield ctx.mond("A másik beléd lőtt!")
    g[poolvar] = pool
    return pool


def _kezitusa(ctx, g, poolvar, skillvar, soff, au, ae, le):
    """Kézitusa / párbaj (a 6400-as rutin szellemében).

    A ``poolvar`` a te sérülésmérőd (életerő vagy páncél), az ``ae`` az
    ellenfél életereje, ``le`` az egy találatra eső sérülés.
    """
    xx = g[poolvar]
    yy = ae
    skill = g[skillvar] + soff
    while xx > 0 and yy > 0:
        a = _d(12) + 1 + au
        f = _d(12) + 1 + skill
        if a == f:
            yield ctx.mond("Egyikőtök sem talált.")
        elif f > a:
            yy -= le
            if yy < 1:
                yield ctx.mond("Leterítetted az ellenfeledet!")
            else:
                yield ctx.mond("Megsebesítetted az ellenfeledet.")
        else:
            xx -= le
            if xx < 1:
                yield ctx.mond("Az ellenfél halálos csapást mért rád.")
            else:
                yield ctx.mond("Az ellenfél megsebzett.")
    g[poolvar] = xx
    return xx, yy


# ======================================================================
# Egyedi, tiszta kocka-elágazások (narráció előtte szövegként megy ki)
# ======================================================================
def _sp_race(g):
    # sebességi verseny Leonárd ellen: A = Leonárd, B = te
    a, b = 0, 1
    while True:
        a += _d(6)
        if a >= 24:
            return (3, 1100)   # a Jaguár győz -> vesztettél
        b += _d(6)
        if b >= 24:
            return (0, 2700)   # te győztél


def _sp_duel4560(g):
    # régi párbajpisztollyal, szabályos párbaj
    a = _d(12) + 10
    f = _d(12) + 1 + g["U"]
    if a == f or f > a:
        return (2, 400)
    g["E"] -= _d(6)
    if g["E"] < 1:
        return ("end", "Meghaltál.")
    return (2, 400)


_SPECIAL = {"race": _sp_race, "duel4560": _sp_duel4560}


# ======================================================================
# Csomópont-tábla.  Kulcs: (overlay, sor).  Érték: műveletek listája.
# Műveletek (első elem szerint):
#   str                         -> elbeszélés (mond)
#   ("+", var, n)               -> g[var] += n
#   ("cap", var, capvar)        -> ha g[var] > g[capvar]: egyenlő
#   ("lose", var, lo, hi)       -> g[var] -= randint(lo,hi)
#   ("die", var, szoveg)        -> ha g[var] < 1: vége (szoveg)
#   ("g", ov, ln)               -> ugrás
#   ("end", szoveg)             -> a kaland vége
#   ("luck", (ov,ln)_szerencse, (ov,ln)_balszerencse)
#   ("skill_gt", (ov,ln)_ha_D>U, (ov,ln)_egyébként)
#   ("armor", (ov,ln)_túlélted, szoveg)   -> P -= d12
#   ("chance", n, kszb, (ov,ln)_ha_D<kszb, (ov,ln)_egyébként)
#   ("chance_gt", n, kszb, (ov,ln)_ha_D>kszb, (ov,ln)_egyébként)
#   ("af", amin, amax, fdie, (ov,ln)_ha_A>F, (ov,ln)_egyébként)
#   ("call", kulcs)             -> _SPECIAL[kulcs](g) -> következő cél
#   ("if", var, cmp, val, [műveletek])   -> feltételes blokk
#   ("ask", prompt, [(cimke, (ov,ln), felt), ...])
#   ("cmbV", poolvar, skillvar, soff, au, ae, bu, be, (win), death)
#   ("cmbP", poolvar, skillvar, soff, au, ae, le, (win), death)
#        death: ("end", szoveg) VAGY (ov, ln)
# ======================================================================

N = {}

# ------------------------------- OVERLAY 0 -----------------------------
N[(0, 50)] = [
    "A falakon kívül mindent ellep a gyom, az utak mentén romok és autóroncsok.",
    "Tizenöt kilométerre Új Reménytől megállsz egy elhagyatott városban, és kikapcsolod a motort.",
    "Csend van, csak az ebek vonyítanak.",
    "Tovább akarnál indulni, amikor lövés dördül.",
    ("ask", "Mit teszel?", [
        ("Továbbmész", (0, 1700), None),
        ("Kiszállsz körülnézni", (1, 1300), None)]),
]
N[(0, 100)] = [
    "A kocsidhoz rohansz, és kígyómarás elleni szérumot adsz be magadnak.",
    ("+", "GG", -1), ("+", "U", -1), ("+", "E", -2),
    ("die", "E", "Már késő. Belehalsz a kígyómarásba."),
    "Elgyengültél.",
    "Visszamész a felfordult Interceptorhoz, és lelövöd a kígyót.",
    "A kesztyűtartóban talált gumicsövet magaddal viszed.",
    ("+", "GC", 1),
    "Tovább hajtasz.",
    ("g", 0, 650),
]
N[(0, 150)] = [
    "Tövig nyomod a gázt, és megelőzöd a Fordot.",
    "Az hátulról nekedrontva öklel.",
    ("luck", (3, 2700), (2, 2350)),
]
N[(0, 200)] = [
    "Leállítod az Interceptort. Megvacsorázol és elalszol.",
    "Reggel kipihenten ébredsz.",
    ("+", "E", 2), ("cap", "E", "EE"),
    "Továbbhajtasz dél felé.",
    ("g", 2, 2700),
]
N[(0, 250)] = [
    "A hotelt zárva találod.",
    ("ask", "Mit teszel?", [
        ("Feltöröd a lakatot", (2, 2050), None),
        ("A benzinszállítóban alszol", (2, 900), None)]),
]
N[(0, 300)] = [
    "Mindkét motoros pisztollyal van felfegyverkezve.",
    "Tűzharc alakul ki köztetek.",
    ("cmbV", "E", "U", 0, 6, 15, 7, 15, (3, 350), ("end", "Meghaltál.")),
]
N[(0, 350)] = [
    "A lány rábeszél, hogy keletre, a sivatagon át menjetek.",
    "Amikor besötétedett, a zsebébe nyúl, hogy kivegyen valamit, ami ébren tart.",
    ("luck", (3, 950), (1, 1800)),
]
N[(0, 400)] = [
    "Kicselezed a Fordot, és elzúgsz mellette.",
    ("g", 3, 2000),
]
N[(0, 450)] = [
    "Végzetes hiba volt, hogy nem törődtél a figyelmeztetéssel.",
    ("end", "A barikád mögötti férfi lézerpuskával végez veled."),
]
N[(0, 500)] = [
    "Elhagyott járművek. Kutatni kezdesz.",
    "Az egyik autóban találsz egy feszítővasat, és felnyitsz vele néhány csomagtartót.",
    "Egyszer csak megrémülsz a gondolattól, hogy őrizetlenül hagytad az Interceptort!",
    ("+", "FV", 1),
    ("ask", "Mit teszel?", [
        ("Visszarohansz", (2, 3200), None),
        ("Tovább kutatsz", (3, 2950), None)]),
]
N[(0, 550)] = [
    "A légikalózok elveszik a vasszögeidet és az olajszóróidat.",
    "Elengednek, mert jó a kedvük, de figyelmeztetnek: legközelebb felrobbantják az Interceptort.",
    "Magadban átkozódva elhajtasz keletnek.",
    ("+", "VV", -99), ("+", "OO", -99), ("+", "S", -2),
    ("g", 2, 800),
]
N[(0, 600)] = [
    "Tudod, hogy reménytelen, de felveszed a harcot.",
    "Hajpántos, ápolatlan férfit látsz. Tüzelsz.",
    ("g", 2, 1355),
]
N[(0, 650)] = [
    "Látod, hogy egy oldalkocsis motor felzárkózott mögéd.",
    "Az utas előtt géppuska van, és tüzet nyit rád.",
    ("+", "P", -1),
    ("if", "VV", "==", 0, [("if", "OO", "==", 0, [
        "Nincs mivel védekezned – kénytelen vagy harcolni.",
        ("g", 2, 4100)])]),
    ("ask", "Mit teszel?", [
        ("Viszonzod a tüzet", (2, 4100), None),
        ("Szögeket szórsz", (1, 1350), ("VV", ">", 0)),
        ("Olajat fecskendezel magad mögé", (3, 3050), ("OO", ">", 0))]),
]
N[(0, 700)] = [
    "Az ágy nagyon kényelmes volt, nyugodtan és frissen ébredsz.",
    ("+", "E", 3), ("cap", "E", "EE"),
    "Az ajtón kilépve látod, hogy egy férfi benzint locsol az Interceptorra.",
    "Morogva hátralép, és egy doboz gyufát vesz elő.",
    ("ask", "Mit teszel?", [
        ("Rákiáltasz", (2, 3000), None),
        ("Odarohansz, hogy kiüsd a kezéből", (2, 850), None)]),
]
N[(0, 750)] = [
    "A férfi kikapcsolja a hegesztőt.",
    "Kétszáz hitelért megjavítom a maga kocsiját is – mondja.",
    ("if", "HH", "<", 200, [
        "Nincs annyi pénzed. Tovább mész keletnek.",
        ("g", 2, 2950)]),
    ("ask", "Mit teszel?", [
        ("Megjavíttatod", (1, 3450), None),
        ("Tovább indulsz keletnek", (1, 2950), None)]),
]
N[(0, 800)] = [
    "Reggel kipihenten, felfrissülve ébredsz.",
    ("+", "E", 2), ("cap", "E", "EE"),
    ("ask", "Mit teszel?", [
        ("Átkutatod a kávézót", (0, 1300), None),
        ("Rögtön útnak indulsz", (2, 2700), None)]),
]
N[(0, 850)] = [
    "Keményen nyomod a gázt, hogy elmenekülj a motorosok elől.",
    "De az aknarobbanás kormányozhatatlanná teszi az Interceptort.",
    ("+", "P", -2),
    "Kiszállva látod, hogy az egyik kereked is leesett.",
    "Ekkor a motorosok feléd indulnak. Visszaülsz, hogy géppuskatűzzel fogadd őket.",
    ("cmbV", "P", "T", -2, 6, 9, 6, 9, (1, 150), ("end", "Az Interceptor megsemmisült.")),
]
N[(0, 900)] = [
    "A polgárok megtörtek. Hiába mondod nekik, hogy harcoljanak.",
    "Ellenállás nélkül adják meg magukat.",
    "Rájössz, hogy a küldetésed kudarcba fulladt.",
    ("end", "A Pusztulás Kutyái bosszút álltak."),
]
N[(0, 950)] = [
    "Gyorsan kereket cserélsz, és hamarosan úton vagy kelet felé.",
    ("g", 1, 950),
]
N[(0, 1000)] = [
    "A Ford nem tud előzni.",
    ("+", "S", 1), ("cap", "S", "SS"),
    "Fél kocsihosszal megnyerted a bliccversenyt!",
    ("g", 1, 550),
]
N[(0, 1050)] = [
    "Rendbe hozod a kocsidat, átnézed a motort, megerősíted a kilazult hátsó kereket.",
    ("+", "P", 1), ("cap", "P", "PP"),
    "Majd elindulsz délnek.",
    ("g", 2, 1050),
]
N[(0, 1100)] = [
    "Útelágazáshoz érsz.",
    ("ask", "Merre mész?", [
        ("Délnek fordulsz", (3, 550), None),
        ("Tovább mész kelet felé", (2, 150), None)]),
]
N[(0, 1150)] = [
    "Egy hídhoz közeledsz, amin egy ember áll, és egy nagy követ egyensúlyoz.",
    "Amikor odaérsz, kuncogva elengedi. A kő az Interceptor elé esik.",
    ("skill_gt", (3, 2100), (1, 1850)),
]
N[(0, 1200)] = [
    "Egy kapuhoz érsz. Az agyontetovált őr megkérdezi, melyik bandához tartozol.",
    "Azt mondod, a Fekete Patkányokhoz.",
    "Nem ismeri őket, de mondja, hogy menj tovább, és vegyél részt a versenyen.",
    ("ask", "Mit teszel?", [
        ("Bemész", (2, 5000), None),
        ("Visszamész az útra", (0, 2950), None)]),
]
N[(0, 1250)] = [
    "A robbanástól elveszted az eszméletedet.",
    ("g", 0, 5000),
]
N[(0, 1300)] = [
    "Feltöröd a kávézót, és látod, hogy kifosztották.",
    "Mivel semmit sem találsz, ami érdekelne, kimész.",
    "Egy fehér ruhás férfit látsz, aki benzint locsol az Interceptorra, majd meggyújt egy szál gyufát.",
    ("ask", "Mit teszel?", [
        ("Rákiáltasz", (2, 3000), None),
        ("Odarohansz, hogy kiüsd a kezéből a gyufát", (2, 850), None)]),
]
N[(0, 1350)] = [
    "Fékezel és megállsz. A Ford kikerül, majd gyorsan eltávolodik.",
    "Mivel nem használhatod az előretüzelő fegyvereidet, öklelni akarod a Fordot.",
    ("g", 1, 1950),
]
N[(0, 1400)] = [
    "Péter a műhelyben megvizsgálja az Interceptort.",
    "Ahhoz, hogy jobban gyorsuljon, át kellene alakítani a motort – mondja.",
    "Ennek száz hitel és két csomag gyógyszer az ára.",
    ("if", "HH", "<", 100, [
        "Ezt nem engedheted meg magadnak. Tovább indulsz délnek.",
        ("g", 0, 4400)]),
    ("if", "GG", "<", 2, [
        "Ezt nem engedheted meg magadnak. Tovább indulsz délnek.",
        ("g", 0, 4400)]),
    ("ask", "Mit teszel?", [
        ("Átalakíttatod", (1, 2050), None),
        ("Tovább mész", (0, 4400), None)]),
]
N[(0, 1450)] = [
    "Egy eltévedt golyó vállon talál.",
    ("lose", "E", 1, 6),
    ("die", "E", "A sebedbe belehaltál."),
    "Bekötöd a sebedet, visszamész az Interceptorhoz, és továbbindulsz.",
    ("g", 0, 1100),
]
N[(0, 1500)] = [
    "A nyílvessző vállon talál, és lecsúszol a létráról.",
    ("lose", "E", 1, 6),
    ("die", "E", "A sebedbe belehaltál."),
    "Sebeddel nem törődve felrohansz a létrán, és rárontasz az ellenségre.",
    ("af", 8, 13, 6, (2, 1300), (0, 3700)),
]
N[(0, 1550)] = [
    "A ház könnyű célpont, telibe találod.",
    "Amíg tart a robbanás hatása, te kijavítod a kocsidon keletkezett lyukat.",
    "Utána elindulsz a romokhoz. Odaérve leállítod a motort, és meghallod, hogy valaki segítségért kiált.",
    ("ask", "Mit teszel?", [
        ("Kiszállsz, hogy segíts", (2, 3100), None),
        ("Továbbhajtasz", (3, 2650), None)]),
]
N[(0, 1600)] = [
    "Együtt indultok el a Pusztulás Kutyáinak tábora felé.",
    "A banda sátrakban él egy hegytetőn, ott parkolnak a kocsijaik is.",
    "Az egyik őr a közeletekben halad el. A lány véletlenül megrúg egy kavicsot, ami legurul.",
    ("luck", (0, 3800), (1, 3000)),
]
N[(0, 1650)] = [
    "Sokáig tart, mire kiásod a kocsidat az árokból.",
    ("+", "E", -1),
    ("die", "E", "A kimerültségtől meghalsz."),
    "Aztán továbbhajtasz délnek.",
    ("g", 0, 2350),
]
N[(0, 1700)] = [
    "Kiérsz a városból. Egy elágazásnál benzinkút és garázs.",
    "Megállsz. Fiatal lány jön ki az irodából, és rád mosolyog.",
    ("ask", "Mit teszel?", [
        ("Továbbmész", (3, 100), None),
        ("Szóba állsz vele", (1, 3350), None)]),
]
N[(0, 1750)] = [
    "A Forddal fej fej mellett száguldotok a híd felé.",
    ("af", 9, 14, 6, (0, 2550), (3, 3950)),
]
N[(0, 1800)] = [
    "A tőr fájdalmasan beléd fúródik.",
    ("lose", "E", 1, 6),
    ("die", "E", "Meghaltál."),
    ("g", 3, 3400),
]
N[(0, 1850)] = [
    "Hatalmas szikla zuhan az Interceptorra.",
    ("armor", (2, 3050), "A karosszéria összeroppant."),
]
N[(0, 1900)] = [
    "Kiveszel egy gyógyszercsomagot, kitisztítod a sebet, majd bekötöd.",
    ("+", "GG", -1),
    "Éppen be akarsz szállni az Interceptorba, amikor egy veszett eb rád támad.",
    ("ask", "Mit teszel?", [
        ("Megpróbálod lelőni", (1, 3800), None),
        ("Késsel küzdesz meg vele", (3, 3700), None)]),
]
N[(0, 1950)] = [
    "Gyorsan előrántod a késedet, és a vigyorgó férfi hasába vágod.",
    "Ő összeesik, de haldokolva még rád lő.",
    ("luck", (1, 3550), (0, 1450)),
]
N[(0, 2000)] = [
    "Mire a tartálykocsihoz érsz, a Pusztulás Kutyája már elindította a motort.",
    "Felugranál, de az a pisztolyáért nyúl.",
    ("if", "U", "<", 6, [("g", 2, 4800)]),
    ("g", 0, 4050),
]
N[(0, 2050)] = [
    "A páncélkocsi vezetője résen van, és kikerüli a szögeket.",
    ("ask", "Mit teszel?", [
        ("Olajat fecskendezel elé", (1, 3250), None),
        ("Szembefordulsz vele", (0, 3850), None)]),
]
N[(0, 2100)] = [
    "A sötétben a fényszóróid fényénél haladsz tovább. Nagyon elfáradtál.",
    ("skill_gt", (1, 4300), (1, 3050)),
]
N[(0, 2150)] = [
    "Mélyet lélegzel, amikor az Interceptor áthalad a gránát fölött.",
    ("luck", (1, 3750), (2, 50)),
]
N[(0, 2200)] = [
    "Hazudsz! Nem úgy nézel ki, mint aki valamelyik bandához tartozik.",
    "Halljuk, mit mondanak a többiek – int a társai felé a géppuskával.",
    ("if", "BS", "==", 1, [("g", 2, 3650)]),
    ("g", 2, 700),
]
N[(0, 2250)] = [
    "Nyílt úton haladsz, és nem veszed észre a leszórt vasszögeket.",
    "A kereked kidurran, és alig bírod tartani a kormányt.",
    ("luck", (3, 200), (0, 3000)),
]
N[(0, 2300)] = [
    "A benzinóra mutatója üres tankot jelez.",
    ("if", "BT", ">", 0, [("g", 3, 500)]),
    ("g", 3, 3200),
]
N[(0, 2350)] = [
    "Minél délebbre jutsz, egyre melegebb lesz, és egyre sivatagosabbá válik a táj.",
    "Útelágazáshoz érsz.",
    ("ask", "Merre mész?", [
        ("Jobbra fordulsz, nyugatnak", (1, 850), None),
        ("Továbbhaladsz délnek", (0, 1150), None)]),
]
N[(0, 2400)] = [
    "Késedet markolva lekuporodsz. Az orgyilkos üvöltve rád veti magát.",
    ("cmbP", "E", "U", 0, 7, 10, 2, (1, 1900), (0, 5000)),
]
N[(0, 2450)] = [
    "Egy görög harci szekérre emlékeztető teherautó parkol előtted, még vágóélek is vannak a kerekein.",
    "Duplacsövű géppisztollyal egy félmeztelen férfi áll a platón, és int a vezetőnek, hogy induljon feléd.",
    ("cmbV", "P", "T", 0, 9, 15, 0, 0, (0, 4550), ("end", "Legyőzött.")),
]
N[(0, 2500)] = [
    "A férfit a földre rántod, de késő.",
    "Az Interceptort elborítják a lángok.",
    ("end", "Az őrült véget vetett a küldetésednek."),
]
N[(0, 2550)] = [
    "Néhány méterre a híd előtt nem bírod tovább. Fékezel, és hagyod, hogy a Ford megelőzzön.",
    "Előttetek a cél, és rájössz, hogy elvesztetted a versenyt.",
    ("+", "S", -1),
    ("g", 2, 1600),
]
N[(0, 2600)] = [
    "Az egyik motort kilövöd, de a vezetője még kilövi az első kerekedet.",
    "Alig bírod az úton tartani az Interceptort. A másik motoros párbajra hív ki.",
    ("ask", "Mit teszel?", [
        ("Kiállsz", (1, 3200), None),
        ("A kabinban maradsz", (1, 4500), None)]),
]
N[(0, 2650)] = [
    "A gázra lépsz, és támadóid felé kormányzod az Interceptort.",
    "Azok felugranak a motorjaikra, és elszáguldanak.",
    ("ask", "Mit teszel?", [
        ("Üldözöd őket", (0, 3900), None),
        ("Visszafordulsz az útra", (0, 2250), None)]),
]
N[(0, 2700)] = [
    "Nem állsz meg ünnepelni a győzelmedet, nyomban továbbindulsz.",
    "Egy teherautó mellett mész el, amely nemrég parkolhatott ide.",
    ("ask", "Mit teszel?", [
        ("Megállsz átvizsgálni", (1, 200), None),
        ("Továbbmész", (1, 900), None)]),
]
N[(0, 2750)] = [
    "Belépsz a kávézóba, és látod, hogy kirabolták.",
    "Saját elemózsiádból eszel valamit. Amikor besötétedik, lefekszel az ágyra.",
    ("chance_gt", 6, 3, (0, 700), (1, 500)),
]
N[(0, 2800)] = [
    "Az őrt leütöd, és saját övével összekötözöd.",
    "Gyorsan elkúszol a kerítés felé.",
    ("g", 1, 4900),
]
N[(0, 2850)] = [
    "Pisztollyal a kézben utasítod a férfit, hogy dobja el a puskáját.",
    "Aztán elmondod, hogy nem te ölted meg a családját.",
    "Csak hazudtad, hogy országúti harcos vagy, mert Új Remény hollétét titokban akarod tartani.",
    "Kiderül, hogy ő éppen oda tart. Elmagyarázod, hogyan juthat el a városba.",
    "Ő figyelmeztet, hogy meg ne állj az útelágazásnál lévő garázsnál, mert ott mindenkit kirabolnak.",
    "Elbúcsúztok, és továbbindulsz.",
    ("g", 0, 1700),
]
N[(0, 2855)] = [
    "Csak hazudtad, hogy országúti harcos vagy, mert Új Remény hollétét titokban akarod tartani.",
    "Kiderül, hogy ő éppen oda tart. Elmagyarázod, hogyan juthat el a városba.",
    "Ő figyelmeztet, hogy meg ne állj az útelágazásnál lévő garázsnál, mert ott mindenkit kirabolnak.",
    "Elbúcsúztok, és továbbindulsz.",
    ("g", 0, 1700),
]
N[(0, 2860)] = [
    "Kiderül, hogy ő éppen oda tart. Elmagyarázod, hogyan juthat el a városba.",
    "Elbúcsúztok, és továbbindulsz.",
    ("g", 0, 1700),
]
N[(0, 2710)] = [
    "Egy teherautó mellett mész el, amely nemrég parkolhatott ide.",
    ("ask", "Mit teszel?", [
        ("Megállsz átvizsgálni", (1, 200), None),
        ("Továbbmész", (1, 900), None)]),
]
N[(0, 2900)] = [
    "A lakókocsiban egy húskonzervet és egy kézigránátot találsz.",
    "A gránátot zsebre vágod, a konzervet megeszed.",
    ("+", "KG", 1), ("+", "E", 2), ("cap", "E", "EE"),
    "Visszamész az Interceptorhoz, és elindulsz délnek.",
    ("g", 1, 2500),
]
N[(0, 2950)] = [
    "Elhajtasz. A férfi egy kézigránátot dob utánad.",
    ("luck", (0, 3650), (1, 1050)),
]
N[(0, 3000)] = [
    "Mindkét hátsó kereked kidurrant, és farolva megállsz.",
    "Egy férfi benzinbombát dob az Interceptorra.",
    ("armor", (1, 1750), "Az Interceptor megsemmisült."),
]
N[(0, 3050)] = [
    "Nyugodtan haladsz keletnek, amíg egy útelágazáshoz érsz.",
    "Itt kell jobbra fordulnod az olajfinomítóhoz.",
    ("g", 2, 3600),
]
N[(0, 3100)] = [
    "Sikerül úrrá lenned az Interceptoron, és kikerülni a roncsot.",
    ("g", 1, 2550),
]
N[(0, 3150)] = [
    "Szögeket szórsz az útra, de a Ford kikerüli.",
    ("+", "VV", -1),
    "A fehér háznál ráfordulsz a célegyenesre. A Ford utolér, és öklelni kezd.",
    ("cmbP", "P", "T", 0, 8, 16, 2, (3, 1700), ("end", "Az Interceptor ezt már nem bírta.")),
]
N[(0, 3155)] = [
    "A fehér háznál ráfordulsz a célegyenesre. A Ford utolér, és öklelni kezd.",
    ("cmbP", "P", "T", 0, 8, 16, 2, (3, 1700), ("end", "Az Interceptor ezt már nem bírta.")),
]
N[(0, 3200)] = [
    "A bandita ruhájában semmit nem találsz.",
    "Megnézed, hogy a kerekeid javíthatók-e.",
    ("luck", (3, 650), (2, 2100)),
]
N[(0, 3250)] = [
    "Egy golyó eltalált.",
    ("+", "E", -2),
    ("die", "E", "Meghaltál."),
    "Az Interceptorral elmenekülsz.",
    ("g", 2, 350),
]
N[(0, 3300)] = [
    "Egy nem teljesen lecsukott hídhoz érsz.",
    ("ask", "Mit teszel?", [
        ("Átugratsz", (2, 3500), None),
        ("Visszafordulsz", (1, 2950), None)]),
]
N[(0, 3350)] = [
    "A két jármű elzúg egymás mellett, aztán a furgon oldalt kanyarodik, hogy nekivágódjon az Interceptornak.",
    "Elrántod a kormányt, hogy kikerüld.",
    ("skill_gt", (2, 2400), (1, 5000)),
]
N[(0, 3400)] = [
    ("g", 2, 2700),
]
N[(0, 3450)] = [
    "Legyőzted a Pusztulás Kutyáit, és jókedvűen elindulsz dél felé.",
    ("g", 0, 4500),
]
N[(0, 3500)] = [
    "A kerekek lecsapódnak a híd túloldalán, és továbbszáguldasz.",
    "Előtted egy felborult teherautó.",
    ("skill_gt", (1, 1650), (0, 3100)),
]
N[(0, 3550)] = [
    "Száguldasz, amikor sziklák zuhannak eléd.",
    ("luck", (1, 3600), (0, 1850)),
]
N[(0, 3600)] = [
    "Az ajtó egy nyílpuskát hoz működésbe, és a nyíl beléd áll.",
    ("lose", "E", 1, 6),
    ("die", "E", "Meghaltál."),
    ("g", 2, 1650),
]
N[(0, 3650)] = [
    "Kilősz a kocsiddal, és megmenekülsz a gránáttól.",
    ("ask", "Mit teszel?", [
        ("Visszamész a főútra", (2, 350), None),
        ("Részt veszel a bliccversenyen", (3, 1500), None)]),
]
N[(0, 3700)] = [
    "Támadódat lelököd a vontatóról.",
    "Aztán egész nap hajtasz, és a benzinszállítóval estére eléred Új Remény falait.",
    ("if", "PH", ">", 0, [("g", 2, 3750)]),
    ("g", 3, 4000),
]
N[(0, 3715)] = [
    "Egész nap hajtasz, és a benzinszállítóval estére eléred Új Remény falait.",
    ("if", "PH", ">", 0, [("g", 2, 3750)]),
    ("g", 3, 4000),
]
N[(0, 3750)] = [
    ("+", "S", -1),
    "Elindulsz az autópálya felé.",
    ("g", 1, 3350),
]
N[(0, 3800)] = [
    "Az őr nem figyel fel a zajra.",
    ("g", 1, 4900),
]
N[(0, 3850)] = [
    "A kocsid kifarol.",
    ("luck", (2, 4500), (3, 2600)),
]
N[(0, 3900)] = [
    "A motorosok eltűnnek Sziklaváros házai között.",
    "Egy közeli farmházból lőnek.",
    ("ask", "Mit teszel?", [
        ("Szétlövöd a házat", (1, 4950), None),
        ("Tovább mész", (3, 3850), None),
        ("Visszatérsz a főútra", (0, 2250), None)]),
]
N[(0, 3950)] = [
    "A motorodnak nincs baja.",
    ("ask", "Mit teszel?", [
        ("Elhajtasz", (2, 4050), None),
        ("Megállsz", (1, 2500), None)]),
]
N[(0, 4000)] = [
    "A Ford leelőz, és előtted ér a célba.",
    ("+", "S", -1),
    ("g", 2, 1600),
]
N[(0, 4050)] = [
    "A fickót kirántod a kocsiból, és kényszeríted, hogy állítsa le a barátait.",
    "A Pusztulás Kutyái visszavonulnak a sivatagba.",
    "Te útnak indulsz a benzinszállítóval. Este egy motelhoz érsz.",
    ("ask", "Mit teszel?", [
        ("A kabinban alszol", (2, 900), None),
        ("Bemész a motelbe", (3, 1750), None)]),
]
N[(0, 4100)] = [
    ("luck", (0, 1950), (2, 2200)),
]
N[(0, 4150)] = [
    "Az Interceptorból tüzelsz a légikalózokra.",
    ("cmbV", "P", "T", -2, 8, 11, 0, 0, (3, 250), ("end", "Meghaltál.")),
]
N[(0, 4200)] = [
    "Álmodban hozzáérsz egy mérges pókhoz. Az megcsíp.",
    ("lose", "E", 1, 6),
    ("die", "E", "A csípés halálos."),
    ("g", 2, 2900),
]
N[(0, 4250)] = [
    "Átvágod a drótot. A kocsikra bombát tesztek.",
    "Elszaladtok. A bombák felrobbannak egy kivételével.",
    "A megmaradt kocsi üldözőbe vesz.",
    ("if", "E", "<", 10, [("g", 3, 1300)]),
    ("g", 1, 350),
]
N[(0, 4253)] = [
    "A kocsikra bombát tesztek. Elszaladtok; a bombák egy kivételével felrobbannak.",
    "A megmaradt kocsi üldözőbe vesz.",
    ("if", "E", "<", 10, [("g", 3, 1300)]),
    ("g", 1, 350),
]
N[(0, 4300)] = [
    "Az idegen lő, és eltalál. Összecsuklasz.",
    ("lose", "E", 3, 8),
    ("die", "E", "Meghaltál."),
    "A férfi magadra hagy.",
    ("ask", "Mit teszel?", [
        ("Azonnal bekötöd a sebed", (0, 1900), None),
        ("Bemászol a kocsidba", (2, 2800), None)]),
]
N[(0, 4350)] = [
    "A férfi elugrik az ütés elől, majd fegyverével tarkón vág.",
    "Elzuhansz.",
    ("g", 0, 5000),
]
N[(0, 4400)] = [
    "A sivatag határán egy keletre menő utat látsz.",
    ("ask", "Mit teszel?", [
        ("Ráfordulsz", (1, 3850), None),
        ("Tovább mész", (2, 3550), None)]),
]
N[(0, 4450)] = [
    "Továbbindulsz.",
    ("g", 0, 1700),
]
N[(0, 4500)] = [
    "A lánnyal eléritek az olajfinomítót.",
    "Az ottaniak hősként kezelnek. Ezen az éjszakán jól alszol.",
    ("+", "U", 1), ("cap", "U", "UU"), ("+", "E", 4), ("cap", "E", "EE"),
    "Reggel a Pusztulás Kutyái megtámadják a finomítót, és felrobbantják a kaput.",
    ("skill_gt", (0, 900), (1, 2350)),
]
N[(0, 4550)] = [
    "Dél felé száguldasz, bekapcsolod a rádiót. Elágazáshoz érsz.",
    ("ask", "Merre mész?", [
        ("Keletre fordulsz", (2, 1500), None),
        ("Tovább mész délnek", (3, 50), None)]),
]
N[(0, 4600)] = [
    ("g", 2, 3600),
]
N[(0, 4650)] = [
    "Megpróbálod újraindítani a motort, mielőtt a banda odaér.",
    ("luck", (1, 3900), (2, 3400)),
]
N[(0, 4700)] = [
    "Kikerülöd a Jaguárt, de látod, hogy két kocsi üldöz.",
    ("if", "OO", ">", 0, [("g", 3, 1400)]),
    ("g", 2, 4200),
]
N[(0, 4750)] = [
    "Megfordulnak, és tüzelnek.",
    ("cmbV", "P", "T", 0, 6, 9, 6, 9, (2, 2450), ("end", "Meghaltál.")),
]
N[(0, 4800)] = [
    "Kifogyott a benzined.",
    ("if", "BT", ">", 0, [("g", 1, 4000)]),
    ("g", 0, 4850),
]
N[(0, 4850)] = [
    "Az egyik legyőzött motorostól egy dobókést veszel el.",
    ("+", "DK", 1),
    ("g", 2, 750),
]
N[(0, 4900)] = [
    "A Ford egy gránátot lő feléd. Robbanást hallasz.",
    ("armor", (2, 4700), "Meghaltál."),
]
N[(0, 4950)] = [
    "Megállsz, és egy kanna benzint a kocsiba töltesz.",
    ("+", "BT", -1),
    ("ask", "Mit teszel?", [
        ("Azonnal javítani kezded a kocsit", (0, 1050), None),
        ("Tovább mész", (2, 1050), None)]),
]
N[(0, 5000)] = [
    "Amikor felébredsz, a fejed fáj. Körülnézel: az Interceptor eltűnt.",
    ("end", "A vállalkozás meghiúsult."),
]

# ------------------------------- OVERLAY 1 -----------------------------
N[(1, 50)] = [
    "Csodával határos módon áthajtasz az aknamezőn.",
    ("+", "S", 1), ("cap", "S", "SS"),
    ("g", 3, 150),
]
N[(1, 100)] = [
    "Két bandita a lánynak jut, kettő neked.",
    ("cmbV", "E", "U", 0, 7, 13, 8, 14, (1, 2700), ("end", "Meghaltál.")),
]
N[(1, 150)] = [
    "Odamész a motorhoz. A két motoros halott.",
    "Egy zárt csomagtartót találsz.",
    ("ask", "Mit teszel?", [
        ("Kinyitod", (2, 300), None),
        ("Kereket cserélsz", (3, 2300), None)]),
]
N[(1, 200)] = [
    "A kocsi üres, de a tank tele van.",
    ("if", "GC", "==", 1, [("g", 3, 300)]),
    ("g", 1, 4350),
]
N[(1, 155)] = [
    "Egy zárt csomagtartót találsz.",
    ("ask", "Mit teszel?", [
        ("Kinyitod", (2, 300), None),
        ("Kereket cserélsz", (3, 2300), None)]),
]
N[(1, 250)] = [
    "Kilőtték a kerekedet, és pont az akna előtt állsz meg.",
    ("+", "P", -1), ("+", "P", -1),
    ("if", "P", ">", 0, [("g", 2, 4600)]),
    ("end", "A robbanást nem élted túl."),
]
N[(1, 300)] = [
    "Szétlövöd a zárat.",
    "Az ott talált bilincset és a kétszáz hitelt elteszed.",
    ("+", "BC", 1), ("+", "HH", 200),
    ("g", 1, 1110),
]
N[(1, 350)] = [
    "Az Interceptorhoz rohantok, és beültök.",
    ("g", 1, 2900),
]
N[(1, 400)] = [
    "A lövés talált, és a kutya felfordult.",
    ("g", 0, 4450),
]
N[(1, 450)] = [
    "A kocsi le van zárva.",
    ("if", "FV", "<", 1, [
        "Mivel nincs feszítővasad, továbbmész.",
        ("g", 0, 2450)]),
    ("ask", "Mit teszel?", [
        ("Felfeszíted", (2, 3850), None),
        ("Továbbmész", (0, 2450), None)]),
]
N[(1, 500)] = [
    "Reggel frissen ébredsz.",
    ("+", "E", 2), ("cap", "E", "EE"),
    "Továbbindulsz.",
    ("g", 2, 2700),
]
N[(1, 550)] = [
    "A nézők gratulálnak, és megkapod a díjat: egy kanna benzint.",
    ("+", "BT", 1),
    "Átnézed az Interceptort. Ekkor a tetovált őr megkérdezi, melyik bandába tartozol.",
    ("ask", "Mit felelsz?", [
        ("Fekete Macskák", (0, 2200), None),
        ("Fekete Patkányok", (1, 2800), None),
        ("Fekete Denevérek", (2, 1400), None)]),
]
N[(1, 600)] = [
    "A boltban találsz egy konzervet, amit megeszel, és két kanna benzint.",
    ("+", "BT", 2), ("+", "E", 2), ("cap", "E", "EE"), ("+", "SB", 1),
    ("if", "SH", "==", 1, [
        "Továbbmész.",
        ("g", 3, 2650)]),
    ("ask", "Mit teszel?", [
        ("Átkutatod a közeli házat", (2, 2600), None),
        ("Továbbmész", (3, 2650), None)]),
]
N[(1, 650)] = [
    "Kilövöd a jármű fényszóróit, és az Interceptorhoz szaladtok.",
    ("g", 1, 2900),
]
N[(1, 700)] = [
    "Továbbra is mellékutakon haladsz.",
    ("g", 0, 4600),
]
N[(1, 750)] = [
    "Két homokfutóval találkozol. Tüzet nyitnak rád.",
    ("cmbV", "P", "T", 0, 7, 10, 8, 11, (1, 4700), ("end", "Meghaltál.")),
]
N[(1, 800)] = [
    "A golyó eltalál.",
    ("lose", "E", 1, 6),
    ("die", "E", "Meghaltál."),
    ("g", 1, 820),
]
N[(1, 820)] = [
    "Viszonzod a tüzet.",
    ("cmbV", "E", "U", -2, 8, 12, 0, 0, (1, 1550), ("end", "Meghaltál.")),
]
N[(1, 850)] = [
    "Elágazáshoz érsz, és balra fordulsz.",
    ("g", 1, 4450),
]
N[(1, 900)] = [
    "A tank kiürült.",
    ("if", "BT", ">", 0, [("g", 0, 4950)]),
    ("g", 3, 3200),
]
N[(1, 950)] = [
    ("g", 2, 3600),
]
N[(1, 1000)] = [
    ("g", 2, 4300),
]
N[(1, 1050)] = [
    "A gránát alattad robban.",
    ("armor", (1, 1700), "Meghaltál."),
]
N[(1, 1100)] = [
    "Kiugrasz a kocsiból, és a motorosok mögé kerülsz. Lefegyverzed őket.",
    "A náluk talált térképen meg van jelölve Új Remény és Sziklaváros.",
    "Kereket cserélsz.",
    ("g", 3, 2300),
]
N[(1, 1110)] = [
    "A náluk talált térképen meg van jelölve Új Remény és Sziklaváros.",
    "Kereket cserélsz.",
    ("g", 3, 2300),
]
N[(1, 1150)] = [
    "Túl gyorsan hajtasz. Az Interceptor megperdül és felborul.",
    "Téged kirángatnak és megkötöznek.",
    ("end", "A kocsit felgyújtják Leonárdék."),
]
N[(1, 1200)] = [
    "Visszaérsz az elágazáshoz.",
    ("ask", "Merre mész?", [
        ("Balra, nyugatnak", (3, 2200), None),
        ("Jobbra, keletnek", (2, 150), None)]),
]
N[(1, 1250)] = [
    "Az őrre veted magad.",
    ("skill_gt", (2, 100), (3, 2450)),
]
N[(1, 1300)] = [
    "A falhoz lapulsz, és kinézel a sarkon.",
    "Egy férfi puskát fog rád, és megkérdezi, honnan jöttél.",
    ("ask", "Mit mondasz?", [
        ("Új Reményből", (2, 3700), None),
        ("Hogy útonálló vagy", (1, 2750), None)]),
]
N[(1, 1350)] = [
    "Szögeket szórsz az útra.",
    ("chance", 6, 5, (3, 3650), (2, 1000)),
]
N[(1, 1400)] = [
    "Hátulról egy páncélkocsi aknát lő ki rád. Az melletted robban.",
    ("ask", "Mit teszel?", [
        ("Szögeket szórsz", (3, 600), None),
        ("Olajat fecskendezel", (0, 3250), None),
        ("Szembefordulsz vele", (0, 3850), None)]),
]
N[(1, 1450)] = [
    "Aknára futottál!",
    ("armor", (0, 4650), "Meghaltál."),
]
N[(1, 1500)] = [
    "Hegyomlásba kerültél.",
    ("ask", "Mit teszel?", [
        ("Fékezel", (3, 700), None),
        ("Gyorsítasz", (0, 3550), None)]),
]
N[(1, 1550)] = [
    "A halottnál százötven hitelt és egy pár boxert találsz. Elteszed őket.",
    ("+", "BK", 2), ("+", "HH", 150),
    "Továbbindulsz keletnek.",
    ("g", 0, 1100),
]
N[(1, 1600)] = [
    "Ellenfeledet lelövöd. Egész nap hajtasz.",
    ("g", 0, 3715),
]
N[(1, 1650)] = [
    "Belerohansz a teherautóba.",
    ("armor", (2, 2550), "Meghaltál."),
]
N[(1, 1700)] = [
    ("ask", "Mit teszel?", [
        ("Visszamész az útra", (2, 350), None),
        ("Elfogadod a kihívást", (3, 1500), None)]),
]
N[(1, 1750)] = [
    "Amikor kilépsz a kocsiból, a bandita feléd dobja a tőrét.",
    ("skill_gt", (0, 1800), (1, 4650)),
]
N[(1, 1800)] = [
    "A lány káromkodni kezd. Elvesztette az energiapirulákat.",
    ("g", 0, 1600),
]
N[(1, 1850)] = [
    "Balra kanyarodsz, és elhúzol a pillér mellett.",
    ("ask", "Mit teszel?", [
        ("Megállsz, hogy elbánj a támadóddal", (2, 4050), None),
        ("Továbbmész", (0, 2500), None)]),
]
N[(1, 1900)] = [
    "A fiatal lány közben elhajt.",
    ("ask", "Mit teszel?", [
        ("Üldözőbe veszed", (0, 3750), None),
        ("Átkutatod a garázst", (1, 2300), None)]),
]
N[(1, 1950)] = [
    "Hátulról nekirohansz, de csak az Interceptornak ártasz.",
    ("+", "P", -2),
    "Meg akarod előzni.",
    ("skill_gt", (2, 4350), (0, 400)),
]
N[(1, 2000)] = [
    "Egy elágazáshoz érsz, és jobbra fordulsz.",
    ("g", 0, 1150),
]
N[(1, 2050)] = [
    "Alszol, amíg Péter szereli a kocsit.",
    ("+", "TG", 1),
    "Aztán fizetsz, majd tovább indulsz.",
    ("+", "HH", -100), ("+", "GG", -2), ("+", "S", 1), ("cap", "S", "SS"),
    ("g", 0, 4400),
]
N[(1, 2100)] = [
    "Megállsz és kiszállsz.",
    "A férfi egy kézigránátot dob feléd. A robbanás ledönt a lábadról.",
    ("luck", (0, 1250), (2, 4950)),
]
N[(1, 2150)] = [
    "Mielőtt a többiek felbukkannak, tovább mész délnek.",
    ("g", 0, 4800),
]
N[(1, 2200)] = [
    "Éjszaka van, és nagyon fáradt vagy.",
    ("skill_gt", (1, 3400), (0, 3400)),
]
N[(1, 2250)] = [
    "A banda egyik tagja észrevesz.",
    ("end", "A Pusztulás Kutyái elfognak."),
]
N[(1, 2300)] = [
    "A garázsban csak egy láncot találsz. Elteszed és elhajtasz.",
    ("+", "LC", 1),
    ("g", 1, 3350),
]
N[(1, 2350)] = [
    "Az egyik támadó a benzinszállítóhoz rohan.",
    "Át kell rohannod a kereszttűzön, hogy megállítsd.",
    ("luck", (2, 3950), (2, 1750)),
]
N[(1, 2400)] = [
    "A Ford megelőz, majd fékez.",
    ("+", "S", -1),
    "Nem tudod megakadályozni, hogy nekedrontson.",
    ("luck", (3, 2700), (2, 2350)),
]
N[(1, 2450)] = [
    "Elágazáshoz érsz.",
    ("ask", "Merre mész?", [
        ("Tovább délnek", (2, 1250), None),
        ("Elfordulsz keletnek", (1, 700), None)]),
]
N[(1, 2500)] = [
    "A sivatag szélén elágazáshoz érsz.",
    ("ask", "Merre mész?", [
        ("Tovább délnek", (0, 2300), None),
        ("Nyugatnak fordulsz", (2, 4900), None)]),
]
N[(1, 2550)] = [
    "Aztán tovább haladsz nyugatnak egy útelágazásig.",
    ("ask", "Mit teszel?", [
        ("Továbbmész", (1, 3950), None),
        ("Délnek fordulsz", (3, 3100), None)]),
]
N[(1, 2600)] = [
    "Fékezel, és a Ford beléd szalad.",
    ("+", "P", -2),
    "Gázt adsz, de a Ford leelőz. Ökleléssel próbálkozol.",
    ("g", 1, 1950),
]
N[(1, 2610)] = [
    "Gázt adsz, de a Ford leelőz. Ökleléssel próbálkozol.",
    ("g", 1, 1950),
]
N[(1, 2650)] = [
    ("g", 2, 1250),
]
N[(1, 2700)] = [
    "A lány is elintézi az ellenfeleit.",
    "Ekkor a bandavezér, aki eddig csak figyelt, kiugrik a furgonból, és rád veti magát.",
    ("+", "E", -2),
    ("die", "E", "Puszta kézzel agyonüt."),
    "A lány egy csavarkulccsal indul segíteni.",
    ("chance", 6, 3, (2, 2250), (3, 3800)),
]
N[(1, 2750)] = [
    "A puskás férfi rajtad akar bosszút állni a családjáért.",
    ("+", "S", -1),
    ("ask", "Mit teszel?", [
        ("Magyarázkodsz", (2, 950), None),
        ("Pisztolyt rántasz", (3, 1650), None)]),
]
N[(1, 2800)] = [
    "Mintha ezt mondtad volna az előbb is. Csak hát sose hallottam róluk – mondja a tetovált.",
    "Aztán otthagy, és te továbbhajtasz.",
    ("g", 2, 350),
]
N[(1, 2850)] = [
    "Elhatároztad, hogy eléred Sziklavárost.",
    "Hirtelen fényt látsz egy szikla tetején.",
    ("luck", (2, 1100), (3, 750)),
]
N[(1, 2900)] = [
    "Szembefordulsz támadóiddal, akik tüzet nyitnak.",
    ("cmbP", "P", "T", 0, 10, 19, 2, (0, 3350), ("end", "Az Interceptor felrobbant.")),
]
N[(1, 2950)] = [
    ("g", 3, 2050),
]
N[(1, 3000)] = [
    "Az őr meghallotta a zajt.",
    ("ask", "Mit teszel?", [
        ("Ráveted magad", (2, 4650), None),
        ("Csendben meglapulsz", (3, 3350), None)]),
]
N[(1, 3050)] = [
    ("g", 1, 1400),
]
N[(1, 3100)] = [
    "Leonárd meglepődik, amikor kikerülöd a parkoló kocsiját.",
    ("skill_gt", (1, 1150), (0, 4700)),
]
N[(1, 3150)] = [
    ("g", 3, 450),
]
N[(1, 3200)] = [
    "Megkezdődik a párbaj.",
    ("af", 8, 13, 6, (2, 250), (1, 1600)),
]
N[(1, 3250)] = [
    "Kiengeded az olajat. A páncélkocsi csúszkál a folton.",
    ("chance", 6, 6, (2, 1700), (2, 4000)),
]
N[(1, 3300)] = [
    "Az egyetlen használható kereket leszeded az Interceptorról, és a kocsidba teszed.",
    ("+", "PK", 1),
    ("ask", "Mit teszel?", [
        ("Átnézed a roncs belsejét", (2, 2650), None),
        ("Továbbhajtasz", (0, 650), None)]),
]
N[(1, 3350)] = [
    "Szembe egy vörös Chevrolet jön, és rád támad.",
    ("cmbV", "P", "T", 0, 8, 15, 0, 0, (1, 4400), ("end", "Meghaltál.")),
]
N[(1, 3400)] = [
    "Nagyon fáradt vagy, és csak későn reagálsz az előtted feltűnő buszra.",
    ("armor", (3, 1350), "Meghaltál."),
]
N[(1, 3450)] = [
    "A férfi vaslemezekkel borítja az Interceptort.",
    ("+", "P", 10), ("cap", "P", "PP"),
    "Aztán továbbindulsz.",
    ("g", 2, 2950),
]
N[(1, 3500)] = [
    "Boxerral a férfi arcába vágsz.",
    ("skill_gt", (0, 4350), (3, 3250)),
]
N[(1, 3550)] = [
    "Szerencsére a golyók nem találnak el. Továbbindulsz.",
    ("g", 0, 1100),
]
N[(1, 3600)] = [
    "Sikerül keresztülhajtanod a lezúduló kövek között anélkül, hogy eltalálnának.",
    "Megkönnyebbülsz.",
    ("g", 3, 2550),
]
N[(1, 3650)] = [
    "Újabb aknát lőnek ki a farmházból.",
    ("end", "Ezt a robbanást nem éled túl."),
]
N[(1, 3700)] = [
    "A melledre céloz, de golyóálló mellényed megvéd.",
    ("g", 0, 4050),
]
N[(1, 3750)] = [
    "A gránát nem robban fel, és te továbbszáguldasz.",
    ("g", 3, 2000),
]
N[(1, 3800)] = [
    ("skill_gt", (3, 2500), (1, 400)),
]
N[(1, 3850)] = [
    "Úttorlaszhoz érsz, ezért jobbra fordulsz délnek.",
    ("g", 0, 2300),
]
N[(1, 3900)] = [
    "A motor nem indul, de könnyen megjavítod.",
    "Egy férfi bukkan fel, és pisztolyt fog rád.",
    ("cmbV", "E", "U", 0, 9, 12, 0, 0, (3, 3750), ("end", "Meghaltál.")),
]
N[(1, 3950)] = [
    "Az úton egy motoros integet.",
    ("ask", "Mit teszel?", [
        ("Megállsz", (1, 2100), None),
        ("Elmész mellette", (2, 750), None)]),
]
N[(1, 4000)] = [
    "Megállsz, és egy kanna benzint a tankba töltesz.",
    ("g", 2, 2150),
]
N[(1, 4050)] = [
    "A páncélkocsi kerekeit kilyuggatják a szögek. Gyorsítasz, és elhagyod.",
    ("g", 0, 2350),
]
N[(1, 4100)] = [
    "Beugrasz a magas fűbe. Hajpántos férfi jön, pisztollyal a kezében, és vaktában tüzelni kezd.",
    ("luck", (1, 800), (2, 1350)),
]
N[(1, 4150)] = [
    "A Ford egy gránátot lő eléd.",
    ("ask", "Mit teszel?", [
        ("Gyorsítasz", (0, 2150), None),
        ("Fékezel", (1, 2600), None)]),
]
N[(1, 4200)] = [
    "Kettő a lánynak, kettő neked jut.",
    ("cmbV", "E", "U", 0, 7, 13, 8, 14, (0, 3450), ("end", "Meghaltál.")),
]
N[(1, 4250)] = [
    "A szobában találsz egy drótvágót, amit elteszel.",
    ("+", "DV", 1), ("+", "BS", 1),
    ("if", "JS", "==", 1, [
        "Elhagyod a házat.",
        ("g", 2, 2300)]),
    ("ask", "Mit teszel?", [
        ("Kinyitod a szemközti ajtót", (0, 3600), None),
        ("Elhagyod a házat", (2, 2300), None)]),
]
N[(1, 4300)] = [
    "Olyan fáradt vagy, hogy elalszol a volánnál, és belerohansz egy elhagyott teherautóba.",
    ("armor", (3, 2400), "Meghaltál."),
]
N[(1, 4350)] = [
    "A benzint nincs mivel kiszívnod.",
    ("g", 1, 900),
]
N[(1, 4400)] = [
    "A rádiódon Új Remény üzenetét veszed.",
    "Megtudod, hogy egy banda megtámadta a várost, és elrabolta a tanács vezetőjét.",
    "Meg kell találnod őket.",
    ("ask", "Merre mész?", [
        ("Keletnek fordulsz", (3, 2050), None),
        ("Nyugatnak fordulsz", (0, 3300), None)]),
]
N[(1, 4450)] = [
    "Jobbra egy földút vezet.",
    ("ask", "Mit teszel?", [
        ("Ráfordulsz", (0, 1200), None),
        ("Továbbmész", (2, 350), None)]),
]
N[(1, 4500)] = [
    "Hallod, hogy a bandita a tartálykocsi tetején mászik előre. Felmászol a vontatóra.",
    "Az útonálló nyílpuskával rád lő.",
    ("luck", (0, 1500), (3, 2250)),
]
N[(1, 4550)] = [
    "Egy sziklának ütközöl.",
    ("lose", "P", 1, 6),
    ("if", "P", "<", 1, [("end", "Szörnyethalsz.")]),
    "A farmházból páncélököllel lőnek rád.",
    ("armor", (2, 4600), "Meghaltál."),
]
N[(1, 4600)] = [
    "A tetovált férfi kitér a rúgás elől, és fegyverével leüt.",
    ("g", 0, 5000),
]
N[(1, 4650)] = [
    "Lebuksz az ajtó mögé, amiről a tőr lepattan. Aztán pisztolyt ránt.",
    ("cmbV", "E", "U", 1, 7, 11, 0, 0, (0, 3200), ("end", "Meghaltál.")),
]
N[(1, 4660)] = [
    ("cmbV", "E", "U", 1, 7, 11, 0, 0, (0, 3200), ("end", "Meghaltál.")),
]
N[(1, 4700)] = [
    "Otthagyod a lángoló homokfutókat, és egy elágazáshoz érsz.",
    ("ask", "Merre mész?", [
        ("Balra fordulsz", (2, 2850), None),
        ("Jobbra fordulsz", (2, 550), None)]),
]
N[(1, 4750)] = [
    "Az ajtó nyitása egy bombát robbant. Megsérülsz.",
    ("lose", "E", 1, 12),
    ("die", "E", "Meghaltál."),
    "A tulajdonos jön.",
    ("ask", "Hová rejtőzöl?", [
        ("A bozótba", (1, 4100), None),
        ("A mentőautó alá", (3, 2800), None)]),
]
N[(1, 4800)] = [
    "Emlékszel a figyelmeztetésre, és lassan haladsz. A hegyomlás zajára megállsz.",
    "Amikor vége van, továbbmész.",
    ("g", 3, 2550),
]
N[(1, 4850)] = [
    "Hol töltöd az éjszakát?",
    ("ask", "Mit teszel?", [
        ("Az Interceptorban", (0, 200), None),
        ("Keresel egy házat", (3, 1050), None),
        ("Egész éjjel vezetsz", (1, 2200), None)]),
]
N[(1, 4900)] = [
    "Eléred a kerítést.",
    ("if", "DV", "==", 1, [("g", 0, 4250)]),
    ("g", 2, 2750),
]
N[(1, 4950)] = [
    ("g", 0, 1550),
]
N[(1, 5000)] = [
    "A furgonnal összeakad a kocsid.",
    "A bandavezér pusztakezes harcra hív ki.",
    ("ask", "Mit teszel?", [
        ("Kiállsz", (2, 3450), None),
        ("A tűzharcot választod", (1, 100), None)]),
]

# ------------------------------- OVERLAY 2 -----------------------------
N[(2, 50)] = [
    "Tompa puffanást hallasz a kocsi alól.",
    ("armor", (2, 3300), "Bentégtél."),
]
N[(2, 100)] = [
    "Az őr nem veszti el az eszméletét, és hívja a barátait.",
    ("end", "Tucatnyi golyó fúródik beléd."),
]
N[(2, 150)] = [
    "Úttorlaszhoz érsz.",
    ("ask", "Mit teszel?", [
        ("Szétlövöd", (3, 3600), None),
        ("Kikerülöd", (3, 850), None),
        ("Visszamész az elágazáshoz és délre fordulsz", (2, 3900), None)]),
]
N[(2, 200)] = [
    "A golyó elzúg melletted, és te elszáguldasz.",
    ("g", 2, 350),
]
N[(2, 250)] = [
    "Ellenfeled gyorsabb. Szíven lő.",
    ("end", "Meghaltál."),
]
N[(2, 300)] = [
    "Szétlövöd a zárat.",
    "Az ott talált bilincset és a kétszáz hitelt elteszed.",
    ("+", "BC", 1), ("+", "HH", 200),
    ("g", 1, 1110),
]
N[(2, 350)] = [
    "Megállsz Péter műhelye előtt.",
    "Ő felajánlja, hogy hitelért és gyógyszerért feljavítja a kocsidat.",
    ("ask", "Mit teszel?", [
        ("Megbízod", (0, 1400), None),
        ("Továbbhajtasz", (0, 4400), None)]),
]
N[(2, 400)] = [
    "A küzdelem után figyelmeztet, hogy az alagút után sűrűn van hegyomlás.",
    "Megköszönöd, és elindulsz.",
    ("g", 1, 4800),
]
N[(2, 450)] = [
    "Nyújtod a kulcsot, de a férfi rád veti magát. Elveszted az eszméleted.",
    ("g", 0, 5000),
]
N[(2, 500)] = [
    ("call", "race"),
]
N[(2, 550)] = [
    "Éppen a porlasztót tisztítod, amikor meghallod a helikoptert.",
    "Hangszórón felszólítanak, hogy rakd az útra a fegyvereidet.",
    ("ask", "Mit teszel?", [
        ("Engedelmeskedsz", (0, 550), None),
        ("Beugrasz és tüzet nyitsz", (0, 4150), None)]),
]
N[(2, 600)] = [
    "Autód csúszkálva megáll. Kiugrasz, és egy bokor mögé veted magad.",
    ("+", "P", -2),
    "Az aknarobbanás tönkreteszi az egyik kerekedet.",
    "Az egyik motoros elkéri a pisztolyodat és a kulcsokat.",
    ("ask", "Mit teszel?", [
        ("Engedelmeskedsz", (2, 4150), None),
        ("Harcolsz", (0, 300), None)]),
]
N[(2, 610)] = [
    "Az egyik motoros elkéri a pisztolyodat és a kulcsokat.",
    ("ask", "Mit teszel?", [
        ("Engedelmeskedsz", (2, 4150), None),
        ("Harcolsz", (0, 300), None)]),
]
N[(2, 650)] = [
    "A por beszívja az olajat. Válaszul a Ford egy gránátot lő eléd.",
    "Ráhajtasz, és egy puffanást hallasz.",
    ("+", "S", -1),
    ("armor", (2, 4700), "Bentégtél."),
]
N[(2, 700)] = [
    "Ahogy a többiekhez kísér, érzed, menekülnöd kell.",
    "Kirúgsz a tetovált felé.",
    ("chance", 6, 5, (1, 4600), (3, 2350)),
]
N[(2, 750)] = [
    "Elágazáshoz érsz, ahol az egyik ágat kocsi torlaszolja el.",
    ("ask", "Mit teszel?", [
        ("Rögtön délnek fordulsz", (1, 2450), None),
        ("Átkutatsz néhány kocsit", (0, 500), None)]),
]
N[(2, 800)] = [
    "Délnek fordulsz.",
    ("g", 2, 2150),
]
N[(2, 850)] = [
    "A férfit nem zavarja, hogy felé futsz. Akkor érsz oda, amikor a gyufát el akarja dobni.",
    ("skill_gt", (0, 2500), (2, 4250)),
]
N[(2, 900)] = [
    "Nyugtalanul alszol, és mire a nap felkel, már úton vagy.",
    "Két motoros húz el melletted, és célba veszik a kerekeidet.",
    ("skill_gt", (3, 1200), (0, 2600)),
]
N[(2, 950)] = [
    "Közlöd vele, hogy nem te ölted meg a családját.",
    ("luck", (2, 4400), (2, 1800)),
]
N[(2, 1000)] = [
    "A motor kikerüli a szögeket, és tüzel.",
    ("cmbV", "P", "T", 0, 9, 8, 0, 0, (1, 2150), ("end", "Meghaltál.")),
]
N[(2, 1050)] = [
    "A sivatagban egy kiégett autó mellett egy lányt találsz.",
    "Kiderül, hogy eléd küldték a finomítóból.",
    "Megtudod, hogy csak úgy juthatsz be a finomítóba, ha előbb tönkreteszed a Pusztulás Kutyáinak kocsijait.",
    "Lehajtasz az útról.",
    ("luck", (3, 1550), (0, 350)),
]
N[(2, 1100)] = [
    "A páncélököl célt téveszt.",
    ("g", 0, 2650),
]
N[(2, 1150)] = [
    "Kereket cserélsz, és továbbmész.",
    ("g", 0, 2710),
]
N[(2, 1200)] = [
    "Az első versenyt egy Ford nyeri. Te elhajtasz dél felé.",
    ("g", 2, 350),
]
N[(2, 1250)] = [
    "A tank kiürült.",
    ("if", "BT", ">", 0, [("g", 1, 4850)]),
    ("g", 3, 3200),
]
N[(2, 1300)] = [
    "Támadód lelő. Elveszted az eszméleted.",
    ("end", "Mire magadhoz térsz, a benzinszállító eltűnt."),
]
N[(2, 1350)] = [
    "A golyó nem talált. Visszalősz.",
    ("g", 1, 820),
]
N[(2, 1355)] = [
    ("g", 1, 820),
]
N[(2, 1400)] = [
    "Hazudsz! Nem úgy nézel ki, mint aki valamelyik bandához tartozik.",
    ("if", "BK", "==", 1, [("g", 2, 3650)]),
    ("g", 2, 700),
]
N[(2, 1450)] = [
    "Óvatosan hajtasz a hídra. Robbanás. Alá volt aknázva.",
    ("end", "Az Interceptor a folyóba esik."),
]
N[(2, 1500)] = [
    "Egy műhelyhez érsz. A szerelő a műhely előtt hegeszt.",
    ("ask", "Mit teszel?", [
        ("Megállsz", (0, 750), None),
        ("Továbbhajtasz", (2, 2950), None)]),
]
N[(2, 1550)] = [
    "A hídról a folyóba csúszol.",
    ("end", "Meghaltál."),
]
N[(2, 1600)] = [
    "Miközben a Fordot ünneplik, te elhajtasz.",
    ("g", 2, 350),
]
N[(2, 1650)] = [
    "Sebedet ellátod, és körülnézel, de nem találsz semmit.",
    ("+", "S", -1), ("+", "JS", 1),
    ("if", "BS", "==", 1, [
        "Elhagyod a házat.",
        ("g", 2, 2300)]),
    ("ask", "Mit teszel?", [
        ("Kinyitod a szemközti ajtót", (1, 4250), None),
        ("Elmész", (2, 2300), None)]),
]
N[(2, 1700)] = [
    "Az árokba fordul.",
    ("g", 0, 2350),
]
N[(2, 1750)] = [
    "Lehajolva futsz, és nem talál el golyó.",
    ("g", 0, 2000),
]
N[(2, 1800)] = [
    "Védd magad – mondja a férfi.",
    ("g", 3, 1650),
]
N[(2, 1850)] = [
    "Az Interceptor elakad a homokban, és nem tudod kiásni.",
    ("end", "Gyalog indulsz vissza Új Reménybe."),
]
N[(2, 1900)] = [
    "A kereket megragasztod, és továbbmész.",
    ("g", 1, 950),
]
N[(2, 1950)] = [
    "A Ford leelőz és győz.",
    ("+", "S", -1),
    ("g", 2, 1600),
]
N[(2, 2000)] = [
    "Kétszáz hitelt odaadsz a sebhelyesnek, aztán előregurulsz a rajtvonalhoz.",
    ("skill_gt", (1, 2400), (0, 150)),
]
N[(2, 2050)] = [
    "Felfeszíted a motelajtót, és belépsz.",
    "Egy öreg két patkányt dob rád. Az egyik megharap.",
    ("+", "PH", 1), ("+", "E", -1),
    "Kimész, és a kabinban alszol.",
    ("g", 2, 900),
]
N[(2, 2100)] = [
    ("g", 2, 1900),
]
N[(2, 2150)] = [
    "Egy elhagyott rendőrautót találsz.",
    ("ask", "Mit teszel?", [
        ("Megállsz átkutatni", (1, 450), None),
        ("Továbbmész", (0, 2450), None)]),
]
N[(2, 2200)] = [
    "Késedért nyúlnál, de ellenfeled lelő.",
    ("end", "Meghaltál."),
]
N[(2, 2250)] = [
    ("+", "E", -2),
    "A lány megpróbálja leütni a vezért.",
    ("g", 3, 3800),
]
N[(2, 2300)] = [
    ("if", "SB", "==", 1, [
        "Továbbmész.",
        ("g", 3, 2650)]),
    ("ask", "Mit teszel?", [
        ("Átkutatod a boltot", (1, 600), None),
        ("Továbbmész", (3, 2650), None)]),
]
N[(2, 2350)] = [
    "A Ford beléd öklel.",
    ("+", "P", -2),
    ("ask", "Mit teszel?", [
        ("Gyorsítasz, hogy meglépj", (1, 4150), None),
        ("Fékezel", (0, 1350), None)]),
]
N[(2, 2400)] = [
    "Lassú vagy.",
    ("end", "Az öklelőrúd a kocsiddal együtt felnyársal."),
]
N[(2, 2450)] = [
    "Az összetört motorhoz mész. Egy zárt csomagtartót találsz.",
    ("ask", "Mit teszel?", [
        ("Kinyitod", (2, 300), None),
        ("Továbbmész", (1, 3150), None)]),
]
N[(2, 2500)] = [
    ("g", 2, 700),
]
N[(2, 2550)] = [
    "Durrdefekted van.",
    ("if", "PK", ">", 0, [("g", 2, 1150)]),
    ("g", 3, 2150),
]
N[(2, 2600)] = [
    "Belépsz a házba. Két ajtó nyílik egymással szembe.",
    ("+", "SH", 1),
    ("ask", "Melyiket nyitod ki?", [
        ("A balt", (1, 4250), None),
        ("A jobbat", (0, 3600), None)]),
]
N[(2, 2650)] = [
    "Az autóban csörgőkígyó fészkébe nyúlsz. Az megmar.",
    ("if", "GG", ">", 0, [("g", 0, 100)]),
    ("g", 3, 2850),
]
N[(2, 2700)] = [
    "A vidék szép, de nem tudod, nincs-e aláaknázva.",
    ("chance", 12, 7, (1, 1450), (1, 50)),
]
N[(2, 2750)] = [
    "Nincs mivel átvágnod a drótot, el kell kúsznod a bejáratig.",
    ("luck", (3, 1950), (1, 2250)),
]
N[(2, 2800)] = [
    "A kocsiban a sebedet bekötöd, és elhajtasz.",
    ("+", "GG", -1),
    ("g", 0, 1700),
]
N[(2, 2850)] = [
    "Az úton barikád. Egy hang felszólít, hogy fordulj vissza.",
    ("ask", "Mit teszel?", [
        ("Visszafordulsz", (3, 1850), None),
        ("Továbbmész", (0, 450), None)]),
]
N[(2, 2900)] = [
    "Kirohansz, és egy gyógyszert felhasználsz.",
    ("+", "GG", -1),
    ("ask", "Mit teszel?", [
        ("A kocsiban alszol", (2, 4850), None),
        ("Továbbmész", (1, 2200), None)]),
]
N[(2, 2950)] = [
    "Egy alagutat látsz, és előtte egy buszt. Odamész megnézni.",
    "Egy férfi ugrik ki, és azt mondja, kétszáz hitel vagy párbaj az ára az átjutásnak.",
    ("ask", "Melyiket választod?", [
        ("Fizetsz", (3, 3450), None),
        ("Párbajozol", (2, 4550), None)]),
]
N[(2, 3000)] = [
    "Hiába kiabálsz. A gyufát a kocsira dobja, amely lángra lobban.",
    ("end", "Az Interceptor odaveszett."),
]
N[(2, 3050)] = [
    "A tető megsérült, de tovább tudsz menni.",
    ("g", 3, 2550),
]
N[(2, 3100)] = [
    "A segélykiáltás egy kunyhóból jön. Felfeszíted.",
    "A fogoly Új Remény tanácsának vezetője. Motorra száll, és hazaindul.",
    ("+", "S", 1), ("cap", "S", "SS"),
    ("ask", "Mit teszel?", [
        ("Átkutatod a boltot", (1, 600), None),
        ("Átkutatod a legközelebbi házat", (2, 2600), None),
        ("Továbbindulsz", (3, 2650), None)]),
]
N[(2, 3150)] = [
    "A golyó szíven talál.",
    ("end", "Meghaltál."),
]
N[(2, 3200)] = [
    "A feszítővassal visszarohansz az Interceptorhoz, és tovább indulsz.",
    ("g", 1, 2450),
]
N[(2, 3250)] = [
    ("g", 0, 2710),
]
N[(2, 3300)] = [
    ("g", 1, 2610),
]
N[(2, 3350)] = [
    "Megállsz, és visszamész a mentőhöz.",
    ("ask", "Mit teszel?", [
        ("Kinyitod az ajtaját", (1, 4750), None),
        ("Továbbmész", (0, 1100), None)]),
]
N[(2, 3400)] = [
    "A motor nem sérült. Sietve elindulsz.",
    ("g", 3, 150),
]
N[(2, 3450)] = [
    "Elfogadod a kihívást azzal a feltétellel, hogy ha győzöl, továbbmehetsz.",
    ("cmbP", "E", "U", 0, 11, 16, 2, (3, 2750), ("end", "Meghaltál.")),
]
N[(2, 3500)] = [
    "Nagy sebességgel száguldasz a hídra.",
    ("skill_gt", (2, 1550), (0, 3500)),
]
N[(2, 3550)] = [
    "Az út mellett egy felborult Interceptort látsz.",
    ("ask", "Mit teszel?", [
        ("Megállsz átkutatni", (1, 3300), None),
        ("Továbbmész", (0, 650), None)]),
]
N[(2, 3600)] = [
    "Látod, hogy a benzined fogytán van.",
    ("if", "BT", ">", 0, [("g", 3, 1150)]),
    ("g", 3, 3200),
]
N[(2, 3650)] = [
    "Miközben a tetovált férfi előtt mész, a zsebedbe nyúlsz a boxerért.",
    ("luck", (2, 2500), (1, 3500)),
]
N[(2, 3700)] = [
    "Puskával a kézben kilép.",
    ("g", 0, 2860),
]
N[(2, 3750)] = [
    "Szédülsz és remegsz. Látod, hogy daganatok nőttek a testeden.",
    "A patkány harapása megfertőzött az ismeretlen járvánnyal.",
    "Üzenetet hagysz hátra, és gyalog indulsz a pusztába meghalni.",
    ("end", "Egy éven belül szobrot állítanak a tiszteletedre."),
]
N[(2, 3800)] = [
    "Lehúzódsz az útról, eszel, és elalszol.",
    ("+", "E", 2), ("cap", "E", "EE"),
    "Reggel továbbmész.",
    ("g", 1, 1400),
]
N[(2, 3850)] = [
    "A csomagtartóban egy golyóbiztos mellényt találsz.",
    ("+", "U", 1), ("cap", "U", "UU"), ("+", "S", 1), ("+", "GM", 1),
    "Felveszed és elhajtasz.",
    ("g", 0, 2450),
]
N[(2, 3900)] = [
    ("g", 3, 550),
]
N[(2, 3950)] = [
    "Egy golyó beléd fúródik, miközben átvágsz a nyílt terepen.",
    ("lose", "E", 1, 6),
    ("die", "E", "A lövés halálos."),
    ("g", 0, 2000),
]
N[(2, 4000)] = [
    "A páncélkocsi áthajt az olajfolton. Szembefordulsz vele.",
    ("g", 0, 3850),
]
N[(2, 4050)] = [
    "Pisztollyal a kezedben ugrasz ki.",
    "Támadód éppen akkor száguld el motoron egy lakókocsi mellől.",
    ("ask", "Mit teszel?", [
        ("Benézel a lakókocsiba", (0, 2900), None),
        ("Továbbmész", (1, 2500), None)]),
]
N[(2, 4100)] = [
    "A motor kanyarogva követ, és nehéz eltalálni.",
    ("cmbV", "P", "T", 0, 2, 8, 0, 0, (1, 2150), ("end", "Meghaltál.")),
]
N[(2, 4150)] = [
    "Az egyik motoros felveszi a kulcsot és a pisztolyt. Aztán leüt.",
    ("g", 0, 5000),
]
N[(2, 4200)] = [
    "Az autók egyre közelebb érnek, és tüzet nyitnak.",
    ("cmbV", "P", "T", 0, 9, 15, 10, 12, (2, 3250), ("end", "Meghaltál.")),
]
N[(2, 4250)] = [
    "Ráveted magad, és kiütöd a kezéből a gyufát. Megmented a kocsidat.",
    ("+", "S", 1),
    "A férfi átkozódva elszalad. Te továbbmész.",
    ("g", 2, 2700),
]
N[(2, 4300)] = [
    "Nem akarsz kockáztatni még egy összetűzést.",
    "Egy másik parkolóig hajtasz, és a kabinban alszol.",
    ("g", 2, 900),
]
N[(2, 4350)] = [
    "A Ford beléd öklel, de te továbbhajtasz.",
    ("+", "P", -2),
    ("g", 3, 2000),
]
N[(2, 4400)] = [
    "Oké, hiszek neked, de mondjál többet is.",
    ("g", 0, 2855),
]
N[(2, 4450)] = [
    "Lősz a járműre, de nem találsz, mert a fényszórói elvakítanak.",
    "Te viszont könnyű célpont vagy.",
    ("end", "Szitává lőnek."),
]
N[(2, 4500)] = [
    "Ura vagy a kocsidnak, és felveszed a harcot.",
    ("cmbV", "P", "T", 0, 9, 20, 0, 0, (1, 300), ("end", "Meghaltál.")),
]
N[(2, 4550)] = [
    "A férfi egy régi párbajpisztolyt ad. Szabályosan párbajoztok.",
    ("call", "duel4560"),
]
N[(2, 4600)] = [
    "A tetovált férfi kitér a rúgás elől, és fegyverével leüt.",
    ("g", 0, 5000),
]
N[(2, 4650)] = [
    ("if", "BK", ">", 0, [("g", 0, 2800)]),
    ("g", 1, 1250),
]
N[(2, 4700)] = [
    ("g", 0, 3155),
]
N[(2, 4750)] = [
    "Az akna felrobban, egy kereked tönkremegy.",
    ("+", "P", -2),
    "Kiugrasz, és egy bokor mögé lapulsz.",
    ("luck", (1, 1100), (3, 1450)),
]
N[(2, 4800)] = [
    "A férfi közelről rád lő.",
    ("if", "GM", ">", 0, [("g", 1, 3700)]),
    ("g", 2, 3150),
]
N[(2, 4850)] = [
    "Frissen ébredsz.",
    ("+", "E", 2), ("cap", "E", "EE"),
    ("ask", "Mit teszel?", [
        ("Átkutatod a kávézót", (0, 1300), None),
        ("Továbbmész", (0, 2700), None)]),
]
N[(2, 4900)] = [
    "A sivatag szélén haladsz, majd délnek fordulsz.",
    "Úgy határozol, hogy a sivatagon át mész délre.",
    ("g", 2, 3550),
]
N[(2, 4950)] = [
    "Egy szilánk megsebesít.",
    ("+", "E", -2),
    "Az Interceptor mögül lősz a motorosra és társára.",
    ("cmbV", "E", "U", -1, 7, 13, 5, 14, (0, 4850), ("end", "Meghaltál.")),
]
N[(2, 5000)] = [
    "Egy csoporthoz odamész, és a versenyről kérdezed őket.",
    "Egy sebhelyesarc elmondja, hogy kétszáz hitel a nevezési díj, és a győztes egy kanna benzint kap.",
    ("ask", "Mit teszel?", [
        ("Kihívod", (2, 2000), None),
        ("Csak nézed a versenyt", (2, 1200), None)]),
]

# ------------------------------- OVERLAY 3 -----------------------------
N[(3, 50)] = [
    "Egy idő után az út megszűnik. Csak eddig építették.",
    ("+", "S", -1),
    ("ask", "Merre mész?", [
        ("Balra, a köves rész felé", (2, 2550), None),
        ("Tovább a homokba", (2, 1850), None)]),
]
N[(3, 100)] = [
    "Kiszállsz. Kukucs!",
    "Ugrik elő egy férfi feszítővassal, és kéri a hiteleidet és a kulcsaidat.",
    ("ask", "Mit teszel?", [
        ("Átadod", (2, 450), None),
        ("Kést rántasz", (0, 2400), None)]),
]
N[(3, 150)] = [
    "A sivatagban egy elágazáshoz érsz.",
    ("ask", "Merre mész?", [
        ("Keletnek fordulsz", (1, 2000), None),
        ("Továbbhaladsz", (1, 4450), None)]),
]
N[(3, 200)] = [
    "Egy férfi benzinbombát dob az Interceptorra, de csak a kereked sérül meg.",
    ("luck", (3, 3500), (2, 1900)),
]
N[(3, 250)] = [
    "A helikopter felrobban. Továbbmész.",
    ("g", 2, 800),
]
N[(3, 300)] = [
    "Van egy gumicsöved. Segítségével egy kannába szívod a benzint.",
    ("+", "S", 1),
    ("g", 1, 900),
]
N[(3, 350)] = [
    "Odamész a motorokhoz.",
    ("g", 1, 155),
]
N[(3, 400)] = [
    ("g", 2, 4300),
]
N[(3, 450)] = [
    "Egy elágazáshoz érsz, amely Sziklavárosba vezet.",
    ("ask", "Mit teszel?", [
        ("Ráfordulsz", (1, 2850), None),
        ("Továbbmész", (0, 2250), None)]),
]
N[(3, 500)] = [
    "Megállsz, és benzint töltesz a tankba.",
    ("+", "BT", -1),
    "Aztán továbbindulsz.",
    ("g", 1, 750),
]
N[(3, 550)] = [
    "Nemsokára egy fahídhoz érsz, amelyre tilos ráhajtani.",
    ("ask", "Mit teszel?", [
        ("Ráhajtasz", (2, 1450), None),
        ("Visszafordulsz", (1, 1200), None)]),
]
N[(3, 600)] = [
    "Szögeket szórsz az útra.",
    ("luck", (0, 2050), (1, 4050)),
]
N[(3, 650)] = [
    ("if", "PK", ">", 0, [("g", 0, 950)]),
    ("g", 3, 1800),
]
N[(3, 700)] = [
    "Csikorogva tolatsz. Sziklák zuhannak eléd az útra.",
    ("+", "S", 1),
    "Hamarosan sértetlenül továbbmész.",
    ("g", 3, 2550),
]
N[(3, 750)] = [
    "Egy páncélököllel telibe találtak.",
    ("armor", (0, 2650), "Meghaltál."),
]
N[(3, 800)] = [
    "A banda tagjai a furgonhoz viszik a vezért.",
    "Te továbbmész délnek.",
    ("g", 0, 4500),
]
N[(3, 850)] = [
    "Bozótos részen vágsz át, amikor egy bandita aknát tapaszt a kocsidra.",
    ("ask", "Mit teszel?", [
        ("Továbbhajtasz", (0, 850), None),
        ("Kiugrasz", (2, 600), None),
        ("Megállsz, és nem szállsz ki", (2, 4750), None)]),
]
N[(3, 900)] = [
    ("luck", (0, 4900), (0, 3150)),
]
N[(3, 950)] = [
    "A lány energiatablettákat ad.",
    ("+", "E", 4), ("cap", "E", "EE"),
    ("g", 0, 1600),
]
N[(3, 1000)] = [
    "Az akna mögötted robban.",
    ("g", 1, 3650),
]
N[(3, 1050)] = [
    "Egy elhagyatott kávézó mögött leparkolsz.",
    ("ask", "Hol alszol?", [
        ("A kávézóban", (0, 2750), None),
        ("Kint a faházikóban", (3, 1600), None)]),
]
N[(3, 1100)] = [
    "A Jaguár győz. Leonárd int, hogy állj meg.",
    ("ask", "Mit teszel?", [
        ("Engedelmeskedsz", (0, 3900), None),
        ("Továbbhajtasz", (1, 3100), None)]),
]
N[(3, 1150)] = [
    "Besötétedik.",
    ("ask", "Mit teszel?", [
        ("A kocsiban alszol", (2, 3800), None),
        ("Továbbhajtasz", (0, 2100), None)]),
]
N[(3, 1200)] = [
    "A motort kilövöd, de az olajszállító megbillen és felborul.",
    ("end", "A vállalkozás meghiúsul."),
]
N[(3, 1250)] = [
    "Kidobod a pisztolyod, majd kimászol. A férfi kéri a kulcsaidat is.",
    ("ask", "Mit teszel?", [
        ("Odaadod", (3, 3300), None),
        ("A késedért nyúlsz", (0, 4100), None)]),
]
N[(3, 1300)] = [
    "Nincs remény, hogy elérjétek az Interceptort. Lehasaltok, és a fényszórókra lőttök.",
    ("skill_gt", (2, 4450), (1, 650)),
]
N[(3, 1350)] = [
    "Reggel továbbindulsz.",
    ("+", "E", 1), ("cap", "E", "EE"),
    ("g", 2, 2700),
]
N[(3, 1400)] = [
    "Olajat engedsz az útra. Üldözőid összeütköznek. Már csak egy Toyota üldöz.",
    ("cmbV", "P", "T", 0, 9, 15, 0, 0, (2, 3250), ("end", "Meghaltál.")),
]
N[(3, 1450)] = [
    "Észreveszik, hogy kiugrottál.",
    ("g", 2, 610),
]
N[(3, 1500)] = [
    "Megfordulsz, és bemész a kapun.",
    ("g", 2, 5000),
]
N[(3, 1550)] = [
    "A lány egy dzsipre mutat, ami őt is megtámadta. Közel ér és tüzel.",
    ("cmbV", "P", "T", 0, 9, 14, 0, 0, (0, 350), ("end", "Meghaltál.")),
]
N[(3, 1600)] = [
    ("luck", (0, 4200), (0, 800)),
]
N[(3, 1650)] = [
    ("skill_gt", (0, 4300), (0, 2850)),
]
N[(3, 1700)] = [
    "Egy kőhídhoz közeledtek.",
    ("ask", "Mit teszel?", [
        ("Továbbra is nyomod a gázt", (0, 1750), None),
        ("Fékezel", (2, 1950), None)]),
]
N[(3, 1750)] = [
    ("luck", (3, 3250), (0, 250)),
]
N[(3, 1800)] = [
    ("end", "Ezzel a kerékkel nem tudsz továbbmenni. Megbuktál."),
]
N[(3, 1850)] = [
    "Visszaérsz az elágazáshoz, és nyugat felé mész.",
    ("g", 2, 550),
]
N[(3, 1900)] = [
    "A házból újra lőnek.",
    ("luck", (3, 1000), (1, 250)),
]
N[(3, 1950)] = [
    "Észrevétlenül juttok be.",
    ("g", 0, 4253),
]
N[(3, 2000)] = [
    "Vasszöget szórsz, vagy olajat öntesz?",
    ("ask", "Mit teszel?", [
        ("Vasszöget szórsz", (3, 900), None),
        ("Olajat öntesz", (2, 650), None)]),
]
N[(3, 2050)] = [
    "Egy elhagyott mentőautót látsz.",
    ("ask", "Mit teszel?", [
        ("Továbbmész", (0, 1100), None),
        ("Megállsz átnézni", (2, 3350), None)]),
]
N[(3, 2100)] = [
    "Nekiütközöl az egyik pillérnek.",
    ("lose", "P", 1, 6),
    ("if", "P", "<", 1, [("end", "Nem élted túl.")]),
    ("g", 0, 3950),
]
N[(3, 2150)] = [
    ("g", 3, 1800),
]
N[(3, 2200)] = [
    "Visszatérsz az útra. Elhaladsz a mentő mellett.",
    "Nemsokára egy függőhídhoz érsz, amely nincs teljesen leeresztve.",
    "Úgy gondolod, hogy lendülettel átjuthatsz.",
    ("g", 2, 3500),
]
N[(3, 2250)] = [
    "A nyílvessző nem talál. Felugrasz, és birokra kelsz vele.",
    ("af", 8, 13, 6, (2, 1300), (0, 3700)),
]
N[(3, 2300)] = [
    "Továbbmész.",
    ("g", 3, 450),
]
N[(3, 2350)] = [
    "A tetovált férfi lassú, és a rúgás hason találja.",
    "Összeesik, és te a kocsidhoz rohansz. A férfi utánad lő.",
    ("luck", (0, 3250), (2, 200)),
]
N[(3, 2400)] = [
    "Úgy döntesz, hogy hajnalig alszol.",
    ("+", "E", 1), ("cap", "E", "EE"),
    "Reggel tovább indulsz.",
    ("g", 1, 1400),
]
N[(3, 2450)] = [
    ("g", 0, 2800),
]
N[(3, 2500)] = [
    "Lövésed nem talál, és a kutya rád veti magát. Kést rántasz.",
    ("g", 3, 3705),
]
N[(3, 2550)] = [
    "Két bőrruhás leállít, és mondja, hogy csak akkor mehetsz tovább, ha sebességi versenyben legyőzöd a vezetőjüket.",
    "Ha veszítesz, vissza kell fordulnod. Leonárd az ellenfeled. A verseny máris megkezdődött.",
    ("if", "TG", "==", 1, [("g", 2, 500)]),
    ("g", 3, 2900),
]
N[(3, 2600)] = [
    "Az árokba fordulsz, és a páncélautó támad.",
    ("cmbV", "P", "T", -2, 9, 20, 0, 0, (0, 1650), ("end", "Meghaltál.")),
]
N[(3, 2650)] = [
    "A földút kanyarog, aztán kiér a sztrádára.",
    ("ask", "Merre fordulsz?", [
        ("Nyugatnak", (3, 3550), None),
        ("Keletnek", (0, 3050), None)]),
]
N[(3, 2700)] = [
    ("ask", "Mit teszel?", [
        ("Gyorsítasz", (1, 4150), None),
        ("Fékezel", (0, 1350), None)]),
]
N[(3, 2750)] = [
    "Az útonállók összenéznek, amikor a földön látják a vezérüket.",
    ("luck", (3, 800), (1, 4200)),
]
N[(3, 2800)] = [
    "Fekszel a mentőautó alatt, és markolod a pisztolyt.",
    "Te hülye, dobd ki a fegyvered, és mássz ki!",
    ("ask", "Mit teszel?", [
        ("Engedelmeskedsz", (3, 1250), None),
        ("Rálősz", (0, 600), None)]),
]
N[(3, 2850)] = [
    ("end", "A méreg lassan végez veled."),
]
N[(3, 2900)] = [
    ("call", "race"),
]
N[(3, 2950)] = [
    "Egy öreg kocsiban egy teli kanna benzint találsz.",
    ("+", "BT", 1),
    "Visszamész az Interceptorhoz, és folytatod az utad.",
    ("g", 1, 2450),
]
N[(3, 3000)] = [
    "Torkon akarod ragadni a vezért.",
    ("+", "E", -2),
    "A lány lecsap a csavarkulccsal.",
    ("g", 3, 3800),
]
N[(3, 3050)] = [
    "Olajat engedsz az útra, és a motor fejre áll.",
    ("g", 0, 4800),
]
N[(3, 3100)] = [
    "Hamarosan egy elágazáshoz érsz.",
    ("ask", "Merre fordulsz?", [
        ("Balra", (0, 4600), None),
        ("Jobbra", (1, 2650), None)]),
]
N[(3, 3150)] = [
    "A férfi eszméletlenül esik össze.",
    "Az Interceptorhoz rohansz, és elhajtasz.",
    ("g", 2, 350),
]
N[(3, 3200)] = [
    ("end", "A benzined elfogyott. Gyalog indulsz vissza Új Reménybe."),
]
N[(3, 3250)] = [
    ("g", 2, 4300),
]
N[(3, 3300)] = [
    "A férfi leüt.",
    ("g", 0, 5000),
]
N[(3, 3350)] = [
    "A férfi észrevesz, és riasztja a társait.",
    ("end", "A Pusztulás Kutyái szitává lőnek."),
]
N[(3, 3400)] = [
    "Kihúzod a tőrt, de támadód pisztolyt ránt.",
    ("g", 1, 4660),
]
N[(3, 3450)] = [
    "A férfi elveszi a pénzt, és arrébb áll a busszal.",
    ("+", "HH", -200),
    "Áthajtasz az alagúton.",
    ("g", 1, 1500),
]
N[(3, 3500)] = [
    "A kereked tönkre ment.",
    ("if", "PK", ">", 0, [("g", 0, 950)]),
    ("g", 3, 1800),
]
N[(3, 3550)] = [
    "Balra fordulsz nyugat felé.",
    ("g", 2, 1250),
]
N[(3, 3600)] = [
    "Szétlövöd az akadályt, és a nyíláson át két motoros tör ki.",
    ("ask", "Mit teszel?", [
        ("Utánuk mész", (0, 4750), None),
        ("Futni hagyod őket", (3, 450), None)]),
]
N[(3, 3650)] = [
    "A motor ráfut a szögekre, és felbukfencezik.",
    ("g", 0, 4800),
]
N[(3, 3700)] = [
    "Késsel a kézben várod a kutyát.",
    ("cmbP", "E", "U", 0, 7, 5, 2, (0, 4450), ("end", "Meghaltál.")),
]
N[(3, 3705)] = [
    ("cmbP", "E", "U", 0, 7, 5, 2, (0, 4450), ("end", "Meghaltál.")),
]
N[(3, 3750)] = [
    ("g", 3, 150),
]
N[(3, 3800)] = [
    "A vezér elveszti az eszméletét. Megkötözöd.",
    "Délnek hajtasz.",
    ("g", 0, 4500),
]
N[(3, 3850)] = [
    "Cikázol, és viszonzod a tüzet.",
    ("skill_gt", (1, 4550), (3, 1900)),
]
N[(3, 3950)] = [
    "Meg akarod akadályozni a Fordot az előzésben.",
    ("ask", "Merre rántod a kormányt?", [
        ("Balra", (0, 1000), None),
        ("Jobbra", (0, 4000), None)]),
]
N[(3, 4000)] = [
    "A kapu nyitva, és mindenki ünnepel.",
    ("end", "Visszaértél Új Reménybe. Teljesítetted a küldetést!"),
]

# ======================================================================
# Értelmező
# ======================================================================
def _cel(x):
    """(ov,ln) párrá alakít, vagy meghagyja a vég/hívás jelet."""
    return x


def jatek_harcos(ctx):
    yield ctx.mond(
        "Az országút harcosa. Ian Livingstone lapozgatós kalandkönyve, "
        "amelyet Dr. Földi János ültetett gépre. A járvány utáni pusztaság: "
        "Új Remény városa téged bíz meg, hogy a felfegyverzett Interceptorral "
        "eljuttass egy rakomány gabonát a déli olajfinomítóba, és üzemanyaggal "
        "térj vissza. A döntéseidet a felkínált számmal hozod meg.")
    while True:
        g = _uj_allas()
        yield ctx.mond(
            "A tanács a rendelkezésedre bocsát egy páncélozott Interceptort: "
            "beépített géppuska, három doboz vasszög, két olajtartály, két "
            "pótkerék, elsősegélydoboz tíz csomag gyógyszerrel és kétszáz "
            "hitel. Sok szerencsét!")
        yield ctx.mond(_statsor(g))
        vege_ok = yield from _jatszd_egy_kaland(ctx, g)
        v = yield ctx.kerdez("Újrajátszod a kalandot? (igen/nem)")
        if not str(v).strip().lower().startswith("i"):
            break
    yield ctx.vege("Köszönöm a játékot!")


def _jatszd_egy_kaland(ctx, g):
    node = (0, 50)
    hatar = 0
    while True:
        hatar += 1
        if hatar > 4000:
            yield ctx.mond("A kaland motorja elakadt – biztonságból befejezem.")
            return False
        ops = N.get(node)
        if ops is None:
            yield ctx.mond(f"(Ismeretlen helyszín: {node}. A kaland itt véget ér.)")
            return False
        ugras = yield from _futtat(ctx, g, ops)
        if ugras is None:
            # nincs explicit ugrás: a kaland vége (ritka, biztonsági)
            return True
        if ugras[0] == "VEGE":
            yield ctx.mond(ugras[1])
            yield ctx.mond(_statsor(g))
            return True
        node = ugras


def _futtat(ctx, g, ops):
    """Végrehajtja egy csomópont műveleteit; visszaad egy célt (ov,ln),
    vagy ("VEGE", szoveg), vagy None (nincs átvitel)."""
    for op in ops:
        if isinstance(op, str):
            yield ctx.mond(op)
            continue
        fajta = op[0]
        if fajta == "+":
            g[op[1]] = g.get(op[1], 0) + op[2]
        elif fajta == "cap":
            if g[op[1]] > g[op[2]]:
                g[op[1]] = g[op[2]]
        elif fajta == "lose":
            g[op[1]] -= random.randint(op[2], op[3])
        elif fajta == "die":
            if g[op[1]] < 1:
                return ("VEGE", op[2])
        elif fajta == "g":
            return (op[1], op[2])
        elif fajta == "end":
            return ("VEGE", op[1])
        elif fajta == "luck":
            dobas = _d(12)
            balszerencse = dobas > g["S"]
            g["S"] -= 1
            return op[2] if balszerencse else op[1]
        elif fajta == "skill_gt":
            if _d(12) > g["U"]:
                return op[1]
            return op[2]
        elif fajta == "armor":
            g["P"] -= _d(12)
            if g["P"] < 1:
                return ("VEGE", op[2])
            return op[1]
        elif fajta == "chance":
            if _d(op[1]) < op[2]:
                return op[3]
            return op[4]
        elif fajta == "chance_gt":
            if _d(op[1]) > op[2]:
                return op[3]
            return op[4]
        elif fajta == "af":
            a = random.randint(op[1], op[2])
            f = _d(op[3]) + g["U"]
            if a > f:
                return op[4]
            return op[5]
        elif fajta == "call":
            cel = _SPECIAL[op[1]](g)
            if cel[0] == "end":
                return ("VEGE", cel[1])
            return cel
        elif fajta == "if":
            if _felt(g, op[1], op[2], op[3]):
                cel = yield from _futtat(ctx, g, op[4])
                if cel is not None:
                    return cel
        elif fajta == "ask":
            cel = yield from _kerdes(ctx, g, op[1], op[2])
            return cel
        elif fajta == "cmbV":
            (_, poolvar, skillvar, soff, au, ae, bu, be, win, death) = op
            yield from _tuzharc(ctx, g, poolvar, skillvar, soff, au, ae, bu, be)
            if g[poolvar] < 1:
                if death[0] == "end":
                    return ("VEGE", death[1] if len(death) > 1 else "Meghaltál.")
                return death
            yield ctx.mond(_statsor(g))
            return win
        elif fajta == "cmbP":
            (_, poolvar, skillvar, soff, au, ae, le, win, death) = op
            yield from _kezitusa(ctx, g, poolvar, skillvar, soff, au, ae, le)
            if g[poolvar] < 1:
                if death[0] == "end":
                    return ("VEGE", death[1] if len(death) > 1 else "Meghaltál.")
                return death
            yield ctx.mond(_statsor(g))
            return win
    return None


def _felt(g, var, cmp, val):
    x = g.get(var, 0)
    if cmp == "==":
        return x == val
    if cmp == "<":
        return x < val
    if cmp == ">":
        return x > val
    if cmp == "<=":
        return x <= val
    if cmp == ">=":
        return x >= val
    return False


def _kerdes(ctx, g, prompt, opciok):
    # a feltételnek megfelelő opciók, 1-től sorszámozva (akadálymentes)
    probak = 0
    while True:
        elerheto = []
        for cimke, cel, felt in opciok:
            if felt is None or _felt(g, felt[0], felt[1], felt[2]):
                elerheto.append((cimke, cel))
        if not elerheto:
            return None
        probak += 1
        if probak > 25:
            # vészkijárat: sok érvénytelen próba után az első lehetőség
            return elerheto[0][1]
        yield ctx.mond(_statsor(g))
        sorok = "  ".join(f"{i + 1}: {c}." for i, (c, _) in enumerate(elerheto))
        v = yield ctx.kerdez(f"{prompt}  {sorok}")
        t = str(v).strip()
        valasztott = None
        if t.isdigit():
            idx = int(t) - 1
            if 0 <= idx < len(elerheto):
                valasztott = elerheto[idx][1]
        if valasztott is None:
            # szöveges egyezés is elfogadott
            for cimke, cel in elerheto:
                if t and t.lower() in cimke.lower():
                    valasztott = cel
                    break
        if valasztott is None:
            yield ctx.mond("Nem értem. Kérlek, üss egy számot a felajánlottak közül.")
            continue
        return valasztott
