# -*- coding: utf-8 -*-
"""A Könyvek modul a BEÉPÍTETT fájlválasztót használja, ne a rendszerét.

Dr. Kiss István 4.6.4-es összeomlás-naplójában a program NATÍVAN kilépett,
miközben a fő szál a `bookwin._on_pick_book` fájlválasztójában járt. A
`superdl/fajlvalaszto.py` saját docstringje szerint pontosan ezért készült:
a Windows fájlválasztójába idegen bővítmények épülnek be, és ha egyikük
elszáll, viszi magával az egész programot. A megoldás megvolt – a Könyvek
modul nem használta.
"""
import importlib
import inspect
import re

import pytest

BASE = "modules_src.konyvek.konyvek_mod"
V = pytest.importorskip(BASE + ".valaszto")

ABLAKOK = ("bookwin", "audiobookwin", "readerwin")


def _forras(nev):
    return inspect.getsource(importlib.import_module(f"{BASE}.{nev}"))


@pytest.mark.parametrize("nev", ABLAKOK)
def test_nincs_tobbe_kozvetlen_rendszerdialogus(nev):
    """A modulablakok NEM nyithatnak közvetlenül rendszer-dialógust."""
    sz = _forras(nev)
    assert not re.search(r"wx\.(FileDialog|DirDialog)\(", sz), (
        f"{nev}: maradt közvetlen rendszer-fájlválasztó")


@pytest.mark.parametrize("nev", ABLAKOK)
def test_a_kozos_valasztot_hasznaljak(nev):
    sz = _forras(nev)
    assert "valaszto.egy_fajl(" in sz or "valaszto.egy_mappa(" in sz


def test_a_valaszto_maga_hasznalhat_rendszerdialogust():
    """A visszaesés SZÁNDÉKOS: inkább a régi viselkedés, mint működésképtelen
    menüpont, ha a beépített választó valamiért nem érhető el."""
    sz = inspect.getsource(V)
    assert "wx.FileDialog(" in sz and "wx.DirDialog(" in sz


# ---- a választó viselkedése -------------------------------------------

def test_egy_fajl_a_beepitettet_hivja(monkeypatch):
    hivas = {}

    class _Fv:
        @staticmethod
        def valassz_fajlokat(szulo, cim, kit, tobb=True, mondd=None):
            hivas.update(cim=cim, kit=kit, tobb=tobb)
            return [r"C:\konyvek\alma.epub"]

    monkeypatch.setattr(V, "_beepitett", lambda: _Fv)
    ut = V.egy_fajl(None, "Könyv kiválasztása", V.KONYV_KITERJESZTESEK)
    assert ut == r"C:\konyvek\alma.epub"
    assert hivas["tobb"] is False           # EGY fájl kell, nem több
    assert ".epub" in hivas["kit"]


def test_megse_valasztas_ures_szoveg(monkeypatch):
    class _Fv:
        @staticmethod
        def valassz_fajlokat(*a, **k):
            return []

    monkeypatch.setattr(V, "_beepitett", lambda: _Fv)
    assert V.egy_fajl(None, "cím") == ""


def test_egy_mappa_a_beepitettet_hivja(monkeypatch):
    class _Fv:
        @staticmethod
        def valassz_mappat(szulo, cim, kezdo, mondd=None):
            return kezdo + r"\ki"

    monkeypatch.setattr(V, "_beepitett", lambda: _Fv)
    assert V.egy_mappa(None, "Célmappa", r"C:\a") == r"C:\a\ki"


def test_ha_a_beepitett_elszall_visszaesunk(monkeypatch):
    """A visszaesés nem elmélet: le is van tesztelve."""
    class _Fv:
        @staticmethod
        def valassz_fajlokat(*a, **k):
            raise RuntimeError("nem megy")

    monkeypatch.setattr(V, "_beepitett", lambda: _Fv)
    monkeypatch.setattr(V, "_nativ_fajl",
                        lambda szulo, cim, wildcard: r"C:\tartalek.txt")
    assert V.egy_fajl(None, "cím") == r"C:\tartalek.txt"


def test_ha_nincs_beepitett_visszaesunk(monkeypatch):
    monkeypatch.setattr(V, "_beepitett", lambda: None)
    monkeypatch.setattr(V, "_nativ_mappa",
                        lambda szulo, cim, kezdo: r"C:\tartalek")
    assert V.egy_mappa(None, "cím") == r"C:\tartalek"


def test_a_kiterjesztesek_pontosak():
    assert set(V.KONYV_KITERJESZTESEK) == {".txt", ".docx", ".epub", ".pdf"}
    for k in (".mp3", ".m4a", ".flac", ".opus", ".wav"):
        assert k in V.HANG_KITERJESZTESEK
    for k in V.KONYV_KITERJESZTESEK + V.HANG_KITERJESZTESEK:
        assert k.startswith(".") and k == k.lower()
