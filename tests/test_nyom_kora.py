# -*- coding: utf-8 -*-
"""A nyom KÖRÜLMÉNYE: mikor volt, melyik verzióban, mi jött utána.

Dr. Kiss István 2026-09-16-i jelentése négy napos nyomot hordozott egy
AZÓTA JAVÍTOTT hibáról (`bookwin.py` `_on_pick_book`, 4.6.7), és utána
huszonöt indulás következett baj nélkül. A jelentés élén viszont csak egy
dátumtalan ⚠️ állt — így úgy nézett ki, mintha a program most omlott volna
össze. A nyom marad; a körülménye kerül mellé.
"""
from superdl import diagnostics, osszeomlas

_NAPLO = """
=== SuperDL indult: 2026-09-12 15:07:39 (verzió: 4.6.7) ===
Windows fatal exception: access violation

Current thread 0x00002944 (most recent call first):
  File "bookwin.py", line 361 in _on_pick_book

=== SuperDL indult: 2026-09-13 00:40:45 (verzió: 4.6.8) ===

=== SuperDL indult: 2026-09-14 21:34:46 (verzió: 4.6.11) ===

=== SuperDL indult: 2026-09-16 00:02:27 (verzió: 4.6.11) ===
"""


def _naplot_ir(tmp_path, monkeypatch, szoveg):
    p = tmp_path / "osszeomlas.log"
    p.write_text(szoveg, encoding="utf-8")
    monkeypatch.setattr(osszeomlas, "NAPLO", p)
    return p


def test_megmondja_mikor_es_melyik_verzioban(tmp_path, monkeypatch):
    _naplot_ir(tmp_path, monkeypatch, _NAPLO)
    info = osszeomlas.nyom_kora()
    assert info["ido"] == "2026-09-12 15:07:39"
    assert info["verzio"] == "4.6.7"


def test_megszamolja_az_azota_tortent_indulasokat(tmp_path, monkeypatch):
    _naplot_ir(tmp_path, monkeypatch, _NAPLO)
    info = osszeomlas.nyom_kora()
    assert info["ota"] == 3
    assert info["most"] == "4.6.11"


def test_friss_nyomnal_nincs_azota(tmp_path, monkeypatch):
    """Ha a nyom után NEM volt indulás, akkor tényleg most történt."""
    _naplot_ir(tmp_path, monkeypatch,
               "=== SuperDL indult: 2026-09-16 08:00:00 (verzió: 4.6.12) ===\n"
               "Windows fatal exception: access violation\n"
               "Current thread 0x1 (most recent call first):\n")
    info = osszeomlas.nyom_kora()
    assert info["ota"] == 0
    assert info["verzio"] == "4.6.12"


def test_nyom_nelkul_ures(tmp_path, monkeypatch):
    _naplot_ir(tmp_path, monkeypatch,
               "=== SuperDL indult: 2026-09-16 08:00:00 (verzió: 4.6.12) ===\n")
    assert osszeomlas.nyom_kora() == {}


def test_hianyzo_naplo_nem_dob_kivetelt(tmp_path, monkeypatch):
    monkeypatch.setattr(osszeomlas, "NAPLO", tmp_path / "nincs.log")
    assert osszeomlas.nyom_kora() == {}


# --- ami a jelentésbe kerül -------------------------------------------

def test_a_jelentes_kiirja_a_korulmenyt(tmp_path, monkeypatch):
    _naplot_ir(tmp_path, monkeypatch, _NAPLO)
    sorok = diagnostics._nyom_kora_sorok(osszeomlas)
    egyben = " ".join(sorok)
    assert "2026-09-12 15:07:39" in egyben
    assert "4.6.7" in egyben
    assert "3 indulás" in egyben


def test_regi_verzional_kulon_figyelmeztet(tmp_path, monkeypatch):
    """Ez a mondat a lényeg: a nyom nem a most futó programból való."""
    _naplot_ir(tmp_path, monkeypatch, _NAPLO)
    egyben = " ".join(diagnostics._nyom_kora_sorok(osszeomlas))
    assert "KORÁBBI verzióból" in egyben
    assert "4.6.11" in egyben


def test_azonos_verzional_nincs_felesleges_figyelmeztetes(tmp_path,
                                                          monkeypatch):
    """Ha a nyom a MOST futó verzióból való, a „már javítottuk" mondat
    hazugság volna — ilyenkor nem szabad megjelennie."""
    _naplot_ir(tmp_path, monkeypatch,
               "=== SuperDL indult: 2026-09-16 08:00:00 (verzió: 4.6.12) ===\n"
               "Windows fatal exception: access violation\n"
               "Current thread 0x1 (most recent call first):\n"
               "\n"
               "=== SuperDL indult: 2026-09-16 09:00:00 (verzió: 4.6.12) ===\n")
    egyben = " ".join(diagnostics._nyom_kora_sorok(osszeomlas))
    assert "1 indulás" in egyben
    assert "KORÁBBI verzióból" not in egyben


def test_nyom_nelkul_semmit_nem_ir(tmp_path, monkeypatch):
    monkeypatch.setattr(osszeomlas, "NAPLO", tmp_path / "nincs.log")
    assert diagnostics._nyom_kora_sorok(osszeomlas) == []
