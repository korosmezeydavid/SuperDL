"""A beszélő óra motorja: ütemezés, csendes sáv, szövegek, időzítők.

Minden időfüggő függvény kap `most`-ot, így a tesztek determinisztikusak –
nincs `sleep`, és nem függnek attól, mikor futnak.
"""

import datetime as dt

import pytest

from superdl import idoora as I


# ───────────────────── 1. szabály: órához igazítás ──────────────────

@pytest.mark.parametrize("perc,var", [
    (0, "14:20"), (7, "14:20"), (19, "14:20"), (20, "14:40"),
    (39, "14:40"), (40, "15:00"), (59, "15:00"),
])
def test_husz_perces_periodus_mindig_kerek_pontra_esik(perc, var):
    most = dt.datetime(2026, 9, 20, 14, perc, 33)
    kov = I.kovetkezo_bemondas(most, 20)
    assert kov.strftime("%H:%M") == var
    assert kov.minute % 20 == 0


def test_a_periodus_nem_az_inditashoz_igazodik():
    """14:07-kor indítva is :20-kor szól, nem 14:27-kor."""
    assert I.kovetkezo_bemondas(
        dt.datetime(2026, 9, 20, 14, 7, 0), 20).minute == 20


def test_hatvan_perces_periodus_a_kovetkezo_egesz_ora():
    kov = I.kovetkezo_bemondas(dt.datetime(2026, 9, 20, 14, 0, 0), 60)
    assert (kov.hour, kov.minute) == (15, 0)


@pytest.mark.parametrize("p", [5, 10, 15, 20, 30, 60, 1, 2, 3, 4, 6, 12])
def test_hatvan_osztoi_engedettek(p):
    assert I.periodus_ok(p)


@pytest.mark.parametrize("p", [7, 13, 25, 0, -5, 61, 90, "húsz", None])
def test_nem_oszto_periodus_nem_fogadhato_el(p):
    assert not I.periodus_ok(p)


def test_rossz_periodus_eseten_az_alapertelmezett_jar(): 
    """Rossz értékkel sem eshet szét: a 20 perces alapra esik vissza."""
    kov = I.kovetkezo_bemondas(dt.datetime(2026, 9, 20, 14, 7), 7)
    assert kov.minute == 20


# ─────────────── csendes sáv (és az éjfél-átnyúlás csapdája) ────────

@pytest.mark.parametrize("ido,var", [
    ("21:59", False), ("22:00", True), ("23:30", True),
    ("00:00", True), ("03:00", True), ("06:59", True),
    ("07:00", False), ("12:00", False),
])
def test_csendes_sav_ejfelen_atnyulva(ido, var):
    h, m = map(int, ido.split(":"))
    most = dt.datetime(2026, 9, 20, h, m)
    assert I.csendben(most, "22:00", "07:00") is var


def test_csendes_sav_ejfel_nelkul():
    assert I.csendben(dt.datetime(2026, 9, 20, 13, 0), "12:00", "14:00")
    assert not I.csendben(dt.datetime(2026, 9, 20, 15, 0), "12:00", "14:00")


def test_azonos_kezdet_es_veg_nem_jelent_orokos_csendet():
    assert not I.csendben(dt.datetime(2026, 9, 20, 3, 0), "07:00", "07:00")


def test_rossz_idoformatum_az_alapertelmezett_savot_adja():
    assert I.csendben(dt.datetime(2026, 9, 20, 23, 0), "hupsz", "szintén")


# ───────────────── 2. szabály: ami elmúlt, az elmúlt ────────────────

def test_alvas_utan_egyetlen_elmaradt_bemondas_sincs():
    u = I.Utemezo({"bemondas": True, "periodus_perc": 20,
                   "csend_tol": "03:00", "csend_ig": "03:01"})
    assert u.esedekes(dt.datetime(2026, 9, 20, 10, 0, 5)) is not None
    # három óra alvás – ébredés 13:07-kor, a 13:00-s pont RÉG elmúlt
    assert u.esedekes(dt.datetime(2026, 9, 20, 13, 7, 0)) is None
    # ...de a következő kerek pont már jön
    assert u.esedekes(dt.datetime(2026, 9, 20, 13, 20, 3)) is not None


def test_ugyanazt_a_pontot_nem_mondja_be_ketszer():
    u = I.Utemezo({"bemondas": True, "periodus_perc": 20,
                   "csend_tol": "03:00", "csend_ig": "03:01"})
    assert u.esedekes(dt.datetime(2026, 9, 20, 10, 0, 5)) is not None
    assert u.esedekes(dt.datetime(2026, 9, 20, 10, 0, 25)) is None
    assert u.esedekes(dt.datetime(2026, 9, 20, 10, 0, 45)) is None


def test_inditaskor_nincs_visszamenoleges_bemondas():
    """14:07-kor indulva a 14:00-s pont nem szólal meg utólag."""
    u = I.Utemezo({"bemondas": True, "periodus_perc": 20,
                   "csend_tol": "03:00", "csend_ig": "03:01"})
    assert u.esedekes(dt.datetime(2026, 9, 20, 14, 7, 0)) is None


