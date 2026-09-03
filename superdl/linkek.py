# -*- coding: utf-8 -*-
"""KÖZÖS LINK-FELISMERŐ (letöltő-motor MK7).

**Miért kellett.** A programba HÁROM úton kerülhet be egy link — a
vágólap-figyelőn, a fogd-és-viddel, és az URL-mezőn keresztül —, és mindhárom
MÁSHOGY döntötte el, mi számít linknek:

- a vágólap-figyelő csak `http`/`https`/`magnet`-et fogadott, és a többsoros
  szöveget egy külön feltétellel (`"\\n" not in text`) SZÁNDÉKOSAN eldobta;
- a fogd-és-vidd ugyanezt a hármat fogadta, DE soronként, tehát több linket is;
- az `_on_add` ezeken felül a `.torrent` fájlútvonalat is elfogadta.

Vagyis ugyanaz a program ugyanarra a szövegre háromféle választ adott. Ez a
modul az egyetlen közös válasz.

SZÁNDÉKOSAN nem tud a wx-ről és a letöltéskezelőről: szövegből listát csinál,
tehát felület és hálózat nélkül tesztelhető.
"""
from __future__ import annotations

import re
from pathlib import Path

# A felismert alakok. A `magnet:` NEM URL-séma a szokásos értelemben (nincs
# `//`), ezért külön kell kezelni – ez a leggyakoribb elrontás.
_SEMA = ("http://", "https://", "magnet:")

# A szövegből linkeket vágó minta. Whitespace mentén darabol, de a záró
# írásjeleket levágja: ha valaki egy mondat végéről másol linket, a pont vagy
# a zárójel ne kerüljön bele.
_ZARO_IRASJEL = ".,;:!?\"')]}>" + "”«…"


def tisztit(darab: str) -> str:
    """Egy szódarabról levágja a körülölelő írásjeleket.

    Ha a felhasználó egy mondat végéről másol („…nézd meg itt: https://a.hu/x."),
    a záró pont a linkbe ragadna, és a letöltés 404-re futna – a felhasználó
    pedig nem értené, hiszen a böngészőben működik."""
    d = (darab or "").strip()
    # A SORREND SZÁMÍT: előbb a NYITÓ jeleket vágjuk le, és csak utána
    # döntünk a záró zárójelről. Fordítva a „(https://a.hu/x)" alakban a
    # záró zárójel párosnak látszana (egy nyitó, egy záró), és bent ragadna —
    # a link pedig 404-re futna.
    while d and d[0] in "\"'([{<„»":
        d = d[1:]
    while d and d[-1] in _ZARO_IRASJEL:
        # a záró zárójelet CSAK akkor tartjuk meg, ha van hozzá NYITÓ pár a
        # linken belül: a Wikipédia-linkekben valódi zárójel van (…_(film))
        if d[-1] == ")" and d.count("(") >= d.count(")"):
            break
        d = d[:-1]
    return d


def link_e(darab: str) -> bool:
    """Link-e ez a szódarab? http/https, magnet, vagy `.torrent` fájlútvonal."""
    d = (darab or "").strip()
    if not d:
        return False
    also = d.lower()
    if also.startswith(_SEMA):
        return True
    # `.torrent` fájlútvonal: a kiterjesztés önmagában nem elég, mert egy
    # ELÍRT név is így végződhet – a fájlnak LÉTEZNIE kell
    if also.endswith(".torrent"):
        try:
            return Path(d).is_file()
        except (OSError, ValueError):
            return False
    return False


