# -*- coding: utf-8 -*-
"""BEÉPÍTETT fájlválasztó – teljesen a saját kódunk, Windows-bővítmények nélkül.

MIÉRT VAN RÁ SZÜKSÉG? Egy felhasználónál a program NATÍVAN kilépett, amikor a
Windows fájlválasztójában megnyitott egy könyvtárat. Ilyenkor nem a mi kódunk
hibázik: a rendszer fájlválasztójába idegen bővítmények épülnek be (kodek-
csomagok bélyegkép-készítői, felhő-szinkron, vírusirtó), és ha ezek egyike
elszáll, viszi magával az egész programot. Ezt Pythonból nem lehet elkapni.

Ez a választó SEMMILYEN rendszerbővítményt nem használ: sima listákból áll,
amiket mi töltünk fel `os.scandir`-ral. Ha a rendszer választója összeomlana,
ez akkor is működik.

RÁADÁSKÉNT vakon kényelmesebb is:
  • két lista (mappák, fájlok), mindkettő nyilazható, minden elem felolvasva;
  • Enter a mappán: belépés, Backspace: vissza a szülőmappába;
  • gyorshelyek (Asztal, Dokumentumok, Letöltések, Zene, meghajtók);
  • gépeléssel szűrhető a lista, és a program mondja, hány találat maradt.
"""

from __future__ import annotations

import os
import string
from pathlib import Path

import wx


def _meret_szoveg(bajt: int) -> str:
    for egyseg, hatar in (("gigabájt", 1024 ** 3), ("megabájt", 1024 ** 2),
                          ("kilobájt", 1024)):
        if bajt >= hatar:
            return "%.1f %s" % (bajt / hatar, egyseg)
    return "%d bájt" % bajt


def gyorshelyek() -> list:
    """(név, útvonal) párok: ahova a leggyakrabban megyünk."""
    haza = Path.home()
    jeloltek = [
        ("Asztal", haza / "Desktop"),
        ("Dokumentumok", haza / "Documents"),
        ("Letöltések", haza / "Downloads"),
        ("Zene", haza / "Music"),
        ("Videók", haza / "Videos"),
        ("Képek", haza / "Pictures"),
        ("Saját mappa", haza),
    ]
    ki = [(nev, str(ut)) for nev, ut in jeloltek if ut.is_dir()]
    if os.name == "nt":
        for betu in string.ascii_uppercase:
            gyoker = "%s:\\" % betu
            if os.path.isdir(gyoker):
                ki.append(("%s meghajtó" % betu, gyoker))
    return ki


def tartalom(mappa: str, kiterjesztesek=()) -> tuple:
    """(mappák, fájlok) a megadott könyvtárban, ábécében.

    A rejtett és a hozzáférhetetlen elemeket csendben kihagyjuk – egy
    rendszermappa miatt ne álljon meg a böngészés."""
    mappak, fajlok = [], []
    kit = tuple(k.lower() for k in (kiterjesztesek or ()))
    try:
        with os.scandir(mappa) as bejegyzesek:
            for b in bejegyzesek:
                try:
                    if b.name.startswith("."):
                        continue
                    if b.is_dir(follow_symlinks=False):
                        mappak.append(b.name)
                    elif b.is_file(follow_symlinks=False):
                        if not kit or b.name.lower().endswith(kit):
                            fajlok.append(b.name)
                except OSError:
                    continue
    except OSError:
        return [], []
    mappak.sort(key=str.lower)
    fajlok.sort(key=str.lower)
    return mappak, fajlok


def szuro(nevek, minta: str) -> list:
    """Gépelés szerinti szűrés – ékezet- és kisbetű-tűrően."""
    m = (minta or "").strip().lower()
    if not m:
        return list(nevek)
    return [n for n in nevek if m in n.lower()]


