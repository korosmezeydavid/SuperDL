# -*- coding: utf-8 -*-
"""Praktiker – a bolt saját akciós oldalai (praktiker.hu).

Petrus József kérése (2026-09-28): „néhány férfiasabb bolt is belekerülhetne:
Euronics, MediaMarkt, Praktiker, OBI".

Nem lapozós kép: a praktiker.hu oldalai a termékeket a lapba ágyazott
adatként is kiadják (ugyanazt, amit a weboldal kirajzol) – név, ár, régi ár,
kedvezmény, az akció kezdete és vége, a termék címe:

    {"id":421301,"name":"Keter Hollywood műanyag 270L … kerti tároló", …,
     "url":"/kert/…/p/421301", …,
     "price":{"displayPrice":"13.990 Ft / darab","price":13990,
              "oldPrice":16990,"discountPercent":17,"isLoyaltyPrice":false,
              "details":{"name":"Akció","fromDate":"2026-09-01",
                         "endDate":"2026-09-28"}}, …}

Két oldal: az „Árzuhanás" (/kiarusitas/bfd, ~190 termék) és a
törzsvásárlói ajánlatok (/torzsvasarloi-ajanlatok/ilp, ~60 termék).
"""
import json
import re

from .termek import Termek

BOLT = "Praktiker"
ALAP = "https://www.praktiker.hu"
OLDALAK = [("/kiarusitas/bfd", "Árzuhanás"),
           ("/torzsvasarloi-ajanlatok/ilp", "Törzsvásárlói ajánlatok")]
KARTYA = "Praktiker Plusz törzsvásárlói kártyával"

_OBJ = re.compile(r'\{"id":(\d+),"name":"')


def _datum(s: str) -> str:
    """"2026-09-28" → "09.28" (a `termek.lejart` ezt érti)."""
    m = re.match(r"\d{4}-(\d{2})-(\d{2})", s or "")
    return "%s.%s" % m.groups() if m else ""


def ervenyes(reszlet: dict) -> str:
    tol, ig = _datum(reszlet.get("fromDate", "")), _datum(reszlet.get("endDate", ""))
    if tol and ig:
        return "%s-tól %s-ig" % (tol, ig)
    if ig:
        return "%s-ig" % ig
    return ""


def termekek(oldal: str, kategoria: str = "") -> list:
    dec = json.JSONDecoder()
    ki, latott = [], set()
    for m in _OBJ.finditer(oldal or ""):
        if m.group(1) in latott:
            continue
        try:
            o, _ = dec.raw_decode(oldal, m.start())
        except ValueError:
            continue
        ar = o.get("price") if isinstance(o, dict) else None
        if not (isinstance(ar, dict) and ar.get("price")):
            continue
        nev = (o.get("name") or "").strip()
        if not nev:
            continue
        latott.add(m.group(1))
        url = o.get("url") or ""
        t = Termek(bolt=BOLT, nev=nev, kategoria=kategoria,
                   kod=str(o.get("id")),
                   url=ALAP + url if url.startswith("/") else url,
                   ervenyes=ervenyes(ar.get("details") or {}))
        try:
            most = int(round(float(ar["price"])))
            regi = int(round(float(ar["oldPrice"]))) if ar.get("oldPrice") else None
        except (TypeError, ValueError):
            continue
        if ar.get("isLoyaltyPrice"):
            # a kártyás ár KÜLÖN hangzik el; kártya nélkül a régi ár érvényes
            t.kartyas_ar, t.kartya_nev = most, KARTYA
            t.ar = regi
        else:
            t.ar = most
            if regi and regi > most:
                t.regi_ar = regi
        if ar.get("discountPercent"):
            t.kedvezmeny = "-%d%%" % int(ar["discountPercent"])
        # PRAKTIKER PLUSZ: a törzsvásárlói ár SZINTENKÉNT más (3 %, 5 %…).
        # Kártyás árként a legalsó szint megy (azt minden tag megkapja), a
        # magasabbak a megjegyzésbe.
        szintek = []
        for sz in o.get("loyalty") or []:
            p = (sz or {}).get("price") or {}
            if p.get("isLoyaltyPrice") and p.get("price"):
                try:
                    szintek.append((int(round(float(p["price"]))),
                                    int(p.get("discountPercent") or 0)))
                except (TypeError, ValueError):
                    pass
        szintek.sort(reverse=True)          # legkisebb kedvezmény elöl
        if szintek and t.ar and szintek[0][0] < t.ar and not t.kartyas_ar:
            t.kartyas_ar, t.kartya_nev = szintek[0][0], KARTYA
            if len(szintek) > 1:
                # csak a legjobb szint – öt szám egymás után felolvasva sok
                t.megjegyzes = ("a legmagasabb törzsvásárlói szinten "
                                "%d forint (-%d%%)" % szintek[-1])
        if not t.ervenyes:
            t.ervenyes = ervenyes({"fromDate": o.get("startDate") or "",
                                   "endDate": o.get("endDate") or ""})
        # egységár: csak ha más, mint a darab-/csomagár („3999 Ft / m2")
        egyseg = ((o.get("productItemUnit") or {}).get("unitType") or "").strip()
        try:
            e_ar = int(round(float(ar.get("unitPrice") or 0)))
        except (TypeError, ValueError):
            e_ar = 0
        if e_ar and egyseg and e_ar != most:
            t.egysegar = "%d Ft / %s" % (e_ar, egyseg)
        ki.append(t)
    return ki


def letolt(get, jelez=lambda s: None) -> list:
    ki, latott = [], set()
    for ut, cim in OLDALAK:
        jelez("Praktiker: %s…" % cim)
        try:
            lap = get(ALAP + ut)
        except Exception:                   # noqa: BLE001 – a másik oldal még jöhet
            continue
        for t in termekek(lap, cim):
            if t.kod not in latott:
                latott.add(t.kod)
                ki.append(t)
    return ki
