# -*- coding: utf-8 -*-
"""Mappa becsomagolása küldés előtt (2026-09-06).

**Miért kell.** A p2p küldés eddig `wx.FileDialog`-gal indult, tehát EGYETLEN
fájlt lehetett elküldeni. A felhasználók — jogosan — azt kérték, hogy ami
Androidon megy, az itt is menjen: mappát is lehessen küldeni.

**Miért nem a wormhole saját mappa-módját használjuk.** A magic-wormhole tud
könyvtárat is küldeni, de akkor a csomagolás a mi látókörünkön kívül történik:
nem tudunk haladást mondani, nem tudjuk megszakítani, és ugyanaz a csomag nem
használható a felhős úthoz. Egy helyen csomagolunk, és a kész fájl mindkét úton
mehet.

**JELSZÓ NINCS — tudatos döntés (Alph, 2026-09-06).** A Python `zipfile`
jelszavas zipet olvasni tud, írni nem; a külső AES-es megoldás pedig olyan
csomagot gyárt, amit a Windows Intézője NEM nyit meg — a címzett dupla
kattintásra érthetetlen hibát kapna. A régi ZipCrypto megnyílna, de gyenge, és
**egy gyenge titkosítás rosszabb a semminél, mert biztonságérzetet ad.**
Aki titkot küld, arra ott a p2p: az végpontok között titkosít.

A modul SZÁNDÉKOSAN nem tud a wx-ről: tiszta függvények, valódi felület nélkül
is tesztelhetők.
"""

from __future__ import annotations

import os
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path

# A felajánlott formátumok. Mindkettő a Python beépített moduljaival megy —
# nulla új függőség, nulla letöltendő eszköz.
FORMATUMOK = (
    ("zip", "ZIP – ezt minden Windows megnyitja"),
    ("targz", "tar.gz – Linuxra vagy Macre küldve ez a természetes"),
)

KITERJESZTES = {"zip": ".zip", "targz": ".tar.gz"}


def formatum_nevek() -> list[str]:
    """A választható formátumok felolvasható leírásai, a FORMATUMOK sorrendjében."""
    return [leiras for _id, leiras in FORMATUMOK]


def formatum_id(index: int) -> str:
    """Listaindex → formátum-azonosító. Rossz indexnél a ZIP, mert az a biztos."""
    if 0 <= index < len(FORMATUMOK):
        return FORMATUMOK[index][0]
    return "zip"


def biztonsagos(gyoker: Path, ut: Path) -> bool:
    """Igaz, ha `ut` tényleg a `gyoker` ALATT van, és nem szimbolikus link.

    ⚠️ Miért kell ez. Egy mappában lehet olyan hivatkozás, ami kifelé mutat (egy
    másik meghajtóra, a felhasználó egész profiljára). Ha ezeket követnénk, a
    „küldöm ezt a mappát" mozdulatból akaratlanul is egy sokkal nagyobb — és
    magánabb — csomag lenne. A `mentes.py`-nál ugyanezt már egy teszt védi:
    „a csomagban elrejtett útvonal nem ír kifelé."
    """
    try:
        if ut.is_symlink():
            return False
        gy = gyoker.resolve()
        return ut.resolve().is_relative_to(gy)
    except (OSError, ValueError):
        return False


def gyujtes(mappa) -> tuple[list[Path], int]:
    """(fájlok, összméret). A szimbolikus linkeket és a kifelé mutatókat kihagyja.

    A méret azért kell előre, mert (1) ebből tudjuk a szabad helyet ellenőrizni,
    és (2) enélkül a haladás-jelzés csak fájlszámot tudna mondani, ami egy
    nagy videó és ezer apró kép mellett félrevezető."""
    gyoker = Path(mappa)
    fajlok: list[Path] = []
    meret = 0
    for dp, dirnevek, fajlnevek in os.walk(gyoker):
        d = Path(dp)
        # a kifelé mutató alkönyvtárakba be sem lépünk
        dirnevek[:] = [n for n in dirnevek if biztonsagos(gyoker, d / n)]
        for n in fajlnevek:
            f = d / n
            if not biztonsagos(gyoker, f):
                continue
            try:
                meret += f.stat().st_size
            except OSError:
                continue
            fajlok.append(f)
    return fajlok, meret


