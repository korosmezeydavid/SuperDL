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
from . import superm_stretch as STRETCH

BASS_STREAM_DECODE = 0x200000
BASS_FX_FREESOURCE = 0x10000
BASS_ATTRIB_TEMPO = 0x10000                # sebesség százalékban, hangmagasság nélkül
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

# A minták a meglévő pitch/tempo/DX8 motort kombinálják; nem állítanak
# természetes beszélőazonosságot és a mikrofon eredeti jelét nem módosítják.
PRESETS = {
    "Tiszta hang": (0, 0, {}),
    "Mély hang": (-5, -8, {FX.DX8_COMPRESSOR: 35}),
    "Rajzfilm": (6, 8, {FX.DX8_CHORUS: 25}),
    "Robot": (-2, 0, {FX.DX8_GARGLE: 45, FX.DX8_DISTORTION: 22}),
    "Űrhang": (3, -10, {FX.DX8_FLANGER: 45, FX.DX8_ECHO: 22}),
    "Nagyterem": (0, 0, {FX.DX8_REVERB: 65, FX.DX8_ECHO: 15}),
    "Telefonhang": (1, 0, {FX.EQ_DARK: 75, FX.EQ_NASAL: 45,
                            FX.DX8_COMPRESSOR: 35}),
    "Rádióbeszéd": (0, 0, {FX.EQ_PRESENCE: 55, FX.DX8_COMPRESSOR: 45}),
    "Barlang": (-2, -6, {FX.DX8_REVERB: 75, FX.DX8_ECHO: 38}),
    "Apró manó": (9, 12, {FX.DX8_CHORUS: 18, FX.EQ_PRESENCE: 35}),
    "Óriás": (-10, -12, {FX.EQ_BASS: 60, FX.DX8_REVERB: 25}),
    "Fémes robot": (-3, 0, {FX.DX8_GARGLE: 38, FX.DX8_FLANGER: 32,
                             FX.EQ_NASAL: 45}),
    "Sci-fi rádió": (-1, 0, {FX.DX8_DISTORTION: 22, FX.DX8_FLANGER: 27,
                              FX.EQ_PRESENCE: 52, FX.DX8_COMPRESSOR: 30}),
    "Víz alatti hang": (-3, -8, {FX.EQ_DARK: 80, FX.DX8_CHORUS: 20,
                                  FX.DX8_REVERB: 32}),
    "Digitális jel": (2, 0, {FX.DX8_GARGLE: 52, FX.DX8_DISTORTION: 28,
                              FX.DX8_ECHO: 12}),
    "Visszhangos alagút": (0, 0, {FX.DX8_ECHO: 50, FX.DX8_REVERB: 48}),
    "Űrrádió": (-4, -6, {FX.DX8_FLANGER: 58, FX.DX8_GARGLE: 20,
                           FX.EQ_NASAL: 30}),
    "Mély narrátor": (-2, -5, {FX.EQ_BASS: 35, FX.DX8_COMPRESSOR: 35,
                                 FX.EQ_PRESENCE: 18}),
}


