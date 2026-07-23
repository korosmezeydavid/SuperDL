"""„Napi infó" párbeszéd (Ctrl+Shift+W): mai dátum, névnap és időjárás.

Akadálymentes: a szöveg egy csak olvasható, többsoros mezőben jelenik meg,
amelyet a képernyőolvasó nyilakkal bejár. Gombok: Frissítés (újra lekéri az
időjárást), Felolvasás (hangosan kimondja), Bezárás.
"""

import wx

HELP = """NAPI INFÓ

MIRE VALÓ
A mai dátum, névnap és időjárás egy helyen, felolvasva.

LÉPÉSRŐL LÉPÉSRE (vakon is)
1. Az ablak megnyitásakor a szöveg (dátum, névnap, majd az időjárás is)
   megjelenik a „Napi infó” mezőben; a képernyőolvasóval nyilakkal bejárható.
2. „Frissítés” – újra lekéri az időjárást.
3. „Felolvasás” – hangosan kimondja az egészet.
4. „Bezárás” vagy Esc – kilép.

GYORSBILLENTYŰK
F1 – súgó.  Esc – bezárás.

TIPP
A várost a fő program beállításainál adhatod meg."""


class DayInfoDialog(wx.Dialog):
    def __init__(self, parent, compose_fn, fetch_weather_fn, speaker):
        super().__init__(parent, title="SuperDL – Napi infó", size=(560, 320))
        self._compose = compose_fn          # compose(weather_or_None) -> szöveg
        self._fetch = fetch_weather_fn      # fetch(on_done) háttérben
        self._speaker = speaker
        self._closing = False        # zárás alatt a háttér-callbackek kilépnek
        self._wgen = 0               # időjárás-kérés generációja (stale-védelem)

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="Mai &napi infó:"), 0, wx.ALL, 8)
        self.text = wx.TextCtrl(
            p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP)
        self.text.SetName("Napi infó szövege")
        v.Add(self.text, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        b_ref = wx.Button(p, label="&Frissítés")
        b_ref.Bind(wx.EVT_BUTTON, lambda e: self._refresh())
        self.b_speak = wx.Button(p, label="Fel&olvasás")
        self.b_speak.Bind(wx.EVT_BUTTON, lambda e: self._speak())
        self.b_speak.Enable(bool(getattr(speaker, "available", False)))
        b_close = wx.Button(p, wx.ID_CANCEL, "&Bezárás")
        row.Add(b_ref, 0, wx.RIGHT, 6)
        row.Add(self.b_speak, 0, wx.RIGHT, 6)
        row.Add(b_close, 0)
        v.Add(row, 0, wx.ALL, 8)
        p.SetSizer(v)

        self._last = ""
        # azonnal mutatjuk a dátum+névnap részt (időjárás nélkül), majd
        # a háttérből frissül az időjárással
        self._set_text(self._compose(None))
        self._refresh()
        self.text.SetFocus()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_help_key)
        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _on_close(self, e):
        self._closing = True     # a folyamatban lévő időjárás-válasz eldobandó
        e.Skip()

    def _on_help_key(self, e):
        if e.GetKeyCode() == wx.WXK_F1:
            try:
                from superdl.helpdialog import show_help
                show_help(self, "Napi infó", HELP)
            except Exception:
                wx.MessageBox(HELP, "Súgó – Napi infó",
                              wx.OK | wx.ICON_INFORMATION, self)
        else:
            e.Skip()

    def _set_text(self, txt):
        self._last = txt
        self.text.SetValue(txt)

    def _refresh(self):
        self._set_text(self._compose(None) + "\n\n(Időjárás frissítése…)")
        self._wgen += 1
        gen = self._wgen

        def done(w):
            # A puszta `if self:` NEM bizonyítja, hogy a natív ablak még él, és
            # generáció nélkül egy RÉGI, lassú válasz felülírhatta a frisset.
            # [Herman Tibi INFO-P0-01, INFO-P0-02]
            def apply():
                if self._closing or gen != self._wgen:
                    return
                self._set_text(self._compose(w))
            wx.CallAfter(apply)
        self._fetch(done)

    def _speak(self):
        if getattr(self._speaker, "available", False) and self._last:
            self._speaker.speak(self._last)
