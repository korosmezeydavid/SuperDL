# -*- coding: utf-8 -*-
"""dm – a dm.hu kiárusításos termékei.

A dm-nek Magyarországon nincs heti akciós újsága (tartósan alacsony árakkal
dolgozik); ami valóban olcsóbb a korábbinál, az a „Kiárusítás”. A dm.hu
a termékeket a saját keresőszolgáltatásából tölti
(product-search.services.dmtech.com), mi is onnan kérjük, a böngészővel
azonos szűrővel (popularFacet=Kiárusítás; 2026-09-25: 232 termék).

⚠️ A szolgáltatás a sok, gyors kérést elutasítja („Too many requests”),
ezért 48-as lapokkal és a lapok között szünettel kérünk.

Egy termék tileData-ja (a használt mezők):
    title.tileHeadline / a top-level „title”: „Pelenkázó alátét, 10 db”
    brand.name, price.price.current.value „1 499 Ft”,
    price.price.previous.value „2 999 Ft”, price.tileInfos[0]
    „150 ml (9,99 Ft / 1 ml)”, trackingData.categories[0]
"""
import re
import time
import urllib.parse

from .termek import Termek, ar_szam

BOLT = "dm"
KERES = "https://product-search.services.dmtech.com/hu/search/static?"


def cim(lap: int, meret: int) -> str:
    return KERES + urllib.parse.urlencode({"pageSize": meret, "currentPage": lap,
                                           "popularFacet": "Kiárusítás"})
LAP = 48
MAX_LAP = 15
SZUNET_MP = 1.5
_INFO = re.compile(r"^(.*?)\s*\((.+?)\s*/\s*(.+?)\)\s*$")


def termek(p: dict) -> Termek | None:
    td = p.get("tileData") or {}
    arak = ((td.get("price") or {}).get("price") or {})
    ar = ar_szam(((arak.get("current") or {}).get("value")) or "")
    if not ar:
        return None
    marka = ((td.get("brand") or {}).get("name")) or p.get("brandName") or ""
    cim = re.sub(r"\s+", " ", p.get("title") or "").strip()
    info = ((td.get("price") or {}).get("tileInfos") or [""])[0] or ""
    info = info.replace("\xa0", " ").replace(" ", " ")
    meret, egysegar = "", ""
    m = _INFO.match(info or "")
    if m:
        meret = m.group(1).strip()
        ertek = re.sub(r"[\s ]+", "", m.group(2)).replace("Ft", "")
        ertek = re.sub(r",00$", "", ertek)
        egysegar = "%s = %s Ft" % (m.group(3).strip(), ertek)
    if meret and cim.endswith(", " + meret):
        cim = cim[: -len(meret) - 2].strip()
    nev = cim if not marka or cim.lower().startswith(marka.lower()) \
        else "%s %s" % (marka, cim)
    kat = ((td.get("trackingData") or {}).get("categories") or [""])[0]
    t = Termek(bolt=BOLT, nev=nev, ar=int(ar), kiszereles=meret,
               egysegar=egysegar, kategoria=kat,
               megjegyzes="Kiárusítás, a készlet erejéig")
    regi = ar_szam(((arak.get("previous") or {}).get("value")) or "")
    if regi and regi > ar:
        t.regi_ar = int(regi)
        t.kedvezmeny = "-%d%%" % round((1 - ar / regi) * 100)
    t.kod = str(p.get("dan") or p.get("gtin") or "")
    return t


VARAKOZAS_MP = (5, 15, 30)       # „Too many requests” után ennyit várunk


def _kerd(get_json, url, jelez):
    """Egy lap; 429-nél türelmesen újrapróbáljuk, aztán feladjuk."""
    for i in range(len(VARAKOZAS_MP) + 1):
        try:
            return get_json(url, {"Origin": "https://www.dm.hu",
                                  "Referer": "https://www.dm.hu/"})
        except Exception as e:                     # noqa: BLE001
            if "429" not in str(e) or i == len(VARAKOZAS_MP):
                raise
            jelez("dm: a bolt lassítást kér, %d mp múlva újra…" % VARAKOZAS_MP[i])
            time.sleep(VARAKOZAS_MP[i])


def letolt(get_json, jelez=lambda s: None) -> list:
    """get_json(url, fejlec) -> dict."""
    ki, latott = [], set()
    lap, osszes = 0, 1
    while lap < min(osszes, MAX_LAP):
        jelez("dm: %d. oldal…" % (lap + 1))
        d = _kerd(get_json, cim(lap, LAP), jelez) or {}
        osszes = int(d.get("totalPages") or 0)
        termekek = d.get("products") or []
        if not termekek:
            break
        for p in termekek:
            t = termek(p)
            if t and t.kod not in latott:
                latott.add(t.kod)
                ki.append(t)
        lap += 1
        if lap < min(osszes, MAX_LAP):
            time.sleep(SZUNET_MP)
    return ki
