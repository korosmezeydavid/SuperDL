"""store: atomikus (fsync-es) mentés, .bak-lánc, sérült fájl helyreállítása,
titkosított kulcstárolás (DPAPI, ha elérhető)."""

import json

import pytest

store = pytest.importorskip("superdl.store")


def test_save_load_kor(tmp_path):
    p = tmp_path / "q.json"
    store.save_json(p, [{"a": 1}])
    store.save_json(p, [{"a": 2}])
    assert store.load_json(p, []) == [{"a": 2}]
    # a .bak az ELŐZŐ jó állapotot őrzi
    bak = p.with_suffix(p.suffix + ".bak")
    assert bak.exists()
    assert json.loads(bak.read_text(encoding="utf-8")) == [{"a": 1}]


def test_hianyzo_fajl_alapertek(tmp_path):
    assert store.load_json(tmp_path / "nincs.json", {"x": 1}) == {"x": 1}


def test_serult_fajl_bak_bol_all_helyre(tmp_path):
    p = tmp_path / "q.json"
    store.save_json(p, ["jó adat"])
    store.save_json(p, ["még jobb"])          # a .bak: ["jó adat"]
    p.write_text("{ez nem json", encoding="utf-8")
    assert store.load_json(p, []) == ["jó adat"]


def test_serult_fajl_bak_nelkul_felreteszi(tmp_path):
    p = tmp_path / "q.json"
    p.write_text("{sérült", encoding="utf-8")
    assert store.load_json(p, ["alap"]) == ["alap"]
    # a sérültet .corrupt-* néven félretette, nem hagyta a helyén
    assert not p.exists()
    assert any(f.name.startswith("q.json.corrupt-")
               for f in tmp_path.iterdir())


def test_titkos_mentes_dpapi(tmp_path):
    try:
        import win32crypt  # noqa: F401
    except ImportError:
        pytest.skip("pywin32/DPAPI nem elérhető")
    p = tmp_path / "ai.json"
    store.save_secret_json(p, {"k": "szigoruan-titkos-123456"})
    raw = p.read_text(encoding="utf-8")
    assert "__dpapi__" in raw
    assert "szigoruan-titkos" not in raw      # SOHA nem nyílt szöveg
    # titoknál .bak sem maradhat
    assert not p.with_suffix(p.suffix + ".bak").exists()
