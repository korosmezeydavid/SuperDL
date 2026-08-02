# -*- coding: utf-8 -*-
"""SuperDL SAJÁT játékok (nem retró): normál hanggal, modern + fémes
hangeffektekkel. Az ellenfelek VALÓDI nevek.

Egyelőre: Félkarú rabló (slot) és UNO. A Mille Bornes külön hullámban jön."""
import random
from collections import Counter

from ._util import igen, szam, kever, ekezet_nelkul


_NEVEK = ["Béla", "Józsi", "Hanna", "Dezső", "Feri", "Ákos", "Erzsi", "Pista",
          "Kati", "Gábor", "Marika", "Sanyi", "Juli", "Laci", "Anna", "Zoli"]


def _ellenfelek(n):
    return kever(_NEVEK)[:n]


# ============================================================ FÉLKARÚ RABLÓ
_SLOT = [("cseresznye", 6), ("citrom", 6), ("szilva", 5), ("dinnye", 4),
         ("csengő", 3), ("hetes", 2), ("gyémánt", 1)]
_SLOT_HARMAS = {"hetes": 50, "gyémánt": 40, "csengő": 20, "dinnye": 14,
                "szilva": 10, "citrom": 8, "cseresznye": 6}


def _slot_dob():
    keszlet = []
    for nev, suly in _SLOT:
        keszlet += [nev] * suly
    return random.choice(keszlet)


def _slot_nyeremeny(r):
    if r[0] == r[1] == r[2]:
        return _SLOT_HARMAS.get(r[0], 10)
    cser = r.count("cseresznye")
    if cser == 2:
        return 3
    if cser == 1:
        return 1
    return 0


def jatek_slot(ctx):
    penz = 20
    yield ctx.mond(
        "FÉLKARÚ RABLÓ. Húsz érmével kezdesz, minden pörgetés egy érme. Három "
        "egyforma nagy nyeremény – a hetes és a gyémánt a legértékesebb –, de "
        "már két cseresznye is fizet. Pörgetéshez nyomj Entert; kilépéshez "
        "írd, hogy kilép.")
    while penz > 0:
        v = yield ctx.kerdez(f"{penz} érméd van. Pörgetsz? (Enter = igen, "
                             "„kilép” = vége)")
        if (v or "").strip().lower().startswith("kil"):
            break
        penz -= 1
        yield ctx.effekt("erme")
        yield ctx.effekt("porgetes")
        r = [_slot_dob(), _slot_dob(), _slot_dob()]
        yield ctx.effekt("megall")
        yield ctx.mond(f"A tárcsák: {r[0]}, {r[1]}, {r[2]}.")
        nyer = _slot_nyeremeny(r)
        if nyer > 0:
            penz += nyer
            yield ctx.effekt("nagy_nyeremeny" if nyer >= 10 else "nyeremeny")
            yield ctx.mond(f"Nyertél {nyer} érmét! Mostantól {penz} érméd van.")
        else:
            yield ctx.effekt("veszit")
            yield ctx.mond(f"Most nem jött össze. {penz} érméd maradt.")
    if penz <= 0:
        yield ctx.mond("Elfogyott az érméd. Legközelebb több szerencsét!")
    else:
        yield ctx.mond(f"Kiszálltál {penz} érmével. Szép játék volt!")
    yield ctx.vege("Köszönöm a játékot!")


# ======================================================================= UNO
_SZINEK = ["piros", "sárga", "zöld", "kék"]
_AKCIO = {"kihagy": "Kihagyás", "irany": "Irányváltó", "+2": "plusz kettő"}


def _uno_pakli():
    p = []
    for sz in _SZINEK:
        p.append((sz, "0"))
        for e in [str(i) for i in range(1, 10)] + ["kihagy", "irany", "+2"]:
            p.append((sz, e))
            p.append((sz, e))
    for _ in range(4):
        p.append(("szín", "szín"))
        p.append(("szín", "+4"))
    random.shuffle(p)
    return p


def _uno_nev(k):
    sz, e = k
    if sz == "szín":
        return "plusz négy Színkérő" if e == "+4" else "Színkérő"
    if e in _AKCIO:
        return f"{sz} {_AKCIO[e]}"
    return f"{sz} {e}"


def _uno_top_nev(szin, ertek):
    if ertek in ("szín", "+4"):
        elo = "plusz négy " if ertek == "+4" else ""
        return f"{elo}Színkérő, a kért szín {szin}"
    if ertek in _AKCIO:
        return f"{szin} {_AKCIO[ertek]}"
    return f"{szin} {ertek}"


def _uno_rakhato(k, szin, ertek):
    sz, e = k
    return sz == "szín" or sz == szin or e == ertek


def _uno_gep_valaszt(kez, szin, ertek):
    rak = [k for k in kez if _uno_rakhato(k, szin, ertek)]
    if not rak:
        return None
    nemwild = [k for k in rak if k[0] != "szín"]
    return random.choice(nemwild) if nemwild else random.choice(rak)


