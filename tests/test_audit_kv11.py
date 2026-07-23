# -*- coding: utf-8 -*-
"""Memória-keret a visszavonáshoz + a mentetlen munka védelme.
Herman Tibi EDIT-P0-01 / REC-P0-04 / EDIT-P0-06."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "modules_src" / "supermedia"))
from supermedia_mod import supereditor            # noqa: E402


def _src(rel: str) -> str:
    return (ROOT / "modules_src" / rel).read_text(encoding="utf-8")


def _clip(mb: float) -> supereditor.Clip:
    return supereditor.Clip(pcm=b"\x00\x01" * int(mb * 1024 * 1024 / 2),
                            freq=44100, channels=2)


# ---- EDIT-P0-01: az undo nem eheti meg a memóriát -------------------------

def test_az_undo_keret_letezik():
    c = supereditor.Clip()
    assert getattr(c, "_undo_budget", 0) > 0


def test_sok_szerkesztes_utan_a_memoria_keret_alatt_marad():
    """A régi kód 30 TELJES másolatot tartott: egy nagy klipnél több tíz GB."""
    c = _clip(4)                       # 4 MB-os klip
    c._undo_budget = 12 * 1024 * 1024  # 12 MB keret a teszthez
    for _ in range(30):
        c._snapshot()
    assert c.undo_memory_bytes() <= c._undo_budget, \
        f"{c.undo_memory_bytes()} bájt > {c._undo_budget}"
    assert len(c._undo) < 30, "a keret nem nyesett semmit"


def test_a_visszavonas_a_keret_mellett_is_mukodik():
    c = _clip(2)
    c._undo_budget = 1                 # szélsőséges: 1 bájt keret
    c._snapshot()
    c._snapshot()
    assert c.can_undo() is True, "a legutóbbi lépés is kiesett"
    assert c.undo() is True


def test_a_redo_verem_sem_no_korlatlanul():
    c = _clip(2)
    c._undo_budget = 3 * 1024 * 1024
    for _ in range(10):
        c._snapshot()
    for _ in range(10):
        c.undo()
    assert c.undo_memory_bytes() <= c._undo_budget * 2 + 1024


def test_darabszam_korlat_tovabbra_is_el():
    c = _clip(0.01)                    # apró klip: a keret nem fog beavatkozni
    for _ in range(50):
        c._snapshot()
    assert len(c._undo) <= c._max_undo


# ---- REC-P0-04 / EDIT-P0-06: a mentetlen munka nem veszhet el -------------

def test_felvevo_rakerdez_a_mentetlen_felvetelre():
    src = _src("supermedia/supermedia_mod/superrecwin.py")
    assert "_has_unsaved_audio" in src
    assert "ELVÉSZ" in src and "e.Veto()" in src
    i = src.index("def _on_close")
    assert "_has_unsaved_audio()" in src[i:i + 700], \
        "a zárás nem kérdez rá a mentetlen felvételre"


def test_felvetel_inditasa_mentetlenne_tesz():
    src = _src("supermedia/supermedia_mod/superrecwin.py")
    assert "self._saved = False" in src and "self._saved = True" in src


def test_szerkeszto_rakerdez_a_mentetlen_munkara():
    src = _src("supermedia/supermedia_mod/supereditwin.py")
    assert "_has_unsaved_edit" in src
    assert "ELVESZNEK" in src and "e.Veto()" in src
    i = src.index("def _on_close")
    assert "_has_unsaved_edit()" in src[i:i + 700]


def test_szerkesztes_utan_mentetlen_mentes_utan_tiszta():
    src = _src("supermedia/supermedia_mod/supereditwin.py")
    i = src.index("def _after_edit")
    assert "self._saved = False" in src[i:i + 200], \
        "a szerkesztés nem jelöli mentetlennek"
    j = src.index("def _save_done")
    assert "self._saved = True" in src[j:j + 400], \
        "a sikeres mentés nem törli a mentetlen jelzést"
