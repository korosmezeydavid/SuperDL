# -*- coding: utf-8 -*-
"""AUTOMATIKUS RENDEZÉS: a kész letöltés a típusa szerinti mappába (MK10).

⚠️ **A terv szerint ehhez „az `organizer.py` megvan". NEM.** Az `organizer.py`
a NAPTÁR, a teendők és a jegyzetek kezelője — semmi köze a letöltött
fájlokhoz. Ez a modul nulláról épült.

**Miért hasznos ez vakon, és miért kockázatos.** Hasznos, mert a
Letöltések mappa hetek alatt átláthatatlanná válik, és szemmel átfutni nem
lehet: a „hol van a tegnapi hangoskönyv" kérdésre a válasz ma végigléptetés.
Kockázatos, mert **fájlt mozgatni visszafordíthatatlan** — ha rossz helyre
teszünk valamit, a felhasználó nem találja meg.

Ezért:
- **alapból KIKAPCSOLT**, a felhasználó dönt;
- **soha nem írunk felül**: ütközésnél a fájl a helyén marad;
- **soha nem lépünk ki a célmappából**: az almappa a letöltési mappán belül van;
- a mozgatás hibája **nem hiba a letöltésen**: a fájl megvan, csak máshol.
"""
from __future__ import annotations

from pathlib import Path

# Kiterjesztés → almappa. A nevek magyarul, mert a felhasználó ezeket hallja
# és ezek közt keres majd a Fájlkezelőben.
CSOPORTOK: dict[str, tuple[str, ...]] = {
    "Videók": (".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".ts",
               ".flv", ".wmv", ".mpg", ".mpeg", ".m2ts"),
    "Zene": (".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav",
             ".wma", ".aiff"),
    "Képek": (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff",
              ".svg"),
    "Dokumentumok": (".pdf", ".epub", ".mobi", ".azw3", ".doc", ".docx",
                     ".odt", ".rtf", ".txt", ".xls", ".xlsx", ".ppt",
                     ".pptx"),
    "Csomagok": (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
                 ".iso", ".exe", ".msi"),
}

EGYEB = "Egyéb"


def csoport(nev: str) -> str:
    """A fájlnévhez tartozó almappa neve."""
    try:
        kit = Path(str(nev or "")).suffix.lower()
    except (OSError, ValueError):
        return EGYEB
    if not kit:
        return EGYEB
    for mappa, kiterjesztesek in CSOPORTOK.items():
        if kit in kiterjesztesek:
            return mappa
    return EGYEB


def celut(fajl, gyoker=None) -> Path | None:
    """Hova kerüljön a fájl – vagy None, ha nem kell mozgatni.

    A `gyoker` a letöltési mappa. Ha a fájl MÁR egy almappában van (tehát nem
    közvetlenül a gyökérben), nem nyúlunk hozzá: lehet, hogy a felhasználó
    vagy egy lejátszási lista tette oda, és nem a mi dolgunk átrakni."""
    try:
        f = Path(fajl)
        gy = Path(gyoker) if gyoker else f.parent
    except (OSError, ValueError):
        return None
    if f.parent.resolve() != gy.resolve():
        return None                      # nem a gyökérben van → békén hagyjuk
    cel = gy / csoport(f.name)
    if cel.resolve() == f.parent.resolve():
        return None
    return cel / f.name


def rendez(fajl, gyoker=None) -> tuple[str, str]:
    """A fájl áthelyezése a típusa szerinti almappába.

    Visszaad: (új_útvonal_vagy_üres, hibaüzenet_vagy_üres).

    **Soha nem írunk felül**: ha a célnéven már van fájl, a mozgatás elmarad,
    és ezt hibaként adjuk vissza — de a hívó tudja, hogy ez NEM a letöltés
    hibája. Egy meglévő fájl csendben felülírása sokkal rosszabb volna, mint
    egy rendezetlenül maradt letöltés."""
    cel = celut(fajl, gyoker)
    if cel is None:
        return "", ""
    try:
        forras = Path(fajl)
        if not forras.is_file():
            return "", ""
        if cel.exists():
            return "", (f"A(z) {cel.name} már létezik a(z) "
                        f"{cel.parent.name} mappában, ezért nem mozgattam.")
        cel.parent.mkdir(parents=True, exist_ok=True)
        forras.replace(cel)
        return str(cel), ""
    except OSError as e:
        return "", f"A rendezés nem sikerült: {e}"


def rendez_mondat(nev: str, mappa: str) -> str:
    """Amit a felhasználó HALL. A mappa nevét ki KELL mondani: ha nem
    tudja, hova került, a rendezés rosszabb, mint a rendetlenség."""
    return f"{nev} a(z) {mappa} mappába került."
