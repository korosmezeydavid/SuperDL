"""HELYI MENÜ az időzítő-profilok listáján (Dávid kérése, 2026-09-20).

⚠️ MIÉRT `EVT_CONTEXT_MENU` ÉS NEM JOBB KATTINTÁS. Aki nem lát, nem
egérrel keres helyi menüt: az Alkalmazás billentyűt vagy a Shift+F10-et
nyomja meg. A `wx.EVT_CONTEXT_MENU` MINDKETTŐT lefedi, az
`EVT_RIGHT_DOWN` csak az egeret – az utóbbival a funkció vakon nem
létezne.

A menü TARTALMÁT (`helyi_menu_tetelek`) külön metódus adja, hogy
tesztelhető legyen anélkül, hogy modális menüt kellene felnyitni – egy
felnyitott `PopupMenu` megállítaná a teszt futását.
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
    def __init__(self):
        self.naplo = []

    def mond(self, szoveg, valtozat="", **kw):
        self.naplo.append((szoveg, valtozat))
        return True


@pytest.fixture
def modul():
    from szervezes_mod import orawin
    return orawin


PROFILOK = [
    {"nev": "munkaidő", "hossz_perc": 480, "kozbenso_perc": 60,
     "valtozat": "m3"},
    {"nev": "ebédszünet", "hossz_perc": 20, "kozbenso_perc": 5,
     "valtozat": "f2"},
]


@pytest.fixture
def panel(keret, modul):
    mentve = []
    motor = I.OraMotor(BeszeloBab(), dict(I.ALAP))
    p = modul.IdozitoPanel(keret, motor, BeszeloBab(), list(PROFILOK),
                           mentve.append)
    p._mentve = mentve
    p._motor_ref = motor
    yield p
    p.leall()


def _feliratok(p):
    return [f.replace("&", "") for f, _ in p.helyi_menu_tetelek() if f]


def _engedelyezett(p):
    return [f.replace("&", "") for f, fv in p.helyi_menu_tetelek()
            if f and fv is not None]


# ───────────────────────── a menü szerkezete ────────────────────────

def test_a_lista_tenyleg_valaszol_a_context_menu_esemenyre(panel,
                                                           monkeypatch):
    """⚠️ Ez fedi le az Alkalmazás billentyűt és a Shift+F10-et is.
    Élő eseményt küldünk, nem a forrást olvassuk. A `PopupMenu`-t
    kiiktatjuk: egy felnyitott menü megállítaná a tesztet."""
    # a menüt a kezelő a felnyitás UTÁN eldobja, ezért ITT olvassuk ki
    felnyitva = []
    monkeypatch.setattr(
        type(panel.lista), "PopupMenu",
        lambda self, menu, *a: felnyitva.append(
            [menu.GetMenuItemCount(),
             [i.GetItemLabelText() for i in menu.GetMenuItems()]]))
    e = wx.ContextMenuEvent(wx.wxEVT_CONTEXT_MENU, panel.lista.GetId())
    e.SetEventObject(panel.lista)
    e.SetPosition(wx.DefaultPosition)        # billentyűről jött
    panel.lista.GetEventHandler().ProcessEvent(e)
    assert felnyitva, "a lista nem nyitott helyi menüt"
    db, feliratok = felnyitva[0]
    assert db >= 7
    assert any("Szerkeszt" in f for f in feliratok)


def test_billentyurol_erkezve_a_meglevo_kijeloles_marad(panel, monkeypatch):
    """Alkalmazás billentyűnél a pozíció (-1, -1): olyankor NEM szabad
    másik sort kijelölni."""
    monkeypatch.setattr(type(panel.lista), "PopupMenu",
                        lambda self, menu, *a: None)
    panel.lista.Select(1)
    e = wx.ContextMenuEvent(wx.wxEVT_CONTEXT_MENU, panel.lista.GetId())
    e.SetEventObject(panel.lista)
    e.SetPosition(wx.DefaultPosition)
    panel.lista.GetEventHandler().ProcessEvent(e)
    assert panel.lista.GetFirstSelected() == 1


def test_a_menu_a_szerkesztessel_kezdodik(panel):
    """A leggyakoribb művelet legyen az első – vakon minden lépés számít."""
    assert _feliratok(panel)[0] == "Szerkesztés…"


def test_a_menu_minden_kert_muveletet_tartalmazza(panel):
    f = _feliratok(panel)
    for kell in ("Szerkesztés…", "Indítás", "Megállítás",
                 "Új időzítő profil…", "Másolat készítése", "Törlés",
                 "Mennyi van hátra"):
        assert kell in f, "hiányzik a helyi menüből: %s" % kell


def test_kijelolt_sorral_a_szerkesztes_es_a_torles_elerheto(panel):
    panel.lista.Select(0)
    e = _engedelyezett(panel)
    assert "Szerkesztés…" in e
    assert "Törlés" in e
    assert "Másolat készítése" in e


def test_kijeloles_nelkul_a_sorfuggo_tetelek_szurkek(panel):
    """Nem eltüntetjük őket, hanem letiltjuk – így a képernyőolvasó is
    elmondja, hogy LÉTEZNEK, csak most nem használhatók."""
    for i in range(panel.lista.GetItemCount()):
        panel.lista.Select(i, 0)
    assert panel.lista.GetFirstSelected() == -1
    e = _engedelyezett(panel)
    assert "Szerkesztés…" not in e
    assert "Törlés" not in e
    assert "Új időzítő profil…" in e, "új profil kijelölés nélkül is kell"
    assert "Mennyi van hátra" in e


def test_nem_futo_idozitonel_az_indites_aktiv_a_megallitas_nem(panel):
    panel.lista.Select(0)
    e = _engedelyezett(panel)
    assert "Indítás" in e
    assert "Megállítás" not in e


def test_futo_idozitonel_forditva(panel):
    panel.lista.Select(1)
    panel._indit()
    e = _engedelyezett(panel)
    assert "Megállítás" in e
    assert "Indítás" not in e, "ami már fut, azt ne lehessen újra indítani"


# ───────────────────────── másolat készítése ────────────────────────

def test_a_masolat_uj_nevet_kap_es_a_kijelolt_utan_kerul(panel):
    panel.lista.Select(1)
    panel._masolat()
    nevek = [p["nev"] for p in panel._profilok]
    assert nevek == ["munkaidő", "ebédszünet", "ebédszünet 2"]
    assert panel.lista.GetFirstSelected() == 2, "a másolat legyen kijelölve"


def test_a_masolat_atveszi_a_beallitasokat(panel):
    panel.lista.Select(1)
    panel._masolat()
    uj = panel._profilok[2]
    assert uj["hossz_perc"] == 20
    assert uj["kozbenso_perc"] == 5
    assert uj["valtozat"] == "f2"


def test_tobbszoros_masolat_nem_utkozik(panel):
    panel.lista.Select(1)
    panel._masolat()
    panel.lista.Select(1)
    panel._masolat()
    nevek = [p["nev"] for p in panel._profilok]
    assert len(set(nevek)) == len(nevek), "két azonos nevű profil zavaró"
    assert "ebédszünet 3" in nevek


def test_a_masolat_azonnal_mentodik(panel):
    panel.lista.Select(1)
    panel._masolat()
    assert len(panel._mentve) == 1
    assert len(panel._mentve[0]) == 3
