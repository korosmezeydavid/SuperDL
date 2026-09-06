# -*- coding: utf-8 -*-
"""A célmappa érvényessége (Barbi hibajelentése, 2026-09-05).

**Mi történt.** A főablak célmappa-mezőjébe egyetlen „t" betű került, és a
letöltések egy `t` nevű mappába mentek a program indítási könyvtára alatt.
A felhasználó nem tudta, hová tűntek a fájljai.

**Miért történhetett meg.** Semmi nem ellenőrizte az útvonalat: sem azt, hogy
üres-e, sem azt, hogy ABSZOLÚT-e. A relatív `t` a munkakönyvtárhoz képest
értendő — a program szó nélkül létrehozta és odatöltött.

**Miért külön modul.** Ugyanaz az ellenőrzés kell a felületnek (mielőtt
elfogadja a beírt értéket), az induló betöltésnek (a mentett érték is lehet
hibás) és a letöltés indításának. Három helyen külön megírva előbb-utóbb
elcsúsznának — és pont az egyik maradna ki.

⚠️ **A modul SZÁNDÉKOSAN nem tud a wx-ről**: tiszta függvények, amik valódi
felület nélkül is ellenőrizhetők.
"""

import os
from pathlib import Path


def alapertelmezett() -> str:
    """A tartalék célmappa: a felhasználó Letöltések mappája.

    Ha az bármiért nem elérhető, a felhasználói mappa maga — az mindig létezik,
    és a felhasználó biztosan megtalálja. Sosem adunk vissza relatív útvonalat."""
    try:
        le = Path.home() / "Downloads"
        if le.is_dir():
            return str(le)
        return str(Path.home())
    except Exception:
        return os.getcwd()


def ervenyes(ut) -> tuple[bool, str]:
    """(rendben_van, miért_nem). A hibaszöveg a FELHASZNÁLÓNAK szól.

    Három ok, és mindhárom más teendőt kíván:

    1. **üres** – nincs hova tölteni;
    2. **nem abszolút** – EZ okozta Barbi hibáját. A relatív útvonal nem
       „majdnem jó": a program munkakönyvtárához képest értendő, ami a
       felhasználó számára láthatatlan hely;
    3. **nem hozható létre** – nincs jogosultság, vagy leválasztott meghajtó.

    ⚠️ A NEM LÉTEZŐ mappa önmagában NEM hiba: a letöltő eddig is létrehozta, és
    egy új, még üres célmappa teljesen jogos kérés. Csak azt nézzük, hogy
    LÉTRE LEHET-E hozni."""
    szoveg = str(ut or "").strip()
    if not szoveg:
        return False, "A célmappa üres."
    p = Path(szoveg)
    if not p.is_absolute():
        return False, (f"A célmappa nem teljes útvonal: {szoveg}. "
                       "Így a letöltések a program mappájába kerülnének, ahol "
                       "nem találnád meg őket. Teljes útvonal kell, "
                       "meghajtóbetűvel.")
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return False, (f"A célmappa nem hozható létre: {szoveg}. "
                       f"A rendszer üzenete: {e.strerror or e}.")
    if not p.is_dir():
        return False, f"A célmappa nem mappa: {szoveg}."
    return True, ""


def ellenoriz(ut, tartalek: str = "") -> tuple[str, str]:
    """(használandó_útvonal, kimondandó_üzenet).

    Ha az útvonal jó, az üzenet üres. Ha nem, visszaesünk a tartalékra (vagy az
    alapértelmezettre), és **megmondjuk, miért** — ez a lényeg. Barbinál épp az
    hiányzott, hogy bármi is szóljon: a program csendben elfogadta a rosszat."""
    jo, hiba = ervenyes(ut)
    if jo:
        return str(ut).strip(), ""
    vissza = str(tartalek or "").strip()
    if vissza:
        jo2, _ = ervenyes(vissza)
        if not jo2:
            vissza = ""
    if not vissza:
        vissza = alapertelmezett()
    return vissza, f"{hiba} Maradok ennél: {vissza}."


def valtozas_mondat(ut: str) -> str:
    """A megváltozott célmappa bemondása.

    Vakon a mező tartalmának megváltozása NEM észlelhető magától. Barbinál a
    letöltések addig mentek rossz helyre, amíg fel nem tűnt — és ez azért
    tarthatott sokáig, mert semmi nem szólt érte."""
    return f"Célmappa: {str(ut).strip()}"
