# -*- coding: utf-8 -*-
"""Aldi – az Aldi saját lapozós újságja (szorolap.aldi.hu, Publitas).

A lapozó minden oldalhoz kiadja a nyomdai SZÖVEGRÉTEGET is
(`<újság>/spreads.json` → pages[].text). Ez nem kép és nem AI: ugyanaz a
szöveg, ami az újságban le van nyomtatva.

⚠️ A szöveg sorrendje a nyomdai elrendezést követi, ezért az ár („769 /kg”,
„Ft”) gyakran NEM a név mellett áll. Ami viszont mindig egyben van, az a
termék blokkja: név, kiszerelés, EGYSÉGÁR és cikkszám:

    VAJAS RÚD
    150 g/csomag
    3 660 Ft/kg
    156305

Az árat ebből SZÁMOLJUK: 0,150 kg × 3 660 Ft/kg = 549 Ft – ami pontosan a
kiírt ár (2026-09-25-én mérve a teljes újságon). A kiírt egységár a bolt
hivatalos adata, a szorzás csak visszafejti belőle a darabárat.
"""
import datetime as _dt
import json
import re

from .termek import Termek, ar_szam

BOLT = "Aldi"
ALAP = "https://szorolap.aldi.hu"

_KOD = re.compile(r"^\d{6}$")
_EGYSEGAR = re.compile(
    r"^([\d  .,]+?)(?:\s*/\s*[\d  .,]+)?\s*Ft\s*/\s*(kg|l|db|darab|m|m2|tekercs|mosás|pár)\b",
    re.I)
_MERET = re.compile(r"(\d+(?:[,.]\d+)?)\s*(?:x\s*(\d+(?:[,.]\d+)?)\s*)?(kg|g|dkg|ml|cl|l|db)\b",
                    re.I)
_SZEMET = re.compile(
    r"(^a kép illusztráció|dekoráció|kiegészítők|^szuper$|csak ennyi|"
    r"^többféle$|^\*|lásd a hátoldalon|árkedvezmény|érvényben volt|"
    r"állandó kínálatunk|mostantól még több|^ft$|^vegán$|ai által készült|"
    r"^\d{2}\.\s*\d{2}\.|csütörtök|szerdáig|készlet erejéig)",
    re.I)


def ujsag_nevek(ma: _dt.date | None = None) -> list:
    """A lehetséges újságnevek: az idei és a jövő heti élelmiszer-újság,
    meg a „középső sor” (nonfood). A Publitas-címek hét szerint épülnek."""
    ma = ma or _dt.date.today()
    ki = []
    for eltolas in (0, 1, -1):
        d = ma + _dt.timedelta(weeks=eltolas)
        ev, het, _ = d.isocalendar()
        for fajta in ("aldi_online_akcios_ujsag", "aldi_kozepso_sor"):
            ki.append(("%s_%d_kw%02d" % (fajta, ev, het), fajta, het))
    return ki


def _szam(s: str) -> float | None:
    s = (s or "").replace("\xa0", " ").replace(" ", " ").strip()
    s = s.replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def szamolt_ar(meret: str, egysegar: str) -> int | None:
    """„150 g/csomag” + „3 660 Ft/kg” → 549. Ha nem egyértelmű: None."""
    e = _EGYSEGAR.match((egysegar or "").strip())
    if not e:
        return None
    egys = _szam(e.group(1))
    alap = e.group(2).lower()
    if egys is None:
        return None
    if alap in ("db", "darab", "tekercs", "pár", "mosás", "m"):
        # „6 darab” + „58,17 Ft/db” → 349; „10 tekercs” + „102,90 Ft/tekercs”
        m = re.search(r"(\d+)\s*(?:x\s*\d+\s*\w+\s*)?(darab|db|tekercs|pár|"
                      r"mosás|m)\b", meret or "", re.I)
        darab = int(m.group(1)) if m else 1
        ar = darab * egys
        return int(round(ar)) if 0 < ar < 1_000_000 else None
    m = _MERET.search(meret or "")
    if not m:
        return None
    menny = _szam(m.group(1))
    szorzo = _szam(m.group(2)) if m.group(2) else None
    egyseg = m.group(3).lower()
    if menny is None:
        return None
    if szorzo:                       # „4 x 125 g”
        menny = menny * szorzo
    valto = {"g": 0.001, "dkg": 0.01, "kg": 1, "ml": 0.001, "cl": 0.01,
             "l": 1}.get(egyseg)
    if valto is None or (alap == "kg" and egyseg in ("ml", "cl", "l")) or \
            (alap == "l" and egyseg in ("g", "dkg", "kg")):
        return None
    ar = menny * valto * egys
    return int(round(ar)) if 0 < ar < 1_000_000 else None