def test_csendes_savban_nincs_bemondas():
    u = I.Utemezo({"bemondas": True, "periodus_perc": 20,
                   "csend_tol": "22:00", "csend_ig": "07:00"})
    assert u.esedekes(dt.datetime(2026, 9, 20, 23, 0, 5)) is None


def test_a_csend_vegen_nem_mondja_be_az_ejszakat():
    u = I.Utemezo({"bemondas": True, "periodus_perc": 20,
                   "csend_tol": "22:00", "csend_ig": "07:00"})
    assert u.esedekes(dt.datetime(2026, 9, 20, 23, 0, 5)) is None
    assert u.esedekes(dt.datetime(2026, 9, 21, 7, 0, 5)) is not None


def test_kikapcsolva_nem_szol():
    u = I.Utemezo({"bemondas": False, "periodus_perc": 20})
    assert u.esedekes(dt.datetime(2026, 9, 20, 10, 0, 5)) is None


# ──────────────────────── kimondott számok ──────────────────────────

@pytest.mark.parametrize("n,var", [
    (0, "nulla"), (1, "egy"), (2, "kettő"), (9, "kilenc"), (10, "tíz"),
    (11, "tizenegy"), (12, "tizenkettő"), (19, "tizenkilenc"),
    (20, "húsz"), (21, "huszonegy"), (30, "harminc"), (40, "negyven"),
    (45, "negyvenöt"), (50, "ötven"), (59, "ötvenkilenc"),
])
def test_magyar_szamnevek(n, var):
    assert I.szam(n) == var


@pytest.mark.parametrize("n,var", [
    (2, "két"), (12, "tizenkét"), (22, "huszonkét"), (32, "harminckét"),
    (42, "negyvenkét"), (52, "ötvenkét"), (3, "három"), (20, "húsz"),
])
def test_jelzoi_alak_a_ketto_kivetel(n, var):
    assert I.szam_jelzo(n) == var


# ────────── a csapda: prefix nélkül SEM szabad nyers szám ───────────

def test_ures_prefixnel_is_kimondott_alak_megy():
    b = dict(I.ALAP, prefix_be=False, stilus="pontos")
    szov = I.bemondas_szoveg(dt.datetime(2026, 9, 20, 11, 20), b)
    assert szov == "tizenegy óra húsz perc."
    assert not any(c.isdigit() for c in szov)


def test_a_prefix_szerkesztese_utan_az_uj_szoveg_megy():
    b = dict(I.ALAP, prefix_be=True, prefix_szoveg="az idő")
    szov = I.bemondas_szoveg(dt.datetime(2026, 9, 20, 11, 20), b)
    assert szov.startswith("az idő ")
    assert "A pontos idő" not in szov


def test_ures_prefix_szoveg_ugy_mukodik_mint_a_kikapcsolt():
    b = dict(I.ALAP, prefix_be=True, prefix_szoveg="   ")
    assert I.bemondas_szoveg(dt.datetime(2026, 9, 20, 11, 20), b) == \
        "tizenegy óra húsz perc."


# ─────────────────────── a három stílus ─────────────────────────────

def test_harom_stilus_harom_ismert_mondat():
    t = dt.datetime(2026, 9, 20, 20, 45)
    assert I.idoszoveg(t, "pontos") == "húsz óra negyvenöt perc"
    assert I.idoszoveg(t, "termeszetes") == "este nyolc óra negyvenöt"
    assert I.idoszoveg(t, "koznyelvi") == "háromnegyed kilenc"


@pytest.mark.parametrize("h,m,var", [
    (12, 0, "dél"), (0, 0, "éjfél"),
    (8, 40, "reggel nyolc óra negyven"),
    (15, 0, "délután három óra"),
    (2, 12, "éjjel két óra tizenkettő"),
])
def test_termeszetes_stilus(h, m, var):
    assert I.idoszoveg(dt.datetime(2026, 9, 20, h, m), "termeszetes") == var


@pytest.mark.parametrize("h,m,var", [
    (20, 15, "negyed kilenc"), (20, 30, "fél kilenc"),
    (20, 0, "pontosan nyolc óra"),
    (20, 10, "nyolc óra múlt tíz perccel"),
    (20, 50, "tíz perc múlva kilenc óra"),
    (23, 30, "fél tizenkettő"),
    # a „fél/negyed" után ÖNÁLLÓ alak jár, az „óra" előtt JELZŐI – ezen
    # bukott el az első változat („fél tizenkét")
    (13, 15, "negyed kettő"),
    (1, 40, "húsz perc múlva két óra"),
])
def test_koznyelvi_stilus(h, m, var):
    assert I.idoszoveg(dt.datetime(2026, 9, 20, h, m), "koznyelvi") == var


def test_ismeretlen_stilus_a_pontosra_esik_vissza():
    t = dt.datetime(2026, 9, 20, 20, 45)
    assert I.idoszoveg(t, "nincsilyen") == I.idoszoveg(t, "pontos")


def test_egesz_orakor_nincs_nulla_perc():
    assert I.idoszoveg(dt.datetime(2026, 9, 20, 20, 0), "pontos") == "húsz óra"
