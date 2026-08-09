# -*- coding: utf-8 -*-
"""A P2P hibaértelmező (friendly_error) tesztjei – a küldés/fogadás gyűjtő-hibája
mögé konkrét okot fűz a wormhole utolsó soraiból."""
import pytest

P = pytest.importorskip("modules_src.p2p.p2p_mod.p2p")


def test_idotullepes():
    ok = P.friendly_error(["Sending file...", "timed out waiting for the other side"])
    assert "időtúllépés" in ok


def test_halozat_tuzfal():
    for sor in ["ConnectionError: Connection refused",
                "websocket connection failed",
                "getaddrinfo failed"]:
        ok = P.friendly_error([sor])
        assert "közvetítő-szerver" in ok and "hotspot" in ok


def test_rossz_kod():
    ok = P.friendly_error(["wormhole.errors.WrongPasswordError: key confirmation failed"])
    assert "kód" in ok


def test_lejart_kod():
    ok = P.friendly_error(["The nameplate has already been claimed"])
    assert "ÚJ kódot" in ok


def test_ismeretlen_ok_utolso_sort_adja():
    ok = P.friendly_error(["valami furcsa belső üzenet 42"])
    assert ok.startswith("a hálózat jelzése:")
    assert "furcsa" in ok


def test_ures_bemenet_ures_ok():
    assert P.friendly_error([]) == ""
    assert P.friendly_error(["", "   "]) == ""


def test_haladas_sor_nem_ertelmes():
    # a tqdm haladás-sora nem hasznos a hibához
    assert not P._ertelmes_sor(" 42%|####      | 4.2M/10M, 00:03")
    assert not P._ertelmes_sor("")
    # egy valódi üzenet igen
    assert P._ertelmes_sor("Connection refused")


def test_haladas_szazalek_onmagaban_ertelmes_maradhat():
    # a „100% kész" jellegű sor ne essen ki csak a %-jel miatt
    assert P._ertelmes_sor("Kész: 100% átment")
