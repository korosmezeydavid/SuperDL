"""Super M – valós idejű EFFEKT-RACK a műsorszóró stúdióhoz (MK-A).

A zene-deckekre (és a mikrofonra) menet közben kapcsolható effektek: visszhang,
echo, torzítás, kórus, flanger, kompresszor, gargle. A DirectX-alapú DX8
effektek a BASS MAGJÁBAN vannak (`BASS_ChannelSetFX`), így nem kell hozzá külön
add-on: bármely élő csatornára rátehetők és levehetők, valós időben.

(A pitch/tempó-tartó sebesség és a visszafelé játszás a bass_fx.dll-t igényli –
az a rack későbbi bővítése; a DLL ezért már bundle-ölve van.)
"""

from ctypes import Structure, byref, c_float, c_int, c_uint, c_void_p

from . import superm_audio as A

# BASS_FX_DX8_* effekt-típusok (a BASS magjában)
DX8_CHORUS = 0
DX8_COMPRESSOR = 1
DX8_DISTORTION = 2
DX8_ECHO = 3
DX8_FLANGER = 4
DX8_GARGLE = 5
DX8_REVERB = 8

# (megjelenített név, DX8-típus) – a rack-UI ebből épül
EFFECTS = [
    ("Visszhang (reverb)", DX8_REVERB),
    ("Echo", DX8_ECHO),
    ("Torzítás", DX8_DISTORTION),
    ("Kórus", DX8_CHORUS),
    ("Flanger", DX8_FLANGER),
    ("Kompresszor", DX8_COMPRESSOR),
    ("Gargle (pörgő)", DX8_GARGLE),
]


def _bass():
    b = A._lib()
    if not getattr(b, "_fx_decl", False):
        b.BASS_ChannelSetFX.argtypes = [c_uint, c_uint, c_int]
        b.BASS_ChannelSetFX.restype = c_uint
        b.BASS_ChannelRemoveFX.argtypes = [c_uint, c_uint]
        b.BASS_ChannelRemoveFX.restype = c_int
        b.BASS_FXSetParameters.argtypes = [c_uint, c_void_p]
        b.BASS_FXSetParameters.restype = c_int
        b.BASS_FXGetParameters.argtypes = [c_uint, c_void_p]
        b.BASS_FXGetParameters.restype = c_int
        b._fx_decl = True
    return b


# ---- a DX8 effektek paraméter-struktúrái (a BASS.H szerint) -----------

class _DX8_REVERB(Structure):
    _fields_ = [("fInGain", c_float), ("fReverbMix", c_float),
                ("fReverbTime", c_float), ("fHighFreqRTRatio", c_float)]


class _DX8_ECHO(Structure):
    _fields_ = [("fWetDryMix", c_float), ("fFeedback", c_float),
                ("fLeftDelay", c_float), ("fRightDelay", c_float),
                ("lPanDelay", c_int)]


class _DX8_DISTORTION(Structure):
    _fields_ = [("fGain", c_float), ("fEdge", c_float),
                ("fPostEQCenterFrequency", c_float),
                ("fPostEQBandwidth", c_float), ("fPreLowpassCutoff", c_float)]


class _DX8_CHORUS(Structure):          # a FLANGER azonos szerkezetű
    _fields_ = [("fWetDryMix", c_float), ("fDepth", c_float),
                ("fFeedback", c_float), ("fFrequency", c_float),
                ("lWaveform", c_uint), ("fDelay", c_float), ("lPhase", c_uint)]


class _DX8_COMPRESSOR(Structure):
    _fields_ = [("fGain", c_float), ("fAttack", c_float), ("fRelease", c_float),
                ("fThreshold", c_float), ("fRatio", c_float),
                ("fPredelay", c_float)]


class _DX8_GARGLE(Structure):
    _fields_ = [("dwRateHz", c_uint), ("dwWaveShape", c_uint)]


def _lerp(lo, hi, amount):
    return lo + (hi - lo) * max(0.0, min(100.0, amount)) / 100.0


