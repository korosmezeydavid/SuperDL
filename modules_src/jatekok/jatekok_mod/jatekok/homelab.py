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
# a gép SZÖVEGES DUMÁJA lépéskor (a forrásból – ez adja a játék humorát)
_AMOBA_DUMA = (
    "MEGVAN.", "TESSÉK.", "ÍGY NI!", "NESZE TE TRÓGER!", "NA, ERRE MIT LÉPSZ?",
    "MICSODA EGY ERŐSZAKOS EMBER VAGY!", "EZ TÉNYLEG NEM FÉR A BŐRÉBEN!",
    "CSAK NEM FORGATSZ VALAMIT A FEJEDBEN?",
)


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
            yield ctx.mond(random.choice(_AMOBA_DUMA))     # a forrás humoros dumája
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


# ================================================================== KOCKAPARTI
# Forrás: KOCKA2.HTP (Homelab 4 / Brailab). Mint a KOCKA, de TE adod meg, hány
# menet legyen (1–100), és döntetlennél visszavágót kérhetsz. Párbeszéd szó
# szerint a forrásból; a dobás akadálymentes megfelelője egyenletes 1–6. Az
# eredeti egy nyilvánvaló elgépelést tartalmaz (a gép dobásánál „HOMELAB 4 MOST
# TE DOBSZ" szerepel „MOST ÉN DOBOK" helyett) – ezt a félreérthetőség miatt
# javítottuk, minden más szöveg érintetlen.

_KOCKA2_ISMERTETO = (
    "A JÁTÉKOT EGY SZEMÉLY JÁTSZHATJA.",
    "A JÁTÉKBAN TE SZABOD MEG HOGY HÁNY MENET LEGYEN A FORDULÓ.",
    "HA AZT MONDOM NEKED HOGY INDUL A KOCKÁD AKKOR NEKED CSAK A KÁ BILLENTYT "
    "KELL MEGPÖTTYINTENI.",
    "AMÍG A BILLENTYT NEM PÖTTYINTED MEG A KOCKÁD GURUL GURUL ÉS FOLYAMATOSAN "
    "GURUL.",
    "ÉN A DOBÁSOK UTÁN MINDÍG ÖSSZESÍTEK ÉS KÖZLÖM AZ ADDIG SZERZETT "
    "PONTSZÁMOK ÖSSZÉRTÉKÉT.",
    "VIGYÁZZ AZÉRT!",
    "EGY OLYAN MESTERT MINT ÉN NAGYON NEHÉZ LEGYŐZNI.",
    "EZT PERSZE NEM AZÉRT MONDOM HOGY ELIJESSZELEK.",
)


def jatek_kockaparti(ctx):
    yield ctx.mond("KOCKAJÁTÉK!")
    nev = ((yield ctx.kerdez("KÉRLEK MUTATKOZZÁL BE! MI AZ UTÓNEVED?"))
           or "").strip() or "BARÁTOM"
    yield ctx.mond(f"SZERBUSZ {nev}! ÉN HOMELAB 4 VAGYOK.")
    v = yield ctx.kerdez(f"{nev} KÉRED AZ ISMERTETŐT? (I VAGY N)")
    if igen(v, False):
        yield ctx.mond("ISMERTETŐ!")
        for sor in _KOCKA2_ISMERTETO:
            yield ctx.mond(sor)

    while True:                                     # a teljes parti, visszavágóval
        while True:
            v = yield ctx.kerdez("AKKOR KEZDHETJÜK A JÁTÉKOT? (I VAGY N)")
            if igen(v, False):
                break
            yield ctx.mond("A KUTYAFÁJÁT! MEDDIG VÁRJAK MÉG?")
            yield ctx.mond("HÁT JÓ. EGY KICSIT VÁROK. NEMSOKÁRA MAJD MEGINT "
                           "MEGKÉRDEZLEK!")

        while True:
            v = yield ctx.kerdez("HÁNY MENET LEGYEN A FORDULÓ?")
            menetszam = szam(v)
            if menetszam is None or menetszam < 1:
                yield ctx.mond("NE SZÓRAKOZZÁL VELEM! MOST JÁTSZUNK VAGY PEDIG "
                               "HÜLYÉSKEDÜNK.")
                continue
            if menetszam > 100:
                yield ctx.mond("TÚL NAGY SZÁM EZ BARÁTOM! NEKEM NINCS ENNYI "
                               "IDŐM! VÁLASSZ KISEBB SZÁMOT. ÉN ADDIG MAJD "
                               "VÁROK!")
                continue
            break

        yield ctx.mond(f"A JÁTÉK {menetszam} MENET.")
        yield ctx.mond("KÍVÁNCSI VAGYOK A VÉGÉN MAJD KI NEVET!")
        yield ctx.mond("KEZDŐDJÖN EL HÁT A FORDULÓ BARÁTOM! KÍVÁNCSIAN VÁROM "
                       "AZ EREDMÉNYÉT!")

        te = gep = 0
        for m in range(1, menetszam + 1):
            yield ctx.mond(f"{m}. MENET!")
            if m == menetszam:
                yield ctx.mond("FIGYELJ! EZ AZ UTOLSÓ MENET.")
            yield ctx.kerdez(f"{nev} MOST TE DOBSZ! INDUL A KOCKÁD. "
                             "(Nyomd meg a K betűt, majd Enter.)")
            d = random.randint(1, 6)
            te += d
            yield ctx.mond(f"A DOBÁSOD ÉRTÉKE {d}.")
            yield ctx.mond(f"CSAK {d}!")
            if m > 1:
                yield ctx.mond(f"{m} DOBÁSOD ÖSSZÉRTÉKE {te}.")

            yield ctx.mond("MOST ÉN, A HOMELAB 4, DOBOK! INDUL A KOCKÁM.")
            g = random.randint(1, 6)
            gep += g
            yield ctx.mond(f"A DOBÁSOM ÉRTÉKE {g}.")
            yield ctx.mond("JÓ DOBÁS VOLT!")
            if m > 1:
                yield ctx.mond(f"{m} DOBÁSOM ÖSSZÉRTÉKE {gep}.")

        yield ctx.mond(f"EREDMÉNYHIRDETÉS! {nev}! EREDMÉNYHIRDETÉS!")
        if te > gep:
            yield ctx.vege(
                "GRATULÁLOK A GYŐZELMEDHEZ BARÁTOM! SAJNOS MOST KIKAPTAM "
                f"TŐLED. HÁNY PONTTAL IS? Ó CSAK {te - gep} PONTTAL! DE NE "
                "ÖRÜLJ! FOGUNK MÉG MI JÁTSZANI! ÉN NEM ADOM FÖL. SOHA. SOHA!")
            return
        if te < gep:
            yield ctx.mond("GYŐZTEM! GYŐZTEM! HALI HALI HALI! HÓ.")
            yield ctx.vege(
                "JAJ DE JAJ DE JAJ DE JÓ! MEGLÁTSZIK HOGY KI A MESTER A "
                f"KOCKADOBÁSBAN BARÁTOM! {gep - te} PONTTAL KIKAPTÁL TŐLEM. "
                "NE BÚSLAKODJ. MAJD MÁSKOR MEGPRÓBÁLOD!")
            return
        # döntetlen → visszavágó
        yield ctx.mond("DÖNTETLEN A KETTŐNK EREDMÉNYE BARÁTOM! "
                       f"{te} PONTOD VAN NEKED ÉS NEKEM.")
        v = yield ctx.kerdez("KÉRSZ-E VISSZAVÁGÓT? (I VAGY N) DÖNTSD EL "
                             "KÉRLEK! ÉN ADDIG MAJD VÁROK!")
        if igen(v, False):
            continue
        yield ctx.vege("REMÉLEM AKKOR JÓL SZÓRAKOZTÁL BARÁTOM! HA MÁSKOR "
                       "UNATKOZOL, KAPCSOLJ BE BÁTRAN! MEGLÁTOD. NEM BÁNOD!")
        return


