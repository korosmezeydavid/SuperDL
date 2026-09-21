"""AZ ABLAK KÉTSZER TÖRLÉSE – éles összeomlás, 2026-09-20.

Dávid az első próbán megnyitotta a Beszélő óra ablakot, majd bezárta, és a
program ELSZÁLLT:

    File "...szervezes_mod\\__init__.py", line 194, in open_ora
        dlg.Destroy()
    RuntimeError: wrapped C/C++ object of type OraDialog has been deleted

AZ OK. Az EVT_CLOSE-kezelőnk `e.Skip()`-elt, így az ALAPÉRTELMEZETT wx
kezelőhöz jutott az esemény, ami MAGA hívja a `Destroy()`-t. A megnyitó
`finally: dlg.Destroy()`-ja utána egy már törölt objektumra futott.

A JAVÍTÁS KÉT PONTON:
  1. modális párbeszédnél a zárás `EndModal` – a `Destroy` a HÍVÓÉ;
  2. a hívó `if dlg:`-gel néz rá, él-e még a natív objektum.

Mindkettőt őrizzük: egy javítás önmagában is elég lenne, de ez a hiba a fő
szálon omlasztja össze az egész programot.
"""

import sys

import pytest

wx = pytest.importorskip("wx")
sys.path.insert(0, "modules_src/szervezes")

from superdl import idoora as I           # noqa: E402


@pytest.fixture(scope="module")
def app():
    yield wx.App(False)


@pytest.fixture
def keret(app):
    f = wx.Frame(None)
    yield f
    f.Destroy()
    wx.SafeYield()


class BeszeloBab:
    def mond(self, szoveg, valtozat="", **kw):
        return True


@pytest.fixture
def modul():
    from szervezes_mod import orawin
    return orawin


PROFILOK = [{"nev": "ebédszünet", "hossz_perc": 20, "kozbenso_perc": 5,
             "valtozat": "f2"}]


def _ablak(keret, modul):
    return modul.OraDialog(keret, I.OraMotor(BeszeloBab(), dict(I.ALAP)),
                           BeszeloBab(), PROFILOK,
                           lambda b: None, lambda p: None)


def _kitakarit(ablak, korok=20):
    """A wx a `Destroy()`-t KÉSLELTETI (pending delete), és a tényleges
    törlés csak az üresjárati események feldolgozásakor történik meg.
    Ezért nem elég egy `SafeYield()` – megvárjuk."""
    for _ in range(korok):
        if not ablak:
            return True
        wx.SafeYield()
        try:
            wx.GetApp().ProcessPendingEvents()
        except Exception:
            pass
    return not ablak


def test_modalis_zarasnal_NEM_a_wx_torli_az_ablakot(keret, modul):
    """1. JAVÍTÁS. Modálisnál `EndModal` megy, `Skip()` NEM – így a wx
    alapértelmezett kezelője nem hívja a `Destroy()`-t, és a hívó
    `finally` ága marad az EGYETLEN törlés."""
    d = _ablak(keret, modul)
    try:
        hivott = []
        d.IsModal = lambda: True
        d.EndModal = lambda kod: hivott.append(kod)
        e = wx.CloseEvent(wx.wxEVT_CLOSE_WINDOW)
        d._zaras(e)
        assert hivott == [wx.ID_CANCEL]
        assert e.GetSkipped() is False, \
            "Skip() esetén a wx maga törölné – és jönne a kettős Destroy"
    finally:
        if d:
            d.Destroy()
        _kitakarit(d)


def test_a_torolt_ablakra_az_if_dlg_hamis(keret, modul):
    """2. JAVÍTÁS. Ez a wx dokumentált módja a „él-e még?" kérdésre –
    a megnyitó `finally: if dlg: dlg.Destroy()` ezen áll."""
    d = _ablak(keret, modul)
    d.idozitok.leall()
    d.Destroy()
    assert _kitakarit(d), "a wx nem törölte az ablakot"
    assert not d
    if d:
        d.Destroy()            # ide nem szabad eljutni


def test_a_zaras_utan_a_Destroy_nem_szall_el(keret, modul):
    """A bejelentett eset végigjátszva: zárás, majd a hívó `finally` ága.
    A lényeg, hogy NE dobjon RuntimeError-t."""
    d = _ablak(keret, modul)
    d.ProcessEvent(wx.CloseEvent(wx.wxEVT_CLOSE_WINDOW))
    _kitakarit(d, korok=5)
    if d:                      # a megnyitó `finally` ága
        d.Destroy()
    _kitakarit(d)


def test_a_zaras_megallitja_a_lista_idozitojet(keret, modul):
    """A wx.Timer visszahívása a vezérlő törlése UTÁN is megjöhet."""
    d = _ablak(keret, modul)
    try:
        d.ProcessEvent(wx.CloseEvent(wx.wxEVT_CLOSE_WINDOW))
        assert d.idozitok._halott is True
    finally:
        if d:
            d.Destroy()
        wx.SafeYield()


def test_nem_modalis_ablaknal_a_zaras_tovabbengedi_az_esemenyt(keret, modul):
    """Nem modális esetben marad az alapértelmezett viselkedés – különben
    egy nem modálisan használt ablak sosem záródna be."""
    d = _ablak(keret, modul)
    try:
        assert not d.IsModal()
        e = wx.CloseEvent(wx.wxEVT_CLOSE_WINDOW)
        e.SetCanVeto(True)
        d._zaras(e)
        assert e.GetSkipped() is True
    finally:
        if d:
            d.Destroy()
        wx.SafeYield()
