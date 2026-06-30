"""Super Recorder – valós idejű voice changer ablak (akadálymentes).

Élő mikrofon-átalakítás: hangmagasság-csúszka + DX8-effekt-pipák, monitor a
kimeneten. Menüsorral és biztonságos gyorsbillentyűkkel (a JAWS-tanulság szerint
NINCS sima-billentyűs accelerator); minden címkézett, billentyűzetes, kimondott.
"""

import wx

from . import supervoicechanger as VC


class VoiceChangerFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Valós idejű voice changer",
                         size=(640, 520))
        self.main = main
        self.vc: VC.VoiceChanger | None = None

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        if not VC.available():
            v.Add(wx.StaticText(p, label="A valós idejű voice changerhez a BASS "
                  "hangmotor (és a bass_fx.dll) szükséges, ami ennél a verziónál "
                  "nem érhető el. Frissíts a legújabb SuperDL-re."),
                  0, wx.ALL, 12)
            p.SetSizer(v)
            return

        # eszközök
        d = wx.FlexGridSizer(2, 2, 6, 8)
        d.Add(wx.StaticText(p, label="&Mikrofon (bemenet):"), 0,
              wx.ALIGN_CENTER_VERTICAL)
        self._ins = VC.input_devices()
        self.in_ch = wx.Choice(p, choices=[n for _i, n in self._ins]
                               or ["Alapértelmezett mikrofon"])
        self.in_ch.SetSelection(0)
        self.in_ch.SetName("Bemeneti mikrofon")
        d.Add(self.in_ch, 1, wx.EXPAND)
        d.Add(wx.StaticText(p, label="&Kimenet (monitor):"), 0,
              wx.ALIGN_CENTER_VERTICAL)
        self._outs = VC.output_devices()
        self.out_ch = wx.Choice(p, choices=["Alapértelmezett kimenet"]
                                + [n for _i, n in self._outs])
        self.out_ch.SetSelection(0)
        self.out_ch.SetName("Kimeneti (monitor) eszköz")
        d.Add(self.out_ch, 1, wx.EXPAND)
        d.AddGrowableCol(1, 1)
        v.Add(d, 0, wx.EXPAND | wx.ALL, 10)

        # indítás
        self.btn = wx.Button(p, label="&Indítás")
        self.btn.Bind(wx.EVT_BUTTON, lambda e: self._toggle())
        v.Add(self.btn, 0, wx.LEFT | wx.BOTTOM, 10)

        # hangmagasság
        ph = wx.BoxSizer(wx.HORIZONTAL)
        ph.Add(wx.StaticText(p, label="&Hangmagasság (félhang, −12…+12):"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.pitch = wx.SpinCtrl(p, min=-12, max=12, initial=0)
        self.pitch.SetName("Hangmagasság félhangban, mínusz tizenkettőtől plusz "
                           "tizenkettőig")
        self.pitch.Bind(wx.EVT_SPINCTRL, lambda e: self._on_pitch())
        ph.Add(self.pitch, 0)
        v.Add(ph, 0, wx.LEFT | wx.BOTTOM, 10)

        # effektek (DX8) – pipák
        box = wx.StaticBoxSizer(wx.VERTICAL, p, "Élő effektek")
        sb = box.GetStaticBox()
        self.fx_chk = {}
        for name, dx8 in VC.EFFECTS:
            c = wx.CheckBox(sb, label=name)
            c.SetName(f"{name} effekt be/ki")
            c.Bind(wx.EVT_CHECKBOX, lambda e, t=dx8: self._on_fx(t))
            box.Add(c, 0, wx.ALL, 4)
            self.fx_chk[dx8] = c
        v.Add(box, 0, wx.EXPAND | wx.ALL, 10)

        p.SetSizer(v)
        self.CreateStatusBar()
        self.SetStatusText("Válassz mikrofont, és nyomd meg az Indítást. "
                           "Fejhallgatót használj, hogy ne legyen visszhang!")
        self._build_menubar()
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.in_ch.SetFocus()
        self._enable_fx(False)

    # ---- menüsor (akadálymentes) -------------------------------------

    def _build_menubar(self):
        mb = wx.MenuBar()
        m = wx.Menu()
        it1 = m.Append(wx.ID_ANY, "&Indítás / leállítás\tF5")
        self.Bind(wx.EVT_MENU, lambda e: self._toggle(), it1)
        it2 = m.Append(wx.ID_ANY, "Hangmagasság &nullázása\tF8")
        self.Bind(wx.EVT_MENU, lambda e: (self.pitch.SetValue(0), self._on_pitch()), it2)
        mb.Append(m, "&Voice changer")
        self.SetMenuBar(mb)

    # ---- segéd -------------------------------------------------------

    def _announce(self, text):
        self.SetStatusText(text)
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            try:
                sv.speak(text, force=True)
            except Exception:
                pass

    def _in_dev(self):
        i = self.in_ch.GetSelection()
        return self._ins[i][0] if 0 <= i < len(self._ins) else -1

    def _out_dev(self):
        i = self.out_ch.GetSelection()      # 0 = alapértelmezett (-1)
        if i > 0 and (i - 1) < len(self._outs):
            return self._outs[i - 1][0]
        return -1

    def _enable_fx(self, on):
        self.pitch.Enable(on)
        for c in self.fx_chk.values():
            c.Enable(on)

    # ---- vezérlés ----------------------------------------------------

    def _toggle(self):
        if self.vc and self.vc.running:
            self.vc.stop()
            self.btn.SetLabel("&Indítás")
            self.in_ch.Enable(True)
            self.out_ch.Enable(True)
            self._enable_fx(False)
            self._announce("Voice changer leállítva.")
            return
        try:
            self.vc = VC.VoiceChanger(self._in_dev(), self._out_dev())
            self.vc.set_pitch(self.pitch.GetValue())
            self.vc.start()
        except Exception as ex:
            self._announce(f"Nem indult: {ex}")
            wx.MessageBox(f"A voice changer nem indult el:\n\n{ex}",
                          "Voice changer", wx.OK | wx.ICON_ERROR, self)
            self.vc = None
            return
        self.btn.SetLabel("&Leállítás")
        self.in_ch.Enable(False)
        self.out_ch.Enable(False)
        self._enable_fx(True)
        # az aktuális effekt-pipák alkalmazása
        for dx8, c in self.fx_chk.items():
            if c.GetValue():
                self.vc.set_effect(dx8, True)
        self._announce("Voice changer elindult. Beszélj a mikrofonba.")

    def _on_pitch(self):
        if self.vc and self.vc.running:
            self.vc.set_pitch(self.pitch.GetValue())
        self._announce(f"Hangmagasság: {self.pitch.GetValue():+d} félhang.")

    def _on_fx(self, dx8):
        if not (self.vc and self.vc.running):
            return
        want = self.fx_chk[dx8].GetValue()
        ok = self.vc.set_effect(dx8, want)
        if not ok and want:
            self.fx_chk[dx8].SetValue(False)
            self._announce("Ez az effekt most nem alkalmazható.")

    def _on_close(self, e):
        try:
            if self.vc:
                self.vc.stop()
        except Exception:
            pass
        if getattr(self.main, "_voicechanger_win", None) is self:
            self.main._voicechanger_win = None
        e.Skip()
