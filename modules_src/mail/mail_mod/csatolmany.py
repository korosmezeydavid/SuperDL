# -*- coding: utf-8 -*-
"""Super Mail – CSATOLMÁNY FELOLVASÁSA.

Ez a mi legnagyobb szerkezeti előnyünk: a SuperDL-ben EGY programban van a
levelező és a dokumentum-feldolgozás. Más levelezőprogramnál egy PDF vagy Word
csatolmányhoz külön alkalmazást kell megnyitni – vakon ez ablakváltás,
tájékozódás, keresgélés. Itt egyetlen billentyű: a csatolmány szövege
megjelenik felolvasható mezőben.

A kinyerést a Core `booktext` rétege végzi (ugyanaz, ami a hangoskönyv-
készítőt is kiszolgálja) – nem duplikálunk kódot.
"""

from __future__ import annotations

import os
import tempfile

# amit szöveggé tudunk alakítani
SZOVEGES = {".txt", ".md", ".csv", ".log", ".ini", ".json", ".xml", ".srt",
            ".sub", ".vtt", ".py"}
DOKUMENTUM = {".pdf", ".docx", ".epub", ".odt", ".rtf"}
HTML = {".html", ".htm"}

OLVASHATO = SZOVEGES | DOKUMENTUM | HTML


def olvashato_e(nev: str) -> bool:
    return os.path.splitext(str(nev or ""))[1].lower() in OLVASHATO


def miert_nem(nev: str) -> str:
    """Felolvasható magyarázat, ha nem tudjuk szöveggé alakítani."""
    kit = os.path.splitext(str(nev or ""))[1].lower() or "(nincs kiterjesztés)"
    if kit in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"):
        return ("Ez egy kép (%s) – nincs benne szöveg, amit felolvashatnék. "
                "Mentsd el, ha meg szeretnéd nézetni valakivel." % kit)
    if kit in (".mp3", ".wav", ".m4a", ".ogg", ".flac"):
        return "Ez egy hangfájl (%s) – mentsd el és játszd le." % kit
    if kit in (".zip", ".rar", ".7z"):
        return ("Ez egy tömörített csomag (%s) – mentsd el, és a SuperDL "
                "kicsomagolójával nyisd meg." % kit)
    return ("Ezt a fájltípust (%s) nem tudom szöveggé alakítani. Mentsd el, és "
            "nyisd meg a hozzá való programmal." % kit)


def _html_szoveg(nyers: str) -> str:
    from . import mail_core as MC
    k = MC._SzovegKinyero()
    k.feed(nyers or "")
    return k.szoveg()


def szoveg(nev: str, adat: bytes) -> str:
    """A csatolmány szövege. Hiba esetén kivételt dob, hogy a hívó KI TUDJA
    MONDANI, mi történt – a néma semmi a legrosszabb."""
    kit = os.path.splitext(str(nev or ""))[1].lower()
    if kit in SZOVEGES:
        from superdl import textdecode
        return textdecode.auto_decode(adat or b"")
    if kit in HTML:
        from superdl import textdecode
        return _html_szoveg(textdecode.auto_decode(adat or b""))
    if kit in DOKUMENTUM:
        from superdl import booktext
        # a kinyerő FÁJLT vár – ideiglenesbe írjuk, és utána takarítunk
        ut = os.path.join(tempfile.gettempdir(),
                          "supermail_csat_%d%s" % (os.getpid(), kit))
        with open(ut, "wb") as f:
            f.write(adat or b"")
        try:
            konyv = booktext.extract(ut)
            return konyv.text
        finally:
            try:
                os.remove(ut)
            except OSError:
                pass
    raise ValueError(miert_nem(nev))


def osszefoglalo(nev: str, szoveg_tartalom: str) -> str:
    """Rövid, felolvasható bevezető a csatolmány szövege előtt."""
    sorok = [s for s in (szoveg_tartalom or "").splitlines() if s.strip()]
    szavak = len((szoveg_tartalom or "").split())
    if not szavak:
        return ("A(z) %s csatolmányban nem találtam felolvasható szöveget. "
                "Ha ez beolvasott (képként mentett) dokumentum, akkor a "
                "szöveg valójában kép – ilyet nem tudok felolvasni." % nev)
    return ("%s – %d szó, %d bekezdés. A szöveg a mezőben, a fel-le nyilakkal "
            "olvasható." % (nev, szavak, len(sorok)))
