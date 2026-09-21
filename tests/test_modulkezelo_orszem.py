# -*- coding: utf-8 -*-
"""A Modulkezelő őrszeme: háttér-visszahívás megszűnt ablakra.

Ujfalusi Zoltán jelentése (2026-09-14):

    File "superdl\\modmanagerwin.py", line 228, in _populate
    RuntimeError: wrapped C/C++ object of type ListCtrl has been deleted

Karcsi ugyanezt kívülről így látta: „nem záródik be a program, csak az
ablaka tűnik el."
"""
from pathlib import Path

import pytest

GYOKER = Path(__file__).resolve().parent.parent
FORRAS = (GYOKER / "superdl" / "modmanagerwin.py").read_text(encoding="utf-8")


def test_minden_hatter_visszahivas_az_orszemen_megy_at():
    """Egyetlen `wx.CallAfter` sem mehet közvetlenül az ablak metódusára.

    Két kivétel megengedett, mindkettő indokolt: maga az őrszem belseje, és
    a kilépés, ami SZÁNDÉKOSAN az ablak bezárása UTÁN, a FŐ ablakon fut."""
    rossz = []
    for i, sor in enumerate(FORRAS.split("\n"), 1):
        if "wx.CallAfter(" not in sor:
            continue
        if "wx.CallAfter(biztonsagos)" in sor:
            continue
        if "kilepes" in sor:
            continue
        rossz.append((i, sor.strip()))
    assert not rossz, (
        "Ezek a visszahívások megkerülik az őrszemet: %r" % rossz)


def test_az_orszem_letezik():
    assert "def _kesobb(self, fv, *args)" in FORRAS
    assert "self._halott = False" in FORRAS
    assert "self._halott = True" in FORRAS


def test_a_halott_ablakra_nem_fut_le_a_visszahivas():
    """Viselkedés, nem forráskód: halott ablakon a visszahívás elmarad."""
    wx = pytest.importorskip("wx")
    from superdl import modmanagerwin

    hivasok = []
    sorbanallo = []

    class Alablak:
        _halott = False

        def __bool__(self):
            return True

        _kesobb = modmanagerwin.ModuleManagerFrame._kesobb

    eredeti = wx.CallAfter
    wx.CallAfter = lambda fv, *a: sorbanallo.append(lambda: fv(*a))
    try:
        a = Alablak()
        a._kesobb(lambda x: hivasok.append(x), "elso")
        a._halott = True                    # közben bezárták az ablakot
        a._kesobb(lambda x: hivasok.append(x), "masodik")
        for f in sorbanallo:
            f()
    finally:
        wx.CallAfter = eredeti
    assert hivasok == [], (
        "A bezárt ablakra is lefutott a visszahívás: %r" % hivasok)


def test_az_elo_ablakon_lefut():
    wx = pytest.importorskip("wx")
    from superdl import modmanagerwin

    hivasok = []
    sorbanallo = []

    class Alablak:
        _halott = False

        def __bool__(self):
            return True

        _kesobb = modmanagerwin.ModuleManagerFrame._kesobb

    eredeti = wx.CallAfter
    wx.CallAfter = lambda fv, *a: sorbanallo.append(lambda: fv(*a))
    try:
        a = Alablak()
        a._kesobb(lambda x: hivasok.append(x), "elso")
        for f in sorbanallo:
            f()
    finally:
        wx.CallAfter = eredeti
    assert hivasok == ["elso"]


def test_a_megsemmisulesi_hibat_elnyeli():
    """Ha az ablak a sorban állás alatt tűnik el, a RuntimeError nem
    szállhat fel a fő szálra – pont az volt az elkapatlan kivétel."""
    wx = pytest.importorskip("wx")
    from superdl import modmanagerwin

    sorbanallo = []

    class Alablak:
        _halott = False

        def __bool__(self):
            return True

        _kesobb = modmanagerwin.ModuleManagerFrame._kesobb

    def robban():
        raise RuntimeError(
            "wrapped C/C++ object of type ListCtrl has been deleted")

    eredeti = wx.CallAfter
    wx.CallAfter = lambda fv, *a: sorbanallo.append(lambda: fv(*a))
    try:
        Alablak()._kesobb(robban)
        for f in sorbanallo:
            f()                              # nem szabad kivételt dobnia
    finally:
        wx.CallAfter = eredeti