class VoiceChanger:
    def __init__(self, in_device: int = -1, out_device: int = -1,
                 freq: int = 44100, natural_pitch: bool = False,
                 vocoder: bool = False):
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
        self.tempo = 0.0
        self.running = False
        self.natural_pitch = natural_pitch
        self.vocoder = vocoder
        self.vocoder_hz = 120.0
        self.vocoder_mix = 1.0
        self._stretch = None
        self._stretch_buffer = None
        self._stretch_failed = False

    # ---- a mic-adat a push streambe ----------------------------------

    def _record_cb(self, handle, buffer, length, user):
        if self._push and length:
            try:
                b = A._lib()
                if self._stretch and not self._stretch_failed and length % 2 == 0:
                    frame_count = length // 2  # mono PCM16
                    offset = 0
                    while offset < frame_count:
                        frames = min(frame_count - offset, self._stretch.max_frames)
                        self._stretch.process(buffer + offset * 2,
                                              self._stretch_buffer, frames)
                        b.BASS_StreamPutData(self._push, self._stretch_buffer,
                                             frames * 2)
                        offset += frames
                else:
                    b.BASS_StreamPutData(self._push, buffer, length)
            except Exception:
                # Keep the monitoring path audible if the optional processor
                # fails. Do not repeat a faulty native call on later buffers.
                self._stretch_failed = True
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
        if self.natural_pitch or self.vocoder:
            self._stretch = STRETCH.StretchProcessor(sample_rate=self.freq)
            self._stretch_buffer = C.create_string_buffer(
                self._stretch.max_frames * 2)
            self._stretch.set_pitch(self.pitch)
            self._stretch.set_vocoder(self.vocoder, self.vocoder_hz,
                                      self.vocoder_mix)

        self._push = b.BASS_StreamCreate(self.freq, self.channels,
                                         BASS_STREAM_DECODE, STREAMPROC_PUSH, None)
        if not self._push:
            raise A.BassError("A push-stream nem jött létre (kód "
                              f"{b.BASS_ErrorGetCode()}).")
        self._tempo = fx.BASS_FX_TempoCreate(self._push, BASS_FX_FREESOURCE)
        if not self._tempo:
            raise A.BassError("A tempó/pitch-stream nem jött létre (bass_fx).")
        self._apply_pitch()
        self._apply_tempo()
        self.rack = FX.EffectRack(self._tempo)

        if self.in_device not in A._rec_inited:
            if not b.BASS_RecordInit(self.in_device):
                if b.BASS_ErrorGetCode() != 14:
                    raise A.BassError("A mikrofon nem indítható (kód "
                                      f"{b.BASS_ErrorGetCode()}).")
            A._rec_inited.add(self.in_device)
        # -1 = az IGAZI alapértelmezett mikrofon (nem a 0-s index) [VC-P0-02]
        A.select_record_device(b, self.in_device)
        self._proc = A.RECORDPROC(self._record_cb)
        self._rec = b.BASS_RecordStart(self.freq, self.channels, 0,
                                       self._proc, None)
        if not self._rec:
            raise A.BassError("A felvétel nem indult (kód "
                              f"{b.BASS_ErrorGetCode()}).")
        b.BASS_ChannelPlay(self._tempo, 0)             # monitor a kimenetre
        self.running = True

    def _apply_pitch(self):
        if self._stretch:
            self._stretch.set_pitch(self.pitch)
        if self._tempo:
            A._lib().BASS_ChannelSetAttribute(
                self._tempo, BASS_ATTRIB_TEMPO_PITCH,
                c_float(0 if self._stretch else self.pitch))

    def set_pitch(self, semitones: float):
        self.pitch = max(-12.0, min(12.0, float(semitones)))
        self._apply_pitch()

    def _apply_tempo(self):
        if self._tempo:
            A._lib().BASS_ChannelSetAttribute(
                self._tempo, BASS_ATTRIB_TEMPO, c_float(self.tempo))

    def set_tempo(self, percent: float):
        """Élő beszédritmus: −30..+30%, a pitch-től függetlenül."""
        self.tempo = max(-30.0, min(30.0, float(percent)))
        self._apply_tempo()

    def set_vocoder(self, carrier_hz: float, mix: float):
        self.vocoder_hz = max(70.0, min(400.0, float(carrier_hz)))
        self.vocoder_mix = max(0.0, min(1.0, float(mix)))
        if self._stretch:
            self._stretch.set_vocoder(self.vocoder, self.vocoder_hz,
                                      self.vocoder_mix)

    def set_effect(self, dx8_type: int, on: bool) -> bool:
        return bool(self.rack and self.rack.set(dx8_type, on))

    def set_effect_intensity(self, dx8_type: int, amount: float) -> bool:
        """A DX8 effekt erőssége 0–100%-ban (akkor is megjegyzi, ha az effekt
        épp nincs bekapcsolva – bekapcsoláskor érvényesül)."""
        return bool(self.rack and self.rack.set_intensity(dx8_type, amount))

    def set_effect_parameter(self, dx8_type: int, key: str, value: float) -> bool:
        """Részletes hangolás egy aktív vagy később bekapcsolt effektben."""
        return bool(self.rack and self.rack.set_parameter(dx8_type, key, value))

    def is_effect_on(self, dx8_type: int) -> bool:
        return bool(self.rack and self.rack.is_on(dx8_type))

    def stop(self):
        try:
            b = A._lib()
            if self._rec:
                b.BASS_ChannelStop(self._rec)
            if self.rack:
                self.rack.clear()
            if self._tempo:
                b.BASS_ChannelStop(self._tempo)
                b.BASS_ChannelFree(self._tempo)        # a push a FREESOURCE-szal megy
        except Exception:
            pass
        if self._stretch:
            self._stretch.close()
            self._stretch = None
            self._stretch_buffer = None
        self._rec = self._tempo = self._push = 0
        self.rack = None
        self._proc = None
        self.running = False
