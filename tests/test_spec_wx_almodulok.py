# -*- coding: utf-8 -*-
"""A modulok `wx.<almodul>` importjai benne vannak-e a fagyasztott csomagban.

Schibik Miklós, 2026-09-28: a Super Mail HTML nézete a kiadott programban
MINDENKINÉL azt mondta, hogy „az Edge WebView2 ezen a gépen nem érhető el" –
pedig telepítve volt. Ok: a `wx.html2`-t csak a (futás közben betöltött) mail
modul importálja, a Core nem, ezért a PyInstaller kihagyta a `_html2`
bővítményt és a WebView2Loader.dll-t. A `tools/modul_importok.py` nem látta,
mert csak a legfelső nevet (`wx`) nézi.

Ez a teszt a FORRÁSBÓL dolgozik (build nélkül, CI-ben is fut): minden
`wx.<almodul>`, amit egy modul importál, és a Core nem, szerepeljen mindkét
GUI-spec hiddenimports-ában.
"""

import ast
import io
import os

GYOKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SPECEK = ("SuperDL.spec", "SuperDL-onedir.spec")
# amit a Core maga is importál, azt a PyInstaller magától is látja
CORE_LATJA = {"wx.adv", "wx.html", "wx.lib"}


def _wx_almodulok(mappa):
    ki = set()
    for tok, _d, fajlok in os.walk(mappa):
        for f in fajlok:
            if not f.endswith(".py"):
                continue
            try:
                fa = ast.parse(io.open(os.path.join(tok, f),
                                       encoding="utf-8").read())
            except Exception:
                continue
            for cs in ast.walk(fa):
                if isinstance(cs, ast.Import):
                    for a in cs.names:
                        if a.name.startswith("wx."):
                            ki.add(".".join(a.name.split(".")[:2]))
                elif isinstance(cs, ast.ImportFrom) and cs.level == 0 \
                        and cs.module and cs.module.startswith("wx."):
                    ki.add(".".join(cs.module.split(".")[:2]))
    return ki


def test_html2_a_ket_specben():
    for nev in SPECEK:
        szoveg = io.open(os.path.join(GYOKER, nev), encoding="utf-8").read()
        assert "'wx.html2'" in szoveg, nev
        assert "WebView2Loader.dll" in szoveg, nev


def test_minden_modul_wx_almodul_bent_van():
    hasznalt = _wx_almodulok(os.path.join(GYOKER, "modules_src"))
    kell = sorted(hasznalt - CORE_LATJA)
    for nev in SPECEK:
        szoveg = io.open(os.path.join(GYOKER, nev), encoding="utf-8").read()
        hiany = [m for m in kell if "'%s'" % m not in szoveg]
        assert not hiany, "%s: hiányzik a hiddenimports-ból: %s" % (nev, hiany)
