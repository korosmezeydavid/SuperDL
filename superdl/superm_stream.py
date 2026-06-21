"""Super M – streaming / enkóder (2. mérföldkő, A iteráció).

A műsor-buszt (superm_audio.Mixer) MP3-ba enkódoljuk és KISUGÁROZZUK egy
internetes rádió-szerverre: Icecast (v2) vagy Shoutcast (v1/v2). A BASS
enkóder-bővítményeire épül:

    bass.dll  ← alap (már be van töltve a superm_audio-ban)
    bassenc.dll      – enkóder-keret + BASS_Encode_Cast* (a szerver-handshake)
    bassenc_mp3.dll  – beépített MP3-enkóder (LAME-kompatibilis kapcsolók)

A lánc: a mixer handle-jére indítunk egy MP3-enkódert (BASS_Encode_MP3_Start),
majd a BASS_Encode_CastInit felépíti a kapcsolatot a szerverrel és onnantól az
enkódolt MP3 folyam a szerverre megy. A „most szól" metaadatot a
BASS_Encode_CastSetTitle küldi.
"""

import ctypes as C
from ctypes import c_uint, c_int, c_char_p, c_void_p

from . import superm_audio as A

# enkóder-jelzők
BASS_ENCODE_QUEUE = 0x200          # async, pufferelt enkódolás (hálózathoz jó)
BASS_ENCODE_CAST_PUBLIC = 1        # listázás a szerver nyilvános könyvtárában

# MIME tartalomtípusok
CONTENT_MP3 = b"audio/mpeg"

# ENCODEPROC: void CALLBACK(HENCODE, DWORD chan, void *buf, DWORD len, void *usr)
ENCODEPROC = C.CFUNCTYPE(None, c_uint, c_uint, c_void_p, c_uint, c_void_p)

_BASS_ERRORS = {
    2: "nem sikerült megnyitni a kapcsolatot (rossz cím/port?)",
    7: "már fut egy enkóder ezen a buszon",
    40: "időtúllépés – a szerver nem válaszolt",
    41: "a szerver elutasította (rossz jelszó vagy mountpoint?)",
    42: "a szerver nem elérhető",
}


def _err(b) -> str:
    code = b.BASS_ErrorGetCode()
    return _BASS_ERRORS.get(code, f"BASS hibakód {code}")


class Caster:
    """A műsor-busz kisugárzása egy Icecast/Shoutcast szerverre."""

    def __init__(self):
        self._enc = None        # bassenc.dll
        self._mp3 = None        # bassenc_mp3.dll
        self._henc = 0          # az aktív enkóder-handle
        self.is_live = False
        self.last_error = ""

    # ---- DLL-ek betöltése + deklarációk ----
    def _libs(self):
        if self._enc is not None:
            return
        A._lib()                       # a bass.dll legyen betöltve (függőség)
        self._enc = C.WinDLL(A._sibling_dll("bassenc.dll"))
        self._mp3 = C.WinDLL(A._sibling_dll("bassenc_mp3.dll"))
        e, m = self._enc, self._mp3
        m.BASS_Encode_MP3_Start.argtypes = [c_uint, c_char_p, c_uint,
                                            ENCODEPROC, c_void_p]
        m.BASS_Encode_MP3_Start.restype = c_uint
        e.BASS_Encode_Stop.argtypes = [c_uint]
        e.BASS_Encode_Stop.restype = c_int
        e.BASS_Encode_CastInit.argtypes = [c_uint, c_char_p, c_char_p, c_char_p,
                                           c_char_p, c_char_p, c_char_p,
                                           c_char_p, c_char_p, c_uint, c_uint]
        e.BASS_Encode_CastInit.restype = c_int
        e.BASS_Encode_CastSetTitle.argtypes = [c_uint, c_char_p, c_char_p]
        e.BASS_Encode_CastSetTitle.restype = c_int

    @staticmethod
    def available() -> bool:
        try:
            A._lib()
            C.WinDLL(A._sibling_dll("bassenc.dll"))
            C.WinDLL(A._sibling_dll("bassenc_mp3.dll"))
            return True
        except Exception:
            return False

    def _server_string(self, host, port, mount, shoutcast) -> str:
        host = host.strip()
        if shoutcast:
            # Shoutcast v1: host:port (nincs mount). v2: host:port,sid – ha a
            # mount számot tartalmaz, sid-ként vesszővel fűzzük.
            sid = mount.strip().lstrip("/")
            return f"{host}:{port},{sid}" if sid.isdigit() and sid else \
                   f"{host}:{port}"
        # Icecast: host:port/mountpoint
        mp = mount.strip()
        if not mp:
            mp = "/stream"
        if not mp.startswith("/"):
            mp = "/" + mp
        return f"{host}:{port}{mp}"

    def start(self, mixer_handle, host, port, mount="", password="",
              bitrate=128, name="", url="", genre="", desc="",
              public=False, shoutcast=False) -> bool:
        """Élő adás indítása. True = sikeres kapcsolódás. Hiba esetén False és
        a self.last_error tartalmazza a magyar üzenetet."""
        self.last_error = ""
        try:
            self._libs()
        except Exception as ex:
            self.last_error = f"Az enkóder-bővítmények nem tölthetők be: {ex}"
            return False
        if self.is_live:
            self.stop()

        b = A._lib()
        # 1) MP3-enkóder a buszra (CBR, a megadott bitrátán), pufferelt
        opts = f"-b {int(bitrate)}".encode("ascii")
        henc = self._mp3.BASS_Encode_MP3_Start(
            int(mixer_handle), opts, BASS_ENCODE_QUEUE, ENCODEPROC(0), None)
        if not henc:
            self.last_error = f"Az MP3-enkóder nem indult ({_err(b)})."
            return False

        # 2) kapcsolódás a szerverhez (handshake) + adás indítása
        server = self._server_string(host, port, mount, shoutcast)
        flags = BASS_ENCODE_CAST_PUBLIC if public else 0
        ok = self._enc.BASS_Encode_CastInit(
            henc,
            server.encode("utf-8"),
            (password or "").encode("utf-8"),
            CONTENT_MP3,
            name.encode("utf-8"),
            url.encode("utf-8"),
            genre.encode("utf-8"),
            desc.encode("utf-8"),
            None,
            int(bitrate),
            flags)
        if not ok:
            self.last_error = (f"A szerverre nem sikerült kapcsolódni "
                               f"({_err(b)}). Szerver: {server}")
            self._enc.BASS_Encode_Stop(henc)
            return False

        self._henc = henc
        self.is_live = True
        return True

    def set_title(self, title: str):
        """A „most szól" metaadat elküldése a hallgatóknak."""
        if self.is_live and self._henc:
            self._enc.BASS_Encode_CastSetTitle(
                self._henc, (title or "").encode("utf-8"), None)

    def stop(self):
        if self._henc:
            try:
                self._enc.BASS_Encode_Stop(self._henc)
            except Exception:
                pass
            self._henc = 0
        self.is_live = False
