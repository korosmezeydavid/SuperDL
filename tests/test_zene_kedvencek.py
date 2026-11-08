# -*- coding: utf-8 -*-
"""Zene: KEDVENCEK, KEVERÉS, HANGKIMENET – élő wx-vezérlőkkel.

Amit itt őrzünk, az mind NÉMÁN tud elromlani:

* a kedvenc az ÚTJÁT jegyzi meg, nem a listabeli helyét (átrendezéskor
  különben más számra mutatna);
* egy új beállítás mentése nem törölheti a régieket (a korábbi mentés az
  egész fájlt felülírta a gyökérmappával);
* a keverés VÉGIGMEGY a listán, mielőtt bármit megismételne;
* a hangkimenet MINDKÉT lejátszóra rááll, különben az áttűnéssel behozott
  következő szám a régi eszközön szólalna meg.
"""

import json
import sys

import pytest

wx = pytest.importorskip("wx")
sys.path.insert(0, "modules_src/zene")

KT = pytest.importorskip("zene_mod.konyvtar")


@pytest.fixture(scope="module")
def app():
    a = wx.App(False)
    yield a


@pytest.fixture
def keret(app):
    f = wx.Frame(None)
    yield f
    f.Destroy()
    wx.SafeYield()


@pytest.fixture
def beallitas(tmp_path, monkeypatch):
    monkeypatch.setattr(KT, "BEALLITAS", tmp_path / "zene.json")
    return tmp_path / "zene.json"


def _szamok(tmp_path, nevek):
    ki = []
    for n in nevek:
        p = tmp_path / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\0" * 16)
        ki.append(KT.Szam(str(p), p.stem, p.parent.name))
    return ki


@pytest.fixture
def ablak(keret, beallitas, tmp_path):
    from zene_mod import zenewin
    monkey = []
    w = zenewin.ZeneFrame(keret)
    w._betoltve(_szamok(tmp_path, ["Rock/a.mp3", "Rock/b.mp3",
                                   "Jazz/c.mp3", "Jazz/d.mp3"]), 3)
    yield w
    w._closing = True
    try:
        w._ora.Stop()
    except Exception:
        pass
    w.Destroy()
    wx.SafeYield()
    assert monkey == []


# ---- a beállításfájl ----------------------------------------------------

def test_egy_beallitas_mentese_nem_torli_a_tobbit(beallitas):
    KT.gyoker_ment(r"D:\Zene")
    KT.keveres_ment(True)
    KT.kimenet_ment("Fejhallgató (WI-C100)")
    KT.kedvencek_ment([r"D:\Zene\a.mp3"])
    d = json.loads(beallitas.read_text(encoding="utf-8"))
    assert d["gyoker"] == r"D:\Zene"
    assert d["keveres"] is True
    assert d["kimenet"] == "Fejhallgató (WI-C100)"
    assert d["kedvencek"] == [r"D:\Zene\a.mp3"]
    # és a gyökér újramentése sem viszi el a kedvenceket
    KT.gyoker_ment(r"E:\Masik")
    assert KT.kedvencek_betolt() == [r"D:\Zene\a.mp3"]
    assert KT.keveres_betolt() is True


def test_serult_beallitasbol_ures_ertekek(tmp_path, monkeypatch):
    p = tmp_path / "zene.json"
    p.write_text("{ez nem json", encoding="utf-8")
    monkeypatch.setattr(KT, "BEALLITAS", p)
    assert KT.kedvencek_betolt() == []
    assert KT.keveres_betolt() is False
    assert KT.kimenet_betolt() == ""


def test_a_kedvencek_nem_ismetlodnek(beallitas):
    KT.kedvencek_ment([r"D:\a.mp3", r"D:\A.MP3", r"D:\b.mp3"])
    assert KT.kedvencek_betolt() == [r"D:\a.mp3", r"D:\b.mp3"]


def test_szam_utbol_cim_es_mappa():
    s = KT.szam_utbol(r"D:\Zene\Rock\Fenyes szelek.mp3")
    assert s.cim == "Fenyes szelek"
    assert s.mappa == "Rock"


# ---- kedvencek a felületen ---------------------------------------------

def test_kedvencnek_jelolt_szam_megmarad_a_fajlban(ablak):
    ablak.lista.SetSelection(1)
    ablak._kedvenc_valt()
    assert KT.kedvencek_betolt() == [ablak._szamok[1].ut]


def test_ujra_megnyomva_leveszi(ablak):
    ablak.lista.SetSelection(1)
    ablak._kedvenc_valt()
    ablak._kedvenc_valt()
    assert KT.kedvencek_betolt() == []


