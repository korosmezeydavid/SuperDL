# -*- coding: utf-8 -*-
"""BENU: a nyilvános akciós újság termékkártyái."""
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .termek import Termek, ar_szam

BOLT = "BENU Gyógyszertár"
ALAP = "https://benu.hu"
OLDAL = ALAP + "/collections/akcios-ujsag"


def termekek(html: str) -> list[Termek]:
    soup = BeautifulSoup(html, "html.parser")
    ki, latott = [], set()
    for card in soup.select(".product-card"):
        title = card.select_one(".product-card__title")
        link = card.select_one("a.product-card__product-link[href]")
        sale = card.select_one(".price-item--sale")
        regular = card.select_one(".price-item--regular")
        if not (title and link and sale and regular):
            continue
        nev = title.get_text(" ", strip=True)
        ar = ar_szam(sale.get_text(" ", strip=True))
        regi = ar_szam(regular.get_text(" ", strip=True))
        url = urljoin(ALAP, link["href"])
        if urlsplit(url).hostname != "benu.hu":
            continue
        if not nev or not ar or not regi or regi <= ar or url in latott:
            continue
        latott.add(url)
        ki.append(Termek(bolt=BOLT, nev=nev, ar=ar, regi_ar=regi,
                         kedvezmeny="-%d%%" % round((regi - ar) * 100 / regi),
                         kategoria="Akciós újság", kod=url, url=url,
                         megjegyzes="A gyógyszertári és online ár eltérhet."))
    return ki


def letolt(get, jelez=lambda s: None) -> list[Termek]:
    ki, latott = [], set()
    # Az újság több lapos; felső korlát védi a boltot és a felhasználót.
    for page in range(1, 11):
        jelez("BENU: akciós újság, %d. oldal…" % page)
        try:
            html = get(OLDAL + ("?page=%d" % page if page > 1 else ""))
        except Exception:  # noqa: BLE001 – a korábbi lapok ajánlatai használhatók
            if not ki:
                raise
            break
        uj = [t for t in termekek(html) if t.url not in latott]
        if not uj:
            break
        ki.extend(uj)
        latott.update(t.url for t in uj)
    return ki
