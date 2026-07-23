# -*- coding: utf-8 -*-
"""MK2/2a: minden modul-ablak megkapja a `_closing` őrt, hogy a háttérszálas
wx.CallAfter-callbackek NE fussanak le, miután az ablakot bezárták
(„wrapped C/C++ object deleted" villódzó összeomlás megelőzése)."""
import os
import re

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
MODS = os.path.join(ROOT, "modules_src")

# (relatív útvonal, ablak-osztály neve nem kell, forrásból dolgozunk)
WINDOWS = [
    "konyvek/konyvek_mod/bookwin.py",
    "konyvek/konyvek_mod/readerwin.py",
    "docconvert/docconvert_mod/docconvertwin.py",
    "hangalamondas/hangalamondas_mod/videodescribewin.py",
    "mediatools/mediatools_mod/convertwin.py",
    "mediatools/mediatools_mod/mediaanalyzewin.py",
    "mediatools/mediatools_mod/ringtonewin.py",
    "mediatools/mediatools_mod/videoeditwin.py",
    "mediatools/mediatools_mod/videowin.py",
    "iptv/iptv_mod/iptvwin.py",
    "radio/radio_mod/radiowin.py",
    "supermedia/supermedia_mod/supereditwin.py",
    "supermedia/supermedia_mod/supermwin.py",
    # 2. audit (Herman Tibi, kimaradt modulok): NEWS/POD/INFO/REC/VC-P0
    "szervezes/szervezes_mod/newswin.py",
    "szervezes/szervezes_mod/podcastwin.py",
    "szervezes/szervezes_mod/dayinfowin.py",
    "szervezes/szervezes_mod/organizerwin.py",
    "supermedia/supermedia_mod/superrecwin.py",
    "supermedia/supermedia_mod/supervoicewin.py",
    "supermedia/supermedia_mod/superstreamwin.py",
]


def _src(rel):
    with open(os.path.join(MODS, rel), encoding="utf-8") as f:
        return f.read()


def test_minden_ablak_inicializalja_a_closing_flaget():
    for rel in WINDOWS:
        src = _src(rel)
        assert "self._closing = False" in src, f"{rel}: hiányzik a _closing init"


def test_minden_ablak_beallitja_a_closingot_zaraskor():
    """A _on_close-ban valahol True-ra kell állnia."""
    for rel in WINDOWS:
        src = _src(rel)
        # _on_close blokk kikeresése és benne a True-ra állítás
        m = re.search(r"def _on_close\(self.*?\):(.*?)(?=\n    def |\Z)", src, re.S)
        assert m, f"{rel}: nincs _on_close"
        assert "self._closing = True" in m.group(1), \
            f"{rel}: a _on_close nem állítja True-ra a _closing-ot"


def test_van_legalabb_egy_ordott_callback():
    """Legalább egy `if self._closing` őr legyen a callbackekben. (Lehet
    kombinált is, pl. `if self._closing or gen != self._wgen:` – a generációs
    stale-védelemmel együtt.)"""
    for rel in WINDOWS:
        src = _src(rel)
        assert "if self._closing" in src, f"{rel}: nincs egyetlen _closing-őr sem"
