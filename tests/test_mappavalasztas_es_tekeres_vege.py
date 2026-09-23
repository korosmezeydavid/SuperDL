# -*- coding: utf-8 -*-
"""Három javítás a 4.6.13 utáni jelentésekből.

1. „EZT A MAPPÁT VÁLASZTOM" a KIJELÖLT almappát vegye (Turai László):
   „Akkor nyitja meg a mappát, amivel néztem, ha bele is megyek és úgy
   választom ki. Ha csak ráállok és úgy, akkor nem."

2. A SÁV VÉGÉRE TEKERVE lépjen a következőre (Turai László):
   „Ha egy fájlt a végére tekerek, nem megy tovább a következőre a
   lejátszás, de ha hagyom végig menni, akkor igen."

3. A ZENELEJÁTSZÓ JEGYEZZE MEG A HANGERŐT (Szabó László):
   „Minden újbóli bekapcsoláskor 100%-kal indul."
"""

import inspect
import json
import sys

import pytest

wx = pytest.importorskip("wx")

from superdl import audioengine as AE      # noqa: E402
from superdl import fajlvalaszto as FV     # noqa: E402


@pytest.fixture(scope="module")
def app():
    return wx.App(False)


@pytest.fixture
def keret(app):
    f = wx.Frame(None)
    yield f
    f.Destroy()
    wx.SafeYield()


# ======================================================================
# 1. A MAPPAVÁLASZTÁS
# ======================================================================

@pytest.fixture
def fa(tmp_path):
    for nev in ("Alma", "Banan", "Cseresznye"):
        (tmp_path / nev).mkdir()
    (tmp_path / "jegyzet.txt").write_text("x", encoding="utf-8")
    return tmp_path


def _valaszto(keret, mappa):
    d = FV.FajlValaszto(keret, "Mappa", str(mappa), (), False, True, None)
    return d


def test_kijeloles_nelkul_a_jelenlegi_hely(keret, fa):
    d = _valaszto(keret, fa)
    try:
        assert d.valasztott_mappa() == str(fa)
    finally:
        d.Destroy()


def test_a_kijelolt_almappa_lesz_a_valasztas(keret, fa):
    """⚠️ EZ VOLT A HIBA: eddig MINDIG a jelenlegi helyet adta vissza."""
    d = _valaszto(keret, fa)
    try:
        i = d.mappa_lista.FindString("Banan")
        assert i >= 0
        d.mappa_lista.SetSelection(i)
        assert d.valasztott_mappa() == str(fa / "Banan")
    finally:
        d.Destroy()


def test_a_belepes_torli_a_kijelolest(keret, fa):
    """A `Set()` kijelölés nélkül tölti újra a listát – tehát a kijelölés
    MINDIG szándékos."""
    d = _valaszto(keret, fa)
    try:
        d.mappa_lista.SetSelection(0)
        d._frissit()
        assert d.mappa_lista.GetSelection() == wx.NOT_FOUND
        assert d.valasztott_mappa() == str(fa)
    finally:
        d.Destroy()


def test_a_gomb_felirata_megmondja_melyiket_valasztja(keret, fa):
    """Vakon ez a lényeg: a gomb maga mondja meg, mit fog csinálni."""
    d = _valaszto(keret, fa)
    try:
        assert "jelenlegi" in d.ok_gomb.GetLabel().lower()
        i = d.mappa_lista.FindString("Cseresznye")
        d.mappa_lista.SetSelection(i)
        d._gomb_felirat()
        assert "Cseresznye" in d.ok_gomb.GetLabel()
    finally:
        d.Destroy()


def test_a_fajlvalaszto_modban_nincs_ok_gomb_felirat_valtas(keret, fa):
    """Fájlválasztásnál a mappalista csak navigáció – a gomb ne változzon."""
    d = FV.FajlValaszto(keret, "Fájl", str(fa), (), False, False, None)
    try:
        cimke = d.ok_gomb.GetLabel()
        d.mappa_lista.SetSelection(0)
        d._gomb_felirat()
        assert d.ok_gomb.GetLabel() == cimke
    finally:
        d.Destroy()


