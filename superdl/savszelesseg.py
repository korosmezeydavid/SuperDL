# -*- coding: utf-8 -*-
"""IDŐSÁVOS SEBESSÉGKORLÁT (letöltő-motor MK9).

**Miért ez az MK9-ből, és miért NEM a munkalopás.** Az MK9 három tételt sorol:
munkalopás, adaptív szálszám, sávszélesség-ütemezés. A munkalopás a
`segment.py` szegmens-listáját írná át futás közben — ugyanazt a listát, amit
az `.sdlstate` ment, és amiből a folytatás dolgozik. Egy hiba ott nem
összeomlás, hanem **csendben sérült fájl**, ami csak hetekkel később derül ki.
Egy nagy, élesben még nem mért csomag előtt ez rossz csere: a nyereség
sebesség, a kockázat adatvesztés.

Az ütemezés viszont olcsó és valódi hasznot ad: **a letöltés éjjel mehet
korlátlanul, nappal pedig ne egye meg a vonalat.** Vakon ez különösen fontos,
mert a lassú net nem látszik — csak az, hogy minden más akadozik.

A modul SZÁNDÉKOSAN nem tud a letöltőkről: időpontból számot ad, tehát óra és
hálózat nélkül tesztelhető.
"""
from __future__ import annotations

import re
import time

# „22:00-06:00=0; 06:00-22:00=500K" alakú szabályok. A `0` = korlátlan
# (ugyanaz a jelentés, mint a beállítás üres mezőjében).
_SZABALY = re.compile(
    r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*=\s*(\S+)\s*$")


def _percben(ora: int, perc: int) -> int:
    return (int(ora) % 24) * 60 + (int(perc) % 60)


def elemez(szoveg: str) -> list:
    """Szövegből szabálylista: [(kezdet_perc, veg_perc, korlat_szoveg), …].

    A hibás sorokat CSENDBEN kihagyjuk – egy elgépelt szabály miatt nem
    állhat meg a letöltés, és nem is szabad hibaüzenettel riogatni valakit
    egy beállítás miatt."""
    ki = []
    for darab in re.split(r"[;\n]", szoveg or ""):
        if not darab.strip():
            continue
        m = _SZABALY.match(darab)
        if not m:
            continue
        o1, p1, o2, p2, korlat = m.groups()
        ki.append((_percben(int(o1), int(p1)),
                   _percben(int(o2), int(p2)), korlat))
    return ki


def _benne_van(most_perc: int, kezd: int, veg: int) -> bool:
    """Beleesik-e az időpont a sávba.

    ⚠️ **Az ÉJFÉLEN ÁTNYÚLÓ sáv a lényeg, és a leggyakoribb elrontás.**
    A „22:00-06:00" nem üres tartomány, hanem az éjszaka — épp az, amit a
    felhasználó be akar állítani. Ha a naiv `kezd <= x < veg` maradna, a
    legfontosabb szabály sosem sülne el."""
    if kezd == veg:
        return True                      # egész napos szabály
    if kezd < veg:
        return kezd <= most_perc < veg
    return most_perc >= kezd or most_perc < veg


def korlat_most(szoveg: str, most=None) -> str | None:
    """A MOST érvényes korlát szövege, vagy None, ha nincs szabály.

    Több illeszkedő szabály esetén az ELSŐ nyer: a felhasználó fentről lefelé
    olvassa, és azt várja, hogy a korábbi az erősebb."""
    szabalyok = elemez(szoveg)
    if not szabalyok:
        return None
    t = time.localtime(most) if most is not None else time.localtime()
    perc = _percben(t.tm_hour, t.tm_min)
    for kezd, veg, korlat in szabalyok:
        if _benne_van(perc, kezd, veg):
            return korlat
    return None


def emberi(korlat: str) -> str:
    """A korlát felolvasható alakja. A `0` és az üres KORLÁTLANT jelent —
    ugyanaz, mint a beállítás üres mezőjében, hogy ne legyen kétféle nyelv."""
    k = (korlat or "").strip()
    if not k or k in ("0", "0K", "0M"):
        return "korlátlan"
    return k


def valtas_mondat(korlat: str) -> str:
    """Amit a felhasználó HALL, ha az ütemezés átvált.

    Ki KELL mondani: a lassabb letöltés magától nem érthető, és a felhasználó
    azt hinné, elromlott valami vagy gyenge a net."""
    return (f"Az időzített sebességkorlát átváltott: {emberi(korlat)}.")
