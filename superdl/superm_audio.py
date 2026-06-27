"""Super M (a SuperDL beépített rádió-/műsorszóró stúdiója) – hangmotor a
BASS könyvtárra (un4seen) építve.

Miért BASS, és miért KÜLÖN motor az audioengine.py mellett? A műsorszóráshoz
EGY könyvtárnak kell lefednie a teljes láncot: dekódolás (MP3/WAV/OGG/AAC),
TÖBB forrás keverése (BASSmix), tempó/BPM + crossfade (BASS_FX), KÉT kimeneti
eszköz (PFL/súgó csatorna a BASS_Init eszköz-indexével), mikrofon
(BASS_Record*), és Shoutcast/Icecast ENKÓDOLÁS (BASSenc + BASS_Encode_Cast).
A BASS ezt natívan tudja – ez a rádió-automatizálás ipari standardja. A
meglévő audioengine.py (sounddevice) a sima lejátszáshoz jó, de a keveréshez/
enkódoláshoz a BASS a megfelelő. (Licenc: ingyenes/freeware termékhez
díjmentes; kereskedelmihez un4seen licenc kell – a SuperDL ingyenes.)

EZ A MODUL EGYELŐRE csak az 1. mérföldkő A iterációjához: stabil
fájl-lejátszás (MP3/WAV) pozícióval, hangerővel, szünettel. A keverő, az
enkóder, a dual-device és a mikrofon a későbbi iterációkban épül erre.
"""

import ctypes as C
import sys
from ctypes import c_int, c_uint, c_ulonglong, c_float, c_void_p, c_wchar_p
from pathlib import Path

BASS_UNICODE = 0x80000000
BASS_ATTRIB_VOL = 2
BASS_ACTIVE_STOPPED = 0
BASS_ACTIVE_PLAYING = 1
BASS_ACTIVE_PAUSED = 3
BASS_POS_BYTE = 0
BASS_STREAM_DECODE = 0x200000          # decode-stream (a mixer húzza, nem a kimenet)
BASS_MIXER_CHAN_PAUSE = 0x20000        # egy mixer-forrás szüneteltetése (BASSmix)
BASS_MIXER_CHAN_BUFFER = 0x2000        # forrás-pufferelés (mikrofonhoz ajánlott)
_QWORD_ERR = 0xFFFFFFFFFFFFFFFF
_DWORD_ERR = 0xFFFFFFFF
# eszköz-státusz jelzők (BASS_DEVICEINFO.flags) – a dual-device/PFL-hez (1/C)
BASS_DEVICE_ENABLED = 1
BASS_DEVICE_DEFAULT = 2
BASS_DEVICE_INIT = 4


class BASS_DEVICEINFO(C.Structure):
    _fields_ = [("name", C.c_char_p), ("driver", C.c_char_p),
                ("flags", C.c_uint)]


class BassError(Exception):
    pass


def _dll_path() -> str:
    cands = []
    mp = getattr(sys, "_MEIPASS", None)
    if mp:
        cands.append(Path(mp) / "bass.dll")
    cands.append(Path(__file__).resolve().parent.parent / "bin" / "bass.dll")
    for c in cands:
        if c.is_file():
            return str(c)
    raise BassError("A bass.dll nem található (bin/bass.dll).")


_bass = None
_bassmix = None
_inited_devices = set()     # mely eszköz-indexek vannak már inicializálva


def _lib():
    global _bass
    if _bass is None:
        _bass = C.WinDLL(_dll_path())
        _decl(_bass)
    return _bass


def _sibling_dll(name: str) -> str:
    """A bass.dll melletti társ-DLL (bassmix/bassenc…) elérési útja."""
    return str(Path(_dll_path()).parent / name)


def _mix():
    """A bassmix.dll (műsor-keverő busz). A bass.dll-re épül, ezért azt előbb
    betöltjük."""
    global _bassmix
    if _bassmix is None:
        _lib()
        _bassmix = C.WinDLL(_sibling_dll("bassmix.dll"))
        m = _bassmix
        m.BASS_Mixer_StreamCreate.argtypes = [c_uint, c_uint, c_uint]
        m.BASS_Mixer_StreamCreate.restype = c_uint
        m.BASS_Mixer_StreamAddChannel.argtypes = [c_uint, c_uint, c_uint]
        m.BASS_Mixer_StreamAddChannel.restype = c_int
        m.BASS_Mixer_ChannelFlags.argtypes = [c_uint, c_uint, c_uint]
        m.BASS_Mixer_ChannelFlags.restype = c_uint
        m.BASS_Mixer_ChannelGetPosition.argtypes = [c_uint, c_uint]
        m.BASS_Mixer_ChannelGetPosition.restype = c_ulonglong
        m.BASS_Mixer_ChannelSetPosition.argtypes = [c_uint, c_ulonglong, c_uint]
        m.BASS_Mixer_ChannelSetPosition.restype = c_int
        m.BASS_Mixer_ChannelRemove.argtypes = [c_uint]
        m.BASS_Mixer_ChannelRemove.restype = c_int
    return _bassmix


