# -*- coding: utf-8 -*-
"""A Zene modul: a lehető legegyszerűbb lejátszó.

A hangsúly azon van, ami NÉMÁN tud elromlani: a mappabejárás, és hogy az
áttűnés hibája SOHA ne hagyja abba a zenét.
"""
import importlib
import inspect
import json
import re
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


# ---- a Média almenü és a helyi menü ---------------------------------------

def test_a_media_almenube_kerul_nem_kulon_fomenube():
    """Egy zenelejátszó miatt nem nyitunk új főmenüt."""
    init = importlib.import_module(BASE)
    f = inspect.getsource(init.register)
    assert '"&Média"' in f
    assert 'add_submenu' in f
    # tartalék, ha a Core nem tud almenüt
    assert 'core.add_menu(' in f


def test_van_helyi_menu_es_minden_muvelet_benne_van():
    win = importlib.import_module(BASE + ".zenewin")
    f = inspect.getsource(win.ZeneFrame._helyi_menu)
    for varhato in ("Szünet", "Előző szám", "Következő szám", "Hangerő fel",
                    "Ismétlés", "Elalvás", "Keresés", "Ugrás &mappára",
                    "Véletlen szám", "Hol tartunk", "vágólapra", "Intézőben",
                    "újraolvasása", "Súgó"):
        assert varhato in f, f"hiányzik a helyi menüből: {varhato}"


def test_a_helyi_menu_a_lista_helyi_menu_esemenyere_nyilik():
    win = importlib.import_module(BASE + ".zenewin")
    f = inspect.getsource(win.ZeneFrame._build)
    assert "EVT_CONTEXT_MENU" in f


def test_a_helyi_menu_a_gyorsbillentyut_is_mutatja():
    """Vakon ez a tanulás útja: a menü mondja be, mi a billentyűje."""
    win = importlib.import_module(BASE + ".zenewin")
    f = inspect.getsource(win.ZeneFrame._helyi_menu)
    for gyors in ("\\tCtrl+R", "\\tCtrl+S", "\\tCtrl+F", "\\tSzóköz"):
        assert gyors.replace("\\\\t", "\\t") in f


def test_a_kapcsolok_pipaval_latszanak():
    win = importlib.import_module(BASE + ".zenewin")
    f = inspect.getsource(win.ZeneFrame._helyi_menu)
    assert "AppendCheckItem" in f


def test_az_uj_muveletek_billentyuvel_is_mennek():
    win = importlib.import_module(BASE + ".zenewin")
    f = inspect.getsource(win.ZeneFrame._on_key)
    for betu in ('ord("F")', 'ord("G")', 'ord("T")', 'ord("C")'):
        assert betu in f
    assert "WXK_F3" in f and "WXK_F5" in f
    assert "WXK_WINDOWS_MENU" in f and "WXK_F10" in f
    assert "ctrl and kod == wx.WXK_UP" in f


def test_a_kereses_korbefordul():
    win = importlib.import_module(BASE + ".zenewin")
    f = inspect.getsource(win.ZeneFrame._talalat_keres)
    assert "% n" in f, "a keresésnek körbe kell fordulnia a lista végén"


def test_a_hangero_megmarad_a_kovetkezo_szamra():
    """Ha csak az aktuális lejátszóra állítanánk, a következő szám megint
    teljes hangerőn indulna – éjjel ez ébresztő."""
    kl = importlib.import_module(BASE + ".keverolejatszo")
    f = inspect.getsource(kl.KeveroLejatszo.jatszik)
    assert "self._cel()" in f
    a = inspect.getsource(kl.KeveroLejatszo._attun)
    assert "self._cel()" in a


def test_az_elalvas_es_a_hangero_nem_uti_egymast():
    """Az elalvás-elhalkulás SZORZÓ, nem abszolút érték: ha a felhasználó
    60 százalékra vette, az elhalkulás onnan induljon, ne 100-ról."""
    kl = importlib.import_module(BASE + ".keverolejatszo")
    f = inspect.getsource(kl.KeveroLejatszo._cel)
    assert "fo_hangero" in f and "_szorzo" in f


def test_a_manifest_ep():
    import pathlib
    gy = pathlib.Path(__file__).resolve().parents[1]
    m = json.loads((gy / "modules_src" / "zene" / "manifest.json")
                   .read_text(encoding="utf-8"))
    assert m["id"] == "zene" and m["entry"] == "zene_mod"
    # a verziót NEM rögzítjük: minden kiadásnál elbukna, és az a fajta teszt,
    # amit az ember gépiesen átír, nem véd semmitől
    assert re.fullmatch(r"\d+\.\d+\.\d+", m["version"])
    assert len(m["description"]) > 200
