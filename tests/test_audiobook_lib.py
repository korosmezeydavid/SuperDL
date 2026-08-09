# -*- coding: utf-8 -*-
"""A hangoskönyv-polc (AudioLibrary) és a sáv-segédek tesztjei."""
import pathlib

import pytest

AP = pytest.importorskip("modules_src.konyvek.konyvek_mod.audiobook_player")


@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.setattr(AP, "_LIB_FILE", tmp_path / "audiobook_library.json")
    return AP.AudioLibrary()


def test_upsert_es_kulcs(lib):
    lib.upsert(r"D:\Hang\sorozat", "Sorozat 1", is_dir=True)
    lib.upsert(r"C:\zene\nagy.mp3", "Nagy", is_dir=False)
    assert len(lib.items) == 2
    # ugyanaz a mappanév más úton -> ugyanaz a kulcs (nem duplikál)
    lib.upsert(r"E:\masutt\SOROZAT", "Sorozat 1", is_dir=True)
    assert len(lib.items) == 2
    it = lib.get(AP.konyv_kulcs(r"x/sorozat", True))
    assert it["path"] == r"E:\masutt\SOROZAT"     # a legutóbbi út marad


def test_resume_es_perzisztencia(lib, tmp_path, monkeypatch):
    lib.upsert(r"D:\Hang\sorozat", "Sorozat", is_dir=True)
    k = AP.konyv_kulcs("sorozat", True)
    lib.set_resume(k, "s01e03.mp3", 754000)
    # újratöltés ugyanarról a fájlról
    ujra = AP.AudioLibrary()
    it = ujra.get(k)
    assert it["track"] == "s01e03.mp3" and it["ms"] == 754000
    assert it["path"] == r"D:\Hang\sorozat"


def test_recent_sorrend(lib):
    import time
    lib.upsert(r"a\egy", "Egy", is_dir=True)
    time.sleep(0.01)
    lib.upsert(r"a\ketto", "Kettő", is_dir=True)
    r = lib.recent()
    assert r[0]["title"] == "Kettő"          # a legutóbbi elöl


def test_remove(lib):
    lib.upsert(r"a\egy", "Egy", is_dir=True)
    lib.remove(AP.konyv_kulcs("egy", True))
    assert lib.items == []


def test_mappa_savok_termeszetes_sorrend(tmp_path):
    for n in ("10.mp3", "2.mp3", "1.mp3", "olvass.txt"):
        (tmp_path / n).write_bytes(b"")
    savok = [pathlib.Path(p).name for p in AP.mappa_savok(str(tmp_path))]
    assert savok == ["1.mp3", "2.mp3", "10.mp3"]    # 2 a 10 előtt, txt kihagyva


def test_ido_str():
    assert AP.ido_str(0) == "0:00"
    assert AP.ido_str(75) == "1:15"
    assert AP.ido_str(3661) == "1:01:01"


def test_mappa_savok_rekurziv_kotetek(tmp_path):
    # „Sorozat" két kötet-almappával -> egy könyv, kötet-sorrendben
    (tmp_path / "1. kotet").mkdir()
    (tmp_path / "2. kotet").mkdir()
    (tmp_path / "1. kotet" / "01.mp3").write_bytes(b"")
    (tmp_path / "1. kotet" / "02.mp3").write_bytes(b"")
    (tmp_path / "2. kotet" / "01.mp3").write_bytes(b"")
    (tmp_path / "borito.jpg").write_bytes(b"")
    savok = AP.mappa_savok(str(tmp_path))
    relatek = [AP.rel_sav(str(tmp_path), p) for p in savok]
    assert relatek == ["1. kotet/01.mp3", "1. kotet/02.mp3", "2. kotet/01.mp3"]


def test_player_track_id_es_index_relativ(tmp_path):
    (tmp_path / "1. kotet").mkdir()
    (tmp_path / "2. kotet").mkdir()
    (tmp_path / "1. kotet" / "01.mp3").write_bytes(b"")
    (tmp_path / "2. kotet" / "01.mp3").write_bytes(b"")   # azonos fájlnév más kötetben
    p = AP.AudioBookPlayer()
    p.load(AP.mappa_savok(str(tmp_path)), book_root=str(tmp_path))
    # a két azonos nevű sáv relatív úton KÜLÖNBÖZIK, és külön feloldható
    assert p.track_index_of("2. kotet/01.mp3") == 1
    assert p.track_index_of("1. kotet/01.mp3") == 0
    p.idx = 1
    assert p.track_id() == "2. kotet/01.mp3"
