# -*- coding: utf-8 -*-
"""A NEGYEDIK bajtípus elleni őrök: „fut, de halott".

Ami csak a letöltött modulokban szerepel, azt a Core sehol nem importálja,
ezért a PyInstaller elemzője NEM LÁTJA. Az ilyen modul betöltődik, a menüje
megjelenik, és a művelet ImportErrorral hal meg. Így veszett el a 4.6.11
első buildjéből a `plistlib` (iPhone modul) és a `comtypes`.
"""
import io
import os

import pytest

GYOKER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MI = pytest.importorskip("tools.modul_importok")


def _spec(nev):
    return io.open(os.path.join(GYOKER, nev), encoding="utf-8").read()


def test_a_modulok_kulso_importjai_szerepelnek_a_specekben():
    """Amit a modulok importálnak, annak MINDKÉT spec-ben ott kell lennie."""
    nevek = MI.modul_importok(GYOKER)
    gui, onedir = _spec("SuperDL.spec"), _spec("SuperDL-onedir.spec")
    # csak azok, amikről tudjuk, hogy külső vagy modul-only import
    figyelt = ["plistlib", "comtypes", "docx", "fpdf", "bs4"]
    for nev in figyelt:
        if nev not in nevek:
            continue
        assert nev in gui, f"{nev} hiányzik a SuperDL.spec-ből"
        assert nev in onedir, f"{nev} hiányzik a SuperDL-onedir.spec-ből"


def test_egy_modul_sem_importal_a_forrasfabol():
    """`modules_src.…` CSAK a forrásfában létezik.

    A kiadott programban a modulok a ~/.superdl/modules/<id>/ alá kerülnek,
    ezért egy ilyen import ott MINDIG ImportError – és ha néma `except` van
    körülötte, a funkció csendben soha nem fut le. A Könyvek modul
    telefon-felajánlása pontosan így volt halott.
    """
    rosszak = []
    for tok, _d, fajlok in os.walk(os.path.join(GYOKER, "modules_src")):
        for f in fajlok:
            if not f.endswith(".py"):
                continue
            ut = os.path.join(tok, f)
            szoveg = io.open(ut, encoding="utf-8").read()
            for i, sor in enumerate(szoveg.split("\n"), 1):
                csupasz = sor.strip()
                if csupasz.startswith("#"):
                    continue
                if "from modules_src" in csupasz or \
                        csupasz.startswith("import modules_src"):
                    # tartalékként (ImportError-ág) megengedett
                    if "except ImportError" in szoveg:
                        continue
                    rosszak.append(f"{os.path.relpath(ut, GYOKER)}:{i}")
    assert not rosszak, "forrásfás import a modulokban: " + ", ".join(rosszak)