def test_a_kedvenc_sor_eleje_mondja_hogy_kedvenc(ablak):
    ablak.lista.SetSelection(0)
    ablak._kedvenc_valt()
    # a jelzés a sor ELEJÉN: nyilazáskor azonnal hallatszik
    assert ablak.lista.GetString(0).startswith("kedvenc, ")
    assert not ablak.lista.GetString(1).startswith("kedvenc, ")


def test_kedvenc_nezet_csak_a_kedvenceket_mutatja(ablak):
    ablak.lista.SetSelection(2)
    ablak._kedvenc_valt()
    ablak._kedvenc_nezet_valt()
    assert ablak._kedvenc_nezet is True
    assert len(ablak._szamok) == 1
    assert ablak._szamok[0].cim == "c"


def test_ures_kedvencekre_nem_valt_at(ablak):
    ablak._kedvenc_nezet_valt()
    assert ablak._kedvenc_nezet is False


def test_a_kedvenc_utat_jegyez_nem_indexet(ablak, tmp_path):
    """Átrendezés után is UGYANARRA a számra mutat."""
    ablak.lista.SetSelection(3)          # Rock/b
    kivalasztott = ablak._szamok[3].ut
    ablak._kedvenc_valt()
    # a zenemappa újraolvasva, MÁS sorrendben
    ujak = list(reversed(ablak._osszes))
    ablak._betoltve(ujak, 3)
    ablak._kedvenc_nezet_valt()
    assert [s.ut for s in ablak._szamok] == [kivalasztott]


def test_az_elveszett_kedvenc_hianyzikkent_latszik(ablak, tmp_path):
    ablak.lista.SetSelection(0)
    ablak._kedvenc_valt()
    ut = ablak._szamok[0].ut
    ablak._kedvenc_nezet_valt()
    import os
    os.remove(ut)
    ablak._nezet_frissit(mondja=False)
    assert "hiányzik" in ablak.lista.GetString(0)


def test_nezetvaltas_utan_ugyanaz_a_szam_az_aktualis(ablak):
    ablak.lista.SetSelection(2)
    ablak._kedvenc_valt()
    ut = ablak._szamok[2].ut
    ablak._index = 2
    ablak._kedvenc_nezet_valt()
    assert ablak._szamok[ablak._index].ut == ut


# ---- keverés ------------------------------------------------------------

def test_a_keveres_megmarad_a_kovetkezo_inditasra(ablak, keret):
    ablak._keveres_valt()
    assert KT.keveres_betolt() is True
    from zene_mod import zenewin
    masik = zenewin.ZeneFrame(keret)
    try:
        assert masik._keveres is True
    finally:
        masik._closing = True
        masik._ora.Stop()
        masik.Destroy()


def test_a_keveres_vegigmegy_mielott_ismetel(ablak):
    ablak._keveres_valt()
    ablak._index = 0
    latott = []
    for _ in range(3):
        k = ablak._kovetkezo_index()
        latott.append(k)
        ablak._index = k
    assert sorted(latott) == [1, 2, 3]      # a 0 az induló, a többi egyszer


def test_keveres_nelkul_sorban_megy(ablak):
    ablak._index = 2
    assert ablak._kovetkezo_index() == 3
    ablak._index = 3
    assert ablak._kovetkezo_index() == 0


def test_a_nyilak_keveresben_is_a_lista_szerint_lepnek(ablak):
    """A navigáció kiszámítható marad – ezt a `_lep` forrása rögzíti."""
    import inspect
    from zene_mod import zenewin
    src = inspect.getsource(zenewin.ZeneFrame._lep)
    assert "_kovetkezo_index" not in src
    assert "_zsakbol" not in src


def test_egyetlen_szamnal_nem_akad_el(ablak, tmp_path):
    ablak._betoltve(_szamok(tmp_path, ["egy/x.mp3"]), 1)
    ablak._keveres_valt()
    ablak._index = 0
    assert ablak._kovetkezo_index() == 0


# ---- hangkimenet --------------------------------------------------------

class LejatszoBab:
    def __init__(self):
        self.kimenetek = []
        self.fo_hangero = 1.0

    def kimenet_allit(self, a):
        self.kimenetek.append(a)

    def szol(self):
        return False


