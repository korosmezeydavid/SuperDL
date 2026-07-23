# -*- coding: utf-8 -*-
"""Memória-keret a visszavonáshoz + a mentetlen munka védelme.
Herman Tibi EDIT-P0-01 / REC-P0-04 / EDIT-P0-06."""
import os
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


# ---- REC-P0-01/02: a felvétel LEMEZRE folyik, nem a memóriába -------------

from supermedia_mod import superrec as SR      # noqa: E402


def _feed(r, mb: float):
    """„Felvétel” szimulálása a visszahívás pufferén át."""
    blokk = b"\x00\x01" * 8192                 # 16 KB
    n = int(mb * 1024 * 1024 / len(blokk))
    for _ in range(n):
        with r._lock:
            r._buf.append(blokk)
            r._buf_bytes += len(blokk)
            r._bytes += len(blokk)
        if r._buf_bytes > 1_000_000:
            r._drain()
    r._flush()


def test_a_felvetel_lemezre_kerul_es_a_memoria_ures_marad():
    r = SR.Recorder()
    try:
        r._open_spill()
        _feed(r, 8)
        assert os.path.getsize(r._spill) == r._bytes, "nem minden ment lemezre"
        assert r._buf_bytes == 0, "maradt bent nem kiírt puffer"
    finally:
        r.close()


def test_a_spill_fajl_zaraskor_torlodik():
    r = SR.Recorder()
    r._open_spill()
    _feed(r, 1)
    p = r._spill
    assert os.path.exists(p)
    r.close()
    assert not os.path.exists(p), "az ideiglenes PCM-fájl bent maradt"


def test_streamelt_wav_mentes_helyes_hosszal(tmp_path):
    import wave
    r = SR.Recorder(freq=44100, channels=2)
    try:
        r._open_spill()
        _feed(r, 4)
        out = str(tmp_path / "felvetel.wav")
        r.save(out)
        with wave.open(out, "rb") as w:
            assert w.getframerate() == 44100 and w.getnchannels() == 2
            assert w.getnframes() == r._bytes // 4
    finally:
        r.close()


def test_reset_uritte_a_felvetelt():
    r = SR.Recorder()
    try:
        r._open_spill()
        _feed(r, 1)
        assert r.has_audio() is True
        r.reset()
        assert r.has_audio() is False and r._bytes == 0
    finally:
        r.close()


def test_pcm_path_es_pcm_bytes_egyezik():
    r = SR.Recorder()
    try:
        r._open_spill()
        _feed(r, 1)
        assert os.path.getsize(r.pcm_path()) == len(r.pcm_bytes())
    finally:
        r.close()


def test_save_pcm_file_letezik_es_streamel():
    src = (ROOT / "modules_src" / "supermedia" / "supermedia_mod"
           / "superrec.py").read_text(encoding="utf-8")
    assert "def save_pcm_file" in src
    assert "def write_wav_from_pcm_file" in src
    assert "self._chunks" not in src, "maradt memóriában gyűjtő chunk-lista"
