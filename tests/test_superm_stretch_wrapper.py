"""The optional native pitch wrapper must not depend on BASS or wx at import."""

import ctypes as C
import importlib
import os
from pathlib import Path

import pytest


MODULE = "modules_src.supermedia.supermedia_mod.superm_stretch"


def test_missing_dll_is_explicit(monkeypatch):
    mod = importlib.import_module(MODULE)
    monkeypatch.setattr(mod, "_load", lambda: (_ for _ in ()).throw(
        mod.StretchUnavailable("missing")))
    with pytest.raises(mod.StretchUnavailable, match="missing"):
        mod.StretchProcessor()


def test_real_bridge_lifecycle(monkeypatch):
    dll_path = os.environ.get("VOICE_STRETCH_PROBE_DLL")
    if not dll_path or not Path(dll_path).is_file():
        pytest.skip("local bridge DLL is not built")
    runtime = os.environ.get("VOICE_STRETCH_RUNTIME_DIR")
    directory = os.add_dll_directory(runtime) if runtime else None
    try:
        mod = importlib.import_module(MODULE)
        monkeypatch.setattr(mod, "_load", lambda: mod._bind(C.CDLL(dll_path)))
        with mod.StretchProcessor(max_frames=256) as processor:
            assert processor.latency_frames == 1024
            processor.set_pitch(4)
            processor.set_vocoder(True, 125, 0.7)
            with pytest.raises(ValueError):
                processor.set_vocoder(True, 500, 1)
            block = (C.c_int16 * 256)(*([1000] * 256))
            output = (C.c_int16 * 256)()
            processor.process(block, output, 256)
            with pytest.raises(ValueError):
                processor.process(block, output, 257)
        assert processor._closed
    finally:
        if directory:
            directory.close()