def csomag_utvonal(mappa, formatum: str = "zip", ideiglenes: bool = True) -> Path:
    """Hova készüljön a csomag.

    `ideiglenes=True` esetén a rendszer ideiglenes mappájába — Windowson egy
    négygigás zip csendben megenné a lemezt, ha kérdés nélkül a mappa mellé
    tennénk. A küldés után a felhasználó dönt, megtartja-e."""
    m = Path(mappa)
    nev = (m.name or "csomag") + KITERJESZTES.get(formatum, ".zip")
    if ideiglenes:
        konyvtar = Path(tempfile.gettempdir()) / "superdl-csomag"
        konyvtar.mkdir(parents=True, exist_ok=True)
        # időbélyeg, hogy két egyidejű csomagolás ne írja felül egymást
        return konyvtar / f"{int(time.time())}-{nev}"
    return m.parent / nev


class Megszakitva(Exception):
    """A felhasználó leállította a csomagolást."""


def csomagol(mappa, cel, formatum: str = "zip", halad=None, megall=None) -> Path:
    """A mappa becsomagolása. Visszaadja a kész csomag útvonalát.

    `halad(kesz_fajl, osszes_fajl, kesz_bajt, ossz_bajt)` — a felület ebből
    mond százalékot ÉS „hányadik fájl hányból"-t; egy négygigás mappa
    csomagolása percekig tart, és **ez nem lehet néma**.

    `megall()` — igaz, ha a felhasználó megszakította. ⚠️ Ilyenkor a FÉLKÉSZ
    csomagot TÖRÖLJÜK: egy megszakított művelet után ottfelejtett kétgigás fájl
    ugyanolyan kár, mint amit az MK3-ban javítottunk.
    """
    gyoker = Path(mappa)
    cel = Path(cel)
    fajlok, ossz = gyujtes(gyoker)
    if not fajlok:
        raise ValueError("Ez a mappa üres, vagy nem tudom elolvasni a "
                         "tartalmát – nincs mit becsomagolni.")
    kesz_bajt = 0
    try:
        if formatum == "targz":
            with tarfile.open(cel, "w:gz") as tf:
                for i, f in enumerate(fajlok, 1):
                    if megall and megall():
                        raise Megszakitva()
                    tf.add(f, arcname=str(f.relative_to(gyoker)),
                           recursive=False)
                    kesz_bajt += _meret(f)
                    if halad:
                        halad(i, len(fajlok), kesz_bajt, ossz)
        else:
            with zipfile.ZipFile(cel, "w", zipfile.ZIP_DEFLATED,
                                 allowZip64=True) as zf:
                for i, f in enumerate(fajlok, 1):
                    if megall and megall():
                        raise Megszakitva()
                    zf.write(f, arcname=str(f.relative_to(gyoker)))
                    kesz_bajt += _meret(f)
                    if halad:
                        halad(i, len(fajlok), kesz_bajt, ossz)
    except BaseException:
        # MEGSZAKÍTÁSNÁL ÉS HIBÁNÁL IS: ne maradjon félkész csomag
        try:
            cel.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return cel


def _meret(f: Path) -> int:
    try:
        return f.stat().st_size
    except OSError:
        return 0


def csomagolas_mondat(nev: str, db: int, meret_szoveg: str) -> str:
    """Amit a csomagolás INDULÁSAKOR mondunk. A darabszám és a méret együtt
    adja meg, mennyit kell várni – önmagában egyik sem mond semmit."""
    return (f"Csomagolom: {nev}. {db} fájl, összesen {meret_szoveg}. "
            "A leállításhoz nyomd meg az Escape billentyűt.")
