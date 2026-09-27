# -*- coding: utf-8 -*-
"""A Szerencsesüti beállításai: be/ki, érkezés szóban, éjszakai csend."""
import wx

from . import suti as S


class BeallitasDialog(wx.Dialog):
    def __init__(self, szulo, allapot):
        super().__init__(szulo, title="Szerencsesüti – beállítások")
        v = wx.BoxSizer(wx.VERTICAL)
        self.be = wx.CheckBox(self, label="&Bekapcsolva (napközben 15 "
                                          "percenként jön egy süti)")
        self.be.SetValue(bool(allapot.bekapcsolva))
        v.Add(self.be, 0, wx.ALL, 8)
        self.szo = wx.CheckBox(self, label="Érkezéskor a &felolvasó is "
                                           "szóljon (nem csak a hang)")
        self.szo.SetValue(bool(allapot.erkezes_szoval))
        v.Add(self.szo, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.cs = wx.CheckBox(self, label="Ünnepi &süticsomagok a netről "
                                          "(karácsony, húsvét és a többi)")
        self.cs.SetValue(bool(allapot.csomagok))
        v.Add(self.cs, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        g = wx.FlexGridSizer(cols=2, vgap=6, hgap=8)
        g.Add(wx.StaticText(self, label="Éjszakai csend &kezdete (óó:pp):"),
              0, wx.ALIGN_CENTER_VERTICAL)
        self.tol = wx.TextCtrl(self, value=allapot.csend_tol)
        self.tol.SetName("Éjszakai csend kezdete, óra kettőspont perc")
        g.Add(self.tol)
        g.Add(wx.StaticText(self, label="Éjszakai csend &vége (óó:pp):"),
              0, wx.ALIGN_CENTER_VERTICAL)
        self.ig = wx.TextCtrl(self, value=allapot.csend_ig)
        self.ig.SetName("Éjszakai csend vége, óra kettőspont perc")
        g.Add(self.ig)
        v.Add(g, 0, wx.ALL, 8)
        v.Add(wx.StaticText(self, label=(
            "Saját üzeneteidet a felhasználói mappád .superdl\\"
            "szerencse_sajat.txt fájljába írhatod – a formát az "
            "uzenetek.txt mutatja.")), 0, wx.ALL, 8)
        v.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0,
              wx.ALL | wx.ALIGN_RIGHT, 8)
        self.SetSizerAndFit(v)
        self.Bind(wx.EVT_BUTTON, self._ok, id=wx.ID_OK)
        self.be.SetFocus()

    def _ok(self, e):
        for mezo, nev in ((self.tol, "kezdete"), (self.ig, "vége")):
            if S.ido_perc(mezo.GetValue()) is None:
                wx.MessageBox("Az éjszakai csend %s nem jó időpont. Így írd: "
                              "22:00" % nev, "Szerencsesüti",
                              wx.OK | wx.ICON_WARNING, self)
                mezo.SetFocus()
                return
        e.Skip()

    def alkalmaz(self, a):
        a.bekapcsolva = self.be.GetValue()
        a.erkezes_szoval = self.szo.GetValue()
        a.csomagok = self.cs.GetValue()
        a.csend_tol = self.tol.GetValue().strip()
        a.csend_ig = self.ig.GetValue().strip()
