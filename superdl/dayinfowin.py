"""„Napi infó" párbeszéd (Ctrl+Shift+W): mai dátum, névnap és időjárás.

Akadálymentes: a szöveg egy csak olvasható, többsoros mezőben jelenik meg,
amelyet a képernyőolvasó nyilakkal bejár. Gombok: Frissítés (újra lekéri az
időjárást), Felolvasás (hangosan kimondja), Bezárás.
"""

import wx


class DayInfoDialog(wx.Dialog):
    def __init__(self, parent, compose_fn, fetch_weather_fn, speaker):
        super().__init__(parent, title="SuperDL – Napi infó", size=(560, 320))
        self._compose = compose_fn          # compose(weather_or_None) -> szöveg
        self._fetch = fetch_weather_fn      # fetch(on_done) háttérben
        self._speaker = speaker

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

    def _set_text(self, txt):
        self._last = txt
        self.text.SetValue(txt)

    def _refresh(self):
        self._set_text(self._compose(None) + "\n\n(Időjárás frissítése…)")

        def done(w):
            if self:                      # az ablak még él
                self._set_text(self._compose(w))
        self._fetch(done)

    def _speak(self):
        if getattr(self._speaker, "available", False) and self._last:
            self._speaker.speak(self._last)
