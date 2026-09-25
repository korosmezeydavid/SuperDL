# -*- coding: utf-8 -*-
"""Tesco – a tesco.hu akciós újságjai (a bolt saját PDF-jei).

A tesco.hu/akciok/akcios-termekek/ oldal (Next.js) a lapjában felsorolja az
aktuális újságokat (hipermarket, szupermarket), mindegyikhez a PDF címét
(`leafletUrl`) és az érvényességet. A PDF-nek valódi szövegrétege van.

Egy termék a szövegben egy bekezdés (2026-09-25-i mérés):

    Tesco csont nélküli,
    szeletelt sertéstarja
    400 g, 2 933 Ft/1 kg      ← kiszerelés + a RENDES egységár
    2498 Ft/1 kg              ← az AKCIÓS egységár

    Kinder tejszelet multipack
    5x28 g/cs
    6421 Ft/1 kg
    Clubcarddal: 6064 Ft/1 kg ← Clubcard-os egységár

A darabárat – az Aldihoz hasonlóan – a kiírt egységárból számoljuk:
0,4 kg × 2498 Ft/kg = 999 Ft, ami pontosan a nyomtatott ár. Ahol a bekezdés
kiírja az árat is („380 g, 2049 Ft, 5392 Ft/1 kg”), azt vesszük.
"""
import io
import json
import re

from .aldi import szamolt_ar
from .termek import Termek

BOLT = "Tesco"
OLDAL = "https://tesco.hu/akciok/akcios-termekek/"
_TIPUS = {"HM": "Hipermarket", "SM": "Szupermarket", "EX": "Expressz"}

_EGYS = re.compile(r"(\d[\d  ]*(?:[,.]\d+)?)\s*Ft/1\s*(kg|l|db|m|pár)\b", re.I)
_EGYS_SOR = re.compile(r"^(clubcarddal:\s*)?(\d[\d  ]*(?:[,.]\d+)?)\s*Ft/1\s*"
                       r"(kg|l|db|m|pár)\s*$", re.I)
_MERET = re.compile(r"\d+(?:[,.]\d+)?\s*(?:x\s*\d+(?:[,.]\d+)?\s*)?(?:g|kg|ml|l|cl|db)\b",
                    re.I)
_SZEMET = re.compile(r"(a termék a következő|áruházainkban|nem kapható|^vidék:|"
                     r"^budapest:|kapható\.?$|^\d+$|^%$|^–|^-\s*\d|clubcard|"
                     r"visszaváltási díj|^ft\b)", re.I)


def _ligatura(s: str) -> str:
    """A PDF az „fi”/„fl” ligatúrát szóközzel adja: „fi nest”, „mellfi lé”."""
    return re.sub(r"(f[il]) (?=[a-záéíóöőúüű])", r"\1", s)


