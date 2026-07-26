"""netdialog: az AKADÁLYMENTES, kétgombos „Nincs internet” felugró őrei.

A felhasználó kérte: MINDEN net-igényes művelet elején egy villámgyors próba, és
ha nincs net, egy világos felugró KÉT gombbal – Újratesztelés (siker → bezár) és
OK (teszt nélkül eltűnik). Ezek a tesztek kijelző (wx.App) nélkül is futnak: a
be/kiágazást és a párbeszéd SZERZŐDÉSÉT ellenőrzik.
"""

import inspect

import pytest

pytest.importorskip("wx")                       # a modul wx-et importál
netdialog = pytest.importorskip("superdl.netdialog")


def test_van_net_eseten_nincs_felugro(monkeypatch):
    """Ha van net, az ensure_online AZONNAL True-t ad, párbeszéd nélkül."""
    monkeypatch.setattr(netdialog.netcheck, "online", lambda **k: True)
    # a _show meghívása hiba lenne (nincs is szükség rá) – ha mégis, buknánk
    monkeypatch.setattr(netdialog, "_show",
                        lambda *a, **k: pytest.fail("nem lett volna szabad "
                                                    "felugrót nyitni"))
    assert netdialog.ensure_online(None, "a teszthez") is True


def test_nincs_net_eseten_felnyitja_a_felugrot(monkeypatch):
    """Ha nincs net (GUI-szálon), felnyitja a párbeszédet a helyes szöveggel, és
    annak eredményét adja vissza."""
    monkeypatch.setattr(netdialog.netcheck, "online", lambda **k: False)
    seen = {}

    def fake_show(parent, mihez, speak):
        seen["parent"] = parent
        seen["mihez"] = mihez
        return True                              # az újratesztelés „sikerült”

    monkeypatch.setattr(netdialog, "_show", fake_show)
    assert netdialog.ensure_online("PARENT", "a rádió hallgatásához") is True
    assert seen["mihez"] == "a rádió hallgatásához"
    assert seen["parent"] == "PARENT"


def test_a_probe_maga_sose_blokkol(monkeypatch):
    """Ha maga a kapcsolat-próba kivételt dob, a program NEM akad el – True."""
    def boom(**k):
        raise OSError("váratlan")
    monkeypatch.setattr(netdialog.netcheck, "online", boom)
    assert netdialog.ensure_online(None, "bármi") is True


def test_a_felugro_szerzodese():
    """A párbeszéd szerződése: az OK gomb ID_CANCEL (Esc is bezárja, teszt
    nélkül), az Újratesztelés az alapértelmezett (Enter), siker esetén a
    self.online igazra vált és ID_OK-kal zár."""
    src = inspect.getsource(netdialog.NoInternetDialog)
    assert "wx.ID_CANCEL" in src                 # OK gomb → Esc is bezárja
    assert "SetDefault" in src                   # Újratesztelés = Enter
    assert "EndModal(wx.ID_OK)" in src           # siker → True-val zár
    assert "self.online = True" in src
    # a teszt háttérszálon fut, hogy a modális ne fagyjon
    assert "threading.Thread" in src
