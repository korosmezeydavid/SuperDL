# -*- coding: utf-8 -*-
"""LETÖLTÉSI ELŐZMÉNYEK és duplikátum-figyelmeztetés (letöltő-motor MK10).

**A lemez-ellenőrzés eredménye: NULLÁRÓL épül.** A terv úgy fogalmazott, hogy
az „automatikus rendezés (`organizer.py` megvan)" — az `organizer.py` viszont a
**naptár, teendők és jegyzetek** kezelője, semmi köze a letöltött fájlokhoz.
Előzmény pedig sehol nem volt a programban: a sorból kikerült elem nyomtalanul
eltűnt.

**Miért ez a legfontosabb az MK10-ből.** Vakon a legdrágább hiba az, ha valamit
MÁSODSZOR töltesz le: nem látszik a mappában, hogy már ott van, a fájlnév
ütközése pedig csak a letöltés VÉGÉN derül ki — addigra elment a sávszélesség
és az idő. Egy előzmény ezt egyetlen kérdéssel megelőzi.

A modul SZÁNDÉKOSAN nem tud a wx-ről: listát és mondatot ad, felület nélkül is
tesztelhető.
"""
from __future__ import annotations

import time
from pathlib import Path

from . import store

FAJL = store.CONFIG_DIR / "elozmenyek.json"

# Meddig tartjuk meg. Nem méret-, hanem IDŐ-alapú korlát: a felhasználót az
# érdekli, hogy „nemrég letöltöttem-e", nem az, hogy hányadik volt a sorban.
MEGORZES_NAP = 365

# Ennyi bejegyzésnél többet semmiképp nem tartunk (a fájl ne hízzon el).
MAX_TETEL = 5000


def betolt() -> list:
    """A mentett előzmények, legfrissebb elöl."""
    adat = store.load_json(FAJL, [])
    return adat if isinstance(adat, list) else []


def ment(tetelek) -> None:
    store.save_json(FAJL, list(tetelek)[:MAX_TETEL])


def _kulcs(url: str) -> str:
    return (url or "").strip().lower()


def rogzit(url: str, nev: str = "", meret: int = 0, mappa: str = "",
           mikor: float = None, tetelek=None) -> list:
    """Egy elkészült letöltés felvétele az előzményekbe.

    Ha ugyanaz az URL már szerepel, NEM duplikálunk: a meglévő bejegyzést
    frissítjük és előre hozzuk. Így az előzmény a „mikor töltöttem le utoljára"
    kérdésre válaszol, nem arra, hogy hányszor."""
    lista = list(betolt() if tetelek is None else tetelek)
    k = _kulcs(url)
    lista = [t for t in lista if _kulcs(t.get("url", "")) != k]
    lista.insert(0, {
        "url": (url or "").strip(),
        "nev": (nev or "").strip(),
        "meret": int(meret or 0),
        "mappa": (mappa or "").strip(),
        "mikor": float(mikor if mikor is not None else time.time()),
    })
    return lista[:MAX_TETEL]


def keres(szo: str, tetelek=None) -> list:
    """Keresés névben és URL-ben, kis/nagybetűtől függetlenül.

    Üres keresőszóra MINDENT ad vissza — a „mi van az előzményben" kérdés
    ugyanolyan jogos, mint a célzott keresés."""
    lista = betolt() if tetelek is None else list(tetelek)
    sz = (szo or "").strip().lower()
    if not sz:
        return lista
    return [t for t in lista
            if sz in str(t.get("nev", "")).lower()
            or sz in str(t.get("url", "")).lower()]


def takarit(tetelek=None, most: float = None) -> list:
    """A `MEGORZES_NAP`-nál régebbi bejegyzések elhagyása."""
    lista = betolt() if tetelek is None else list(tetelek)
    hatar = (most if most is not None else time.time()) - MEGORZES_NAP * 86400
    return [t for t in lista if float(t.get("mikor", 0)) >= hatar]


# ---- duplikátum-figyelmeztetés ----------------------------------------

def mar_letoltve(url: str, tetelek=None) -> dict | None:
    """A korábbi letöltés bejegyzése, vagy None.

    **Csak akkor jelez, ha a FÁJL IS megvan.** Ha a felhasználó azóta
    kitörölte, nincs mit duplikálni — és egy kérdés arról, hogy „ezt már
    letöltötted", miközben a fájl sehol, egyenesen bosszantó volna."""
    k = _kulcs(url)
    if not k:
        return None
    for t in (betolt() if tetelek is None else tetelek):
        if _kulcs(t.get("url", "")) != k:
            continue
        ut = _teljes_ut(t)
        if ut is None or ut.exists():
            return t
        return None
    return None


def _teljes_ut(tetel) -> Path | None:
    mappa = str(tetel.get("mappa") or "").strip()
    nev = str(tetel.get("nev") or "").strip()
    if not mappa or not nev:
        return None            # nem tudjuk ellenőrizni → ne találgassunk
    try:
        return Path(mappa) / nev
    except (OSError, ValueError):
        return None


def duplikatum_kerdes(tetel) -> str:
    """A kérdés szövege. Kimondja, MIKOR és HOVA került — ebből tudja a
    felhasználó eldönteni, tényleg ugyanaz-e."""
    from . import report
    nev = str(tetel.get("nev") or tetel.get("url") or "ez a fájl").strip()
    mikor = float(tetel.get("mikor") or 0)
    reszek = [f"Ezt már letöltötted: {nev}"]
    if mikor:
        reszek.append(time.strftime("%Y. %m. %d.", time.localtime(mikor)))
    meret = int(tetel.get("meret") or 0)
    if meret:
        reszek.append(report.mondott_meret(meret))
    mappa = str(tetel.get("mappa") or "").strip()
    if mappa:
        reszek.append(f"ide: {mappa}")
    return (", ".join(reszek) + ".\n\nA fájl most is megvan. "
            "Letöltsem MÉGIS újra?")
