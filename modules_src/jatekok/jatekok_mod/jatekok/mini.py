# -*- coding: utf-8 -*-
"""A JATEK.EXE gyűjtemény mini-játékai: Dominó, Tőzsde, Korong (Reversi),
Nyúlfarm, Hamurabi, Mokita.

Ezek klasszikus, KÖZKINCS játékmechanikák akadálymentes másai. A szerzőt
egyelőre nem ismerjük – a felület „várjuk a szerző jelentkezését" felirattal
indítja őket. A Dominónál és a Korongnál az üres bevitel (Enter) automatikus
lépést kér: vakon is gyorsan játszható, és a gép segít, ha elakadsz."""
import random

from ._util import igen, szam


# ===================================================================== DOMINÓ
def _domino_illik(ko, e):
    return e in ko


def _domino_masik(ko, e):
    return ko[1] if ko[0] == e else ko[0]


def jatek_domino(ctx):
    yield ctx.mond(
        "DOMINÓ. Huszonnyolc kőből osztunk, neked és a gépnek hét-hetet. A "
        "lánc két végéhez illesztünk; a kő egyik száma egyezzen a vég számával. "
        "Írd be a követ, például: 3 5. Enter: automatikus lépés. „h”: húzol a "
        "készletből. Aki előbb kifogy a kövekből, nyer.")
    keszlet = [(a, b) for a in range(7) for b in range(a, 7)]
    random.shuffle(keszlet)
    en = [keszlet.pop() for _ in range(7)]
    gep = [keszlet.pop() for _ in range(7)]
    elso = keszlet.pop()
    bal, jobb = elso
    yield ctx.mond(f"A kezdő kő: {elso[0]}-{elso[1]}. A lánc két vége most "
                   f"{bal} és {jobb}.")
    passzok = 0
    while True:
        # --- játékos ---
        jatszhato = [k for k in en if _domino_illik(k, bal) or _domino_illik(k, jobb)]
        kez = ", ".join(f"{a}-{b}" for a, b in en)
        yield ctx.mond(f"A köveid: {kez}. A lánc végei: {bal} és {jobb}.")
        if not jatszhato and not keszlet:
            yield ctx.mond("Nem tudsz lépni és a készlet is üres – passzolsz.")
            passzok += 1
        else:
            lepett = False
            while not lepett:
                v = yield ctx.kerdez("Melyik követ rakod le? (pl. 3 5; Enter = "
                                     "automatikus; h = húzol)")
                t = (v or "").strip().lower()
                if t == "h":
                    if keszlet:
                        uj = keszlet.pop()
                        en.append(uj)
                        yield ctx.mond(f"Húztál egy követ: {uj[0]}-{uj[1]}.")
                        jatszhato = [k for k in en
                                     if _domino_illik(k, bal) or _domino_illik(k, jobb)]
                        continue
                    yield ctx.mond("A készlet üres, nem húzhatsz.")
                    continue
                if t == "":
                    if not jatszhato:
                        if keszlet:
                            uj = keszlet.pop()
                            en.append(uj)
                            yield ctx.mond(f"Nincs léphető köved – húztál egyet: "
                                           f"{uj[0]}-{uj[1]}.")
                            jatszhato = [k for k in en
                                         if _domino_illik(k, bal) or _domino_illik(k, jobb)]
                            continue
                        yield ctx.mond("Nincs lépésed és a készlet üres – "
                                       "passzolsz.")
                        passzok += 1
                        lepett = True
                        break
                    ko = jatszhato[0]
                else:
                    szamok = [int(c) for c in t if c.isdigit()]
                    if len(szamok) < 2:
                        yield ctx.mond("Két számot kérek, például: 3 5.")
                        continue
                    ko = (min(szamok[:2]), max(szamok[:2]))
                    if ko not in en:
                        yield ctx.mond("Ilyen köved nincs.")
                        continue
                    if not (_domino_illik(ko, bal) or _domino_illik(ko, jobb)):
                        yield ctx.mond("Ez a kő egyik véghez sem illik.")
                        continue
                # lerakás
                if _domino_illik(ko, bal):
                    bal = _domino_masik(ko, bal)
                else:
                    jobb = _domino_masik(ko, jobb)
                en.remove(ko)
                passzok = 0
                lepett = True
                yield ctx.mond(f"Leraktad a(z) {ko[0]}-{ko[1]} követ. A lánc "
                               f"végei: {bal} és {jobb}.")
        if not en:
            yield ctx.mond("Kifogytál a kövekből – NYERTÉL!")
            break
        # --- gép ---
        gjatszhato = [k for k in gep
                      if _domino_illik(k, bal) or _domino_illik(k, jobb)]
        while not gjatszhato and keszlet:
            gep.append(keszlet.pop())
            gjatszhato = [k for k in gep
                          if _domino_illik(k, bal) or _domino_illik(k, jobb)]
        if gjatszhato:
            ko = gjatszhato[0]
            if _domino_illik(ko, bal):
                bal = _domino_masik(ko, bal)
            else:
                jobb = _domino_masik(ko, jobb)
            gep.remove(ko)
            passzok = 0
            yield ctx.mond(f"A gép leteszi a(z) {ko[0]}-{ko[1]} követ. A lánc "
                           f"végei: {bal} és {jobb}.")
        else:
            yield ctx.mond("A gép passzol.")
            passzok += 1
        if not gep:
            yield ctx.mond("A gép fogyott ki előbb. Ezúttal a gép nyert!")
            break
        if passzok >= 2:
            en_pont = sum(a + b for a, b in en)
            gep_pont = sum(a + b for a, b in gep)
            if en_pont < gep_pont:
                yield ctx.mond(f"A játék beállt. A te köveid értéke {en_pont}, "
                               f"a gépé {gep_pont} – NYERTÉL!")
            elif gep_pont < en_pont:
                yield ctx.mond(f"A játék beállt. A te köveid értéke {en_pont}, "
                               f"a gépé {gep_pont} – a gép nyert.")
            else:
                yield ctx.mond("A játék beállt, és a kövek értéke egyenlő – "
                               "döntetlen.")
            break
    yield ctx.vege("Köszönöm a játékot!")


