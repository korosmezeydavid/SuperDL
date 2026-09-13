# -*- coding: utf-8 -*-
"""A SuperDL saját azonosítója a BitTorrent-hálózaton.

Az nCore Helpdesk kérése (2026-09-12): a peer_id és a user-agent a saját
program nevét és verziószámát tartalmazza, hogy meg lehessen különböztetni a
SuperDL felhasználóit a nyers aria2-től. Eddig mindenki `A2-1-37-0-` peer_id-vel
jelentkezett be.
"""
import pytest

from superdl import torrent


def _ertek(kapcsolok, nev):
    for k in kapcsolok:
        if k.startswith(nev + "="):
            return k.split("=", 1)[1]
    return None


def test_mind_a_harom_kapcsolo_ott_van():
    k = torrent.azonosito_kapcsolok("4.6.9")
    assert _ertek(k, "--peer-id-prefix")          # a TRACKER ezt látja
    assert _ertek(k, "--peer-agent")              # a PEEREK ezt látják
    assert _ertek(k, "--user-agent")              # a HTTP-bejelentkezés


def test_a_nev_es_a_verzio_benne_van():
    k = torrent.azonosito_kapcsolok("4.6.9")
    assert _ertek(k, "--peer-agent") == "SuperDL/4.6.9"
    assert _ertek(k, "--user-agent") == "SuperDL/4.6.9"


def test_a_peer_id_elotag_pontosan_8_karakter():
    """A peer_id 20 bájt; a maradékot az aria2 tölti fel véletlennel."""
    for v in ("4.6.9", "4.6.10", "10.0.0", "1.2.3"):
        e = _ertek(torrent.azonosito_kapcsolok(v), "--peer-id-prefix")
        assert len(e) == 8, f"{v} -> {e}"
        assert e.startswith("-SDL") and e.endswith("-")


def test_a_verzio_latszik_az_elotagban():
    assert _ertek(torrent.azonosito_kapcsolok("4.6.9"),
                  "--peer-id-prefix") == "-SDL469-"
    # két számjegyű rész is ELFÉR (a 4.6.10 nem tolja szét az előtagot)
    assert _ertek(torrent.azonosito_kapcsolok("4.6.10"),
                  "--peer-id-prefix") == "-SDL46a-"


def test_kulonbozo_verziok_kulonbozo_elotagot_adnak():
    a = _ertek(torrent.azonosito_kapcsolok("4.6.8"), "--peer-id-prefix")
    b = _ertek(torrent.azonosito_kapcsolok("4.6.9"), "--peer-id-prefix")
    assert a != b


def test_rossz_verzioszam_nem_dontheti_el():
    """Elgépelt vagy hiányos verzió esetén sem szabad hibás kapcsolót adni:
    az aria2 egy rossz kapcsolótól EL SEM INDUL – akkor nincs torrent."""
    for v in ("", "4", "4.6", "fejlesztoi", "4.6.8-rc1", "x.y.z"):
        e = _ertek(torrent.azonosito_kapcsolok(v), "--peer-id-prefix")
        assert len(e) == 8, f"{v!r} -> {e!r}"
        assert " " not in e


def test_nincs_szokoz_a_kapcsolokban():
    """Szóköz a kapcsolóban parancssori hiba forrása."""
    for k in torrent.azonosito_kapcsolok("4.6.9"):
        assert " " not in k


def test_a_halozati_kapcsolok_kozott_is_ott_van():
    """A GYAKORLATBAN is ki kell mennie – nem elég, hogy a függvény létezik."""
    k = torrent.halozati_kapcsolok()
    assert any(x.startswith("--peer-id-prefix=-SDL") for x in k)
    assert any(x.startswith("--peer-agent=SuperDL/") for x in k)
    assert any(x.startswith("--user-agent=SuperDL/") for x in k)


def test_nem_maradt_ott_az_aria2_alapertelmezese():
    """Az `A2-` előtag azt jelenti, hogy a felhasználó megkülönböztethetetlen
    a nyers aria2-től – pontosan ezt kérte az nCore, hogy szűnjön meg."""
    e = _ertek(torrent.halozati_kapcsolok(), "--peer-id-prefix")
    assert not e.startswith("A2-")


@pytest.mark.parametrize("n,jel", [(0, "0"), (9, "9"), (10, "a"),
                                   (35, "z"), (99, "z")])
def test_b36(n, jel):
    assert torrent._b36(n) == jel
