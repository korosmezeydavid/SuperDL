# -*- coding: utf-8 -*-
"""A médiakereső ELŐHALLGATÁSÁBAN a bal/jobb nyíl tekerjen.

Nagy Károly, 2026-09-21: „A média keresővel megkeresem, kiadja a listát.
Ott kiválasztom, ami érdekelne, és szóközzel elindítom a lejátszást. Hang
fel, le van rendesen, de jobbra balra tekerni nem tudok, mert az erre
szolgáló nyilak nyomkodására nem történik semmi. Miután letöltöttem a
fájlt, nincs vele baj."

Igaza volt: a `_player_key` csak az Escape-et, a szóközt és a fel/le
nyilat ismerte. A tekerés NEM volt bekötve – nem elromlott, hanem sosem
volt meg.
"""

import pytest

wx = pytest.importorskip("wx")

from superdl import searchwin as SW       # noqa: E402


# ---- az időszöveg (felolvasásra) ---------------------------------------

def test_ido_szoveg_felolvashato_alakot_ad():
    assert SW._ido_szoveg(0) == "0 másodperc"
    assert SW._ido_szoveg(45) == "45 másodperc"
    assert SW._ido_szoveg(60) == "1 perc"
    assert SW._ido_szoveg(150) == "2 perc 30 másodperc"


def test_ido_szoveg_nem_kettospontos():
    """A képernyőolvasók a „2:30"-at hol időnek, hol aránynak mondják."""
    assert ":" not in SW._ido_szoveg(150)


def test_negativ_ido_nem_robban():
    assert SW._ido_szoveg(-5) == "0 másodperc"


# ---- a tekerés viselkedése (valódi wx nélkül, bábu lejátszóval) --------

class LejatszoBab:
    def __init__(self, pos=100.0, aktiv=True, szunetel=False):
        self._pos = pos
        self._aktiv = aktiv
        self._szunet = szunetel
        self.seek_hivasok = []
        self.pause_hivasok = 0
        self.volume = 0.7

    def is_active(self):
        return self._aktiv

    def is_paused(self):
        return self._szunet

    def position(self):
        return self._pos

    def seek(self, pos):
        self.seek_hivasok.append(pos)
        self._pos = pos
        self._szunet = False        # a valódi Player is feloldja a szünetet

    def pause(self):
        self.pause_hivasok += 1
        self._szunet = True


class AblakBab:
    """Csak annyi, amennyit a `_teker` használ."""

    _teker = SW.MediaSearchFrame._teker

    def __init__(self, lejatszo):
        self.player = lejatszo
        self._tekert = False
        self.mondott = []

    def _announce(self, sz):
        self.mondott.append(sz)


def test_elore_tekeres_a_pozicio_ele_ugrik():
    b = LejatszoBab(pos=100.0)
    a = AblakBab(b)
    a._teker(SW.TEKERES_MP)
    assert b.seek_hivasok == [110.0]
    assert a.mondott == ["1 perc 50 másodperc."]


def test_vissza_tekeres():
    b = LejatszoBab(pos=100.0)
    a = AblakBab(b)
    a._teker(-SW.TEKERES_MP)
    assert b.seek_hivasok == [90.0]


def test_a_nulla_ala_nem_megy():
    """Negatív kezdőpont az ffmpegnek értelmezhetetlen volna."""
    b = LejatszoBab(pos=3.0)
    a = AblakBab(b)
    a._teker(-SW.TEKERES_MP)
    assert b.seek_hivasok == [0.0]


def test_a_tekeres_jelzi_magat_a_visszahivasnak():
    """⚠️ Enélkül a tekerés utáni „lejátszás" állapot ÚJRA felolvasná a
    teljes indító mondatot, és a pozíció bemondása elveszne alatta."""
    b = LejatszoBab()
    a = AblakBab(b)
    a._teker(SW.TEKERES_MP)
    assert a._tekert is True


def test_szunetben_szunetben_marad():
    """A `seek()` a `play()`-en át megy, az pedig feloldja a szünetet."""
    b = LejatszoBab(pos=50.0, szunetel=True)
    a = AblakBab(b)
    a._teker(SW.TEKERES_MP)
    assert b.pause_hivasok == 1
    assert b.is_paused() is True
    assert "szünetben" in a.mondott[-1]


def test_lejatszas_nelkul_megmondja_hogy_nincs_mit_tekerni():
    b = LejatszoBab(aktiv=False)
    a = AblakBab(b)
    a._teker(SW.TEKERES_MP)
    assert b.seek_hivasok == []
    assert "nem megy lejátszás" in a.mondott[-1].lower()


# ---- a billentyűk tényleg be vannak kötve ------------------------------

def test_a_billentyukezelo_ismeri_a_bal_es_jobb_nyilat():
    import inspect
    src = inspect.getsource(SW.MediaSearchFrame._player_key)
    assert "WXK_LEFT" in src and "WXK_RIGHT" in src
    assert "_teker" in src


def test_a_ctrl_nyil_nagyobbat_lep():
    import inspect
    src = inspect.getsource(SW.MediaSearchFrame._player_key)
    assert "ControlDown" in src
    assert SW.TEKERES_NAGY_MP > SW.TEKERES_MP


def test_a_sugo_es_a_bemondas_is_emliti_a_tekerest():
    """Vakon az a funkció, amiről nem szól a program, nem is létezik."""
    import inspect
    sugo = inspect.getsource(SW.MediaSearchFrame._help)
    allapot = inspect.getsource(SW.MediaSearchFrame._on_player_state)
    for sz in (sugo, allapot):
        assert "tekerés" in sz


def test_a_tekeres_utani_lejatszas_allapot_nem_olvassa_fel_ujra_a_cimet():
    import inspect
    src = inspect.getsource(SW.MediaSearchFrame._on_player_state)
    # a jelző vizsgálata a cím felolvasása ELŐTT kell hogy legyen
    assert src.index("_tekert") < src.index("Lejátszás:")