def _uno_gep_szin(kez):
    c = Counter(k[0] for k in kez if k[0] != "szín")
    return c.most_common(1)[0][0] if c else random.choice(_SZINEK)


def _uno_szin_parse(v):
    t = ekezet_nelkul(v).strip()
    return {"p": "piros", "s": "sárga", "z": "zöld",
            "k": "kék"}.get(t[:1], random.choice(_SZINEK)) if t else \
        random.choice(_SZINEK)


def _uno_kov(jatszo, irany, n):
    return (jatszo + irany) % n


def jatek_uno(ctx):
    nevek = _ellenfelek(3)
    jatekosok = 4
    nevlista = {0: "Te"}
    for i, n in enumerate(nevek, 1):
        nevlista[i] = n
    yield ctx.mond(
        "UNO. Te és három játékos: " + ", ".join(nevek) + ". A felső lapra "
        "színben vagy értékben egyezőt rakhatsz, vagy Színkérőt. Ha egy lapod "
        "marad, a gép bemondja: UNO! Aki elsőként fogy ki, nyer.")

    while True:
        pakli = _uno_pakli()
        dobo = []
        kezek = {i: [pakli.pop() for _ in range(7)] for i in range(jatekosok)}

        def huz(ki, db=1):
            nonlocal pakli, dobo
            for _ in range(db):
                if not pakli:
                    if len(dobo) <= 1:
                        return
                    felso = dobo[-1]
                    maradek = dobo[:-1]
                    random.shuffle(maradek)
                    pakli, dobo = maradek, [felso]
                kezek[ki].append(pakli.pop())

        while True:
            top = pakli.pop()
            if top[0] != "szín" and top[1] not in ("kihagy", "irany", "+2"):
                break
            pakli.insert(0, top)
        dobo.append(top)
        szin, ertek = top
        irany, jatszo, gyoztes = 1, 0, None

        while gyoztes is None:
            aktiv = jatszo
            kez = kezek[aktiv]
            kartya = None
            if aktiv == 0:
                rakhatok = [i for i, k in enumerate(kez)
                            if _uno_rakhato(k, szin, ertek)]
                lista = "; ".join(f"{i + 1}. {_uno_nev(k)}"
                                  for i, k in enumerate(kez))
                yield ctx.mond(f"A felső lap: {_uno_top_nev(szin, ertek)}. "
                               f"A lapjaid: {lista}.")
                if not rakhatok:
                    yield ctx.mond("Nincs rakható lapod – húzol egyet.")
                    yield ctx.effekt("kartya")
                    huz(0, 1)
                    uj = kezek[0][-1]
                    if _uno_rakhato(uj, szin, ertek):
                        v = yield ctx.kerdez(
                            f"Húztál: {_uno_nev(uj)}. Lerakod? (igen/nem)")
                        if igen(v, True):
                            kartya = uj
                    else:
                        yield ctx.mond(f"Húztál: {_uno_nev(uj)} – nem rakható.")
                else:
                    while True:
                        v = yield ctx.kerdez(
                            "Melyik lapot rakod? (szám, vagy „h” = húzol)")
                        t = (v or "").strip().lower()
                        if t.startswith("h"):
                            yield ctx.effekt("kartya")
                            huz(0, 1)
                            break
                        n = szam(t, 1, len(kez))
                        if n is None or (n - 1) not in rakhatok:
                            yield ctx.mond(
                                "Azt nem rakhatod. Rakható sorszámok: "
                                + ", ".join(str(i + 1) for i in rakhatok) + ".")
                            continue
                        kartya = kez[n - 1]
                        break
            else:
                kartya = _uno_gep_valaszt(kez, szin, ertek)
                if kartya is None:
                    yield ctx.effekt("kartya")
                    huz(aktiv, 1)
                    uj = kezek[aktiv][-1]
                    kartya = uj if _uno_rakhato(uj, szin, ertek) else None
                    if kartya is None:
                        yield ctx.mond(f"{nevlista[aktiv]} húz és passzol.")

            if kartya is not None:
                kezek[aktiv].remove(kartya)
                yield ctx.effekt("kartya")
                if kartya[0] == "szín":
                    ujszin = (_uno_szin_parse((yield ctx.kerdez(
                        "Milyen színt kérsz? (piros/sárga/zöld/kék)")))
                        if aktiv == 0 else _uno_gep_szin(kezek[aktiv]))
                    szin, ertek = ujszin, kartya[1]
                    yield ctx.mond(f"{nevlista[aktiv]} {_uno_nev(kartya)}-t "
                                   f"rakott. A kért szín: {szin}.")
                else:
                    szin, ertek = kartya
                    yield ctx.mond(f"{nevlista[aktiv]} lerakott: "
                                   f"{_uno_nev(kartya)}.")
                if len(kezek[aktiv]) == 1:
                    yield ctx.mond(f"{nevlista[aktiv]}: UNO!")
                if len(kezek[aktiv]) == 0:
                    gyoztes = aktiv
                    break
                kihagy = False
                if kartya[1] == "kihagy":
                    kihagy = True
                elif kartya[1] == "irany":
                    irany *= -1
                elif kartya[1] == "+2":
                    kov = _uno_kov(aktiv, irany, jatekosok)
                    huz(kov, 2)
                    yield ctx.mond(f"{nevlista[kov]} húz két lapot és kimarad.")
                    kihagy = True
                elif kartya[1] == "+4":
                    kov = _uno_kov(aktiv, irany, jatekosok)
                    huz(kov, 4)
                    yield ctx.mond(f"{nevlista[kov]} húz négy lapot és kimarad.")
                    kihagy = True
                jatszo = _uno_kov(aktiv, irany, jatekosok)
                if kihagy:
                    jatszo = _uno_kov(jatszo, irany, jatekosok)
            else:
                jatszo = _uno_kov(aktiv, irany, jatekosok)

        if gyoztes == 0:
            yield ctx.effekt("nagy_nyeremeny")
            yield ctx.mond("Kifogytál a lapokból – NYERTÉL!")
        else:
            yield ctx.effekt("veszit")
            yield ctx.mond(f"{nevlista[gyoztes]} fogyott ki elsőként – ő nyert. "
                           "Legközelebb sikerül!")
        v = yield ctx.kerdez("Új játék? (igen/nem)")
        if not igen(v, False):
            break
    yield ctx.vege("Köszönöm a játékot!")


