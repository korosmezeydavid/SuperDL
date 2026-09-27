# -*- coding: utf-8 -*-
"""Pepco – a heti „Újságaink" gyűjtemény (pepco.hu, a bolt saját oldala).

Nem lapozós kép: a pepco.hu Shopify-áruház „Újságaink" gyűjteménye HTML-
lista, minden termék egy hivatkozás, aminek az akadálymentes címkéje
(aria-label) így néz ki:

    <a href="/products/halloween-plussfigura-637271" …
       aria-label="halloween plüssfigura - 1800.0 Ft">

Ugyanezt a szöveget olvassa fel a képernyőolvasó a bolt oldalán is. Az
újság csütörtökönként cserélődik.
"""
import html
import re

from .termek import Termek

BOLT = "Pepco"
ALAP = "https://pepco.hu"
OLDAL = ALAP + "/gyujtemeny/ujsagaink/"

_TERMEK = re.compile(
    r'<a href="(/products/[^"?#]+)"[^>]*?aria-label="([^"]+?) - '
    r'(\d+(?:\.\d+)?) Ft"')
_LEIRAS = re.compile(r'aria-label="Product description: ([^"]*)"')


def _szep(s: str) -> str:
    s = html.unescape(s or "").strip()
    return s[:1].upper() + s[1:]


def termekek(oldal_html: str) -> list:
    ki, latott = [], set()
    for m in _TERMEK.finditer(oldal_html or ""):
        ut, nev, ar = m.group(1), m.group(2), m.group(3)
        if ut in latott:
            continue
        latott.add(ut)
        # a termék rövid leírása (pl. „tökkel és macskával") közvetlenül
        # a kártyán belül, a következő termék előtt
        veg = oldal_html.find('<a href="/products/', m.end())
        resz = oldal_html[m.end(): veg if veg > 0 else m.end() + 4000]
        le = _LEIRAS.search(resz)
        try:
            forint = int(round(float(ar)))
        except ValueError:
            continue
        ki.append(Termek(
            bolt=BOLT, nev=_szep(nev), ar=forint, kategoria="Heti újság",
            megjegyzes=_szep(le.group(1)) if le else "",
            kod=ut, url=ALAP + ut))
    return ki


def letolt(get, jelez=lambda s: None) -> list:
    jelez("Pepco: a heti újság letöltése…")
    return termekek(get(OLDAL))
