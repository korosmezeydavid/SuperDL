"""Képernyőolvasó-kimenet: a bejelentéseket a FUTÓ képernyőolvasónak adja át,
hogy a felhasználó a SAJÁT, megszokott hangján – és a saját nyelvén – hallja.

Ezt kérte a levelezőlista: Áron a Tolkot javasolta, Farkas nem érti a retró
hangot (kikapcsolva meg az angol rendszerhangot kapta). A Tolknak nincs kész,
letölthető `Tolk.dll`-je, ezért KÖZVETLENÜL a képernyőolvasók vezérlőivel
beszélünk – pontosan azzal, amit a Tolk is használ a motorháztető alatt:
- NVDA: `nvdaControllerClient64.dll` (a program mellé csomagolva),
- JAWS: a `FreedomSci.JawsApi` COM-objektuma (ha elérhető a comtypes/pywin32).

Ha egyik SR sem fut (vagy a DLL nincs ott), a `speak()` False-t ad, és a hívó a
saját tartalékára (retró hang / selfvoice / SAPI) esik vissza. SOHA nem dob
kivételt.
"""
import ctypes
import os
import sys
import threading
from pathlib import Path

_lock = threading.Lock()
_nvda = None            # betöltött nvdaControllerClient, vagy False
_nvda_tried = False
_jaws = None            # JAWS COM-objektum, vagy False
_jaws_tried = False


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
        yield d / "nvdaControllerClient64.dll"


def _ensure_nvda():
    global _nvda, _nvda_tried
    if _nvda_tried:
        return _nvda
    with _lock:
        if _nvda_tried:
            return _nvda
        _nvda_tried = True
        if os.name != "nt":
            _nvda = False
            return _nvda
        dll = next((p for p in _dll_candidates() if p.is_file()), None)
        if not dll:
            _nvda = False
            return _nvda
        try:
            n = ctypes.WinDLL(str(dll))
            n.nvdaController_testIfRunning.restype = ctypes.c_ulong
            n.nvdaController_speakText.argtypes = [ctypes.c_wchar_p]
            n.nvdaController_speakText.restype = ctypes.c_ulong
            n.nvdaController_cancelSpeech.restype = ctypes.c_ulong
            _nvda = n
        except Exception:
            _nvda = False
    return _nvda


def _nvda_running(n) -> bool:
    try:
        return n.nvdaController_testIfRunning() == 0   # 0 = fut
    except Exception:
        return False


def _nvda_speak(text: str, interrupt: bool) -> bool:
    n = _ensure_nvda()
    if not n or not _nvda_running(n):
        return False
    try:
        if interrupt:
            try:
                n.nvdaController_cancelSpeech()
            except Exception:
                pass
        return n.nvdaController_speakText(str(text)) == 0
    except Exception:
        return False


def _ensure_jaws():
    global _jaws, _jaws_tried
    if _jaws_tried:
        return _jaws
    with _lock:
        if _jaws_tried:
            return _jaws
        _jaws_tried = True
        if os.name != "nt":
            _jaws = False
            return _jaws
        try:
            import comtypes.client
            _jaws = comtypes.client.CreateObject("FreedomSci.JawsApi")
        except Exception:
            try:
                import win32com.client
                _jaws = win32com.client.Dispatch("FreedomSci.JawsApi")
            except Exception:
                _jaws = False
    return _jaws


def _jaws_speak(text: str, interrupt: bool) -> bool:
    j = _ensure_jaws()
    if not j:
        return False
    try:
        return bool(j.SayString(str(text), bool(interrupt)))
    except Exception:
        return False


def available() -> bool:
    """Fut-e olyan képernyőolvasó, amit meg tudunk szólaltatni?"""
    n = _ensure_nvda()
    if n and _nvda_running(n):
        return True
    return bool(_ensure_jaws())


def screen_reader_name() -> str:
    n = _ensure_nvda()
    if n and _nvda_running(n):
        return "NVDA"
    if _ensure_jaws():
        return "JAWS"
    return ""


def speak(text: str, interrupt: bool = False) -> bool:
    """A szöveget a FUTÓ képernyőolvasónak adja át. True, ha sikerült (a hívó
    ilyenkor NE szólaltasson meg mást); False, ha nincs megszólaltatható SR."""
    if not (text or "").strip():
        return False
    if _nvda_speak(text, interrupt):
        return True
    if _jaws_speak(text, interrupt):
        return True
    return False
