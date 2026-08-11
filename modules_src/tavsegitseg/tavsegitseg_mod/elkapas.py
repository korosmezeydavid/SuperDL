# -*- coding: utf-8 -*-
"""Távsegítség – az IRÁNYÍTÓ-oldali billentyű-elkapás: a segítő wx-billentyű-
eseményeit Windows virtuális billentyűkódú (VK) eseményekké fordítja.

Szándékosan VK down/up-ot küldünk (nem karaktert), hogy a MODIFIKÁTOROK
(Ctrl/Alt/Shift), a gyorsbillentyűk (Ctrl+C…) és a KÉPERNYŐOLVASÓ-PARANCSOK
(Insert+nyilak stb.) is hűen átmenjenek a másik gépre. A tiszta wx→VK leképezés
wx nélkül nem fut, de a `wx_vk` táblázata a UI-tól függetlenül tesztelhető."""
import wx

from . import vezerles as VZ

# --- Windows virtuális billentyűkódok a gyakori speciális billentyűkhöz ---
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12        # Alt
VK_CAPITAL = 0x14     # CapsLock
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_PRIOR = 0x21      # PageUp
VK_NEXT = 0x22       # PageDown
VK_END = 0x23
VK_HOME = 0x24
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_INSERT = 0x2D
VK_DELETE = 0x2E
VK_LWIN = 0x5B

_WXK = {}


def _init_map():
    if _WXK:
        return
    _WXK.update({
        wx.WXK_BACK: VK_BACK, wx.WXK_TAB: VK_TAB,
        wx.WXK_RETURN: VK_RETURN, wx.WXK_NUMPAD_ENTER: VK_RETURN,
        wx.WXK_SHIFT: VK_SHIFT, wx.WXK_CONTROL: VK_CONTROL,
        wx.WXK_ALT: VK_MENU, wx.WXK_CAPITAL: VK_CAPITAL,
        wx.WXK_ESCAPE: VK_ESCAPE, wx.WXK_SPACE: VK_SPACE,
        wx.WXK_PAGEUP: VK_PRIOR, wx.WXK_PAGEDOWN: VK_NEXT,
        wx.WXK_END: VK_END, wx.WXK_HOME: VK_HOME,
        wx.WXK_LEFT: VK_LEFT, wx.WXK_UP: VK_UP,
        wx.WXK_RIGHT: VK_RIGHT, wx.WXK_DOWN: VK_DOWN,
        wx.WXK_INSERT: VK_INSERT, wx.WXK_DELETE: VK_DELETE,
        wx.WXK_WINDOWS_LEFT: VK_LWIN,
    })
    for i in range(12):
        wxk = getattr(wx, "WXK_F%d" % (i + 1), None)
        if wxk is not None:
            _WXK[wxk] = 0x70 + i      # VK_F1..VK_F12


def wx_vk(wxkey):
    """wx keycode → Windows virtuális billentyűkód, vagy None ha nem ismert.
    A 0-9 és A-Z tartományban a wx-kód MEGEGYEZIK a VK-kóddal."""
    _init_map()
    if wxkey in _WXK:
        return _WXK[wxkey]
    if 48 <= wxkey <= 57 or 65 <= wxkey <= 90:
        return wxkey
    return None


class Elkapo:
    """Egy wx-ablakra köti a billentyű-elkapást. Amíg `aktiv`, a lenyomott/
    felengedett billentyűket VK-eseményként a `kuldo(esemeny)`-nek adja, és NEM
    engedi tovább (nehogy az irányító saját gépén is végrehajtódjanak). Ha nem
    `aktiv`, mindent továbbenged (normál használat)."""

    def __init__(self, ablak, kuldo):
        self.kuldo = kuldo
        self.aktiv = False
        ablak.Bind(wx.EVT_KEY_DOWN, lambda e: self._key(e, True))
        ablak.Bind(wx.EVT_KEY_UP, lambda e: self._key(e, False))

    def _key(self, e, le):
        if not self.aktiv:
            e.Skip()
            return
        vk = wx_vk(e.GetKeyCode())
        if vk is not None:
            try:
                self.kuldo(VZ.e_bill(vk, le))
            except Exception:
                pass
        # aktív elkapásnál NEM skipelünk – a billentyű csak a távoli gépre megy
