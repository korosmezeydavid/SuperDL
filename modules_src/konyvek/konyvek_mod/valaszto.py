# -*- coding: utf-8 -*-
"""Fájl- és mappaválasztás a Könyvek modulban – a BEÉPÍTETT választóval.

MIÉRT: Dr. Kiss István 4.6.4-es összeomlás-naplójában a program natívan
KILÉPETT, miközben a fő szál a `bookwin._on_pick_book` fájlválasztójában járt.
Ez nem a mi hibánk: a Windows fájlválasztójába idegen bővítmények épülnek be
(bélyegkép-készítő, felhő-szinkron, vírusirtó), és ha egyikük elszáll, viszi
magával az egész programot – Pythonból ezt nem lehet elkapni.

Erre a SuperDL-ben MÁR VAN megoldás: a `superdl.fajlvalaszto` teljesen a saját
kódunk, semmilyen rendszerbővítményt nem tölt be (sima listák, `os.scandir`),
és vakon kényelmesebb is (két lista, gyorshelyek, gépeléssel szűrés). A
médiakonvertáló már ezt használja; a Könyvek modul eddig nem.

Itt EGY helyen kötjük be a modul mind az öt választóját. Ha a beépített
választó bármi miatt nem érhető el, VISSZAESÜNK a rendszer választójára –
inkább a régi viselkedés, mint egy működésképtelen menüpont.
"""

import wx

KONYV_KITERJESZTESEK = (".txt", ".docx", ".epub", ".pdf")
HANG_KITERJESZTESEK = (".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus",
                       ".wav", ".flac", ".wma", ".mp2", ".mka")


def _beepitett():
    try:
        from superdl import fajlvalaszto
    except Exception:
        return None
    return fajlvalaszto


def egy_fajl(szulo, cim: str, kiterjesztesek=(), wildcard: str = "",
             mondd=None) -> str:
    """Egy fájl kiválasztása. Üres szöveg, ha a felhasználó mégsem választ."""
    fv = _beepitett()
    if fv is not None:
        try:
            ki = fv.valassz_fajlokat(szulo, cim, kiterjesztesek, tobb=False,
                                     mondd=mondd)
            return ki[0] if ki else ""
        except Exception:
            pass                      # essen vissza a rendszer választójára
    return _nativ_fajl(szulo, cim, wildcard)


def egy_mappa(szulo, cim: str, kezdo: str = "", mondd=None) -> str:
    """Egy mappa kiválasztása. Üres szöveg, ha mégsem választ."""
    fv = _beepitett()
    if fv is not None:
        try:
            return fv.valassz_mappat(szulo, cim, kezdo, mondd=mondd) or ""
        except Exception:
            pass
    return _nativ_mappa(szulo, cim, kezdo)


def _nativ_fajl(szulo, cim: str, wildcard: str) -> str:
    with wx.FileDialog(szulo, cim, wildcard=wildcard or "Minden fájl|*.*",
                       style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
        return dlg.GetPath() if dlg.ShowModal() == wx.ID_OK else ""


def _nativ_mappa(szulo, cim: str, kezdo: str) -> str:
    with wx.DirDialog(szulo, cim, kezdo or "") as dlg:
        return dlg.GetPath() if dlg.ShowModal() == wx.ID_OK else ""
