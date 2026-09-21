"""A beszélő óra KEZELŐFELÜLETE – élő wx-vezérlőkkel, nem forráskód-olvasással.

A vezérlőket tényleg létrehozzuk (App + rejtett keret), mert a lényeg pont az,
ami forrásból nem látszik: hogy a Choice tényleg feltöltődik, a próba gomb
tényleg a kiválasztott hanggal szólal meg, és a mentés tényleg a beírt
értékeket adja vissza.

EGY ABLAK, KÉT LAPFÜL (Dávid kérése, 2026-09-20): „Óra" és „Időzítők".
"""

import sys

import pytest

wx = pytest.importorskip("wx")
sys.path.insert(0, "modules_src/szervezes")

from superdl import idoora as I           # noqa: E402
from superdl import orahang as H          # noqa: E402


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


class BeszeloBab:
    """Nem beszél, csak jegyzetel – a próba gombhoz."""

    def __init__(self):
        self.naplo = []

    def mond(self, szoveg, valtozat="", **kw):
        self.naplo.append((szoveg, valtozat))
        return True


@pytest.fixture
def modul():
    from szervezes_mod import orawin
    return orawin


def _motor():
    return I.OraMotor(BeszeloBab(), dict(I.ALAP))


PROFILOK = [
    {"nev": "munkaidő", "hossz_perc": 480, "kozbenso_perc": 60,
     "valtozat": "m3"},
    {"nev": "ebédszünet", "hossz_perc": 20, "kozbenso_perc": 5,
     "valtozat": "f2"},
]


@pytest.fixture
def ablak(keret, modul):
    """A teljes, kétlapfüles párbeszéd – ahogy a felhasználó látja."""
    mentesek = {"ora": [], "profilok": []}
    d = modul.OraDialog(keret, _motor(), BeszeloBab(), PROFILOK,
                        mentesek["ora"].append, mentesek["profilok"].append)
    d.EndModal = lambda kod: None        # itt nem modálisan fut
    d._mentesek = mentesek
    yield d
    d.idozitok.leall()
    d.Destroy()
    wx.SafeYield()


# ─────────────────────── hangválasztó + próba gomb ──────────────────

def test_a_hangvalaszto_feltolti_a_22_es_keszletet(keret, modul):
    hv = modul.HangValaszto(keret, BeszeloBab())
    assert hv.valaszto.GetCount() == len(H.keszlet())
    assert hv.valaszto.GetCount() >= 2


def test_a_proba_gomb_a_kivalasztott_hanggal_szolal_meg(keret, modul):
    """⚠️ E NÉLKÜL A FUNKCIÓ HASZNÁLHATATLAN. Vakon 22 hang közül listából
    választani lehetetlen, ha nem lehet meghallgatni."""
    if not H.letezo_valtozatok():
        pytest.skip("nincs beépített eSpeak-adatmappa ebben a környezetben")
    bab = BeszeloBab()
    hv = modul.HangValaszto(keret, bab)
    hv.allit("f2")
    assert hv.valtozat() == "f2"
    hv._proba()
    assert bab.naplo and bab.naplo[-1][1] == "f2"


def test_a_proba_a_sajat_szoveget_mondja(keret, modul):
    bab = BeszeloBab()
    hv = modul.HangValaszto(keret, bab)
    hv.minta_szoveg("ebédszünet: letelt az idő.")
    hv._proba()
    assert bab.naplo[-1][0] == "ebédszünet: letelt az idő."


def test_a_mind_kapcsolo_bovitti_a_listat_es_megtartja_a_valasztast(keret,
                                                                    modul):
    if not H.letezo_valtozatok():
        pytest.skip("nincs beépített eSpeak-adatmappa ebben a környezetben")
    hv = modul.HangValaszto(keret, BeszeloBab())
    hv.allit("f2")
    szuk = hv.valaszto.GetCount()
    hv.mind.SetValue(True)
    hv._feltolt()
    assert hv.valaszto.GetCount() > szuk
    assert hv.valtozat() == "f2", "a választás nem veszhet el a kapcsolótól"


def test_ismeretlen_valtozat_az_elso_elemre_esik_vissza(keret, modul):
    hv = modul.HangValaszto(keret, BeszeloBab())
    hv.allit("nincsilyenhang")
    assert hv.valaszto.GetSelection() == 0


# ────────────────────── a két lapfül (Dávid kérése) ─────────────────

def test_az_ablaknak_ket_lapfule_van_ora_es_idozitok(ablak):
    assert ablak.fulek.GetPageCount() == 2
    assert ablak.fulek.GetPageText(0).replace("&", "") == "Óra"
    assert ablak.fulek.GetPageText(1).replace("&", "") == "Időzítők"


def test_a_menubol_az_idozitok_lapra_is_lehet_nyitni(ablak):
    ablak.lapra(1)
    assert ablak.fulek.GetSelection() == 1
    ablak.lapra(0)
    assert ablak.fulek.GetSelection() == 0