RECORDPROC = C.CFUNCTYPE(c_int, c_uint, c_void_p, c_uint, c_void_p)


def _decl(b):
    b.BASS_Init.argtypes = [c_int, c_uint, c_uint, c_void_p, c_void_p]
    b.BASS_Init.restype = c_int
    b.BASS_Free.restype = c_int
    b.BASS_GetVersion.restype = c_uint
    b.BASS_ErrorGetCode.restype = c_int
    b.BASS_StreamCreateFile.argtypes = [c_int, c_wchar_p, c_ulonglong,
                                        c_ulonglong, c_uint]
    b.BASS_StreamCreateFile.restype = c_uint
    b.BASS_StreamFree.argtypes = [c_uint]
    b.BASS_ChannelPlay.argtypes = [c_uint, c_int]
    b.BASS_ChannelPause.argtypes = [c_uint]
    b.BASS_ChannelStop.argtypes = [c_uint]
    b.BASS_ChannelIsActive.argtypes = [c_uint]
    b.BASS_ChannelIsActive.restype = c_uint
    b.BASS_ChannelSetAttribute.argtypes = [c_uint, c_uint, c_float]
    b.BASS_ChannelSlideAttribute.argtypes = [c_uint, c_uint, c_float, c_uint]
    b.BASS_ChannelSlideAttribute.restype = c_int
    b.BASS_ChannelGetLength.argtypes = [c_uint, c_uint]
    b.BASS_ChannelGetLength.restype = c_ulonglong
    b.BASS_ChannelGetPosition.argtypes = [c_uint, c_uint]
    b.BASS_ChannelGetPosition.restype = c_ulonglong
    b.BASS_ChannelBytes2Seconds.argtypes = [c_uint, c_ulonglong]
    b.BASS_ChannelBytes2Seconds.restype = C.c_double   # a BASS double-t ad!
    b.BASS_ChannelSeconds2Bytes.argtypes = [c_uint, C.c_double]
    b.BASS_ChannelSeconds2Bytes.restype = c_ulonglong
    b.BASS_ChannelSetPosition.argtypes = [c_uint, c_ulonglong, c_uint]
    # dual-device / PFL (1/C)
    b.BASS_GetDeviceInfo.argtypes = [c_uint, C.POINTER(BASS_DEVICEINFO)]
    b.BASS_GetDeviceInfo.restype = c_int
    b.BASS_SetDevice.argtypes = [c_uint]
    b.BASS_SetDevice.restype = c_int
    b.BASS_ChannelSetDevice.argtypes = [c_uint, c_uint]
    b.BASS_ChannelSetDevice.restype = c_int
    # mikrofon / felvétel (3. mérföldkő)
    b.BASS_RecordGetDeviceInfo.argtypes = [c_uint, C.POINTER(BASS_DEVICEINFO)]
    b.BASS_RecordGetDeviceInfo.restype = c_int
    b.BASS_RecordInit.argtypes = [c_int]
    b.BASS_RecordInit.restype = c_int
    b.BASS_RecordSetDevice.argtypes = [c_uint]
    b.BASS_RecordSetDevice.restype = c_int
    b.BASS_RecordStart.argtypes = [c_uint, c_uint, c_uint, RECORDPROC, c_void_p]
    b.BASS_RecordStart.restype = c_uint


def available() -> bool:
    """Elérhető-e a BASS (megvan-e a bass.dll)?"""
    try:
        _lib()
        return True
    except Exception:
        return False


def init(device: int = -1, freq: int = 44100) -> bool:
    if device in _inited_devices:
        return True
    b = _lib()
    if not b.BASS_Init(device, freq, 0, 0, 0):
        if b.BASS_ErrorGetCode() != 14:        # 14 = már inicializálva
            raise BassError(f"BASS_Init hiba (kód {b.BASS_ErrorGetCode()})")
    _inited_devices.add(device)
    return True


