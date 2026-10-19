"""Supergram: hiányzó/hibás TDLib ne okozzon indítási összeomlást."""

import importlib.util
from pathlib import Path

import pytest


_PATH = Path(__file__).resolve().parents[1] / "modules_src" / "supergram" / "supergram_mod" / "tdlib_loader.py"
_SPEC = importlib.util.spec_from_file_location("supergram_tdlib_loader_test", _PATH)
loader = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(loader)


def test_relative_dll_path_is_rejected(monkeypatch):
    monkeypatch.setenv("SUPERDL_TDJSON_DLL", "tdjson.dll")
    with pytest.raises(loader.TdlibUnavailable, match="teljes elérési út"):
        loader.load_tdlib()


def test_missing_dll_reports_actionable_error(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERDL_TDJSON_DLL", str(tmp_path / "tdjson.dll"))
    with pytest.raises(loader.TdlibUnavailable, match="Telegram-motor hiányzik"):
        loader.load_tdlib()


def test_bundled_dll_is_used_when_user_runtime_is_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("SUPERDL_TDJSON_DLL", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    package = tmp_path / "supergram_mod"
    bundled = package / "tdlib" / "tdjson.dll"
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"placeholder")
    monkeypatch.setattr(loader, "__file__", str(package / "tdlib_loader.py"))
    assert loader.tdlib_path() == bundled


def test_user_runtime_takes_priority_over_bundled(monkeypatch, tmp_path):
    monkeypatch.delenv("SUPERDL_TDJSON_DLL", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    local = tmp_path / "local" / "SuperDL" / "Telegram" / "bin" / "tdjson.dll"
    local.parent.mkdir(parents=True)
    local.write_bytes(b"placeholder")
    package = tmp_path / "supergram_mod"
    bundled = package / "tdlib" / "tdjson.dll"
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"placeholder")
    monkeypatch.setattr(loader, "__file__", str(package / "tdlib_loader.py"))
    assert loader.tdlib_path() == local


def test_wrong_architecture_or_dependency_reports_error(monkeypatch, tmp_path):
    dll = tmp_path / "tdjson.dll"
    dll.write_bytes(b"not a dll")
    monkeypatch.setenv("SUPERDL_TDJSON_DLL", str(dll))
    monkeypatch.setattr(loader.ctypes, "CDLL", lambda path: (_ for _ in ()).throw(OSError("private path")))
    with pytest.raises(loader.TdlibUnavailable, match="64 bites") as error:
        loader.load_tdlib()
    assert "private path" not in str(error.value)
