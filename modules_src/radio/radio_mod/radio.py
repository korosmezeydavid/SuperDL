"""Internetes rádió a nyílt, ingyenes radio-browser.info API-val.

Keresés név, címke vagy ország szerint, és a legnépszerűbb állomások. A
találatok stream-URL-jét a streaming hangmotor (audioengine) játssza le.
"""

import json
import urllib.request
from dataclasses import dataclass
from urllib.parse import quote

SERVERS = ["de1.api.radio-browser.info", "nl1.api.radio-browser.info",
           "at1.api.radio-browser.info", "fi1.api.radio-browser.info"]


@dataclass
class Station:
    name: str
    url: str
    codec: str = ""
    bitrate: int = 0
    country: str = ""
    tags: str = ""
    uuid: str = ""

    def quality(self) -> str:
        parts = []
        if self.codec:
            parts.append(self.codec)
        if self.bitrate:
            parts.append(f"{self.bitrate} kbps")
        return " ".join(parts)


def _api(path: str):
    last = None
    for s in SERVERS:
        try:
            req = urllib.request.Request(
                f"https://{s}{path}", headers={"User-Agent": "SuperDL/2.0"})
            return json.load(urllib.request.urlopen(req, timeout=15))
        except Exception as e:
            last = e
    raise last or RuntimeError("nincs elérhető rádió-szerver")


def _to_stations(data) -> list[Station]:
    out = []
    for s in data:
        url = s.get("url_resolved") or s.get("url")
        if not url:
            continue
        out.append(Station(
            name=(s.get("name") or "").strip() or "(név nélkül)",
            url=url, codec=s.get("codec", "") or "",
            bitrate=int(s.get("bitrate") or 0),
            country=s.get("country", "") or s.get("countrycode", "") or "",
            tags=s.get("tags", "") or "",
            uuid=s.get("stationuuid", "") or ""))
    return out


def search(query: str, by: str = "name", limit: int = 50) -> list[Station]:
    q = quote(query.strip())
    base = ("/json/stations/search?hidebroken=true&order=clickcount"
            f"&reverse=true&limit={limit}")
    if by == "tag":
        base += "&tagList=" + q
    elif by == "country":
        base += "&country=" + q
    else:
        base += "&name=" + q
    return _to_stations(_api(base))


def top(limit: int = 50) -> list[Station]:
    return _to_stations(_api(f"/json/stations/topclick/{limit}"))


@dataclass
class Country:
    name: str
    code: str                          # ISO 3166-1 (pl. „HU")
    count: int = 0                     # állomások száma


def countries(min_count: int = 3) -> list[Country]:
    """Az országok listája (a radio-browser /json/countries-ből), névsorban.
    Csak azokat hozza, ahol van érdemi számú állomás."""
    out: list[Country] = []
    for c in _api("/json/countries"):
        name = (c.get("name") or "").strip()
        code = (c.get("iso_3166_1") or "").strip().upper()
        cnt = int(c.get("stationcount") or 0)
        if name and code and cnt >= min_count:
            out.append(Country(name=name, code=code, count=cnt))
    out.sort(key=lambda x: x.name.lower())
    return out


def by_country_code(code: str, limit: int = 50) -> list[Station]:
    """Egy ország legnépszerűbb állomásai az ISO-kód PONTOS egyezésével.
    (A korábbi név szerinti `country=` keresés azért nem talált, mert pontos
    angol országnevet várt; az ISO-kód megbízható.)"""
    path = (f"/json/stations/bycountrycodeexact/{quote(code.strip().upper())}"
            f"?hidebroken=true&order=clickcount&reverse=true&limit={limit}")
    return _to_stations(_api(path))
