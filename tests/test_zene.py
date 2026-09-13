# -*- coding: utf-8 -*-
"""A Zene modul: a lehető legegyszerűbb lejátszó.

A hangsúly azon van, ami NÉMÁN tud elromlani: a mappabejárás, és hogy az
áttűnés hibája SOHA ne hagyja abba a zenét.
"""
import importlib
import inspect
import json
import threading

import pytest

BASE = "modules_src.zene.zene_mod"
KT = pytest.importorskip(BASE + ".konyvtar")


def _zenetar(tmp_path, szerkezet):
    for rel in szerkezet:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\0" * 16)
    return tmp_path


# ---- mappabejárás -------------------------------------------------------

def test_minden_almappat_bejar(tmp_path):
    _zenetar(tmp_path, [
        "a.mp3",
        "Rock/b.flac",
        "Rock/1970-es/c.ogg",
        "Klasszikus/Bach/Kantatak/d.m4a",
    ])
    szamok, mappak = KT.beolvas(tmp_path)
    assert len(szamok) == 4
    assert mappak >= 5          # gyökér + Rock + 1970-es + Klasszikus + Bach…


def test_a_nem_zenei_fajlokat_kihagyja(tmp_path):
    _zenetar(tmp_path, ["jo.mp3", "borito.jpg", "jegyzet.txt", "video.mp4"])
    szamok, _ = KT.beolvas(tmp_path)
    assert [s.cim for s in szamok] == ["jo"]


def test_a_rejtett_mappat_kihagyja(tmp_path):
    _zenetar(tmp_path, ["jo.mp3", ".lomtar/rossz.mp3"])
    szamok, _ = KT.beolvas(tmp_path)
    assert [s.cim for s in szamok] == ["jo"]


def test_rendezett_mappa_majd_cim_szerint(tmp_path):
    _zenetar(tmp_path, ["Zebra/b.mp3", "Zebra/a.mp3", "Alma/c.mp3"])
    szamok, _ = KT.beolvas(tmp_path)
    assert [(s.mappa, s.cim) for s in szamok] == [
        ("Alma", "c"), ("Zebra", "a"), ("Zebra", "b")]


def test_a_felirat_a_cim_es_a_mappa(tmp_path):
    _zenetar(tmp_path, ["Rock/Fenyes szelek.mp3", "gyokerben.mp3"])
    szamok, _ = KT.beolvas(tmp_path)
    feliratok = [s.felirat() for s in szamok]
    assert "Fenyes szelek – Rock" in feliratok
    assert "gyokerben" in feliratok       # gyökérben nincs mappanév


def test_nem_letezo_mappa_nem_hal_meg(tmp_path):
    assert KT.beolvas(tmp_path / "nincs-ilyen") == ([], 0)
    assert KT.beolvas("") == ([], 0)
    assert KT.beolvas(None) == ([], 0)


def test_a_beolvasas_felbehagyhato(tmp_path):
    """Az ablak bezárása ne várjon egy hálózati meghajtóra."""
    _zenetar(tmp_path, [f"m{i}/x.mp3" for i in range(20)])
    megall = threading.Event()
    megall.set()
    szamok, _ = KT.beolvas(tmp_path, megall)
    assert szamok == []


# ---- a megjegyzett gyökér -----------------------------------------------

def test_gyoker_mentes_es_visszatoltes(tmp_path, monkeypatch):
    monkeypatch.setattr(KT, "BEALLITAS", tmp_path / "zene.json")
    assert KT.gyoker_betolt() == ""
    KT.gyoker_ment(r"D:\Zene")
    assert KT.gyoker_betolt() == r"D:\Zene"
    assert json.loads((tmp_path / "zene.json").read_text(
        encoding="utf-8"))["gyoker"] == r"D:\Zene"


def test_serult_beallitas_nem_hal_meg(tmp_path, monkeypatch):
    p = tmp_path / "zene.json"
    p.write_text("{ ez nem json", encoding="utf-8")
    monkeypatch.setattr(KT, "BEALLITAS", p)
    assert KT.gyoker_betolt() == ""


# ---- idő kimondva --------------------------------------------------------

@pytest.mark.parametrize("mp,vart", [
    (0, "0 másodperc"), (5, "5 másodperc"), (60, "1 perc"),
    (205, "3 perc 25 másodperc"), (3600, "60 perc")])
def test_ido_szoveg(mp, vart):
    assert KT.ido_szoveg(mp) == vart


def test_ido_szoveg_nem_hal_meg_negativra():
    assert KT.ido_szoveg(-10) == "0 másodperc"


# ---- hossz: hiányzó ffprobe nem állíthatja meg a zenét -------------------

def test_hossz_nulla_ha_nincs_ffprobe(monkeypatch):
    monkeypatch.setattr(KT, "_ffprobe", lambda: "")
    assert KT.hossz(r"C:\barmi.mp3") == 0.0