# ================================================================ GÉPI ÉNEK
# A SuperDL saját formáns-szintetizátora dallamra énekel. Nem játék, hanem
# kreatív eszköz: taníts a gépnek egy dalt (szótag + hangnév + hossz soronként),
# és elénekli a saját hangján. Semmi idegen hangminta – 100% saját szintézis.

from .. import enek as _EN

_ENEK_SUGO = (
    "GÉPI ÉNEK – így taníts a gépnek egy dalt. Soronként adj meg egy hangot "
    "ebben a formában: SZÓTAG HANGNÉV HOSSZ. Például: bo g4 0.4 – a bo szótagot "
    "a g4 hangon, 0,4 másodpercig. A SZÓTAG az, amit énekeljen (pl. bo, ci, lá); "
    "ha csak dallam kell szöveg nélkül, írj a szótag helyére kötőjelet, például: "
    "kötőjel c4 0.5. A HANGNÉV egy betű – c, d, e, f, g, a, h – és egy oktávszám, "
    "ahol a 4 a középső; például c4, g4, c5. A nagyobb oktávszám magasabb hang: a "
    "c5 egy oktávval a c4 fölött van. A HOSSZ másodpercben, például 0.4 vagy 0.5, "
    "vagy szóval: egész, fél, negyed, nyolcad. Parancsok: énekeld – elénekli, "
    "amit eddig beírtál; súgó – ez a leírás; példa skála vagy példa boci – egy "
    "beépített dal; töröl – üríti a dalt; kész – kilépés.")


def jatek_enektanito(ctx):
    yield ctx.mond(
        "Gépi ének! Itt megtaníthatsz a gépnek egy dalt, és a saját "
        "formáns-hangján elénekli neked. Soronként adj meg egy hangot így: "
        "szótag, hangnév, hossz – például: bo g4 0.4. A részletes leíráshoz írd "
        "azt, hogy súgó. Beépített példáért írd: példa skála, vagy példa boci.")
    dal = []
    while True:
        v = yield ctx.kerdez("Adj meg egy hangot (szótag hangnév hossz), vagy "
                             "parancsot (énekeld / súgó / példa / töröl / kész):")
        s = (v or "").strip()
        al = ekezet_nelkul(s.lower())
        if not s:
            continue
        if al in ("kesz", "vege", "kilepes"):
            yield ctx.vege("Viszlát! Bármikor visszajöhetsz zenélni.")
            return
        if al == "sugo":
            yield ctx.mond(_ENEK_SUGO)
            continue
        if al == "torol":
            dal = []
            yield ctx.mond("Üres a dal, kezdheted elölről.")
            continue
        if al.startswith("pelda"):
            kulcs = ("boci" if "boci" in al
                     else "skála" if "skala" in al else None)
            if kulcs is None:
                yield ctx.mond("Példák: példa skála, vagy példa boci.")
                continue
            dal = list(_EN.PELDAK[kulcs])
            yield ctx.mond(f"Betöltöttem a(z) {kulcs} példát, most elénekelem!")
            yield ctx.enek(dal)
            continue
        if al in ("enekeld", "enek", "dal", "enekelj"):
            if not dal:
                yield ctx.mond("Még nincs egyetlen hang sem. Adj meg legalább "
                               "egyet, vagy próbáld: példa skála.")
                continue
            yield ctx.mond(f"Éneklem a {len(dal)} hangból álló dalt!")
            yield ctx.enek(dal)
            continue
        hang = _EN.parse_sor(s)
        if hang is None:
            yield ctx.mond("Ezt nem értem. A formátum: szótag hangnév hossz, "
                           "például: lá a4 0.5. Segítségért írd: súgó.")
            continue
        dal.append(hang)
        szotag, hangnev, hossz = hang
        yield ctx.mond(f"Felvéve: {szotag or 'dúdolás'}, a {hangnev} hangon, "
                       f"{hossz} másodperc. Eddig {len(dal)} hang a dalban. Ha "
                       "kész vagy, írd: énekeld.")


