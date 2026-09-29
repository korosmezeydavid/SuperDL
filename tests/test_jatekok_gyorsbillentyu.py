"""A Játékok modul gyorsbillentyűje nem ütközhet a főablak parancsaival.

Turai László (2026-09-29): „a játékok modul nem jön be a CTRL+SHIFT+J
kombinációra. A program közli, hogy nincs aktív letöltés." Ok: a Ctrl+Shift+J
a főablakban a „Mi a helyzet?" parancs is volt, és az nyert. A Játékok ezért
Ctrl+Alt+J-re költözött; ez a teszt őrzi, hogy se a főablak, se más modul
ne vegye el tőle, és hogy a régi ütközés ne jöjjön vissza."""

import glob
import os
import re

GYOKER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MINTA = re.compile(r"\\t((?:Ctrl|Alt|Shift)\+[A-Za-z0-9+.,]+)")


def _gyorsbillentyuk(ut):
    with open(ut, encoding="utf-8") as f:
        return MINTA.findall(f.read())


def _fo_es_modulok():
    fajlok = [os.path.join(GYOKER, "superdl_gui.py")]
    fajlok += glob.glob(os.path.join(GYOKER, "modules_src", "*", "*_mod",
                                     "__init__.py"))
    return fajlok


def test_jatekok_ctrl_alt_j():
    ut = os.path.join(GYOKER, "modules_src", "jatekok", "jatekok_mod",
                      "__init__.py")
    assert _gyorsbillentyuk(ut) == ["Ctrl+Alt+J"]


def test_ctrl_alt_j_csak_a_jatekoke():
    kik = [f for f in _fo_es_modulok() if "Ctrl+Alt+J" in _gyorsbillentyuk(f)]
    assert len(kik) == 1 and "jatekok" in kik[0]


def test_ctrl_shift_j_csak_a_mi_a_helyzet():
    kik = [f for f in _fo_es_modulok() if "Ctrl+Shift+J" in _gyorsbillentyuk(f)]
    assert [os.path.basename(f) for f in kik] == ["superdl_gui.py"]
