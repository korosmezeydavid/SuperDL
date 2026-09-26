# -*- coding: utf-8 -*-
"""Lidl – a Lidl hivatalos szórólap-szolgáltatása (Schwarz „leaflets”).

  overview  → a heti újságok listája, mindegyikhez `pdfUrl`
  PDF       → a nyomdai PDF-nek VALÓDI szövegrétege van (nem kép), a
              Core-ban lévő pdfminer kiolvassa.

A PDF szövegében egy termék EGY bekezdés (üres sorokkal határolt blokk),
aminek az utolsó sora a cikkszám:

    HÚSFARM
    Friss, szeletelt, light karaj
    Hártyázott
    400 g; 1 kg = 2 948 Ft
    6400870

Utána jönnek az ár-bekezdések, háromféle alakban (2026-09-25-i mérés):
    „Szuper ár!” + „1999 Ft”                          → egy ár
    „-13% 1 359 Ft” + „1179 Ft”                       → kedvezmény, régi, új
    „Lidl Plus-szal” + „-30%**” + „1399 Ft” + „1 999 Ft” → appos és rendes ár
A sorvégi dupla szóköz a nyomdában tördelt név folytatását jelzi.
"""
import io
import json
import re

from .termek import Termek, ar_szam

BOLT = "Lidl"
OVERVIEW = ("https://endpoints.leaflets.schwarz/v4/overview"
            "?client_locale=lidl/hu-HU&region_id=0")

_KOD = re.compile(r"^\d{4,7}$")
_KISZERELES = re.compile(
    r"(\d+(?:[,.]\d+)?\s*(?:g|kg|dkg|ml|l|cl|db|m|cm|mm)\b|/kg|/db|/csomag|"
    r"^\s*\d+\s*x\s*\d+|változó kiszerel)", re.I)
_ERVENYES = re.compile(
    r"(\d{2})\.\s?(\d{2})\.\s?\w*(?:tól|től)\s+(\d{2})\.\s?(\d{2})-ig", re.I)
_SZEMET = re.compile(
    r"(jó választás|^a hazai$|^az év|kereskedője|még több ajánlat|az árak a "
    r"dekorációt|akciós termékeink|\.indd|^\d{4}\. \d{2}\. \d{2}\.|^\d+$|"
    r"^\d+/\d{4}$|^\*|a termékek nem képezik|lidl plus applikáció|"
    r"nyomdai hibákért|^friss pékáru)", re.I)
_AR_SOR = re.compile(r"^(-\d+%\**\s*)?\d[\d  ]*\s?Ft\**$")


def ujsagok(overview: dict) -> list:
    """[(cím, pdfUrl, kezdet, vég)] – csak az aktuális vagy jövő heti élelmiszer-
    és nonfood-újságok, a régiek nélkül."""
    ki, latott = [], set()
    for c in overview.get("categories", []):
        for s in c.get("subcategories", []):
            for f in s.get("flyers", []):
                url = f.get("pdfUrl") or ""
                if not url or url in latott:
                    continue
                latott.add(url)
                ki.append((f.get("title") or f.get("name") or "Lidl újság",
                           url, f.get("offerStartDate") or f.get("startDate") or "",
                           f.get("offerEndDate") or f.get("endDate") or ""))
    return ki


def _nev_sorok(sorok: list) -> list:
    """A tördelt sorok összefűzése: a sorvégi szóköz = folytatás."""
    ki = []
    for s in sorok:
        if ki and ki[-1].endswith(" "):
            ki[-1] = ki[-1].rstrip() + " " + s.strip() + \
                (" " if s.endswith(" ") else "")
        elif ki and re.search(r"[-/,]$", ki[-1].rstrip()) \
                and not ki[-1].rstrip().endswith(" -"):
            # „Narancs-grapefruit-” / „Natúr / light /” – a név folytatódik
            elo = ki[-1].rstrip()
            ki[-1] = elo + ("" if elo.endswith("-") else " ") + s.strip() + \
                (" " if s.endswith(" ") else "")
        else:
            ki.append(s.strip() + (" " if s.endswith(" ") else ""))
    return [re.sub(r"\s+", " ", k).strip() for k in ki if k.strip()]


def _szep(s: str) -> str:
    """Csupa nagybetűs márkanév → „Húsfarm” (a képernyőolvasó a csupa nagy
    rövid szavakat betűzi)."""
    return " ".join(w.capitalize() if len(w) >= 2 and w.isupper() else w
                    for w in s.split())


def _arak(bekezdesek: list, t: Termek) -> None:
    sorok = [s.strip() for b in bekezdesek for s in b.split("\n") if s.strip()]
    plus = any("lidl plus" in s.lower() for s in sorok)
    ertekek = []
    for s in sorok:
        m = re.match(r"^(-\d+%)\**\s*(\d[\d  ]*)\s?Ft", s)
        if m:                                  # „-13% 1 359 Ft” = régi ár
            t.kedvezmeny = m.group(1)
            t.regi_ar = ar_szam(m.group(2))
            continue
        m = re.match(r"^(-\d+%)\**$", s)
        if m:
            t.kedvezmeny = m.group(1)
            continue
        if re.search(r"\d\s?Ft\**$", s):
            a = ar_szam(s)
            if a is not None:
                ertekek.append(a)
    ertekek = [a for a in ertekek if 0 < a < 1_000_000]
    if plus and len(ertekek) >= 2:
        # az appos ár a KISEBB (a PDF sorrendje nem mindig ugyanaz)
        t.kartyas_ar, t.ar = sorted(ertekek[:2])
        t.kartya_nev = "Lidl Plus-szal"
    elif plus and ertekek:
        t.kartyas_ar, t.kartya_nev = ertekek[0], "Lidl Plus-szal"
    elif t.regi_ar is not None and ertekek:
        t.ar = ertekek[0]
    elif len(ertekek) >= 2 and ertekek[0] < ertekek[1]:
        # „Minden második termék: -71%” + 199 + 699: az akciós és a rendes
        t.ar, t.regi_ar = ertekek[0], ertekek[1]
    elif ertekek:
        t.ar = ertekek[0]
    _hihetoseg(t)
    tobbes = [s for s in sorok if len(s) < 40
              and re.search(r"minden|második|termék:", s, re.I)]
    if tobbes:
        t.megjegyzes = ", ".join(x for x in [t.megjegyzes,
                                            " ".join(tobbes)] if x)