# ================================================================ SZERENCSEKERÉK
# SAJÁT, akadálymentes kerék-és-szó játék. A rejtett magyar kifejezést kell
# kitalálni: pörgetsz (mássalhangzóért pénz), magánhangzót veszel, vagy megfejtesz.
# Hangok: a fejlesztő saját anyaga (Suno / vállalt effektek) a szerencsekerek_hang
# mappából; ahol nincs, ott csend. A rejtvénybank a szerencsekerek_rejtvenyek.json.
_SZK_MGH = set("aáeéiíoóöőuúüű")
_SZK_MEZOK = [100, 200, 300, 400, 500, 600, 800, 1000, 300, 500, "csod", "passz"]
# a gép betű-tippjeinek sorrendje – MAGÁNHANGZÓK is (a felhasználó kérésére bármely
# betű mondható/vehető, nem csak a klasszikus mássalhangzó–magánhangzó felosztás)
_SZK_GYAKORI = list("eatlnsoárzkémigbdvhuóöőüűíúpjcfy")
_SZK_MGH_AR = 250
_SZK_FORDULO = 3
_szk_cache = None

# ---- szellemes beszólások, hogy éljen a játék (nem sablonos) --------------
_SZK_NAGY = (
    "Na nézd ezt a szerencse fiát! Csak el ne puskázd, jó betűt válassz!",
    "Ekkora summa? Fortuna ma egyenesen beléd szeretett!",
    "Hűha, ez aztán a fogás! Most jó szemed legyen a betűkhöz!",
    "Pörög a szerencse, potyog a pénz! Válassz okosan!",
    "Ez a mező kész kis aranybánya! Ne szórd el egy rossz betűvel!",
    "Csillog a szemed, mi? Ekkora tétnél illik jól tippelni!",
    "Ez a szám kész álom! Koronázd meg egy jó betűvel!",
    "Hallod, hogy csörög? Az a te szerencséd muzsikál!",
    "Fortuna ma bőkezű! Élj a lehetőséggel, barátom!",
    "Ekkora tétnél a kezed se remegjen! Nyugalom, és tippelj!",
    "Ez a mező zsíros falat! Ne hagyd a tányéron!",
    "Most jött el a te pillanatod! Egy jó betű, és gazdag vagy!",
)
_SZK_CSOD = (
    "Barátom, ma Fortuna nem veled megy randira!",
    "A szerencse fogta a kalapját és fütyörészve elsétált.",
    "Puff neki! Ennyit a vagyonról – de a fejed még megvan, az is valami!",
    "Ilyen a szerencse: hol csók, hol pofon.",
    "Fortuna most a bajsza alatt kuncog rajtad.",
    "Nulla forint, tiszta lap. Legalább könnyű lett a zsebed!",
    "Ó, a mindenit! A kerék most jól megtréfált téged.",
    "Elszállt a pénz, mint a füst. Sebaj, jön a következő!",
    "Ez fájt, mi? A szerencse bizony forgandó.",
    "Csőd van! De ne búsulj, a mosoly ingyen van.",
    "A kerék most cserben hagyott. Legközelebb megbékül veled.",
    "Zsupsz, oda a vagyon! De a becsületed megmaradt.",
)
_SZK_PASSZ = (
    "A kerék ma kicsit szűkmarkú veled.",
    "Na, ezt a kört elpasszoltad. Sebaj, mindjárt jössz megint!",
    "Fortuna épp kávézni ment, de visszanéz még.",
    "Kimaradt egy kör – legalább a pénzed megmaradt!",
    "Passz! Ilyen is van, ne csüggedj.",
    "A kerék most passzol, mint egy jó focista.",
    "Egy kör pihenő – gyűjtsd az erőt a következőre!",
    "Most kihagytad, de a szerencse köszön még.",
    "Passz. Legalább van időd gondolkodni!",
)
_SZK_JO = (
    "Szép találat, gyűlik a pénz!",
    "Ez az, a betű bejött!",
    "Telitalálat! Csak így tovább!",
    "Ügyes, jó orrod van a betűkhöz!",
    "Bejött! Fortuna elismerően bólint.",
    "Zseniális megérzés, barátom!",
    "Erre varrjál gombot! Príma betű.",
    "Neked áll a világ, csak így tovább!",
    "Beletaláltál a közepébe! Bravó!",
    "Ez az! A betűk ma barátkoznak veled.",
    "Kapásból eltaláltad! Le a kalappal.",
)
_SZK_ROSSZ = (
    "Ez most mellément. Legközelebb sikerül!",
    "Hmm, nincs ott. Fortuna somolyog a bajsza alatt.",
    "Mellé! De fel a fejjel, jön még jobb kör.",
    "A betűk ma bujócskáznak veled.",
    "Ajaj, ez nem az igazi. Majd legközelebb!",
    "A betű elbújt előled. Semmi baj!",
    "Nem jött össze – de a játék még hosszú!",
    "Ez a betű ma szabadnapos. Próbálj mást!",
    "Elvétetted, de a szerencse nem haragtartó.",
    "Nincs benne. Sebaj, sokan járnak így!",
)
_SZK_MEGFEJT = (
    "Bravó, ezt fejből! Zseniális!",
    "Megfejtve! Fortuna most vastapsot ad.",
    "Ez az! A rejtvény megtört, le a kalappal!",
    "Kitalálva! Okos fej, okos fej!",
    "Telitalálat a megfejtésben! Csúcs vagy!",
    "Ez az agymunka! Kalapemelés előtted!",
    "Fejben megvolt! Elképesztő teljesítmény!",
    "A rejtvény térdre kényszerült előtted!",
    "Telitalálat! Fortuna elismerően füttyent.",
    "Megvan a megfejtés! Így kell ezt csinálni!",
    "Ész a köbön! A rejtvény esélyt sem kapott.",
)


