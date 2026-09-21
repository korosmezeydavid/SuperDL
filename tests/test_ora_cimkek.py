"""CÍMKE-ŐR: a képernyőolvasó a JÓ címkét mondja-e minden mezőre?

⚠️ MIÉRT VAN ERRE KÜLÖN TESZT. Dávid élesben fogta meg: az időzítő-profil
párbeszédben MINDEN címke eggyel elcsúszott – a „Bemondás gyakorisága"
mező „Időzítő neve"-ként szólalt meg.

AZ OK, ÉS EZÉRT NEM LÁTHATÓ A FORRÁSBÓL. A sizer csak azt dönti el, hol
LÁTSZIK a címke. A képernyőolvasó viszont a Z-SORRENDBEN (= létrehozási
sorrendben) KÖZVETLENÜL ELŐTTE álló statikus szöveget párosítja a
vezérlőhöz. Ha a kód a vezérlőt hozza létre előbb és a címkét utána, a
látvány helyes, a felolvasás eggyel elcsúszik. Látó szem ezt nem veszi
észre – gép igen.

Ez a teszt ezért a VALÓDI wx gyerek-sorrendet nézi, nem a forrást.
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
    def mond(self, szoveg, valtozat="", **kw):
        return True


@pytest.fixture
def modul():
    from szervezes_mod import orawin
    return orawin


PROFILOK = [{"nev": "munkaidő", "hossz_perc": 480, "kozbenso_perc": 60,
             "valtozat": "m3"}]

MEZO_TIPUSOK = (wx.TextCtrl, wx.SpinCtrl, wx.Choice, wx.ComboBox, wx.ListCtrl)


def _elozo_cimke(vezerlo):
    """A vezérlő ELŐTT álló statikus szöveg a szülő gyerek-sorrendjében –
    pontosan az, amit a képernyőolvasó a mező nevének hisz."""
    testverek = list(vezerlo.GetParent().GetChildren())
    i = testverek.index(vezerlo)
    for j in range(i - 1, -1, -1):
        if isinstance(testverek[j], wx.StaticText):
            return testverek[j].GetLabel().replace("&", "")
        if isinstance(testverek[j], MEZO_TIPUSOK):
            return None          # másik mező jön előbb: nincs saját címke
    return None


def _mnemonikok(ablak):
    """Alt+betű gyorsbillentyűk az ablakban (a teljes gyerekfával).

    ⚠️ A LAPFÜLEK FELIRATA IS IDE TARTOZIK. Az Alt+betű az egész ablakban
    keres, a lapfül nem határolja el: az „&Időzítők" fül ütközött az
    „&Időbemondás bekapcsolva" jelölőnégyzettel."""
    ki = []

    def felvesz(cimke):
        if not cimke or "&" not in cimke:
            return
        for k in range(len(cimke) - 1):
            if cimke[k] == "&" and cimke[k + 1] != "&":
                ki.append((cimke[k + 1].lower(), cimke.replace("&", "")))

    def bejar(w):
        if isinstance(w, wx.Notebook):
            for i in range(w.GetPageCount()):
                felvesz(w.GetPageText(i))
        for gy in w.GetChildren():
            try:
                felvesz(gy.GetLabel())
            except Exception:
                pass
            bejar(gy)
    bejar(ablak)
    return ki


# ───────────────── a konkrét hiba, amit Dávid megfogott ─────────────

def test_az_idozito_profil_mezoi_a_SAJAT_cimkejuket_kapjak(keret, modul):
    d = modul.ProfilDialog(keret, BeszeloBab())
    try:
        assert _elozo_cimke(d.nev) == "Időzítő neve:"
        assert _elozo_cimke(d.kozbenso) == "Bemondás gyakorisága:"
        assert _elozo_cimke(d.hossz) == "Teljes hossz:"
        assert _elozo_cimke(d.hang.valaszto) == "Bemondó hang:"
    finally:
        d.Destroy()


def test_az_ora_lap_mezoi_a_SAJAT_cimkejuket_kapjak(keret, modul):
    motor = I.OraMotor(BeszeloBab(), dict(I.ALAP))
    d = modul.OraDialog(keret, motor, BeszeloBab(), PROFILOK,
                        lambda b: None, lambda p: None)
    try:
        o = d.ora
        assert _elozo_cimke(o.periodus) == "Milyen gyakran:"
        assert _elozo_cimke(o.stilus) == "Stílus:"
        assert _elozo_cimke(o.csend_tol) == "Csendes sáv kezdete:"
        assert _elozo_cimke(o.csend_ig) == "vége:"
        assert _elozo_cimke(o.ules) == "Ülés-emlékeztető:"
        assert _elozo_cimke(o.hang.valaszto) == "Hang:"
    finally:
        d.idozitok.leall()
        d.Destroy()
        wx.SafeYield()


def test_minden_mezonek_van_felolvashato_neve_is(keret, modul):
    """Öv és nadrágtartó: a Z-sorrend mellett a SetName is legyen helyes,
    mert a két dolog közül a képernyőolvasók nem mindig ugyanazt veszik."""
    d = modul.ProfilDialog(keret, BeszeloBab())
    try:
        assert d.nev.GetName() == "Az időzítő neve"
        assert "gyakorisága" in d.kozbenso.GetName()
        assert "hossza" in d.hossz.GetName()
    finally:
        d.Destroy()


# ─────────────── ütköző Alt+betű gyorsbillentyűk ────────────────────

def test_a_profil_parbeszedben_nincs_ket_azonos_alt_betu(keret, modul):
    d = modul.ProfilDialog(keret, BeszeloBab())
    try:
        parok = _mnemonikok(d)
        betuk = [b for b, _ in parok]
        utkozes = {b for b in betuk if betuk.count(b) > 1}
        assert not utkozes, "ütköző Alt+betűk: %s" % sorted(
            (b, [c for x, c in parok if x == b]) for b in utkozes)
    finally:
        d.Destroy()


def test_az_ora_ablakban_nincs_ket_azonos_alt_betu(keret, modul):
    """⚠️ A lapfülek NEM védenek: az Alt+betű az EGÉSZ ablakban keres."""
    motor = I.OraMotor(BeszeloBab(), dict(I.ALAP))
    d = modul.OraDialog(keret, motor, BeszeloBab(), PROFILOK,
                        lambda b: None, lambda p: None)
    try:
        parok = _mnemonikok(d)
        betuk = [b for b, _ in parok]
        utkozes = {b for b in betuk if betuk.count(b) > 1}
        assert not utkozes, "ütköző Alt+betűk: %s" % sorted(
            (b, [c for x, c in parok if x == b]) for b in utkozes)
    finally:
        d.idozitok.leall()
        d.Destroy()
        wx.SafeYield()
