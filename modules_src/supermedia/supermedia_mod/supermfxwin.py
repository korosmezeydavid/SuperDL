"""Super M – akadálymentes EFFEKT-RACK dialógus (MK-A).

Pipálható effektek (visszhang, echo, torzítás, kórus, flanger, kompresszor,
gargle), amik VALÓS IDŐBEN rákerülnek a most szóló zenére. A `channel_provider`
mindig az AKTUÁLIS deck csatorna-handle-jét adja (a deck-váltást is követjük).
"""

import wx

from . import superm_fx as FX


class EffectRackDialog(wx.Dialog):
    def __init__(self, parent, channel_provider, announce=None):
        super().__init__(parent, title="Super M – Effektek (rack)",
                         size=(440, 440))
        self._chan = channel_provider
        self._say = announce or (lambda t: None)
        self.rack = FX.EffectRack(self._chan() or 0)
        self._checks = {}

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label=(
            "Valós idejű effektek a most szóló zenére. Pipáld be, amit hallani "
            "szeretnél – azonnal hallatszik, és bármikor kikapcsolható.")),
            0, wx.ALL, 10)
        for name, t in FX.EFFECTS:
            cb = wx.CheckBox(p, label=name)
            cb.SetName(name)
            cb.Bind(wx.EVT_CHECKBOX,
                    lambda e, ty=t, nm=name: self._toggle(ty, nm, e.IsChecked()))
            v.Add(cb, 0, wx.ALL, 6)
            self._checks[t] = cb
        row = wx.BoxSizer(wx.HORIZONTAL)
        alloff = wx.Button(p, label="Mind &ki")
        alloff.Bind(wx.EVT_BUTTON, lambda e: self._all_off())
        close = wx.Button(p, label="Be&zárás")
        close.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        row.Add(alloff, 0, wx.RIGHT, 6)
        row.Add(close, 0)
        v.Add(row, 0, wx.ALL, 10)
        p.SetSizer(v)

    def _retarget(self):
        ch = self._chan() or 0
        if ch != self.rack.channel:
            self.rack.set_channel(ch)        # deck-váltás → effektek átvitele

    def _toggle(self, t, name, checked):
        self._retarget()
        if not self.rack.channel:
            self._say("Most nem szól zene, amire effektet tehetnék.")
            self._checks[t].SetValue(False)
            return
        okk = self.rack.set(t, checked)
        if checked and not okk:
            self._checks[t].SetValue(False)
            self._say(f"{name}: nem sikerült bekapcsolni.")
        else:
            self._say(f"{name}: {'be' if checked else 'ki'}.")

    def _all_off(self):
        self.rack.clear()
        for cb in self._checks.values():
            cb.SetValue(False)
        self._say("Minden effekt kikapcsolva.")
