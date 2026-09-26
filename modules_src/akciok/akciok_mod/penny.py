# -*- coding: utf-8 -*-
"""Penny – a penny.hu saját, nyilvános ajánlat-oldalai.

Az oldal szerver oldalon renderelt HTML: minden termék egy „csempe”, benne a
név, a kiszerelés, az érvényesség és az ár(ak) – kártya nélkül és PENNY
Kártyával. Ugyanazt olvassuk, amit a böngésző megmutat; semmit nem
tárolunk tovább és nem terjesztünk.

Felépítés (2026-09-25-i mérés):
  /ajanlatok                    → a heti fő kategória linkje
  /category/ajanlatok-MMDDMMDD-koezoett          → az összes (304 termék, 7 lap)
  /category/ajanlatok-…-koezoett-<alkategória>   → alkategóriák
Az alkategóriákat járjuk be (azokból tudjuk a kategória nevét), lapozva."""
import html
import re

from .termek import Termek, ar_szam

BOLT = "Penny"
ALAP = "https://www.penny.hu"

# A „gyűjtő” alkategóriák ugyanazokat a termékeket ismétlik – ezeket csak
# akkor vesszük fel, ha a termék máshol nem szerepelt.
_GYUJTOK = ("kiemelt", "penny-kartyaval", "online-extra",
            "hetvegi", "hetfotol")