def _hihetoseg(t: Termek) -> None:
    """⚠️ Egy rossz ár rosszabb, mint egy hiányzó. A PDF-ből kiolvasott
    árakat józan ésszel ellenőrizzük, és ami nem stimmel, azt ELHAGYJUK:
      * a régi ár csak akkor igaz, ha nagyobb az újnál, és a kettő aránya
        nagyjából egyezik a kiírt kedvezménnyel;
      * az appos ár nem lehet nagyobb a rendesnél."""
    if t.kartyas_ar is not None and t.ar is not None and t.kartyas_ar > t.ar:
        t.kartyas_ar, t.ar = t.ar, t.kartyas_ar
    if t.kartyas_ar is not None and t.ar is not None and t.ar > t.kartyas_ar * 4:
        t.ar = None                 # összeolvadt számjegyek, nem ár
    # a cikkszám-felsorolás („6412154 / 6412153 /”) nem a felhasználónak szól
    t.megjegyzes = re.sub(r"(,\s*)?(\d{5,7}\s*/?\s*)+$", "",
                          t.megjegyzes).strip(" ,")
    alap = t.ar
    if t.regi_ar is not None:
        if alap is None or t.regi_ar <= alap or t.regi_ar > alap * 5:
            t.regi_ar = None
        elif t.kedvezmeny:
            m = re.match(r"-(\d+)%", t.kedvezmeny)
            if m:
                valos = round((1 - alap / t.regi_ar) * 100)
                if abs(valos - int(m.group(1))) > 3:
                    t.regi_ar = None


def termekek(szoveg: str, ujsag: str = "") -> list:
    """A PDF szövegéből a termékek."""
    bekezdesek = [b for b in re.split(r"\n\s*\n", szoveg.replace("\x0c", "\n\n"))
                  if b.strip()]
    ki = []
    ervenyes = ""
    aktualis = None
    arak = []
    for b in bekezdesek:
        sorok = [s for s in b.split("\n") if s.strip()]
        m = _ERVENYES.search(b)
        if m and len(sorok) <= 2:
            ervenyes = "%s.%s-tól %s.%s-ig" % m.groups()
            continue
        if len(sorok) >= 2 and _KOD.match(sorok[-1].strip()):
            if aktualis is not None:
                _arak(arak, aktualis)
                ki.append(aktualis)
            test = sorok[:-1]
            meret = egysegar = ""
            for i in range(len(test) - 1, -1, -1):
                sor = test[i].strip()
                if re.match(r"^1\s*(kg|l|db|tekercs|m)\s*=", sor):
                    egysegar = test.pop(i).strip().rstrip(";")
                    continue
                if _KISZERELES.search(sor):
                    meret = test.pop(i).strip()
                    break
            nevek = [n for n in _nev_sorok(test) if not _SZEMET.search(n)]
            if not nevek:
                aktualis = None
                arak = []
                continue
            if len(nevek) >= 2 and nevek[0].isupper():
                nev = _szep(nevek[0]) + " " + nevek[1]
                tobbi = nevek[2:]
            else:
                nev, tobbi = _szep(nevek[0]), nevek[1:]
            meret_resz = meret.split(";")
            aktualis = Termek(bolt=BOLT, nev=nev, kod=sorok[-1].strip(),
                              kiszereles=meret_resz[0].strip(),
                              egysegar=(meret_resz[1].strip()
                                        if len(meret_resz) > 1 else "")
                              or egysegar,
                              ervenyes=ervenyes, kategoria=ujsag,
                              megjegyzes=", ".join(tobbi))
            arak = []
            continue
        if aktualis is not None and (
                any(_AR_SOR.match(s.strip()) for s in sorok)
                or re.search(r"lidl plus|szuper ár|^-\d+%|minden|második",
                             b, re.I | re.M)):
            arak.append(b)
    if aktualis is not None:
        _arak(arak, aktualis)
        ki.append(aktualis)
    return [t for t in ki if t.ar is not None or t.kartyas_ar is not None]


def aktualis(lista: list, ma=None) -> list:
    """Csak a még érvényes újságok (a vége ma vagy később), legfeljebb 4."""
    import datetime as _dt
    ma = (ma or _dt.date.today()).isoformat()
    ki = [u for u in lista if not u[3] or u[3][:10] >= ma]
    return ki[:4]


def letolt(get_bytes, jelez=lambda s: None, ma=None) -> list:
    """A heti Lidl-újságok termékei. `get_bytes(url) -> bytes`."""
    from pdfminer.high_level import extract_text
    ov = json.loads(get_bytes(OVERVIEW).decode("utf-8"))
    ki, latott = [], set()
    for cim, url, _k, _v in aktualis(ujsagok(ov), ma):
        jelez("Lidl: %s letöltése…" % cim)
        pdf = get_bytes(url)
        jelez("Lidl: %s olvasása…" % cim)
        for t in termekek(extract_text(io.BytesIO(pdf)), cim):
            if t.kod in latott:
                continue
            latott.add(t.kod)
            ki.append(t)
    return ki
