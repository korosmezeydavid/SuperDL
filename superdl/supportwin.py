"""„Köszönet és támogatás" ablak – önkéntes, sosem kötelező.

Akadálymentes: a szöveg egy csak olvasható mezőben; alul gombok a Revolut
megnyitásához és a számlaszám vágólapra másolásához.
"""

import webbrowser

import wx

IBAN = "HU61 1210 0011 1984 2198 0000 0000"
REVOLUT = "https://revolut.me/davidkoros"

SUPPORT_TEXT = """Köszönet és támogatás

Szia! Ezt a programot Kőrösmezey Dávid Richárd készíti – egyedül, szabad \
időben, azzal a céllal, hogy a letöltés, a média, a hírek és az olvasás \
mindenki számára, képernyőolvasóval is, könnyű és élvezetes legyen.

A SuperDL ingyenes, és az is marad. Támogatni SEMMI nem kötelez – a program \
minden funkciója ugyanúgy működik nélküle is. Ezt tényleg szívből írom: a \
köszönet a legfontosabb, és azt már most megkaptam azzal, hogy használod.

De ha örömödet lelted benne, és szeretnél hozzájárulni a továbbfejlesztéshez \
– vagy csak meghívnál egy kávéra, egy uzsonnára, annyira, amennyit jónak \
látsz –, azt hálásan köszönöm. Minden korty és falat erőt ad a következő \
ötletekhez.

Támogatás (Magyarország):
   Kedvezményezett: Kőrösmezey Dávid Richárd
   Számlaszám: 12100011-19842198
   IBAN: HU61 1210 0011 1984 2198 0000 0000
   BIC / SWIFT: GNBAHUHB

Revolut:
   https://revolut.me/davidkoros

Köszönöm, hogy velem tartasz ezen az úton.
   – Dávid"""


class SupportDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Köszönet és támogatás",
                         size=(640, 560))
        self._announce = getattr(parent, "_announce", None)
        v = wx.BoxSizer(wx.VERTICAL)
        txt = wx.TextCtrl(self, value=SUPPORT_TEXT,
                          style=wx.TE_MULTILINE | wx.TE_READONLY |
                          wx.TE_BESTWRAP)
        txt.SetName("Köszönet és támogatás – szöveg")
        v.Add(txt, 1, wx.EXPAND | wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        b_rev = wx.Button(self, label="&Revolut megnyitása")
        b_rev.Bind(wx.EVT_BUTTON, lambda e: webbrowser.open(REVOLUT))
        b_iban = wx.Button(self, label="&IBAN másolása")
        b_iban.Bind(wx.EVT_BUTTON, lambda e: self._copy(IBAN))
        b_close = wx.Button(self, wx.ID_CANCEL, "&Bezárás")
        for b in (b_rev, b_iban, b_close):
            row.Add(b, 0, wx.RIGHT, 6)
        v.Add(row, 0, wx.ALL | wx.ALIGN_RIGHT, 8)
        self.SetSizer(v)
        txt.SetInsertionPoint(0)
        txt.SetFocus()

    def _copy(self, text):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Close()
            if self._announce:
                self._announce("Az IBAN a vágólapra másolva.")
