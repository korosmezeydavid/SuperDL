# -*- coding: utf-8 -*-
"""Dokumentum-konverter: megszakíthatóság + kimenet-ellenőrzés.
Herman Tibi DOC-P0-03 / DOC-P0-05."""
import pathlib
import sys
import zipfile

import pytest

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "modules_src" / "docconvert"))
from docconvert_mod import docconvert as DC        # noqa: E402


def _src(rel: str) -> str:
    return (ROOT / "modules_src" / rel).read_text(encoding="utf-8")


# ---- DOC-P0-05: kimenet-ellenőrzés ---------------------------------------

def test_nem_letezo_kimenet_elutasitva(tmp_path):
    with pytest.raises(RuntimeError):
        DC.validate_output(str(tmp_path / "nincs.txt"), "txt")


def test_ures_kimenet_elutasitva(tmp_path):
    p = tmp_path / "ures.docx"
    p.write_bytes(b"")
    with pytest.raises(RuntimeError, match="ÜRES"):
        DC.validate_output(str(p), "docx")


@pytest.mark.parametrize("fmt", ["docx", "epub"])
def test_serult_zip_alapu_kimenet_elutasitva(tmp_path, fmt):
    p = tmp_path / f"rossz.{fmt}"
    p.write_bytes(b"ez nem zip")
    with pytest.raises(RuntimeError, match="SÉRÜLT"):
        DC.validate_output(str(p), fmt)


def test_hianyos_docx_elutasitva(tmp_path):
    p = tmp_path / "hianyos.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("valami.txt", "x")
    with pytest.raises(RuntimeError, match="hiányzik"):
        DC.validate_output(str(p), "docx")


def test_hianyos_epub_elutasitva(tmp_path):
    p = tmp_path / "hianyos.epub"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("valami.txt", "x")
    with pytest.raises(RuntimeError, match="hiányzik"):
        DC.validate_output(str(p), "epub")


def test_ervenytelen_pdf_elutasitva(tmp_path):
    p = tmp_path / "rossz.pdf"
    p.write_bytes(b"NEM PDF")
    with pytest.raises(RuntimeError, match="PDF"):
        DC.validate_output(str(p), "pdf")


def test_ervenyes_kimenetek_atmennek(tmp_path):
    d = tmp_path / "jo.docx"
    with zipfile.ZipFile(d, "w") as z:
        z.writestr("word/document.xml", "<x/>")
    DC.validate_output(str(d), "docx")

    e = tmp_path / "jo.epub"
    with zipfile.ZipFile(e, "w") as z:
        z.writestr("META-INF/container.xml", "<x/>")
    DC.validate_output(str(e), "epub")

    pdf = tmp_path / "jo.pdf"
    pdf.write_bytes(b"%PDF-1.7\nx")
    DC.validate_output(str(pdf), "pdf")

    t = tmp_path / "jo.txt"
    t.write_text("szia", encoding="utf-8")
    DC.validate_output(str(t), "txt")


def test_a_convert_minden_utjan_ellenoriz():
    src = (ROOT / "modules_src" / "docconvert" / "docconvert_mod"
           / "docconvert.py").read_text(encoding="utf-8")
    assert "def _convert_inner" in src, "nincs burkoló, egyes utak kimaradnak"
    i = src.index("def convert(")
    torzs = src[i:i + 700]
    assert "validate_output(dst, out_format)" in torzs


# ---- DOC-P0-03: megszakíthatóság ----------------------------------------

def test_van_leallitas_gomb():
    src = _src("docconvert/docconvert_mod/docconvertwin.py")
    assert "stop_btn" in src and "_on_stop_convert" in src
    assert "Konvertálás &leállítása" in src


def test_a_koteg_fajlonkent_ellenoriz():
    src = _src("docconvert/docconvert_mod/docconvertwin.py")
    i = src.index("def _run_separate")
    torzs = src[i:i + 900]
    assert "_cancelled()" in torzs, "a köteg nem szakítható meg"
    assert "break" in torzs


def test_a_megszakitas_lathato_az_osszegzesben():
    src = _src("docconvert/docconvert_mod/docconvertwin.py")
    assert "LEÁLLÍTVA" in src, "a felhasználó nem tudja meg, hogy megszakadt"


def test_zaraskor_rakerdez():
    src = _src("docconvert/docconvert_mod/docconvertwin.py")
    i = src.index("def _on_close")
    torzs = src[i:i + 900]
    assert "self._busy" in torzs and "e.Veto()" in torzs
