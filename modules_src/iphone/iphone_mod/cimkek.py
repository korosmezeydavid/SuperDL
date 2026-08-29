# -*- coding: utf-8 -*-
"""Hangfájl-címkék olvasása – KÜLSŐ CSOMAG NÉLKÜL.

A telefonra feltöltött szám a gyári Zene alkalmazásban CÍMMEL és ELŐADÓVAL
jelenjen meg, ne fájlnévvel. A címeket a fájl maga hordozza (MP3-ban ID3,
M4A-ban „atomok”), csak ki kell olvasni. Külön csomagot (mutagen) nem hozunk be
egyetlen mezőért – a modul így függőség nélküli marad.

Amit nem találunk meg, arra a FÁJLNÉV a tartalék: jobb egy értelmes fájlnév,
mint egy üres cím.
"""
from __future__ import annotations

import os
import struct

# MPEG-1 Layer III bitráta- és mintavétel-táblák (a hossz becsléséhez)
_BITRATE = (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0)
_MINTA = {0: 44100, 1: 48000, 2: 32000}


def _szoveg(adat: bytes) -> str:
    """Egy ID3 szövegmező: az első bájt a kódolást mondja meg."""
    if not adat:
        return ""
    kod, test = adat[0], adat[1:]
    try:
        if kod == 0:
            s = test.decode("latin-1")
        elif kod == 1:
            s = test.decode("utf-16")
        elif kod == 2:
            s = test.decode("utf-16-be")
        else:
            s = test.decode("utf-8")
    except (UnicodeDecodeError, LookupError):
        s = test.decode("latin-1", "replace")
    return s.split("\x00")[0].strip()


def _syncsafe(b: bytes) -> int:
    return (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]


def _id3(ut: str) -> tuple:
    """(cím, előadó, album, a címke mérete) egy MP3-ból."""
    with open(ut, "rb") as f:
        fej = f.read(10)
        if len(fej) < 10 or fej[:3] != b"ID3":
            return "", "", "", 0
        verzio = fej[3]
        meret = _syncsafe(fej[6:10])
        adat = f.read(meret)
    cim = eloado = album = ""
    i = 0
    while i + 10 <= len(adat):
        azon = adat[i:i + 4]
        if not azon.strip(b"\x00"):
            break                                   # kitöltő rész, vége
        if verzio >= 4:
            hossz = _syncsafe(adat[i + 4:i + 8])
        else:
            hossz = struct.unpack(">I", adat[i + 4:i + 8])[0]
        test = adat[i + 10:i + 10 + hossz]
        if azon == b"TIT2":
            cim = _szoveg(test)
        elif azon == b"TPE1":
            eloado = _szoveg(test)
        elif azon == b"TALB":
            album = _szoveg(test)
        i += 10 + hossz
        if hossz <= 0:
            break
    return cim, eloado, album, meret + 10


def _mp3_hossz_ms(ut: str, cimke_meret: int) -> int:
    """Becsült hossz: az első keret fejlécéből vett bitrátával. Állandó
    bitrátánál pontos, változónál közelítő – a Zene appnak ennyi elég."""
    try:
        meret = os.path.getsize(ut)
        with open(ut, "rb") as f:
            f.seek(cimke_meret)
            nyers = f.read(4096)
        for i in range(len(nyers) - 4):
            if nyers[i] == 0xFF and (nyers[i + 1] & 0xE0) == 0xE0:
                br = _BITRATE[(nyers[i + 2] >> 4) & 0x0F]
                mi = _MINTA.get((nyers[i + 2] >> 2) & 0x03)
                if br and mi:
                    return int((meret - cimke_meret) * 8 / (br * 1000) * 1000)
        return 0
    except OSError:
        return 0


def _m4a(ut: str) -> tuple:
    """(cím, előadó, album, hossz ms) egy M4A/M4B fájlból (atom-szerkezet)."""
    cim = eloado = album = ""
    hossz = 0
    try:
        with open(ut, "rb") as f:
            adat = f.read(4 << 20)          # a címkék a fájl elején vannak
    except OSError:
        return "", "", "", 0

    def _mezo(jel: bytes) -> str:
        i = adat.find(jel)
        if i < 0:
            return ""
        j = adat.find(b"data", i)
        if j < 0 or j - i > 64:
            return ""
        h = struct.unpack(">I", adat[j - 4:j])[0]
        return adat[j + 12:j - 4 + h].decode("utf-8", "replace").strip()

    cim = _mezo(b"\xa9nam")
    eloado = _mezo(b"\xa9ART")
    album = _mezo(b"\xa9alb")
    i = adat.find(b"mvhd")
    if i > 0:
        try:
            ido_egyseg, tartam = struct.unpack(">II", adat[i + 12:i + 20])
            if ido_egyseg:
                hossz = int(tartam / ido_egyseg * 1000)
        except struct.error:
            pass
    return cim, eloado, album, hossz


def beolvas(ut: str) -> dict:
    """Egy hangfájl adatai: {'cim', 'eloado', 'album', 'ms'}.

    Ha a fájl nem árulja el a címét, a FÁJLNEVET használjuk – az mindig
    értelmesebb, mint egy üres sor a telefon lejátszójában."""
    kit = os.path.splitext(ut)[1].lower()
    cim = eloado = album = ""
    ms = 0
    try:
        if kit == ".mp3":
            cim, eloado, album, cimke = _id3(ut)
            ms = _mp3_hossz_ms(ut, cimke)
        elif kit in (".m4a", ".m4b", ".mp4", ".aac"):
            cim, eloado, album, ms = _m4a(ut)
    except Exception:
        pass                                 # sérült címke nem gátolhatja a küldést
    if not cim:
        cim = os.path.splitext(os.path.basename(ut))[0]
    return {"cim": cim, "eloado": eloado, "album": album, "ms": max(0, ms)}