def _tiszta(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def fo_kategoria(ajanlatok_html: str) -> str:
    """Az /ajanlatok oldalról a heti fő kategória útja."""
    for ut in re.findall(r'href="(/category/ajanlatok-[^"?#]+)"',
                         ajanlatok_html):
        return ut
    return ""


def alkategoriak(fo_html: str, fo_ut: str) -> list:
    """[(út, név)] – a fő kategória alkategóriái, a linkszöveg a név."""
    ki, latott = [], set()
    minta = r'<a[^>]+href="(%s-[^"?#]+)"[^>]*>(.*?)</a>' % re.escape(fo_ut)
    for ut, szoveg in re.findall(minta, fo_html, re.S):
        if ut in latott:
            continue
        latott.add(ut)
        # a linkszöveg végén a termékszám áll („Italok 29”) – az nem név
        nev = re.sub(r"\s+\d+$", "", _tiszta(szoveg)) \
            or _slugbol(ut[len(fo_ut) + 1:])
        ki.append((ut, nev))
    return ki


def _slugbol(slug: str) -> str:
    return slug.replace("-", " ").strip().capitalize()


def lapok_szama(oldal_html: str) -> int:
    szamok = [int(n) for n in re.findall(r'[?&]page=(\d+)', oldal_html)]
    return max(szamok) if szamok else 1


def csempek(oldal_html: str) -> list:
    """Egy kategória-oldal termékei (Termek-lista, kategória nélkül)."""
    darabok = re.split(r'(?=<a href="/products/)', oldal_html)
    ki = []
    for d in darabok[1:]:
        m = re.match(r'<a href="(/products/[^"]+)"', d)
        nev = re.search(r'data-test="product-title"[^>]*>(.*?)</', d, re.S)
        if not (m and nev):
            continue
        t = Termek(bolt=BOLT, nev=_tiszta(nev.group(1)).capitalize()
                   if _tiszta(nev.group(1)).isupper()
                   else _tiszta(nev.group(1)), kod=ALAP + m.group(1))
        leiras = re.search(
            r'data-test="product-information-piece-description"[^>]*>(.*?)</ul>',
            d, re.S)
        if leiras:
            t.kiszereles = ", ".join(
                x for x in (_tiszta(li) for li in
                            re.findall(r"<li>(.*?)</li>", leiras.group(1), re.S))
                if x)
        erv = re.search(r'data-test="product-price-validity"[^>]*>(.*?)</div></div>',
                        d, re.S)
        if erv:
            t.ervenyes = _ervenyesseg(_tiszta(erv.group(1)))
        kedv = re.search(r'discount-info[^>]*>(.*?)</div>', d, re.S)
        if kedv:
            k = _tiszta(kedv.group(1))
            m2 = re.search(r"-\s?\d+\s?%", k)
            if m2:
                t.kedvezmeny = m2.group(0).replace(" ", "")
        for blokk in re.split(r'data-test="product-price-type"', d)[1:]:
            cimke = re.search(r'price-label"[^>]*>(.*?)</div>', blokk, re.S)
            fo = re.search(r'ws-product-price-value__main[^>]*>(.*?)</span>',
                           blokk, re.S)
            egys = re.search(r'data-test="product-price-type-label"[^>]*>(.*?)</div>',
                             blokk, re.S)
            ar = ar_szam(_tiszta(fo.group(1))) if fo else None
            cim = _tiszta(cimke.group(1)) if cimke else ""
            if ar is None:
                continue
            if "kártyával" in cim.lower() or "kartyaval" in cim.lower():
                t.kartyas_ar, t.kartya_nev = ar, "Penny Kártyával"
                if egys and not t.egysegar:
                    t.egysegar = _egysegar(_tiszta(egys.group(1)))
            elif t.ar is None:
                t.ar = ar
                if egys:
                    t.egysegar = _egysegar(_tiszta(egys.group(1)))
        regi = re.search(r'text-decoration-line-through[^>]*>(.*?)</', d, re.S)
        if regi:
            t.regi_ar = ar_szam(_tiszta(regi.group(1)))
        ki.append(t)
    return ki


def _ervenyesseg(s: str) -> str:
    """„Cs 2026.09.24-tól Sze 2026.09.30-ig” → „09.24. csütörtöktől 09.30.
    szerdáig” helyett röviden: „szeptember 24-től 30-ig” – egyszerűen
    kimondható alakban: „09.24-től 09.30-ig”."""
    datumok = re.findall(r"\d{4}\.(\d{2})\.(\d{2})", s)
    if len(datumok) >= 2:
        return "%s.%s-tól %s.%s-ig" % (datumok[0] + datumok[-1])
    if len(datumok) == 1:
        return "%s.%s-tól" % datumok[0] if "tól" in s or "től" in s \
            else "%s.%s-ig" % datumok[0]
    return s


def _egysegar(s: str) -> str:
    """„1 KG 3897 Ft” → „1 kg = 3897 Ft”."""
    m = re.match(r"(1\s*\w+)\s+(\d[\d ]*)\s*Ft", s, re.I)
    if m:
        return "%s = %s Ft" % (m.group(1).lower(), m.group(2).strip())
    return s


def letolt(get, jelez=lambda s: None) -> list:
    """Az összes heti Penny-ajánlat. `get(url) -> str` a hálózat (tesztben
    kicserélhető). Egy termék csak egyszer szerepel; a kategóriája az első
    NEM gyűjtő alkategória, ahol előfordul."""
    fo_ut = fo_kategoria(get(ALAP + "/ajanlatok"))
    if not fo_ut:
        raise RuntimeError("A Penny oldalán nem találom a heti ajánlatokat.")
    fo_html = get(ALAP + fo_ut)
    alk = alkategoriak(fo_html, fo_ut)
    rendes = [a for a in alk if not any(g in a[0] for g in _GYUJTOK)]
    gyujto = [a for a in alk if any(g in a[0] for g in _GYUJTOK)]
    ki, index = [], {}
    for ut, nev in rendes + gyujto:
        jelez("Penny: %s…" % nev)
        elso = get(ALAP + ut)
        oldalak = [elso] + [get(ALAP + ut + "?page=%d" % n)
                            for n in range(2, lapok_szama(elso) + 1)]
        for o in oldalak:
            for t in csempek(o):
                if t.kod in index:
                    continue
                t.kategoria = nev
                index[t.kod] = t
                ki.append(t)
    if not alk:                         # nincs alkategória: a fő lista lapjai
        for n in range(1, lapok_szama(fo_html) + 1):
            o = fo_html if n == 1 else get(ALAP + fo_ut + "?page=%d" % n)
            for t in csempek(o):
                if t.kod not in index:
                    index[t.kod] = t
                    ki.append(t)
    return ki