def test_a_valasztott_kimenet_megmarad_es_ravaltunk(ablak, monkeypatch):
    from superdl import audioengine as AE
    monkeypatch.setattr(AE, "eszkozok", lambda: [
        ("", "Rendszer alapértelmezett kimenete"),
        ("Fejhallgató (WI-C100)", "Fejhallgató (WI-C100)")])
    bab = LejatszoBab()
    ablak._lejatszo = bab
    monkeypatch.setattr(wx.SingleChoiceDialog, "ShowModal", lambda s: wx.ID_OK)
    monkeypatch.setattr(wx.SingleChoiceDialog, "GetSelection", lambda s: 1)
    ablak._kimenet_valaszt()
    assert ablak._kimenet == "Fejhallgató (WI-C100)"
    assert KT.kimenet_betolt() == "Fejhallgató (WI-C100)"
    assert bab.kimenetek == ["Fejhallgató (WI-C100)"]


def test_a_megse_nem_valtoztat_semmit(ablak, monkeypatch):
    from superdl import audioengine as AE
    monkeypatch.setattr(AE, "eszkozok", lambda: [
        ("", "Rendszer alapértelmezett kimenete"), ("X", "X")])
    monkeypatch.setattr(wx.SingleChoiceDialog, "ShowModal",
                        lambda s: wx.ID_CANCEL)
    ablak._kimenet_valaszt()
    assert ablak._kimenet == ""
    assert KT.kimenet_betolt() == ""


def test_az_eltunt_eszkozt_bemondja_nem_nemul_el(ablak):
    ablak._allapot = lambda sz, mondja=True: ablak.__dict__.setdefault(
        "_mondott", []).append(sz)
    ablak._kimenet_valtott("Fejhallgató (WI-C100)", "")
    assert any("nem" in s and "érhető el" in s
               for s in ablak.__dict__["_mondott"])


def test_a_magatol_valtast_bemondja(ablak):
    ablak._allapot = lambda sz, mondja=True: ablak.__dict__.setdefault(
        "_mondott", []).append(sz)
    ablak._kimenet_valtott("", "Fejhallgató (WI-C100)")
    assert any("átváltott" in s for s in ablak.__dict__["_mondott"])


def test_a_kevero_mindket_lejatszot_atallitja():
    """⚠️ Csak az aktívat átállítani kevés: az áttűnés a MÁSIKAT hozza be."""
    import inspect
    from zene_mod import keverolejatszo
    src = inspect.getsource(keverolejatszo.KeveroLejatszo.kimenet_allit)
    assert "self._a" in src and "self._b" in src


# ---- a felület épsége ---------------------------------------------------

@pytest.mark.parametrize("kedvenc_nezet", [False, True])
def test_a_helyi_menuben_nincs_utkozo_gyorsbetu(ablak, kedvenc_nezet):
    """Két azonos Alt-betű a menüben: az egyik művelet elérhetetlen lenne.

    A TÉNYLEGESEN létrejövő menüt nézzük, mindkét nézetben – forrásból az
    elágazások két felirata hamis ütközésnek látszana."""
    import re
    if kedvenc_nezet:
        ablak.lista.SetSelection(0)
        ablak._kedvenc_valt()
        ablak._kedvenc_nezet_valt()
    m = ablak._menu_epit()
    try:
        betuk = []
        for it in m.GetMenuItems():
            betuk += [x.lower()
                      for x in re.findall(r"&(\w)", it.GetItemLabel())]
        assert len(betuk) == len(set(betuk)), betuk
        assert len(betuk) >= 6
    finally:
        m.Destroy()


def test_a_hol_tartunk_bemondja_a_harom_uj_allapotot(ablak):
    ablak._allapot = lambda sz, mondja=True: ablak.__dict__.setdefault(
        "_mondott", []).append(sz)
    ablak._keveres_valt()
    ablak.lista.SetSelection(0)
    ablak._kedvenc_valt()
    ablak._hol_tartunk()
    mondat = ablak.__dict__["_mondott"][-1]
    assert "keverés be" in mondat
    assert "kedvenc" in mondat


def test_minden_uj_muvelet_bekotve_billentyure(ablak):
    import inspect
    from zene_mod import zenewin
    src = inspect.getsource(zenewin.ZeneFrame._on_key)
    for betu, fv in (("D", "_kedvenc_valt"), ("B", "_kedvenc_nezet_valt"),
                     ("K", "_keveres_valt"), ("H", "_kimenet_valaszt")):
        assert 'ord("%s")' % betu in src
        assert fv in src


