"""A hangszín-szabályzó párbeszéde: NYILAZHATÓ LISTA + EGY csúszka.

⚠️ A forma Stolmár Barbival egyeztetve (2026-09-21/23). Nincs tíz sáv és
nincs decibel-szám: egy lista megnevezett hangszínekkel, és egy csúszka
arra, hogy MENNYIRE.

⚠️ ÉLŐBEN SZÓL. Nyilazásra és a csúszka elengedésére a program AZONNAL
átállítja a hangot. Vakon a hangszínt kizárólag HALLÁS alapján lehet
megválasztani – egy „Rendben"-re váró párbeszéd itt használhatatlan lenne.

⚠️ A MÉGSE VISSZAÁLLÍT. Ha élőben állítunk, a visszaút kötelező.
"""
import wx

from . import hangszin as HSZ


class HangszinParbeszed(wx.Dialog):
    def __init__(self, szulo, profil: str, erosseg: int, alkalmaz, mond=None):
        super().__init__(szulo, title="Hangszín", size=(560, 420))
        self._alkalmaz = alkalmaz
        self._mond = mond or (lambda _sz: None)
        self._kezdo = (profil, int(erosseg))

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        # ⚠️ A CÍMKE A VEZÉRLŐ ELŐTT jön létre: a képernyőolvasó a LÉTREHOZÁSI
        # sorrend szerint párosít, nem a sizer szerint.
        v.Add(wx.StaticText(p, label="&Hangszín (fel-le nyíllal válassz, "
                                     "azonnal hallod):"), 0, wx.ALL, 8)
        self.lista = wx.ListBox(p, choices=HSZ.nevek())
        self.lista.SetName("Hangszín")
        self.lista.SetSelection(HSZ.index(profil))
        self.lista.Bind(wx.EVT_LISTBOX, lambda _e: self._valtozott(mondd=True))
        v.Add(self.lista, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        self.leiras = wx.StaticText(p, label=HSZ.leiras(profil))
        v.Add(self.leiras, 0, wx.ALL, 8)

        v.Add(wx.StaticText(p, label="&Mértéke (százalék) – a nulla mindig az "
                                     "eredeti hang:"), 0, wx.ALL, 8)
        self.csuszka = wx.Slider(p, value=int(erosseg), minValue=0,
                                 maxValue=100,
                                 style=wx.SL_HORIZONTAL | wx.SL_LABELS)
        self.csuszka.SetName("Mérték százalékban")
        # ⚠️ SCROLL_CHANGED, nem SCROLL: a nyilazás közben minden lépésnél
        # újraindítani a lejátszást szaggatna. Így az ELENGEDÉSRE (illetve a
        # billentyűs lépés végére) alkalmazunk.
        self.csuszka.Bind(wx.EVT_SCROLL_CHANGED,
                          lambda _e: self._valtozott(mondd=True))
        v.Add(self.csuszka, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        b_alap = wx.Button(p, label="&Alapállapot (eredeti hang)")
        b_alap.Bind(wx.EVT_BUTTON, lambda _e: self._alapallapot())
        sor.Add(b_alap, 0, wx.RIGHT, 6)
        b_ok = wx.Button(p, wx.ID_OK, label="&Rendben")
        b_ok.SetDefault()
        sor.Add(b_ok, 0, wx.RIGHT, 6)
        b_megse = wx.Button(p, wx.ID_CANCEL, label="Mé&gse")
        sor.Add(b_megse, 0)
        v.Add(sor, 0, wx.ALL, 8)

        p.SetSizer(v)
        self.lista.SetFocus()
        self.Bind(wx.EVT_BUTTON, self._megse, id=wx.ID_CANCEL)

    # ---- a jelenlegi választás ----
    def profil(self) -> str:
        i = self.lista.GetSelection()
        azon = HSZ.azonositok()
        return azon[i] if 0 <= i < len(azon) else HSZ.ALAP_PROFIL

    def erosseg(self) -> int:
        return int(self.csuszka.GetValue())

    # ---- élő alkalmazás ----
    def _valtozott(self, mondd=False):
        pr = self.profil()
        self.leiras.SetLabel(HSZ.leiras(pr))
        try:
            self._alkalmaz(pr, self.erosseg())
        except Exception:
            pass
        if mondd:
            self._mond(HSZ.mondat(pr, self.erosseg()))

    def _alapallapot(self):
        self.lista.SetSelection(HSZ.index(HSZ.ALAP_PROFIL))
        self.csuszka.SetValue(HSZ.ALAP_EROSSEG)
        self._valtozott(mondd=True)
        self.lista.SetFocus()

    def _megse(self, e):
        """⚠️ Élőben állítottunk, tehát a Mégse tényleg állítson vissza."""
        try:
            self._alkalmaz(self._kezdo[0], self._kezdo[1])
        except Exception:
            pass
        e.Skip()
