# -*- coding: utf-8 -*-
"""A `~$` Office-zárolófájlok nem valók a fájllistába.

Schibik Miklós jelzése (2026-09-14): „A fájl lista végén van egy csomó
tilde-el kezdődő fájl. Ezeket nem lehet megnyitni, sőt volt, hogy egy
DOCX-re le is fagyott az egész. Még a Jaws is."
"""
from superdl import fajlvalaszto


def test_a_zarolofajlok_kimaradnak(tmp_path):
    (tmp_path / "Regenyem.docx").write_text("x", encoding="utf-8")
    (tmp_path / "~$genyem.docx").write_text("x", encoding="utf-8")
    (tmp_path / "~$tablazat.xlsx").write_text("x", encoding="utf-8")
    mappak, fajlok = fajlvalaszto.tartalom(str(tmp_path))
    assert fajlok == ["Regenyem.docx"]
    assert mappak == []


def test_a_tilde_onmagaban_nem_zarolofajl(tmp_path):
    """Csak a `~$` pár szűr. Egy sima tildével kezdődő fájlnév a
    felhasználó saját fájlja lehet – azt elvenni tőle hiba volna."""
    (tmp_path / "~vazlat.txt").write_text("x", encoding="utf-8")
    (tmp_path / "~$vazlat.docx").write_text("x", encoding="utf-8")
    _, fajlok = fajlvalaszto.tartalom(str(tmp_path))
    assert fajlok == ["~vazlat.txt"]


def test_a_zarolomappa_is_kimarad(tmp_path):
    (tmp_path / "~$mappa").mkdir()
    (tmp_path / "Konyvek").mkdir()
    mappak, _ = fajlvalaszto.tartalom(str(tmp_path))
    assert mappak == ["Konyvek"]


def test_kiterjesztes_szuressel_egyutt_is(tmp_path):
    (tmp_path / "a.docx").write_text("x", encoding="utf-8")
    (tmp_path / "~$a.docx").write_text("x", encoding="utf-8")
    (tmp_path / "b.txt").write_text("x", encoding="utf-8")
    _, fajlok = fajlvalaszto.tartalom(str(tmp_path), (".docx",))
    assert fajlok == ["a.docx"]
