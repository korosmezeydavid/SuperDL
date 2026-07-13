"""docconvert: KÖTEGELT szöveg-kinyerés + több fájl EGY kimenetbe fűzése
(M3/M4 – felhasználói kérés, 2026-07-12)."""

import pytest

dc = pytest.importorskip("modules_src.docconvert.docconvert_mod.docconvert")


def _txt(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_extract_book_txt(tmp_path):
    src = _txt(tmp_path, "a.txt", "Árvíztűrő tükörfúrógép.")
    book = dc.extract_book(src)
    assert "Árvíztűrő" in book.text


def test_merge_ossze_txt(tmp_path):
    files = [_txt(tmp_path, "1.txt", "Első, árvíz."),
             _txt(tmp_path, "2.txt", "Második, őszi űr."),
             _txt(tmp_path, "3.txt", "Harmadik.")]
    dst = str(tmp_path / "out.txt")
    events = []
    ok, errs = dc.merge_documents(
        files, dst, "txt",
        on_file=lambda i, n, s, e: events.append((i, s)),
        progress=lambda a, b: None)
    assert ok == 3 and not errs
    merged = (tmp_path / "out.txt").read_text(encoding="utf-8")
    for frag in ("Első", "őszi űr", "Harmadik"):
        assert frag in merged
    assert merged.count("—") >= 3          # fájlonkénti fejlécek
    assert sum(1 for _i, s in events if s == "kész") == 3


def test_merge_hibas_elemet_kihagy(tmp_path):
    files = [_txt(tmp_path, "ok.txt", "jó"),
             str(tmp_path / "nincs.txt")]     # nem létező
    dst = str(tmp_path / "out.txt")
    ok, errs = dc.merge_documents(files, dst, "txt")
    assert ok == 1 and len(errs) == 1
    assert (tmp_path / "out.txt").exists()


def test_merge_mind_hibas_nem_ir_ki(tmp_path):
    files = [str(tmp_path / "x.txt"), str(tmp_path / "y.txt")]  # egyik sincs
    dst = str(tmp_path / "out.txt")
    with pytest.raises(RuntimeError):
        dc.merge_documents(files, dst, "txt")
    assert not (tmp_path / "out.txt").exists()   # nem hozott létre üres fájlt


def test_merge_sorrend_megmarad(tmp_path):
    files = [_txt(tmp_path, "a.txt", "ALMA"),
             _txt(tmp_path, "b.txt", "BÖRTÖN"),
             _txt(tmp_path, "c.txt", "CITROM")]
    dst = str(tmp_path / "out.txt")
    dc.merge_documents(files, dst, "txt")
    merged = (tmp_path / "out.txt").read_text(encoding="utf-8")
    assert merged.index("ALMA") < merged.index("BÖRTÖN") < merged.index("CITROM")
