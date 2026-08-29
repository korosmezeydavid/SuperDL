# -*- coding: utf-8 -*-
"""Super Mail – a fordító HÁLÓZATI HIBÁI érthető mondatot adjanak.

Farkas István hibajelzése (2026-08-29): a levél fordítása közben ez jött fel:
„HTTP Error 429: Too Many Requests”. Ez az ingyenes fordító napi korlátja, de
a felhasználó ebből semmit nem tud meg – főleg azt nem, hogy mit tegyen.

A kód eddig CSAK azt a korlátot ismerte fel, amit a szolgáltató rendes
válaszban küld („LIMIT”). A 429 viszont KIVÉTELKÉNT érkezik, tehát a
válasz-vizsgálatig el sem jutunk. Ezek a tesztek ezt a rést mérik.
"""

import sys

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import forditas as F            # noqa: E402


def _http_hiba(kod):
    import urllib.error

    def dob(url, timeout=30):
        raise urllib.error.HTTPError(url, kod, "Too Many Requests", {}, None)
    return dob


def test_a_429_ertheto_magyar_mondatot_ad(monkeypatch):
    """Farkas István jelezte (2026-08-29): „HTTP Error 429: Too Many Requests”.
    A korlát nem mindig rendes válaszban érkezik – sokszor HTTP-hibaként, ami
    a válasz-vizsgálatot MEGKERÜLI. A felhasználó ilyenkor is tudja meg, mi
    történt és mit tehet."""
    monkeypatch.setattr(F.urllib.request, "urlopen", _http_hiba(429))
    with pytest.raises(RuntimeError) as hiba:
        F.mymemory_fordit("hello", "en", "hu")
    sz = str(hiba.value)
    assert "429" not in sz, "ne a nyers hibakód menjen a felhasználónak"
    assert "napi keret" in sz or "nem fogad több kérést" in sz
    assert "helyben" in sz, "mondjuk meg a kiutat is"


def test_a_szolgaltato_hibaja_masfele_uzenetet_ad(monkeypatch):
    monkeypatch.setattr(F.urllib.request, "urlopen", _http_hiba(503))
    with pytest.raises(RuntimeError) as hiba:
        F.mymemory_fordit("hello", "en", "hu")
    assert "szolgáltató oldalán" in str(hiba.value)


def test_halozat_nelkul_is_ertheto_a_hiba(monkeypatch):
    import urllib.error

    def nincs_net(url, timeout=30):
        raise urllib.error.URLError("nincs kapcsolat")
    monkeypatch.setattr(F.urllib.request, "urlopen", nincs_net)
    with pytest.raises(RuntimeError) as hiba:
        F.mymemory_fordit("hello", "en", "hu")
    assert "Nincs kapcsolat" in str(hiba.value)
