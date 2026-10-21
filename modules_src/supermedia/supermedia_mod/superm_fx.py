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
DX8_PARAMEQ = 7
DX8_REVERB = 8

# Saját EQ-karakterek: egyenként külön DX8 PARAMEQ-példányt használnak.
EQ_BASS = 1001
EQ_PRESENCE = 1002
EQ_NASAL = 1003
EQ_DARK = 1004
_EQ_CENTERS = {EQ_BASS: 180, EQ_PRESENCE: 2600, EQ_NASAL: 1100, EQ_DARK: 6500}

# (megjelenített név, DX8-típus) – a rack-UI ebből épül
EFFECTS = [
    ("Visszhang (reverb)", DX8_REVERB),
    ("Echo", DX8_ECHO),
    ("Torzítás", DX8_DISTORTION),
    ("Kórus", DX8_CHORUS),
    ("Flanger", DX8_FLANGER),
    ("Kompresszor", DX8_COMPRESSOR),
    ("Gargle (pörgő)", DX8_GARGLE),
    ("Mélykiemelés", EQ_BASS),
    ("Beszédérthetőség", EQ_PRESENCE),
    ("Orrhang", EQ_NASAL),
    ("Tompa hang", EQ_DARK),
]

# név -> (felolvasott címke, alsó, felső, alap, struktúramezők, szorzó)
PARAMETERS = {
    DX8_ECHO: {
        "delay": ("Ismétlések közti idő, ezredmásodperc", 20, 1200, 350,
                  ("fLeftDelay", "fRightDelay"), 1.0),
        "feedback": ("Ismétlések sűrűsége, százalék", 0, 85, 35,
                     ("fFeedback",), 1.0),
    },
    DX8_REVERB: {
        "decay": ("Térhang lecsengése, ezredmásodperc", 100, 3000, 1000,
                  ("fReverbTime",), 1.0),
    },
    DX8_CHORUS: {
        "depth": ("Kórus mélysége, százalék", 0, 100, 25, ("fDepth",), 1.0),
        "rate": ("Kórus hullámzása, tized hertz", 1, 50, 11,
                 ("fFrequency",), 0.1),
    },
    DX8_FLANGER: {
        "depth": ("Flanger mélysége, százalék", 0, 100, 50, ("fDepth",), 1.0),
        "rate": ("Flanger hullámzása, tized hertz", 1, 50, 3,
                 ("fFrequency",), 0.1),
        "feedback": ("Flanger visszacsatolása, százalék", -90, 90, -50,
                     ("fFeedback",), 1.0),
    },
    DX8_DISTORTION: {
        "edge": ("Torzítás élessége, százalék", 0, 100, 15,
                 ("fEdge",), 1.0),
        "color": ("Torzítás hangszíne, hertz", 100, 8000, 2400,
                  ("fPostEQCenterFrequency",), 1.0),
        "lowpass": ("Torzítás magasvágása, hertz", 100, 8000, 8000,
                    ("fPreLowpassCutoff",), 1.0),
    },
    DX8_COMPRESSOR: {
        "threshold": ("Kompresszor küszöbe, decibel", -60, 0, -20,
                      ("fThreshold",), 1.0),
        "ratio": ("Kompresszor aránya", 1, 20, 3,
                  ("fRatio",), 1.0),
        "attack": ("Kompresszor indulása, ezredmásodperc", 1, 200, 10,
                   ("fAttack",), 1.0),
        "release": ("Kompresszor lecsengése, ezredmásodperc", 50, 1000, 200,
                    ("fRelease",), 1.0),
    },
    **{kind: {
        "center": ("Hangszín középfrekvenciája, hertz", 80, 10000, center,
                   ("fCenter",), 1.0),
        "bandwidth": ("Hangszín sávszélessége, félhang", 1, 36, 12,
                      ("fBandwidth",), 1.0),
    } for kind, center in _EQ_CENTERS.items()},
}


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


class _DX8_PARAMEQ(Structure):
    _fields_ = [("fCenter", c_float), ("fBandwidth", c_float),
                ("fGain", c_float)]


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
    EQ_BASS: (_DX8_PARAMEQ, lambda s, a: _set_eq(s, 180, _lerp(0, 12, a))),
    EQ_PRESENCE: (_DX8_PARAMEQ, lambda s, a: _set_eq(s, 2600, _lerp(0, 12, a))),
    EQ_NASAL: (_DX8_PARAMEQ, lambda s, a: _set_eq(s, 1100, _lerp(0, 12, a))),
    EQ_DARK: (_DX8_PARAMEQ, lambda s, a: _set_eq(s, 6500, _lerp(0, -15, a))),
}


def _set_eq(params, center, gain):
    params.fCenter = center
    params.fBandwidth = 12
    params.fGain = gain


def set_effect_params(fx_handle: int, dx8_type: int, amount: float,
                      overrides: dict | None = None) -> bool:
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
        if not b.BASS_FXGetParameters(fx_handle, byref(st)):
            return False
        apply(st, amount)
        for key, value in (overrides or {}).items():
            definition = PARAMETERS.get(dx8_type, {}).get(key)
            if definition is None:
                continue
            _, minimum, maximum, _, fields, scale = definition
            converted = max(minimum, min(maximum, float(value))) * scale
            for field in fields:
                setattr(st, field, converted)
        return bool(b.BASS_FXSetParameters(fx_handle, byref(st)))
    except Exception:
        return False


def apply_effect(channel: int, dx8_type: int, priority: int = 0) -> int:
    """Effekt rátétele egy élő csatornára. Visszaad: FX-handle (0 = hiba)."""
    if not channel:
        return 0
    bass_type = DX8_PARAMEQ if dx8_type in _EQ_CENTERS else dx8_type
    return int(_bass().BASS_ChannelSetFX(channel, bass_type, priority))


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
        self._parameters: dict[int, dict[str, float]] = {}

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
                if amt is not None or dx8_type in _EQ_CENTERS or dx8_type in self._parameters:
                    set_effect_params(h, dx8_type, amt if amt is not None else 50,
                                      self._parameters.get(dx8_type))
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
        return set_effect_params(h, dx8_type, amount,
                                 self._parameters.get(dx8_type)) if h else True

    def set_parameter(self, dx8_type: int, key: str, value: float) -> bool:
        if key not in PARAMETERS.get(dx8_type, {}):
            return False
        self._parameters.setdefault(dx8_type, {})[key] = value
        handle = self._on.get(dx8_type)
        return set_effect_params(handle, dx8_type,
                                 self._intensity.get(dx8_type, 50),
                                 self._parameters[dx8_type]) if handle else True

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
