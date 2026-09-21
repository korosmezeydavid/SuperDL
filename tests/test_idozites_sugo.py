# -*- coding: utf-8 -*-
"""Az időzítés MAGÁTÓL mondja meg, hogyan kell használni.

Stolmár Barbi a listán (2026-09-17): „Most először próbálom használni a
letöltés időzítését, de nem tudom, hogy kell beírni, hány óra hány perctől
töltsön le."

A mező működött; csak sehol nem volt leírva, hogy ÓRA:PERC alakban kell
írni, és a puszta szám (+90) percjelentése végképp nem szerepelt sehol.
Ezek a tesztek arra vigyáznak, hogy az ÍGÉRET és a VISELKEDÉS együtt
maradjon: amit a súgó mond, azt a `parse_when` tudja is.
"""
import datetime as dt
from pathlib import Path

from superdl.manager import parse_when

GYOKER = Path(__file__).resolve().parent.parent
_GUI = (GYOKER / "superdl_gui.py").read_text(encoding="utf-8")


# --- amit a súgó ígér ---------------------------------------------------

def test_a_sugo_kimondja_az_ora_perc_alakot():
    assert "óra kettőspont perc" in _GUI or "ÓRA:PERC" in _GUI


def test_a_sugo_elmondja_a_puszta_szam_jelenteset():
    """Ez volt a leginkább kitalálhatatlan szabály."""
    assert "+90" in _GUI
    assert "PERCET jelent" in _GUI or "PERC)" in _GUI


def test_a_sugo_elmondja_a_holnapi_atfordulast():
    assert "HOLNAP" in _GUI or "holnap" in _GUI


def test_a_mezo_neve_peldat_ad():
    resz = _GUI.split("self.sched_entry.SetName(", 1)[1].split(")", 1)[0]
    assert "3:00" in resz


def test_a_hibauzenet_tanit_nem_csak_panaszkodik():
    resz = _GUI.split("start_at is None", 1)[1].split("return", 1)[0]
    assert "+90" in resz and "3:00" in resz


# --- és amit a program TÉNYLEG tud ------------------------------------
# Egy súgó, ami mást ígér, mint amit a kód csinál, rosszabb a semminél.

def test_ora_perc_ma_ha_meg_nem_mult_el():
    kesobb = (dt.datetime.now() + dt.timedelta(hours=2)).replace(second=0,
                                                                 microsecond=0)
    t = parse_when("%d:%02d" % (kesobb.hour, kesobb.minute))
    assert t is not None
    assert dt.datetime.fromtimestamp(t).date() == dt.date.today()


def test_ora_perc_holnap_ha_mar_elmult():
    korabban = dt.datetime.now() - dt.timedelta(hours=2)
    t = parse_when("%d:%02d" % (korabban.hour, korabban.minute))
    assert t is not None
    holnap = dt.date.today() + dt.timedelta(days=1)
    assert dt.datetime.fromtimestamp(t).date() == holnap


def test_egy_jegyu_ora_is_jo():
    """A súgó „3:00"-t ír, nem „03:00"-t — annak működnie kell."""
    assert parse_when("3:00") is not None


def test_a_puszta_szam_percet_jelent():
    most = dt.datetime.now().timestamp()
    t = parse_when("+90")
    assert t is not None
    assert 89 * 60 <= (t - most) <= 91 * 60


def test_ora_es_perc_es_nap_kesleltetes():
    most = dt.datetime.now().timestamp()
    assert 119 * 60 <= parse_when("+2h") - most <= 121 * 60
    assert 29 * 60 <= parse_when("+30m") - most <= 31 * 60
    assert 23 * 3600 <= parse_when("+1d") - most <= 25 * 3600


def test_pontos_nap_es_ido():
    t = parse_when("2026-09-18 03:00")
    assert dt.datetime.fromtimestamp(t) == dt.datetime(2026, 9, 18, 3, 0)


def test_ures_es_nulla_nem_idozites():
    assert parse_when("") is None
    assert parse_when("   ") is None
    assert parse_when("0") is None


def test_ertelmetlen_szoveg_nem_omlik_ossze():
    for rossz in ("holnap", "25:99", "+", "+abc", "három óra"):
        assert parse_when(rossz) is None, rossz


# --- év nélküli nap: működik, és NEM eszi meg az óra:perc alakot -------

def test_ev_nelkuli_nap_az_idei_evre_megy():
    t = parse_when("12-25 03:00")
    assert t is not None
    d = dt.datetime.fromtimestamp(t)
    assert (d.month, d.day, d.hour) == (12, 25, 3)
    assert d.year == dt.date.today().year


def test_az_ora_perc_SOHA_nem_lesz_datum():
    """A legveszélyesebb tévedés, ami itt előfordulhatna: a 9:17-ből
    szeptember 17. Lemérve — az óra:perc egyik dátumformátumra sem
    illeszkedik —, de teszt nélkül ez csak remény volna."""
    for szoveg in ("9:17", "3:00", "12:25", "1:5", "23:59"):
        t = parse_when(szoveg)
        assert t is not None, szoveg
        d = dt.datetime.fromtimestamp(t)
        ora, perc = (int(x) for x in szoveg.split(":"))
        assert (d.hour, d.minute) == (ora, perc), szoveg
        # ma vagy holnap – de SOHA nem egy távoli nap
        assert (d.date() - dt.date.today()).days in (0, 1), szoveg


def test_nincs_1900_as_ev_sehol():
    """A régi megoldás a strptime 1900-as alapértelmezett évére épült, amit
    utólag cserélt ki. A Python 3.15 ezt elrontaná."""
    for szoveg in ("12-25 03:00", "3:00", "2026-09-18 03:00"):
        t = parse_when(szoveg)
        assert dt.datetime.fromtimestamp(t).year >= 2000, szoveg
