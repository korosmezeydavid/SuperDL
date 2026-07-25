# -*- coding: utf-8 -*-
"""HITELES portok a hivatalos Homelab/Brailab gyűjteményből
(`Documents\\játékok\\szabalyok\\*.md` + detokenizált BASIC).

ELV: a szabályokat, üzeneteket és állandókat A FORRÁS SZERINT követjük – nem
a miénk, nincs jogunk megváltoztatni. Minden játék a saját, EREDETI szerzőjét
kapja a szerző-megjelölésben. A BR4.ROM-hoz nem nyúlunk, gépi kódot nem
másolunk; a VISELKEDÉST írjuk újra."""
import random

from ._util import igen, szam, ekezet_nelkul


# ================================================================= BLACKJACK
# Forrás: BLACKJAC.HTP – Készítette: Halmágyi István, 1985.
# Tét 0,1–500 Ft; parancsok: 0 megállás, 1 lapkérés, 2 duplázás, split azonos
# lapoknál; biztosítás, ha az osztó terített lapja ász. Üzenetek a forrásból.

def _bj_pakli():
    p = []
    for _ in range(4):
        p += [("ász", 11), ("király", 10), ("dáma", 10), ("bubi", 10)]
        p += [(str(n), n) for n in range(2, 11)]
    random.shuffle(p)
    return p


def _bj_ertek(kez):
    total = sum(e for _, e in kez)
    aszok = sum(1 for nev, _ in kez if nev == "ász")
    while total > 21 and aszok:
        total -= 10
        aszok -= 1
    return total


def _bj_kez(kez):
    return ", ".join(nev for nev, _ in kez)


def _bj_tet(v):
    t = (v or "").strip().replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def jatek_blackjack(ctx):
    penz = 100.0
    yield ctx.mond(
        "BLACKJACK. A cél 21-hez minél közelebb kerülni túllépés nélkül. Az "
        "ász 1 vagy 11, a figurák tízet érnek. A tét 0,1 és 500 forint között "
        "lehet; a 0 tét kilépés.")
    while True:
        yield ctx.mond(f"Az egyenleged: {penz:.1f} forint.")
        v = yield ctx.kerdez("Mennyit teszel? (0,1–500 Ft; 0 = kilépés)")
        tet = _bj_tet(v)
        if tet is None or tet < 0:
            yield ctx.mond("Érvényes tétet kérek.")
            continue
        if tet == 0:
            break
        if tet > 500:
            yield ctx.mond("TUL SOK! 500 A FELSŐ HATÁR")
            continue
        if tet > penz:
            yield ctx.mond("Nincs annyi pénzed.")
            continue

        pakli = _bj_pakli()
        gep = [pakli.pop()]
        jatekos = [pakli.pop()]
        gep.append(pakli.pop())
        jatekos.append(pakli.pop())
        yield ctx.mond(f"A gép terített lapja: {gep[0][0]}. A te lapjaid: "
                       f"{_bj_kez(jatekos)}, érték {_bj_ertek(jatekos)}.")

        biztositas = 0.0
        if gep[0][0] == "ász":
            v = yield ctx.kerdez("A gépnek ásza van – kérsz biztosítást a tét "
                                 "felére? (igen/nem)")
            if igen(v, False):
                biztositas = tet / 2

        kezek = [jatekos]
        tetek = [tet]
        if jatekos[0][1] == jatekos[1][1]:
            v = yield ctx.kerdez("A két lapod azonos értékű – szétválasztod "
                                 "(split)? (igen/nem)")
            if igen(v, False):
                if tet * 2 > penz:
                    yield ctx.mond("MOST NEM LEHET VÁGNI -- UJRA!")
                else:
                    kezek = [[jatekos[0], pakli.pop()],
                             [jatekos[1], pakli.pop()]]
                    tetek = [tet, tet]

        for idx, kez in enumerate(kezek):
            if len(kezek) > 1:
                yield ctx.mond("ELSŐ KÉZ JÁTSZIK" if idx == 0
                               else "A MÁSODIK KÖVETKEZIK")
            while True:
                e = _bj_ertek(kez)
                if e > 21:
                    yield ctx.mond(f"{_bj_kez(kez)} – {e}, túllépted a 21-et!")
                    break
                if e == 21:
                    break
                v = yield ctx.kerdez(
                    f"{_bj_kez(kez)}, érték {e}. Parancs: 0 megállás, "
                    "1 lapkérés, 2 duplázás.")
                t = (v or "").strip()
                if t == "1":
                    kez.append(pakli.pop())
                elif t == "2":
                    if len(kez) != 2:
                        yield ctx.mond("TUL KÉSŐ DUPLÁZNI, ÖREGEM!")
                        continue
                    if tetek[idx] * 2 > penz:
                        yield ctx.mond("Nincs elég pénzed duplázni.")
                        continue
                    tetek[idx] *= 2
                    kez.append(pakli.pop())
                    yield ctx.mond(f"Duplázás! A lapjaid: {_bj_kez(kez)}, "
                                   f"érték {_bj_ertek(kez)}.")
                    break
                elif t == "0":
                    break
                else:
                    yield ctx.mond("0, 1 vagy 2 legyen.")

        yield ctx.mond(f"A FEDETT LAPOM : {gep[1][0]}.")
        while _bj_ertek(gep) < 17:
            gep.append(pakli.pop())
        gep_e = _bj_ertek(gep)
        yield ctx.mond(f"AZ EREDMÉNYEM : {gep_e}. Az osztó lapjai: "
                       f"{_bj_kez(gep)}.")

        for idx, kez in enumerate(kezek):
            e = _bj_ertek(kez)
            w = tetek[idx]
            termeszetes = (len(kezek) == 1 and len(kez) == 2 and e == 21)
            if e > 21:
                penz -= w
                uz = "túllépted, vesztettél."
            elif gep_e > 21 or e > gep_e:
                if termeszetes:
                    penz += 1.5 * w
                    uz = f"BLACKJACK! Nyertél {1.5 * w:.1f} forintot."
                else:
                    penz += w
                    uz = f"nyertél {w:.1f} forintot."
            elif e < gep_e:
                penz -= w
                uz = "az osztó nyert."
            else:
                uz = "döntetlen."
            elozo = f"{idx + 1}. kéz: " if len(kezek) > 1 else ""
            yield ctx.mond(f"{elozo}{uz} Egyenleg: {penz:.1f} forint.")

        if biztositas > 0:
            if gep_e == 21 and len(gep) == 2:
                penz += biztositas * 2
                yield ctx.mond(f"A biztosítás bejött: plusz "
                               f"{biztositas * 2:.1f} forint.")
            else:
                penz -= biztositas
                yield ctx.mond(f"A biztosítás elveszett: mínusz "
                               f"{biztositas:.1f} forint.")

        if penz <= 0:
            yield ctx.mond("Elfogyott a pénzed. Vége a játéknak.")
            break

    yield ctx.vege("Köszönöm a játékot!")


