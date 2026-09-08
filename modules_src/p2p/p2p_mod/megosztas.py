# -*- coding: utf-8 -*-
"""Megosztási előzmények (2026-09-06).

Az androidos `share/ShareHistory.kt` windowsos testvére, azonos viselkedéssel.

**Miért kell egyáltalán.** Egy feltöltött link élettartama véges. Aki tegnap
küldött egy linket, és ma nem érti, miért nem működik, annak valahol meg kell
kapnia a választ. Enélkül a program némán hagyná magára.

⚠️ **Külön a letöltés-előzményektől** (`superdl/elozmenyek.py`): az más adat,
más élettartammal és más jelentéssel. Egy közös fájlban a kettő
összekeveredne, és a „töröld az előzményeimet" kérés kétértelmű lenne.

⚠️ **A saját gépünkön tároljuk, nem a megosztotton.** Az, hogy ki mit kinek
küldött, magánadat.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

FAJL = Path.home() / ".superdl" / "megosztas_elozmenyek.json"

# A lejárt sorok ENNYI ideig még látszanak. Nem díszítés: aki tegnap küldött
# egy linket, és ma nem érti, miért nem működik, ITT kapja meg a választ.
# Némán eltüntetve nem lenne felelet a kérdésére.
LEJART_LATSZIK_NAP = 1

MAX_TETEL = 500


def _most() -> float:
    return time.time()


def betolt() -> list[dict]:
    try:
        adat = json.loads(FAJL.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return adat if isinstance(adat, list) else []


def ment(tetelek: list[dict]) -> bool:
    try:
        FAJL.parent.mkdir(parents=True, exist_ok=True)
        FAJL.write_text(json.dumps(tetelek[:MAX_TETEL], ensure_ascii=False,
                                   indent=2), encoding="utf-8")
        return True
    except OSError:
        return False


def rogzit(nev: str, link: str, tarhely_id: str, tarhely_nev: str,
           meret: int, nap: int, egyszeri: bool = False,
           torolheto: bool = False, torlo_kulcs: str = "") -> dict:
    """Új sor az előzményekbe. A lejárat IDŐPONTKÉNT tárolódik, nem
    időtartamként — különben minden induláskor újraszámolódna."""
    tetel = {
        "nev": nev, "link": link,
        "tarhely": tarhely_id, "tarhely_nev": tarhely_nev,
        "meret": int(meret), "kuldve": _most(),
        "lejar": _most() + nap * 86400,
        "egyszeri": bool(egyszeri), "torolheto": bool(torolheto),
        "torlo_kulcs": torlo_kulcs,
    }
    tetelek = betolt()
    tetelek.insert(0, tetel)
    ment(tetelek)
    return tetel


def lathatoak(tetelek=None, most: float = None) -> list[dict]:
    """A megjelenítendő sorok, LEJÁRAT SZERINT rendezve — elöl, ami hamarabb
    tűnik el. A rendezés nem esztétika: vakon a lista sorrendje az egyetlen
    térkép, és a sürgős tétel legyen elöl."""
    most = _most() if most is None else most
    tetelek = betolt() if tetelek is None else tetelek
    hatar = most - LEJART_LATSZIK_NAP * 86400
    elo = [t for t in tetelek if float(t.get("lejar", 0)) > hatar]
    elo.sort(key=lambda t: float(t.get("lejar", 0)))
    return elo


def takarit(most: float = None) -> int:
    """A régen lejárt sorok eltakarítása. Visszaadja, hányat vett ki."""
    tetelek = betolt()
    maradok = lathatoak(tetelek, most)
    ment(maradok)
    return len(tetelek) - len(maradok)


def hatralevo_ido(tetel: dict, most: float = None) -> str:
    """EMBERI idő, nem időbélyeg. „még két nap és négy óra" — a
    `2026-09-08 14:12` kimondva használhatatlan.

    ⚠️ **Lefelé kerekítünk, nem a legközelebbihez.** Egy lejárat-visszaszámlálónál
    a két irány nem egyenrangú: ha többet mondanánk a valóságnál, a felhasználó
    azt hinné, van még ideje – és pont akkor veszítené el a linket, amikor
    számít rá. Kevesebbet mondani legfeljebb kellemes meglepetés."""
    most = _most() if most is None else most
    hatra = float(tetel.get("lejar", 0)) - most
    if hatra <= 0:
        return "LEJÁRT"
    nap = int(hatra // 86400)
    ora = int((hatra % 86400) // 3600)
    perc = int((hatra % 3600) // 60)
    if nap:
        return f"még {nap} nap és {ora} óra" if ora else f"még {nap} nap"
    if ora:
        return f"még {ora} óra és {perc} perc" if perc else f"még {ora} óra"
    return f"még {perc} perc" if perc else "kevesebb, mint egy perc"


def sor_szoveg(tetel: dict, most: float = None) -> str:
    """Egy előzmény-sor felolvasható alakja."""
    reszek = [str(tetel.get("nev") or "névtelen"),
              str(tetel.get("tarhely_nev") or ""),
              hatralevo_ido(tetel, most)]
    if tetel.get("egyszeri"):
        reszek.append("csak egyszer tölthető le")
    return " – ".join(r for r in reszek if r)


def sor_torles_mondat(tetel: dict) -> str:
    """⚠️ Amit a „sor törlése" UTÁN mondunk.

    A sor kivétele a nyilvántartásból NEM törli a fájlt a tárhelyről. Ha ezt
    elhallgatnánk, a felhasználó azt hinné, visszavonta a megosztást — az pedig
    hamis biztonságérzet, ugyanaz a hiba, mint egy gyenge titkosítás."""
    if tetel.get("torolheto"):
        return ("Kivettem a nyilvántartásomból. A fájl a tárhelyen MARAD – ha "
                "onnan is törölni akarod, használd a „Törlés a tárhelyről” "
                "műveletet.")
    return ("Kivettem a nyilvántartásomból. A fájl a tárhelyen MARAD a "
            "lejáratáig – ez a szolgáltató döntése, nem tudom visszavonni.")


def betuzve(link: str) -> str:
    """A link betűzve – a fő út a vágólap, de ha valakinek telefonba kell
    bemondania, ez az egyetlen megbízható mód."""
    nevek = {".": "pont", "/": "per jel", ":": "kettőspont", "-": "kötőjel",
             "_": "alulvonás", "?": "kérdőjel", "=": "egyenlőségjel",
             "&": "és jel", "#": "kettőskereszt", "~": "hullámvonal",
             "+": "pluszjel", "%": "százalékjel"}
    return ", ".join(nevek.get(k, k) for k in (link or ""))
