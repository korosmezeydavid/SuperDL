"""KILÉPÉS-ŐR: fut időzítő → a program megkérdezi, tényleg kilépsz-e.

⚠️ MIÉRT VAN ERRE KÜLÖN TESZT. Csendben elveszíteni egy futó időzítőt
rosszabb a semminél: a felhasználó azt hiszi, szólni fog az ebédszünet vége,
és nem szól. A kérdés csak akkor jó, ha TÉNYLEG kilépésnél jön – háttérmódban
(tálcára minimalizálás) a program nem lép ki, ott nem szabad kérdeznie.

A Core `_on_close`-át wx.App nélkül nem futtatjuk; a SORRENDET és a
HÁTTÉRMÓD-ágat forrásszinten őrizzük, a modul őrének VISELKEDÉSÉT viszont
élőben.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "modules_src" / "szervezes"))

from superdl import idoora as I          # noqa: E402

GUI = (ROOT / "superdl_gui.py").read_text(encoding="utf-8")


def test_a_core_ismeri_a_kilepes_oroket():
    for nev in ("def kilepes_or_hozzaad", "def kilepes_or_eltavolit",
                "def _kilepes_orok_kerdeznek", "self._kilepes_orok = []"):
        assert nev in GUI, "hiányzik a Core-ból: %s" % nev


def test_az_orok_a_hattermod_UTAN_kerdeznek():
    """⚠️ A sorrend a lényeg: háttérmódban a `_on_close` már visszatért,
    tehát oda nem jutunk el. Ha ez a hívás feljebb csúszna, a tálcára
    minimalizálás is kilépés-kérdést hozna – naponta többször."""
    kezdet = GUI.index("def _on_close(self, event):")
    reszlet = GUI[kezdet:kezdet + 3000]
    hattermod = reszlet.index("self._bg_mode and not self._really_quit")
    orok = reszlet.index("self._kilepes_orok_kerdeznek(event)")
    letoltes = reszlet.index("Letöltés van folyamatban")
    assert hattermod < orok < letoltes


def test_az_or_vetoja_megallitja_a_kilepest():
    """A `_kilepes_orok_kerdeznek` szerződése: True = megvétóztuk."""
    assert "event.Veto()" in GUI[GUI.index("def _kilepes_orok_kerdeznek"):
                                 GUI.index("def _on_close(self, event):")]


def test_a_hibas_or_nem_akadalyozza_meg_a_kilepest():
    """Egy elszálló modul-őr nem zárhatja csapdába a felhasználót."""
    reszlet = GUI[GUI.index("def _kilepes_orok_kerdeznek"):
                  GUI.index("def _on_close(self, event):")]
    assert "except Exception:" in reszlet
    assert "continue" in reszlet


# ───────────────── a modul őrének VISELKEDÉSE (élőben) ──────────────

class BeszeloBab:
    def mond(self, szoveg, valtozat="", **kw):
        return True


@pytest.fixture
def modul():
    import szervezes_mod
    return szervezes_mod


def test_nem_futo_idozitonel_nincs_kerdes(modul):
    motor = I.OraMotor(BeszeloBab(), dict(I.ALAP))
    modul._state["motor"] = motor
    try:
        assert modul._kilepes_or() == ""
    finally:
        modul._state.pop("motor", None)


def test_futo_idozitonel_kerdez_es_megnevezi(modul):
    motor = I.OraMotor(BeszeloBab(), dict(I.ALAP))
    motor.idozito_indit({"nev": "ebédszünet", "hossz_perc": 20,
                         "kozbenso_perc": 5, "valtozat": "f2"})
    modul._state["motor"] = motor
    try:
        szoveg = modul._kilepes_or()
        assert "ebédszünet" in szoveg
        assert "Biztosan kilépsz?" in szoveg
        assert "profilok megmaradnak" in szoveg
    finally:
        modul._state.pop("motor", None)


def test_ora_nelkul_nincs_kerdes(modul):
    modul._state.pop("motor", None)
    assert modul._kilepes_or() == ""


def test_tobb_futo_idozitot_mind_felsorol():
    motor = I.OraMotor(BeszeloBab(), dict(I.ALAP))
    motor.idozito_indit({"nev": "munkaidő", "hossz_perc": 480})
    motor.idozito_indit({"nev": "ebédszünet", "hossz_perc": 20})
    szoveg = motor.futo_osszefoglalo()
    assert "munkaidő" in szoveg and "ebédszünet" in szoveg
    assert szoveg.startswith("Fut két időzítőd")
