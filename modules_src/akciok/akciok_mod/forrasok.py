# -*- coding: utf-8 -*-
"""A boltok listája, a letöltés és a helyi gyorsítótár.

Új bolt = egy új modul (`penny.py` mintájára) + egy sor a BOLTOK-ban.

A gyorsítótár (~/.superdl/akciok/<bolt>.json) azért kell, hogy a lista
AZONNAL megnyíljon, és net nélkül is böngészhető legyen – a friss adat a
háttérben jön. Ez a felhasználó saját gépén marad, sehová nem kerül tovább.
"""
import json
import time
from pathlib import Path

from . import aldi, dm, lidl, penny, rossmann, spar, tesco
from .termek import Termek

MAPPA = Path.home() / ".superdl" / "akciok"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36 SuperDL")
FRISS_ORA = 6                    # ennél frissebb adatot nem töltünk újra

# (azonosító, megjelenő név, letöltő, milyen get kell neki)
BOLTOK = [
    ("penny", "Penny", lambda get, gb, j: penny.letolt(get, j)),
    ("lidl", "Lidl", lambda get, gb, j: lidl.letolt(gb, j)),
    ("aldi", "Aldi", lambda get, gb, j: aldi.letolt(gb, j)),
    ("tesco", "Tesco", lambda get, gb, j: tesco.letolt(get, gb, j)),
    ("spar", "Spar és Interspar", lambda get, gb, j: spar.letolt(get, gb, j)),
    ("rossmann", "Rossmann", lambda get, gb, j: rossmann.letolt(_post_json, j)),
    ("dm", "dm", lambda get, gb, j: dm.letolt(_get_json, j)),
]


def _get_json(url: str, fejlec: dict | None = None) -> dict:
    try:
        from curl_cffi import requests as cr
        r = cr.get(url, headers=fejlec or {}, impersonate="chrome", timeout=60)
    except ImportError:
        import requests
        r = requests.get(url, headers={"User-Agent": UA, **(fejlec or {})},
                         timeout=60)
    r.raise_for_status()
    return r.json()


def _post_json(url: str, adat: dict, fejlec: dict | None = None) -> dict:
    """JSON-kérés (GraphQL) böngészőként; ugyanaz a tartalék, mint a get-nél."""
    fej = {"Content-Type": "application/json", **(fejlec or {})}
    try:
        from curl_cffi import requests as cr
        r = cr.post(url, json=adat, headers=fej, impersonate="chrome", timeout=60)
    except ImportError:
        import requests
        r = requests.post(url, json=adat, headers={"User-Agent": UA, **fej},
                          timeout=60)
    r.raise_for_status()
    return r.json()


def _get_bytes(url: str) -> bytes:
    """Böngészőként kérünk (curl_cffi), mert több bolt oldala a sima
    Python-kérést elutasítja; ha a curl_cffi nincs meg, a sima requests."""
    try:
        from curl_cffi import requests as cr
        r = cr.get(url, impersonate="chrome", timeout=90)
        r.raise_for_status()
        return r.content
    except ImportError:
        pass
    import requests                         # a Core-ból
    r = requests.get(url, headers={"User-Agent": UA,
                                   "Accept-Language": "hu-HU,hu;q=0.9"},
                     timeout=90)
    r.raise_for_status()
    return r.content


def _get(url: str) -> str:
    return _get_bytes(url).decode("utf-8", "replace")


def _fajl(bolt_id: str) -> Path:
    return MAPPA / ("%s.json" % bolt_id)


def mentett(bolt_id: str) -> tuple:
    """(termékek, letöltés ideje epoch-ban vagy 0)."""
    try:
        d = json.loads(_fajl(bolt_id).read_text(encoding="utf-8"))
        return ([Termek.szotarbol(x) for x in d.get("termekek", [])],
                float(d.get("ido", 0)))
    except (OSError, ValueError, TypeError):
        return [], 0.0


def _ment(bolt_id: str, termekek: list) -> None:
    MAPPA.mkdir(parents=True, exist_ok=True)
    tmp = _fajl(bolt_id).with_suffix(".tmp")
    tmp.write_text(json.dumps({"ido": time.time(),
                               "termekek": [t.szotar() for t in termekek]},
                              ensure_ascii=False), encoding="utf-8")
    tmp.replace(_fajl(bolt_id))


def friss_e(ido: float) -> bool:
    return ido > 0 and time.time() - ido < FRISS_ORA * 3600


def letolt(bolt_id: str, jelez=lambda s: None, get=None, get_bytes=None) -> list:
    """Letölti és elmenti. ⚠️ Üres eredmény NEM írja felül a korábbi jó
    adatot (a TV-műsor 2026-09-21-i tanulsága: egy hiányos forrás egyszer
    már felülírta a jót)."""
    for azon, _nev, fv in BOLTOK:
        if azon == bolt_id:
            termekek = fv(get or _get, get_bytes or _get_bytes, jelez)
            if termekek:
                _ment(bolt_id, termekek)
            return termekek
    raise KeyError(bolt_id)


def bolt_nev(bolt_id: str) -> str:
    return next((n for a, n, _ in BOLTOK if a == bolt_id), bolt_id)
