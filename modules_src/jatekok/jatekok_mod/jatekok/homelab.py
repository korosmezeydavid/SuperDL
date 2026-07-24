# -*- coding: utf-8 -*-
"""HITELES portok a hivatalos Homelab/Brailab gyűjteményből
(`Documents\\játékok\\szabalyok\\*.md` + detokenizált BASIC).

ELV: a szabályokat, üzeneteket és állandókat A FORRÁS SZERINT követjük – nem
a miénk, nincs jogunk megváltoztatni. Minden játék a saját, EREDETI szerzőjét
kapja a szerző-megjelölésben. A BR4.ROM-hoz nem nyúlunk, gépi kódot nem
másolunk; a VISELKEDÉST írjuk újra."""
import random

from ._util import igen, szam


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
