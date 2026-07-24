# -*- coding: utf-8 -*-
"""Egységes F1-súgó bármely wx-ablakhoz.

Használat az ablak __init__ végén:
    from superdl.uihelp import bind_help
    bind_help(self, "Súgó – <ablak neve>", "…a súgó szövege…")

Az F1 a Core közös, felolvasható súgó-dialógusát nyitja (helpdialog); ha az
nem elérhető, sima üzenetablakot. Csak akkor kösd be, ha az ablaknak MÉG NINCS
saját EVT_CHAR_HOOK / F1 kezelője (a dupla-kötést kerüld)."""
import wx


def bind_help(window, cim: str, szoveg: str) -> None:
    def _f1(e):
        if e.GetKeyCode() == wx.WXK_F1:
            try:
                from superdl.helpdialog import show_help
                show_help(window, cim, szoveg)
            except Exception:
                wx.MessageBox(szoveg, cim, wx.OK | wx.ICON_INFORMATION, window)
        else:
            e.Skip()
    window.Bind(wx.EVT_CHAR_HOOK, _f1)