# ============================================================ CÉLOZZ A HAJÓRA
# Forrás: CELOZZ.HTP – „KÉSZ RUN TETTE SCHUCK ANTAL", 1987. december 22–28.
# A szerző a REM-sorban a FELESÉGÉNEK ajánlotta a programot – ezt tiszteletből
# megőrizzük és a játék elején elmondjuk. 20×20-as tengeri mező, rejtett hajó,
# 10 lövedék; irány-visszajelzés (észak/dél/kelet/nyugat), tízszeri hibázásnál
# hadbíróság. A szöveg szó szerint a forrásból; a „gyorsbeszéd?" kérdés a
# Brailab hardveres beszédsebesség-kapcsolója volt, ezt kihagyjuk (a retró hang
# tempóját a Hangbeállítás kezeli).

_CELOZZ_INTRO = (
    "EGY 20-SZOR 20-AS MEZŐBEN ISMERETLEN HELYEN ELLENSÉGES HAJÓ TARTÓZKODIK.",
    "EZT KELL ELSÜLLYESZTENED.",
    "A FELADAT VÉGREHAJTÁSÁHOZ 10 LÖVEDÉKED VAN.",
    "HA NEM TALÁLOD EL A HAJÓT, KÜLÖNBÖZŐ BÜNTETÉSEK VÁRNAK RÁD!",
    "AZ ÁGYÚ BEÁLLÍTÁSÁT A GÉP VÉGZI AZ ÁLTALAD MEGADOTT KOORDINÁTÁK ALAPJÁN.",
    "A KILÖVÉS UTÁN PONTOS TÁJÉKOZTATÁST KAPSZ A BECSAPÓDÁS HELYÉRŐL.",
    "KELLEMES IDŐTÖLTÉST KÍVÁNOK!",
    "FIGYELJ! A MEZŐ BAL ALSÓ SARKÁNAK KOORDINÁTÁI 1 1. A JOBB FELSŐ SAROK "
    "KOORDINÁTÁI 20 20. AZ ELSŐ KOORDINÁTA A FÜGGŐLEGES, A MÁSODIK A VÍZSZINTES "
    "SOROKRA VONATKOZIK.",
)


def jatek_celozz(ctx):
    yield ctx.mond("CÉLOZZ A HAJÓRA!")
    yield ctx.mond("A szerző, Schuck Antal, ezt a játékot 1987-ben a "
                   "feleségének ajánlotta.")
    for sor in _CELOZZ_INTRO:
        yield ctx.mond(sor)

    while True:                                     # egy ütközet
        yield ctx.mond("KEZDŐDIK AZ ÜTKÖZET!")
        yield ctx.mond("ELLENSÉGES HAJÓ BUKKANT FEL A LÁTHATÁRON!")
        while True:
            v = yield ctx.kerdez("FELKÉSZÜLTÉL A MEGSEMMISÍTÉSÉRE? (I VAGY N)")
            if igen(v, False):
                break
            yield ctx.mond("NE TÉTOVÁZZ!")

        xa = random.randint(1, 20)
        ya = random.randint(1, 20)
        z = 0
        talalt = False
        while z < 10:
            while True:
                v = yield ctx.kerdez("KÉREM AZ EGYIK KOORDINÁTÁT! (1–20)")
                xb = szam(v, 1, 20)
                if xb is not None:
                    break
                yield ctx.mond("NEM LÉTEZŐ JELZŐSZÁM! 1-ES ÉS 20-AS SZÁM "
                               "KOORDINÁTÁK KÖZÖTT TARTÓZKODIK A HAJÓ.")
            while True:
                v = yield ctx.kerdez("KÉREM A MÁSIK KOORDINÁTÁT! (1–20)")
                yb = szam(v, 1, 20)
                if yb is not None:
                    break
                yield ctx.mond("NEM LÉTEZŐ JELZŐSZÁM! 1-ES ÉS 20-AS SZÁM "
                               "KOORDINÁTÁK KÖZÖTT TARTÓZKODIK A HAJÓ.")
            z += 1
            if xa == xb and ya == yb:
                yield ctx.mond(f"{z} LÖVÉSSEL ELSÜLLYESZTETTED A TÁMADÓKAT. "
                               "JÓ TÜZÉR VAGY!")
                talalt = True
                break
            yield ctx.mond(f"EDDIG {z} LÖVEDÉKET HASZNÁLTÁL EL.")
            irany = []
            if xa > xb:
                irany.append("DÉL")
            if xa < xb:
                irany.append("ÉSZAK")
            if ya > yb:
                irany.append("NYUGAT")
            if ya < yb:
                irany.append("KELET")
            yield ctx.mond(f"A HAJÓTÓL {' '.join(irany)} IRÁNYBAN A TENGERBE "
                           "CSAPÓDOTT A LÖVEDÉK.")

        if not talalt:
            yield ctx.mond("GYENGE TELJESÍTMÉNYEDDEL ELPAZAROLTAD A LŐSZERT. "
                           "EZÉRT HADBÍRÓSÁG ELÉ KERÜLSZ.")
            q = random.randint(1, 10)
            yield ctx.mond("A BÍRÓSÁG TANÁCSKOZIK.")
            b = random.randint(1, 3)
            if b == 1:
                yield ctx.mond(f"A BÍRÓSÁG {q} NAPRA VÉCÉTAKARÍTÁSRA ÍTÉLT.")
            elif b == 2:
                yield ctx.mond(f"A BÍRÓSÁG {q} HÉTIG TARTÓ AKNAKERESŐ "
                               "SZOLGÁLATRA ÍTÉLT.")
            else:
                yield ctx.mond(f"A BÍRÓSÁG {q} HÓNAPI FOGDÁRA ÍTÉLT.")
            yield ctx.mond("LETELT A BÜNTETÉSED.")

        while True:
            v = yield ctx.kerdez("MARADSZ-E A PARTVÉDELEMNÉL? (I VAGY N)")
            d = (v or "").strip().lower()[:1]
            if d == "i":
                yield ctx.mond("AKKOR SIESS A HELYEDET ELFOGLALNI, MERT ÚJABB "
                               "TÁMADÁS FENYEGET.")
                break
            if d == "n":
                yield ctx.vege("NAGYON SAJNÁLOM HOGY ÍGY DÖNTÖTTÉL. A "
                               "VISZONTLÁTÁSRA.")
                return
            yield ctx.mond("MI EZ A FEGYELMEZETLENSÉG? PONTOS VÁLASZT KÉREK!")


# ========================================================= TÍZ FELES (10FELES)
# Forrás: 10FELES.HTP (Homelab). Számkitaláló 1..N között, TÍZ tippel; minél
# hamarabb találsz, annál több „feles" a jutalom – csavaros, pálinkás humorral.
# Öt kör után a gép „nem játszik részegekkel". A szöveg szó szerint a forrásból.

