# -*- coding: utf-8 -*-
"""Super Media caster: az adás-állapot lekérdezés nem tart fenn korlátlan
hamis „ÉLŐ" állapotot.

Herman Tibor média-audit SM-P1-10: a check_live a BASS_Encode_IsActive
kivételekor eddig MINDIG True-t adott (fail-open), így tartós DLL-/handle-
hibánál a felület örökké élő adást mutathatott, miközben csend ment ki."""
import pytest

S = pytest.importorskip("modules_src.supermedia.supermedia_mod.superm_stream")


class _RaisingEnc:
    def BASS_Encode_IsActive(self, h):
        raise OSError("a hangmotor nem válaszol")


class _OkEnc:
    def __init__(self, active):
        self.active = active
    def BASS_Encode_IsActive(self, h):
        return self.active


def _live_caster(enc):
    c = S.Caster()
    c.is_live = True
    c._henc = 1
    c._enc = enc
    return c


def test_atmeneti_hiba_meg_nem_riaszt_de_tartos_igen():
    c = _live_caster(_RaisingEnc())
    # az első néhány sikertelen lekérdezés lehet átmeneti → még ÉLŐ
    for _ in range(4):
        assert c.check_live() is True
    # az 5. egymás utáni hiba után viszont megszakadtnak vesszük
    assert c.check_live() is False
    assert c.is_live is False
    assert c.last_error


def test_sikeres_lekerdezes_nullazza_a_szamlalot():
    c = _live_caster(_OkEnc(1))       # 1 = aktív
    c._live_query_fails = 3
    assert c.check_live() is True
    assert c._live_query_fails == 0


def test_stopped_allapot_megszakadast_jelez():
    c = _live_caster(_OkEnc(0))       # 0 = BASS_ACTIVE_STOPPED
    assert c.check_live() is False
    assert c.is_live is False