# ============================================================== SZÁMKITALÁLÓ
# Forrás: SZAMKIT1.HTP – a gép számra gondol, a játékos tippel; „NAGYOBBAT!" /
# „KISSEBBET!" visszajelzés. Az üzenetek a forrásból, szó szerint.

def jatek_szamkit1(ctx):
    yield ctx.mond("SZÁMKITALÁLÓ JÁTÉK. Egy számra gondolok 1 és 100 között.")
    while True:
        a = random.randint(1, 100)
        c = 0
        while True:
            v = yield ctx.kerdez("KÉREM A TIPPET!")
            b = szam(v)
            if b is None:
                yield ctx.mond("Számot kérek.")
                continue
            c += 1
            if a > b:
                yield ctx.mond("NAGYOBBAT!")
            elif a < b:
                yield ctx.mond("KISSEBBET!")
            else:
                yield ctx.mond("ELTALÁLTAD!")
                yield ctx.mond(f"{c} TIPPED VOLT.")
                break
        v = yield ctx.kerdez("SZERETNÉL MÉG JÁTSZANI?")
        if not igen(v, False):
            break
    yield ctx.vege("NAGYON SAJNÁLOM MERT IGEN JÖ JÁTÉKOS VOLTÁL.")


# ==================================================================== AMŐBA
# Forrás: AMOBA.HTP – 17×17-es amőba (öt egy sorban) a gép ellen. A játékos
# jele X, a gépé O. Az oszlopokat és sorokat A-tól R-ig betűk jelölik (a Q
# kimarad!). Kérdőjellel letapogatható a mező. Üzenetek a forrásból.
_AMOBA_BETUK = "ABCDEFGHIJKLMNOPR"      # 17 betű, a Q szándékosan kimarad
_AMOBA_N = 17


def _amoba_koord(v):
    t = [ch for ch in (v or "").upper() if ch in _AMOBA_BETUK]
    if len(t) < 2:
        return None
    return (_AMOBA_BETUK.index(t[0]), _AMOBA_BETUK.index(t[1]))   # (oszlop, sor)


def _amoba_nyer(board, r, c, jel):
    n = _AMOBA_N
    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
        db = 1
        for s in (1, -1):
            nr, nc = r + dr * s, c + dc * s
            while 0 <= nr < n and 0 <= nc < n and board[nr][nc] == jel:
                db += 1
                nr += dr * s
                nc += dc * s
        if db >= 5:
            return True
    return False


def _amoba_minta(hossz, nyilt):
    if hossz >= 5:
        return 100000
    if hossz == 4:
        return 10000 if nyilt == 2 else 1200
    if hossz == 3:
        return 1000 if nyilt == 2 else 120
    if hossz == 2:
        return 100 if nyilt == 2 else 12
    return 1 if nyilt else 0


def _amoba_ertek(board, r, c, jel):
    n = _AMOBA_N
    ossz = 0
    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
        hossz = 1
        nyilt = 0
        for s in (1, -1):
            nr, nc = r + dr * s, c + dc * s
            while 0 <= nr < n and 0 <= nc < n and board[nr][nc] == jel:
                hossz += 1
                nr += dr * s
                nc += dc * s
            if 0 <= nr < n and 0 <= nc < n and board[nr][nc] == ".":
                nyilt += 1
        ossz += _amoba_minta(hossz, nyilt)
    return ossz


