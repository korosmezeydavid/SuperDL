# -*- coding: utf-8 -*-
"""A Core szövegdekódolója – UTF-16 felismerés.

Hibajelentés (Laci, 2026-08-19): „Szóközöket tett a fájlba a betűk után…”
A csatolt fájl UTF-16 LE volt, BOM-mal. Egybájtos kódlappal megfejtve minden
betű után egy NULLA-bájt maradt – ez látszik szóköznek, és ez kerül bele az
összefűzött, UTF-8-as kimenetbe is.

A tesztek két irányba védenek: az UTF-16 mostantól megfejthető, ÉS a korábban
is jól működő fájlok (UTF-8, CP1250, CWI) változatlanul jók maradnak.
"""

import pytest

from superdl import textdecode

MAGYAR = ("1993-ban sugárzott színházi közvetítések\n\n"
          "Január 24. Vasárnap\nVánya bácsi – Csehov színműve\n"
          "Árvíztűrő tükörfúrógép")


# ---------------------------------------------------- UTF-16

@pytest.mark.parametrize("kodolas", ["utf-16", "utf-16-le", "utf-16-be"])
def test_utf16_bommal_es_anelkul(kodolas):
    assert textdecode.auto_decode(MAGYAR.encode(kodolas)) == MAGYAR


def test_a_nulla_bajtok_eltunnek():
    """A tünet maga: a betűk közti nulla-bájt (a felhasználónak: szóköz)."""
    ki = textdecode.auto_decode("1993-ban".encode("utf-16"))
    assert "\x00" not in ki
    assert ki == "1993-ban"


def test_utf32_bom_is_mukodik():
    assert textdecode.auto_decode(MAGYAR.encode("utf-32")) == MAGYAR


def test_paratlan_hosszusagu_csonka_utf16_sem_szall_el():
    nyers = MAGYAR.encode("utf-16-le")[:-1]          # levágott utolsó bájt
    ki = textdecode.auto_decode(nyers)
    assert "Csehov" in ki


# ---------------------------------------------------- nincs regresszió

def test_utf8_valtozatlan():
    assert textdecode.auto_decode(MAGYAR.encode("utf-8")) == MAGYAR
    assert textdecode.auto_decode(MAGYAR.encode("utf-8-sig")) == MAGYAR


def test_cp1250_valtozatlan():
    assert textdecode.auto_decode(MAGYAR.encode("cp1250")) == MAGYAR


def test_latin2_valtozatlan():
    # a latin-2 nem ismeri a gondolatjelet (–), ezért ehhez sima kötőjeles szöveg
    szoveg = MAGYAR.replace("–", "-")
    assert textdecode.auto_decode(szoveg.encode("iso-8859-2")) == szoveg


def test_ures_es_apro_bemenet():
    assert textdecode.auto_decode(b"") == ""
    assert textdecode.auto_decode(b"A") == "A"


def test_binaris_szemet_nem_lesz_utf16_nak_nezve():
    """Sok nulla-bájt önmagában nem elég: értelmes szöveggé kell válnia."""
    szemet = bytes([0, 1, 2, 3, 0, 200, 0, 199, 0, 5]) * 40
    ki = textdecode.auto_decode(szemet)
    assert isinstance(ki, str)          # nem száll el, bármit is ad vissza


def test_valos_fajl_szerkezete_megmarad():
    """Sorvégek és tabulátorok is épen maradjanak – a listás fájlok ezekkel
    tagoltak."""
    eredeti = "Első sor\t18.05\r\nMásodik sor\r\n"
    assert textdecode.auto_decode(eredeti.encode("utf-16")) == eredeti


# ---------------------------------------------------- szerkezet-tartás

def test_a_tabulatoros_tagolas_megmarad():
    """Laci jelzése: a műsorlistában a tabulátor maga a tartalom.
    Felolvasáshoz továbbra is szóközzé olvad – fájl→fájl átalakításnál nem."""
    from superdl import booktext
    eredeti = "\tB. 22.05 - 24.23\tKözvetítés a Vígszínházból\r\n\tVánya bácsi\r\n"
    tartott = booktext.clean_structured(eredeti)
    assert "\t" in tartott
    assert tartott.splitlines()[0].startswith("\tB. 22.05")
    # a felolvasáshoz való tisztító viszont ÖSSZEVONJA – ez szándékos
    assert "\t" not in booktext._clean(eredeti)


def test_a_szerkezet_tarto_tisztito_a_sorvegi_szemetet_levagja():
    from superdl import booktext
    assert booktext.clean_structured("sor   \n\tmásik\t\t\n") == "sor\n\tmásik"


def test_tul_sok_ures_sor_osszevonasa_szerkezettel_egyutt():
    from superdl import booktext
    ki = booktext.clean_structured("A\n\n\n\n\tB")
    assert ki == "A\n\n\tB"