class FajlValaszto(wx.Dialog):
    def __init__(self, parent, cim="Fájl kiválasztása", kezdo="",
                 kiterjesztesek=(), tobb=True, mappat_valassz=False,
                 mondd=None):
        super().__init__(parent, title=cim, size=(760, 600))
        self._kit = tuple(kiterjesztesek or ())
        self._tobb = bool(tobb) and not mappat_valassz
        self._mappat = bool(mappat_valassz)
        self._mondd_kulso = mondd
        self.eredmeny = []
        self._mappa = str(kezdo or Path.home())

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        self.hely = wx.StaticText(p, label="")
        v.Add(self.hely, 0, wx.ALL, 8)

        felso = wx.BoxSizer(wx.HORIZONTAL)
        felso.Add(wx.StaticText(p, label="&Gyorshely:"), 0,
                  wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._helyek = gyorshelyek()
        self.hely_v = wx.Choice(p, choices=[n for n, _ in self._helyek])
        self.hely_v.SetName("Gyorshely")
        self.hely_v.Bind(wx.EVT_CHOICE, lambda e: self._gyorshely())
        felso.Add(self.hely_v, 0, wx.RIGHT, 12)
        felso.Add(wx.StaticText(p, label="S&zűrés (gépelj):"), 0,
                  wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.szuro_mezo = wx.TextCtrl(p)
        self.szuro_mezo.SetName("Szűrés a nevekre")
        self.szuro_mezo.Bind(wx.EVT_TEXT, lambda e: self._frissit(csendes=False))
        felso.Add(self.szuro_mezo, 1)
        v.Add(felso, 0, wx.EXPAND | wx.ALL, 8)

        kozep = wx.BoxSizer(wx.HORIZONTAL)
        bal = wx.BoxSizer(wx.VERTICAL)
        bal.Add(wx.StaticText(p, label="&Mappák  (Enter: belépés, "
                                       "Backspace: vissza):"), 0, wx.LEFT, 4)
        self.mappa_lista = wx.ListBox(p, style=wx.LB_SINGLE)
        self.mappa_lista.SetName("Mappák")
        self.mappa_lista.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._belep())
        bal.Add(self.mappa_lista, 1, wx.EXPAND | wx.ALL, 4)
        kozep.Add(bal, 1, wx.EXPAND)

        if not self._mappat:
            jobb = wx.BoxSizer(wx.VERTICAL)
            jobb.Add(wx.StaticText(p, label="&Fájlok:"), 0, wx.LEFT, 4)
            self.fajl_lista = wx.ListBox(
                p, style=wx.LB_EXTENDED if self._tobb else wx.LB_SINGLE)
            self.fajl_lista.SetName("Fájlok")
            self.fajl_lista.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._kesz())
            jobb.Add(self.fajl_lista, 1, wx.EXPAND | wx.ALL, 4)
            kozep.Add(jobb, 1, wx.EXPAND)
        else:
            self.fajl_lista = None
        v.Add(kozep, 1, wx.EXPAND | wx.ALL, 6)

        gs = wx.BoxSizer(wx.HORIZONTAL)
        b_fel = wx.Button(p, label="&Vissza a szülőmappába  (Backspace)")
        b_fel.Bind(wx.EVT_BUTTON, lambda e: self._szulo())
        gs.Add(b_fel, 0, wx.RIGHT, 8)
        cimke = "Ezt a mappát választom" if self._mappat else "&Kiválasztás"
        ok = wx.Button(p, wx.ID_OK, cimke)
        ok.SetDefault()
        ok.Bind(wx.EVT_BUTTON, lambda e: self._kesz())
        gs.Add(ok, 0, wx.RIGHT, 8)
        gs.Add(wx.Button(p, wx.ID_CANCEL, "&Mégsem"), 0)
        v.Add(gs, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        p.SetSizer(v)

        self.Bind(wx.EVT_CHAR_HOOK, self._bill)
        self.CentreOnParent()
        self._frissit()
        wx.CallAfter(self.mappa_lista.SetFocus)

    # ---------------------------------------------------- segédek
    def _mondd(self, szoveg):
        if callable(self._mondd_kulso):
            try:
                self._mondd_kulso(szoveg)
                return
            except Exception:
                pass
        try:
            from . import screenreader
            screenreader.speak(szoveg)
        except Exception:
            pass

    def _bill(self, e):
        k = e.GetKeyCode()
        if k == wx.WXK_BACK and self.FindFocus() is not self.szuro_mezo:
            self._szulo()
            return
        if k in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) \
                and self.FindFocus() is self.mappa_lista:
            self._belep()
            return
        e.Skip()

    # ---------------------------------------------------- tartalom
    def _frissit(self, csendes=True):
        mappak, fajlok = tartalom(self._mappa, self._kit)
        minta = self.szuro_mezo.GetValue()
        mappak, fajlok = szuro(mappak, minta), szuro(fajlok, minta)
        self._mappak, self._fajlok = mappak, fajlok
        self.mappa_lista.Set(mappak or [])
        if self.fajl_lista is not None:
            self.fajl_lista.Set(fajlok or [])
        self.hely.SetLabel("Jelenlegi hely: %s" % self._mappa)
        uzenet = ("%s – %d mappa, %d fájl"
                  % (self._mappa, len(mappak), len(fajlok)))
        if minta:
            uzenet += " (szűrve erre: %s)" % minta
        if not csendes:
            self._mondd(uzenet)
        return uzenet

    def _belep(self):
        i = self.mappa_lista.GetSelection()
        if i < 0 or i >= len(self._mappak):
            return
        uj = os.path.join(self._mappa, self._mappak[i])
        if not os.path.isdir(uj):
            self._mondd("Ez a mappa nem nyitható meg.")
            return
        self._mappa = uj
        self.szuro_mezo.SetValue("")
        self._mondd(self._frissit())
        self.mappa_lista.SetFocus()

    def _szulo(self):
        szulo = os.path.dirname(self._mappa.rstrip("\\/")) or self._mappa
        if szulo == self._mappa:
            self._mondd("Ez már a legfelső szint.")
            return
        self._mappa = szulo
        self.szuro_mezo.SetValue("")
        self._mondd(self._frissit())
        self.mappa_lista.SetFocus()

    def _gyorshely(self):
        i = self.hely_v.GetSelection()
        if 0 <= i < len(self._helyek):
            self._mappa = self._helyek[i][1]
            self.szuro_mezo.SetValue("")
            self._mondd(self._frissit())
            self.mappa_lista.SetFocus()

    # ---------------------------------------------------- eredmény
    def _kesz(self):
        if self._mappat:
            self.eredmeny = [self._mappa]
            self.EndModal(wx.ID_OK)
            return
        if self.fajl_lista is None:
            return
        if self._tobb:
            indexek = list(self.fajl_lista.GetSelections())
        else:
            i = self.fajl_lista.GetSelection()
            indexek = [i] if i >= 0 else []
        if not indexek:
            self._mondd("Előbb jelölj ki legalább egy fájlt a Fájlok "
                        "listában.")
            return
        self.eredmeny = [os.path.join(self._mappa, self._fajlok[i])
                         for i in indexek if 0 <= i < len(self._fajlok)]
        self.EndModal(wx.ID_OK)


def valassz_fajlokat(parent, cim="Fájlok kiválasztása", kiterjesztesek=(),
                     tobb=True, kezdo="", mondd=None) -> list:
    d = FajlValaszto(parent, cim, kezdo, kiterjesztesek, tobb, False, mondd)
    ki = d.eredmeny if d.ShowModal() == wx.ID_OK else []
    d.Destroy()
    return list(ki)


def valassz_mappat(parent, cim="Mappa kiválasztása", kezdo="",
                   mondd=None) -> str:
    d = FajlValaszto(parent, cim, kezdo, (), False, True, mondd)
    ki = d.eredmeny if d.ShowModal() == wx.ID_OK else []
    d.Destroy()
    return ki[0] if ki else ""