_TIZFELES_ISMERTETO = (
    "HA FÖLTESZEM NEKED AZT A KÉRDÉST HOGY MI LEHESSEN A LEGNAGYOBB GONDOLT "
    "SZÁM AKKOR NEKED IDE EGY SZÁMOT KELL BEÍRNI.",
    "HA PÉLDÁUL SZÁZAT ÍRSZ BE AKKOR ÉN 1 ÉS 100 KÖZÖTT VÁLASZTHATOK CSAK KI "
    "SZÁMOT.",
    "TERMÉSZETESEN IDE BÁRMILYEN MÁS SZÁMOT IS BEÍRHATSZ, NULLA ÉS A NEGATÍV "
    "SZÁMOK KIVÉTELÉVEL.",
    "ÉN A MEGADOTT HATÁRON BELÜL BÁRMELYIK SZÁMRA GONDOLHATOK, AMIT NEKED KI "
    "KELL TALÁLNI.",
    "FIGYELEM! CSAK TÍZ FELESED VAN.",
    "EZ AZT JELENTI HOGY TÍZSZER TIPPELHETSZ CSAK A GONDOLT SZÁMRA.",
    "AHÁNYSZOR NEM TALÁLOD EL A GONDOLT SZÁMOT, ANNYIVAL KEVESEBB FELEST "
    "NYERHETSZ CSAK.",
    "JÓ SZÓRAKOZÁST KÍVÁN A PROGRAM KÉSZÍTŐJE A JÁTÉKHOZ.",
)
# a győzelmi üzenet aszerint, hányadik tippre találtál el (1..10) – szó szerint
_TIZFELES_NYERT = (
    "GRATULÁLOK AZ EREDMÉNYHEZ BARÁTOM! HA ILYEN JÓL TUDSZ TIPPELNI, PRÓBÁLD "
    "KI SZERENCSEJÁTÉKON!",
    "KIVÁLÓ EREDMÉNY MÉG EZ IS BARÁTOM! KÖSZÖNÖM A FELESEDET! A TÖBBI KILENCET "
    "NEKED AJÁNLOM!",
    "EZ MÁR CSAK JÓ EREDMÉNY BARÁTOM! NE BÚSLAKODJ! JUTALOMBÓL ITT VAN NYOLC "
    "FELES. EGÉSZSÉGEDRE! NEKED MEG EZT KÍVÁNOM.",
    "JÓ EREDMÉNY MÉG A TUDOMÁNYOD! HÁROM FELESEDET MEGITTAM, HÉT MARADT NEKED. "
    "EZ A JUTALMAD BARÁTOM!",
    "JÓ KEDVEM KEZD LENNI A NÉGY FELESEDTŐL BARÁTOM! DE JÓ NEKED, TE MÉG "
    "MEGIHATSZ HATOT! LELKEMET NEM SZÁNOD?",
    "ÖT FELEST VESZÍTETTÉL BARÁTOM! ÉN EZEKET MEGITTAM. A TÖBBI ÖT A TIÉD "
    "BARÁTOM!",
    "ELÉGSÉGES EREDMÉNY BARÁTOM! NÉGY FELES A TIED, HAT AZ ENYÉM! KÖSZÖNÖM "
    "BARÁTOM!",
    "TUDÁSODÉRT HÁROM FELES A JUTALOM! A MARADÉK HETET MAJD ÉN MEGISZOM.",
    "GYENGE A TUDÁSOD ÁTLAGA BARÁTOM! NYOLC FELES MÁR MÉREG. KETTŐ A TIÉD "
    "PAJTÁSOM!",
    "EGY FELESED MARADT CSAK BARÁTOM! DE ÉN TŐLED MÁR EZT IS SAJNÁLOM.",
)


def jatek_tizfeles(ctx):
    yield ctx.mond("TÍZ FELES A TUDOMÁNYOD! HA A SZÁMOT ELTALÁLOD.")
    v = yield ctx.kerdez("KÉRED AZ ISMERTETŐT? (I VAGY N)")
    if igen(v, False):
        for sor in _TIZFELES_ISMERTETO:
            yield ctx.mond(sor)

    kor = 0
    while True:
        while True:
            v = yield ctx.kerdez("MI LEHESSEN A LEGNAGYOBB GONDOLT SZÁM?")
            felso = szam(v)
            if felso is not None and felso >= 1:
                break
            yield ctx.mond("LEHETŐLEG 1 VAGY ANNÁL NAGYOBB SZÁMOT KÉREK.")
        x = random.randint(1, felso)
        yield ctx.mond(f"GONDOLTAM EGY SZÁMOT 1 ÉS {felso} KÖZÖTT.")

        talalt = False
        i = 0
        while i < 10:
            v = yield ctx.kerdez(f"{i + 1}. tipp (1 és {felso} között):")
            tipp = szam(v)
            if tipp is None:
                yield ctx.mond("Számot kérek – ez a tipp nem számít.")
                continue                       # érvénytelenre ne fogyjon feles
            i += 1
            if tipp < x:
                yield ctx.mond("NAGYOBB SZÁMOT KERESS! UGROTT EGY FELES!")
            elif tipp > x:
                yield ctx.mond("KISSEBB SZÁMOT KERESS! UGROTT EGY FELES!")
            else:
                yield ctx.mond(_TIZFELES_NYERT[i - 1])
                talalt = True
                break
        if not talalt:
            yield ctx.mond("VESZÍTETTÉL BARÁTOM! ELFOGYTAK A FELESEID. A "
                           f"GONDOLT SZÁM {x} VOLT PAJTÁSOM.")

        kor += 1
        if kor == 5:
            yield ctx.vege(
                "ÁLLJUNK MEG EGY SZÓRA! NEM GONDOLOD HOGY KICSIT SOKAT ITTÁL "
                "MÁR BARÁTOM? GONDOLKODJ EL EZEN. ÉN RÉSZEGEKKEL NEM JÁTSZOM!")
            return
        v = yield ctx.kerdez("SZERETNÉL MÉG VELEM JÁTSZANI? (I VAGY N)")
        if igen(v, False):
            yield ctx.mond("AKKOR TOVÁBBI JÓ SZÓRAKOZÁST A JÁTÉKHOZ.")
            continue
        yield ctx.vege("REMÉLEM AKKOR JÓL SZÓRAKOZTÁL BARÁTOM! HA MÁSKOR "
                       "UNATKOZOL, KAPCSOLJ BE BÁTRAN! MEGLÁTOD. NEM BÁNOD!")
        return


# ============================================== FOGADÁSOS AUTÓVERSENY (FOGADAS)
# Forrás: FOGADAS.HTP – „Produced by Balogh Tibor", HOMELAB 3, 1984. december
# (átdolgozott változat: 1986. július). Több (max 4) játékos fogad az 1980-as
# évek Forma-1-eseire (Lauda, Prost, McLaren, Alboreto); mindenki 200 forinttal
# indul, a nyertes fogadás a téttel nő, a vesztes csökken, 0-nál kiesel, 800
# forinttól nyersz. A grafikus versenyt akadálymentesen: véletlen futam, a
# győztest bemondjuk.

