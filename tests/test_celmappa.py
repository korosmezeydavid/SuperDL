# -*- coding: utf-8 -*-
"""Barbi hibajelentése (2026-09-05): a célmappából egyetlen „t" betű lett.

A `t` RELATÍV útvonal: a program munkakönyvtárához képest értendő, tehát a
letöltések egy `t` nevű mappába kerültek a program mellé, ahol a felhasználó
nem találta meg őket. Semmi nem ellenőrizte, és a hibás érték MENTŐDÖTT is —
vagyis egy véletlen billentyűleütésből tartós állapot lett.
"""

from pathlib import Path

from superdl import celmappa


# ---- a hiba magja: a relatív útvonal ----------------------------------

def test_a_relativ_utvonal_NEM_ervenyes():
    """EZ Barbi hibája, egy sorban. A „t" nem majdnem jó útvonal: olyan helyre
    mutat, amit a felhasználó nem lát."""
    jo, hiba = celmappa.ervenyes("t")
    assert jo is False
    assert "t" in hiba


def test_a_hibauzenet_megmondja_MIERT_baj():
    """A puszta „érvénytelen" semmit nem ér: a felhasználónak azt kell tudnia,
    mi történne, ha elfogadnánk."""
    _, hiba = celmappa.ervenyes("t")
    assert "teljes útvonal" in hiba.lower()
    assert "program" in hiba.lower()          # …a program mappájába kerülne


def test_az_ures_sem_ervenyes():
    assert celmappa.ervenyes("")[0] is False
    assert celmappa.ervenyes("   ")[0] is False
    assert celmappa.ervenyes(None)[0] is False


# ---- ami VISZONT érvényes ---------------------------------------------

def test_a_letezo_mappa_ervenyes(tmp_path):
    assert celmappa.ervenyes(str(tmp_path)) == (True, "")


def test_a_MEG_NEM_LETEZO_mappa_is_ervenyes(tmp_path):
    """⚠️ Ez fontos: egy új, még üres célmappa teljesen jogos kérés — a letöltő
    eddig is létrehozta. Ha ezt hibának vennénk, elrontanánk egy működő
    szokást, és a felhasználó azt hinné, elromlott a program."""
    uj = tmp_path / "Filmek" / "2026"
    jo, hiba = celmappa.ervenyes(str(uj))
    assert jo is True, hiba
    assert uj.is_dir()                         # létre is hozza


def test_a_szokozos_utvonal_egyben_marad(tmp_path):
    uj = tmp_path / "Az en letolteseim"
    assert celmappa.ervenyes(str(uj))[0] is True


# ---- visszaesés: mindig marad HASZNÁLHATÓ mappa -----------------------

def test_hibasnal_a_TARTALEKRA_esunk_vissza(tmp_path):
    jo, uzenet = celmappa.ellenoriz("t", str(tmp_path))
    assert jo == str(tmp_path)
    assert uzenet                              # és MEGMONDJUK, miért
    assert str(tmp_path) in uzenet


def test_tartalek_nelkul_az_alapertelmezett_jon():
    jo, uzenet = celmappa.ellenoriz("t", "")
    assert Path(jo).is_absolute()              # SOSEM relatív
    assert uzenet


def test_a_rossz_tartalekot_sem_fogadjuk_el():
    """Ha a tartalék maga is hibás (mert korábban azt is elrontották), akkor is
    értelmes mappát kell adnunk – nem szabad rosszat rosszal pótolni."""
    jo, _ = celmappa.ellenoriz("t", "sz")
    assert Path(jo).is_absolute()
    assert jo not in ("t", "sz")


def test_a_jo_utvonalnal_NINCS_uzenet(tmp_path):
    jo, uzenet = celmappa.ellenoriz(str(tmp_path), "")
    assert jo == str(tmp_path)
    assert uzenet == ""                        # ilyenkor hallgatunk


def test_az_alapertelmezett_mindig_abszolut_es_letezo():
    ut = celmappa.alapertelmezett()
    assert Path(ut).is_absolute()
    assert Path(ut).is_dir()


# ---- a bemondás --------------------------------------------------------

def test_a_valtozas_mondata_kimondja_az_utvonalat(tmp_path):
    mondat = celmappa.valtozas_mondat(str(tmp_path))
    assert str(tmp_path) in mondat
    assert mondat.lower().startswith("célmappa")
