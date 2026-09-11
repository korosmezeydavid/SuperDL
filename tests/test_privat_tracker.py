# -*- coding: utf-8 -*-
"""PRIVÁT TRACKER VÉDELEM — a 4.6.1 óta élő, csendes kár javítása.

**Mit mértem 2026-09-11-én.** A 4.6.1-ben hat nyilvános trackert adtunk az
aria2 parancssorához (`--bt-tracker`), hogy a peer-felderítés működjön. Az
aria2 ezeket **a privát torrentekre is ráteszi** — élőben ellenőrizve: egy
`private=1` jelzőjű torrent `announceList`-jében ott volt mind a kettő
kísérleti extra tracker.

**Miért súlyos.** Egy privát tracker (nCore, iNSANE és társaik) torrentjét
bejelenteni nyilvános trackereknek minden ilyen oldal szabályzatában tilos,
és a következménye kitiltás. A felhasználó tehát elveszítheti a fiókját egy
olyan döntés miatt, amit MI hoztunk helyette, a háta mögött — ráadásul a
letöltés tényét és az IP-címét is kiszivárogtattuk egy nyilvános hálózatra.

Ez a fájl azt védi, hogy ez soha ne kerülhessen vissza csendben.
"""

import hashlib

import pytest

from superdl import bencode, torrent
from superdl.torrent import TorrentDownloader


# ---- egy valódi (minimális) torrentfájl előállítása ---------------------

def _ben(o):
    if isinstance(o, int):
        return b"i%de" % o
    if isinstance(o, bytes):
        return b"%d:%s" % (len(o), o)
    if isinstance(o, list):
        return b"l" + b"".join(_ben(x) for x in o) + b"e"
    if isinstance(o, dict):
        return b"d" + b"".join(_ben(k) + _ben(o[k])
                               for k in sorted(o)) + b"e"
    raise TypeError(type(o))


def _torrent_fajl(tmp_path, privat, nev=b"proba.bin"):
    info = {b"length": 16384, b"name": nev, b"piece length": 16384,
            b"pieces": hashlib.sha1(b"z" * 16384).digest()}
    if privat:
        info[b"private"] = 1
    adat = _ben({b"announce": b"http://tracker.pelda.hu/announce",
                 b"info": info})
    ut = tmp_path / ("priv.torrent" if privat else "nyilv.torrent")
    ut.write_bytes(adat)
    return ut


# ---- 1. a globális kapcsoló SOHA ne tartalmazzon trackert ---------------

def test_a_motor_parancssoraban_NINCS_kiegeszito_tracker(tmp_path):
    """⚠️ EZ A LEGFONTOSABB TESZT EBBEN A FÁJLBAN.

    A globális `--bt-tracker` a privát torrentekre is érvényes (mérve). Ha
    valaha visszakerül ide egy kényelmi okból, a kár CSENDES: semmi nem
    jelez, a felhasználó pedig hetekkel később kap egy kitiltást."""
    k = torrent.halozati_kapcsolok(tmp_path / "dht.dat")
    assert not any(x.startswith("--bt-tracker") for x in k), (
        "A kiegészítő trackerek NEM mehetnek a motor parancssorába: onnan a "
        "privát torrentekre is rákerülnek.")


# ---- 2. a privát jelző felismerése --------------------------------------

def test_a_privat_jelzot_felismerjuk(tmp_path):
    assert bencode.privat_torrent(_torrent_fajl(tmp_path, True)) is True


def test_a_nyilvanos_torrent_nem_privat(tmp_path):
    assert bencode.privat_torrent(_torrent_fajl(tmp_path, False)) is False


def test_a_fajlnevben_levo_private_szo_nem_teveszt_meg(tmp_path):
    """⚠️ Ezért kell VALÓDI bencode-olvasó, nem szövegkeresés: a
    `7:privatei1e` bájtsorozat egy fájlnévben is előfordulhat, és egy téves
    „privát" válasz csak lassít – egy téves „nyilvános" viszont kitilt."""
    ut = _torrent_fajl(tmp_path, False, nev=b"7:privatei1e csalogato.bin")
    assert bencode.privat_torrent(ut) is False


@pytest.mark.parametrize("tartalom", [b"", b"szemet", b"d8:announce",
                                      b"di3ei4ee"])
def test_az_ertelmezhetetlen_fajl_PRIVATNAK_szamit(tmp_path, tartalom):
    """⚠️ A két tévedés nem egyenrangú. Ha egy nyilvános torrentet privátnak
    hiszünk, annyi történik, hogy nem kap extra trackert – lassabban indul.
    Fordítva a felhasználó a FIÓKJÁT veszítheti el. Bizonytalanságnál tehát
    a biztonságos irányba tévedünk."""
    ut = tmp_path / "rossz.torrent"
    ut.write_bytes(tartalom)
    assert bencode.privat_torrent(ut) is True


def test_a_nem_letezo_fajl_nem_privat(tmp_path):
    """A magnet-link és a nem létező út nem fájl: itt nincs mit olvasni,
    és a hívó (`privat()`) dönt róla külön."""
    assert bencode.privat_torrent(tmp_path / "nincs.torrent") is False


# ---- 3. a letöltő tényleg eszerint jár el -------------------------------

def _letolto(ut, tmp_path):
    return TorrentDownloader(str(ut), str(tmp_path))


def test_a_privat_torrent_NEM_kap_extra_trackert(tmp_path):
    d = _letolto(_torrent_fajl(tmp_path, True), tmp_path)
    assert d.privat() is True


def test_a_nyilvanos_torrent_KAP_extra_trackert(tmp_path):
    d = _letolto(_torrent_fajl(tmp_path, False), tmp_path)
    assert d.privat() is False


def test_a_magnet_nyilvanosnak_szamit(tmp_path):
    """Privát trackeren a magnet gyakorlatilag használhatatlan: ott a DHT és
    a partnercsere ki van kapcsolva, metaadat nélkül pedig nincs letöltés."""
    d = TorrentDownloader("magnet:?xt=urn:btih:abc", str(tmp_path))
    assert d.privat() is False


def test_a_dontest_csak_egyszer_szamoljuk_ki(tmp_path):
    """A torrentfájl a letöltés alatt is a lemezen van; minden hozzáadásnál
    újraolvasni fölösleges, és egy időközben törölt fájl miatt a válasz meg
    is változhatna menet közben."""
    ut = _torrent_fajl(tmp_path, True)
    d = _letolto(ut, tmp_path)
    assert d.privat() is True
    ut.unlink()                       # a fájl eltűnik
    assert d.privat() is True         # a válasz NEM változik


# ---- 4. a felderítés a nyilvános torrenteken megmarad -------------------

def test_a_peer_felderites_tovabbra_is_be_van_kapcsolva(tmp_path):
    """⚠️ Laci 4.6.1-es hibája NEM jöhet vissza. A DHT, a PEX és az LPD
    marad – az aria2 ezeket a privát torrentekre magától kikapcsolja
    (dokumentált viselkedés), tehát ott sem okoznak bajt."""
    k = torrent.halozati_kapcsolok(tmp_path / "dht.dat")
    assert "--enable-dht=true" in k
    assert "--enable-peer-exchange=true" in k
    assert "--bt-enable-lpd=true" in k
    assert any(x.startswith("--dht-entry-point=") for x in k)


def test_a_tracker_lista_megvan_es_ep():
    """A lista maga nem tűnt el, csak máshova került."""
    assert len(torrent.TRACKEREK) >= 3
    assert all(u.startswith(("udp://", "http://", "https://"))
               for u in torrent.TRACKEREK)
