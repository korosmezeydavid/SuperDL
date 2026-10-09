"""szakember83 (2026-09-27): a „Minden bolt" nézet ~12 000 sora a ListBoxszal
20 másodpercnél tovább akasztotta meg a programot. A virtuális lista
feltöltése azonnali, és a ListBox-hívásokat ugyanúgy tudja."""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "modules_src" / "akciok"))


@pytest.fixture(scope="module")
def app():
    wx = pytest.importorskip("wx")
    a = wx.App(False)
    yield a


def test_virtualis_lista_gyors_es_listbox_szeru(app):
    import wx
    from akciok_mod.akciokwin import TermekLista
    f = wx.Frame(None)
    lista = TermekLista(f)
    esemenyek = []
    lista.Bind(wx.EVT_LISTBOX, lambda e: esemenyek.append(e.GetInt()))
    t0 = time.time()
    lista.Set(["termék %d, %d forint" % (i, i) for i in range(20000)])
    assert time.time() - t0 < 1.0
    assert lista.GetCount() == 20000
    assert lista.GetString(7) == "termék 7, 7 forint"
    assert lista.OnGetItemText(19999, 0) == "termék 19999, 19999 forint"
    lista.SetSelection(42)
    assert lista.GetSelection() == 42
    lista.SetSelection(3)
    assert lista.GetSelection() == 3          # egyszerre csak egy kijelölt
    assert esemenyek[-1] == 3
    lista.Set([])
    assert lista.GetCount() == 0 and lista.OnGetItemText(0, 0) == ""
    f.Destroy()


def test_sajat_boltjaim_kijeloles_allapota_felolvashato(app, monkeypatch):
    import wx
    from akciok_mod import akciokwin

    monkeypatch.setattr(akciokwin, "_mondd", lambda *_args: None)
    f = wx.Frame(None)
    d = akciokwin.SajatBoltjaimDialog(f, [])
    try:
        assert "nincs kijelölve" in d.lista.GetString(0)
        elso = d._boltok[0][0]
        d._valt()
        assert d.lista.GetSelection() == 0
        assert d.lista.GetString(0).endswith("kijelölve")
        assert "nincs kijelölve" not in d.lista.GetString(0)
        assert elso in d.valasztott
        d._valt()
        assert "nincs kijelölve" in d.lista.GetString(0)
        assert elso not in d.valasztott
    finally:
        d.Destroy()
        f.Destroy()