# a gép szurkál a többieknek (emberhez ÉS géphez is) – {nev} a megszólított
_SZK_BESZOL_JATEKOSNAK = (
    "{nev}, te bundázol, hogy ilyen jók a betűid!",
    "{nev}, reméljük a következő pörgetésed csőd lesz!",
    "{nev}, ne bízd el magad, mindjárt fordul a kocka!",
    "{nev}, ezt a szerencsét! Biztos a kerékkel súgtok össze?",
    "{nev}, én a helyedben nem ünnepelnék korán!",
    "{nev}, add kölcsön a szerencséd, jó?",
    "{nev}, csak halkan mondom: engem úgysem versz meg!",
    "{nev}, na, most izzadj csak egy kicsit!",
    "{nev}, a te szerencséd az én malmomra hajtja a vizet!",
    "{nev}, egy jó kis csőd rád férne, nem gondolod?",
    "{nev}, remélem, nem álmodban tanultad a betűket!",
    "{nev}, a szerencséd hamarosan szabadságra megy!",
    "{nev}, csak halkan: én azért egy fokkal jobb vagyok. :)",
    "{nev}, a következő pörgetésednek szurkolok… hogy csőd legyen!",
    "{nev}, ne szokj hozzá a nyeréshez, mert vége lesz!",
    "{nev}, a kerék engem szeret jobban, majd meglásd!",
    "{nev}, szép-szép, de a végén úgyis én kacagok!",
    "{nev}, most jól megy, mi? Élvezd, amíg tart!",
)


def _szk_beszol(lista):
    return random.choice(lista)


def _szk_nevetes():
    """Egy véletlen közönség-nevetés effekt neve (a poénokhoz). A fájlok a
    szerencsekerek_hang mappában: nevetes1/nevetes2. Ha nincs ott, a felület
    csendben átugorja."""
    return "nevetes" + str(random.randint(1, 2))


def _szk_rejtvenyek():
    """(kategória, megoldás) párok a bankból. Ha a fájl hiányzik, beépített kis lista."""
    global _szk_cache
    if _szk_cache is None:
        import json
        import os
        p = os.path.join(os.path.dirname(__file__), "szerencsekerek_rejtvenyek.json")
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            _szk_cache = [(r["kategoria"], r["megoldas"]) for r in data
                          if r.get("megoldas")]
        except Exception:
            _szk_cache = [("Közmondás", "Ki korán kel aranyat lel"),
                          ("Szólás", "Zsákbamacska"),
                          ("Étel és ital", "Gulyásleves")]
    return _szk_cache


def _szk_valaszt(rejtvenyek):
    """A forduló rejtvénye (tesztben monkeypatchelhető)."""
    return random.choice(rejtvenyek)


def _szk_maganhangzo(ch):
    return len(ch) == 1 and ch.lower() in _SZK_MGH


def _szk_elofordul(megoldas, betu):
    b = betu.lower()
    return sum(1 for ch in megoldas if ch.lower() == b)


def _szk_tabla(megoldas, felfedett):
    """Akadálymentes tábla-felolvasás: szavanként a betűk, a rejtettek „üres"."""
    reszek = []
    for szo in megoldas.split(" "):
        jelek = []
        betuk = 0
        for ch in szo:
            if not ch.isalpha():
                jelek.append(ch)
            elif ch.lower() in felfedett:
                jelek.append(ch.upper())
                betuk += 1
            else:
                jelek.append("üres")
                betuk += 1
        reszek.append(f"{betuk} betű: " + ", ".join(jelek))
    return "A rejtvény — " + " ; új szó — ".join(reszek) + "."


