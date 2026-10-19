"""A Windowsos TDLib JSON C felületének betöltése és ellenőrzése.

Nem töltünk DLL-t a munkakönyvtárból: csak explicit beállított abszolút
útvonalról, a felhasználói SuperDL-adatkönyvtárból vagy a csomagolt motorból.
A helyi bejelentkezési adatok nem kerülnek a modulcsomagba.
"""

import ctypes
import os
from pathlib import Path


class TdlibUnavailable(RuntimeError):
    pass


def tdlib_path() -> Path:
    configured = os.environ.get("SUPERDL_TDJSON_DLL", "").strip()
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            raise TdlibUnavailable("A SUPERDL_TDJSON_DLL teljes elérési út legyen.")
        return candidate
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "SuperDL" / "Telegram" / "bin" / "tdjson.dll"
    if local.is_file():
        return local
    # A publikus modul csomagolható saját, ellenőrzött TDLib-futásidővel.
    # A már beállított helyi motor elsőbbséget élvez, így a meglévő fiók
    # adatbázisa és a teszttelepítés változatlan marad.
    bundled = Path(__file__).resolve().parent / "tdlib" / "tdjson.dll"
    return bundled if bundled.is_file() else local


def load_tdlib():
    path = tdlib_path()
    if not path.is_file():
        raise TdlibUnavailable(
            "A Telegram-motor hiányzik. A tdjson.dll-t és függőségeit a "
            "felhasználói SuperDL/Telegram/bin mappába kell telepíteni, "
            "vagy az ellenőrzött motorral csomagolt Supergram-változatot kell használni.")
    try:
        # A TDLib függő DLL-jeit kizárólag a vele együtt telepített,
        # felhasználói modulmappában keressük; a globális PATH-ot nem írjuk át.
        dll_directory = os.add_dll_directory(str(path.parent)) if os.name == "nt" else None
        lib = ctypes.CDLL(str(path))  # TDLib C ABI (Windows alatt is cdecl)
        lib._supergram_dll_directory = dll_directory
        lib.td_create_client_id.argtypes = []
        lib.td_create_client_id.restype = ctypes.c_int
        lib.td_send.argtypes = [ctypes.c_int, ctypes.c_char_p]
        lib.td_send.restype = None
        lib.td_receive.argtypes = [ctypes.c_double]
        lib.td_receive.restype = ctypes.c_char_p
        lib.td_execute.argtypes = [ctypes.c_char_p]
        lib.td_execute.restype = ctypes.c_char_p
        # A TDLib alapértelmezés szerint részletes belső naplót írhat.
        # Üzenet- és belépési adatok védelmében csak hibákat naplózzon.
        response = lib.td_execute(
            b'{"@type":"setLogVerbosityLevel","new_verbosity_level":1}')
        if response != b'{"@type":"ok"}':
            raise TdlibUnavailable("A Telegram-motor naplózása nem állítható biztonságos szintre.")
        return lib
    except (OSError, AttributeError, TdlibUnavailable) as exc:
        if "dll_directory" in locals() and dll_directory is not None:
            dll_directory.close()
        raise TdlibUnavailable(
            "A Telegram-motor nem tölthető be. Ellenőrizd a 64 bites TDLib-verziót és a függőségeit.") from exc
