"""Modulkör 2026-09-25: hangoskönyv elalvás-időzítő (Könyvek 1.3.6) és a
zene induló mappájának kapcsolója (Zene 1.3.1) – Turai László javaslatai."""
import sys
import time
import types

import pytest

wx = pytest.importorskip("wx")
sys.path.insert(0, "modules_src/konyvek")
sys.path.insert(0, "modules_src/zene")

ABW = pytest.importorskip("konyvek_mod.audiobookwin")
KT = pytest.importorskip("zene_mod.konyvtar")


# ---- hangoskönyv: elalvás -----------------------------------------------

class _Lej:
    def __init__(self):
        self.aktiv = True
        self.hangerok = []
        self.idx = 2
        self.poz = 125.0

    def is_active(self):
        return self.aktiv

    def set_volume(self, v):
        self.hangerok.append(round(v, 3))

    def position(self):
        return self.poz


def _en(vege):
    en = types.SimpleNamespace(player=_Lej(), _hangero=0.8, _alvas_vege=vege,
                               allapot=[], leallitva=[])
    en.SetStatusText = en.allapot.append
    en._stop = lambda: (en.leallitva.append(True),
                        setattr(en.player, "aktiv", False))
    return en


def test_halkulas_a_vege_elott_a_sajat_hangerohoz_merten():
    en = _en(time.time() + 5)           # félúton a 10 mp-es halkulásban
    ABW.AudioBookFrame._alvas_figyel(en)
    assert en.player.hangerok and 0.3 < en.player.hangerok[-1] < 0.5
    assert en.leallitva == []


def test_korabban_nem_nyul_a_hangerohoz():
    en = _en(time.time() + 600)
    ABW.AudioBookFrame._alvas_figyel(en)
    assert en.player.hangerok == []


def test_lejart_idonel_leall_helyet_ment_es_visszaallitja_a_hangerot():
    en = _en(time.time() - 1)
    ABW.AudioBookFrame._alvas_figyel(en)
    assert en.leallitva == [True]
    assert en._alvas_vege == 0.0
    assert en.player.hangerok[-1] == 0.8     # a felhasználó hangereje
    assert "megjegyeztem" in en.allapot[-1]


def test_kikapcsolva_semmit_nem_csinal():
    en = _en(0.0)
    ABW.AudioBookFrame._alvas_figyel(en)
    assert en.player.hangerok == [] and en.leallitva == []


def test_a_leallitas_utan_az_f5_onnan_folytat():
    """Az Esc (és az elalvás) után a `_resume_at` a mostani hely."""
    en = types.SimpleNamespace(player=_Lej(), _resume_at=None,
                               SetStatusText=lambda s: None)
    en.player.stop = lambda: None
    en._save_resume = lambda: None
    ABW.AudioBookFrame._stop(en)
    assert en._resume_at == (2, 125000)


def test_valasztek_szovegek():
    assert ABW.valasztek_szoveg(25) == "25 perc"
    assert ABW.valasztek_szoveg(60) == "1 óra"
    assert ABW.valasztek_szoveg(90) == "másfél óra"
    assert ABW.valasztek_szoveg(120) == "2 óra"
    assert ABW.ALVAS_PERCEK[0] == 5 and ABW.ALVAS_PERCEK[-1] == 120


def test_ctrl_s_a_gomb_es_a_sugo():
    import inspect
    src = inspect.getsource(ABW)
    assert "(wx.ACCEL_CTRL, ord('S'), ids[\"alvas\"])" in src
    assert "Elalvás-&időzítő… (Ctrl+S)" in src
    assert "Ctrl+S: elalvás-időzítő" in ABW._SUGO


def test_a_gombok_alt_betui_nem_utkoznek():
    import inspect
    import re
    blokk = inspect.getsource(ABW.AudioBookFrame._build)
    blokk = blokk.split("for label, fn in (", 1)[1].split("):", 1)[0]
    betuk = [m.lower() for m in re.findall(r'"[^"]*?&(\w)', blokk)]
    assert len(betuk) == len(set(betuk)), betuk


# ---- zene: induló mappa ------------------------------------------------

@pytest.fixture
def beallitas(tmp_path, monkeypatch):
    monkeypatch.setattr(KT, "BEALLITAS", tmp_path / "zene.json")
    return tmp_path / "zene.json"


def test_alapbol_betolti_az_elozo_mappat(beallitas):
    assert KT.indulaskor_betolt() is True


def test_kikapcsolva_megmarad_es_a_mappa_nem_vesz_el(beallitas):
    KT.gyoker_ment(r"D:\Zene")
    KT.indulaskor_betolt_ment(False)
    assert KT.indulaskor_betolt() is False
    assert KT.gyoker_betolt() == r"D:\Zene"


@pytest.fixture(scope="module")
def app():
    a = wx.App(False)
    yield a


def test_kikapcsolva_ures_listaval_indul(app, beallitas, tmp_path,
                                         monkeypatch):
    from zene_mod import zenewin
    (tmp_path / "z").mkdir()
    (tmp_path / "z" / "a.mp3").write_bytes(b"\0" * 16)
    KT.gyoker_ment(str(tmp_path / "z"))
    KT.indulaskor_betolt_ment(False)
    beolvasott = []
    monkeypatch.setattr(zenewin.ZeneFrame, "_beolvas",
                        lambda self, *a, **k: beolvasott.append(a))
    keret = wx.Frame(None)
    w = zenewin.ZeneFrame(keret)
    try:
        assert beolvasott == []
        m = w._menu_epit()
        cimkek = [i.GetItemLabelText() for i in m.GetMenuItems()]
        assert "Induláskor az előző mappa betöltése" in cimkek
        assert "Az előző mappa betöltése" in cimkek
        tetel = next(i for i in m.GetMenuItems() if i.GetItemLabelText()
                     == "Induláskor az előző mappa betöltése")
        assert tetel.IsCheckable() and not tetel.IsChecked()
        m.Destroy()
        w._indulas_valt()
        assert KT.indulaskor_betolt() is True
    finally:
        w._closing = True
        w._ora.Stop()
        w.Destroy()
        keret.Destroy()
        wx.SafeYield()