def _szep(s: str) -> str:
    s = re.sub(r"\s+", " ", s.replace("*", "")).strip()
    return " ".join(w.capitalize() if len(w) >= 2 and w.isupper() else w
                    for w in s.split())


def termekek(oldalak: list, ujsag: str = "", ervenyes: str = "") -> list:
    """`oldalak`: az oldalak szövegei sorrendben."""
    ki = []
    for szoveg in oldalak:
        bekezdesek = [b for b in re.split(r"\n\s*\n", szoveg or "") if b.strip()]
        elozo = ""
        for b in bekezdesek:
            sorok = [s.strip() for s in b.split("\n") if s.strip()]
            if not (len(sorok) >= 3 and _KOD.match(sorok[-1])):
                if len(sorok) == 1 and sorok[0].isupper() and len(sorok[0]) < 30 \
                        and not _SZEMET.search(sorok[0]):
                    elozo = sorok[0]        # a márka gyakran külön blokk
                continue
            egysegar_i = next((i for i, s in enumerate(sorok)
                               if _EGYSEGAR.match(s)), None)
            if egysegar_i is None:
                continue
            egysegar = sorok[egysegar_i]
            meret_i = next((i for i in range(egysegar_i - 1, -1, -1)
                            if _MERET.search(sorok[i]) or "/" in sorok[i]),
                           None)
            meret = sorok[meret_i] if meret_i is not None else ""
            vege = meret_i if meret_i is not None else egysegar_i
            nevek = [s for s in sorok[:vege] if not _SZEMET.search(s)]
            if not nevek:
                continue
            nagy = [s for s in nevek if s.isupper() or s.endswith("*")]
            kicsi = [s for s in nevek if s not in nagy]
            nev = _szep(" ".join(nagy or nevek[:1]))
            if elozo and elozo.lower() not in nev.lower():
                nev = _szep(elozo) + " " + nev
            t = Termek(bolt=BOLT, nev=nev, kod=sorok[-1],
                       kiszereles=re.sub(r"/.*$", "", meret).strip() or meret,
                       egysegar=egysegar.replace("  ", " "),
                       ervenyes=ervenyes, kategoria=ujsag,
                       megjegyzes=", ".join(kicsi))
            t.ar = szamolt_ar(meret, egysegar)
            if t.ar is None and "/db" in egysegar.replace(" ", "").lower():
                t.ar = ar_szam(egysegar)
            ki.append(t)
            elozo = ""
    return ki


def _ervenyes(oldalak: list) -> str:
    for sz in oldalak[:3]:
        m = re.search(r"(\d{2})\.(\d{2})\.\s*C\s*S\s*Ü", sz or "")
        if m:
            return "%s.%s-tól" % m.groups()
        m = re.search(r"(\d{2})\.(\d{2})\.\s*[-–]\s*(\d{2})\.(\d{2})\.", sz or "")
        if m:
            return "%s.%s-tól %s.%s-ig" % m.groups()
    return ""


def letolt(get_bytes, jelez=lambda s: None, ma=None) -> list:
    ki, latott, fajtak = [], set(), set()
    for nev, fajta, het in ujsag_nevek(ma):
        if fajta in fajtak:
            continue                # fajtánként a legfrissebb egy elég
        try:
            adat = get_bytes("%s/%s/spreads.json" % (ALAP, nev))
        except Exception:
            continue
        fajtak.add(fajta)
        cim = ("Akciós újság, %d. hét" if "akcios" in fajta
               else "Középső sor (nem élelmiszer), %d. hét") % het
        jelez("Aldi: %s…" % cim)
        oldalak = [pg.get("text") or ""
                   for sp in json.loads(adat.decode("utf-8"))
                   for pg in sp.get("pages", [])]
        erv = _ervenyes(oldalak)
        for t in termekek(oldalak, cim, erv):
            if t.kod in latott:
                continue
            latott.add(t.kod)
            ki.append(t)
    return ki
