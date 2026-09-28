"""Schibik Miklós (2026-09-28): ha a Játékok ablaka van elöl, és jön a
frissítés-kérdés, „lefagy az egész", amíg Alt+Tab-bal meg nem találja a
dobozt. A kérdés az AKTÍV ablakhoz kötődjön, ne a főablakhoz."""
import re
from pathlib import Path

GUI = (Path(__file__).resolve().parents[1] / "superdl_gui.py").read_text(
    encoding="utf-8")


def test_a_frissites_kerdesek_az_aktiv_ablakhoz_kotodnek():
    i = GUI.index("def _after_auto_check")
    j = GUI.index("def _offer_resume")
    resz = GUI[i:j]
    hivasok = re.findall(r"wx\.MessageBox\((.*?)\)\s*==", resz, re.S)
    assert len(hivasok) == 2
    for h in hivasok:
        assert "self.aktiv_ablak()" in h
        assert not re.search(r",\s*self\)\s*$", h.strip())


def test_aktiv_ablak_visszaesik_a_foablakra():
    assert "def aktiv_ablak(self)" in GUI
    i = GUI.index("def aktiv_ablak(self)")
    assert "return self" in GUI[i:i + 1200]