_FOGADAS_ISMERTETO = (
    "EZ EGY AUTÓVERSENY JÁTÉK.",
    "A JÁTÉKOT MAX NÉGYEN JÁTSZHATJÁK.",
    "MINDEN JÁTÉKOS MEGNEVEZ EGY AUTÓVERSENYZŐT AKIRE FOGADNI AKAR, ÉS MEGADJA "
    "A TÉTET, AMENNYIRE A NYERÉSI ESÉLYEIT ÉRTÉKELI.",
    "A KÉRDÉSEKET SAMU, A GÉP TESZI FEL.",
    "AZ AUTÓVERSENYZŐK NEVEI: LAUDA, PROST, MC LAREN, ALBORETO.",
    "FIGYELJ! A VERSENYZŐK NEVEIT PRECÍZEN ÍRD LE.",
)
_FOGADAS_VERSENYZOK = ("LAUDA", "PROST", "MC LAREN", "ALBORETO")


def _fogadas_versenyzo(v):
    """A beírt nevet a négy versenyzőhöz illeszti (ékezet/szóköz/kisbetű nélkül)."""
    t = ekezet_nelkul((v or "").strip().lower()).replace(" ", "")
    if not t:
        return None
    for nev in _FOGADAS_VERSENYZOK:
        n = ekezet_nelkul(nev.lower()).replace(" ", "")
        if n == t or n.startswith(t):
            return nev
    return None


def jatek_fogadas(ctx):
    yield ctx.mond("HOMELAB 3 – FOGADÁSOS AUTÓVERSENY. Produced by Balogh "
                   "Tibor, 1984.")
    v = yield ctx.kerdez("Kéred az ismertetőt? (i/n)")
    if igen(v, False):
        for sor in _FOGADAS_ISMERTETO:
            yield ctx.mond(sor)

    while True:
        v = yield ctx.kerdez("HÁNY JÁTÉKOS JÁTSZIK? (MAX 4 FŐ)")
        letszam = szam(v, 1, 4)
        if letszam is not None:
            break
        yield ctx.mond("Egy és négy közötti számot kérek.")
    nevek = []
    for i in range(letszam):
        v = yield ctx.kerdez(f"{i + 1}. JÁTÉKOS NEVE?")
        nevek.append((v or "").strip() or f"{i + 1}. játékos")
    penz = [200] * letszam                     # mindenki 200 forinttal indul

    while True:
        aktiv = [i for i in range(letszam) if penz[i] > 0]
        if not aktiv:
            yield ctx.mond("MINDENKI VESZTETT!")
            v = yield ctx.kerdez("ISMÉTLÉS? (I=IGEN, N=NEM)")
            if igen(v, False):
                penz = [200] * letszam
                continue
            yield ctx.vege("JÖHET A KÖVETKEZŐ PROGRAM.")
            return
        gyoztes = next((i for i in aktiv if penz[i] >= 800), None)
        if gyoztes is not None:
            yield ctx.mond(f"{nevek[gyoztes]}, GYŐZTÉL!")
            v = yield ctx.kerdez("ISMÉTLÉS? (I=IGEN, N=NEM)")
            if igen(v, False):
                penz = [200] * letszam
                continue
            yield ctx.vege("JÖHET A KÖVETKEZŐ PROGRAM.")
            return

        tet = [0] * letszam
        valasztott = [None] * letszam
        for i in aktiv:
            yield ctx.mond(f"{nevek[i]}, NEKED {penz[i]} FORINTOD VAN.")
            while True:
                v = yield ctx.kerdez("MELYIK VERSENYZŐRE TESZEL? "
                                     "(Lauda, Prost, Mc Laren, Alboreto)")
                vz = _fogadas_versenyzo(v)
                if vz:
                    break
                yield ctx.mond("Ilyen versenyző nincs – írd pontosan: Lauda, "
                               "Prost, Mc Laren vagy Alboreto.")
            valasztott[i] = vz
            while True:
                v = yield ctx.kerdez(f"MEKKORA ÖSSZEGGEL FOGADSZ {vz} "
                                     f"GYŐZELMÉRE? (0 és {penz[i]} között)")
                t = szam(v, 0, penz[i])
                if t is not None:
                    break
                yield ctx.mond(f"Nulla és {penz[i]} közötti tétet kérek.")
            tet[i] = t

        # a verseny: a négy versenyző véletlenül halad, az első a célban nyer
        yield ctx.mond("Rajt! A versenyzők elindultak...")
        poz = {nev: 0 for nev in _FOGADAS_VERSENYZOK}
        while True:
            fut = random.choice(_FOGADAS_VERSENYZOK)
            poz[fut] += 1
            if poz[fut] >= 20:
                gyoztes_vz = fut
                break
        yield ctx.mond(f"A VERSENY GYŐZTESE: {gyoztes_vz}!")

        for i in aktiv:
            if valasztott[i] == gyoztes_vz:
                penz[i] += tet[i]
                yield ctx.mond(f"{nevek[i]}: nyertél {tet[i]} forintot, "
                               f"egyenleged {penz[i]} forint.")
            else:
                penz[i] -= tet[i]
                allap = (f"egyenleged {penz[i]} forint" if penz[i] > 0
                         else "elfogyott a pénzed, kiestél")
                yield ctx.mond(f"{nevek[i]}: elvesztetted a {tet[i]} "
                               f"forintodat, {allap}.")


# ============================================== GYUFAPÖCKÖLŐ JÁTÉK (GYUFAPOC)
# Forrás: GYUFAPOC.HTP (Homelab). TELJES, forráshű újraírás (a listás kérésre):
# szabály-ismertető, elérendő pontszám (>=2), 1–5 játékos + a gép („Brailab"),
# pöckölés-esélyek a forrásból (SEMMI 5/11, KETTŐ 4/11, ÖT 1/11, a maradékból
# NEM FORDULT MEG 2/3, TÍZ 1/3), F/M döntés, gép-AI és a záró szövegek.
# A pöckölést mindig a JÁTÉKOS kezdeményezi (P), az E az állást mondja.

_GYUFAPOC_SZABALY = (
    "A gyufapöckölés népszerű játék.",
    "A játékos egy gyufásdobozt az asztal széléről felfelé pöcköl.",
    "Ha a mintás oldalával felfelé esik le a doboz, két pontot ér.",
    "Ha az élére esik, az öt pont.",
    "Minden dobásnál kérdezheted az eredményt az E betűvel.",
    "Folytatni az F, eredményt tartani az M betűvel kell.",
    "Ha a hátlapja van felül a doboznak, akkor az eredmény nulla.",
    "Ha valami csoda folytán a legkisebb lapján áll meg a gyufa, akkor az tíz "
    "pontot jelent!",
)


def _gyufapoc_dobas():
    """Egy pöckölés eredménye a FORRÁS valószínűségeivel → (üzenet, pont)."""
    xx = random.randint(1, 11)
    if xx <= 5:
        return "SEMMI!", 0
    if xx <= 9:
        return "KETTŐ!", 2
    if xx == 10:
        return "ÖT!", 5
    if random.randint(1, 3) == 3:          # a 11-esből 1/3 a csoda
        return "TÍZ!", 10
    return "NEM FORDULT MEG!", 0


def _gyufapoc_allas(nevek, pont, gep_jatszik, gep_pont):
    reszek = [f"{nevek[i]}: {pont[i]} pont" for i in range(len(nevek))]
    if gep_jatszik:
        reszek.append(f"Brailab (én): {gep_pont} pont")
    return "Állás – " + ", ".join(reszek) + ". Pöckölj!"