def _szk_egyezik(tipp, megoldas):
    import re
    norm = lambda s: re.sub(r"[^a-z0-9]", "", ekezet_nelkul(s))
    return bool(norm(tipp)) and norm(tipp) == norm(megoldas)


def _szk_porget():
    m = random.choice(_SZK_MEZOK)
    if m in ("csod", "passz"):
        return (m,)
    return ("penz", m)


def _szk_gep_betu(felfedett):
    """A gép következő betű-tippje (magánhangzó is lehet)."""
    for c in _SZK_GYAKORI:
        if c not in felfedett:
            return c
    return None


def _szk_mond(ctx, text):
    """Kimond egy szöveget, majd megvárja, amíg a felolvasó nagyjából végez – hogy
    a RÁKÖVETKEZŐ hang ne olvadjon a szövegre, és hallható legyen a beszólás/
    kommentár. Becslés: kb. 16 karakter másodpercenként."""
    yield ctx.mond(text)
    yield ctx.szunet(min(12000, 400 + len(text) * 60))


def _szk_csalodas():
    """Egy véletlen csalódott közönség-hang neve (csőd / rossz tipp után)."""
    return random.choice(("boo", "awww", "ooo"))


def _szk_ember_kor(ctx, nev, megoldas, felfedett, korpenz, bank, nevek):
    """Egy emberi kör. Visszaad: megoldva (bool). Ha False, a kör átszáll."""
    yield ctx.mond(f"{nev} következik. " + _szk_tabla(megoldas, felfedett))
    while True:
        v = ((yield ctx.kerdez(
            f"{nev}, mit lépsz? (P = pörgetés és betű, V = betűt veszek "
            f"{_SZK_MGH_AR}-ért, M = megfejtés, ? = tábla; pénzem = a pénzed; "
            "többiek = mindenki pénze)")) or "").strip().lower()
        if v.startswith("?"):
            yield ctx.mond(_szk_tabla(megoldas, felfedett)
                           + f" A fordulóban gyűjtött pénzed: {korpenz[nev]}.")
            continue
        if v.startswith("pénzem") or v == "pénz":
            yield ctx.mond(f"{nev}, a fordulóban {korpenz[nev]} forintot gyűjtöttél, "
                           f"a bankodban eddig {bank[nev]} forint van.")
            continue
        if "többiek" in v or "mindenki" in v or v == "állás":
            reszek = [f"{n}: {bank[n]} a bankban, {korpenz[n]} a fordulóban"
                      for n in nevek]
            yield ctx.mond("Mindenki pénze — " + "; ".join(reszek) + ".")
            continue
        if v.startswith("m"):
            tipp = ((yield ctx.kerdez("Mondd a teljes megfejtést!")) or "").strip()
            if _szk_egyezik(tipp, megoldas):
                return True
            yield ctx.effekt_var("sikertelen_tipp")
            yield from _szk_mond(ctx, "Sajnos nem talált. "
                                 + _szk_beszol(_SZK_ROSSZ) + " A kör átszáll.")
            yield ctx.effekt_var(_szk_csalodas())
            return False
        if v.startswith("v"):
            if korpenz[nev] < _SZK_MGH_AR:
                yield ctx.mond(f"Ehhez legalább {_SZK_MGH_AR} forint kell a "
                               "fordulóban. Válassz mást.")
                continue
            betu = ((yield ctx.kerdez("Melyik betűt veszed meg? (bármely betű)"))
                    or "").strip().lower()
            if len(betu) != 1 or not betu.isalpha():
                yield ctx.mond("Az nem egy betű. Válassz mást.")
                continue
            if betu in felfedett:
                yield ctx.mond("Ezt a betűt már megvették vagy mondták. Válassz mást.")
                continue
            korpenz[nev] -= _SZK_MGH_AR
            yield ctx.effekt_var("maganhangzo_vasarlas")
            db = _szk_elofordul(megoldas, betu)
            felfedett.add(betu)
            if db:
                yield ctx.mond(f"Van benne {db} darab {betu.upper()}! "
                               + _szk_tabla(megoldas, felfedett))
                continue
            yield ctx.mond(f"Nincs benne {betu.upper()}. A {_SZK_MGH_AR} forint "
                           "elúszott, a kör átszáll.")
            return False
        # bármi más = pörgetés
        yield ctx.effekt_var("kerekporges")   # megvárjuk a pörgés-hang végét
        mezo = _szk_porget()
        if mezo[0] == "csod":
            korpenz[nev] = 0
            yield ctx.effekt_var("csod")
            yield from _szk_mond(ctx, "A kerék megállt: CSŐD! "
                                 + _szk_beszol(_SZK_CSOD)
                                 + " A fordulóban gyűjtött pénzed elveszett, a kör átszáll.")
            yield ctx.effekt_var(_szk_csalodas())
            return False
        if mezo[0] == "passz":
            yield ctx.effekt_var("passz")
            yield ctx.mond("A kerék megállt: PASSZ! " + _szk_beszol(_SZK_PASSZ)
                           + " A pénzed marad, de a kör átszáll.")
            return False
        osszeg = mezo[1]
        if osszeg >= 600:
            yield ctx.mond(_szk_beszol(_SZK_NAGY))
        betu = ((yield ctx.kerdez(f"A kerék megállt: {osszeg} forint. Mondj egy "
                "betűt!")) or "").strip().lower()
        if len(betu) != 1 or not betu.isalpha():
            yield ctx.mond("Az nem egy betű. A kör átszáll.")
            return False
        if betu in felfedett:
            yield ctx.mond("Ezt a betűt már mondták. A kör átszáll.")
            return False
        db = _szk_elofordul(megoldas, betu)
        felfedett.add(betu)
        if db:
            korpenz[nev] += osszeg * db
            yield ctx.effekt_var("sikeres_tipp")
            uzenet = (f"Van benne {db} darab {betu.upper()}! Kaptál "
                      f"{osszeg * db} forintot.")
            if random.random() < 0.5:
                uzenet += " " + _szk_beszol(_SZK_JO)
            yield ctx.mond(uzenet + " " + _szk_tabla(megoldas, felfedett))
            continue
        yield ctx.effekt_var("sikertelen_tipp")
        rossz = f"Nincs benne {betu.upper()}. A kör átszáll."
        if random.random() < 0.5:
            rossz += " " + _szk_beszol(_SZK_ROSSZ)
        yield from _szk_mond(ctx, rossz)
        yield ctx.effekt_var(_szk_csalodas())
        return False