def test_eltunt_almappa_eseten_a_jelenlegi_hely(keret, fa):
    """Ha a kijelölt mappát közben letörölték, ne adjunk vissza nem létezőt."""
    d = _valaszto(keret, fa)
    try:
        i = d.mappa_lista.FindString("Alma")
        d.mappa_lista.SetSelection(i)
        (fa / "Alma").rmdir()
        assert d.valasztott_mappa() == str(fa)
    finally:
        d.Destroy()


# ======================================================================
# 2. A SÁV VÉGÉRE TEKERÉS
# ======================================================================

def test_a_tekeres_utani_ures_lejatszas_VEGE_es_nem_hiba():
    """⚠️ Ez akadályozta meg a következő sávra lépést: tekerés után az
    ffmpeg nem ad hangot, `started` hamis marad, és a régi kód
    „hiba: a forrás nem játszható le"-t küldött."""
    src = inspect.getsource(AE.Player._feed)
    assert "kezdo_pozicio" in src
    # a tekeréses ág a „vége"-t küldi
    i = src.index("kezdo_pozicio > 0")
    assert '"vége"' in src[i:i + 700]


def test_a_kezdo_poziciot_a_szal_indulasakor_kapjuk_el():
    """Egy újabb `play()` átírhatná a `_start_offset`-et menet közben."""
    src = inspect.getsource(AE.Player._feed)
    assert src.index("kezdo_pozicio = self._start_offset") < src.index("while")


def test_a_valodi_hiba_tovabbra_is_hiba():
    """Tekerés NÉLKÜL (0-ról indulva) a néma forrás továbbra is hiba."""
    src = inspect.getsource(AE.Player._feed)
    assert "hiba: a forrás nem játszható le" in src


def test_a_hangoskonyv_a_vege_jelzesre_lep_tovabb():
    sys.path.insert(0, "modules_src/konyvek")
    ap = pytest.importorskip("konyvek_mod.audiobook_player")
    src = inspect.getsource(ap.AudioBookPlayer._on_state)
    assert "vége" in src
    assert "_on_track_end" in src


# ======================================================================
# 3. A ZENELEJÁTSZÓ HANGEREJE
# ======================================================================

@pytest.fixture
def zene_kt(tmp_path, monkeypatch):
    sys.path.insert(0, "modules_src/zene")
    KT = pytest.importorskip("zene_mod.konyvtar")
    monkeypatch.setattr(KT, "BEALLITAS", tmp_path / "zene.json")
    return KT


def test_a_hangero_alapbol_teljes(zene_kt):
    assert zene_kt.hangero_betolt() == 1.0


def test_a_hangero_megmarad(zene_kt, tmp_path):
    zene_kt.hangero_ment(0.3)
    assert abs(zene_kt.hangero_betolt() - 0.3) < 1e-9
    d = json.loads((tmp_path / "zene.json").read_text(encoding="utf-8"))
    assert abs(d["hangero"] - 0.3) < 1e-9


def test_a_hangero_hatarok_koze_szorul(zene_kt):
    zene_kt.hangero_ment(5.0)
    assert zene_kt.hangero_betolt() == 1.0
    zene_kt.hangero_ment(-2.0)
    assert zene_kt.hangero_betolt() == 0.0


def test_a_romlott_ertek_nem_robban(zene_kt):
    zene_kt.beallit(hangero="nem szám")
    assert zene_kt.hangero_betolt() == 1.0


def test_a_hangero_mentese_es_betoltese_be_van_kotve():
    sys.path.insert(0, "modules_src/zene")
    zw = pytest.importorskip("zene_mod.zenewin")
    init = inspect.getsource(zw.ZeneFrame.__init__)
    allit = inspect.getsource(zw.ZeneFrame._hangero_allit)
    assert "hangero_betolt" in init
    assert "hangero_ment" in allit


def test_a_hangero_nem_torli_a_tobbi_beallitast(zene_kt):
    zene_kt.gyoker_ment(r"D:\Zene")
    zene_kt.hangero_ment(0.5)
    assert zene_kt.gyoker_betolt() == r"D:\Zene"