# type -> (struct-osztály, fn(struct, amount0-100) az intenzitás fő mezőjéhez)
_PARAMS = {
    DX8_REVERB: (_DX8_REVERB,
                 lambda s, a: setattr(s, "fReverbMix", _lerp(-20.0, 0.0, a))),
    DX8_ECHO: (_DX8_ECHO,
               lambda s, a: (setattr(s, "fWetDryMix", _lerp(0.0, 100.0, a)),
                             setattr(s, "fFeedback", _lerp(0.0, 60.0, a)))),
    DX8_DISTORTION: (_DX8_DISTORTION,
                     lambda s, a: (setattr(s, "fGain", _lerp(-40.0, 0.0, a)),
                                   setattr(s, "fEdge", _lerp(0.0, 80.0, a)))),
    DX8_CHORUS: (_DX8_CHORUS,
                 lambda s, a: setattr(s, "fWetDryMix", _lerp(0.0, 100.0, a))),
    DX8_FLANGER: (_DX8_CHORUS,
                  lambda s, a: setattr(s, "fWetDryMix", _lerp(0.0, 100.0, a))),
    DX8_COMPRESSOR: (_DX8_COMPRESSOR,
                     lambda s, a: (setattr(s, "fRatio", _lerp(1.0, 20.0, a)),
                                   setattr(s, "fGain", _lerp(0.0, 20.0, a)))),
    DX8_GARGLE: (_DX8_GARGLE,
                 lambda s, a: setattr(s, "dwRateHz",
                                      max(1, int(_lerp(1, 100, a))))),
}


def set_effect_params(fx_handle: int, dx8_type: int, amount: float) -> bool:
    """Egy aktív DX8 effekt intenzitásának állítása 0–100%-ról. BIZTONSÁGOS:
    előbb LEKÉRJÜK a BASS alapértelmezett paramétereit (a teljes struct feltöltve),
    csak a fő mező(ke)t hangoljuk, majd visszaírjuk – így a struct mindig ép."""
    spec = _PARAMS.get(dx8_type)
    if not fx_handle or not spec:
        return False
    cls, apply = spec
    st = cls()
    b = _bass()
    try:
        b.BASS_FXGetParameters(fx_handle, byref(st))
        apply(st, amount)
        return bool(b.BASS_FXSetParameters(fx_handle, byref(st)))
    except Exception:
        return False


def apply_effect(channel: int, dx8_type: int, priority: int = 0) -> int:
    """Effekt rátétele egy élő csatornára. Visszaad: FX-handle (0 = hiba)."""
    if not channel:
        return 0
    return int(_bass().BASS_ChannelSetFX(channel, dx8_type, priority))


def remove_effect(channel: int, fx_handle: int) -> bool:
    """Egy korábban rátett effekt levétele."""
    if not channel or not fx_handle:
        return False
    return bool(_bass().BASS_ChannelRemoveFX(channel, fx_handle))


class EffectRack:
    """Egy csatorna effekt-állapotának kezelése: típusonként legfeljebb egy
    aktív effekt, ki/be kapcsolható. A deck-váltáskor `set_channel` átviszi az
    aktív effekteket az új csatornára (a régiek a régi handle-lel megszűnnek)."""

    def __init__(self, channel: int = 0):
        self.channel = int(channel or 0)
        self._on: dict[int, int] = {}      # dx8_type -> FX-handle
        self._intensity: dict[int, float] = {}   # dx8_type -> 0..100%

    def is_on(self, dx8_type: int) -> bool:
        return dx8_type in self._on

    def set(self, dx8_type: int, enabled: bool) -> bool:
        """Effekt be/ki. True, ha az állapot a kívánt lett."""
        if enabled:
            if dx8_type in self._on:
                return True
            h = apply_effect(self.channel, dx8_type)
            if h:
                self._on[dx8_type] = h
                amt = self._intensity.get(dx8_type)
                if amt is not None:            # a beállított intenzitás alkalmazása
                    set_effect_params(h, dx8_type, amt)
                return True
            return False
        if dx8_type in self._on:
            remove_effect(self.channel, self._on.pop(dx8_type))
        return True

    def set_intensity(self, dx8_type: int, amount: float) -> bool:
        """Az effekt intenzitása 0–100%. Megjegyezzük (a bekapcsoláskor és
        csatornaváltáskor is érvényesül), és ha épp aktív, azonnal alkalmazzuk."""
        self._intensity[dx8_type] = amount
        h = self._on.get(dx8_type)
        return set_effect_params(h, dx8_type, amount) if h else True

    def active_types(self) -> list[int]:
        return list(self._on)

    def clear(self):
        for t, h in list(self._on.items()):
            remove_effect(self.channel, h)
        self._on.clear()

    def set_channel(self, channel: int):
        """Új csatornára vált: a korábban bekapcsolt effekteket átviszi rá."""
        wanted = list(self._on)
        # a régi handle-ök a régi csatornával együtt megszűnnek
        self._on.clear()
        self.channel = int(channel or 0)
        for t in wanted:
            self.set(t, True)