def _szk_gep_kor(ctx, nev, megoldas, felfedett, korpenz, nevek, szint=2):
    """A gép köre. Visszaad: megoldva (bool). A gép be is szól a többieknek
    (emberhez ÉS géphez is), és apró szüneteket tart, hogy ki lehessen élvezni.
    A `szint` (1 kezdő … 3 profi) szabja, MENNYIRE hamar próbál megfejteni."""
    # nehézség: hány rejtett betűnél mer megfejteni, milyen eséllyel, és mekkora a
    # véletlen korai megfejtés esélye. A KEZDŐ gép csak a legvégén old meg.
    kuszob = {1: 1, 2: 3, 3: 5}.get(szint, 3)
    eselye = {1: 0.5, 2: 0.6, 3: 0.75}.get(szint, 0.6)
    korai = {1: 0.0, 2: 0.03, 3: 0.08}.get(szint, 0.03)
    yield ctx.mond(f"{nev} következik.")
    while True:
        # néha beszól valamelyik ellenfélnek – a beszólás HALLHATÓ, utána a nevetés
        masok = [n for n in nevek if n != nev]
        if masok and random.random() < 0.3:
            cel = random.choice(masok)
            yield from _szk_mond(ctx, nev + ": "
                                 + _szk_beszol(_SZK_BESZOL_JATEKOSNAK).format(nev=cel))
            yield ctx.effekt_var(_szk_nevetes())     # nevet a közönség a poénon
        rejtett = [ch for ch in megoldas if ch.isalpha() and ch.lower() not in felfedett]
        if not rejtett or (len(rejtett) <= kuszob and random.random() < eselye) \
                or random.random() < korai:
            yield ctx.mond(f"{nev} megpróbálja megfejteni…")
            yield ctx.szunet(1200)
            return True
        yield ctx.effekt_var("kerekporges")   # a pörgés-hang végéig várunk
        mezo = _szk_porget()
        if mezo[0] == "csod":
            korpenz[nev] = 0
            yield ctx.effekt_var("csod")
            yield from _szk_mond(ctx, f"A kerék megállt: {nev} Csődöt pörgetett! "
                                 + _szk_beszol(_SZK_CSOD) + " A kör átszáll.")
            yield ctx.effekt_var(_szk_csalodas())
            return False
        if mezo[0] == "passz":
            yield ctx.effekt_var("passz")
            yield ctx.mond(f"A kerék megállt: {nev} Passzt pörgetett. "
                           + _szk_beszol(_SZK_PASSZ) + " A kör átszáll.")
            return False
        osszeg = mezo[1]
        if osszeg >= 600:
            yield from _szk_mond(ctx, f"{nev} elégedetten dörzsöli a tenyerét: "
                                 f"{osszeg} forintos mező!")
            yield ctx.effekt_var(_szk_nevetes())
        jelolt = _szk_gep_betu(felfedett)
        if jelolt is None:
            yield ctx.mond(f"{nev} inkább megfejt.")
            yield ctx.szunet(1200)
            return True
        db = _szk_elofordul(megoldas, jelolt)
        felfedett.add(jelolt)
        if db:
            korpenz[nev] += osszeg * db
            yield ctx.effekt_var("sikeres_tipp")
            uz = (f"{nev} a {jelolt.upper()} betűt mondta: {db} darab! "
                  f"Kap {osszeg * db} forintot.")
            if random.random() < 0.4:
                uz += " " + _szk_beszol(_SZK_JO)
            yield ctx.mond(uz)
            yield ctx.szunet(900)             # apró szünet a gép pörgetései közt
            continue
        yield ctx.effekt_var("sikertelen_tipp")
        uz = (f"{nev} a {jelolt.upper()} betűt mondta, de nincs benne. "
              "A kör átszáll.")
        if random.random() < 0.4:
            uz += " " + _szk_beszol(_SZK_ROSSZ)
        yield from _szk_mond(ctx, uz)
        yield ctx.effekt_var(_szk_csalodas())
        return False


