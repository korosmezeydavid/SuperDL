"""Super M – valós idejű EFFEKT-RACK a műsorszóró stúdióhoz (MK-A).

A zene-deckekre (és a mikrofonra) menet közben kapcsolható effektek: visszhang,
echo, torzítás, kórus, flanger, kompresszor, gargle. A DirectX-alapú DX8
effektek a BASS MAGJÁBAN vannak (`BASS_ChannelSetFX`), így nem kell hozzá külön
add-on: bármely élő csatornára rátehetők és levehetők, valós időben.

(A pitch/tempó-tartó sebesség és a visszafelé játszás a bass_fx.dll-t igényli –
az a rack későbbi bővítése; a DLL ezért már bundle-ölve van.)
"""

from ctypes import c_int, c_uint

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
        b._fx_decl = True
    return b


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
                return True
            return False
        if dx8_type in self._on:
            remove_effect(self.channel, self._on.pop(dx8_type))
        return True

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
