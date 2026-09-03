# -*- coding: utf-8 -*-
"""KÖZÖS ÚJRAPRÓBA-POLITIKA (letöltő-motor MK4).

Eddig motoronként MÁS szabály élt: a szegmentálté 5 próba exponenciális
szünettel, a yt-dlp-é 5+5, a torrenté NULLA. Ez a modul egyetlen, közös
politikát ad mindháromnak – és ami legalább ennyire fontos: **felolvasható
mondatot** is, mert vakon a „hányadik próbálkozás és mikor” nem a naplóban,
hanem a fülben kell hogy megjelenjen.

A szünetek a tervezőszobai döntés szerint (2026-08-30):
**1, 2, 5, 10 perc, utána 15 percenként.**

Ez a modul SZÁNDÉKOSAN nem tud semmit a letöltőkről: csak számol és mondatot
gyárt, így wx és hálózat nélkül tesztelhető.
"""
from __future__ import annotations

# a próbálkozások közti szünetek másodpercben; a lista végét ismételjük
SZUNETEK: tuple[int, ...] = (60, 120, 300, 600)
ISMETLODO: int = 900                      # 15 perc, a lista kifutása után

# meddig próbálkozunk egyáltalán: 0 = korlátlan (a torrentnél ez a helyes,
# mert a seedelés/letöltés napokig is eltarthat, és a hálózat visszajöhet)
VEGTELEN: int = 0


def szunet(probak: int) -> int:
    """Hány másodperc múlva jöjjön a KÖVETKEZŐ próba, ha eddig `probak`
    darab sikertelen próbálkozás volt (0 = még egy sem)."""
    if probak < 0:
        probak = 0
    if probak < len(SZUNETEK):
        return SZUNETEK[probak]
    return ISMETLODO


# ---- BELSŐ újrapróba: a letöltésen BELÜL, másodperces léptékben (MK8) ----
#
# ⚠️ **A fenti, PERCES politikát NEM szabad ráhúzni a motorok belső
# újrapróbájára, és ez nem lustaság, hanem szándék.** A `SZUNETEK` a JOB
# szintjén él: ott egy bukás azt jelenti, hogy az egész letöltés elhasalt, és
# egy perc várakozás olcsó. A szegmentált letöltőben viszont EGY DARAB
# szegmens akad meg egy 8 szálas letöltésből — ha arra várnánk egy percet, a
# letöltés a töredékére lassulna, miközben a másik hét szál dolgozik.
#
# Két különböző fogalom, két különböző lépték. Amit egységesíteni ÉRDEMES, az
# nem az időzítés, hanem hogy EGY helyen legyen leírva, és hogy a felhasználó
# MEGTUDJA: ez a letöltés épp küzd.
BELSO_SZUNETEK: tuple[int, ...] = (1, 2, 4, 8, 16)
BELSO_MAX = len(BELSO_SZUNETEK)


def belso_szunet(probak: int) -> int:
    """Hány másodperc múlva jöjjön a következő BELSŐ próba (szegmens, darab)."""
    if probak < 0:
        probak = 0
    if probak < len(BELSO_SZUNETEK):
        return BELSO_SZUNETEK[probak]
    return BELSO_SZUNETEK[-1]


def kuzd_uzenet(probak: int) -> str:
    """Amit a felhasználó HALL, ha egy letöltés belül küzd.

    Eddig ez teljesen néma volt: a szegmens ötször újrapróbált, a felhasználó
    pedig annyit érzékelt, hogy „lassú". Vakon a lassú és az akadozó között
    nincs különbség — pedig az egyik normális, a másik nem."""
    return ("Ez a letöltés akadozik: %s újrapróbálkozás menet közben. "
            "Nem kell tenned semmit, magától folytatódik." % sorszam(probak))


def probalkozhat(probak: int, max_proba: int = VEGTELEN) -> bool:
    return max_proba == VEGTELEN or probak < max_proba


def emberi_ido(mp: int) -> str:
    """„öt perc”, „negyed óra” – felolvasva a 00:15:00 használhatatlan.

    A vak felhasználó a fülével kap időt, nem a szemével: a „negyed óra múlva”
    egy mozdulattal érthető, a „00:15:00” előbb ki kell hogy legyen bogarászva.
    """
    mp = max(0, int(mp))
    if mp < 60:
        return "néhány másodperc"
    perc = round(mp / 60)
    if perc == 1:
        return "egy perc"
    if perc == 15:
        return "negyed óra"
    if perc == 30:
        return "fél óra"
    if perc == 45:
        return "háromnegyed óra"
    if perc < 60:
        return "%d perc" % perc
    ora = perc / 60
    if abs(ora - round(ora)) < 0.01:
        return "egy óra" if round(ora) == 1 else "%d óra" % round(ora)
    return "%d perc" % perc


_SORSZAM = ("első", "második", "harmadik", "negyedik", "ötödik", "hatodik",
            "hetedik", "nyolcadik", "kilencedik", "tizedik")


def sorszam(n: int) -> str:
    """1 → „első”. Tizedik fölött a szám marad, de a mondat maradjon magyar."""
    if 1 <= n <= len(_SORSZAM):
        return _SORSZAM[n - 1]
    return "%d." % n


def uzenet(probak: int, mp: int | None = None) -> str:
    """A felolvasandó mondat: „Második próbálkozás, öt perc múlva.”

    `probak`: hány sikertelen próba volt EDDIG. A most következő tehát a
    (probak + 1). Ha `mp` None, a politikából számoljuk.
    """
    kovetkezo = max(1, probak + 1)
    if mp is None:
        mp = szunet(probak)
    return "%s próbálkozás, %s múlva." % (
        sorszam(kovetkezo).capitalize(), emberi_ido(mp))


def feladtuk_uzenet(probak: int) -> str:
    return ("%d sikertelen próbálkozás után feladtam. "
            "A sorban marad, kézzel újraindíthatod." % probak)
