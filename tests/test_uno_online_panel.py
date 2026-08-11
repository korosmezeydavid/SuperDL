# -*- coding: utf-8 -*-
"""UNO ONLINE panel – hálózati kör teszt hamis (mockolt) Ably-busszal.

Két UnoOnlinePanel (host + vendég) egy közös, szinkron „buszon": lobbi →
osztás (PRIVÁT kéz-routing) → teljes parti a győztesig → szünet. Élő hálózat
nélkül, determinisztikusan. Ahol nincs GUI (fejnélküli CI display nélkül), a
teszt kihagyja magát."""
import importlib

import pytest

wx = pytest.importorskip("wx")
BASE = "modules_src.jatekok.jatekok_mod"
UO = importlib.import_module(BASE + ".uno_online")
SZK = importlib.import_module(BASE + ".jatekok.sajat")
netroom = importlib.import_module(BASE + ".netroom")


@pytest.fixture
def app():
    try:
        a = wx.App()
    except Exception:                      # nincs megjeleníthető felület
        pytest.skip("nincs GUI ehhez a teszthez")
    yield a
    try:
        a.Destroy()
    except Exception:
        pass


class _Bus:
    def __init__(self):
        self.listeners = []


def _fake_szoba_gyar(bus):
    class FakeSzoba:
        def __init__(self, kod, nev):
            self.kod, self.nev, self._cb = kod, nev, None
            bus.listeners.append(self)

        def elerheto(self):
            return True

        def figyel(self, cb):
            self._cb = cb

        def kuld(self, tipus, adat=None):
            u = {"tipus": tipus, "ki": self.nev, "adat": adat or {}}
            for s in list(bus.listeners):
                if s._cb:
                    s._cb(u)

        def leallit(self):
            pass
    return FakeSzoba


def _setup(monkeypatch):
    bus = _Bus()
    monkeypatch.setattr(wx, "CallAfter", lambda f, *a, **k: f(*a, **k))
    monkeypatch.setattr(netroom, "ably_kulcs", lambda: "x")
    monkeypatch.setattr(netroom, "szobakod", lambda: "ABCD")
    monkeypatch.setattr(netroom, "NetSzoba", _fake_szoba_gyar(bus))


class _FM:
    selfvoice = None
    settings = {}


def test_online_kor_privat_kez_es_teljes_parti(app, monkeypatch):
    _setup(monkeypatch)
    frame = wx.Frame(None)
    host = UO.UnoOnlinePanel(frame, _FM())
    client = UO.UnoOnlinePanel(frame, _FM())
    for p in (host, client):              # ne nyisson szín-párbeszédet
        p._szin_ha_wild = lambda k: ("piros" if k and k[0] == "szín" else None)

    host.nev_mezo.SetValue("Host")
    host._uj_szoba(None)
    client.nev_mezo.SetValue("Vendeg")
    client.kod_mezo.SetValue("ABCD")
    client._csatlakozas(None)
    assert host._jatekosok == ["Host", "Vendeg"]

    host._indit(None)
    # PRIVÁT kéz: mindenki csak a SAJÁT kezét kapja
    assert host._kezem == host._motor.kez("Host")
    assert client._kezem == host._motor.kez("Vendeg")
    assert len(host._kezem) == 7 and len(client._kezem) == 7
    pub = host._motor.allapot_publikus()
    assert "kezek" not in pub and pub["lapszamok"] == {"Host": 7, "Vendeg": 7}

    panels = {"Host": host, "Vendeg": client}

    def drive(p):
        if p._fazis == "huzas_utan":
            p._kirak()
            return
        for i, k in enumerate(p._kezem):
            if SZK._uno_rakhato(k, p._szin, p._ertek):
                p._kez_lst.SetSelection(i)
                p._kirak()
                return
        p._akcio("huz")

    import random
    random.seed(5)
    for _step in range(3000):
        if host._motor.fazis == "vege":
            break
        drive(panels[host._soron])
    assert host._motor.fazis == "vege"
    assert host._motor.gyoztes in ("Host", "Vendeg")
    assert "VÉGE" in host._felso.GetValue() and "VÉGE" in client._felso.GetValue()

    host.leallit()
    client.leallit()
    frame.Destroy()


def test_szunet_valtas(app, monkeypatch):
    _setup(monkeypatch)
    frame = wx.Frame(None)
    p = UO.UnoOnlinePanel(frame, _FM())
    p._kezeld({"tipus": "szunet", "ki": "Host", "adat": {"be": True}})
    assert p._szunet is True
    p._kezeld({"tipus": "szunet", "ki": "Host", "adat": {"be": False}})
    assert p._szunet is False
    frame.Destroy()