def _gyufapoc_gep_dont(ma, gep_pont, pont, cel):
    """A gép megtartja (True) vagy folytatja (False) – a forrás logikájával."""
    legjobb_ember = max(pont) if pont else 0
    if ma >= 10:
        return True, "Nahogy megtartom!"
    if gep_pont + ma >= cel:
        return True, "Nahogy megtartom!"
    if gep_pont > legjobb_ember:
        return True, "Vezetek. Minek kockáztassak?"
    if pont and all(p > gep_pont for p in pont):
        return False, "Utolsó vagyok. Nincs vesztenivalóm!"
    if random.randint(1, 2) == 1:
        return True, "Nem kockáztatok."
    return False, "Megpróbálom mégegyszer!"


def jatek_gyufapoc(ctx):
    yield ctx.mond("GYUFAPÖCKÖLŐ JÁTÉK")
    v = yield ctx.kerdez("Kéred a szabályokat? (i/n)")
    if igen(v, False):
        while True:
            for sor in _GYUFAPOC_SZABALY:
                yield ctx.mond(sor)
            v = yield ctx.kerdez("Értetted? (i/n)")
            if igen(v, True):
                break

    while True:                                  # egy teljes játszma
        while True:
            v = yield ctx.kerdez("Mi legyen az elérendő pontszám?")
            cel = szam(v)
            if cel is not None and cel >= 2:
                break
            yield ctx.mond("Ostobaságokat ne írj!")
        while True:
            v = yield ctx.kerdez("Hányan szeretnétek játszani? (1–5)")
            jatszok = szam(v, 1, 5)
            if jatszok is not None:
                break
            yield ctx.mond("Egytől ötig lehet!")

        nevek = []
        if jatszok == 1:
            v = yield ctx.kerdez("Írd ide a nevedet!")
            nevek.append((v or "").strip() or "Játékos")
            gep_jatszik = True
        else:
            v = yield ctx.kerdez("Én is játszak? (i/n)")
            gep_jatszik = igen(v, False)
            yield ctx.mond("Köszönöm." if gep_jatszik else "Sajnálom.")
            kerdesek = ("Kérem az első nevet!", "Kérem a másodikat is!",
                        "A harmadik nevet kérem!",
                        "Szeretném a negyedik nevet is tudni!",
                        "Örülnék az ötödik névnek!")
            for i in range(jatszok):
                v = yield ctx.kerdez(kerdesek[i])
                nevek.append((v or "").strip() or f"{i + 1}. játékos")
        if gep_jatszik:
            yield ctx.mond("Én meg Brailab vagyok!")

        pont = [0] * len(nevek)
        gep_pont = 0
        yield ctx.mond(f"{nevek[0]}, kezdd el a játékot!")
        yield ctx.mond("A P betűvel pöckölhetsz!")

        gyoztes = None
        while gyoztes is None:
            for idx in range(len(nevek)):
                ma = 0
                fo = 0
                while True:                      # egy emberi kör
                    while True:                  # pöckölés (P) / eredmény (E)
                        v = yield ctx.kerdez(
                            f"{nevek[idx]}: pöckölj! (P) — vagy E: eredmény")
                        if (v or "").strip().lower().startswith("e"):
                            yield ctx.mond(_gyufapoc_allas(
                                nevek, pont, gep_jatszik, gep_pont))
                            continue
                        break
                    do, ertek = _gyufapoc_dobas()
                    yield ctx.mond(do)
                    if do == "SEMMI!":
                        ma = 0
                        break
                    if do == "NEM FORDULT MEG!":
                        fo += 1
                        if fo == 2:
                            ma = 0
                            break
                        yield ctx.mond("Pöckölj újra!")
                        continue
                    ma += ertek
                    v = yield ctx.kerdez("Folytatod vagy marad az eredmény? "
                                         "(F/M)")
                    if (v or "").strip().lower().startswith("m"):
                        break
                    yield ctx.mond("Pöckölj újra!")
                pont[idx] += ma
                yield ctx.mond(f"{nevek[idx]} pontja: {pont[idx]}.")
                if pont[idx] >= cel:
                    gyoztes = nevek[idx]
                    break
            if gyoztes is not None:
                break

            if gep_jatszik:                      # a gép köre
                yield ctx.mond("Én jövök!")
                ma = 0
                fo = 0
                while True:
                    do, ertek = _gyufapoc_dobas()
                    yield ctx.mond(do)
                    if do == "SEMMI!":
                        ma = 0
                        break
                    if do == "NEM FORDULT MEG!":
                        fo += 1
                        if fo == 2:
                            ma = 0
                            break
                        yield ctx.mond("Újra pöckölök!")
                        continue
                    ma += ertek
                    tart, uzenet = _gyufapoc_gep_dont(ma, gep_pont, pont, cel)
                    yield ctx.mond(uzenet)
                    if tart:
                        break
                gep_pont += ma
                yield ctx.mond(f"Nekem {gep_pont} pontom van.")
                if gep_pont >= cel:
                    gyoztes = "Brailab"
                    break

        if gyoztes == "Brailab":
            yield ctx.mond("Én győztem!")
            if len(nevek) == 1:
                yield ctx.mond(f"Neked {pont[0]} pontod volt.")
            else:
                yield ctx.mond("De ti is szépen játszottatok!")
        elif len(nevek) == 1:
            yield ctx.mond("Te győztél!")
            yield ctx.mond(f"Nekem {gep_pont} pontom volt.")
        else:
            yield ctx.mond(f"{gyoztes} győzött!")
            yield ctx.mond("Gratuláljunk neki!")

        v = yield ctx.kerdez("Játszunk még egyet? (i/n)")
        if igen(v, False):
            continue
        yield ctx.vege("KÖSZÖNÖM A JÁTÉKOT!")
        return


# =============================================== SZÓ KITALÁLÓS JÁTÉK (SZOKITA)
# Forrás: SZOKITA.HTP (Homelab). Szó-mastermind: a gép egy 3 betűs magyar szóra
# gondol (a forrás 328 szavas listájából), te 3 betűs szavakat tippelsz, és
# megmondja, hány betű egyezik a SORSZÁM szerint is. X-re elárulja a szót. Az
# összehasonlítás ékezet-érzéketlen (a korabeli töltő ékezet-eltolása miatt).

