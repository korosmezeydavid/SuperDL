# -*- coding: utf-8 -*-
"""A nevesített könyvjelző-tár (superdl.bookmarks) tesztjei – ideiglenes fájlon."""
import importlib

import pytest

bm = pytest.importorskip("superdl.bookmarks")


@pytest.fixture
def store(tmp_path, monkeypatch):
    # a tárfájlt ideiglenes helyre irányítjuk, hogy ne írjunk a valós ~/.superdl-be
    monkeypatch.setattr(bm, "_FILE", tmp_path / "book_bookmarks.json")
    return bm.BookmarkStore()


def test_add_es_dedup(store):
    store.add("C:/Konyvek/regeny.epub", title="Regény", char=100,
              preview="eleje", created=111)
    store.add("C:/Konyvek/regeny.epub", title="Regény", char=100,
              preview="eleje", created=111)          # ugyanaz -> nincs duplikát
    assert len(store.all()) == 1
    store.add("C:/Konyvek/regeny.epub", char=200, preview="kesobb", created=222)
    assert len(store.for_book("regeny.epub")) == 2
    # a for_book fájlnév szerint megy, más útról is
    assert len(store.for_book("D:/masutt/REGENY.EPUB")) == 2


def test_perzisztencia(store, tmp_path, monkeypatch):
    store.add("regeny.epub", char=5, preview="x", created=1)
    store.save()
    ujra = bm.BookmarkStore()          # újratöltés ugyanarról a fájlról
    assert len(ujra.all()) == 1
    assert ujra.all()[0].created == 1


def test_merge_dedup_fajlnev_es_created(store):
    store.add("regeny.epub", char=1, preview="a", created=100)
    be = [
        {"book": "regeny.epub", "char": 999, "preview": "a", "created": 100},  # dup
        {"book": "masik.epub", "char": 2, "preview": "b", "created": 200},     # új
    ]
    uj = store.merge(be)
    assert uj == 1
    assert len(store.all()) == 2


def test_hang_mezok_perzisztencia(store):
    store.add("sorozat", title="Sorozat", kind="audio", track="s01e03.mp3",
              pos_ms=754000, preview="3. sáv • 12:34", created=42)
    store.save()
    ujra = bm.BookmarkStore()
    b = ujra.for_book("sorozat")[0]
    assert b.kind == "audio" and b.pos_ms == 754000
    assert b.track == "s01e03.mp3"
    # a régi rekord (hang-mezők nélkül) alapértékkel töltődik
    b2 = bm.Bookmark.from_record({"book": "regi.epub", "char": 10, "created": 1})
    assert b2.kind == "text" and b2.pos_ms == 0 and b2.track == ""


def test_remove(store):
    store.add("regeny.epub", char=1, preview="a", created=100)
    store.add("regeny.epub", char=2, preview="b", created=200)
    store.remove("regeny.epub", 100)
    marad = store.for_book("regeny.epub")
    assert len(marad) == 1 and marad[0].created == 200
