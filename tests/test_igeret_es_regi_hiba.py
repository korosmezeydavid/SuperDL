# -*- coding: utf-8 -*-
"""Három javítás a 4.6.14 utáni jelentésekből.

1. A BE NEM TARTOTT ÍGÉRET, NEGYEDSZER (Nagy Károly). Az F6 („következő
   problémás elem") ugyanúgy azt mondta, hogy „a pontos szövege az
   eseménynaplóban van", mint a Shift+F6 – csak épp SOSEM ÍRT oda semmit.
   Ráadásul a naplózó egy „ne ismételjük magunkat" gyorsítótárral dolgozott,
   ami az ígéretet bizonytalanná tette.

2. A RÉGI HIBA MINT MAI MAGYARÁZAT (Tóth László). A mai elakadás mellé egy
   KÉT NAPPAL korábbi hiba került oda magyarázatként.

3. A MÉDIAKERESŐ NÉMA VISSZAJELZÉSEI (Nagy Károly). Az `_announce` csak az
   állapotsort írta át – vakon semmi nem hallatszott belőle.
"""

import inspect
import pathlib
import time

import pytest

from superdl import searchwin as SW

_GUI = pathlib.Path("superdl_gui.py").read_text(encoding="utf-8")


def _gui_forras(nev: str) -> str:
    i = _GUI.index("    def %s(" % nev)
    j = _GUI.find("\n    def ", i + 10)
    return _GUI[i:j if j > 0 else len(_GUI)]


# ======================================================================
# 1. AZ ÍGÉRET
# ======================================================================

def test_az_F6_is_naploz_mielott_igerne():
    """⚠️ Ez a hely kimaradt a 4.6.12-es javításból."""
    src = _gui_forras("_on_next_problem")
    assert "_nyers_hibat_naploz" in src, "az F6 ígéri a naplót, de nem ír oda"
    assert src.index("_nyers_hibat_naploz") < src.index("gond_mondat"), \
        "előbb kell naplózni, csak utána ígérni"
    assert "van_nyers" in src


def test_a_shift_F6_is_naploz_mielott_igerne():
    src = _gui_forras("_on_miert")
    assert src.index("_nyers_hibat_naploz") < src.index("gond_mondat")


def test_a_naplozas_nem_ugorja_at_az_ismetlodest():
    """⚠️ A gyorsítótár tette bizonytalanná az ígéretet: ha a szöveg egyszer
    bekerült, a program attól kezdve ÍGÉRTE a naplót anélkül, hogy odaírta
    volna."""
    src = _gui_forras("_nyers_hibat_naploz")
    elott = src[:src.index("self._naplo(")]
    assert "return True" not in elott, \
        "valami az írás előtt True-val tér vissza – megint ígéret írás nélkül"


def test_a_naplozas_hamisat_ad_ha_nincs_mit_irni():
    assert "return False" in _gui_forras("_nyers_hibat_naploz")


def test_a_nyers_szoveg_harom_helyrol_johet():
    src = _gui_forras("_nyers_hibaszoveg")
    for mezo in ("error_nyers", "utolso_hiba", "error"):
        assert mezo in src


# ======================================================================
# 2. A RÉGI HIBA
# ======================================================================

class GuiBab:
    """Csak a kor-eldöntés logikája, wx nélkül."""
    import superdl_gui as _G
    REGI_HIBA_MP = _G.MainFrame.REGI_HIBA_MP
    _regi_hiba = _G.MainFrame.__dict__["_regi_hiba"].__func__


def test_a_friss_hiba_nem_regi():
    assert GuiBab._regi_hiba(GuiBab, time.time() - 60) is False


def test_a_ket_napos_hiba_regi():
    assert GuiBab._regi_hiba(GuiBab, time.time() - 2 * 86400) is True


def test_az_idopont_nelkuli_hiba_REGINEK_szamit():
    """Ha nem tudjuk, mikor volt, nem állíthatjuk, hogy a mostanihoz tartozik."""
    assert GuiBab._regi_hiba(GuiBab, None) is True
    assert GuiBab._regi_hiba(GuiBab, 0) is True


def test_a_romlott_idopont_sem_robban():
    assert GuiBab._regi_hiba(GuiBab, "tegnap") is True


def test_a_regi_hibat_nem_tálalja_mai_magyarazatkent():
    src = _gui_forras("_on_miert")
    assert "_regi_hiba" in src
    i = src.index("_regi_hiba")
    korny = src[i:i + 900]
    assert "KORÁBBI futásból" in korny
    assert "NEM a mostani" in korny


def test_a_frissnel_marad_a_regi_megfogalmazas():
    src = _gui_forras("_on_miert")
    assert "Korábban" in src


def test_a_naploba_az_idopont_is_bekerul():
    src = _gui_forras("_on_miert")
    assert "korábbi hiba nyers szövege" in src
    i = src.index("korábbi hiba nyers szövege")
    assert "mikor" in src[i:i + 120]


# ======================================================================
# 3. A MÉDIAKERESŐ HANGJA
# ======================================================================

def test_a_mediakereso_kimondja_az_allapotot():
    """⚠️ Eddig csak az állapotsort írta át – vakon néma volt."""
    src = inspect.getsource(SW.MediaSearchFrame._announce)
    assert "screenreader" in src
    assert "selfvoice" in src


def test_a_kepernyoolvaso_van_eloszor():
    """A sorrend kötelező: fordítva képernyőolvasó-módban néma maradna."""
    src = inspect.getsource(SW.MediaSearchFrame._announce)
    assert src.index("screenreader") < src.index("selfvoice")


def test_az_ures_szoveget_nem_mondja_ki():
    src = inspect.getsource(SW.MediaSearchFrame._announce)
    assert "strip()" in src


def test_a_nemitott_sajat_hangot_tiszteletben_tartja():
    src = inspect.getsource(SW.MediaSearchFrame._announce)
    assert "muted" in src


def test_a_tekeres_pozicioja_az_announce_on_megy_ki():
    """Így a 4.6.13-as tekerés-bemondás végre hallatszik is."""
    src = inspect.getsource(SW.MediaSearchFrame._teker)
    assert "_announce" in src
