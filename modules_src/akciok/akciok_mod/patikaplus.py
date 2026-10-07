# -*- coding: utf-8 -*-
"""PatikaPlus: a patikában megvásárolható havi ajánlatok."""
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .termek import Termek, ar_szam

BOLT = "PatikaPlus"
ALAP = "https://patikaplus.hu"
OLDAL = ALAP + "/patika"


def termekek(html: str) -> list[Termek]:
    soup = BeautifulSoup(html, "html.parser")
    ki, latott = [], set()
    for card in soup.select("#patika_row .termek-item"):
        title = card.select_one(".text-center b")
        link = card.select_one('a[href^="/patika/"]')
        old = card.select_one("del")
        if not (title and link and old):
            continue
        # A kártyán az első árcímke a tényleges kedvezményes ár.
        price = card.select_one(".text-start b")
        if not price:
            continue
        nev = title.get_text(" ", strip=True)
        ar = ar_szam(price.get_text(" ", strip=True))
        regi = ar_szam(old.get_text(" ", strip=True))
        url = urljoin(ALAP, link["href"])
        if urlsplit(url).hostname != "patikaplus.hu":
            continue
        if not nev or not ar or not regi or regi <= ar or url in latott:
            continue
        latott.add(url)
        ki.append(Termek(bolt=BOLT, nev=nev, ar=ar, regi_ar=regi,
                         kedvezmeny="-%d%%" % round((regi - ar) * 100 / regi),
                         kategoria="Havi patikai ajánlat", kod=url, url=url,
                         megjegyzes="Az ár és a készlet patikánként eltérhet."))
    return ki


def letolt(get, jelez=lambda s: None) -> list[Termek]:
    jelez("PatikaPlus: havi patikai ajánlatok…")
    return termekek(get(OLDAL))
