# -*- coding: utf-8 -*-
"""Petrus József, 2026-09-30:
1. Az Akciós újság "Megnyitás a Super Editben" a Super Recorder hangszerkesztőjét
   nyitotta - a supermedia modul ugyanazt az ablakkulcsot (superedit_module)
   foglalta, mint a Super Edit szövegszerkesztő.
2. A Spar-listán a MySpar-os / kuponos ár elveszett, ha a PDF egy sorba ragasztotta
   a nagy árat és az egységárat ("999(3.330 Ft/1 kg)").
3. A mennyiségi akció (SPAR Verde: 6 db-tól 119 Ft/db) a listasorban nem hangzott el.
"""
import ast
import os
import sys

GYOKER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(GYOKER, "modules_src", "akciok"))

from akciok_mod import spar  # noqa: E402
from akciok_mod.termek import Termek  # noqa: E402


def _ablakkulcsok():
    """{kulcs: [modul, ...]} - minden modul register_window / _add kulcsa."""
    ki = {}
    src = os.path.join(GYOKER, "modules_src")
    for modul in sorted(os.listdir(src)):
        for gy, _d, fajlok in os.walk(os.path.join(src, modul)):
            if "__init__.py" not in fajlok or "__pycache__" in gy:
                continue
            fa = ast.parse(open(os.path.join(gy, "__init__.py"), encoding="utf-8").read())
            for n in ast.walk(fa):
                if not isinstance(n, ast.Call):
                    continue
                nev = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
                if nev not in ("register_window", "_add"):
                    continue
                for a in n.args[:3]:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                            and a.value.endswith("_module"):
                        ki.setdefault(a.value, []).append(modul)
    return ki


def test_ablakkulcsok_egyediek():
    kulcsok = _ablakkulcsok()
    assert "superedit_module" in kulcsok
    dupla = {k: v for k, v in kulcsok.items() if len(v) > 1}
    assert not dupla, dupla


def test_superedit_kulcs_a_szovegszerkesztoe():
    assert _ablakkulcsok()["superedit_module"] == ["superedit"]


SZOVEG = "\n".join([
    "Regnum füstölt,", "főtt tarja", "a kiszolgálópultban", "(5.290 Ft/1 kg)",
    "529 Ft", "MYSPAR ÁR*", "-24%", "399(3.990 Ft/1 kg)", "Ft", "/10 dkg",
    "1001_ISP_10-11.indd 10", "2026. 09. 24. 12:33",
    "Regnum", "hot-dog kolbász", "csomagolt", "300 g", "(5.330 Ft/1 kg)",
    "1.599 Ft", "MYSPAR", "KUPONOS ÁR:", "Ft", "999(3.330 Ft/1 kg)",
    "SPAR Verde", "ásványvíz", "1,5 l", "(119,35 Ft/1 l)", "6 db esetén:",
    "(79,33 Ft/1 l)", "(+visszaváltási", "díj: 50 Ft)",
])


def _tetelek():
    return {t.nev: t for t in spar.termekek(SZOVEG, "Spar szórólap")}


def test_ragadt_kuponos_ar_megmarad():
    t = _tetelek()["Regnum hot-dog kolbász csomagolt"]
    assert t.ar == 1599
    assert t.kartyas_ar == 999 and t.kartya_nev == "MySpar-kuponnal"
    assert "999" in t.sor()


def test_ragadt_myspar_ar_pultos():
    t = _tetelek()["Regnum füstölt, főtt tarja"]
    assert t.ar == 5290 and t.kartyas_ar == 3990 and t.kartya_nev == "MySpar-ral"


def test_nyomdai_szemet_nem_kerul_a_nevbe():
    for nev in _tetelek():
        assert "indd" not in nev and "12:33" not in nev, nev


def test_mennyisegi_akcio_a_listasorban():
    t = _tetelek()["SPAR Verde ásványvíz"]
    assert t.ar == 179 and "6 db-tól 119 Ft/db" in t.megjegyzes
    assert "6 db-tól 119 Ft/db" in t.sor()
    assert "6 db-tól 119 Ft/db" in t.sor(bolttal=True, legjobb_elol=True)


def test_mas_megjegyzes_nem_kerul_a_sorba():
    t = Termek(bolt="X", nev="Alma", ar=100, megjegyzes="csak online")
    assert "online" not in t.sor()
