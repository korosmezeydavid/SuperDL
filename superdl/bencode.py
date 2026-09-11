# -*- coding: utf-8 -*-
"""Minimális bencode-olvasó — EGYETLEN kérdéshez: privát-e ez a torrent?

**Miért kellett, és miért sürgősen.** A 4.6.1-ben hat nyilvános trackert
adtunk az aria2 parancssorához (`--bt-tracker`), hogy a peer-felderítés
végre működjön. Mérve 2026-09-11: **az aria2 ezeket a PRIVÁT torrentekre is
ráteszi.** Egy privát tracker (nCore, iNSANE és társaik) torrentjét tehát
bejelentettük hat nyilvános trackernek is.

Ez nem szépséghiba. A privát trackerek szabályzata ezt kivétel nélkül
tiltja, és a következménye kitiltás — a felhasználó önhibáján kívül, egy
olyan döntés miatt, amit MI hoztunk helyette, a háta mögött. Ráadásul a
letöltés tényét és az IP-címét is kiszivárogtattuk egy nyilvános hálózatra.

Ezért a torrentfájlt a hozzáadás ELŐTT meg kell néznünk. A `private` jelző
az `info` szótárban van (BEP-27), és csak a fájl valódi elemzésével
olvasható ki megbízhatóan: a nyers szövegben keresgélni („7:privatei1e")
azért rossz, mert ugyanaz a bájtsorozat egy fájlnévben is előfordulhat, és
egy TÉVES „nyilvános" válasz itt éppen a kitiltást okozná.

⚠️ Ez a modul SZÁNDÉKOSAN nem teljes bencode-könyvtár: nem írunk, nem
ellenőrzünk aláírást, nem dolgozunk fel hibás fájlt „valahogy". Egy kérdésre
felel, és ha bizonytalan, a BIZTONSÁGOS irányba téved (privátnak mondja).
"""

from __future__ import annotations

from pathlib import Path


class BencodeHiba(ValueError):
    """Értelmezhetetlen bencode adat."""


def _dekodol(adat: bytes, i: int):
    """Egy elem beolvasása az `i` pozíciótól. Visszaad: (érték, új pozíció)."""
    if i >= len(adat):
        raise BencodeHiba("váratlan vég")
    c = adat[i:i + 1]
    if c == b"i":                                   # egész: i<szám>e
        vege = adat.index(b"e", i)
        return int(adat[i + 1:vege]), vege + 1
    if c == b"l":                                   # lista
        i += 1
        ki = []
        while adat[i:i + 1] != b"e":
            ertek, i = _dekodol(adat, i)
            ki.append(ertek)
        return ki, i + 1
    if c == b"d":                                   # szótár
        i += 1
        ki = {}
        while adat[i:i + 1] != b"e":
            kulcs, i = _dekodol(adat, i)
            ertek, i = _dekodol(adat, i)
            ki[kulcs] = ertek
        return ki, i + 1
    if c.isdigit():                                 # bájtfüzér: <hossz>:<adat>
        ketto = adat.index(b":", i)
        hossz = int(adat[i:ketto])
        eleje = ketto + 1
        return adat[eleje:eleje + hossz], eleje + hossz
    raise BencodeHiba("ismeretlen típusjel: %r" % c)


def dekodol(adat: bytes):
    """Bencode bájtsorozat → Python adat. Hibás adatnál `BencodeHiba`."""
    try:
        ertek, _ = _dekodol(adat, 0)
    except BencodeHiba:
        raise
    except Exception as e:                          # index, int, unicode…
        raise BencodeHiba(str(e)) from e
    return ertek


def privat_torrent(ut) -> bool:
    """Privát-e a torrentfájl? (BEP-27: `info` → `private` = 1.)

    ⚠️ **Bizonytalanságnál IGAZAT ad vissza**, és ennek a döntésnek ára van:
    egy privátnak hitt nyilvános torrent csak annyit veszít, hogy nem kap
    extra trackereket — kicsit lassabban indul. Fordítva viszont a
    felhasználó fiókját veszítheti el. A két tévedés nem egyenrangú, ezért
    nem is bánunk velük egyformán.
    """
    try:
        p = Path(ut)
        if not p.is_file():
            return False            # nem fájl (magnet): itt nincs mit olvasni
        adat = p.read_bytes()
    except OSError:
        return True                 # nem tudtuk megnézni → óvatosan
    try:
        meta = dekodol(adat)
        info = meta[b"info"]
        return int(info.get(b"private", 0)) == 1
    except BencodeHiba:
        return True                 # értelmezhetetlen → óvatosan
    except Exception:
        return True


def magnet_e(url: str) -> bool:
    return (url or "").strip().lower().startswith("magnet:")
