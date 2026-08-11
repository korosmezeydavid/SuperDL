# -*- coding: utf-8 -*-
"""Távsegítség – a VEZÉRLÉS-motor: a segített gépen alkalmazza az irányítótól
kapott billentyű-/egér-eseményeket (Windows SendInput, ctypes-szal).

Az események hálózat-barát dict-ek (netroom-on átküldhetők), a felbontástól
függetlenek (az egér 0..1 normalizált koordinátát kap). A motor wx nélkül
működik, így külön is tesztelhető (a kurzor-mozgás GetCursorPos-szal
ellenőrizhető). SZIGORÚAN felügyelt használatra – a beleegyezést/pánikot a
felület kezeli, itt csak a technikai injektálás van.

Esemény-szótár (mind JSON-barát):
  {"t":"mozog","x":0.5,"y":0.3}          – egér ABSZOLÚT mozgás (képarány)
  {"t":"katt","gomb":"bal|jobb|kozep"}   – teljes kattintás (le+fel)
  {"t":"katt","gomb":"bal","le":true}    – csak lenyomás vagy felengedés
  {"t":"gorget","d":120}                 – görgetés (Windows-egység, ±120/notch)
  {"t":"bill","vk":65,"le":true}         – billentyű virtuális kóddal (le/fel)
  {"t":"char","ch":"á"}                  – egy karakter beírása (Unicode)
"""
import ctypes
from ctypes import wintypes

_user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None

# --- SendInput konstansok ---
_INPUT_MOUSE = 0
_INPUT_KEYBOARD = 1
_M_MOVE = 0x0001
_M_ABSOLUTE = 0x8000
_M_LEFTDOWN, _M_LEFTUP = 0x0002, 0x0004
_M_RIGHTDOWN, _M_RIGHTUP = 0x0008, 0x0010
_M_MIDDLEDOWN, _M_MIDDLEUP = 0x0020, 0x0040
_M_WHEEL = 0x0800
_K_KEYUP = 0x0002
_K_UNICODE = 0x0004

_GOMB = {
    "bal": (_M_LEFTDOWN, _M_LEFTUP),
    "jobb": (_M_RIGHTDOWN, _M_RIGHTUP),
    "kozep": (_M_MIDDLEDOWN, _M_MIDDLEUP),
}

ULONG_PTR = wintypes.WPARAM      # pointer-méretű (UINT_PTR)


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]


def _kepernyo():
    """A (fő) képernyő szélessége, magassága pixelben."""
    if not _user32:
        return (1920, 1080)
    return (_user32.GetSystemMetrics(0) or 1920,
            _user32.GetSystemMetrics(1) or 1080)


def _kuld_mouse(dwFlags, dx=0, dy=0, mouseData=0):
    inp = _INPUT(type=_INPUT_MOUSE)
    inp.u.mi = _MOUSEINPUT(dx, dy, mouseData, dwFlags, 0, 0)
    _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def _kuld_key(wVk=0, wScan=0, dwFlags=0):
    inp = _INPUT(type=_INPUT_KEYBOARD)
    inp.u.ki = _KEYBDINPUT(wVk, wScan, dwFlags, 0, 0)
    _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


class Vezerlo:
    """A segített gépen fut: alkalmazza a kapott eseményeket. `aktiv` False
    esetén MINDENT figyelmen kívül hagy (pánik/szünet – ezt a felület állítja)."""

    def __init__(self):
        self.aktiv = False
        self.elerheto = _user32 is not None

    def alkalmaz(self, esemeny):
        """Egy esemény végrehajtása. Csak akkor tesz bármit, ha `aktiv` és
        Windows-on fut. Visszaad: True, ha csinált valamit."""
        if not self.aktiv or not self.elerheto or not isinstance(esemeny, dict):
            return False
        t = esemeny.get("t")
        try:
            if t == "mozog":
                self._mozog(float(esemeny.get("x", 0)),
                            float(esemeny.get("y", 0)))
            elif t == "katt":
                self._katt(esemeny.get("gomb", "bal"), esemeny.get("le"))
            elif t == "gorget":
                _kuld_mouse(_M_WHEEL, mouseData=int(esemeny.get("d", 0)))
            elif t == "bill":
                flags = _K_KEYUP if not esemeny.get("le", True) else 0
                _kuld_key(wVk=int(esemeny.get("vk", 0)), dwFlags=flags)
            elif t == "char":
                self._char(str(esemeny.get("ch", "")))
            else:
                return False
            return True
        except Exception:
            return False

    def _mozog(self, x, y):
        # 0..1 → 0..65535 abszolút koordináta (a teljes fő képernyőn)
        ax = max(0, min(65535, int(x * 65535)))
        ay = max(0, min(65535, int(y * 65535)))
        _kuld_mouse(_M_MOVE | _M_ABSOLUTE, ax, ay)

    def _katt(self, gomb, le):
        le_flag, fel_flag = _GOMB.get(gomb, _GOMB["bal"])
        if le is True:
            _kuld_mouse(le_flag)
        elif le is False:
            _kuld_mouse(fel_flag)
        else:                       # teljes kattintás
            _kuld_mouse(le_flag)
            _kuld_mouse(fel_flag)

    def _char(self, ch):
        for c in ch:
            kod = ord(c)
            _kuld_key(wScan=kod, dwFlags=_K_UNICODE)
            _kuld_key(wScan=kod, dwFlags=_K_UNICODE | _K_KEYUP)


# --- kényelmi esemény-építők (az irányító oldalán) ---
def e_mozog(x, y):
    return {"t": "mozog", "x": round(float(x), 4), "y": round(float(y), 4)}


def e_katt(gomb="bal", le=None):
    d = {"t": "katt", "gomb": gomb}
    if le is not None:
        d["le"] = bool(le)
    return d


def e_gorget(delta):
    return {"t": "gorget", "d": int(delta)}


def e_bill(vk, le=True):
    return {"t": "bill", "vk": int(vk), "le": bool(le)}


def e_char(ch):
    return {"t": "char", "ch": str(ch)}