def jatek_szerencsekerek(ctx):
    # az üdvözlést KIMONDJUK és megvárjuk, mielőtt a főcím-zene rászólna
    yield from _szk_mond(ctx, "SZERENCSEKERÉK! A népszerű kerék-és-szó játék "
                         "akadálymentes, saját változata.")
    yield ctx.effekt("focim")
    rejtvenyek = _szk_rejtvenyek()

    v = yield ctx.kerdez("Hány EMBER játékos lesz? (1–4)")
    n_ember = szam(v, 1, 4) or 1
    nevek = []
    for i in range(n_ember):
        nv = (((yield ctx.kerdez(f"{i + 1}. játékos neve?")) or "").strip()
              or f"{i + 1}. játékos")
        while nv in nevek:                       # ne ütközzön két azonos név
            nv += " II"
        nevek.append(nv)
    v = yield ctx.kerdez("Hány GÉP-ellenfél szálljon be? (0–4)")
    n_gep = szam(v, 0, 4) or 0
    szint = 2                                    # a gépek okossága (1 kezdő … 3 profi)
    if n_gep > 0:
        v = yield ctx.kerdez("Milyen okosak legyenek a gépek? "
                             "(1 = kezdő, 2 = közepes, 3 = profi)")
        szint = szam(v, 1, 3) or 2
    gep_halmaz = set()
    szabad = [x for x in kever(_NEVEK) if x not in nevek]  # a gépek NEVET kapnak
    for i in range(n_gep):
        gnev = szabad[i] if i < len(szabad) else f"Gépjátékos {i + 1}"
        nevek.append(gnev)
        gep_halmaz.add(gnev)

    bank = {nev: 0 for nev in nevek}
    if len(nevek) <= 2:
        tarsak = " és ".join(nevek)
    else:
        tarsak = ", ".join(nevek[:-1]) + " és " + nevek[-1]
    yield ctx.mond(f"Játszik: {tarsak}. Három forduló, a legtöbb pénzt gyűjtő "
                   "nyer. Sok szerencsét!")

    for fordulo in range(1, _SZK_FORDULO + 1):
        kat, megoldas = _szk_valaszt(rejtvenyek)
        felfedett = set()
        korpenz = {nev: 0 for nev in nevek}
        yield ctx.mond(f"{fordulo}. forduló! A kategória: {kat}.")
        yield ctx.mond(_szk_tabla(megoldas, felfedett))
        aktiv = 0
        biztonsag = 0
        while True:
            biztonsag += 1
            if biztonsag > 400:
                yield ctx.mond(f"Lejárt az idő! A megfejtés: {megoldas}.")
                break
            nev = nevek[aktiv]
            ember = nev not in gep_halmaz
            if ember:
                megoldva = yield from _szk_ember_kor(ctx, nev, megoldas, felfedett,
                                                     korpenz, bank, nevek)
            else:
                megoldva = yield from _szk_gep_kor(ctx, nev, megoldas, felfedett,
                                                   korpenz, nevek, szint)
            if megoldva:
                for ch in megoldas:
                    felfedett.add(ch.lower())
                bank[nev] += korpenz[nev]
                yield ctx.effekt_var("megfejtes_siker")
                yield ctx.mond(f"{nev} megfejtette a rejtvényt: {megoldas}! "
                               + _szk_beszol(_SZK_MEGFEJT)
                               + f" Ebben a fordulóban {korpenz[nev]} forintot nyert.")
                break
            aktiv = (aktiv + 1) % len(nevek)
        yield ctx.mond("Állás: "
                       + ", ".join(f"{nev}: {bank[nev]}" for nev in nevek) + " forint.")

    yield ctx.effekt_var("jatek_vege")
    gyoztes = max(bank, key=bank.get)
    yield from _szk_mond(ctx, f"Vége a játéknak! A győztes: {gyoztes}, "
                         f"{bank[gyoztes]} forinttal. Gratulálok!")
    yield ctx.effekt_var("taps")      # tapsvihar a győztesnek
    yield ctx.vege("Köszönöm a játékot!")