def kigyujt(szoveg: str) -> list[str]:
    """Egy tetszőleges szövegből kigyűjti a linkeket, SORRENDBEN, egyszer.

    Nem csak soronként darabol: egy sorban több link is lehet (egy chat-üzenet
    vagy egy e-mail bekezdés bőven adhat kettőt). A duplikátumot kiszűrjük, de
    a SORRENDET megtartjuk – vakon a lista sorrendje az egyetlen fogódzó, és a
    felhasználó abban a sorrendben várja őket, ahogy másolta.

    Egy `.torrent` fájl útvonalában lehet SZÓKÖZ, ezért a szóköz menti darabolás
    azt szétvágná. Ezért a teljes sort is megvizsgáljuk: ha az EGÉSZ sor egy
    létező .torrent fájl, akkor az a link, és a darabolást elhagyjuk."""
    talalt: list[str] = []
    latott: set[str] = set()

    def hozzaad(jelolt: str) -> None:
        j = tisztit(jelolt)
        if not link_e(j):
            return
        kulcs = j.lower()
        if kulcs in latott:
            return
        latott.add(kulcs)
        talalt.append(j)

    for sor in (szoveg or "").splitlines():
        egesz = sor.strip().strip('"')
        if egesz.lower().endswith(".torrent"):
            # szóközös fájlútvonal: az egész sor egyben
            hozzaad(egesz)
            if egesz.lower() in latott:
                continue
        for darab in re.split(r"\s+", sor):
            hozzaad(darab)
    return talalt


def ujak(linkek, mar_a_sorban) -> list[str]:
    """Azok a linkek, amik MÉG NINCSENEK a sorban.

    Enélkül egy vágólap-másolás újra meg újra felvenné ugyanazt: a figyelő
    másodpercenként néz rá a vágólapra, és a felhasználó nem törli ki onnan a
    linket csak azért, mert egyszer már letöltötte."""
    meglevo = {str(u).strip().lower() for u in (mar_a_sorban or [])}
    return [x for x in linkek if x.strip().lower() not in meglevo]


# Ennyi linktől kérdezünk. EGY link marad néma: ott a kérdés csak bosszantana,
# és ez a mai, megszokott viselkedés – nem vesszük el a felhasználótól.
KERDES_KUSZOB = 2


def kerdezzunk(db: int) -> bool:
    return db >= KERDES_KUSZOB


def kerdes_szoveg(linkek, honnan: str = "a vágólapon") -> str:
    """A kérdés, ami egynél több link esetén elhangzik.

    **Ez a kérdés a feltétele annak, hogy a többsoros bevitelt egyáltalán
    bevezethessük.** Eddig a vágólap-figyelő NÉMÁN adott hozzá – ami egyetlen
    linknél elmegy, de egy harminc soros másolásnál némán harminc letöltést
    indítana. Vakon ez ijesztő, és nehéz visszacsinálni.

    A mondat kimondja a DARABSZÁMOT (ez a legfontosabb: ebből tudja, mekkora
    dologba megy bele) és az ELSŐ nevét, hogy legyen fogódzó arról, miről van
    szó egyáltalán."""
    db = len(linkek)
    elso = (linkek[0] if linkek else "").strip()
    if len(elso) > 70:
        elso = elso[:67] + "…"
    return (f"{db} hivatkozást találtam {honnan}. Hozzáadjam mind a "
            f"{db}-t a letöltési sorhoz?\n\nAz első: {elso}")


def letoltendo(argv) -> str:
    """A parancssorból érkező LETÖLTENDŐ hivatkozás – vagy üres szöveg (MK7).

    Akkor kap ilyet a program, ha a Windows társításon át indul: egy
    `.torrent` fájlra kattintva, vagy egy `magnet:` linkre a böngészőben.

    ⚠️ **Enélkül a társítás fél javítás volna, ami ráadásul ROSSZUL viselkedne.**
    A program eddig `os.path.isfile()` szűrővel kereste az argumentumot:

    - a `magnet:` link ezen fennakadt (nem fájl), tehát **némán elveszett** —
      a felhasználó kattint, elindul a program, és nem történik semmi;
    - a `.torrent` fájl VISZONT fájl, tehát átment a szűrőn, és a program
      **médiafájlként** próbálta volna megnyitni (zenelejátszó/felolvasó).

    A kapcsolóval kezdődő argumentumokat kihagyjuk (`--wh`, `--assoc-on`…)."""
    for a in list(argv or [])[1:]:
        d = str(a).strip()
        if not d or d.startswith("-"):
            continue
        if d.lower().startswith("magnet:"):
            return d
        if d.lower().endswith(".torrent"):
            try:
                if Path(d).is_file():
                    return d
            except (OSError, ValueError):
                continue
    return ""
