# -*- coding: utf-8 -*-
"""Lemezhely-ellenőrzés a letöltésekhez (MK3).

Miért külön modul: a helyellenőrzés mind a három letöltőmotort érinti, és a
W6 éjszakai figyelőnek is kötelező előfeltétele (egy felügyelet nélküli
letöltés nem tölthet tele egy lemezt éjjel). Ha ez a letöltőkben szétszórva
lenne, háromszor kellene megírni és háromszor javítani.

A modul SZÁNDÉKOSAN nem tud a wx-ről és a letöltőkről: tiszta függvények,
amiket teszteléskor valódi lemez nélkül is meg lehet hívni.
"""

import shutil
from pathlib import Path

# Biztonsági tartalék: soha ne töltsük az utolsó bájtig. A Windows a
# majdnem tele lemezen lassul és hibázik, és a program saját naplói,
# ideiglenes fájljai is helyet kérnek.
TARTALEK = 64 * 1024 * 1024                  # 64 MB

# Futás közbeni figyelmeztetés küszöbe: ennél kevesebb szabad helynél szólunk,
# még ha az adott letöltés bele is férne.
ALACSONY_KUSZOB = 300 * 1024 * 1024          # 300 MB

# MK8: indulás előtti küszöb ISMERETLEN méretnél (yt-dlp, torrent). Magasabb,
# mint a futás közbeni: itt még nem tudjuk, mekkora a fájl, tehát bőkezűbben
# kell figyelmeztetni – egy sorozat-torrent 20 gigabájt is lehet.
INDULAS_KUSZOB = 2 * 1024 * 1024 * 1024      # 2 GB

# Az egész ellenőrzés kikapcsolható. SZÁNDÉKOSAN egyetlen modulszintű
# kapcsoló, nem paraméter három rétegen át: így a felület és a CLI ugyanazt
# az egy dolgot állítja, és nem tudnak eltérni egymástól. Kell, mert a
# hálózati és virtuális meghajtók szabad helye néha hazudik, és egy hamis
# „nincs hely" teljesen megbénítaná a programot.
BEKAPCSOLVA = True


def emberi_meret(b: float) -> str:
    """Bájt → felolvasható magyar méret. Tizedesvesszővel, mert a tizedespontot
    a felolvasó mondatvégi pontnak olvassa."""
    b = float(b)
    if b < 0:
        b = 0.0
    for egyseg, hatar in (("bájt", 1024.0),
                          ("kilobájt", 1024.0 ** 2),
                          ("megabájt", 1024.0 ** 3),
                          ("gigabájt", 1024.0 ** 4)):
        if b < hatar:
            ertek = b / (hatar / 1024.0)
            if egyseg == "bájt":
                return f"{int(ertek)} bájt"
            if ertek >= 100:
                return f"{ertek:.0f} {egyseg}"
            return f"{ertek:.1f} {egyseg}".replace(".", ",")
    return f"{b / 1024.0 ** 4:.1f} terabájt".replace(".", ",")


def letezo_szulo(ut) -> Path:
    """A legközelebbi LÉTEZŐ könyvtár az útvonal felett.

    A célmappa gyakran még nem létezik (a letöltő hozza létre), a
    `shutil.disk_usage` viszont létező útvonalat kér. A szülő ugyanazon a
    köteten van, tehát a válasz ugyanaz."""
    p = Path(ut)
    while True:
        if p.exists():
            return p
        szulo = p.parent
        if szulo == p:                        # elértük a gyökeret
            return p
        p = szulo


def szabad(ut) -> int:
    """Szabad hely bájtban a megadott útvonal kötetén.

    Ha nem megállapítható (hálózati meghajtó, jogosultsági hiba), −1 – és a
    hívó ilyenkor NEM akadályozza meg a letöltést. A bizonytalanság nem hiba:
    egy hamis „nincs hely" rosszabb, mint egy be nem fejezett letöltés."""
    try:
        return int(shutil.disk_usage(letezo_szulo(ut)).free)
    except OSError:
        return -1


