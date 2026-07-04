"""Egységes, akadálymentes SÚGÓ-ablak a modul-eszközökhöz.

A súgó egy csak olvasható, görgethető szövegmező, aminek INDULÁSKOR a fókusz a
szövegen van → a képernyőolvasó rögtön felolvassa az egészet. Minden súgóban ott
a „Támogatás" gomb is (a Köszönet és támogatás ablakot nyitja), hogy bárki
felfedezhesse az önkéntes támogatás lehetőségét.

Használat a modulokban (visszafelé kompatibilisen, régi Core-on is):
    try:
        from superdl.helpdialog import show_help
        show_help(self, cím, szöveg)
    except Exception:
        import wx; wx.MessageBox(szöveg, cím, wx.OK | wx.ICON_INFORMATION, self)
"""

import wx

_SUPPORT_LINE = (
    "\n\n———\nTÁMOGATÁS\n"
    "A SuperDL ingyenes, és az is marad. A fejlesztés rengeteg munka; ha "
    "szeretnéd támogatni (SOHA nem kötelező, és semmilyen funkciót nem zár el), "
    "nyomd meg ezen az ablakon a „Támogatás” gombot – ott a Revolut-hivatkozás "
    "és a bankszámla (IBAN), másolható. Köszönöm!")


class HelpDialog(wx.Dialog):
    def __init__(self, parent, title, text):
        super().__init__(parent, title=f"Súgó – {title}",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
                         size=(700, 580))
        v = wx.BoxSizer(wx.VERTICAL)
        self.txt = wx.TextCtrl(
            self, value=(text or "").strip() + _SUPPORT_LINE,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP
            | wx.HSCROLL)
        self.txt.SetName(f"{title} – súgó szövege")
        v.Add(self.txt, 1, wx.EXPAND | wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        b_sup = wx.Button(self, label="&Támogatás…")
        b_sup.SetName("Köszönet és támogatás – Revolut és IBAN")
        b_sup.Bind(wx.EVT_BUTTON, self._on_support)
        b_close = wx.Button(self, wx.ID_CANCEL, "&Bezárás")
        row.Add(b_sup, 0, wx.RIGHT, 8)
        row.Add(b_close, 0)
        v.Add(row, 0, wx.ALIGN_RIGHT | wx.ALL, 8)
        self.SetSizer(v)

        self.SetEscapeId(wx.ID_CANCEL)          # Esc zárja
        # F1 zárja is (kikapcsolja a súgót), hogy ne ragadjon be
        _cid = wx.NewIdRef()
        self.Bind(wx.EVT_MENU, lambda e: self.EndModal(wx.ID_CANCEL), id=_cid)
        self.SetAcceleratorTable(
            wx.AcceleratorTable([(wx.ACCEL_NORMAL, wx.WXK_F1, _cid)]))
        # a fókusz a szövegre → a képernyőolvasó rögtön olvassa a súgót
        wx.CallAfter(self.txt.SetInsertionPoint, 0)
        wx.CallAfter(self.txt.SetFocus)

    def _on_support(self, e):
        try:
            from superdl.supportwin import SupportDialog
            d = SupportDialog(self)
            d.ShowModal()
            d.Destroy()
        except Exception:
            wx.MessageBox(
                "A támogatási ablak most nem elérhető. Köszönjük a szándékot!",
                "Támogatás", wx.OK | wx.ICON_INFORMATION, self)


def show_help(parent, title: str, text: str) -> None:
    """A megadott súgó megjelenítése az egységes, akadálymentes ablakban
    (a végén a támogatás lehetőségével)."""
    dlg = HelpDialog(parent, title, text)
    try:
        dlg.ShowModal()
    finally:
        dlg.Destroy()
