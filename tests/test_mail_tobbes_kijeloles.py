# -*- coding: utf-8 -*-
"""A levéllista TÖBBSZÖRÖS kijelölésű – ott a GetSelection() bezárja a programot.

Dr. Kiss István 4.6.4-es naplója (2026-09-11):

    File "mailwin.py", line 5423, in _on_key
        self._megnyit()
    File "mailwin.py", line 4983, in _megnyit
        info = self._kivalasztott()
    File "mailwin.py", line 4968, in _kivalasztott
        i = sel[0] if sel else self.level_lista.GetSelection()
    wx._core.wxAssertionError: C++ assertion "!HasMultipleSelection()" failed
    ... GetSelection() can't be used with multiple-selection listboxes

Vagyis: Enter a levéllistán, amikor semmi nincs kijelölve → a KIVÉTEL a fő
szálon szállt el, és az EGÉSZ program bezárult. Nem a levélmodul – a SuperDL.
"""
import importlib
import inspect
import re

import pytest

BASE = "modules_src.mail.mail_mod"
MW = pytest.importorskip(BASE + ".mailwin")


def _forras():
    return inspect.getsource(MW)


def _hivas(szoveg: str):
    """Valódi HÍVÁS egy vezérlőn (`valami.GetSelection()`) – a megjegyzésben
    vagy docstringben szereplő puszta említés nem az."""
    return re.search(r"\w\.GetSelection\(\)", szoveg)


def test_a_levellista_tobbszoros_kijelolesu():
    """Ez a teszt alapfeltevése – ha ez megváltozik, a többi is átgondolandó."""
    assert re.search(r"self\.level_lista\s*=\s*wx\.ListBox\([^)]*LB_EXTENDED",
                     _forras(), re.S)


def test_sehol_nem_hivunk_GetSelection_t_a_levellistan():
    """A konkrét összeomlás: `self.level_lista.GetSelection()`."""
    talalatok = [m for m in re.finditer(r"self\.level_lista\.GetSelection\(\)",
                                        _forras())]
    assert not talalatok, ("a level_lista LB_EXTENDED – a GetSelection() "
                           "C++ assertion-t dob és bezárja a programot")


def test_a_kivalasztott_csak_GetSelections_t_hasznal():
    f = inspect.getsource(MW.MailFrame._kivalasztott)
    assert not _hivas(f)
    seged = inspect.getsource(MW.MailFrame._elso_kijelolt_index)
    assert "GetSelections()" in seged and not _hivas(seged)


def test_kijeloles_nelkul_minusz_egy():
    class _Hamis:
        def GetSelections(self):
            return ()

    class _Ablak:
        level_lista = _Hamis()
    assert MW.MailFrame._elso_kijelolt_index(_Ablak()) == -1


def test_elso_kijelolt_tobb_kijelolesnel():
    class _Hamis:
        def GetSelections(self):
            return (3, 7, 9)

    class _Ablak:
        level_lista = _Hamis()
    assert MW.MailFrame._elso_kijelolt_index(_Ablak()) == 3


def test_a_megnyitas_nem_nema_kijeloles_nelkul():
    """Az Enter eddig vagy összeomlott, vagy némán nem csinált semmit."""
    f = inspect.getsource(MW.MailFrame._megnyit)
    assert "Nincs kijelölt levél" in f


def test_ujrarajzolas_megtartja_MINDEN_kijelolest():
    f = inspect.getsource(MW.MailFrame._lista_ujrarajzol)
    assert "GetSelections()" in f
    assert not _hivas(f)


def test_lista_index_nem_kockaztat_tobbes_listan():
    """A stílust nézzük, nem a kivételre bízzuk magunkat."""
    import wx
    f = inspect.getsource(MW.MailFrame._lista_index)
    assert "LB_EXTENDED" in f and "GetWindowStyleFlag" in f

    class _Tobbes:
        def GetSelections(self):
            return ()

        def GetWindowStyleFlag(self):
            return wx.LB_EXTENDED

        def GetSelection(self):            # ide NEM szabad eljutni
            raise AssertionError("GetSelection() hívás többes listán!")

    assert MW.MailFrame._lista_index(_Tobbes()) == -1


def test_lista_index_egyszeres_listan_mukodik():
    import wx

    class _Egyes:
        def GetSelections(self):
            return ()

        def GetWindowStyleFlag(self):
            return wx.LB_SINGLE

        def GetSelection(self):
            return 4

    assert MW.MailFrame._lista_index(_Egyes()) == 4
