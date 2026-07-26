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