def devices() -> list:
    """A használható KIMENETI eszközök listája: [(index, név), …]. A 0-s
    „nincs hang" eszközt kihagyjuk. Init nélkül is lekérdezhető (a PFL/súgó-
    csatorna eszközválasztójához)."""
    b = _lib()
    out = []
    info = BASS_DEVICEINFO()
    i = 1
    while b.BASS_GetDeviceInfo(i, C.byref(info)):
        if info.flags & BASS_DEVICE_ENABLED:
            name = (info.name.decode("utf-8", "replace")
                    if info.name else f"Eszköz {i}")
            out.append((i, name))
        i += 1
    return out


def default_device() -> int:
    """A rendszer alapértelmezett kimeneti eszközének INDEXE (a -1 helyett egy
    valódi index kell, hogy a stream-eket a megfelelő eszközre tudjuk
    létrehozni a több-eszközös PFL-nél)."""
    b = _lib()
    info = BASS_DEVICEINFO()
    i = 1
    first = None
    while b.BASS_GetDeviceInfo(i, C.byref(info)):
        if info.flags & BASS_DEVICE_ENABLED:
            if first is None:
                first = i
            if info.flags & BASS_DEVICE_DEFAULT:
                return i
        i += 1
    return first if first is not None else 1


def record_devices() -> list:
    """A bemeneti (mikrofon) eszközök listája: [(index, név), …]. A felvevő-
    eszközök indexe 0-tól indul (nincs „nincs hang" tétel)."""
    b = _lib()
    out = []
    info = BASS_DEVICEINFO()
    i = 0
    while b.BASS_RecordGetDeviceInfo(i, C.byref(info)):
        if info.flags & BASS_DEVICE_ENABLED:
            name = (info.name.decode("utf-8", "replace")
                    if info.name else f"Mikrofon {i}")
            out.append((i, name))
        i += 1
    return out


_rec_inited = set()


class Mic:
    """Mikrofon-bemenet a műsor-buszra keverve (3. mérföldkő). NINCS zajkapu –
    a műsorvezető KÉZZEL kapcsolja be/ki (reteszelő gomb). „Kikapcsolt"
    állapotban a mikrofon hangereje 0 (nem hallatszik, nem megy adásba); a
    bekapcsolás a hangerőt sima csúsztatással 1-re viszi (kattanásmentes)."""

    def __init__(self, mixer: "Mixer", device: int = -1, freq: int = 44100):
        self.mixer = mixer
        self.device = device           # -1 = alap felvevő eszköz
        self.freq = freq
        self._h = 0
        self._vol = 0.0                # induláskor néma (KI)

    def start(self) -> bool:
        """A mikrofon megnyitása és a buszra csatolása (némán). Egyszer kell
        meghívni; utána a be/ki a hangerővel történik."""
        if self._h:
            return True
        b = _lib()
        if self.device not in _rec_inited:
            if not b.BASS_RecordInit(self.device):
                if b.BASS_ErrorGetCode() != 14:    # 14 = már inicializálva
                    raise BassError(
                        f"Mikrofon nem indítható (BASS_RecordInit kód "
                        f"{b.BASS_ErrorGetCode()}). Van csatlakoztatott mikrofon?")
            _rec_inited.add(self.device)
        b.BASS_RecordSetDevice(self.device if self.device >= 0 else 0)
        # próbáljuk sztereóban, ha nem megy, monóban
        h = b.BASS_RecordStart(self.freq, 2, 0, RECORDPROC(0), None)
        if not h:
            h = b.BASS_RecordStart(self.freq, 1, 0, RECORDPROC(0), None)
        if not h:
            raise BassError(f"A felvétel nem indult (kód "
                            f"{b.BASS_ErrorGetCode()}).")
        self._h = h
        _mix().BASS_Mixer_StreamAddChannel(
            self.mixer.handle, self._h, BASS_MIXER_CHAN_BUFFER)
        self.set_volume(0.0)           # némán csatlakozik
        return True

    def set_volume(self, v: float):
        self._vol = max(0.0, min(1.0, v))
        if self._h:
            _lib().BASS_ChannelSetAttribute(self._h, BASS_ATTRIB_VOL,
                                            c_float(self._vol))

    def slide_volume(self, target: float, ms: int = 120):
        if self._h:
            self._vol = max(0.0, min(1.0, target))
            _lib().BASS_ChannelSlideAttribute(
                self._h, BASS_ATTRIB_VOL, c_float(self._vol), int(ms))

    @property
    def volume(self) -> float:
        return self._vol

    def active(self) -> bool:
        return bool(self._h)

    def stop(self):
        if self._h:
            b = _lib()
            b.BASS_ChannelStop(self._h)
            self._h = 0


def version() -> str:
    v = _lib().BASS_GetVersion()
    return f"{(v >> 24) & 0xff}.{(v >> 16) & 0xff}.{(v >> 8) & 0xff}.{v & 0xff}"


