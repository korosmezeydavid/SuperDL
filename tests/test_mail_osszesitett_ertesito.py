# -*- coding: utf-8 -*-
"""Super Mail: az egyesített (Összes bejövő) nézetben is a FIÓKONKÉNTI
értesítő szól (Schibik Miklós jelzése, 2026-10-01).

Eddig az egyesített nézet háttér-köre mindig az alapmondatot mondta („2 új
levél érkezett.”), a fiókhoz beállított saját szöveget, hangot vagy „nincs”-et
figyelmen kívül hagyta – ezért „nem jött össze” a saját szöveg.
"""
import ast
import sys
from pathlib import Path

GYOKER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GYOKER / "modules_src" / "mail"))

import pytest                            # noqa: E402
from mail_mod import mail_core as MC     # noqa: E402

if not hasattr(MC, "osszesitett_ertesites"):
    pytest.skip("a Super Mail forrása ebben a tárolóban régebbi",
                allow_module_level=True)

BEALL = {
    "gmail@x.hu": {"tipus": "szoveg", "szoveg": "Levél jött a Gmailre.", "hang": ""},
    "freemail@x.hu": {"tipus": "szoveg", "szoveg": "Új leveled érkezett.", "hang": ""},
    "nema@x.hu": {"tipus": "nincs", "szoveg": "", "hang": ""},
    "hangos@x.hu": {"tipus": "hang", "szoveg": "", "hang": "csengo.wav"},
}


def _cfg(em):
    return BEALL.get(em, {"tipus": "szoveg", "szoveg": MC.ALAP_ERTESITO_SZOVEG, "hang": ""})


def test_sajat_szoveg_elhangzik():
    r, alap, h = MC.osszesitett_ertesites([("gmail@x.hu", 2)], _cfg)
    assert r == ["Levél jött a Gmailre."] and alap == 0 and h == []


def test_alap_szovegu_fiokok_osszeszamolva():
    r, alap, h = MC.osszesitett_ertesites(
        [("freemail@x.hu", 2), ("mas@x.hu", 1), ("gmail@x.hu", 1)], _cfg)
    assert r == ["Levél jött a Gmailre."] and alap == 3


def test_nincs_es_hang():
    r, alap, h = MC.osszesitett_ertesites(
        [("nema@x.hu", 4), ("hangos@x.hu", 2)], _cfg)
    assert r == [] and alap == 0 and h == [("csengo.wav", 2)]


def test_ismetles_nelkul_es_nulla_darab():
    r, alap, h = MC.osszesitett_ertesites(
        [("gmail@x.hu", 1), ("gmail@x.hu", 1), ("mas@x.hu", 0)], _cfg)
    assert r == ["Levél jött a Gmailre."] and alap == 0


def test_az_egyesitett_nezet_ezt_hasznalja():
    forras = (GYOKER / "modules_src" / "mail" / "mail_mod" / "mailwin.py").read_text(
        encoding="utf-8")
    fa = ast.parse(forras)
    fv = next(n for n in ast.walk(fa)
              if isinstance(n, ast.FunctionDef) and n.name == "_ertesit_osszes")
    assert "osszesitett_ertesites" in ast.unparse(fv)
    assert "_osszes_uj_fiokok" in forras
