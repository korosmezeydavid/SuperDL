# -*- coding: utf-8 -*-
"""Braille gyakorlat – a MAGYAR pontírás táblája.

Hibajelentés (2026-08-24): „betűk rosszul vannak benne megadva, például a z
hivatalosan 1, 2, 6.” Igaza volt: a játékban az ANGOL tábla szerepelt, ahol a
z = 1356, a q = 12345, és ékezetes betűk egyáltalán nem voltak benne.

A javított tábla KÉT független, hiteles forrással egyezik:
  1. liblouis magyar tábla (`hu-chardefs.cti`, `hu-hu-g1.ctb`) – az INFOALAP
     gondozásában, ezt használja az NVDA képernyőolvasó is;
  2. a magyar Braille-ábécé nyilvános táblája (lexiq.hu), Unicode
     Braille-jelekkel – a jeleket pontszámokra váltva minden érték egyezik.

Ez a teszt a TELJES táblát ellenőrzi, nem mintavételesen: a felhasználó
„teljes körű ellenőrzést” kért, és egy tanuló-játékban egyetlen rossz betű is
rossz beidegződést okoz.
"""

import sys

import pytest

sys.path.insert(0, "modules_src/jatekok")
from jatekok_mod.jatekok import kviz as K          # noqa: E402


# A HIVATALOS magyar tábla – a fenti két forrásból, kézzel egyeztetve.
HIVATALOS = {
    # alapbetűk
    "a": "1", "b": "12", "c": "14", "d": "145", "e": "15", "f": "124",
    "g": "1245", "h": "125", "i": "24", "j": "245", "k": "13", "l": "123",
    "m": "134", "n": "1345", "o": "135", "p": "1234", "q": "12346",
    "r": "1235", "s": "234", "t": "2345", "u": "136", "v": "1236",
    "w": "2456", "x": "1346", "y": "13456", "z": "126",
    # ékezetes magánhangzók
    "á": "4", "é": "16", "í": "34", "ó": "246", "ö": "12345",
    "ő": "12456", "ú": "346", "ü": "12356", "ű": "23456",
    # kétjegyű mássalhangzók (mindegyik EGY cella)
    "cs": "146", "gy": "1456", "ly": "456", "ny": "1246",
    "sz": "156", "ty": "1256", "zs": "345",
}


@pytest.mark.parametrize("betu,pontok", sorted(HIVATALOS.items()))
def test_minden_betu_a_hivatalos_ertek(betu, pontok):
    assert betu in K._BRAILLE, "hiányzik a táblából: %s" % betu
    assert K._BRAILLE[betu] == pontok, (
        "a(z) %s hibás: nálunk %s, hivatalosan %s"
        % (betu, K._BRAILLE[betu], pontok))


def test_a_tabla_nem_tartalmaz_tobbet_mint_a_hivatalos():
    """Ami nincs a hivatalos táblában, azt ne tanítsuk."""
    tobblet = set(K._BRAILLE) - set(HIVATALOS)
    assert not tobblet, "ismeretlen jelek a táblában: %s" % sorted(tobblet)


def test_a_ket_leggyakoribb_hiba():
    """A felhasználó ezt jelezte, és ez a két érték tér el az angoltól."""
    assert K._BRAILLE["z"] == "126", "a magyar z: 1, 2, 6 (az angol 1356)"
    assert K._BRAILLE["q"] == "12346", "a magyar q: 1,2,3,4,6 (az angol 12345)"


def test_a_ket_betus_jelek_egy_cellat_kapnak():
    """A cs, gy, ly, ny, sz, ty, zs a magyar pontírásban EGYETLEN jel – ez az
    egyik legfontosabb különbség az angolhoz képest."""
    for ketjegyu in ("cs", "gy", "ly", "ny", "sz", "ty", "zs"):
        assert ketjegyu in K._BRAILLE
        assert 1 <= len(K._BRAILLE[ketjegyu]) <= 6


def test_a_dz_es_dzs_nincs_a_tablaban():
    """Ezek NEM önálló jelek: két, illetve három cellával íródnak. Ha
    felvennénk őket, hibás jelet tanítanánk."""
    assert "dz" not in K._BRAILLE and "dzs" not in K._BRAILLE


def test_nincs_ket_azonos_pontkombinacio():
    """Két betűnek nem lehet ugyanaz a jele – ha volna, a „pontokból betű”
    kérdésre két jó válasz létezne, és a játék az egyiket hibásnak mondaná."""
    forditva = {}
    for betu, pontok in K._BRAILLE.items():
        kulcs = K._pontok(pontok)
        assert kulcs not in forditva, (
            "ugyanaz a jel két betűnél: %s és %s" % (forditva.get(kulcs), betu))
        forditva[kulcs] = betu


@pytest.mark.parametrize("pontok", sorted(set(HIVATALOS.values())))
def test_minden_jel_ervenyes_pontokbol_all(pontok):
    """Csak 1–6 közötti pontszám létezik, és egy pont nem ismétlődhet."""
    assert pontok, "üres jel"
    assert all(c in "123456" for c in pontok), "érvénytelen pontszám: %s" % pontok
    assert len(set(pontok)) == len(pontok), "ismétlődő pont: %s" % pontok
    assert pontok == "".join(sorted(pontok)), \
        "a pontokat növekvő sorrendben írjuk: %s" % pontok


# ---------------------------------------------------- Unicode Braille-jel

@pytest.mark.parametrize("pontok,jel", [
    ("1", "⠁"), ("12", "⠃"), ("126", "⠣"), ("12346", "⠯"),
    ("4", "⠈"), ("23456", "⠾"), ("146", "⠩"),
])
def test_a_unicode_jel_helyes(pontok, jel):
    """A Braille-kijelzőn és a képernyőn is látszódjon, amiről szó van."""
    assert K.braille_jel(pontok) == jel


def test_a_jel_pontszam_nelkul_ures_cella():
    assert K.braille_jel("") == "⠀"


# ---------------------------------------------------- a gyakorló készletek

def test_a_keszletek_tartalma():
    nevek = [n for n, _k in K._BRAILLE_KESZLETEK]
    assert "alapbetűk (a-tól z-ig)" in nevek[0]
    assert len(K._BRAILLE_ALAP) == 26
    assert len(K._BRAILLE_EKEZETES) == 9
    assert len(K._BRAILLE_KETJEGYU) == 7
    assert len(K._BRAILLE) == 42, "26 + 9 + 7 = 42 jel"


def test_a_teljes_keszlet_az_utolso():
    _nev, keszlet = K._BRAILLE_KESZLETEK[-1]
    assert keszlet is K._BRAILLE