def _amoba_lep(board, vedekezo):
    n = _AMOBA_N
    cellak = set()
    van_ko = False
    for r in range(n):
        for c in range(n):
            if board[r][c] != ".":
                van_ko = True
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < n and 0 <= nc < n and board[nr][nc] == ".":
                            cellak.add((nr, nc))
    if not van_ko:
        return (n // 2, n // 2)
    w_def = 1.4 if vedekezo else 1.0
    legjobb, legjobb_ert = None, -1.0
    for (r, c) in cellak:
        tamado = _amoba_ertek(board, r, c, "O")
        vedo = _amoba_ertek(board, r, c, "X")
        ert = tamado + w_def * vedo
        if ert > legjobb_ert:
            legjobb_ert, legjobb = ert, (r, c)
    return legjobb


def jatek_amoba(ctx):
    yield ctx.mond(
        "AMŐBA JÁTÉK A SZÁMÍTÓGÉP ELLEN. A játék célja a játékos ikszeiből 5 "
        "darabot felhelyezni egymás mellé egyenes vonalban vízszintesen, "
        "függőlegesen vagy átlósan. Természetesen a gép is erre törekszik, de "
        "az ő jele az O betű. A játéktábla 17 oszlopból és 17 sorból áll. Az A "
        "A a bal felső, az R R a jobb alsó sarok. Először a kívánt pont "
        "oszlopát, majd a sorát add meg betűvel, például: H H. Kérdőjellel "
        "letapogathatod a mezőt.")
    v = yield ctx.kerdez("KÉRI E A VÉDEKEZŐ JÁTÉKSTÍLUST I VAGY N?")
    vedekezo = igen(v, False)
    while True:
        board = [["."] * _AMOBA_N for _ in range(_AMOBA_N)]
        gyoztes = None
        while gyoztes is None:
            yield ctx.mond("TE JÖSSZ!")
            while True:
                v = yield ctx.kerdez("HOVÁ RAKSZ? (oszlop és sor betűje, pl. H H)")
                t = (v or "").strip()
                if t.startswith("?"):
                    cella = _amoba_koord(t[1:])
                    if cella is None:
                        yield ctx.mond("KÉRDEZZ!")
                        continue
                    col, row = cella
                    b = board[row][col]
                    yield ctx.mond("A TIED." if b == "X" else
                                   "AZ ENYÉM." if b == "O" else "MÉG ŰRES.")
                    continue
                cella = _amoba_koord(t)
                if cella is None:
                    yield ctx.mond("NEM JÖL RAKTÁL!")
                    continue
                col, row = cella
                if board[row][col] != ".":
                    yield ctx.mond("NEM JÖL RAKTÁL!")
                    continue
                board[row][col] = "X"
                break
            if _amoba_nyer(board, row, col, "X"):
                yield ctx.mond("TE GYŐZTÉL    GRATULÁLOK !")
                break
            if all(board[r][c] != "." for r in range(_AMOBA_N)
                   for c in range(_AMOBA_N)):
                yield ctx.mond("Betelt a tábla – döntetlen.")
                break
            yield ctx.mond("Gondolkodom.")
            gr, gc = _amoba_lep(board, vedekezo)
            board[gr][gc] = "O"
            yield ctx.mond(f"Lépek: {_AMOBA_BETUK[gc]} {_AMOBA_BETUK[gr]}.")
            if _amoba_nyer(board, gr, gc, "O"):
                yield ctx.mond("MA NEM VAGY FORMÁBAN    MOST ÉN NYERTEM!")
                break
        v = yield ctx.kerdez("JÁTSZUNK MÉG EGYET I VAGY N?")
        if not igen(v, False):
            break
    yield ctx.vege("Köszönöm a játékot!")


# ==================================================================== NIM JÁTÉK
# Forrás: NIMJATEK.HTP – „AZ NYER, AKI UTOLSÓNAK VESZ". A játékos adja a kezdő
# állást (2-5 kupac, egyenként 1-1000). A gép XOR (nim-összeg) optimális
# stratégiával lép. (A forrás győzelem-ellenőrzése csak az első 4 kupacot
# nézte – a hivatalos leírás javítást kér: az ÖSSZES kupacot nézzük.)

def _nim_ai(kupacok):
    x = 0
    for a in kupacok:
        x ^= a
    if x != 0:
        for i, a in enumerate(kupacok):
            cel = x ^ a
            if cel < a:
                return i, a - cel
    i = max(range(len(kupacok)), key=lambda j: kupacok[j])
    if kupacok[i] == 0:
        for j in range(len(kupacok)):
            if kupacok[j] > 0:
                i = j
                break
    return i, (kupacok[i] + 1) // 2


def jatek_nimjatek(ctx):
    yield ctx.mond("NIM JÁTÉK. AZ NYER, AKI UTOLSÓNAK VESZ. ADD MEG A KEZDŐ "
                   "ÁLLÁST.")
    while True:
        v = yield ctx.kerdez("HÁNY KUPAC LEGYEN? (2-5)")
        k = szam(v, 2, 5)
        if k is not None:
            break
    kupacok = []
    for n in range(1, k + 1):
        while True:
            v = yield ctx.kerdez(f"A({n})= (1-1000)")
            a = szam(v, 1, 1000)
            if a is not None:
                kupacok.append(a)
                break
    while True:
        yield ctx.mond("A kupacok: "
                       + ", ".join(str(x) for x in kupacok) + ".")
        while True:
            v = yield ctx.kerdez("HONNAN VESZEL?")
            n = szam(v, 1, k)
            if n is None:
                continue
            if kupacok[n - 1] == 0:
                yield ctx.mond("Az a kupac üres.")
                continue
            break
        while True:
            v = yield ctx.kerdez("ÉS ABBÓL MENNYIT?")
            m = szam(v, 1, kupacok[n - 1])
            if m is not None:
                break
        kupacok[n - 1] -= m
        if sum(kupacok) == 0:
            yield ctx.mond("TE NYERTÉL")
            break
        gi, gm = _nim_ai(kupacok)
        kupacok[gi] -= gm
        yield ctx.mond(f"ÉN MEG {gi + 1}-BŐL {gm} DB-T.")
        if sum(kupacok) == 0:
            yield ctx.mond("EN NYERTEM")
            break
    yield ctx.vege("Köszönöm a játékot!")


# ================================================================= MEMÓRIATESZT
# Forrás: MEMTESZT.HTP – a gép szám+szó párokat mond, meg kell jegyezni, majd
# sorban visszamondani. Az eredeti szólista és üzenetek. A forrás ON AA GOTO-ja
# 20 körnél megáll, ezért 20 párnál teljesített a teszt.
_MEMTESZT_SZAVAK = ["SZEKRÉNY", "ASZTAL", "NADRÁG", "SZOKNYA", "MACSKA",
                    "ZONGORA", "ORSZÁG", "VACSORA", "KENYÉR", "ORGONA",
                    "BUZOGÁNY", "CSÓTÁNY", "DELFIN", "ELEFÁNT", "CIGARETTA",
                    "KILINCS"]


def _memteszt_ell(v, parok):
    toks = (v or "").strip().split()
    if len(toks) < 2 * len(parok):
        return False
    for i, (s, w) in enumerate(parok):
        ns, nw = toks[2 * i], toks[2 * i + 1]
        if not ns.isdigit() or int(ns) != s:
            return False
        if ekezet_nelkul(nw) != ekezet_nelkul(w):
            return False
    return True


def jatek_memteszt(ctx):
    yield ctx.mond(
        "MEMÓRIA TESZT. Számokat és szavakat fogok mondani. Meg kell jegyezned "
        "őket! Később ismételned kell ezeket az egymáshoz rendelt párokat. "
        "Minden szám és szó egy pár.")
    while True:
        yield ctx.mond("FIGYELJ! INDULUNK!")
        parok = []
        pont = 0
        while True:
            parok.append((random.randint(1, 30),
                          random.choice(_MEMTESZT_SZAVAK)))
            bemutat = ", ".join(f"{s} {w}" for s, w in parok)
            yield ctx.mond("A párok: " + bemutat + ".")
            v = yield ctx.kerdez("ISMÉTELD MEG A SZÁMOKAT ÉS SZAVAKAT! "
                                 "(szám szó, szám szó, …)")
            if _memteszt_ell(v, parok):
                pont += len(parok)
                if len(parok) >= 20:
                    yield ctx.mond("EZ RENDKIVŰLI TELJESITMÉNY VOLT! KÁPRÁZATOS "
                                   "MEMÓRIÁD VAN! GRATULÁLOK!")
                    yield ctx.mond(f"A JÁTÉK ALATT {pont} PONTOT ÉRTÉL EL.")
                    break
                yield ctx.mond("EDDIG JÖ! FOLYTASSUK TOVÁBB!")
            else:
                yield ctx.mond("HIBÁZTÁL. SAJNÁLOM!")
                yield ctx.mond("A HELYES VÁLASZOK AZ ALÁBBIAK VOLTAK: "
                               + bemutat + ".")
                yield ctx.mond(f"A JÁTÉK ALATT {pont} PONTOT ÉRTÉL EL.")
                break
        v = yield ctx.kerdez("JÁTSZUNK MÉG TOVÁBB?")
        if not igen(v, False):
            break
    yield ctx.vege("KÖSZÖNÖM A JÁTÉKOT!")


# ======================================================================= LOTTÓ
# Forrás: LOTTO.HTP – lottószám-tipp generátor. 1-255 szelvény; hagyományos
# (5/90) vagy hatos (6/45) lottó. A gép sorra bemondja a kihúzott számokat.
_LOTTO_SORSZAM = ["AZ ELSŐ SZÁM", "A MÁSODIK SZÁM", "A HARMADIK SZÁM",
                  "A NEGYEDIK SZÁM", "AZ ÖTÖDIK SZÁM", "A HATODIK SZÁM"]


def jatek_lotto(ctx):
    yield ctx.mond("LOTTÓ SZERENCSE.")
    while True:
        v = yield ctx.kerdez("HÁNY SZELVÉNYRE ÁLLÍTSAK ÖSSZE TIPPET?")
        h = szam(v, 1, 255)
        if h is None:
            yield ctx.mond("MINIMUM 1 MAXIMUM 255 SZELVÉNYRE LEHET KÉRNI "
                           "TIPPET.")
            continue
        break
    while True:
        v = yield ctx.kerdez("HA HAGYOMÁNYOS LOTTÓHOZ KELL TIPP, ÍRJ 1-ET, HA "
                             "HATOS LOTTÓHOZ, 2-ŐT.")
        t = (v or "").strip()
        if t == "1":
            sz, db = 90, 5
            break
        if t == "2":
            sz, db = 45, 6
            break
        yield ctx.mond("NE KUKACOSKODJ VELEM!")
    for i in range(1, h + 1):
        szamok = sorted(random.sample(range(1, sz + 1), db))
        yield ctx.mond(f"{i}. szelvény:")
        for j, n in enumerate(szamok):
            yield ctx.mond(f"{_LOTTO_SORSZAM[j]}: {n}.")
    yield ctx.mond("A KÉRT SZÁMÚ SZELVÉNYRE A TIPP ELFOGYOTT.")
    yield ctx.vege("Köszönöm a játékot!")


# ==================================================================== FÖLDRAJZ
# Forrás: FOLDRAJZ.HTP – a gép igen/nem kérdésekkel kitalálja, melyik EURÓPAI
# országra gondolsz. A döntési fa PONTOSAN a BASIC-forrás szerint (a sorszámok
# a node-azonosítók). ("q", kérdés, IGEN-cél, NEM-cél) / ("g", ország).
_FOLDRAJZ_FA = {
    90:  ("q", "Az ország nagyobb Magyarországnál?", 930, 120),
    120: ("q", "Az ország törpeállam?", 150, 370),
    150: ("q", "Olaszország területén fekszik?", 180, 250),
    180: ("q", "Az ország vezetője a Pápa?", 210, 230),
    210: ("g", "a Vatikánra"),
    230: ("g", "San Marinóra"),
    250: ("q", "Az ország Franciaországgal határos?", 300, 274),
    274: ("q", "Afrikához ez az ország fekszik a legközelebb?", 277, 280),
    277: ("g", "Gibraltárra"),
    280: ("g", "Liechtensteinre"),
    300: ("q", "Az ország köztársaság?", 330, 350),
    330: ("g", "Andorrára"),
    350: ("g", "Monacóra"),
    370: ("q", "Az ország szigetország?", 400, 510),
    400: ("q", "Éghajlata mediterrán?", 430, 490),
    430: ("q", "Fővárosa La Valetta?", 455, 470),
    455: ("g", "Máltára"),
    470: ("g", "Ciprusra"),
    490: ("g", "Írországra"),
    510: ("q", "BENELUX állam?", 540, 660),
    540: ("q", "Európa legsűrűbben lakott állama?", 570, 590),
    570: ("g", "Hollandiára"),
    590: ("q", "Hivatalos nyelve a flamand és a francia?", 620, 640),
    620: ("g", "Belgiumra"),
    640: ("g", "Luxemburgra"),
    660: ("q", "Zászlójában van fehér szín?", 690, 860),
    690: ("q", "Az ország éghajlata óceáni?", 720, 740),
    720: ("g", "Dániára"),
    740: ("q", "Semleges ország?", 764, 790),
    764: ("q", "Fővárosa adott már otthont csúcsértekezletnek?", 820, 770),
    770: ("g", "Svájcra"),
    790: ("q", "Fővárosa adott már otthont csúcsértekezletnek?", 820, 840),
    820: ("g", "Ausztriára"),
    840: ("g", "Magyarországra"),
    860: ("q", "Csak egy országgal határos?", 890, 910),
    890: ("g", "Portugáliára"),
    910: ("g", "Albániára"),
    930: ("q", "Magyarországgal határos?", 960, 1130),
    960: ("q", "Az ország tagja a világbanknak?", 990, 1010),
    990: ("g", "Jugoszláviára"),
    1010: ("q", "Két egyenjogú tagállam alkotja?", 1040, 1060),
    1040: ("g", "Csehszlovákiára"),
    1060: ("q", "A világ ipari termelésének egyötödét adja?", 1090, 1110),
    1090: ("g", "a Szovjetunióra"),
    1110: ("g", "Romániára"),
    1130: ("q", "Skandináv állam?", 1160, 1280),
    1160: ("q", "Az ezer tó országának nevezik?", 1190, 1210),
    1190: ("g", "Finnországra"),
    1210: ("q", "Az egy főre jutó áramtermelésben első a földön?", 1240, 1260),
    1240: ("g", "Norvégiára"),
    1260: ("g", "Svédországra"),
    1280: ("q", "Az ország a Balkán félszigeten fekszik?", 1310, 1380),
    1310: ("q", "A zászlójában ugyanazok a színek, mint a magyar zászlóban?",
           1340, 1360),
    1340: ("g", "Bulgáriára"),
    1360: ("g", "Görögországra"),
    1380: ("q", "Szigetország?", 1410, 1480),
    1410: ("q", "1976 január elsejétől tagja a Közös Piacnak?", 1440, 1460),
    1440: ("g", "Nagybritanniára"),
    1460: ("g", "Izlandra"),
    1480: ("q", "Szocialista ország?", 1510, 1580),
    1510: ("q", "Az éves szaporulata nagyobb, mint 5 százalék?", 1540, 1560),
    1540: ("g", "Lengyelországra"),
    1560: ("g", "a Német Demokratikus Köztársaságra"),
    1580: ("q", "Andorrával határos?", 1610, 1680),
    1610: ("q", "A NÁTÓBÓL 1966-ban lépett ki?", 1640, 1660),
    1640: ("g", "Franciaországra"),
    1660: ("g", "Spanyolországra"),
    1680: ("q", "Lakosságának nagy része mohamedán?", 1710, 1730),
    1710: ("g", "Törökországra"),
    1730: ("q", "A lakosságának nagyobb része katolikus?", 1760, 1780),
    1760: ("g", "Olaszországra"),
    1780: ("g", "a Német Szövetségi Köztársaságra"),
}


def _cap(s):
    return s[:1].upper() + s[1:]


def jatek_foldrajz(ctx):
    yield ctx.mond("FÖLDRAJZ. Gondolj egy európai országra, és kitalálom, "
                   "melyikre gondoltál! A kérdéseimre I-vel (igen) vagy N-nel "
                   "(nem) válaszolj.")
    while True:
        v = yield ctx.kerdez("Szeretnél játszani? (I/N)")
        if not igen(v, True):
            yield ctx.mond("Nagyon sajnálom! Viszontlátásra.")
            break
        yield ctx.mond("Gondolj egy európai országra!")
        v = yield ctx.kerdez("Megvan? (I/N)")
        while not igen(v, True):
            v = yield ctx.kerdez("Megvan? (I/N)")
        node = 90
        while True:
            tip = _FOLDRAJZ_FA[node]
            if tip[0] == "g":
                v = yield ctx.kerdez(_cap(tip[1]) + " gondoltál? (I/N)")
                if igen(v, True):
                    yield ctx.mond("Köszönöm a játékot, nagyon élvezetes volt!")
                else:
                    yield ctx.mond("Sajnálom, de valahol hibáztál a "
                                   "válaszadásban.")
                break
            while True:
                v = yield ctx.kerdez(tip[1] + " (I/N)")
                valasz = igen(v, None)
                if valasz is None:
                    yield ctx.mond("Kérlek, I vagy N legyen a válasz.")
                    continue
                node = tip[2] if valasz else tip[3]
                break
    yield ctx.vege("Köszönöm a játékot!")


# ================================================================ SZÁMKITALÁLÓ 2
# Forrás: SZAMKIT2.HTP – a gép gondol egy számot 0 és a megadott felső határ
# között; tippelsz, „NAGYOBBAT/KISSEBBET GONDOLTAM", plusz ellentmondás- és
# ismétlés-figyelés, szurka-piszka üzenetekkel. Minden szöveg a forrásból.

def jatek_szamkit2(ctx):
    yield ctx.mond("SZÁMKITALÁLÓS JÁTÉK.")
    while True:
        v = yield ctx.kerdez("MEKKORA SZÁMIG JÁTSZUNK?")
        bu = szam(v, 1, 1000000)
        if bu is None:
            continue
        es = random.randint(0, bu)
        yield ctx.mond(f"GONDOLTAM EGY SZÁMOT 0 ÉS {bu} KÖZÖTT.")
        sa, po, elso = 0, 1, True
        while True:
            v = yield ctx.kerdez("PRÓBÁLD MEG KITALÁLNI!" if elso
                                 else "PRÓBÁLD MEG UJRA!")
            elso = False
            va = szam(v)
            if va is None:
                yield ctx.mond("Számot kérek.")
                continue
            if va == es:
                if po > 10:
                    yield ctx.mond("VÉGŰL HA NEHEZEN IS DE ELTALÁLTAD!")
                else:
                    yield ctx.mond("ELTALÁLTAD GRATULÁLOK!")
                yield ctx.mond(f"A PRÖBÁLKOZÁSAID SZÁMA {po} VOLT.")
                break
            if va < 0:
                yield ctx.mond("EZ OSTOBASÁG VOLT INKÁBB MEGÁLLOK!")
                yield ctx.vege("SZERBUSZ!")
                return
            if (va > sa and es < sa) or (va < sa and es > sa):
                yield ctx.mond("HIBÁS ELKÉPZELÉS!")
                yield ctx.mond("EZT A SZÁMOT MÁR TAGADTAM A VÁLASZOMMAL!")
                po += 1
                continue
            if va == sa:
                yield ctx.mond("AZ ELŐBB IS EZT PRÖBÁLTAD!")
                po += 1
                continue
            if va > bu:
                yield ctx.mond(f"NEM TUDSZ SZÁMOLNI FIAM CSAK {bu}-IG "
                               "TIPPELHETSZ!")
                po += 1
                continue
            yield ctx.mond("NAGYOBBAT GONDOLTAM." if va < es
                           else "KISSEBBET GONDOLTAM.")
            sa, po = va, po + 1
        v = yield ctx.kerdez("JÁTSZUNK MÉGEGGYET?")
        if not igen(v, False):
            yield ctx.mond("REMÉLEM JÖL SZÖRAKOZTUNK EGGYŰT!")
            break
    yield ctx.vege("SZERBUSZ!")


# ================================================================= DOBÓKOCKA
# Forrás: DOBOKOC.HTP – dobókockás pontgyűjtő. Az eredetiben két ember játszik;
# nálunk TE a gép ellen (akadálymentes, egyszemélyes), az eredeti szabállyal:
# 3 dobás, de a hatos újabb három dobást ad; 55/77/99 pontnál „legurul a kocka"
# és nulláról kezded; 99 fölött vége, a több pont nyer. Üzenetek a forrásból.

def _dobokoc_kor(p, aktiv):
    """A gép egy körének lepörgetése (nem yield-el). Visszaad: üzenetsor +
    (vege, új-pont)."""
    d = 0
    uzenetek = []
    while True:
        g = random.randint(1, 6)
        d += 1
        p += g
        uzenetek.append(f"A gép dobott: {g}. Összesen: {p}.")
        if p in (55, 77, 99):
            p, d = 0, 0
            uzenetek.append("HOPPÁ! LEGURULT A KOCKA AZ ASZTALRÖL! ÍGY "
                            "KEZDHETED ELŐRŐL A JÁTÉKOT!")
            continue
        if p > 99:
            return uzenetek, True, p
        if p < 6:
            p = 0
        if g == 6:
            d = 0
            uzenetek.append("UJJABB HÁROM DOBÁS ILLET MEG.")
            continue
        if d < 3:
            continue
        uzenetek.append(f"{p} PONTOD VAN. NEKED MOST NINCS TŐBB DOBÁSOD.")
        return uzenetek, False, p


def jatek_dobokoc(ctx):
    yield ctx.mond(
        "JÁTÉK A DOBÓKOCKÁVAL! Felváltva dobtok a géppel. Három dobás jár, de "
        "ha hatost dobsz, újabb három dobás illet meg! Ha a pontod 55, 77 vagy "
        "99, legurul a kocka az asztalról, és nulláról kezded. Kilencvenkilenc "
        "fölött vége, és a több pont nyer.")
    jatszmak = [0, 0]
    while True:
        p = [0, 0]
        vege = False
        aktiv = 0
        while not vege:
            if aktiv == 0:
                yield ctx.mond(f"Te jössz. {p[0]} pontod van. Dobjál!")
                d = 0
                while True:
                    yield ctx.kerdez("Dobáshoz nyomj Entert!")
                    g = random.randint(1, 6)
                    d += 1
                    p[0] += g
                    yield ctx.mond(f"Dobtál: {g}. Összesen: {p[0]}.")
                    if p[0] in (55, 77, 99):
                        p[0], d = 0, 0
                        yield ctx.mond("HOPPÁ! LEGURULT A KOCKA AZ ASZTALRÖL! "
                                       "ÍGY ELŐRŐL KEZDHETED A JÁTÉKOT.")
                        continue
                    if p[0] > 99:
                        vege = True
                        break
                    if p[0] < 6:
                        p[0] = 0
                    if g == 6:
                        d = 0
                        yield ctx.mond("UJJABB HÁROM DOBÁS ILLET MEG.")
                        continue
                    if d < 3:
                        continue
                    yield ctx.mond(f"{p[0]} PONTOD VAN. NEKED MOST NINCS TŐBB "
                                   "DOBÁSOD.")
                    break
            else:
                yield ctx.mond("A gép következik.")
                uzenetek, vege, p[1] = _dobokoc_kor(p[1], 1)
                for u in uzenetek:
                    yield ctx.mond(u)
            if not vege:
                aktiv = 1 - aktiv
        yield ctx.mond("ÁLLJATOK FEL! EREDMÉNYT HIRDETEK.")
        if p[0] > p[1]:
            jatszmak[0] += 1
            yield ctx.mond(f"{p[0]} PONTTAL MEGNYERTED A JÁTSZMÁT! GRATULÁLOK! "
                           "ŰGYES VOLTÁL!")
        elif p[1] > p[0]:
            jatszmak[1] += 1
            yield ctx.mond(f"A gép {p[1]} PONTTAL MEGNYERTE A JÁTSZMÁT! AZÉRT "
                           "NE PITYEREGJ!")
        else:
            yield ctx.mond("Döntetlen ez a játszma!")
        yield ctx.mond(f"Játszmák: te {jatszmak[0]}, a gép {jatszmak[1]}.")
        v = yield ctx.kerdez("AKARTOK MÉG JÁTSZANI? (I/N)")
        if not igen(v, False):
            break
    yield ctx.vege("KÖSZÖNÖM HOGY IRÁNYÍTHATTAM A JÁTÉKOT. JÖK VOLTATOK.")


# ================================================================= HUSZONEGY
# Forrás: Ócsvári Áron „Huszonegyes kártyajáték", 2010. 05. 29.
# (oaron1@gmail.com, http://oarononline.try.hu). A program nyílt forráskódú,
# a szerző kifejezett engedélyével és a kreditje megtartásával kerül ide.
# MINDEN szöveg és szabály a FORRÁSBÓL, szó szerint: 32 lapos magyar kártya;
# legalább két lapot kérni kell, és 15 pont alatt megállni nem szabad; a gép
# 19-ig húz; aki 21 fölé megy, befuccsol.

_H21_SZINEK = ("piros", "zöld", "makk", "tök")
_H21_LAPOK = (("alsó", 2), ("felső", 3), ("király", 4), ("ász", 11),
              ("hét", 7), ("nyolc", 8), ("kilenc", 9), ("tíz", 10))

# a „szabályok" menüpont teljes szövege – szó szerint a forrásból
_H21_SZABALY = (
    "A bankár mindenkinek egy lapot ad, utoljára magának is. Ezután minden "
    "játékos tesz. Legalább két lapot kérni kell, és 15 pont alatt megállni "
    "nem szabad. Ha a pontszám nagyobb 21-nél, a játékos befuccsol, vagyis "
    "veszít. Egyébként az nyer, akinek több pontja van. A lapok értékei: "
    "Alsó: 2, Felső: 3, Király: 4, Ász: 11. A hetes, nyolcas, kilences és "
    "tizes kártyák értékei egyértelműek. :) Kellemes szórakozást! Készítette: "
    "Ócsvári Áron – oaron1@gmail.com")


def _h21_pakli():
    """A 32 lapos magyar pakli: (lapnév, érték) párok."""
    return [(f"{sz} {nev}", ertek)
            for sz in _H21_SZINEK for nev, ertek in _H21_LAPOK]


def _h21_huz(pakli, huzott):
    """Egy még ki nem húzott lap véletlen kiválasztása → (lapnév, érték)."""
    szabad = [i for i in range(len(pakli)) if i not in huzott]
    i = random.choice(szabad)
    huzott.add(i)
    return pakli[i]


def _h21_eredmeny(jszam, jnyert, gnyert, dontetlen, vesztett):
    """A kilépéskori összesítő – a forrás fordulataival, szó szerint."""
    if jszam == 1 and jnyert == 0 and gnyert == 0:
        return ("Nos akkor az eredmények... A lejátszott 1 játékból ön egy "
                "menetet sem nyert meg, de mivel én sem, ezért mind a ketten "
                "elbuktuk! Máskor talán több szerencsénk lesz... Azért "
                "gratulálok, remélem máskor is találkozunk!")
    s = f"Nos akkor az eredmények... A lejátszott {jszam} játékból ön "
    s += ("egy menetet sem nyert meg," if jnyert == 0
          else f"{jnyert} menetet nyert meg,")
    s += (" én egy menetet sem" if gnyert == 0
          else f" én {gnyert} menetet,")
    s += (" és egy sem lett döntetlen." if dontetlen == 0
          else f" és {dontetlen} lett döntetlen.")
    if vesztett > 0:
        s += f" Szégyen, de {vesztett} menetet mind a ketten elbuktunk!"
    return s + " Gratulálok, remélem máskor is találkozunk!"


def jatek_huszonegy(ctx):
    yield ctx.mond("Üdvözlöm a huszonegyes játékban!")

    # ---- kezdőmenü: k / s / n --------------------------------------------
    while True:
        v = yield ctx.kerdez("Kérem, válasszon: k – játék kezdése, "
                             "s – a játék szabályainak elolvasása, "
                             "n – kilépés.")
        d = (v or "").strip().lower()[:1]
        if d == "s":
            yield ctx.mond(_H21_SZABALY)
            yield ctx.mond("Kedvet kapott a játékra? Ha igen, nyomja meg a k "
                           "betűt! Ha meg megíjedt... Akkor ne kerüljön a "
                           "szemem elé, és nyomja meg az n betűt!")
            continue
        if d == "n":
            yield ctx.vege("Rendben, értettem... Viszlát!")
            return
        if d == "k":
            break
        # bármi más: újra a menü

    jszam = jnyert = gnyert = dontetlen = vesztett = 0

    # ---- a menetek -------------------------------------------------------
    while True:
        pakli = _h21_pakli()
        huzott = set()
        jszam += 1
        nev, ertek = _h21_huz(pakli, huzott)
        jatekos = ertek
        kszam = 1
        yield ctx.mond(f"Az első húzott kártyája a {nev}, melynek értéke: "
                       f"{ertek}.")

        dont = ""
        gep = 0
        kilep = False
        while not kilep:
            if jatekos <= 21:
                v = yield ctx.kerdez("Szeretne újra húzni? (i/n)")
                dont = (v or "").strip().lower()[:1]
            # lapkérés – a forrás szerint legfeljebb az 5. lapig, 21-ig
            if dont == "i" and kszam <= 4 and jatekos <= 21:
                nev, ertek = _h21_huz(pakli, huzott)
                jatekos += ertek
                kszam += 1
                yield ctx.mond(f"A kapott kártya a {nev}, melynek értéke: "
                               f"{ertek}. A kártyái összértéke: {jatekos}.")
            if kszam > 4 or jatekos >= 21:
                if jatekos == 21:
                    yield ctx.mond("Az nevet a legjobban, aki utoljára nevet!")
                    yield ctx.mond("Most én következem!")
                else:
                    yield ctx.mond("Sajnálom, ennél többet nem húzhat! Épp "
                                   "ezért én jövök!")
            if dont == "n" or kszam > 4 or jatekos >= 21:
                if kszam < 2 or jatekos < 15:
                    yield ctx.mond(
                        "Szabálytalan művelet, ezért ön kiesett! Máskor "
                        "figyelmesebben olvassa el a játék leírását! Én nem "
                        "szomorkodok, mivel ilyenkor mindent visz a bank!")
                    yield ctx.vege()
                    return
                # a gép húz, amíg el nem éri a 19-et
                gep = 0
                while gep < 19:
                    nev, ertek = _h21_huz(pakli, huzott)
                    gep += ertek
                    yield ctx.mond(f"A kapott kártya a {nev}, melynek értéke: "
                                   f"{ertek}. A kártyáim értéke: {gep}.")
                kilep = True

        yield ctx.mond(f"Az én kártyáim értéke: {gep}, az öné pedig "
                       f"{jatekos}.")

        # ---- a nyertes kiválasztása (a forrás elágazásai szerint) --------
        if jatekos <= 21 and gep <= 21:
            if jatekos > gep:
                yield ctx.mond("Gratulálok, ön nyert!")
                jnyert += 1
            elif jatekos == gep:
                yield ctx.mond("Hopsz, döntetlen! Önnek kivételesen nagy "
                               "szerencséje van...")
                dontetlen += 1
            else:
                yield ctx.mond("Hát ez ma önnek nem jött be... Na de nembaj, "
                               "majd legközelebb!")
                gnyert += 1
        else:
            if jatekos > 21 and gep > 21:
                yield ctx.mond("Hát így jártunk, egyikünk se nyert.")
                vesztett += 1
            elif jatekos <= 21:
                yield ctx.mond("Gratulálok, ön nyert!")
                jnyert += 1
            else:
                yield ctx.mond("Sajnálom, ön sajnos most nem nyert... De ne "
                               "adja fel, próbálkozzon tovább!")
                gnyert += 1

        # ---- új parti? ---------------------------------------------------
        while True:
            v = yield ctx.kerdez("Szeretne még egyet játszani? (i/n)")
            d = (v or "").strip().lower()[:1]
            if d == "i":
                yield ctx.mond("Akkor hajrá! Úgyis én fogok nyerni!")
                break
            if d == "n":
                yield ctx.mond(_h21_eredmeny(jszam, jnyert, gnyert,
                                             dontetlen, vesztett))
                yield ctx.vege()
                return
            # bármi más: újra kérdez


# ================================================================= KOCKAJÁTÉK
# Forrás: KOCKA.HTP (Homelab 4 / Brailab). Egyszemélyes kockapárbaj a gép
# ellen: hatszor dobsz te, hatszor a gép, a nagyobb összeg nyer. A párbeszéd
# szó szerint a forrásból; a mangolt ékezeteket a valódi (Brailabon megjelent)
# magyar szöveghez igazítva. Az eredeti időzítés-alapú „gördülő kocka" (a K
# lenyomásának pillanata adta az értéket) akadálymentes megfelelője: dobásra
# egyenletes 1–6 véletlen.

_KOCKA_ISMERTETO = (
    "A JÁTÉKOT EGY SZEMÉLY JÁTSZHATJA.",
    "A JÁTÉKBAN HATSZOR DOBHATSZ ÉS HATSZOR DOBHATOK ÉN AMI EGY FORDULÓNAK "
    "SZÁMÍT.",
    "HA ARRA KÉRLEK HOGY DOBJÁL AKKOR NEKED CSAK A KÁ BILLENTYT KELL "
    "MEGPÖTTYINTENI.",
    "AMÍG EZT NEM TESZED MEG A KOCKA GURUL GURUL ÉS GURUL.",
    "ÉN A DOBÁSOK UTÁN MINDÍG ÖSSZESÍTEK ÉS KÖZLÖM AZ ADDIG SZERZETT "
    "PONTSZÁMOKAT.",
    "VIGYÁZZ AZÉRT!",
    "EGY OLYAN MESTERT MINT ÉN NAGYON NEHÉZ LEGYŐZNI.",
    "EZT PERSZE NEM AZÉRT MONDOM HOGY ELIJESSZELEK.",
    "JÓ SZÓRAKOZÁST KÍVÁN A PROGRAM KÉSZÍTŐJE.",
)
_KOCKA_ORD = ("AZ ELSŐ", "A MÁSODIK", "A HARMADIK", "A NEGYEDIK",
              "AZ ÖTÖDIK", "A HATODIK")
_KOCKA_OSSZ = (None, "A KÉT", "A HÁROM", "A NÉGY", "AZ ÖT", "A HAT")


def jatek_kocka(ctx):
    yield ctx.mond("KOCKAJÁTÉK!")
    nev = ((yield ctx.kerdez("KÉRLEK MUTATKOZZÁL BE. MI AZ UTÓNEVED?"))
           or "").strip() or "BARÁTOM"
    yield ctx.mond(f"SZERBUSZ {nev}. ÉN HOMELAB 4 VAGYOK.")
    v = yield ctx.kerdez(f"{nev} KÉRED AZ ISMERTETŐT? (I VAGY N)")
    if igen(v, False):
        for sor in _KOCKA_ISMERTETO:
            yield ctx.mond(sor)

    while True:
        v = yield ctx.kerdez("AKKOR KEZDHETJÜK A JÁTÉKOT? (I VAGY N)")
        if igen(v, False):
            break
        yield ctx.mond("NE VICCELJ VELEM! NE BOSSZANTS FÖLBARÁTOM!")
        yield ctx.mond("HÁT JÓ.")
        yield ctx.mond("EGY KICSIT MÉG HAGYLAK GONDOLKODNI. DE NE ÖRÜLJ! "
                       "NEMSOKÁRA MEGINT FÖLTESZEK EGY KÉRDÉST BARÁTOM.")

    te = gep = 0
    for i in range(6):
        biztat = "DE ÜGYES LEGYÉL ÁM!" if i == 0 else "LÉGYSZÍVES DOBJÁL."
        yield ctx.kerdez(f"{nev} MOST TE DOBSZ. {biztat} "
                         "(Nyomd meg a K betűt, majd Enter, a dobáshoz.)")
        d = random.randint(1, 6)
        te += d
        yield ctx.mond(f"{_KOCKA_ORD[i]} DOBÁSOD ÉRTÉKE {d}.")
        yield ctx.mond(f"CSAK {d}!")
        if i > 0:
            yield ctx.mond(f"{_KOCKA_OSSZ[i]} DOBÁSOD ÖSSZÉRTÉKE {te}.")

        yield ctx.mond("FIGYELJ! MOST ÉN DOBOK.")
        g = random.randint(1, 6)
        gep += g
        yield ctx.mond(f"{_KOCKA_ORD[i]} DOBÁSOM ÉRTÉKE {g}.")
        yield ctx.mond("JÓ DOBÁS VOLT !" if i == 0 else "JÓ DOBÁS VOLT!")
        if i > 0:
            yield ctx.mond(f"{_KOCKA_OSSZ[i]} DOBÁSOM ÖSSZÉRTÉKE {gep}.")

    yield ctx.mond(f"EREDMÉNYHIRDETÉS! {nev}! EREDMÉNYHIRDETÉS!")
    if te > gep:
        yield ctx.mond(f"{nev} GRATULÁLOK NEKED! SAJNOS MOST KIKAPTAM TŐLED. "
                       "HÁNY PONTTAL IS?")
        yield ctx.vege(f"Ó CSAK {te - gep} PONTTAL! DE FOGUNK MÉG MI JÁTSZANI! "
                       "ÉN NEM ADOM FÖL. SOHA. SOHA!")
    elif te < gep:
        yield ctx.mond("HA HA! HA HA HA!")
        yield ctx.vege(
            "MEGLÁTSZIK HOGY KI A MESTER A KOCKADOBÁSBAN BARÁTOM! "
            f"{gep - te} PONTTAL KIKAPTÁL TŐLEM. NE BÚSLAKODJ {nev}. "
            "MAJD MÁSKOR MEGPRÓBÁLOD!")
    else:
        yield ctx.vege(
            "DÖNTETLEN A KETTŐNK EREDMÉNYE BARÁTOM! "
            f"{te} PONTOD VAN NEKED ÉS NEKEM. KÉRSZ-E VISSZAVÁGÓT? {nev}! "
            "GONDOLKODJ EL EZEN! ÉN ADDIG MAJD VÁROK.")


# =================================================================== FEJTÖRŐ
# Forrás: FEJTORO.HTP (Homelab 4). Tíz szorzási feladat; jó válasz +5, rossz
# −10, a végén osztályzat. A párbeszéd szó szerint a forrásból. Az eredeti ~10
# másodperces gondolkodási időt AKADÁLYMENTESSÉGBŐL nem kényszerítjük ki (a vak
# játékosnak nyugodtan lehet gépelni); az üres/nulla válasz a forrás „SZ=0"
# ágára visz (a „buta vagy" büntetés), a hibás szám a „szorzótábla" ágra.

_FEJTORO_ISMERTETO = (
    "TÍZ KÉRDÉSRE KELL FELELNED!",
    "MINDEN JÓ VÁLASZODAT ÖT PONTTAL DÍJAZOM.",
    "HA VISZONT ROSSZUL VÁLASZOLSZ!",
    "AKKOR SZIGORÚAN TÍZ PONTODAT ELVESZEM.",
    "KÖRÜLBELÜL TÍZ MÁSODPERC GONDOLKODÁSI IDŐ ÁLL RENDELKEZÉSEDRE.",
    "HA VÁLASZOLNI KÍVÁNSZ AKKOR CSAK A MEGFELELŐ SZÁMOT VAGY SZÁMOKAT KELL "
    "MEGPÖCCINTENED.",
    "AMENNYIBEN A GONDOLKODÁSI IDŐN BELÜL NEM VÁLASZOLSZ A MEGADOTT KÉRDÉSRE "
    "UGYANCSAK TÍZ PONTOT VESZEK EL TŐLED.",
    "JÓ FEJTÖRÉST KÍVÁNOK NEKED!",
)


def jatek_fejtoro(ctx):
    yield ctx.mond("*MATEMATIKA*")
    yield ctx.mond("SZERBUSZ! ÉN HOMELAB 4 SZÁMÍTÓGÉP VAGYOK.")
    while True:
        nev = ((yield ctx.kerdez("ÉS NEKED MI AZ UTÓNEVED? KÉRLEK ÍRD BE!"))
               or "").strip()
        if nev:
            break
        yield ctx.mond("ARRA KÉRTELEK HOGY MUTATKOZZÁL BE! NEM PEDIG ARRA "
                       "HOGY JÁTSZÁL VELEM!")
    v = yield ctx.kerdez(f"{nev} KÉRED AZ ISMERTETŐT? (I VAGY N)")
    if igen(v, False):
        for sor in _FEJTORO_ISMERTETO:
            yield ctx.mond(sor)

    while True:
        v = yield ctx.kerdez("KEZDHETJÜK A TANULÁST? (I VAGY N)")
        if igen(v, False):
            break
        yield ctx.mond("HA KEZDHETÜNK KÉRLEK NYOMD LE AZ I BILLENTYT!")

    pont = 0
    for _ in range(10):
        a = random.randint(1, 9)
        b = random.randint(1, 9)
        helyes = a * b
        v = yield ctx.kerdez(f"{nev}! mennyi {a}*{b}?")
        sz = szam(v)
        if sz is not None and sz == helyes:
            yield ctx.mond("GRATULÁLOK! JÓL MEGFEJTETTED A SZÁMOT! EZ PLUSSZ "
                           "ÖT PONTOT JELENT NEKED.")
            pont += 5
        elif sz is None or sz == 0:
            yield ctx.mond("JAJ DE BUTA VAGY! ILYEN EGYSZER KÉRDÉSRE SEM TUDSZ "
                           "VÁLASZOLNI? VAGY TALÁN ALUDTÁL? EZÉRT TÍZ PONT "
                           "LEVONÁS JÁR!")
            pont -= 10
        else:
            yield ctx.mond(f"HOGY TANULTAD MEG A SZORZÓTÁBLÁT? HOGYAN LEHETNE "
                           f"{a}*{b} {sz}? EZ MINUSZ TÍZ PONTOT JELENT.")
            pont -= 10
        yield ctx.mond(f"{a}*{b}={helyes}.")
        yield ctx.mond(f"MOST {pont} PONTOD VAN.")

    if pont < 1:
        yield ctx.vege("ELÉGTELEN A TUDÁSOD! HA SOKAT TANULSZ MÉG VIHETED "
                       "FÖLJEBB IS BARÁTOM.")
    elif pont < 16:
        yield ctx.vege("ELÉGSÉGES EREDMÉNY A TUDÁSOD! TANULNI SOSEM ÁRT. EZT "
                       "JÓ LESZ HA BELÁTOD.")
    elif pont < 31:
        yield ctx.vege("KÖZEPES AZ EREDMÉNYED ÉS A TUDÁSOD! TANULJ MÉG EGY "
                       "KICSIT! NEM BÁNOD MEG. MEGLÁTOD!")
    elif pont < 41:
        yield ctx.vege("JÓ AZ ELMÉD ÉS A TUDÁSOD! EZÉRT MÁR DÍCSÉRET JÁR. "
                       "CSAK ÍGY TOVÁBB BARÁTOM!")
    else:
        yield ctx.vege("RAGYOGÓAN MEGY A MATEMATIKA NEKED! EZÉRT MÁR "
                       "GRATULÁCIÓ JÁR. GRATULÁLOK NEKED!")
