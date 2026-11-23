"""A tallózó két ága: a Tab oldalt vált, a vágólap a másik mappát nevezi meg."""

import os
import sys

import wx

sys.path.insert(0, "modules_src/fajlok")
from fajlok_mod.masolo import beillesztes_oka
from fajlok_mod.tallozowin import TallozoFrame, keres, lista_sor


class _Fo:
    selfvoice = None


def test_ket_ag_oldalt_valt_es_vagolapra_tesz(tmp_path):
    app = wx.App.Get() or wx.App(False)
    bal = tmp_path / "bal"
    jobb = tmp_path / "jobb"
    bal.mkdir()
    jobb.mkdir()
    (bal / "level.txt").write_text("szia", encoding="utf-8")
    frame = TallozoFrame(_Fo(), str(bal), ketag=True)
    try:
        assert frame._ketag
        assert frame._jobb.doboz.IsShown()
        assert frame._bal.lista.GetName() == "Bal oldal tartalma"
        assert frame._jobb.lista.GetName() == "Jobb oldal tartalma"
        frame._jobb.mappa = str(jobb)
        frame._tolts(frame._jobb)
        frame._aktiv = frame._bal
        frame._bal.lista.SetSelection(0)
        frame._masikra()
        assert frame._aktiv is frame._jobb
        frame._aktiv = frame._bal
        frame._vagolapra("masol")
        assert frame._vagolap == [str(bal / "level.txt")]
        assert frame._vagolap_muv == "masol"
        allapot = frame.GetStatusBar().GetStatusText()
        assert "Másolás" in allapot
        assert "jobb oldal" in allapot
        frame._aktiv = frame._jobb
        assert frame._cel_ag() is frame._jobb
        assert beillesztes_oka(frame._vagolap, frame._cel_ag().mappa) == ""
        frame._ketag_allit(False, mondja=False)
        assert not frame._jobb.doboz.IsShown()
        frame._vagolapra("masol")
        assert "két ág" in frame.GetStatusBar().GetStatusText()
    finally:
        frame.Destroy()
        app.Yield()


def test_minden_kijeloles_tobb_elemet_visz_a_vagolapra(tmp_path):
    app = wx.App.Get() or wx.App(False)
    bal = tmp_path / "bal"
    jobb = tmp_path / "jobb"
    bal.mkdir()
    jobb.mkdir()
    (bal / "a.txt").write_text("a", encoding="utf-8")
    (bal / "b.txt").write_text("b", encoding="utf-8")
    frame = TallozoFrame(_Fo(), str(bal), ketag=True)
    try:
        frame._jobb.mappa = str(jobb)
        frame._tolts(frame._jobb)
        frame._aktiv = frame._bal
        frame._mindet()
        assert len(frame.lista.GetSelections()) == 2
        frame._vagolapra("athelyez")
        assert len(frame._vagolap) == 2
        assert frame._vagolap_cel is frame._jobb
        assert "2 elem" in frame.GetStatusBar().GetStatusText()
    finally:
        frame.Destroy()
        app.Yield()


def test_az_enter_a_fokuszban_levo_meghajtot_nyitja(tmp_path):
    app = wx.App.Get() or wx.App(False)
    belso = tmp_path / "Users"
    belso.mkdir()
    (belso / "jegyzet.txt").write_text("a", encoding="utf-8")
    frame = TallozoFrame(_Fo(), ketag=True)
    try:
        frame._aktiv.nevek = [str(tmp_path), "Z:\\"]
        frame._aktiv.mappa = ""
        frame.lista.Set([str(tmp_path), "Z:\\"])
        frame.lista.SetSelection(0)
        assert frame._kivalasztott() == str(tmp_path)
        frame._nyit()
        assert os.path.normcase(frame._mappa) == os.path.normcase(str(tmp_path))
        assert any(nev.lower() == "users" for nev in frame._nevek)
    finally:
        frame.Destroy()
        app.Yield()


def test_a_kulso_mappak_menu_megvan(tmp_path):
    app = wx.App.Get() or wx.App(False)
    frame = TallozoFrame(_Fo(), ketag=True)
    try:
        sav = frame.GetMenuBar()
        assert sav.FindMenu("Külső mappák") != wx.NOT_FOUND
    finally:
        frame.Destroy()
        app.Yield()


def test_a_mappa_sora_a_nevvel_kezdodik():
    assert lista_sor("Users", True).startswith("Users")
    assert lista_sor("jegyzet.txt", False) == "jegyzet.txt"


def test_kereses_nevreszletre_es_tipusra(tmp_path):
    (tmp_path / "Users").mkdir()
    (tmp_path / "Users" / "film.mkv").write_text("a", encoding="utf-8")
    (tmp_path / "masik.txt").write_text("b", encoding="utf-8")
    (tmp_path / "MKV-jegyzet.txt").write_text("c", encoding="utf-8")
    nevek = keres(str(tmp_path), "user", "nev")
    assert any(ut.endswith(os.path.join("Users")) or ut.endswith("Users") for ut in nevek)
    tipus = keres(str(tmp_path), "mkv", "tipus")
    assert len(tipus) == 1
    assert tipus[0].lower().endswith(".mkv")
    assert keres(str(tmp_path), ".mkv", "tipus") == tipus
