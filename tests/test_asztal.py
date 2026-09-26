"""Asztal (Petrus József ötlete): ABC-sorrend, betűre ugrás körbeéréssel,
modul-menüpontok nyilvántartása, a kiválasztott pont tényleg lefut."""
import pytest

from superdl import asztal as A


def test_cimke_es_gyorsbill():
    assert A.cimke("&Akciós újság…\tCtrl+Alt+A") == "Akciós újság"
    assert A.gyorsbill("&Akciós újság…\tCtrl+Alt+A") == "Ctrl+Alt+A"
    assert A.cimke("Rock && Roll...") == "Rock & Roll"
    assert A.gyorsbill("Modulkezelő") == ""
    assert A.megjelenes("Óra", "") == "Óra"
    assert A.megjelenes("Óra", "Ctrl+K") == "Óra (Ctrl+K)"


def test_kovetkezo_korbeer_es_ekezet():
    nevek = ["Akciós újság", "Álmos rádió", "Beállítások", "Óra",
             "Olvasó", "Zene"]
    assert A.kovetkezo(nevek, -1, "a") == 0
    assert A.kovetkezo(nevek, 0, "a") == 1       # Á is „a"
    assert A.kovetkezo(nevek, 1, "A") == 0       # körbeér
    assert A.kovetkezo(nevek, 0, "o") == 3
    assert A.kovetkezo(nevek, 3, "ó") == 4
    assert A.kovetkezo(nevek, 4, "o") == 3
    assert A.kovetkezo(nevek, 2, "x") == -1
    assert A.kovetkezo([], -1, "a") == -1
    assert A.kovetkezo(["Zene"], 0, "z") == 0    # egyetlen: önmaga


def test_abc_ekezet_nelkul():
    nevek = ["Zene", "Óra", "Akciók", "Ábécé", "olvasó"]
    s = sorted(nevek, key=A.rendezo_kulcs)
    assert s == ["Ábécé", "Akciók", "olvasó", "Óra", "Zene"]


def test_egyertelmusit():
    ki = A.egyertelmusit([("Beállítások", "", "Super M"),
                          ("Beállítások", "", "Rádió"),
                          ("Óra", "Ctrl+K", "Eszközök")])
    assert ki[0][0] == "Beállítások – Super M"
    assert ki[1][0] == "Beállítások – Rádió"
    assert ki[2] == ("Óra", "Óra (Ctrl+K)")


@pytest.fixture(scope="module")
def app():
    wx = pytest.importorskip("wx")
    a = wx.App(False)
    yield a


def test_elemek_es_megnyitas(app):
    import wx
    from superdl.coremod import WxHost
    f = wx.Frame(None)
    mb = wx.MenuBar()
    m_tools = wx.Menu()
    core = m_tools.Append(wx.ID_ANY, "&Internet-teszt…\tCtrl+Alt+I")
    kihagy = m_tools.Append(wx.ID_ANY, "Nem Asztal-pont")
    mb.Append(m_tools, "&Eszközök")
    f.SetMenuBar(mb)
    host = WxHost(f)
    hivas = []
    sub = host.add_submenu("&Eszközök", "&Szervezés")
    it = host.add_menu_item(sub, "&Akciós újság…", lambda: hivas.append(1),
                            shortcut="Ctrl+Alt+A")
    host.add_menu_item(host.add_menu("&Média"), "&Zene",
                       lambda: hivas.append(2))
    assert it.GetId() in host.modul_menu_idk
    el = A.elemek(f, host.modul_menu_idk, [core.GetId()])
    szovegek = [e[0] for e in el]
    assert szovegek == ["Akciós újság (Ctrl+Alt+A)",
                        "Internet-teszt (Ctrl+Alt+I)", "Zene"]
    assert kihagy.GetId() not in [e[2] for e in el]

    w = A.AsztalAblak(f, host)
    assert A.AsztalAblak(f, host) is w          # egy példány
    w._nyit(0)
    for _ in range(5):
        wx.Yield()
    assert hivas == [1]
    assert getattr(f, "_asztal_win", None) is None

    host.remove_menu_item(it)
    assert it.GetId() not in host.modul_menu_idk
    f.Destroy()