class Mixer:
    """A „műsor-busz" (air bus): ide keverünk MINDEN hangforrást (a zene-deckek,
    később a mikrofon és a jingle-k), és EZT az egy csatornát hallgatja a
    kimenet ÉS az enkóder (streaming, 2. mérföldkő). A források decode-streamek,
    amelyeket a mixer húz; a mixer maga folyamatosan szól a kimeneti eszközre
    (csend, ha épp nincs aktív forrás)."""

    def __init__(self, device: int = None, freq: int = 44100):
        self.device = default_device() if device is None else int(device)
        self.freq = freq
        init(self.device)
        b, m = _lib(), _mix()
        b.BASS_SetDevice(self.device)
        self._h = m.BASS_Mixer_StreamCreate(freq, 2, 0)
        if not self._h:
            raise BassError(f"BASS_Mixer_StreamCreate hiba "
                            f"(kód {b.BASS_ErrorGetCode()})")
        b.BASS_ChannelPlay(self._h, 0)        # a busz elindul (folyamatosan szól)

    @property
    def handle(self) -> int:
        return self._h

    def add(self, source_h: int, paused: bool = True):
        _mix().BASS_Mixer_StreamAddChannel(
            self._h, source_h, BASS_MIXER_CHAN_PAUSE if paused else 0)

    def free(self):
        if self._h:
            _lib().BASS_StreamFree(self._h)
            self._h = 0


