# -*- coding: utf-8 -*-
"""Wi-Fi jelerősség FOLYAMATOS figyelése – mesh-hálózat építéséhez.

Felhasználói kérés (2026-08-20): „olyan eszközt keresnék, ami kiírná, hogy
milyen jelerősségű az épp használt wifi-kapcsolat, a dBm értéket megadva…
mesh hálót építek éppen ki, jó lenne látnom laptopon is, hogy hol milyen erős
még a kapcsolat.”

MIÉRT NEM ELÉG A SZÁM KIÍRÁSA? Mert a mesh-építés közben az ember JÁRKÁL a
lakásban, és közben nem nézi a képernyőt – vakon pedig végképp nem. Ezért:

  • a program másfél másodpercenként mér, és az érdemi változást KIMONDJA;
  • közben rövid hangot ad, aminek a MAGASSÁGA követi a jelerősséget (erősebb
    jel = magasabb hang) – ez a leggyorsabb visszajelzés, nem kell megvárni a
    bemondást;
  • a SZÓKÖZZEL megjelölhető a mostani helyszín („konyha”), a végén pedig a
    program megmondja, hol gyenge a jel, vagyis hova érdemes még egy egység.

A mérés-logika a `nettest`-ben van (wx nélkül, tesztelhetően); itt csak az
ablak van.
"""

from __future__ import annotations

import wx

from . import nettest as _nt