_SZOKITA_SZAVAK = (
    'ADÓ AKÓ ARA ÁLL BAB BÁJ BÉL BOT CÉG DÁN DÓM EDE ELV ÉRT FAL FEN FOG GAZ '
    'GÉP HAJ HÁJ HEG HOL IDA INT JAJ JÓD KAN KÁN KÉK KÉR KOS KÖR LAP LÁT LES '
    'LOM MAR MÁZ MÉH MÓD NÉV OLÁ ORR ÓTA PAP PÉK PÓZ RAK RÉG RÉZ RÜH SÁS SOM '
    'SÜT TÁG TÁR TÉR TÓT TUS VAD VAS VÁR VÉG VÉT ZÁR ADU ALÁ ARC ÁRT BAJ BÁL '
    'BÉR BÓK CÉH DÉL DÖF EDZ ETA ÉRV FAR FÉK FOK GÁT GÉZ HAL HÁL HÉJ HON IDE '
    'INY JÁR JÓS KAP KÁR KÉL KÉS KÓD KÖT LAT LÁZ LÉC LOP MÁJ MEG MÉN NAP NÉZ '
    'OLD ORV ÖLT PÁL PÉP PUD RÁF RÉM ROM SAH SÁV SOR SZÓ TÁJ TÁV TÉT TÖK ÜDE '
    'VAJ VÁD VÁZ VÉL VON ZUG AGA APA ÁCS ÁRU BAK BÁN BOG BÖK CÉL DÉR DÖG EGY '
    'ÉLC ÉSZ FED FÉL FON GÁZ GÓL HAS HÁM HÉT HOZ IGA IRT JEL JÖN KAR KEL KÉM '
    'KÉZ KÓR KÖZ LÁB LEL LÉK LÓG MÁK MER MÉR NÁD NOS OLT OTT ÖNT PÁR POR RAB '
    'RÁG RÉS ROP SAV SEB SÖR TAG TÁL TEJ TOK TÖM ÜDV VAK VÁG VER VÉN ZAB AGY '
    'APÓ ÁGY ÁSÓ BAL BÁR BOJ CÁR COL DOB DUG EKE ÉPP ÉVA FEJ FÉM FUT GÉM HAB '
    'HAT HÁT HÉV HÓD IGE ITT JÉG JUH KAS KEN KÉN KIÉ KÖD KUN LÁM LEN LÉP LÖK '
    'MÁR MEZ MÉZ NEM ODA OLY ÓDA ÖRV PEJ PÓK RAG RÁK RÉT RÖG SÁL SEM SUT TAR '
    'TÁN TÉL TOL TÖR ÜGY VAN VÁJ VET VÉR ZAJ AHA APU ÁLD ÁSZ BÁB BÉG BOR CET '
    'DAL DOH DÜH ELÉ ÉRC FAJ FEL FÉR FÜL GÉN HAD HÁG HÁZ HIT HUN IMA IZÉ JOG '
    'JUT KÁD KÉJ KÉP KOR KÖP LAK LÁP LEP LÉT MAG MÁS MÉG MOS NÉP ODU ONT ÓRA '
    'PAD PER PÓR RAJ RÁZ RÉV RUM SÁR SOK SÜL TAT TÁP TÉP TOR TUD ÜST VAR VÁM '
    'VÉD VÉS ZÁP'
).split()


def _szokita_norm(w):
    return ekezet_nelkul((w or "").strip()).upper()


def jatek_szokita(ctx):
    yield ctx.mond("SZÓ KITALÁLÓS JÁTÉK.")
    v = yield ctx.kerdez("KÉRED A SZABÁLYOK ISMERTETÉSÉT? (igen/nem)")
    if igen(v, False):
        yield ctx.mond("GONDOLOK EGY HÁROMBETŰS SZÓRA, AMIT KI KELL TALÁLNI.")
        yield ctx.mond("Minden tipp után megmondom, hány KÖZÖS betű van a "
                       "tippelt és az általam gondolt szóban.")
        yield ctx.mond("KÖZÖS BETŰKNEK A SORSZÁM SZERINT IS MEGEGYEZŐ BETŰKET "
                       "TEKINTJÜK.")
        yield ctx.mond("Ha nem sikerül kitalálnod a szót, de mégis kíváncsi "
                       "vagy rá, írj be egy ikszet.")

    while True:
        szo = random.choice(_SZOKITA_SZAVAK)
        cel = _szokita_norm(szo)
        p = 0
        yield ctx.mond("Gondoltam egy szót. TIPPELJ!")
        while True:
            v = yield ctx.kerdez("A tipped (3 betűs szó, vagy X a megoldásért):")
            tn = _szokita_norm(v)
            if tn == "X":
                if p == 0:
                    yield ctx.mond("EJNYE! MEG SE PRÓBÁLOD?")
                elif p <= 5:
                    yield ctx.mond("NE ADD FEL! MÉG ÖTSZÖR SEM PRÓBÁLKOZTÁL.")
                    continue
                else:
                    yield ctx.mond(f"A GONDOLT SZÓ {szo}. {p} TIPPED VOLT.")
                break
            if len(tn) != 3 or not tn.isalpha() or tn[0] == tn[1]:
                yield ctx.mond("ÉRVÉNYTELEN!")
                continue
            p += 1
            t = sum(1 for k in range(3) if cel[k] == tn[k])
            if t == 0:
                yield ctx.mond("NEM TALÁLT!")
            elif t < 3:
                yield ctx.mond(f"{t} betűt talált.")
            else:
                yield ctx.mond(f"TALÁLT! {p} TIPPEL NYERTÉL.")
                break
        v = yield ctx.kerdez("Gondoljak új szót? (igen/nem)")
        if igen(v, True):
            continue
        yield ctx.vege("Jó szórakozást volt! Viszlát!")
        return


# ================================================================== SZÓFAJOK
# Forrás: SZOFAJOK.HTP (Homelab). A gép szót mond, te felismered a SZÓFAJÁT:
# N=névelő, S=számnév, F=főnév, I=ige, M=melléknév. A forrás 60 szó-párja
# (a hiányzó SZÁMNÉV/MELLÉKNÉV meghatározás pótolva). A végén osztályzat.

_SZOFAJOK_PAROK = (
    ('FUT', 'IGE'), ('OLVAS', 'IGE'), ('TANUL', 'IGE'), ('MOZDUL', 'IGE'),
    ('HALLGAT', 'IGE'), ('PIHEN', 'IGE'), ('ÉNEKEL', 'IGE'),
    ('CSAVARODIK', 'IGE'), ('TÁNCOL', 'IGE'), ('A', 'NÉVELŐ'),
    ('KETTŐ', 'SZÁMNÉV'), ('SZOBA', 'FŐNÉV'), ('ASZTAL', 'FŐNÉV'),
    ('SZÉK', 'FŐNÉV'), ('LÁMPA', 'FŐNÉV'), ('HÁROM', 'SZÁMNÉV'),
    ('HÁZ', 'FŐNÉV'), ('EBÉD', 'FŐNÉV'), ('ISKOLA', 'FŐNÉV'),
    ('GÁBOR', 'FŐNÉV'), ('TAMÁS', 'FŐNÉV'), ('DUNA', 'FŐNÉV'),
    ('BAKONY', 'FŐNÉV'), ('ÍRÁS', 'FŐNÉV'), ('JÁTÉK', 'FŐNÉV'),
    ('ÓRA', 'FŐNÉV'), ('MAGNETOFON', 'FŐNÉV'), ('DÉLCEG', 'MELLÉKNÉV'),
    ('SÜKET', 'MELLÉKNÉV'), ('VAK', 'MELLÉKNÉV'), ('PIROS', 'MELLÉKNÉV'),
    ('ALACSONY', 'MELLÉKNÉV'), ('NAGY', 'MELLÉKNÉV'), ('ZENÉL', 'IGE'),
    ('FORDUL', 'IGE'), ('ÉL', 'IGE'), ('FEKETE', 'MELLÉKNÉV'),
    ('MORCOS', 'MELLÉKNÉV'), ('ROSSZ', 'MELLÉKNÉV'), ('SOK', 'SZÁMNÉV'),
    ('SZERÉNY', 'MELLÉKNÉV'), ('SZAPORA', 'MELLÉKNÉV'), ('MAJOM', 'FŐNÉV'),
    ('PÁVIÁN', 'FŐNÉV'), ('PINGVIN', 'FŐNÉV'), ('AZ', 'NÉVELŐ'),
    ('CSÍKOS', 'MELLÉKNÉV'), ('ZSARNOK', 'MELLÉKNÉV'), ('MÁRTI', 'FŐNÉV'),
    ('ZSOLTIKA', 'FŐNÉV'), ('ÉREM', 'FŐNÉV'), ('HASOGAT', 'IGE'),
    ('VAN', 'IGE'), ('FELEL', 'IGE'), ('KRISZTUS', 'FŐNÉV'),
    ('LENIN', 'FŐNÉV'), ('BUDAPEST', 'FŐNÉV'), ('VARANGY', 'FŐNÉV'),
    ('TOLLÁSZKODIK', 'IGE'), ('CSILLAG', 'FŐNÉV'),
)
_SZOFAJOK_DICSER = ("JÓL VÁLASZOLTÁL!", "JÓL TUDTAD!", "JÓ A VÁLASZ!",
                    "EZ A HELYES!", "ÍGY VAN!")