class Player:
    """Egyetlen forrás lejátszása fájlból, pozícióval és hangerővel.

    KÉT mód:
    • `mixer` megadva → a forrás DECODE-stream, amit a műsor-busz (Mixer) húz;
      a lejátszás/szünet a mixer-forrás PAUSE jelzőjével történik (így a
      crossfade és a streaming egy közös buszon, keveredve megy). Ezt használja
      a két adás-deck.
    • `device` (mixer nélkül) → a forrás közvetlenül a megadott KIMENETI
      eszközre szól (None=alap). Ezt használja a PFL/súgó-csatorna (1/C), ami
      KÜLÖN eszközön, az adástól függetlenül szól."""

    def __init__(self, device: int = None, mixer: "Mixer" = None):
        self.mixer = mixer
        if mixer is not None:
            self.device = mixer.device
        else:
            self.device = default_device() if device is None else int(device)
            init(self.device)
        self._h = 0
        self._vol = 1.0

    def load(self, path: str) -> bool:
        self.unload()
        b = _lib()
        if self.mixer is not None:
            h = b.BASS_StreamCreateFile(0, str(path), 0, 0,
                                        BASS_UNICODE | BASS_STREAM_DECODE)
            self._h = h or 0
            if self._h:
                self.mixer.add(self._h, paused=True)   # szüneteltetve csatolva
                self.set_volume(self._vol)
        else:
            init(self.device)
            b.BASS_SetDevice(self.device)   # a stream EZEN az eszközön jöjjön létre
            h = b.BASS_StreamCreateFile(0, str(path), 0, 0, BASS_UNICODE)
            self._h = h or 0
            if self._h:
                self.set_volume(self._vol)
        return bool(self._h)

    @property
    def handle(self) -> int:
        """A lejátszott csatorna BASS-handle-je (0, ha nincs betöltve) – az
        effekt-rack (superm_fx) ehhez csatolja a valós idejű effekteket."""
        return self._h

    def unload(self):
        if self._h:
            _lib().BASS_StreamFree(self._h)     # a mixerből is kiveszi
            self._h = 0

    # --- belső: mixer-forrás szünet-állapota ---
    def _mix_paused(self) -> bool:
        fl = _mix().BASS_Mixer_ChannelFlags(self._h, 0, 0)   # 0 maszk = csak olvas
        return fl != _DWORD_ERR and bool(fl & BASS_MIXER_CHAN_PAUSE)

    def play(self, restart: bool = False) -> bool:
        if not self._h:
            return False
        if self.mixer is not None:
            if restart:
                self.seek(0)
            _mix().BASS_Mixer_ChannelFlags(self._h, 0, BASS_MIXER_CHAN_PAUSE)
            return True
        return bool(_lib().BASS_ChannelPlay(self._h, 1 if restart else 0))

    def pause(self):
        if not self._h:
            return
        if self.mixer is not None:
            _mix().BASS_Mixer_ChannelFlags(self._h, BASS_MIXER_CHAN_PAUSE,
                                           BASS_MIXER_CHAN_PAUSE)
        else:
            _lib().BASS_ChannelPause(self._h)

    def toggle_pause(self) -> bool:
        if not self._h:
            return False
        if self.is_playing():
            self.pause()
            return True
        self.play()
        return False

    def stop(self):
        if not self._h:
            return
        if self.mixer is not None:
            _mix().BASS_Mixer_ChannelFlags(self._h, BASS_MIXER_CHAN_PAUSE,
                                           BASS_MIXER_CHAN_PAUSE)
            self.seek(0)
        else:
            b = _lib()
            b.BASS_ChannelStop(self._h)
            b.BASS_ChannelSetPosition(self._h, 0, BASS_POS_BYTE)

    def is_playing(self) -> bool:
        if not self._h:
            return False
        if self.mixer is not None:
            ln = self.length()
            return (not self._mix_paused()) and ln > 0 \
                and self.position() < ln - 0.05
        return _lib().BASS_ChannelIsActive(self._h) == BASS_ACTIVE_PLAYING

    def is_paused(self) -> bool:
        if not self._h:
            return False
        if self.mixer is not None:
            return self._mix_paused() and self.position() < self.length()
        return _lib().BASS_ChannelIsActive(self._h) == BASS_ACTIVE_PAUSED

    def is_active(self) -> bool:
        if not self._h:
            return False
        if self.mixer is not None:
            ln = self.length()
            return ln > 0 and self.position() < ln - 0.05
        return _lib().BASS_ChannelIsActive(self._h) in (BASS_ACTIVE_PLAYING,
                                                        BASS_ACTIVE_PAUSED)

    def _heard_pos(self) -> float:
        """A ténylegesen HALLOTT pozíció (a mixer kimeneti puffere figyelembe
        véve). Csak a vég-detektáláshoz kell – hogy a puffer farkát (~0,5 mp) ne
        vágjuk le a következő számra lépéskor."""
        b = _lib()
        by = _mix().BASS_Mixer_ChannelGetPosition(self._h, BASS_POS_BYTE)
        if by == _QWORD_ERR:
            return 0.0
        return float(b.BASS_ChannelBytes2Seconds(self._h, by))

    def ended(self) -> bool:
        if not self._h:
            return False
        ln = self.length()
        if self.mixer is not None:
            return ln > 0 and not self._mix_paused() \
                and self._heard_pos() >= ln - 0.25
        return _lib().BASS_ChannelIsActive(self._h) == BASS_ACTIVE_STOPPED \
            and ln > 0 and self.position() >= ln - 0.25

    @property
    def volume(self) -> float:
        return self._vol

    def set_volume(self, v: float):
        self._vol = max(0.0, min(1.0, v))
        if self._h:
            _lib().BASS_ChannelSetAttribute(self._h, BASS_ATTRIB_VOL,
                                            c_float(self._vol))

    def slide_volume(self, target: float, ms: int):
        """A hangerő SIMA átcsúsztatása `target`-re `ms` alatt (a BASS
        időzítésével) – ez a crossfade alapja. A logikai _vol-t nem írja át.
        Decode-forrásnál a mixer renderelése közben fut le."""
        if self._h:
            _lib().BASS_ChannelSlideAttribute(
                self._h, BASS_ATTRIB_VOL,
                c_float(max(0.0, min(1.0, target))), int(ms))

    def length(self) -> float:
        if not self._h:
            return 0.0
        b = _lib()
        ln = b.BASS_ChannelGetLength(self._h, BASS_POS_BYTE)
        if ln == _QWORD_ERR:
            return 0.0
        return float(b.BASS_ChannelBytes2Seconds(self._h, ln))

    def position(self) -> float:
        # Mixer-módban a DEKÓDOLÁSI pozíciót adjuk (BASS_ChannelGetPosition):
        # azonnal követi a tekerést, szünetnél áll (a mixer nem húzza), és a
        # crossfade-időzítéshez is ez a jó (a hallott pozíció a puffer miatt
        # késne). A tényleges hallott pozíció a _heard_pos() (csak a véghez).
        if not self._h:
            return 0.0
        b = _lib()
        by = b.BASS_ChannelGetPosition(self._h, BASS_POS_BYTE)
        if by == _QWORD_ERR:
            return 0.0
        return float(b.BASS_ChannelBytes2Seconds(self._h, by))

    def seek(self, seconds: float):
        if not self._h:
            return
        b = _lib()
        by = b.BASS_ChannelSeconds2Bytes(self._h, max(0.0, seconds))
        if self.mixer is not None:
            _mix().BASS_Mixer_ChannelSetPosition(self._h, by, BASS_POS_BYTE)
        else:
            b.BASS_ChannelSetPosition(self._h, by, BASS_POS_BYTE)
