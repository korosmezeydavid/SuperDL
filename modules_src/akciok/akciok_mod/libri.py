# -*- coding: utf-8 -*-
"""Libri – a Könyvutca akciós könyvei (libri.hu, a bolt saját oldala).

A lista lapozható (`/konyvutca?page=N`, oldalanként kb. 20 könyv). Minden
könyv egy `product-grid-item` doboz, a bolt a saját adatait adatmezőkben
adja:

    data-url="https://www.libri.hu/konyv/…html" data-name="Cím"
    data-category="eletmod-egeszseg/…" data-price="2793"

a borító ár pedig a dobozban: „Borító ár: 3 990 Ft". ⚠️ Az oldal
ISO-8859-2 kódolású (nem UTF-8) – ha UTF-8-nak olvasnánk, minden ékezet
elveszne.
"""
import html
import re
import time

from .termek import Termek, ar_szam

BOLT = "Libri"
ALAP = "https://www.libri.hu"
OLDAL = ALAP + "/konyvutca"
MAX_LAP = 60                 # ~1000 könyv; a bolt jelenleg 51 oldalt ad
SZUNET_MP = 0.6              # kíméletesen: két oldal között pihenő

_DOBOZ = re.compile(r'<div class="product-grid-item[^"]*"([^>]*)>')
_ADAT = re.compile(r'data-([a-z-]+)="([^"]*)"')
_SZERZO = re.compile(r'class="authors"[^>]*>([^<]+)</a>')
_BORITO = re.compile(r'Borító ár:</span>\s*<span>([^<]+)</span>')
_KATEG = re.compile(r'<a href="/konyv/([a-z0-9-]+)/" title="([^"]+)">')
_LAPOK = re.compile(r'[?&]page=(\d+)')
_CHARSET = re.compile(rb'charset=["\']?([\w-]+)', re.I)


def dekod(b: bytes) -> str:
    m = _CHARSET.search(b[:4000] or b"")
    kod = m.group(1).decode("ascii", "ignore") if m else "utf-8"
    try:
        return b.decode(kod, "replace")
    except LookupError:
        return b.decode("utf-8", "replace")


def kategoriak(oldal: str) -> dict:
    """slug → olvasható név, a bolt saját menüjéből."""
    return {slug: html.unescape(nev) for slug, nev in _KATEG.findall(oldal)}


def lapok_szama(oldal: str) -> int:
    szamok = [int(x) for x in _LAPOK.findall(oldal)]
    return max(szamok) if szamok else 1


def termekek(oldal: str, katok: dict | None = None) -> list:
    katok = katok or {}
    ki, latott = [], set()
    dobozok = list(_DOBOZ.finditer(oldal or ""))
    for n, m in enumerate(dobozok):
        adat = {k: html.unescape(v) for k, v in _ADAT.findall(m.group(1))}
        azon = adat.get("doc-id") or adat.get("url")
        if not azon or azon in latott or not adat.get("name"):
            continue
        latott.add(azon)
        veg = dobozok[n + 1].start() if n + 1 < len(dobozok) else m.end() + 6000
        resz = oldal[m.end():veg]
        szerzo = _SZERZO.search(resz)
        borito = _BORITO.search(resz)
        ar = ar_szam(adat.get("price", ""))
        regi = ar_szam(borito.group(1)) if borito else None
        slug = (adat.get("category") or "").split("/")[0]
        nev = adat["name"].strip()
        if szerzo:
            nev = "%s: %s" % (html.unescape(szerzo.group(1)).strip(), nev)
        t = Termek(bolt=BOLT, nev=nev, ar=ar, regi_ar=regi,
                   kategoria=katok.get(slug, "Könyv"), kod=str(azon),
                   url=adat.get("url", ""), csoport="Könyv")
        if ar and regi and regi > ar:
            t.kedvezmeny = "-%d%%" % round(100 * (regi - ar) / regi)
        if "Csak online" in resz:
            t.megjegyzes = "Csak online rendelhető"
        ki.append(t)
    return ki


def letolt(get_bytes, jelez=lambda s: None, szunet=SZUNET_MP) -> list:
    jelez("Libri: a Könyvutca első oldala…")
    elso = dekod(get_bytes(OLDAL))
    katok = kategoriak(elso)
    ki = termekek(elso, katok)
    latott = {t.kod for t in ki}
    osszes = min(lapok_szama(elso), MAX_LAP)
    for lap in range(2, osszes + 1):
        time.sleep(szunet)
        if lap % 10 == 0:
            jelez("Libri: %d. oldal a %d-ből…" % (lap, osszes))
        try:
            uj = termekek(dekod(get_bytes("%s?page=%d" % (OLDAL, lap))), katok)
        except Exception:
            break                   # ami eddig jött, az megmarad
        uj = [t for t in uj if t.kod not in latott]
        if not uj:
            break
        latott.update(t.kod for t in uj)
        ki.extend(uj)
    return ki
