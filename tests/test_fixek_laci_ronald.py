# -*- coding: utf-8 -*-
"""Laci + a rádiós felhasználó jelentéseinek javításai (create maxima kör).

A GUI-kód (wx) fejtelen tesztkörnyezetben nem példányosítható, ezért a BEKÖTÉST
a forrásszövegből ellenőrizzük (mint a test_feeds_seen), a tiszta függvényt
(`_rovid_hiba`) pedig futtatva. A lényeg minden esetben egy konkrét, korábban
HIÁNYZÓ bekötés/ág, ami a jelentett hibát okozta."""
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ---- A) TÁLCA: asztali indításnál is legyen close-to-tray, ha be van kapcsolva

def test_tálca_asztali_inditasnal_visszaallitja_a_tray_modot():
    s = _src("superdl_gui.py")
    # a NEM-háttér (asztali) ágon, ha az autostart be van kapcsolva, _ensure_tray
    i = s.index("frame.Show()")
    reszlet = s[i:i + 900]
    assert "autostart.is_enabled()" in reszlet
    assert "frame._ensure_tray()" in reszlet


# ---- B) FELOLVASÓ: AcceleratorTable + F8 hallhatóság + verzió + hallható hiba

def test_felolvaso_verzio_es_rovid_hiba():
    import json
    import pathlib
    m = importlib.import_module(
        "modules_src.felolvaso.felolvaso_mod.felolvasowin")
    # a futásidejű MOD_VERSION egyezzen a manifesttel (SUB-P2-29: ne csússzon
    # szét a kézi konstans és a manifest – így a teszt magától követi a bumpot)
    manifest = json.loads((pathlib.Path(__file__).parent.parent
                           / "modules_src" / "felolvaso" / "manifest.json"
                           ).read_text(encoding="utf-8"))
    assert m.MOD_VERSION == manifest["version"]
    # a hiba rövidítve, felolvashatóan jön vissza
    assert m._rovid_hiba("  sapi:   valami   hiba ") == "sapi: valami hiba"
    hosszu = m._rovid_hiba("x" * 300)
    assert hosszu.endswith("…") and len(hosszu) <= 141


def test_felolvaso_acceleratortable_minden_vezerlon():
    s = _src("modules_src/felolvaso/felolvaso_mod/felolvasowin.py")
    assert "def _setup_accelerators" in s
    assert "SetAcceleratorTable" in s
    # a globális gyorsbillentyűk accelerator-ral (nem csak CHAR_HOOK-kal)
    for k in ("WXK_F8", "WXK_UP", "WXK_DOWN", "ACCEL_CTRL"):
        assert k in s
    # a _setup_accelerators-t meghívjuk az indításkor
    assert "self._setup_accelerators()" in s


def test_felolvaso_f8_kepernyoolvasora_is_szol():
    s = _src("modules_src/felolvaso/felolvaso_mod/felolvasowin.py")
    # az _announce a némított selfvoice esetén a képernyőolvasónak szól
    assert "screenreader" in s
    assert "getattr(sv, \"muted\", False)" in s
    assert "screenreader.speak(" in s


# ---- C) RÁDIÓ: a valódi hiba – a „Hozzáadás" gomb nem volt bekötve

def test_radio_hozzaadas_gomb_be_van_kotve():
    s = _src("modules_src/radio/radio_mod/radiowin.py")
    # ez volt a gyökér-ok: a _on_ok SEHOL nem volt bekötve → station None maradt
    assert "ok.Bind(wx.EVT_BUTTON, self._on_ok)" in s


def test_radio_kedvencekre_fokuszal_es_jobb_forras():
    s = _src("modules_src/radio/radio_mod/radiowin.py")
    assert "def _select_fav" in s
    assert "def _add_better_source" in s
    # az _add_custom a végén a Kedvencekre viszi a fókuszt
    assert "self._select_fav(st)" in s
    # a „jobb minőségű forrás" előre kitöltött párbeszédet nyit
    assert "CustomStationDialog(self, preset=" in s
    # a párbeszéd fogadja a preset-et és előre kitölti az URL-t
    assert "def __init__(self, parent, preset=None)" in s
    assert "self.c_url.SetValue(preset.url" in s


def test_radio_gomb_a_feluleten():
    s = _src("modules_src/radio/radio_mod/radiowin.py")
    assert "Jobb minőségű forrás" in s
    assert "b_better.Bind(wx.EVT_BUTTON, lambda e: self._add_better_source())" in s


# ---- D) FRISSÍTÉS-ELLENŐRZÉS: periodikusan is, ne csak induláskor (Laci)

def test_frissites_ellenorzes_periodikusan_is_fut():
    """Eddig az _auto_update_check CSAK induláskor futott egyszer → aki a
    programot a tálcán/háttérben futtatja (napokig nyitva), sosem kapott
    automatikus frissítés-ajánlatot. Mostantól a 15 perces időzítő is meghívja
    (napi zárral olcsó), így az always-on példány is újraellenőriz."""
    s = _src("superdl_gui.py")
    # a periodikus feed-időzítő kezelője meghívja a frissítés-ellenőrzést
    i = s.index("def _on_feed_timer")
    reszlet = s[i:i + 700]
    assert "self._auto_update_check()" in reszlet
    # és a napi zár a helyén van (naponta ténylegesen egyszer fut le)
    assert "update_last_check" in s