def test_hossz_nulla_ures_utra():
    assert KT.hossz("") == 0.0


# ---- az áttűnés SOHA ne hagyja némán -------------------------------------

def test_az_attunes_hibaja_visszaesik_egyszeru_valtasra():
    kl = importlib.import_module(BASE + ".keverolejatszo")
    f = inspect.getsource(kl.KeveroLejatszo._attun)
    assert "self.attunes_megy = False" in f
    assert "self.jatszik(" in f, ("ha a második hangfolyam nem megy, a "
                                 "következő számnak AKKOR IS szólnia kell")


def test_a_vege_jelzes_akkor_is_lep_ha_nincs_hossz():
    """Nincs ffprobe → nincs áttűnés-időzítés → a „vége” jelzés visz tovább."""
    win = importlib.import_module(BASE + ".zenewin")
    f = inspect.getsource(win.ZeneFrame._szam_vege)
    assert "_indit(k)" in f


def test_az_attunes_szal_nem_allithatja_le_az_UJ_szamot():
    """A SAJÁT hibám, még kiadás előtt elkapva.

    Ha a felhasználó ÁTTŰNÉS KÖZBEN másik számra nyilaz, a `jatszik()` új
    nemzedéket nyit — a még futó halványító szál viszont a végén `ki.stop()`-ot
    hívna arra a lejátszóra, amin már az ÚJ szám szól. A zene elhallgatna,
    méghozzá pont attól, amit a kényelemért építettünk."""
    kl = importlib.import_module(BASE + ".keverolejatszo")
    f = inspect.getsource(kl.KeveroLejatszo._attun)
    # a magyarázó docstring nélkül – csak a VÉGREHAJTOTT kód számít
    kod = f.split('"""')[-1]
    assert kod.count("gen != self._nemzedek") >= 3, (
        "a nemzedéket a ciklus elején, a hangerő-írás előtt ÉS a lezáráskor "
        "is ellenőrizni kell")
    # a régi lejátszó leállítása CSAK nemzedék-ellenőrzés után jöhet
    assert kod.rindex("gen != self._nemzedek") < kod.rindex("ki.stop()")
    # a hangerő-írás zár alatt van (különben ráülhet az új számra)
    assert "with self._zar:" in kod.split("arany = i / lepesek")[1]


def test_a_leallitott_szam_uzenete_nem_szol_bele():
    kl = importlib.import_module(BASE + ".keverolejatszo")
    f = inspect.getsource(kl.KeveroLejatszo._allapot_kezelo)
    assert "gen != self._nemzedek" in f


# ---- a felület ígéretei ---------------------------------------------------

def test_a_billentyuk_ott_vannak():
    win = importlib.import_module(BASE + ".zenewin")
    f = inspect.getsource(win.ZeneFrame._on_key)
    for kod in ("WXK_SPACE", "WXK_LEFT", "WXK_RIGHT", "WXK_ESCAPE", "WXK_F1"):
        assert kod in f
    for betu in ('ord("R")', 'ord("E")', 'ord("S")', 'ord("O")', 'ord("I")'):
        assert betu in f


def test_alvas_5_tol_60_percig_otosevel():
    win = importlib.import_module(BASE + ".zenewin")
    assert win.ALVAS_PERCEK == (5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60)


def test_az_idozitobol_nem_nyilik_ablak():
    """4.6.7 tanulsága: időzítő-visszahívásból indított ablak összeomlást
    okozott. Az óra CSAK bemondhat és hangerőt állíthat."""
    win = importlib.import_module(BASE + ".zenewin")
    f = inspect.getsource(win.ZeneFrame._on_ora)
    for tiltott in ("ShowModal", "MessageBox", "MessageDialog"):
        assert tiltott not in f


def test_a_beepitett_fajlvalasztot_hasznalja():
    win = importlib.import_module(BASE + ".zenewin")
    f = inspect.getsource(win.ZeneFrame._mappat_valaszt)
    assert "fajlvalaszto.valassz_mappat" in f


def test_a_lista_egyszeres_kijelolesu():
    """Így a GetSelection() legális rajta (a levéllista tanulsága)."""
    win = importlib.import_module(BASE + ".zenewin")
    f = inspect.getsource(win.ZeneFrame._build)
    assert "wx.LB_SINGLE" in f


def test_a_manifest_ep():
    import pathlib
    gy = pathlib.Path(__file__).resolve().parents[1]
    m = json.loads((gy / "modules_src" / "zene" / "manifest.json")
                   .read_text(encoding="utf-8"))
    assert m["id"] == "zene" and m["entry"] == "zene_mod"
    assert m["version"] == "1.0.0"
    assert len(m["description"]) > 200