def eleg_hely(ut, kell: int, tartalek: int = TARTALEK) -> tuple[bool, int, int]:
    """(belefér, szabad_hely, hiányzik) hármas.

    `kell` = 0 (ismeretlen méret) esetén mindig belefér: nem tarthatunk vissza
    egy letöltést azért, mert a szerver nem mondta meg a méretet.
    `szabad` = −1 (nem megállapítható) esetén szintén."""
    if not BEKAPCSOLVA:
        return True, -1, 0
    sz = szabad(ut)
    if kell <= 0 or sz < 0:
        return True, sz, 0
    kellene = int(kell) + int(tartalek)
    if sz >= kellene:
        return True, sz, 0
    return False, sz, kellene - sz


def indulas_elott(ut, kell: int = 0, nev: str = "") -> str:
    """Indulás előtti helyellenőrzés MINDEN motorra – hibaszöveg vagy üres (MK8).

    **Miért kellett ez az MK3 után is.** Az MK3 csak a szegmentált (HTTP)
    motorba került be, mert ott a `_probe()` már tudja a méretet. A yt-dlp és
    a torrent viszont indulás előtt NEM ismeri a méretet — így ott semmilyen
    ellenőrzés nem futott, pedig egy sorozat-torrent vagy egy hosszú videó
    tölti meg leginkább a lemezt.

    Amit ilyenkor tehetünk: **a küszöb alatti helyet kimondjuk ELŐRE**, méret
    nélkül is. Ez nem tartja vissza a letöltést (nem tudjuk, elfér-e), csak
    figyelmeztet, amíg tenni lehet valamit — a késői „elfogyott a hely"
    ugyanis fél óra munkát dob el."""
    if not BEKAPCSOLVA:
        return ""
    if kell and kell > 0:
        fer, sz, hianyzik = eleg_hely(ut, kell)
        if not fer:
            return hiba_szoveg(nev, kell, sz, hianyzik)
        return ""
    keves, sz = alacsony(ut, INDULAS_KUSZOB)
    if keves:
        return (f"Kevés a hely a célmeghajtón: {emberi_meret(sz)} szabad. "
                "A letöltés elindul, de a méretét előre nem tudom – "
                "figyeld, vagy szabadíts fel helyet.")
    return ""


def alacsony(ut, kuszob: int = ALACSONY_KUSZOB) -> tuple[bool, int]:
    """(alacsony-e, szabad_hely). Nem megállapítható helynél sosem alacsony."""
    if not BEKAPCSOLVA:
        return False, -1
    sz = szabad(ut)
    if sz < 0:
        return False, sz
    return sz < int(kuszob), sz


def hiba_szoveg(nev: str, kell: int, sz: int, hianyzik: int) -> str:
    """A megtagadott letöltés indoklása.

    Három dolgot mond ki, mert vakon egyik sem látszik: mennyi kell, mennyi
    van, és mennyi hiányzik. A harmadik a legfontosabb: abból derül ki, hogy
    egy fájl kitörlése elég lesz-e, vagy más meghajtó kell."""
    nev = (nev or "a fájl").strip()
    return (f"Nincs elég hely a letöltéshez. A(z) {nev} mérete "
            f"{emberi_meret(kell)}, a célmeghajtón viszont csak "
            f"{emberi_meret(sz)} szabad, tehát nagyjából "
            f"{emberi_meret(hianyzik)} hiányzik. Válassz másik célmappát, "
            "vagy szabadíts fel helyet, és indítsd újra a letöltést.")


def alacsony_szoveg(sz: int) -> str:
    """Futás közbeni figyelmeztetés.

    NEM állítunk le semmit: lehet, hogy közben felszabadul a hely, és a futó
    letöltés megölése biztosan rosszabb, mint egy mondat. Csak szólunk, amíg
    tenni lehet valamit."""
    return (f"Fogy a hely a célmeghajtón: már csak {emberi_meret(sz)} szabad. "
            "A futó letöltések megállhatnak, ha betelik.")
