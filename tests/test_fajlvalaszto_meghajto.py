# -*- coding: utf-8 -*-
"""A beépített fájlválasztó: a meghajtó gyökeréből KI KELL tudni lépni.

Dávid jelzése: „ha kiérek például a c meghajtóból nem hajlandó kilépni és nem
tudok például az mmc-re váltani vagy bármi másra."

Az ok: a `C:\\` szülője önmaga, tehát a `_szulo()` ott „Ez már a legfelső
szint"-et mondott. Volt ugyan egy legördülő gyorshely a meghajtókkal, de
listában nyilazva ez zsákutcának LÁTSZOTT – és a felhasználó azt hiszi el,
amit a program mond. A választót a médiakonvertáló és a Zene modul is
használja, tehát ez két helyen is falat jelentett.
"""
import inspect
import os

import pytest

from superdl import fajlvalaszto as FV


def test_a_gep_szint_a_meghajtokat_adja(monkeypatch):
    monkeypatch.setattr(FV, "meghajtok", lambda: ["C:\\", "E:\\"])
    mappak, fajlok = FV.tartalom(FV.GEP)
    assert mappak == ["C:\\", "E:\\"]
    assert fajlok == []


def test_a_gyorshelyek_elso_eleme_a_gep():
    h = FV.gyorshelyek()
    assert h[0][1] == FV.GEP
    assert "gép" in h[0][0].lower()


def test_a_meghajtok_a_gyorshelyek_kozott_is_ott_vannak(monkeypatch):
    monkeypatch.setattr(FV, "meghajtok", lambda: ["C:\\", "Q:\\"])
    utak = [ut for _n, ut in FV.gyorshelyek()]
    assert "C:\\" in utak and "Q:\\" in utak


def test_a_meghajtokat_MINDIG_frissen_kerdezzuk():
    """A pendrive és a kártya menet közben is bekerülhet – nem elég az
    induláskor egyszer összeszedni."""
    f = inspect.getsource(FV.gyorshelyek)
    assert "meghajtok()" in f, "a gyorshelyek hívja a friss lekérdezést"
    g = inspect.getsource(FV.meghajtok)
    assert "isdir" in g


@pytest.mark.skipif(os.name != "nt", reason="Windows-útvonalak")
@pytest.mark.parametrize("ut", ["C:\\", "D:\\", "c:\\"])
def test_gyoker_e_igaz_a_meghajto_gyokerere(ut):
    assert FV.gyoker_e(ut)


@pytest.mark.skipif(os.name != "nt", reason="Windows-útvonalak")
@pytest.mark.parametrize("ut", ["C:\\Users", "C:\\Users\\msn", "D:\\Zene\\a"])
def test_gyoker_e_hamis_a_mappara(ut):
    assert not FV.gyoker_e(ut)


def test_gyoker_e_ures_utra_hamis():
    assert not FV.gyoker_e("")
    assert not FV.gyoker_e(None)


# ---- a navigáció maga (hamis ablakkal, wx nélkül) -----------------------

class _HamisValaszto:
    """A `_szulo` és a `_belep` a `self`-en csak néhány dolgot használ."""

    def __init__(self, mappa):
        self._mappa = mappa
        self._mappak = []
        self.mondatok = []
        self.frissitve = 0

    def _mondd(self, sz):
        self.mondatok.append(sz)

    def _frissit(self, csendes=True):
        self.frissitve += 1
        return "frissitve"

    class _Mezo:
        def SetValue(self, v):
            pass

    class _Lista:
        def SetFocus(self):
            pass

        def GetSelection(self):
            return 0

    szuro_mezo = _Mezo()
    mappa_lista = _Lista()


def _szulo(mappa):
    h = _HamisValaszto(mappa)
    FV.FajlValaszto._szulo(h)
    return h


@pytest.mark.skipif(os.name != "nt", reason="Windows-útvonalak")
def test_a_meghajto_gyokerebol_a_GEP_szintre_jutunk():
    """EZ A HIBA LÉNYEGE: a C:\\-ből fel kell jutni a meghajtók listájára."""
    h = _szulo("C:\\")
    assert h._mappa == FV.GEP
    assert h.frissitve == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows-útvonalak")
def test_a_mappabol_a_szulobe_jutunk():
    h = _szulo("C:\\Users\\msn")
    assert h._mappa == "C:\\Users"


def test_a_GEP_szintrol_mar_nem_megy_feljebb():
    h = _szulo(FV.GEP)
    assert h._mappa == FV.GEP
    assert any("meghajtók" in m for m in h.mondatok)
    assert h.frissitve == 0


def test_a_GEP_szinten_a_belepes_a_meghajtot_nyitja(monkeypatch):
    h = _HamisValaszto(FV.GEP)
    h._mappak = ["C:\\", "E:\\"]
    monkeypatch.setattr(os.path, "isdir", lambda p: True)
    FV.FajlValaszto._belep(h)
    assert h._mappa == "C:\\", "a meghajtó gyökerét NEM szabad összefűzni"


def test_a_sima_belepes_valtozatlan(monkeypatch):
    h = _HamisValaszto(os.path.join("C:\\", "Zene"))
    h._mappak = ["Rock"]
    monkeypatch.setattr(os.path, "isdir", lambda p: True)
    FV.FajlValaszto._belep(h)
    assert h._mappa == os.path.join("C:\\", "Zene", "Rock")


def test_ctrl_d_egyenesen_a_meghajtokra_visz():
    """Két út a meghajtókhoz: a Backspace fölfelé, és a Ctrl+D azonnal.
    Aki mélyen bent van egy mappaszerkezetben, annak a Backspace sok lépés —
    és ebből egyszer már volt zsákutca."""
    f = inspect.getsource(FV.FajlValaszto._bill)
    assert 'ord("D")' in f and "GEP" in f
    cimke = inspect.getsource(FV.FajlValaszto.__init__)
    assert "Ctrl+D: meghajtók" in cimke, "a címke mondja is meg"


def test_a_GEP_szint_nem_adhato_vissza_mappakent():
    """Üres utat nem szabad eredményként visszaadni."""
    f = inspect.getsource(FV.FajlValaszto._kesz)
    assert "GEP" in f
    assert "Előbb válassz egy meghajtót" in f
