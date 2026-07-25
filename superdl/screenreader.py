"""Képernyőolvasó-kimenet a Tolk könyvtárral.

A bejelentéseket a FUTÓ képernyőolvasónak (NVDA/JAWS/…) adja át, hogy a
felhasználó a SAJÁT, megszokott hangján – és a saját nyelvén – hallja őket.
Ezt kérte a levelezőlista (Áron a Tolkot javasolta; Farkas nem érti a retró
hangot, kikapcsolva meg az angol rendszerhangot kapta).

Ha nincs Tolk-DLL vagy épp NEM fut képernyőolvasó, a `speak()` False-t ad, és a
hívó a saját tartalékára esik vissza (retró hang / selfvoice / SAPI). A Tolk
BELSŐ SAPI-tartalékát KIKAPCSOLJUK: a SAPI-t mi kezeljük, itt kizárólag valódi
képernyőolvasót akarunk megszólaltatni.

A Tolk.dll (és a mellé csomagolt kliens-DLL-ek: nvdaControllerClient64.dll,
SAAPI64.dll, …) a program mellé kerülnek; a betöltés ctypes-szal, lustán történik.
"""
import ctypes
import os
import sys
import threading
from pathlib import Path

_lock = threading.Lock()
_tolk = None            # a betöltött Tolk.dll, vagy False ha nincs
_tried = False


def _dll_candidates():
    dirs = []
    if getattr(sys, "frozen", False):
        exedir = Path(sys.executable).resolve().parent
        dirs += [exedir, exedir / "_internal", exedir / "tolk"]
    here = Path(__file__).resolve().parent
    dirs += [here / "tolk", here]
    seen = set()
    for d in dirs:
        if d in seen:
            continue
        seen.add(d)
        yield d / "Tolk.dll"


def _ensure():
    global _tolk, _tried
    if _tried:
        return _tolk
    with _lock:
        if _tried:
            return _tolk
        _tried = True
        if os.name != "nt":
            _tolk = False
            return _tolk
        dll = next((p for p in _dll_candidates() if p.is_file()), None)
        if not dll:
            _tolk = False
            return _tolk
        try:
            os.add_dll_directory(str(dll.parent))   # a kliens-DLL-ek mellette
        except Exception:
            pass
        try:
            t = ctypes.WinDLL(str(dll))
            t.Tolk_Output.restype = ctypes.c_bool
            t.Tolk_Output.argtypes = [ctypes.c_wchar_p, ctypes.c_bool]
            t.Tolk_DetectScreenReader.restype = ctypes.c_wchar_p
            t.Tolk_HasSpeech.restype = ctypes.c_bool
            t.Tolk_TrySAPI.argtypes = [ctypes.c_bool]
            t.Tolk_Load()
            t.Tolk_TrySAPI(False)      # NE a Tolk SAPI-ja – azt mi kezeljük
            _tolk = t
        except Exception:
            _tolk = False
    return _tolk


def available() -> bool:
    """Betöltődött a Tolk ÉS fut is épp egy megszólaltatható képernyőolvasó?"""
    t = _ensure()
    if not t:
        return False
    try:
        return bool(t.Tolk_DetectScreenReader()) and bool(t.Tolk_HasSpeech())
    except Exception:
        return False


def screen_reader_name() -> str:
    """A futó képernyőolvasó neve (pl. „NVDA"), vagy üres sztring."""
    t = _ensure()
    if not t:
        return ""
    try:
        return t.Tolk_DetectScreenReader() or ""
    except Exception:
        return ""


def speak(text: str, interrupt: bool = False) -> bool:
    """A szöveget a FUTÓ képernyőolvasónak adja át. True, ha sikerült (ilyenkor
    a hívó NE szólaltasson meg mást); False, ha nincs Tolk vagy képernyőolvasó."""
    if not (text or "").strip():
        return False
    t = _ensure()
    if not t:
        return False
    try:
        if not t.Tolk_DetectScreenReader():
            return False
        return bool(t.Tolk_Output(str(text), bool(interrupt)))
    except Exception:
        return False