def ujsagok(oldal_html: str) -> list:
    """[(cím, pdf, kezdet, vég)] a tesco.hu akciós oldalából."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                  oldal_html, re.S)
    if not m:
        return []
    allapot = json.loads(m.group(1)).get("props", {}).get("pageProps", {}) \
        .get("__APOLLO_STATE__", {})
    ki = []
    for k, v in allapot.items():
        if k.startswith("Leaflet") and v.get("leafletUrl"):
            ki.append(("%s újság" % _TIPUS.get(v.get("type"), v.get("type") or ""),
                       v["leafletUrl"], (v.get("validFrom") or "")[:10],
                       (v.get("validTo") or "")[:10]))
    return ki


def _szam(s: str) -> float | None:
    try:
        return float(s.replace(" ", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def termekek(szoveg: str, ujsag: str = "", ervenyes: str = "") -> list:
    ki = []
    for b in re.split(r"\n\s*\n", _ligatura(szoveg or "")):
        sorok = [s.strip() for s in b.split("\n") if s.strip()]
        if not any(_EGYS.search(s) for s in sorok):
            continue
        # több termék egy bekezdésben: „…, 2049 Ft, 5392 Ft/1 kg” alak
        explicit = [i for i, s in enumerate(sorok)
                    if re.search(r"\d\s*Ft,\s*\d[\d ]*\s*Ft/1", s)]
        if explicit:
            eleje = 0
            for i in explicit:
                nev = " ".join(x for x in sorok[eleje:i] if not _SZEMET.search(x))
                m = re.search(r"^(.*?),?\s*(\d[\d ]*)\s*Ft,\s*(.+Ft/1\s*\w+)", sorok[i])
                if nev and m and not re.search(r"\bFt\b", nev):
                    t = Termek(bolt=BOLT, nev=nev.strip(" ,"),
                               kiszereles=m.group(1).strip(" ,"),
                               egysegar=m.group(3).strip(), ervenyes=ervenyes,
                               kategoria=ujsag)
                    t.ar = int(_szam(m.group(2)) or 0) or None
                    ki.append(t)
                eleje = i + 1
            continue
        nevsorok, meret, egysegek, club = [], "", [], None
        for s in sorok:
            e = _EGYS_SOR.match(s)
            if e:
                ertek = _szam(e.group(2))
                if e.group(1):
                    club = (ertek, e.group(3))
                else:
                    egysegek.append((ertek, e.group(3)))
                continue
            if s.lower().startswith("clubcarddal"):
                continue
            # „400 g, 2 933 Ft/1 kg” – kiszerelés és egységár egy sorban
            e = _EGYS.search(s)
            if e and _MERET.search(s[:e.start()]):
                meret = meret or s[:e.start()].strip(" ,")
                egysegek.append((_szam(e.group(1)), e.group(2)))
                continue
            if not meret and _MERET.search(s) and nevsorok:
                meret = s.strip(" ,")
                continue
            if not _SZEMET.search(s) and not egysegek:
                nevsorok.append(s)
        if not nevsorok or not (egysegek or club):
            continue
        # club-számjegyek egy külön sorban is jöhetnek („Clubcarddal:” + „2396 Ft/1 kg”)
        if "clubcarddal:" in b.lower() and club is None and len(egysegek) >= 2:
            club = egysegek.pop()
        nev = re.sub(r"\s+", " ", " ".join(nevsorok)).strip(" ,*")
        # „2026. 09. 02 – 09. 29. Head&Shoulders sampon” – az eltérő érvényesség
        # a név elején: átkerül az érvényességbe
        m = re.match(r"^(\d{4}\.\s*\d{2}\.\s*\d{2})\s*[–-]\s*(\d{2}\.\s*\d{2}\.?)\s*(.*)$",
                     nev)
        sajat_erv = ""
        if m:
            sajat_erv = "%s–%s" % (m.group(1), m.group(2))
            nev = m.group(3)
        if not nev or re.search(r"\bFt\b", nev):
            continue        # két termék összecsúszott – inkább kihagyjuk
        # ha a kiszerelés tömeg/űrtartalom, az ahhoz illő egységárat vesszük
        # (a „12x100 g/cs” mellett ott állhat „167 Ft/1 db” is)
        meret_egyseg = (re.search(r"(kg|g|ml|cl|l|db)\b", _meret_resz(meret) or "",
                                  re.I) or [None, ""])[1].lower()
        csoport = {"g": "kg", "kg": "kg", "ml": "l", "cl": "l", "l": "l",
                   "db": "db"}.get(meret_egyseg)
        if csoport and len({e[1].lower() for e in egysegek}) > 1:
            egysegek = [e for e in egysegek if e[1].lower() == csoport] or egysegek
        alap = (egysegek[-1] if egysegek else club)[1].lower()
        mertek = "1 %s" % alap
        t = Termek(bolt=BOLT, nev=nev, kiszereles=_meret_resz(meret),
                   ervenyes=sajat_erv or ervenyes, kategoria=ujsag)
        uj = egysegek[-1][0] if egysegek else None
        regi = egysegek[0][0] if len(egysegek) >= 2 else None
        t.egysegar = "%s = %s Ft" % (mertek, _ft(uj if uj is not None else club[0]))
        if _MERET.search(meret or ""):
            t.ar = _darabar(meret, uj, alap)
            t.regi_ar = _darabar(meret, regi, alap) if regi and regi > (uj or 0) else None
            if club:
                t.kartyas_ar = _darabar(meret, club[0], alap)
        else:                                   # pultos, kilós áru: az ár /kg
            t.ar = int(round(uj)) if uj else None
            t.regi_ar = int(round(regi)) if regi and uj and regi > uj else None
            if club:
                t.kartyas_ar = int(round(club[0]))
            t.kiszereles = "kilónként" if alap == "kg" else "1 " + alap
        if t.kartyas_ar is not None:
            t.kartya_nev = "Clubcarddal"
        # ⚠️ Sok darabos csomagnál a kerekített egységár × darabszám pár
        # forinttal eltérhet a nyomtatott ártól – ezt kimondjuk, nem titkoljuk.
        db = re.search(r"(\d+)\s*(?:x\s*(\d+)\s*)?db", t.kiszereles or "")
        if db and int(db.group(1)) * int(db.group(2) or 1) >= 20:
            t.megjegyzes = ", ".join(x for x in (
                t.megjegyzes, "az ár az egységárból számolva, pár forint "
                              "eltérés lehet") if x)
        if t.ar is None and t.kartyas_ar is not None:
            t.ar, t.kartyas_ar = t.kartyas_ar, None
            t.kartya_nev = ""
            t.megjegyzes = "Csak Clubcarddal"
        if t.regi_ar and t.ar:
            t.kedvezmeny = "-%d%%" % round((1 - t.ar / t.regi_ar) * 100)
        if t.ar is not None:
            ki.append(t)
    return ki


def _meret_resz(meret: str) -> str:
    """„többféle, 6x51 g/cs” → „6x51 g/cs”; „zsírtartalom < 20%, 500 g” → „500 g”."""
    m = _MERET.search(meret or "")
    if not m:
        return meret
    return (meret[m.start():]).strip(" ,")


def _ft(x) -> str:
    return ("%d" % round(x)) if x is not None else "?"


def _darabar(meret: str, egysegar, alap: str):
    if egysegar is None:
        return None
    return szamolt_ar(_meret_resz(meret), "%s Ft/%s" % (_ft(egysegar), alap))


def letolt(get, get_bytes, jelez=lambda s: None) -> list:
    from pdfminer.high_level import extract_text
    ki, latott = [], set()
    for cim, pdf_url, kezd, veg in ujsagok(get(OLDAL)):
        jelez("Tesco: %s letöltése…" % cim)
        pdf = get_bytes(pdf_url)
        jelez("Tesco: %s olvasása…" % cim)
        erv = "%s-tól %s-ig" % (kezd[5:].replace("-", "."), veg[5:].replace("-", "."))
        for t in termekek(extract_text(io.BytesIO(pdf)), cim, erv):
            k = t.nev.lower()
            if k in latott:
                continue
            latott.add(k)
            ki.append(t)
    return ki