def test_ertelmetlen_lapszamra_nem_szall_el(ablak):
    ablak.lapra(7)
    assert ablak.fulek.GetSelection() in (0, 1)


# ───────────────────────── az Óra lapfül ────────────────────────────

def test_az_ora_lap_visszaadja_a_beirt_ertekeket(ablak):
    o = ablak.ora
    o.be.SetValue(True)
    o.periodus.SetSelection(I.PERIODUSOK.index(30))
    o.prefix_be.SetValue(True)
    o.prefix.SetValue("az idő")
    o.jingle.SetValue(False)
    o.csend_tol.SetValue("23:30")
    o.csend_ig.SetValue("06:15")
    e = ablak.ertekek()
    assert e["bemondas"] is True
    assert e["periodus_perc"] == 30
    assert e["prefix_szoveg"] == "az idő"
    assert e["jingle"] is False
    assert (e["csend_tol"], e["csend_ig"]) == ("23:30", "06:15")


def test_csak_a_hatvan_osztoi_valaszthatoak(ablak):
    assert ablak.ora.periodus.GetCount() == len(I.PERIODUSOK)
    for p in I.PERIODUSOK:
        assert I.periodus_ok(p)


def test_hibas_csendes_sav_nem_mentheto_es_az_ora_lapra_ugrik(ablak,
                                                              monkeypatch,
                                                              modul):
    """Egy elgépelt sáv CSENDBEN rossz időben némítana – ezért itt szólunk.
    És mivel a hiba az Óra lapon van, oda is visszaugrunk."""
    monkeypatch.setattr(modul.wx, "MessageBox", lambda *a, **k: None)
    ablak.fulek.SetSelection(1)
    ablak.ora.csend_tol.SetValue("huszonkettő")
    ablak._mentes()
    assert ablak._mentesek["ora"] == [], "hibás időponttal nem menthet"
    assert ablak.fulek.GetSelection() == 0, "a hibás mezőhöz kell ugrani"
    ablak.ora.csend_tol.SetValue("22:00")
    ablak._mentes()
    assert len(ablak._mentesek["ora"]) == 1


def test_az_ora_mezoi_felolvashato_nevet_kapnak(ablak):
    o = ablak.ora
    for v in (o.periodus, o.prefix, o.stilus, o.csend_tol, o.csend_ig, o.ules):
        assert v.GetName() and v.GetName() != "control", \
            "a képernyőolvasó különben csak a vezérlő típusát mondaná"


# ─────────────────── az időzítő-profil szerkesztő ───────────────────

def test_a_profil_parbeszed_negy_mezoje(keret, modul):
    """Dávid kérése szerint: név, bemondás gyakorisága, teljes hossz, hang."""
    d = modul.ProfilDialog(keret, BeszeloBab())
    try:
        d.nev.SetValue("ebédszünet")
        d.kozbenso.SetValue(5)
        d.hossz.SetValue(20)
        d.hang.allit("f2" if H.ervenyes("f2") else "")
        e = d.ertekek()
        assert e["nev"] == "ebédszünet"
        assert e["kozbenso_perc"] == 5
        assert e["hossz_perc"] == 20
        assert "valtozat" in e
    finally:
        d.Destroy()


def test_uj_profilnal_ures_a_nev_es_a_cim_is_azt_mondja(keret, modul):
    d = modul.ProfilDialog(keret, BeszeloBab())
    try:
        assert d.nev.GetValue() == ""
        assert "Új időzítő profil" in d.GetTitle()
    finally:
        d.Destroy()


def test_a_profil_mezoi_felolvashato_nevet_kapnak(keret, modul):
    d = modul.ProfilDialog(keret, BeszeloBab())
    try:
        for v in (d.nev, d.kozbenso, d.hossz):
            assert v.GetName() and v.GetName() != "control"
    finally:
        d.Destroy()


def test_a_proba_szovege_a_profil_nevet_koveti(keret, modul):
    bab = BeszeloBab()
    d = modul.ProfilDialog(keret, bab)
    try:
        d.nev.SetValue("meeting")
        d._minta()
        d.hang._proba()
        assert bab.naplo[-1][0] == "meeting: letelt az idő."
    finally:
        d.Destroy()


def test_nev_nelkul_nem_menthato_a_profil(keret, modul, monkeypatch):
    monkeypatch.setattr(modul.wx, "MessageBox", lambda *a, **k: None)
    d = modul.ProfilDialog(keret, BeszeloBab())
    lezart = []
    d.EndModal = lambda kod: lezart.append(kod)
    try:
        d.nev.SetValue("   ")
        d._mentes()
        assert lezart == [], "névtelen profilt nem lett volna szabad menteni"
        d.nev.SetValue("ebédszünet")
        d._mentes()
        assert lezart == [wx.ID_OK]
    finally:
        d.Destroy()


# ──────────────────────── az Időzítők lapfül ────────────────────────

