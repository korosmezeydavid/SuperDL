"""Super Recorder – VALÓS IDEJŰ voice changer (élő mikrofon-átalakító).

Lánc (BASS): élő mikrofon → RECORDPROC → PUSH DECODE stream → BASS_FX TEMPÓ
(valós idejű, tempó-tartó HANGMAGASSÁG-váltás) → DX8-effektek (visszhang/echo/
torzítás/kórus/flanger/gargle) → kimenet (monitor a fejhallgatóban).

A pitch-hez a bass_fx.dll kell (a Core bin/-jéből; a build a 3.28.5-től bundle-öli);
a DX8-effektek a bass.dll magjában vannak. A superm_audio (BASS-betöltő, record-
primitívek) és a superm_fx (EffectRack) újrahasznosítva. Kecses hiba: ha bármi
nem indul (nincs mic/eszköz/DLL), érthető kivételt dob, nem omlik.
"""

import ctypes as C
from ctypes import c_int, c_uint, c_float, c_void_p

from . import superm_audio as A
from . import superm_fx as FX

BASS_STREAM_DECODE = 0x200000
BASS_FX_FREESOURCE = 0x10000
BASS_ATTRIB_TEMPO_PITCH = 0x10001          # félhang (-60..60)
# STREAMPROC_PUSH = (void*)-1 – a mutató-méretű csupa-1 érték
STREAMPROC_PUSH = (1 << (8 * C.sizeof(c_void_p))) - 1

_fx_lib = None
_decl_done = False


def _ensure() -> tuple:
    """Az extra BASS-függvények deklarálása + a bass_fx betöltése. (b, fx)-et ad."""
    global _fx_lib, _decl_done
    b = A._lib()
    if not _decl_done:
        b.BASS_StreamCreate.argtypes = [c_uint, c_uint, c_uint, c_void_p, c_void_p]
        b.BASS_StreamCreate.restype = c_uint
        b.BASS_StreamPutData.argtypes = [c_uint, c_void_p, c_uint]
        b.BASS_StreamPutData.restype = c_uint
        b.BASS_ChannelFree.argtypes = [c_uint]
        b.BASS_ChannelFree.restype = c_int
        _decl_done = True
    if _fx_lib is None:
        _fx_lib = C.WinDLL(A._sibling_dll("bass_fx.dll"))
        _fx_lib.BASS_FX_TempoCreate.argtypes = [c_uint, c_uint]
        _fx_lib.BASS_FX_TempoCreate.restype = c_uint
    return b, _fx_lib


def available() -> bool:
    """Megvan-e a BASS és a bass_fx (a valós idejű voice changerhez)?"""
    try:
        _ensure()
        return True
    except Exception:
        return False


def input_devices() -> list:
    return A.record_devices()


def output_devices() -> list:
    try:
        return A.devices()
    except Exception:
        return []


# a DX8-effektek (név, típus) a superm_fx-ből
EFFECTS = FX.EFFECTS


class VoiceChanger:
    def __init__(self, in_device: int = -1, out_device: int = -1,
                 freq: int = 44100):
        self.in_device = in_device
        self.out_device = out_device
        self.freq = freq
        self.channels = 1                  # monó mic – kisebb latencia
        self._push = 0
        self._tempo = 0
        self._rec = 0
        self._proc = None
        self.rack: FX.EffectRack | None = None
        self.pitch = 0.0
        self.running = False

    # ---- a mic-adat a push streambe ----------------------------------

    def _record_cb(self, handle, buffer, length, user):
        if self._push and length:
            try:
                A._lib().BASS_StreamPutData(self._push, buffer, length)
            except Exception:
                pass
        return 1

    def start(self):
        if self.running:
            return
        b, fx = _ensure()
        A.init(self.out_device, self.freq)             # kimeneti eszköz

        self._push = b.BASS_StreamCreate(self.freq, self.channels,
                                         BASS_STREAM_DECODE, STREAMPROC_PUSH, None)
        if not self._push:
            raise A.BassError("A push-stream nem jött létre (kód "
                              f"{b.BASS_ErrorGetCode()}).")
        self._tempo = fx.BASS_FX_TempoCreate(self._push, BASS_FX_FREESOURCE)
        if not self._tempo:
            raise A.BassError("A tempó/pitch-stream nem jött létre (bass_fx).")
        self._apply_pitch()
        self.rack = FX.EffectRack(self._tempo)

        if self.in_device not in A._rec_inited:
            if not b.BASS_RecordInit(self.in_device):
                if b.BASS_ErrorGetCode() != 14:
                    raise A.BassError("A mikrofon nem indítható (kód "
                                      f"{b.BASS_ErrorGetCode()}).")
            A._rec_inited.add(self.in_device)
        b.BASS_RecordSetDevice(self.in_device if self.in_device >= 0 else 0)
        self._proc = A.RECORDPROC(self._record_cb)
        self._rec = b.BASS_RecordStart(self.freq, self.channels, 0,
                                       self._proc, None)
        if not self._rec:
            raise A.BassError("A felvétel nem indult (kód "
                              f"{b.BASS_ErrorGetCode()}).")
        b.BASS_ChannelPlay(self._tempo, 0)             # monitor a kimenetre
        self.running = True

    def _apply_pitch(self):
        if self._tempo:
            A._lib().BASS_ChannelSetAttribute(
                self._tempo, BASS_ATTRIB_TEMPO_PITCH, c_float(self.pitch))

    def set_pitch(self, semitones: float):
        self.pitch = max(-12.0, min(12.0, float(semitones)))
        self._apply_pitch()

    def set_effect(self, dx8_type: int, on: bool) -> bool:
        return bool(self.rack and self.rack.set(dx8_type, on))

    def is_effect_on(self, dx8_type: int) -> bool:
        return bool(self.rack and self.rack.is_on(dx8_type))

    def stop(self):
        b = A._lib()
        try:
            if self._rec:
                b.BASS_ChannelStop(self._rec)
            if self.rack:
                self.rack.clear()
            if self._tempo:
                b.BASS_ChannelStop(self._tempo)
                b.BASS_ChannelFree(self._tempo)        # a push a FREESOURCE-szal megy
        except Exception:
            pass
        self._rec = self._tempo = self._push = 0
        self.rack = None
        self._proc = None
        self.running = False
