# -*- coding: utf-8 -*-
"""Teljes mentés és visszaállítás – az ablak.

„Új gépre költözöm” esetén ez az egy ablak elég: egy fájl, egy jelszó, és
minden ott van, ahol volt.

A logika a `mentes.py`-ban van (wx nélkül, tesztelhetően); itt csak a felület
és a felolvasás.
"""

from __future__ import annotations

import os
import threading

import wx

from . import mentes as _m


def _mondd(szoveg):
    if not (szoveg or "").strip():
        return
    try:
        from . import screenreader
        screenreader.speak(szoveg)
    except Exception:
        pass


class MentesDialog(wx.Dialog):
    def __init__(self, parent, main=None):
        super().__init__(parent, title="Teljes mentés és visszaállítás",
                         size=(760, 620))
        self.main = main
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        sug = wx.StaticText(p, label=(
            "Itt egyetlen fájlba mentheted az EGÉSZ SuperDL-t: a "
            "beállításokat, a feliratkozásokat, a könyvjelzőket, a naptárt, a "
            "címjegyzéket, a levelező szabályait — és a bizalmas adatokat is: "
            "az e-mail jelszavakat és az AI-kulcsokat.\n\n"
            "Éppen ezért a mentéshez JELSZÓ kell, és a fájl azzal titkosítva "
            "készül. Ha elveszted a jelszót, a mentés nem nyitható ki — ezt "
            "senki, én sem tudom megkerülni. A fájl sehova nem megy: oda "
            "mented, ahova te szeretnéd."))
        sug.Wrap(720)
        v.Add(sug, 0, wx.ALL, 12)

        s1 = wx.BoxSizer(wx.HORIZONTAL)
        s1.Add(wx.StaticText(p, label="&Jelszó:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.jelszo = wx.TextCtrl(p, style=wx.TE_PASSWORD)
        self.jelszo.SetName("Jelszó a mentéshez, legalább %d karakter"
                            % _m.MIN_JELSZO)
        s1.Add(self.jelszo, 1, wx.RIGHT, 12)
        self.mutat = wx.CheckBox(p, label="Jelszó &mutatása")
        self.mutat.SetName("A jelszó megmutatása – ellenőrzéshez")
        self.mutat.Bind(wx.EVT_CHECKBOX, lambda e: self._jelszo_valt())
        s1.Add(self.mutat, 0, wx.ALIGN_CENTER_VERTICAL)
        v.Add(s1, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        s2 = wx.BoxSizer(wx.HORIZONTAL)
        b_ment = wx.Button(p, label="&Mentés készítése…")
        b_ment.SetName("Teljes mentés készítése fájlba")
        b_ment.SetDefault()
        b_ment.Bind(wx.EVT_BUTTON, lambda e: self._ment())
        b_vissza = wx.Button(p, label="&Visszaállítás mentésből…")
        b_vissza.SetName("Korábbi mentés visszatöltése")
        b_vissza.Bind(wx.EVT_BUTTON, lambda e: self._vissza())
        b_zar = wx.Button(p, wx.ID_CANCEL, "&Bezárás")
        for b in (b_ment, b_vissza, b_zar):
            s2.Add(b, 0, wx.RIGHT, 8)
        v.Add(s2, 0, wx.LEFT | wx.BOTTOM, 12)

        v.Add(wx.StaticText(p, label="&Eredmény:"), 0, wx.LEFT, 12)
        self.naplo = wx.TextCtrl(
            p, value="", style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.naplo.SetName("Eredmény")
        v.Add(self.naplo, 1, wx.EXPAND | wx.ALL, 12)
        p.SetSizer(v)

        self.CentreOnParent()
        self.jelszo.SetFocus()
        wx.CallAfter(_mondd,
                     "Teljes mentés és visszaállítás. Adj meg egy jelszót, "
                     "majd válaszd a mentés készítését vagy a visszaállítást.")

    # ---------------------------------------------------- segédek
    def _jelszo_valt(self):
        """A jelszó megmutatása: a mezőt újra kell építeni (a wx nem enged
        stílust váltani menet közben)."""
        ertek = self.jelszo.GetValue()
        szulo = self.jelszo.GetParent()
        uj = wx.TextCtrl(szulo, value=ertek,
                         style=0 if self.mutat.GetValue() else wx.TE_PASSWORD)
        uj.SetName(self.jelszo.GetName())
        self.jelszo.GetContainingSizer().Replace(self.jelszo, uj)
        self.jelszo.Destroy()
        self.jelszo = uj
        szulo.Layout()
        self.jelszo.SetFocus()

    def _ir(self, szoveg):
        self.naplo.SetValue(szoveg)
        _mondd(szoveg)

    def _jelszo_ok(self) -> str:
        j = self.jelszo.GetValue()
        if len(j) < _m.MIN_JELSZO:
            self._ir("A jelszónak legalább %d karakternek kell lennie. A "
                     "mentés e-mail jelszavakat és kulcsokat tartalmaz, ezért "
                     "jelszó nélkül nem készíthető el." % _m.MIN_JELSZO)
            self.jelszo.SetFocus()
            return ""
        return j

    # ---------------------------------------------------- mentés
    def _ment(self):
        j = self._jelszo_ok()
        if not j:
            return
        if not _m.titkositas_elerheto():
            self._ir("A titkosító réteg nem érhető el ezen a gépen, ezért nem "
                     "készítek mentést – nyílt szövegben nem írom ki a "
                     "jelszavaidat.")
            return
        d = wx.FileDialog(self, "Mentés helye", "", _m.alap_fajlnev(),
                          "SuperDL-mentés (*%s)|*%s" % (_m.KITERJESZTES,
                                                        _m.KITERJESZTES),
                          wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        ut = d.GetPath()
        d.Destroy()
        self._ir("Mentés készül… ez néhány másodperc.")

        def munka():
            try:
                ossz = _m.keszit(ut, j)
            except Exception as ex:
                wx.CallAfter(self._ir, "A mentés nem sikerült: %s" % ex)
                return
            wx.CallAfter(self._ment_kesz, ossz)

        threading.Thread(target=munka, daemon=True).start()

    def _ment_kesz(self, ossz):
        meta = ossz.get("meta") or {}
        sorok = [
            "Kész a mentés: %s" % ossz["ut"],
            "Mérete: %s" % _m.meret_szoveg(ossz["meret"]),
            "%d adatfájl, %d bizalmas fájl (jelszavak, kulcsok), %d modul "
            "feljegyezve." % (ossz["fajlok"], ossz["titkos"], ossz["modulok"]),
            "",
            "Ezt a fájlt tedd biztonságos helyre. Jelszó nélkül NEM nyitható "
            "ki – ez a védelme, de egyben azt is jelenti, hogy a jelszót nem "
            "lehet pótolni.",
        ]
        if ossz.get("hibak"):
            sorok.append("")
            sorok.append("Ezekhez nem fértem hozzá: "
                         + "; ".join(ossz["hibak"][:5]))
        self._ir("\n".join(sorok))

    # ---------------------------------------------------- visszaállítás
    def _vissza(self):
        j = self._jelszo_ok()
        if not j:
            return
        d = wx.FileDialog(self, "Melyik mentésből?", "", "",
                          "SuperDL-mentés (*%s)|*%s" % (_m.KITERJESZTES,
                                                        _m.KITERJESZTES),
                          wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        ut = d.GetPath()
        d.Destroy()
        try:
            elonezet = _m.elonezet(ut, j)
        except Exception as ex:
            self._ir("A mentés nem nyitható meg: %s" % ex)
            return
        # VAKON KÜLÖNÖSEN FONTOS: mondjuk el ELŐRE, mit fogunk felülírni
        kerdes = ("%s\n\nA visszaállítás FELÜLÍRJA a mostani beállításokat és "
                  "adatokat. A régiekről előbb biztonsági másolatot készítek.\n\n"
                  "Folytassam?" % elonezet)
        _mondd(elonezet + " A visszaállítás felülírja a mostani adatokat.")
        if wx.MessageBox(kerdes, "Visszaállítás",
                         wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
            self._ir("Rendben, nem nyúltam semmihez.")
            return
        self._ir("Visszaállítás folyamatban…")

        def munka():
            try:
                return _m.visszaallit(ut, j)
            except Exception as ex:
                wx.CallAfter(self._ir, "A visszaállítás nem sikerült: %s" % ex)
                return None

        def fut():
            eredmeny = munka()
            if eredmeny:
                wx.CallAfter(self._vissza_kesz, eredmeny)

        threading.Thread(target=fut, daemon=True).start()

    def _vissza_kesz(self, eredmeny):
        modulok = eredmeny.get("modulok") or []
        sorok = ["Kész: %d elem visszaállítva." % eredmeny["visszaallt"]]
        if eredmeny.get("elozo"):
            sorok.append("A korábbi adataidról ide készült biztonsági másolat: "
                         "%s" % eredmeny["elozo"])
        if modulok:
            sorok.append("")
            sorok.append("A mentésben ezek a modulok szerepeltek: "
                         + ", ".join(m.get("nev", m.get("id", ""))
                                     for m in modulok))
            sorok.append("A Modulkezelőben telepítsd őket – az adataik már a "
                         "helyükön vannak.")
        if eredmeny.get("hibak"):
            sorok.append("")
            sorok.append("Ezek nem sikerültek: "
                         + "; ".join(eredmeny["hibak"][:5]))
        sorok.append("")
        sorok.append("INDÍTSD ÚJRA a programot, hogy minden a helyére "
                     "kerüljön.")
        self._ir("\n".join(sorok))


def mutasd(parent, main=None) -> None:
    d = MentesDialog(parent, main)
    d.ShowModal()
    d.Destroy()
