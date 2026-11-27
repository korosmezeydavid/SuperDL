"""A három szerkesztő nyíl-lépése és az Alt-menük betűi."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "modules_src" / "supermedia"))
sys.path.insert(0, str(ROOT / "modules_src" / "mediatools"))


def _betuk(menu):
    betuk = []
    for item in menu.GetMenuItems():
        if item.IsSeparator():
            continue
        cimke = item.GetItemLabel().split("\t", 1)[0]
        if "&" in cimke:
            i = cimke.index("&")
            if i + 1 < len(cimke) and cimke[i + 1] != "&":
                betuk.append(cimke[i + 1].casefold())
        al = item.GetSubMenu()
        if al is not None:
            albetu = _betuk(al)
            assert len(albetu) == len(set(albetu)), albetu
    assert len(betuk) == len(set(betuk)), betuk
    return betuk


def _menu_betuk(frame):
    sav = frame.GetMenuBar()
    felsok = []
    for i in range(sav.GetMenuCount()):
        cim = sav.GetMenuLabel(i)
        if "&" in cim:
            j = cim.index("&")
            felsok.append(cim[j + 1].casefold())
        _betuk(sav.GetMenu(i))
    assert len(felsok) == len(set(felsok)), felsok


def test_fulre_lepes_es_shift_kijeloles():
    wx = pytest.importorskip("wx")
    from supermedia_mod.supereditwin import SuperEditorFrame

    app = wx.GetApp() or wx.App(False)
    frame = SuperEditorFrame(None)
    try:
        _menu_betuk(frame)
        frame._step = 0.1
        frame._adjust_step(-1)
        assert frame._step == 0.1
        frame._step = 10.0
        frame._adjust_step(1)
        assert frame._step == 10.0
        frame._adjust_step(-1)
        assert frame._step == 9.9
        frame.load_pcm(b"\x00\x00" * 44100 * 2 * 5, 44100, 2, "teszt")
        frame._step = 2.0
        frame._on_arrow(1, False, True)
        assert frame._sel == (0.0, 2.0)
        frame._on_arrow(1, False, False)
        assert frame._sel is None
        assert frame._pos == 4.0
    finally:
        frame.Destroy()


def test_video_lepes_es_kijeloles_a_szakasz():
    wx = pytest.importorskip("wx")
    from mediatools_mod import videoedit as VE
    from mediatools_mod.videoeditwin import VideoEditFrame

    app = wx.GetApp() or wx.App(False)
    frame = VideoEditFrame(None)
    try:
        _menu_betuk(frame)
        cimkek = []
        sav = frame.GetMenuBar()
        for i in range(sav.GetMenuCount()):
            for item in sav.GetMenu(i).GetMenuItems():
                cimkek.append(item.GetItemLabelText())
        assert "Kép hozzáadása itt…" in cimkek
        frame.editor.clips.append(VE.Clip(path="teszt.mp4", duration=20))
        frame._on_arrow(1, True, False)
        assert frame._step == 2.1
        frame._step = 2.0
        frame._on_arrow(1, False, True)
        assert frame._sel == (0.0, 2.0)
        assert frame._section_markers() == (0.0, 2.0)
    finally:
        frame.Destroy()


def test_kepvideo_lepeskoz():
    wx = pytest.importorskip("wx")
    from mediatools_mod.videowin import VideoComposeFrame

    app = wx.GetApp() or wx.App(False)
    frame = VideoComposeFrame(None)
    try:
        _menu_betuk(frame)
        frame.music = "teszt.mp3"
        frame.duration = 30.0
        frame.edit_panel.Show()
        assert frame._on_arrow(1, True, False) is True
        assert frame._step == 2.1
        frame._step = 2.0
        frame._on_arrow(1, False, True)
        assert frame._sel == (0.0, 2.0)
        assert frame._pos == 2.0
    finally:
        frame.Destroy()
