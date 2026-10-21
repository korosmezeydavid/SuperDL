"""Isolated native DSP probe; run with VOICE_STRETCH_PROBE_DLL set."""

import ctypes as C
import math
import os
from pathlib import Path

import pytest


def _native():
    path = os.environ.get("VOICE_STRETCH_PROBE_DLL")
    if not path:
        pytest.skip("The optional native probe is not built.")
    runtime = os.environ.get("VOICE_STRETCH_RUNTIME_DIR")
    if runtime and hasattr(os, "add_dll_directory"):
        os.add_dll_directory(runtime)
    dll = C.CDLL(str(Path(path).resolve()))
    dll.voice_stretch_create.argtypes = [C.c_int] * 4
    dll.voice_stretch_create.restype = C.c_void_p
    dll.voice_stretch_destroy.argtypes = [C.c_void_p]
    dll.voice_stretch_latency.argtypes = [C.c_void_p]
    dll.voice_stretch_latency.restype = C.c_int
    dll.voice_stretch_set_pitch.argtypes = [C.c_void_p, C.c_float]
    dll.voice_stretch_set_pitch.restype = C.c_int
    dll.voice_stretch_set_vocoder.argtypes = [C.c_void_p, C.c_int,
                                             C.c_float, C.c_float]
    dll.voice_stretch_set_vocoder.restype = C.c_int
    dll.voice_stretch_process.argtypes = [C.c_void_p, C.POINTER(C.c_int16),
                                          C.POINTER(C.c_int16), C.c_int]
    dll.voice_stretch_process.restype = C.c_int
    return dll


def _frequency(samples, rate):
    crossings = [i for i in range(1, len(samples))
                 if samples[i - 1] <= 0 < samples[i]]
    return (len(crossings) - 1) * rate / (crossings[-1] - crossings[0])


def test_formant_bridge_changes_pitch_without_changing_duration():
    dll = _native()
    state = dll.voice_stretch_create(44100, 1024, 256, 256)
    assert state
    try:
        assert dll.voice_stretch_latency(state) == 1024
        assert dll.voice_stretch_set_pitch(state, 4) == 1
        assert dll.voice_stretch_set_pitch(state, 20) == 0
        output = []
        for block in range(44100 * 3 // 256):
            source = (C.c_int16 * 256)(*(round(12000 * math.sin(
                2 * math.pi * 180 * (block * 256 + i) / 44100))
                for i in range(256)))
            target = (C.c_int16 * 256)()
            assert dll.voice_stretch_process(state, source, target, 256) == 1
            output.extend(target)
        tail = output[-22050:]
        assert max(abs(value) for value in tail) > 1000
        assert _frequency(tail, 44100) == pytest.approx(
            180 * 2 ** (4 / 12), rel=0.06)
    finally:
        dll.voice_stretch_destroy(state)


def test_vocoder_is_modulated_by_input_and_has_bounded_output():
    dll = _native()
    state = dll.voice_stretch_create(44100, 1024, 256, 256)
    assert state
    try:
        assert dll.voice_stretch_set_vocoder(state, 1, 120, 1) == 1
        assert dll.voice_stretch_set_vocoder(state, 1, 500, 1) == 0
        assert dll.voice_stretch_set_vocoder(state, 1, 120, -0.1) == 0
        output = []
        for block in range(44100 * 3 // 256):
            source = (C.c_int16 * 256)(*(
                round(16000 * math.sin(2 * math.pi * 180 * (block * 256 + i)
                                       / 44100))
                if 0.5 <= (block * 256 + i) / 44100 < 1.5 else 0
                for i in range(256)))
            target = (C.c_int16 * 256)()
            assert dll.voice_stretch_process(state, source, target, 256) == 1
            output.extend(target)
        def rms(part):
            return math.sqrt(sum(value * value for value in part) / len(part))
        assert rms(output[33075:55125]) > 100
        assert rms(output[110250:132300]) < 100
        assert max(abs(value) for value in output) <= 32767
    finally:
        dll.voice_stretch_destroy(state)
