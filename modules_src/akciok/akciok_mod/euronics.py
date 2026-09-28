# -*- coding: utf-8 -*-
"""Euronics – a bolt saját ajánlat-oldalai (euronics.hu).

Petrus József kérése (2026-09-28). A „Heti ajánlatok" oldal (/heti-ajanlatok)
maga is tíz terméket mutat, és felsorolja az éppen futó kampányokat is,
mindegyiket az érvényességével és egy hivatkozással:

    Érvényes: 2026.09.17. - 2026.09.30. között.
    <a class="btn btn-primary" href="/jo-arak-jo-helyen">…

A termékkártyák rendes HTML-ben jönnek (nem kép), schema.org-jelöléssel:
név, termékcím, ár, és ha akciós, az áthúzott eredeti ár. A lejárt kampányok
(a lapon régi, 2023-as is áll) kimaradnak.
"""
import datetime as _dt
import html
import re

from .termek import Termek, ar_szam

BOLT = "Euronics"
ALAP = "https://euronics.hu"
HETI = ALAP + "/heti-ajanlatok"

_KAMPANY = re.compile(
    r"Érvényes:\s*(20\d\d)\.\s*(\d\d)\.\s*(\d\d)\.?\s*-\s*"
    r"(20\d\d)\.\s*(\d\d)\.\s*(\d\d)\.?")


# a kampány-oldalak címéből ékezetes név (a többi az útból lesz)
_CIMEK = {"/jo-arak-jo-helyen": "Jó árak jó helyen",
          "/kiemelt-ajanlatok": "Kiemelt ajánlatok"}


def _szoveg(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s).replace("\xa0", " ")).strip()


def kampanyok(oldal: str, ma: _dt.date | None = None) -> list:
    """[(út, cím, érvényes)] – csak a MOST futó kampányok."""
    ma = ma or _dt.date.today()
    ki, latott = [], set()
    for m in _KAMPANY.finditer(oldal or ""):
        try:
            tol = _dt.date(*(int(x) for x in m.group(1, 2, 3)))
            ig = _dt.date(*(int(x) for x in m.group(4, 5, 6)))
        except ValueError:
            continue
        if not (tol <= ma <= ig):
            continue
        h = re.search(r'href="(/[a-z0-9-]+)"', oldal[m.end():m.end() + 600])
        if not h or h.group(1) in latott:
            continue
        latott.add(h.group(1))
        cim = _CIMEK.get(h.group(1)) or \
            h.group(1).strip("/").replace("-", " ").capitalize()
        ki.append((h.group(1), cim, "%02d.%02d-tól %02d.%02d-ig"
                   % (tol.month, tol.day, ig.month, ig.day)))
    return ki


def termekek(oldal: str, kategoria: str = "", ervenyes: str = "") -> list:
    ki = []
    for d in (oldal or "").split('data-product-id="')[1:]:
        kod = d[:d.find('"')]
        url = re.search(r'itemprop="url" content="([^"]+)"', d)
        nev = re.search(r'itemprop="name" class="product-card__name-link-text">'
                        r'(.*?)</span>', d, re.S)
        arblokk = re.search(r'<div class="price[^"]*"[^>]*>(.*?)</div>', d, re.S)
        if not (nev and arblokk):
            continue
        regi = re.search(r'class="price-original">(.*?)</span>',
                         arblokk.group(1), re.S)
        most = arblokk.group(1)
        if regi:
            most = most.replace(regi.group(0), "")
        ar = ar_szam(_szoveg(most))
        if ar is None:
            continue
        t = Termek(bolt=BOLT, nev=_szoveg(nev.group(1)), ar=ar, kod=kod,
                   url=url.group(1) if url else "", kategoria=kategoria,
                   ervenyes=ervenyes)
        if regi:
            r = ar_szam(_szoveg(regi.group(1)))
            if r and r > ar:
                t.regi_ar = r
                t.kedvezmeny = "-%d%%" % round((r - ar) * 100 / r)
        ki.append(t)
    return ki


def letolt(get, jelez=lambda s: None, ma=None) -> list:
    jelez("Euronics: heti ajánlatok…")
    fo = get(HETI)
    ki, latott = [], set()

    def hozza(lista):
        for t in lista:
            if t.kod not in latott:
                latott.add(t.kod)
                ki.append(t)

    for ut, cim, erv in kampanyok(fo, ma):
        jelez("Euronics: %s…" % cim)
        try:
            hozza(termekek(get(ALAP + ut), cim, erv))
        except Exception:                   # noqa: BLE001 – a többi még jöhet
            continue
    hozza(termekek(fo, "Heti ajánlatok"))
    return ki
