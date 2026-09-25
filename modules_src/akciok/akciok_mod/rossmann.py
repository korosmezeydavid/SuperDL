# -*- coding: utf-8 -*-
"""Rossmann – a shop.rossmann.hu kedvezményes termékei.

A webshop (Next.js) a termékeket a saját nyilvános GraphQL-végpontjáról
tölti (api.rossmann.hu/graphql, `listProductsByCategory`). Ugyanazt kérjük,
amit a böngésző az „Általános akciók” oldalon: az IS_DISCOUNTED=1 szűrővel
(2026-09-25-i mérés: 1938 termék), oldalanként 100-at, a lapok között kis
szünettel, hogy ne terheljük a boltot.

Egy termék (a mezők, amiket használunk):
    name "Kubu gyümölcspüré alma - barack - banán - répa - 100 g"
    price 199, price_original 299, price_unit 1990, unit_base "kg"
    price_rplus / price_rossmano: kártyás (Rossmann Plus / Rossmanó) ár
    category_path_main[0].name "Baba", deposit_fee 0
"""
import re
import time

from .termek import Termek

BOLT = "Rossmann"
API = "https://api.rossmann.hu/graphql"
FEJLEC = {"Origin": "https://shop.rossmann.hu",
          "Referer": "https://shop.rossmann.hu/altalanos-akciok"}
LAP = 100
MAX_LAP = 40                     # 4000 termék – bőven a mért 1938 fölött
SZUNET_MP = 0.7

KERDES = """query($f:[ProductFilter!],$first:Int!,$page:Int){
 listProductsByCategory(filters:$f, first:$first, page:$page){
  paginatorInfo{ total lastPage currentPage }
  data{ id name slug price price_original price_unit unit_base
        price_rplus price_rossmano deposit_fee
        category_path_main{ name } badges_featured{ info } }
 }
}"""

_MERET = re.compile(r"^\(?\d[\d,.x ]*\)?\s*(?:\d[\d,.]*\s*)?(g|kg|ml|l|cl|db|tekercs|"
                    r"lap|pár|mosás|m|cm|kapszula|tabletta|tasak|darab)\b", re.I)


def _szetvag(nev: str) -> tuple:
    """„Kubu … - répa - 100 g” → („Kubu … - répa”, „100 g”)."""
    nev = re.sub(r"\s+", " ", nev or "").strip()
    # árnyalat: „ajakfény /Blush Rush” → „ajakfény, Blush Rush”
    nev = re.sub(r"\s+/(?=\S)", ", ", nev)
    i = nev.rfind(" - ")
    if i > 0 and _MERET.match(nev[i + 3:].strip()):
        return nev[:i].strip(), nev[i + 3:].strip()
    return nev, ""


def _egesz(x):
    try:
        return int(round(float(x))) if x is not None else None
    except (TypeError, ValueError):
        return None


def termek(p: dict) -> Termek | None:
    """Egy GraphQL-termékből Termek; None, ha nincs használható ára."""
    ar = _egesz(p.get("price"))
    if not ar:
        return None
    nev, meret = _szetvag(p.get("name") or "")
    if not nev:
        return None
    kat = (p.get("category_path_main") or [{}])[0].get("name") or ""
    t = Termek(bolt=BOLT, nev=nev, ar=ar, kiszereles=meret, kategoria=kat)
    regi = _egesz(p.get("price_original"))
    if regi and regi > ar:
        t.regi_ar = regi
        t.kedvezmeny = "-%d%%" % round((1 - ar / regi) * 100)
    egys, alap = _egesz(p.get("price_unit")), (p.get("unit_base") or "").strip()
    if egys and alap:
        t.egysegar = "1 %s = %d Ft" % (alap, egys)
    # kártyás ár: a kisebbik, ha tényleg olcsóbb a polcárnál
    for mezo, kartya in (("price_rplus", "Rossmann Plus kártyával"),
                         ("price_rossmano", "Rossmanó klubtagként")):
        k = _egesz(p.get(mezo))
        if k and k < ar and (t.kartyas_ar is None or k < t.kartyas_ar):
            t.kartyas_ar, t.kartya_nev = k, kartya
    if not t.regi_ar and t.kartyas_ar:
        t.kedvezmeny = "-%d%% kártyával" % round((1 - t.kartyas_ar / ar) * 100)
    jegyzet = []
    betet = _egesz(p.get("deposit_fee"))
    if betet:
        jegyzet.append("+ %d Ft betétdíj" % betet)
    for b in p.get("badges_featured") or []:
        info = (b or {}).get("info") or ""
        if info and not re.search(r"^(\d+\s*%|R\+ kártyával)", info, re.I):
            jegyzet.append(info.strip().capitalize())
    t.megjegyzes = ", ".join(dict.fromkeys(jegyzet))
    t.kod = str(p.get("id") or "")
    return t


def letolt(post_json, jelez=lambda s: None) -> list:
    """post_json(url, adat, fejlec) -> dict. Két kör: a leárazott termékek,
    aztán a csak Rossmann Plus kártyával olcsóbbak (azoknak nincs „eredeti
    áruk”, csak kártyás áruk). Egy termék csak egyszer kerül a listába."""
    ki, latott = [], set()
    for mezo, ertek, cim in (("IS_DISCOUNTED", "1", "akciós termékek"),
                             ("PROMOTION_TYPE", "rossmann_plus", "kártyás ajánlatok")):
        _kor(post_json, jelez, mezo, ertek, cim, ki, latott)
    return ki


def _kor(post_json, jelez, mezo, ertek, cim, ki, latott) -> None:
    lap, utolso = 1, 1
    while lap <= min(utolso, MAX_LAP):
        jelez("Rossmann %s: %d. oldal…" % (cim, lap))
        v = post_json(API, {"query": KERDES, "variables": {
            "f": [{"field": mezo, "value": [ertek]}],
            "first": LAP, "page": lap}}, FEJLEC)
        lista = ((v or {}).get("data") or {}).get("listProductsByCategory") or {}
        utolso = int((lista.get("paginatorInfo") or {}).get("lastPage") or 0)
        adat = lista.get("data") or []
        if not adat:
            break
        for p in adat:
            t = termek(p)
            if t and t.kod not in latott:
                latott.add(t.kod)
                ki.append(t)
        lap += 1
        time.sleep(SZUNET_MP)