# ===================================================================== TŐZSDE
def jatek_tozsde(ctx):
    penz, reszveny, ar = 1000, 0, 100
    yield ctx.mond(
        "TŐZSDE. Ezer pénzed van. Tíz napon át kereskedhetsz egy részvénnyel: "
        "vegyél olcsón, adj el drágán. Minden nap után változik az ár.")
    for nap in range(1, 11):
        yield ctx.mond(f"{nap}. nap. A részvény ára {ar}. Pénzed {penz}, "
                       f"részvényed {reszveny} darab.")
        v = yield ctx.kerdez("Mit teszel? v = veszel, e = eladsz, t = tartasz")
        t = (v or "").strip().lower()
        if t.startswith("v") and penz >= ar:
            v = yield ctx.kerdez(f"Hány darabot veszel? (max {penz // ar})")
            db = szam(v, 0, penz // ar) or 0
            reszveny += db
            penz -= db * ar
            if db:
                yield ctx.mond(f"Vettél {db} darabot.")
        elif t.startswith("e") and reszveny > 0:
            v = yield ctx.kerdez(f"Hány darabot adsz el? (van {reszveny})")
            db = szam(v, 0, reszveny) or 0
            reszveny -= db
            penz += db * ar
            if db:
                yield ctx.mond(f"Eladtál {db} darabot.")
        else:
            yield ctx.mond("Kihagyod ezt a napot.")
        ar = max(5, int(ar * random.uniform(0.8, 1.25)))
    penz += reszveny * ar
    yield ctx.mond(f"A tőzsdezárás után a részvényeidet {ar}-es áron beváltva "
                   f"a vagyonod {penz}.")
    if penz > 1000:
        yield ctx.mond("Nyereséggel zártál – ügyes befektető vagy!")
    elif penz < 1000:
        yield ctx.mond("Veszteséggel zártál – legközelebb jobban megy!")
    else:
        yield ctx.mond("Nullszaldó – se nem nyertél, se nem vesztettél.")
    yield ctx.vege("Köszönöm a játékot!")


# ========================================================== KORONG (Reversi)
_REV_IR = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _rev_flips(tabla, x, y, szin, N=8):
    if tabla[y][x] != ".":
        return []
    ell = "O" if szin == "X" else "X"
    flips = []
    for dx, dy in _REV_IR:
        ut = []
        nx, ny = x + dx, y + dy
        while 0 <= nx < N and 0 <= ny < N and tabla[ny][nx] == ell:
            ut.append((nx, ny))
            nx += dx
            ny += dy
        if ut and 0 <= nx < N and 0 <= ny < N and tabla[ny][nx] == szin:
            flips += ut
    return flips


def _rev_legal(tabla, szin, N=8):
    d = {}
    for y in range(N):
        for x in range(N):
            f = _rev_flips(tabla, x, y, szin, N)
            if f:
                d[(x, y)] = f
    return d


def _rev_rak(tabla, x, y, szin, flips):
    tabla[y][x] = szin
    for fx, fy in flips:
        tabla[fy][fx] = szin


def _rev_szamol(tabla):
    x = sum(r.count("X") for r in tabla)
    o = sum(r.count("O") for r in tabla)
    return x, o


def _rev_koord(v):
    t = (v or "").strip().lower()
    if not t or t[0] < "a" or t[0] > "h":
        return None
    x = ord(t[0]) - ord("a")
    num = "".join(c for c in t[1:] if c.isdigit())
    if not num:
        return None
    y = int(num) - 1
    if not (0 <= x < 8 and 0 <= y < 8):
        return None
    return (x, y)


def _rev_nev(x, y):
    return f"{chr(ord('a') + x)}{y + 1}"


def jatek_korong(ctx):
    N = 8
    tabla = [["."] * N for _ in range(N)]
    tabla[3][3] = tabla[4][4] = "O"
    tabla[3][4] = tabla[4][3] = "X"
    yield ctx.mond(
        "KORONG, más néven Reversi. Nyolcszor nyolcas tábla. Te a sötét "
        "korongokkal játszol (jelük: iksz), a gép a világossal. A mezőt "
        "oszlopbetű és sorszám adja, például c4. Ha közrefogod a gép "
        "korongjait, a magad színére fordítod őket. Enter: a gép lép helyetted "
        "egy jó lépést. Akinek a végén több korongja van, nyer.")
    jatekos_passz = gep_passz = False
    while True:
        legal = _rev_legal(tabla, "X", N)
        if not legal:
            if gep_passz:
                break
            yield ctx.mond("Nincs érvényes lépésed – passzolsz.")
            jatekos_passz = True
        else:
            jatekos_passz = False
            lepett = False
            while not lepett:
                v = yield ctx.kerdez("Hová raksz korongot? (pl. c4; Enter = a "
                                     "gép lép helyetted)")
                t = (v or "").strip().lower()
                if t == "":
                    cel = max(legal, key=lambda c: len(legal[c]))
                    _rev_rak(tabla, cel[0], cel[1], "X", legal[cel])
                    yield ctx.mond(f"A gép a(z) {_rev_nev(*cel)} mezőt "
                                   "javasolta és le is rakta helyetted.")
                    lepett = True
                    break
                cel = _rev_koord(t)
                if cel is None or cel not in legal:
                    yield ctx.mond("Oda most nem rakhatsz – válassz olyan "
                                   "mezőt, ahol közrefogsz.")
                    continue
                _rev_rak(tabla, cel[0], cel[1], "X", legal[cel])
                yield ctx.mond(f"Leraktál egy korongot a(z) {_rev_nev(*cel)} "
                               f"mezőre, és {len(legal[cel])} korongot "
                               "fordítottál át.")
                lepett = True
        x, o = _rev_szamol(tabla)
        yield ctx.mond(f"Állás: sötét (te) {x}, világos (gép) {o}.")
        # --- gép ---
        glegal = _rev_legal(tabla, "O", N)
        if not glegal:
            if jatekos_passz:
                break
            yield ctx.mond("A gépnek nincs lépése – passzol.")
            gep_passz = True
        else:
            gep_passz = False
            cel = max(glegal, key=lambda c: len(glegal[c]))
            _rev_rak(tabla, cel[0], cel[1], "O", glegal[cel])
            yield ctx.mond(f"A gép a(z) {_rev_nev(*cel)} mezőre rak, és "
                           f"{len(glegal[cel])} korongot fordít át.")
        if all(tabla[y][x] != "." for y in range(N) for x in range(N)):
            break
    x, o = _rev_szamol(tabla)
    if x > o:
        yield ctx.mond(f"Vége! Sötét {x} – világos {o}. NYERTÉL!")
    elif o > x:
        yield ctx.mond(f"Vége! Sötét {x} – világos {o}. A gép nyert.")
    else:
        yield ctx.mond(f"Vége! Sötét {x} – világos {o}. Döntetlen.")
    yield ctx.vege("Köszönöm a játékot!")


# ==================================================================== NYÚLFARM
def jatek_nyulfarm(ctx):
    nyul, penz = 6, 100
    yield ctx.mond(
        "NYÚLFARM. Hat nyúllal és száz pénzzel indulsz. Évről évre a nyulak "
        "szaporodnak; eladhatsz belőlük, de a megmaradókat etetni kell. Hét "
        "évig gazdálkodsz – gyarapítsd a farmot!")
    for ev in range(1, 8):
        ujak = nyul // 2
        nyul += ujak
        yield ctx.mond(f"{ev}. év. A nyulak szaporodtak {ujak} kicsivel, most "
                       f"{nyul} nyulad és {penz} pénzed van.")
        v = yield ctx.kerdez(f"Hány nyulat adsz el? (darabja 10 pénz; van {nyul})")
        elad = szam(v, 0, nyul)
        if elad is None:
            elad = 0
        nyul -= elad
        penz += elad * 10
        koltseg = nyul * 2
        yield ctx.mond(f"Eladtál {elad} nyulat. A takarmány {koltseg} pénzbe "
                       "kerül.")
        penz -= koltseg
        if penz < 0:
            veszt = min(nyul, (-penz) // 2 + 1)
            nyul -= veszt
            penz = 0
            yield ctx.mond(f"Nem futotta takarmányra: {veszt} nyúl elpusztult.")
        if nyul <= 0:
            yield ctx.mond("Elfogytak a nyulaid – a farm bezár.")
            break
    else:
        yield ctx.mond(f"Hét év elteltével {nyul} nyulad és {penz} pénzed van. "
                       "Szép munka, gazda!")
    yield ctx.vege("Köszönöm a játékot!")


# ==================================================================== HAMURABI
def jatek_hamurabi(ctx):
    nep, buza, foldek = 100, 2800, 1000
    yield ctx.mond(
        "HAMURABI. Ókori városállamod ura vagy tíz éven át. Minden évben "
        "földet vehetsz vagy adhatsz el, búzát oszthatsz szét a népnek "
        "(fejenként 20 véka kell), és vetőmagot vethetsz. Az aratás és a sors "
        "a többit hozza. Vezesd bölcsen a népedet!")
    veg_ok = "letelt"
    for ev in range(1, 11):
        ar = random.randint(17, 26)
        yield ctx.mond(f"{ev}. év. Néped {nep} fő, raktáradban {buza} véka "
                       f"búza, birtokod {foldek} hold. Egy hold ára {ar} véka.")
        while True:
            v = yield ctx.kerdez("Hány holdat veszel? (eladáshoz negatív szám)")
            vesz = szam(v)
            if vesz is None:
                vesz = 0
            if vesz >= 0 and vesz * ar > buza:
                yield ctx.mond("Nincs annyi búzád – kevesebbet!")
                continue
            if vesz < 0 and -vesz > foldek:
                yield ctx.mond("Nincs annyi eladható földed – kevesebbet!")
                continue
            break
        foldek += vesz
        buza -= vesz * ar
        while True:
            v = yield ctx.kerdez(f"Hány véka búzát osztasz szét? (van {buza})")
            etet = szam(v)
            if etet is None or etet < 0:
                yield ctx.mond("Érvényes mennyiséget kérek.")
                continue
            etet = min(etet, buza)         # a raktárnál többet nem oszthatsz
            break
        buza -= etet
        while True:
            maxvet = min(foldek, buza, nep * 10)
            v = yield ctx.kerdez(f"Hány holdat vetsz be? (holdanként 1 véka "
                                 f"vetőmag; max {maxvet})")
            vet = szam(v)
            if vet is None or vet < 0:
                yield ctx.mond("Érvényes mennyiséget kérek.")
                continue
            vet = min(vet, maxvet)         # a lehetőségnél többet nem vethetsz
            break
        buza -= vet
        termes = random.randint(1, 6)
        aratott = vet * termes
        buza += aratott
        patkany = random.choice([0, 0, buza // 10, buza // 20])
        buza -= patkany
        jollakott = min(nep, etet // 20)
        ehen = max(0, nep - jollakott)
        szuletett = random.randint(0, max(1, jollakott // 10 + 1))
        reszek = [f"Az aratás holdanként {termes} véka volt, összesen {aratott}."]
        if patkany:
            reszek.append(f"A patkányok {patkany} vékát faltak fel.")
        reszek.append(f"{szuletett} gyermek született.")
        if ehen:
            reszek.append(f"{ehen} ember éhen halt.")
        yield ctx.mond(" ".join(reszek))
        if ehen > 0.45 * nep:
            veg_ok = "lazadas"
            break
        nep = jollakott + szuletett
        if nep <= 0:
            veg_ok = "kihalt"
            break
    if veg_ok == "lazadas":
        yield ctx.mond("Túl sokan haltak éhen – a nép fellázadt és elűzött. "
                       "Vége az uralkodásnak.")
    elif veg_ok == "kihalt":
        yield ctx.mond("Kihalt a néped – Hamurabi uralkodásának vége.")
    else:
        yield ctx.mond(f"Letelt a tíz év. Néped {nep} főre gyarapodott, "
                       f"birtokod {foldek} hold. Jól kormányoztál!")
    yield ctx.vege("Köszönöm a játékot!")


# ===================================================================== MOKITA
def jatek_mokita(ctx):
    yield ctx.mond(
        "MOKITA. Egy háromjegyű számra gondolok, csupa különböző számjeggyel "
        "(1-től 9-ig). Találd ki! Minden tippedre megmondom, hány számjegy van "
        "jó helyen, és hány jó számjegy szerepel rossz helyen.")
    while True:
        titok = "".join(random.sample("123456789", 3))
        probak = 0
        while True:
            v = yield ctx.kerdez("Tipp (három különböző számjegy):")
            t = "".join(c for c in (v or "") if c.isdigit())
            if len(t) != 3 or len(set(t)) != 3:
                yield ctx.mond("Három különböző számjegyet kérek.")
                continue
            probak += 1
            johely = sum(1 for a, b in zip(t, titok) if a == b)
            kozos = len(set(t) & set(titok))
            if johely == 3:
                yield ctx.mond(f"Kitaláltad {probak} próbából! A szám {titok}. "
                               "Gratulálok!")
                break
            yield ctx.mond(f"{johely} jó helyen, {kozos - johely} jó számjegy "
                           "rossz helyen.")
        v = yield ctx.kerdez("Új játék? (igen/nem)")
        if not igen(v, False):
            break
    yield ctx.vege("Köszönöm a játékot!")