def test_a_lista_minden_oszlopa_felolvashato_szoveget_kap(ablak):
    li = ablak.idozitok.lista
    assert li.GetItemCount() == 2
    assert li.GetItemText(0, 0) == "munkaidő"
    assert li.GetItemText(0, 1) == "60 percenként"
    assert li.GetItemText(0, 2) == "480 perc"
    assert li.GetItemText(0, 3) == H.cimke("m3")
    assert li.GetItemText(0, 4) == "áll"


def test_az_oszlopok_sorrendje_a_kert_sorrend(ablak):
    li = ablak.idozitok.lista
    cimek = [li.GetColumn(i).GetText() for i in range(li.GetColumnCount())]
    assert cimek == ["Név", "Bemondás", "Teljes hossz", "Hang", "Állapot"]


def test_csak_a_vegen_szolo_idozito_igy_is_irodik_ki(keret, modul):
    p = modul.IdozitoPanel(keret, _motor(), BeszeloBab(),
                           [{"nev": "x", "hossz_perc": 5,
                             "kozbenso_perc": 0}], lambda pr: None)
    try:
        assert p.lista.GetItemText(0, 1) == "csak a végén"
    finally:
        p.leall()


def test_megnyitaskor_az_elso_sor_ki_van_jelolve(ablak):
    """Vakon a „nincs kijelölés" üzenet felesleges kör – legyen kijelölve."""
    assert ablak.idozitok.lista.GetFirstSelected() == 0


def test_az_inditas_utan_a_lista_fut_allapotot_mutat(keret, modul):
    motor = _motor()
    bab = BeszeloBab()
    p = modul.IdozitoPanel(keret, motor, bab, PROFILOK, lambda pr: None)
    try:
        p.lista.Select(1)
        p._indit()
        assert p.lista.GetItemText(1, 4).startswith("FUT")
        assert "ebédszünet" in bab.naplo[-1][0]
        assert bab.naplo[-1][1] == "f2", "a profil saját hangján induljon"
    finally:
        p.leall()


def test_tobb_idozito_egyszerre_futhat(keret, modul):
    motor = _motor()
    p = modul.IdozitoPanel(keret, motor, BeszeloBab(), PROFILOK,
                           lambda pr: None)
    try:
        p.lista.Select(0)
        p._indit()
        p.lista.Select(1)
        p._indit()
        assert len(motor.futok()) == 2
        assert p.lista.GetItemText(0, 4).startswith("FUT")
        assert p.lista.GetItemText(1, 4).startswith("FUT")
    finally:
        p.leall()


def test_a_profilok_azonnal_mentodnek_nem_az_ablak_mentesevel(keret, modul,
                                                              monkeypatch):
    """⚠️ Szándékos aszimmetria: egy elindított időzítő és egy eldobott
    profil együtt értelmetlen állapot lenne. A törlés tehát AZONNAL ment,
    nem az ablak „Mentés" gombjára vár."""
    mentve = []
    p = modul.IdozitoPanel(keret, _motor(), BeszeloBab(), list(PROFILOK),
                           mentve.append)
    try:
        monkeypatch.setattr(modul.wx, "MessageBox", lambda *a, **k: wx.YES)
        p.lista.Select(1)
        p._torol()
        assert len(mentve) == 1
        assert [x["nev"] for x in mentve[0]] == ["munkaidő"]
        assert p.lista.GetItemCount() == 1
    finally:
        p.leall()


def test_a_torles_megszakithato(keret, modul, monkeypatch):
    mentve = []
    p = modul.IdozitoPanel(keret, _motor(), BeszeloBab(), list(PROFILOK),
                           mentve.append)
    try:
        monkeypatch.setattr(modul.wx, "MessageBox", lambda *a, **k: wx.NO)
        p.lista.Select(1)
        p._torol()
        assert mentve == []
        assert p.lista.GetItemCount() == 2
    finally:
        p.leall()


def test_a_kilepesi_osszefoglalo_a_futo_idozitoket_sorolja():
    motor = _motor()
    assert motor.futo_osszefoglalo() == ""
    motor.idozito_indit(PROFILOK[1])
    szoveg = motor.futo_osszefoglalo()
    assert "ebédszünet" in szoveg
    assert not any(c.isdigit() for c in szoveg), "kimondott alak kell"


def test_a_zart_lap_frissitese_nem_szall_el(keret, modul):
    """A Modulkezelőnél élesben látott hiba mintája: a wx.Timer visszahívása
    a natív vezérlő törlése UTÁN is megjöhet."""
    p = modul.IdozitoPanel(keret, _motor(), BeszeloBab(), PROFILOK,
                           lambda pr: None)
    p.leall()
    p.Destroy()
    wx.SafeYield()
    p._allapotok()          # nem dobhat


def test_az_ablak_zarasa_megallitja_a_lista_idozitojet(ablak):
    ablak._zaras(wx.CloseEvent())
    assert ablak.idozitok._halott is True
