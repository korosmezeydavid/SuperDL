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


_PULT = re.compile(r"^(?:csont nélkül,\s*)?(hús|csemege)pultban kapható\s*$", re.I)
_KILOS_AR = re.compile(r"^(\d[\d  ]*)\s*Ft/kg\s*$", re.I)
_CSAK_SZAM = re.compile(r"^(\d[\d  ]*)\s*$")
_EGYSEG_BLOKK = re.compile(r"^Ft(?:/kg|/10 dkg)?\s*$", re.I)
_SZAZALEK = re.compile(r"^[–-]\s*(\d+)\s*%\s*$")
_REGI_AR = re.compile(r"^(\d[\d  ]*)\s*Ft(?:/kg|/10 dkg)?\s*$", re.I)


def _blokkok(szoveg: str) -> list:
    return [[s.strip() for s in b.split("\n") if s.strip()]
            for b in re.split(r"\n\s*\n", _ligatura(szoveg or ""))]


def _ar_elotte(blokkok: list, i: int):
    """A HÚSPULTOS termék ára a PDF-ben sokszor a neve ELŐTT áll, külön
    blokkokban: „1599 Ft/kg" · „– 28 %" · „1145" · „Ft/kg" · a név.
    Visszafelé olvassuk: (új ár, régi ár) vagy (None, None)."""
    j = i - 1
    if j < 0 or len(blokkok[j]) != 1 or not _EGYSEG_BLOKK.match(blokkok[j][0]):
        return None, None
    j -= 1
    if j < 0 or len(blokkok[j]) != 1 or not _CSAK_SZAM.match(blokkok[j][0]):
        return None, None
    uj = int(re.sub(r"[  ]", "", blokkok[j][0]))
    j -= 1
    if j >= 0 and len(blokkok[j]) == 1 and _SZAZALEK.match(blokkok[j][0]):
        j -= 1
    regi = None
    if j >= 0 and len(blokkok[j]) == 1:
        m = _REGI_AR.match(blokkok[j][0])
        if m:
            regi = int(re.sub(r"[  ]", "", m.group(1)))
    return uj, (regi if regi and regi > uj else None)


def pultos_termekek(szoveg: str, ujsag: str = "", ervenyes: str = "") -> list:
    """A húspultos (kilós) áru. Schibik Miklós (2026-09-28): „a Tescónál a
    húspultos dolgok nincsenek benne". Ezeknél a PDF nem „Ft/1 kg"-ot ír,
    hanem „Ft/kg"-ot, és az ár vagy a név UTÁN áll a blokkban (870 Ft/kg,
    699 Ft/kg), vagy a név ELŐTT külön blokkokban (`_ar_elotte`). Ha a
    blokkban a pultos mellett a csomagolt párja is ott van („csomagolt,
    különböző kiszerelésben kapható"), a blokk végi kilós árak a csomagolté."""
    ki = []
    blokkok = _blokkok(szoveg)
    for i, sorok in enumerate(blokkok):
        jelek = [k for k, s in enumerate(sorok) if _PULT.match(s)]
        if not jelek or any(_EGYS_SOR.match(s) for s in sorok):
            continue            # „Ft/1 kg"-os blokk: a rendes elemző dolga
        csomagolt = next((k for k, s in enumerate(sorok)
                          if s.lower().startswith("csomagolt, különböző")), None)
        kilos = [(k, int(re.sub(r"[  ]", "", _KILOS_AR.match(s).group(1))))
                 for k, s in enumerate(sorok) if _KILOS_AR.match(s)]
        utana = [a for k, a in kilos if k > jelek[-1]
                 and (csomagolt is None or k < csomagolt)]
        eleje = 0
        for k in jelek:
            nev = " ".join(sorok[eleje:k]).strip(" ,")
            eleje = k + 1
            if not nev or re.search(r"\bFt\b", nev):
                continue
            if utana:
                uj, regi = utana[-1], (utana[0] if len(utana) > 1 else None)
            else:
                uj, regi = _ar_elotte(blokkok, i)
            if uj is None:
                continue
            pult = "húspult" if "hús" in sorok[k].lower() else "csemegepult"
            t = Termek(bolt=BOLT, nev=nev, ar=uj, kiszereles="kilónként",
                       egysegar="1 kg = %d Ft" % uj, ervenyes=ervenyes,
                       kategoria=ujsag, megjegyzes="%sban kapható" % pult)
            if regi and regi > uj:
                t.regi_ar = regi
                t.kedvezmeny = "-%d%%" % round((1 - uj / regi) * 100)
            ki.append(t)
        # a csomagolt párja (vákuumcsomagolt): a blokk végi kilós árak
        if csomagolt is not None:
            nev = " ".join(sorok[jelek[-1] + 1:csomagolt]).strip(" ,")
            arak = [a for k, a in kilos if k > csomagolt]
            if nev and arak and not re.search(r"\bFt\b", nev):
                uj, regi = arak[-1], (arak[0] if len(arak) > 1 else None)
                t = Termek(bolt=BOLT, nev=nev, ar=uj, kiszereles="kilónként",
                           egysegar="1 kg = %d Ft" % uj, ervenyes=ervenyes,
                           kategoria=ujsag,
                           megjegyzes="csomagolt, különböző kiszerelésben")
                if regi and regi > uj:
                    t.regi_ar = regi
                    t.kedvezmeny = "-%d%%" % round((1 - uj / regi) * 100)
                ki.append(t)
    return ki


def termekek(szoveg: str, ujsag: str = "", ervenyes: str = "") -> list:
    ki = pultos_termekek(szoveg, ujsag, ervenyes)
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
