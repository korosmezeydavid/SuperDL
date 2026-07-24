# -*- coding: utf-8 -*-
"""HITELES portok a hivatalos Homelab/Brailab gyűjteményből
(`Documents\\játékok\\szabalyok\\*.md` + detokenizált BASIC).

ELV: a szabályokat, üzeneteket és állandókat A FORRÁS SZERINT követjük – nem
a miénk, nincs jogunk megváltoztatni. Minden játék a saját, EREDETI szerzőjét
kapja a szerző-megjelölésben. A BR4.ROM-hoz nem nyúlunk, gépi kódot nem
másolunk; a VISELKEDÉST írjuk újra."""
import random

from ._util import igen


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
