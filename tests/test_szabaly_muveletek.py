# -*- coding: utf-8 -*-
"""MK3 – az új szabály-műveletek és az ütközés-ellenőrzés."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "modules_src" / "mail"))

from mail_mod import szabalyok as SZ          # noqa: E402


def _sz(**muveletek):
    return SZ.Szabaly(
        feltetelek=[SZ.Feltetel(SZ.MEZO_FELADO, SZ.VISZ_TARTALMAZZA, "@x.hu")],
        muveletek=dict(muveletek))


# ---------------------------------------------------------------- mondatok

def test_emlekezteto_ideje_felolvashato():
    assert SZ.emlekezteto_szoveg(3600) == "egy óra múlva"
    assert SZ.emlekezteto_szoveg(24 * 3600) == "holnap ilyenkor"
    assert SZ.emlekezteto_szoveg(2 * 86400) == "2 nap múlva"   # nem listás érték
    assert "ismeretlen" in SZ.emlekezteto_szoveg("blabla")


def test_minden_muveletnek_van_mondata():
    """Egy művelet sem hangozhat el nyers kulcsként a felolvasóban."""
    for kulcs in SZ.VALASZTHATO_MUVELETEK:
        fajta = SZ.MUVELET_ERTEK.get(kulcs, "")
        ertek = {"mappa": "Számlák", "ido": 3600, "cim": "a@b.hu",
                 "szoveg": "Megjött a NAV levele", "level": "Szia"}.get(
                     fajta, True)
        mondat = SZ.muvelet_leiras(kulcs, ertek)
        # a mondat SOSEM lehet a nyers kulcs, és a magyar nevével kell kezdődnie
        assert mondat and mondat != kulcs, kulcs
        assert mondat.startswith(SZ.MUVELET_NEVEK[kulcs]), kulcs


def test_szabaly_mondata_az_uj_muveletekkel():
    mondat = _sz(**{SZ.MUV_FONTOS: True, SZ.MUV_EMLEKEZTETO: 3600,
                    SZ.MUV_BEMONDAS: "Megjött a NAV"}).leiras()
    assert "megjelölés fontosként" in mondat
    assert "emlékeztess rá egy óra múlva" in mondat
    assert "mondja ki érkezéskor: „Megjött a NAV”" in mondat


# ---------------------------------------------------------------- ütközés

def test_kuka_es_athelyezes_utkozik():
    assert SZ.utkozes({SZ.MUV_TOROL: True, SZ.MUV_ATHELYEZ: "Számlák"})


def test_kuka_es_emlekezteto_utkozik():
    assert SZ.utkozes({SZ.MUV_TOROL: True, SZ.MUV_EMLEKEZTETO: 3600})


def test_ugyanaz_a_mappa_masolasra_es_athelyezesre_utkozik():
    assert SZ.utkozes({SZ.MUV_ATHELYEZ: "Számlák", SZ.MUV_MASOL: "számlák"})


def test_ertelmes_kombinacio_nem_utkozik():
    """A kért példa: fontosnak jelölés + emlékeztető + naptár."""
    assert SZ.utkozes({SZ.MUV_FONTOS: True, SZ.MUV_EMLEKEZTETO: 3600,
                       SZ.MUV_NAPTARBA: True}) == ""
    assert SZ.utkozes({SZ.MUV_TOROL: True,
                       SZ.MUV_AUTOVALASZ: "Nem érdekel."}) == ""


# ---------------------------------------------------------------- mentés

def test_az_uj_muveletek_visszaolvashatok(tmp_path):
    sz = _sz(**{SZ.MUV_EMLEKEZTETO: 4 * 3600, SZ.MUV_NAPTARBA: True,
                SZ.MUV_TOVABBIT: "titkar@ceg.hu",
                SZ.MUV_BEMONDAS: "Sürgős!"})
    SZ.ment(str(tmp_path), [sz])
    vissza = SZ.betolt(str(tmp_path))[0]
    assert vissza.muveletek[SZ.MUV_EMLEKEZTETO] == 4 * 3600
    assert vissza.muveletek[SZ.MUV_NAPTARBA] is True
    assert vissza.muveletek[SZ.MUV_TOVABBIT] == "titkar@ceg.hu"
    assert vissza.muveletek[SZ.MUV_BEMONDAS] == "Sürgős!"


def test_a_regi_szabalyok_valtozatlanul_betoltodnek(tmp_path):
    """A fájlformátum nem változott – a korábbi szabályok tovább élnek."""
    regi = _sz(**{SZ.MUV_ATHELYEZ: "Hírlevelek", SZ.MUV_OLVASOTT: True})
    SZ.ment(str(tmp_path), [regi])
    vissza = SZ.betolt(str(tmp_path))[0]
    assert vissza.muveletek == {SZ.MUV_ATHELYEZ: "Hírlevelek",
                                SZ.MUV_OLVASOTT: True}


def test_a_valaszthato_muveletek_es_az_ertekek_osszhangban_vannak():
    """Minden felkínált művelet neve ismert, és minden érték-fajtát kezelünk."""
    for kulcs in SZ.VALASZTHATO_MUVELETEK:
        assert kulcs in SZ.MUVELET_NEVEK
    for kulcs, fajta in SZ.MUVELET_ERTEK.items():
        assert kulcs in SZ.VALASZTHATO_MUVELETEK
        assert fajta in ("mappa", "ido", "cim", "szoveg", "level")