_SZOFAJOK_ROSSZ = ("NEM JÓ!", "TÉVEDÉS!", "NEM TALÁLT!")


def jatek_szofajok(ctx):
    yield ctx.mond("SZÓFAJOK")
    yield ctx.mond("SZAVAKAT FOGOK MONDANI.")
    yield ctx.mond("FEL KELL ISMERNED ŐKET!")
    yield ctx.mond("MINDIG KÉRDEZZ ELŐSZÖR MAGADBAN, AZUTÁN VÁLASZOLJ!")
    while True:
        while True:
            v = yield ctx.kerdez("HÁNY KÉRDÉST ADJAK?")
            db = szam(v, 1, len(_SZOFAJOK_PAROK))
            if db is not None:
                break
            yield ctx.mond(f"Egy és {len(_SZOFAJOK_PAROK)} közötti számot kérek.")

        jo = rossz = 0
        elozo = None
        for _ in range(db):
            szo, szofaj = random.choice(_SZOFAJOK_PAROK)
            while szo == elozo:
                szo, szofaj = random.choice(_SZOFAJOK_PAROK)
            elozo = szo
            yield ctx.mond("MILYEN SZÓ A KÖVETKEZŐ?")
            v = yield ctx.kerdez(f"{szo}  (N=névelő, S=számnév, F=főnév, "
                                 "I=ige, M=melléknév)")
            valasz = _szokita_norm(v)[:1]
            helyes = _szokita_norm(szofaj)[:1]
            if valasz == helyes:
                yield ctx.mond(random.choice(_SZOFAJOK_DICSER))
                jo += 1
            else:
                yield ctx.mond(random.choice(_SZOFAJOK_ROSSZ))
                yield ctx.mond(f"A HELYES VÁLASZ {szofaj} LETT VOLNA!")
                rossz += 1

        if jo == 0:
            yield ctx.mond("POCSÉK EREDMÉNY!")
            yield ctx.mond("LEGALÁBB VÉLETLENÜL ELTALÁLHATTÁL VOLNA VALAMIT!")
            yield ctx.mond("TANULJ, MERT ILYEN MARADSZ!")
        elif rossz > jo:
            yield ctx.mond("GYENGE TELJESÍTMÉNY!")
            yield ctx.mond("TÖBBET KELL FOGLALKOZNOD A NYELVTANNAL!")
            yield ctx.mond("TÖBB ROSSZ VÁLASZOD VOLT MINT JÓ.")
        elif rossz == jo:
            yield ctx.mond("ENNÉL MÉG TÖBBRE VAGY KÉPES.")
            yield ctx.mond("FELE JÓ VOLT, DE FELE ROSSZ!")
        elif rossz == 0:
            yield ctx.mond("GRATULÁLOK!")
            yield ctx.mond("KIFOGÁSTALANUL DOLGOZTÁL.")
        else:
            yield ctx.mond("BEFEJEZTED A VÁLASZOKAT.")
            yield ctx.mond(f"ROSSZ VÁLASZOD {rossz} VOLT.")
            yield ctx.mond(f"{db} VÁLASZBÓL {jo} VOLT JÓ!")

        v = yield ctx.kerdez("AKARSZ MÉGEGYSZER PRÓBÁLKOZNI? (igen/nem)")
        if igen(v, False):
            continue
        yield ctx.vege("SZERBUSZ!")
        return


# =========================================================== RÉSZEG (RESZEG)
# Forrás: RESZEG.HTP – „KÉSZ RUN TETTE: SCHUCK ANTAL", 1987. november 7–11.
# (Ugyanaz a szerző, mint a Célozz a hajórának.) Számkitaláló 0 és 20 között,
# konyakért; minden rossz tipp egy felesbe kerül. Tíz tipp után „fizetsz nekem".
# Hat kör után záróra. Felnőtt, humoros hangvétel.

def jatek_reszeg(ctx):
    v = yield ctx.kerdez("KÉRED AZ ISMERTETŐT? (igen/nem)")
    d = (v or "").strip().lower()
    if d.startswith("i"):
        yield ctx.mond("EGY SZÁMRA FOGOK GONDOLNI 0 ÉS 20 KÖZÖTT.")
        yield ctx.mond("PRÓBÁLD MEG KITALÁLNI. FÉL LITER KONYAK A JUTALMAD, HA "
                       "SIKERÜL.")
        yield ctx.mond("VISZONT MINDEN ROSSZ TIPP UTÁN LEVONOK EGY FELEST.")
        yield ctx.mond("AZT HISZEM, TISZTESSÉGES AZ AJÁNLATOM.")
        yield ctx.mond("KEZDJÜK!")
    elif not d.startswith("n"):
        yield ctx.mond("MÉG NEM IS ITTÁL, DE MÁR NEM TUDSZ VISELKEDNI!")

    kor = 0
    while True:
        kor += 1
        if kor == 7:
            yield ctx.mond("SAJNÁLOM, DE ZÁRÓRA VAN, ÉS NINCS TÖBB KONYAKOM.")
            yield ctx.vege("KÜLÖNBEN IS RÉSZEG DISZNÓKAT NEM ITATOK!")
            return
        a = random.randint(1, 20)
        yield ctx.mond("GONDOLTAM 1 SZÁMOT 0 ÉS 20 KÖZÖTT. TIPPELHETSZ.")
        d = 0                    # tippek száma
        rossz = 0                # rossz tippek (a jutalomból levonva)
        tul = 0                  # a „fizetsz nekem" mód tippjei (10 tipp után)
        while True:
            v = yield ctx.kerdez("A tipped (0–20):")
            b = szam(v)
            if b is None:
                yield ctx.mond("Számot kérek.")
                continue
            d += 1
            if d > 10:           # tíz tipp után: már te fizetsz
                if a == b:
                    yield ctx.mond("HUK! GRATULÁLOK, ELTALÁLTAD. HAVER, "
                                   f"FIZETHETSZ NEKEM {tul} FELEST.")
                    break
                tul += 1
                yield ctx.mond("TÚL NAGY." if a < b else "TÚL KICSI.")
                yield ctx.mond("EGY FELESEDNEK LŐTTEK.")
                continue
            if a == b:
                yield ctx.mond(f"GRATULÁLOK, NYERTÉL {10 - rossz} FELEST! "
                               "EGÉSZSÉGEDRE!")
                break
            rossz += 1
            yield ctx.mond("TÚL NAGY." if a < b else "TÚL KICSI.")
            yield ctx.mond("EGY FELESEDNEK LŐTTEK.")

        v = yield ctx.kerdez("AKARSZ-E MÉG INNI? (igen/nem)")
        if (v or "").strip().lower().startswith("i"):
            continue
        yield ctx.mond("MARS KI!")
        yield ctx.vege("HA TEJET INNÁL, AZ IS POCSÉKBA MENNE!")
        return