def test_a_sugo_mind_a_harom_ujdonsagot_leirja():
    from zene_mod import zenewin
    for kulcs in ("Ctrl+D", "Ctrl+B", "Ctrl+K", "Ctrl+H",
                  "KEDVENCEK", "KEVERÉS", "HANGKIMENET"):
        assert kulcs in zenewin.SUGO, kulcs


def test_queue_picker_space_marks_in_order_without_playback(ablak, monkeypatch):
    from types import SimpleNamespace
    from zene_mod import zenewin

    sounded = []
    monkeypatch.setattr(ablak, "_indit", lambda i: sounded.append(i))
    dialog = zenewin.SorDialog(ablak, ablak._osszes, [])
    try:
        focus = [dialog.lista]
        monkeypatch.setattr(wx.Window, "FindFocus", lambda: focus[-1])
        space = SimpleNamespace(GetKeyCode=lambda: wx.WXK_SPACE)
        dialog.lista.SetSelection(2)
        dialog._billentyu(space)
        dialog.lista.SetSelection(0)
        dialog._billentyu(space)
        assert [s.ut for s in dialog.szamai()] == [ablak._osszes[i].ut for i in (2, 0)]
        assert dialog.lista.GetString(0).startswith("bejelölve, ")
        assert dialog.lista.GetSelection() == 0
        focus.append(dialog.sorlista)
        dialog.sorlista.SetSelection(0)
        dialog._billentyu(SimpleNamespace(GetKeyCode=lambda: wx.WXK_DELETE))
        assert [s.ut for s in dialog.szamai()] == [ablak._osszes[0].ut]
        assert not sounded
    finally:
        dialog.Destroy()


def test_queue_waits_then_plays_ordered_and_stops(ablak, tmp_path, monkeypatch):
    from types import SimpleNamespace
    played = []
    external = _szamok(tmp_path, ["Other/external.mp3"])[0]
    missing = KT.szam_utbol(str(tmp_path / "missing.mp3"))
    monkeypatch.setattr(KT, "hossz", lambda path: 4)
    monkeypatch.setattr(ablak, "_motor", lambda: SimpleNamespace(
        jatszik=lambda path, duration: played.append(path),
        attunes_ra=lambda *args: pytest.fail("The queue must wait for the actual end"),
    ))
    ablak._indit(0)
    ablak._keveres = ablak._ismetles = True
    ablak._sor_alkalmaz([missing, external, ablak._szamok[1]])
    ablak._attunes_ideje()
    assert played == [ablak._szamok[0].ut]
    ablak._szam_vege()
    assert ablak._index == -1 and ablak._szolo_szam is external
    ablak._szam_vege()
    assert ablak._index == 1
    ablak._szam_vege()
    assert played == [ablak._szamok[0].ut, external.ut, ablak._szamok[1].ut]
    assert not ablak._lejatszas_folyamatban and ablak._sorban is None
    ablak._lep(1)
    assert played[-1] == ablak._szamok[2].ut


def test_named_lists_keep_order_and_do_not_replace_settings(beallitas, tmp_path):
    tracks = _szamok(tmp_path, ["Alma.mp3", "Barack.mp3"])
    KT.gyoker_ment(str(tmp_path))
    saved = {"Esti válogatás": [tracks[1].ut, tracks[0].ut]}
    KT.listak_ment(saved)
    assert KT.listak_betolt() == saved
    assert KT.gyoker_betolt() == str(tmp_path)
    saved["Második"] = [tracks[0].ut]
    KT.listak_ment(saved)
    assert KT.listak_betolt() == saved


def test_picker_cancel_does_not_replace_pending_queue(ablak, monkeypatch):
    from zene_mod import zenewin
    from collections import deque

    class CancelDialog:
        def __init__(self, parent, tracks, queue):
            assert list(queue) == [ablak._szamok[2]]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def ShowModal(self):
            return wx.ID_CANCEL

    ablak._sorban = deque([ablak._szamok[2]])
    monkeypatch.setattr(zenewin, "SorDialog", CancelDialog)
    ablak._sor_kivalaszt()
    assert list(ablak._sorban) == [ablak._szamok[2]]


def test_stale_end_callback_cannot_advance_the_new_track(ablak, monkeypatch):
    from types import SimpleNamespace

    waiting, called = [], []
    monkeypatch.setattr(wx, "CallAfter", waiting.append)
    motor = SimpleNamespace(nemzedek=1)
    ablak._lejatszo = motor
    ablak._lejatszo_kesobb(called.append, "old")
    motor.nemzedek = 2
    ablak._lejatszo_kesobb(called.append, "new")
    for callback in waiting:
        callback()
    assert called == ["new"]
