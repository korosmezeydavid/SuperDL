"""Optional native, formant-compensated pitch processor for mono PCM16 audio.

The Signalsmith-based DLL belongs to the Super Media module package.  It is
loaded only when selected; the ordinary BASS path remains usable without it.
"""

import ctypes as C
from pathlib import Path


class StretchUnavailable(RuntimeError):
    pass


def _load():
    path = Path(__file__).resolve().parent / "bin" / "voice_stretch_bridge.dll"
    if not path.is_file():
        raise StretchUnavailable("A természetes hangmagasság-motor nem található.")
    try:
        return _bind(C.CDLL(str(path)))  # exported C ABI uses cdecl
    except OSError as exc:
        raise StretchUnavailable("A természetes hangmagasság-motor nem tölthető be.") from exc


def _bind(dll):
    dll.voice_stretch_create.argtypes = [C.c_int] * 4
    dll.voice_stretch_create.restype = C.c_void_p
    dll.voice_stretch_destroy.argtypes = [C.c_void_p]
    dll.voice_stretch_destroy.restype = None
    dll.voice_stretch_latency.argtypes = [C.c_void_p]
    dll.voice_stretch_latency.restype = C.c_int
    dll.voice_stretch_set_pitch.argtypes = [C.c_void_p, C.c_float]
    dll.voice_stretch_set_pitch.restype = C.c_int
    dll.voice_stretch_set_vocoder.argtypes = [C.c_void_p, C.c_int,
                                             C.c_float, C.c_float]
    dll.voice_stretch_set_vocoder.restype = C.c_int
    dll.voice_stretch_process.argtypes = [C.c_void_p, C.c_void_p,
                                          C.c_void_p, C.c_int]
    dll.voice_stretch_process.restype = C.c_int
    return dll


def available():
    try:
        _load()
        return True
    except StretchUnavailable:
        return False


class StretchProcessor:
    def __init__(self, sample_rate=44100, window=1024, interval=256,
                 max_frames=4096):
        self._dll = _load()
        self._handle = self._dll.voice_stretch_create(
            sample_rate, window, interval, max_frames)
        if not self._handle:
            raise StretchUnavailable("A természetes hangmagasság-motor nem indítható.")
        self.max_frames = max_frames
        self._closed = False

    @property
    def latency_frames(self):
        return self._dll.voice_stretch_latency(self._handle)

    def set_pitch(self, semitones):
        if self._closed or not self._dll.voice_stretch_set_pitch(
                self._handle, float(semitones)):
            raise ValueError("A hangmagasság csak −12 és +12 félhang között állítható.")

    def set_vocoder(self, enabled, carrier_hz=120, mix=1.0):
        if self._closed or not self._dll.voice_stretch_set_vocoder(
                self._handle, int(bool(enabled)), float(carrier_hz), float(mix)):
            raise ValueError("Vocoder: 70–400 Hz-es vivő és 0–100% keverés adható meg.")

    def process(self, input_ptr, output_ptr, frames):
        if self._closed or not 0 <= frames <= self.max_frames:
            raise ValueError("Érvénytelen hangblokk.")
        if not self._dll.voice_stretch_process(
                self._handle, input_ptr, output_ptr, frames):
            raise StretchUnavailable("A hangblokk feldolgozása sikertelen.")

    def close(self):
        if not self._closed:
            self._dll.voice_stretch_destroy(self._handle)
            self._closed = True
            self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