# ================================================================= BETŰPÖKER
# Forrás: BETPOKER.HTP (Homelab). Szó-mastermind PONTOZÁSSAL: a gép egy szóra
# gondol (257 szavas lista, 3–10 betű), megmondja a hosszát; te azonos hosszú
# szavakat tippelsz, és megmondja, hány betű van a helyén. 200 pont az előleg,
# a rossz tippekért von; a megismételt rossz tipp külön −10. * = feladás,
# ** = pontállás. Ékezet-érzéketlen összevetés (mint a SZOKITA).

_BETPOKER_SZAVAK = (
    "HÁZ ÁGY PAD TÉL KÁD MÉZ ÁSÓ RÉZ NAP ÓRA VAJ CÉL BOR VAD KÉP ODU JÉG SIP "
    "SÜT SÜN HAL HID FIU DIÓ VIZ MOS DOB ZÁR VÉR SEB AJTÓ ALMA AVAR ARAT ADAT "
    "AKTA BABA CICA CSÓK CSAP DARU DOMB EGÉR EBÉD ESTE ESIK ÉDES ÉRIK ÉTEL FALU "
    "FÖLD FÉSÜ ERDÖ GYOM GYIK GOMB HAJÓ IRÁS ITAL LIBA LÁNY MOZI AUTÓ NÉNI NYÁR "
    "NYUL OBOA ORSÓ ÖREG PART PARK POLC PULT RÉPA RUCA RIGÓ RIAD RÁCS SAJT SIET "
    "SZÉK SZIV SZÓL TEST TURÓ TYUK UTCA UGAT ÜRES ÜVEG ÜRGE VÁZA VERS PIAC ZENE "
    "ZSIR ZSEB ZSÁK ZORD ABLAK ALKOT ÁLLAT ÁRVIZ ÁRKÁD ÁRULÓ BANÁN BALTA BOLHA "
    "BIRKA BUTIK BUTOR BUNDA BÖGRE BÜNÖS BORSÓ BETEG BORDÓ CÉLOZ CUKOR CÉKLA "
    "CÉRNA CSONT CSUCS DARÁL DIVAT DOBOZ DÁTUM EZÜST EVEZÖ ESZIK ISZIK EPEKÖ "
    "ERNYÖ ÉRTÉK ÉRZÉS FEHÉR FORRÓ FORMA FESTÖ GITÁR GALLY GÖDÖR GYALU GYORS "
    "HORDÓ HURKA IRODA IRIGY JÁTÉK JÁRDA JÁRMÜ KULCS KERES KÖRTE KALAP KOCSI "
    "LÁMPA PIÓCA SAS PATIKA CSÓNAK CSENGÖ TAPÉTA PILLANAT SZEDER TEJFÖL RÓKA "
    "TRÉFA SÜSÜ SÖR KUTYA KACSA LABDA LIGET MACKÓ MALAC MÉTER MOSODA ORVOS OKTAT "
    "ÖNTÖZ PAPIR POSTA PEREC SÁTOR SZÖLÖ SZITA TEHÉN TÖRPE TORTA VERÉB VONAT "
    "ÜZLET ALTATÓ ASZTAL ÁRUHÁZ CSOMAG CSAVAR CSALÁD DOMINÓ ELEDEL FEKETE GALAMB "
    "GYEREK HIRDET KAGYLÓ FARKAS SZIGET SZÖVET SZILVA POKRÓC MACSKA HEGEDÜ "
    "ZONGORA FURULYA KENGURU SZUNYOG HATALOM MONDÓKA PAPRIKA MOZDONY HÜTÖGÉP "
    "VILLAMOS MANDARIN SZEKRÉNY RADIÁTOR MEGÉRTÉS TÜRELEM UDVARIAS SZÖRP "
    "OROSZLÁN BÜNTETÉS KORCSOLYA BOLDOGSÁG BILLENTYÜ SZÁGULDÁS SZIMFÓNIA "
    "TÖRTÉNELEM PATAK FORDULÓ BIRODALOM IGAZSÁGOS KARÁCSONY BABLEVES TAKARMÁNY "
    "MIKULÁS MARADÉK PADLÁS PINCE GYÜMÖLCS FÉK"
).split()


def jatek_betpoker(ctx):
    yield ctx.mond("BETŰPÖKER.")
    v = yield ctx.kerdez("Ismertessem a játékszabályokat? (i/n)")
    if igen(v, False):
        yield ctx.mond("Egy szót kell kitalálnod.")
        yield ctx.mond("A játékhoz kapsz előlegbe 200 pontot.")
        yield ctx.mond("Ebből vonok le a rossz tippekért!")
        yield ctx.mond("Ha kétszer egyformán tippelsz rosszul, többet vonok le!")
        yield ctx.mond("Segítségül a szó hosszát és az azonos helyen lévő betűk "
                       "számát közlöm.")
        yield ctx.mond("Ha feladod, akkor írj egy csillagot: *")
        yield ctx.mond("Ha kíváncsi vagy, hány pontod van még, írj két "
                       "csillagot: ** – ezt nem számolom tippnek!")

    while True:
        szo = random.choice(_BETPOKER_SZAVAK)
        cel = _szokita_norm(szo)
        hossz = len(cel)
        tipp_db = 0
        buntetes = 0
        eddigi = []
        yield ctx.mond(f"A szó hossza {hossz} betű.")
        while True:
            v = yield ctx.kerdez("Kérem a szót! (* = feladás, ** = pontállás)")
            f = (v or "").strip()
            pont = 200 - (10 - hossz) * tipp_db - buntetes
            if f == "**":
                yield ctx.mond(f"{pont} pontod van.")
                continue
            tipp_db += 1
            if f == "*":
                yield ctx.mond(f"A szó {szo}. {tipp_db} tipped volt!")
                break
            pont = 200 - (10 - hossz) * tipp_db - buntetes
            if pont < 0:
                yield ctx.mond("Elfogytak a pontjaid.")
                yield ctx.mond(f"A szó {szo}. Eddig {tipp_db} tipped volt!")
                break
            tn = _szokita_norm(f)
            if len(tn) < hossz:
                yield ctx.mond("Kevesebb betűt adtál meg!")
                continue
            if len(tn) > hossz:
                yield ctx.mond("Több betűt adtál meg!")
                continue
            if tn in eddigi:
                yield ctx.mond("Ilyen tipped már volt! Figyelj jobban! Ezért "
                               "büntetésből levonok tíz pontot!")
                buntetes += 10
            else:
                eddigi.append(tn)
            talalat = sum(1 for k in range(hossz) if cel[k] == tn[k])
            yield ctx.mond(f"{talalat} betű van a helyén.")
            if talalat == hossz:
                pont = 200 - (10 - hossz) * tipp_db - buntetes
                yield ctx.mond(f"Eltaláltad {tipp_db} tippből. {pont} pontot "
                               "szereztél.")
                if pont > 150:
                    yield ctx.mond("Rendkívül ügyesen játszottál! Remélem, hogy "
                                   "nem csak szerencséd volt.")
                elif pont > 100:
                    yield ctx.mond("Ügyes voltál!")
                elif pont >= 50:
                    yield ctx.mond("Szépen játszottál.")
                else:
                    yield ctx.mond("Megkínlódtál érte, de azért sikerült "
                                   "kitalálnod!")
                break
        v = yield ctx.kerdez("Játszunk még? (i/n)")
        if igen(v, False):
            continue
        yield ctx.vege("Remélem, nemsokára találkozunk! Köszönöm a játékot!")
        return