class WifiFigyeloDialog(wx.Dialog):
    IDOKOZ_MS = 1500

    def __init__(self, parent, mondd):
        super().__init__(parent, title="Wi-Fi jelerősség figyelése",
                         size=(720, 520))
        self._mondd_kulso = mondd
        self._naplo = _nt.JelNaplo()
        self._halozat = ""
        self._closing = False
        self._hang_be = True

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        sug = wx.StaticText(p, label=(
            "Indítsd el a figyelést, és sétálj körbe a lakásban. A program "
            "kimondja a jelerősséget, és egy hanggal is jelzi: minél magasabb "
            "a hang, annál erősebb a jel. A szóközzel megjelölheted, hol jársz "
            "éppen — a végén megmondom, hova érdemes még egy mesh-egység."))
        sug.Wrap(680)
        v.Add(sug, 0, wx.ALL, 10)

        self.allapot = wx.TextCtrl(
            p, value="A figyelés még nem indult el.", size=(-1, 70),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.allapot.SetName("Jelenlegi jelerősség")
        v.Add(self.allapot, 0, wx.EXPAND | wx.ALL, 10)

        v.Add(wx.StaticText(p, label="&Megjelölt helyek:"), 0, wx.LEFT, 10)
        self.lista = wx.ListBox(p, choices=[])
        self.lista.SetName("Megjelölt helyek")
        v.Add(self.lista, 1, wx.EXPAND | wx.ALL, 10)

        s1 = wx.BoxSizer(wx.HORIZONTAL)
        self.b_start = wx.Button(p, label="&Figyelés indítása")
        self.b_start.SetDefault()
        self.b_start.Bind(wx.EVT_BUTTON, lambda e: self._inditas_valt())
        self.b_pont = wx.Button(p, label="Hely meg&jelölése  (szóköz)")
        self.b_pont.Bind(wx.EVT_BUTTON, lambda e: self._pont())
        self.b_pont.Enable(False)
        self.cb_hang = wx.CheckBox(p, label="&Hangjelzés")
        self.cb_hang.SetValue(True)
        self.cb_hang.SetName("Hangjelzés: a hang magassága követi a "
                             "jelerősséget")
        self.cb_hang.Bind(wx.EVT_CHECKBOX, lambda e: self._hang_valt())
        for w in (self.b_start, self.b_pont, self.cb_hang):
            s1.Add(w, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 8)
        v.Add(s1, 0, wx.LEFT | wx.BOTTOM, 10)

        s2 = wx.BoxSizer(wx.HORIZONTAL)
        b_ossz = wx.Button(p, label="Ö&sszefoglaló")
        b_ossz.Bind(wx.EVT_BUTTON, lambda e: self._osszefoglalo())
        b_ment = wx.Button(p, label="Mentés &fájlba…")
        b_ment.Bind(wx.EVT_BUTTON, lambda e: self._ment())
        b_zar = wx.Button(p, wx.ID_CANCEL, "&Bezárás")
        for w in (b_ossz, b_ment, b_zar):
            s2.Add(w, 0, wx.RIGHT, 8)
        v.Add(s2, 0, wx.ALL, 10)
        p.SetSizer(v)

        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self._meres(), self._timer)
        self.Bind(wx.EVT_CLOSE, self._bezar)
        self.Bind(wx.EVT_CHAR_HOOK, self._bill)
        self.CentreOnParent()
        wx.CallAfter(self._mondd,
                     "Wi-Fi jelerősség figyelése. Indítsd el, és sétálhatsz; "
                     "a szóköz megjelöli, hol jársz.")

    # ------------------------------------------------ segédek
    def _mondd(self, szoveg):
        if not self._closing and szoveg:
            self._mondd_kulso(szoveg)

    def _hang_valt(self):
        self._hang_be = bool(self.cb_hang.GetValue())

    def _bill(self, e):
        if e.GetKeyCode() == wx.WXK_SPACE and self._timer.IsRunning():
            self._pont()
            return
        e.Skip()

    # ------------------------------------------------ mérés
    def _inditas_valt(self):
        if self._timer.IsRunning():
            self._timer.Stop()
            self.b_start.SetLabel("&Figyelés indítása")
            self.b_pont.Enable(False)
            self._mondd("Figyelés leállítva. " + self._naplo.osszefoglalo())
            return
        adat = _nt.wifi()
        if not adat:
            self._mondd("Most nem látok Wi-Fi kapcsolatot. Vezetékes hálózaton "
                        "nincs mit mérni.")
            return
        self._halozat = adat.get("halozat", "")
        self.b_start.SetLabel("Figyelés &leállítása")
        self.b_pont.Enable(True)
        self._mondd("Figyelés indul a(z) %s hálózaton." % self._halozat)
        self._meres()
        self._timer.Start(self.IDOKOZ_MS)

    def _meres(self):
        if self._closing:
            return
        adat = _nt.wifi()
        if not adat:
            self.allapot.SetValue("Megszakadt a Wi-Fi kapcsolat.")
            self._mondd("Megszakadt a Wi-Fi kapcsolat.")
            self._timer.Stop()
            self.b_start.SetLabel("&Figyelés indítása")
            self.b_pont.Enable(False)
            return
        dbm = int(adat.get("dbm", 0))
        jel = int(adat.get("jel", 0))
        szoveg = _nt.jel_szoveg(dbm, jel, bool(adat.get("dbm_mert")))
        self.allapot.SetValue(
            "%s\n%s – %s, %d. csatorna"
            % (szoveg, adat.get("halozat", ""), adat.get("sav", ""),
               int(adat.get("csatorna", 0))))
        if self._hang_be:
            self._hang(dbm)
        # csak az ÉRDEMI változást mondjuk ki – különben végig beszélne
        if self._naplo.hozzaad(dbm, jel):
            fokozat, _ = _nt.jel_minosites(dbm)
            self._mondd("%d dBm, %s" % (dbm, fokozat))

    @staticmethod
    def _hang(dbm):
        """Rövid síp, aminek a magassága követi a jelerősséget."""
        try:
            import winsound
            winsound.Beep(int(_nt.jel_frekvencia(dbm)), 90)
        except Exception:
            pass

    # ------------------------------------------------ pontok
    def _pont(self):
        if not self._naplo.meresek:
            self._mondd("Előbb indítsd el a figyelést.")
            return
        d = wx.TextEntryDialog(self, "Hol vagy most? (például: konyha, "
                               "hálószoba, padlás)", "Hely megjelölése")
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        nev = d.GetValue()
        d.Destroy()
        tetel = self._naplo.pont(nev)
        self.lista.Append(self._naplo.pont_szoveg(tetel))
        self.lista.SetSelection(self.lista.GetCount() - 1)
        self._mondd("Megjelölve – " + self._naplo.pont_szoveg(tetel))

    def _osszefoglalo(self):
        sz = self._naplo.osszefoglalo()
        self._mondd(sz)
        wx.MessageBox(sz, "Összefoglaló", wx.OK | wx.ICON_INFORMATION, self)

    def _ment(self):
        d = wx.FileDialog(self, "Bejárás mentése", "", "wifi-bejaras.txt",
                          "Szövegfájl (*.txt)|*.txt",
                          wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        ut = d.GetPath()
        d.Destroy()
        try:
            with open(ut, "w", encoding="utf-8") as f:
                f.write(self._naplo.mentheto_szoveg(self._halozat))
            self._mondd("Elmentve: %s" % ut)
        except OSError as ex:
            self._mondd("A mentés nem sikerült: %s" % ex)

    def _bezar(self, e):
        self._closing = True
        try:
            self._timer.Stop()
        except Exception:
            pass
        e.Skip()


def mutasd(parent, mondd) -> None:
    d = WifiFigyeloDialog(parent, mondd)
    d.ShowModal()
    d.Destroy()
