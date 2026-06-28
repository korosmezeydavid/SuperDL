"""Super Stream – akadálymentes ablak az élő multistreamhez (FB/YouTube/TikTok).

A felhasználó megad: egy ÁLLÓKÉPET (a videó), egy HANGFORRÁST (mikrofon vagy
hangfájl) és egy vagy több ADÁSCÉLT (platform + szerver-URL + stream-kulcs).
Egy gombbal indul/áll az adás. A stream-kulcsot NEM jelenítjük meg és NEM
mentjük fájlba (biztonság).
"""

from pathlib import Path

import wx

from . import superstream as SS


class SuperStreamFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Super Stream (élő multistream)",
                         size=(780, 600))
        self.main = main
        self.targets: list[SS.Target] = []
        self.streamer = None
        self._build()
        self.CreateStatusBar()
        self.SetStatusText("Adj meg állóképet, hangforrást és legalább egy "
                           "adáscélt, majd Indítás.")
        self.Bind(wx.EVT_CLOSE, self._on_close)
        wx.CallAfter(self._load_mics)

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label=(
            "Élő adás egyszerre több platformra (YouTube, Facebook, TikTok…). "
            "A saját fiókod stream-kulcsát add meg. Csak legális tartalmat!")),
            0, wx.ALL, 10)

        # --- állókép ---
        ir = wx.BoxSizer(wx.HORIZONTAL)
        ir.Add(wx.StaticText(p, label="Á&llókép (a videó):"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.img_txt = wx.TextCtrl(p)
        self.img_txt.SetName("Állókép fájl")
        ib = wx.Button(p, label="&Tallózás…")
        ib.Bind(wx.EVT_BUTTON, lambda e: self._pick_image())
        ir.Add(self.img_txt, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        ir.Add(ib, 0)
        v.Add(ir, 0, wx.EXPAND | wx.ALL, 8)

        # --- hangforrás ---
        ar = wx.BoxSizer(wx.HORIZONTAL)
        ar.Add(wx.StaticText(p, label="&Hangforrás:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.audio_ch = wx.Choice(p, choices=["(mikrofonok keresése…)"])
        self.audio_ch.SetName("Hangforrás")
        self.audio_ch.SetSelection(0)
        refresh = wx.Button(p, label="Mikrofonok f&rissítése")
        refresh.Bind(wx.EVT_BUTTON, lambda e: self._load_mics())
        filebtn = wx.Button(p, label="Hang&fájl…")
        filebtn.Bind(wx.EVT_BUTTON, lambda e: self._pick_audio_file())
        ar.Add(self.audio_ch, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        ar.Add(refresh, 0, wx.RIGHT, 6)
        ar.Add(filebtn, 0)
        v.Add(ar, 0, wx.EXPAND | wx.ALL, 8)
        self._audio_file = ""

        # --- adáscél hozzáadása ---
        sb = wx.StaticBoxSizer(wx.StaticBox(p, label="Adáscél hozzáadása"),
                               wx.VERTICAL)
        g = wx.FlexGridSizer(0, 2, 4, 6)
        g.AddGrowableCol(1, 1)
        self.plat_ch = wx.Choice(p, choices=[n for n, _ in SS.PRESETS])
        self.plat_ch.SetName("Platform")
        self.plat_ch.SetSelection(0)
        self.plat_ch.Bind(wx.EVT_CHOICE, lambda e: self._preset_changed())
        self.srv_txt = wx.TextCtrl(p, value=SS.PRESETS[0][1])
        self.srv_txt.SetName("Szerver URL")
        self.key_txt = wx.TextCtrl(p, style=wx.TE_PASSWORD)
        self.key_txt.SetName("Stream kulcs")
        for lbl, ctl in (("&Platform:", self.plat_ch),
                         ("&Szerver-URL:", self.srv_txt),
                         ("Stream-&kulcs:", self.key_txt)):
            g.Add(wx.StaticText(p, label=lbl), 0, wx.ALIGN_CENTER_VERTICAL)
            g.Add(ctl, 1, wx.EXPAND)
        sb.Add(g, 0, wx.EXPAND | wx.ALL, 6)
        addb = wx.Button(p, label="Cél hozzá&adása a listához")
        addb.Bind(wx.EVT_BUTTON, lambda e: self._add_target())
        sb.Add(addb, 0, wx.ALL, 6)
        v.Add(sb, 0, wx.EXPAND | wx.ALL, 8)

        # --- célok listája ---
        self.list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.list.SetName("Adáscélok listája")
        self.list.InsertColumn(0, "Platform", width=200)
        self.list.InsertColumn(1, "Szerver", width=420)
        self.list.Bind(wx.EVT_KEY_DOWN, self._on_list_key)
        v.Add(self.list, 1, wx.EXPAND | wx.ALL, 8)
        delb = wx.Button(p, label="Kijelölt cél &eltávolítása")
        delb.Bind(wx.EVT_BUTTON, lambda e: self._remove_target())
        v.Add(delb, 0, wx.LEFT | wx.BOTTOM, 8)

        # --- indítás ---
        self.go_btn = wx.Button(p, label="Élő adás &indítása")
        self.go_btn.Bind(wx.EVT_BUTTON, lambda e: self._toggle())
        v.Add(self.go_btn, 0, wx.ALL, 10)

        p.SetSizer(v)

    # ---- segédek ------------------------------------------------------

    def _announce(self, text):
        self.SetStatusText(text)
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            try:
                sv.speak(text, force=True)
            except Exception:
                pass

    def _preset_changed(self):
        i = self.plat_ch.GetSelection()
        if 0 <= i < len(SS.PRESETS):
            self.srv_txt.SetValue(SS.PRESETS[i][1])

    def _pick_image(self):
        dlg = wx.FileDialog(self, "Állókép kiválasztása", wildcard=(
            "Képek|*.png;*.jpg;*.jpeg;*.bmp|Minden fájl|*.*"),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.img_txt.SetValue(dlg.GetPath())
        dlg.Destroy()

    def _pick_audio_file(self):
        dlg = wx.FileDialog(self, "Hangfájl kiválasztása", wildcard=(
            "Hang/videó|*.mp3;*.wav;*.m4a;*.aac;*.flac;*.ogg;*.mp4|"
            "Minden fájl|*.*"),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self._audio_file = dlg.GetPath()
            n = self.audio_ch.Append(f"Hangfájl: {Path(self._audio_file).name}")
            self.audio_ch.SetSelection(n)
            self._announce(f"Hangfájl kiválasztva: {Path(self._audio_file).name}")
        dlg.Destroy()

    def _load_mics(self):
        self._announce("Mikrofonok keresése…")

        def work():
            mics = SS.list_audio_devices()
            wx.CallAfter(self._fill_mics, mics)
        import threading
        threading.Thread(target=work, daemon=True).start()

    def _fill_mics(self, mics):
        self._mics = mics
        self.audio_ch.Clear()
        for m in mics:
            self.audio_ch.Append(f"Mikrofon: {m}")
        if self._audio_file:
            self.audio_ch.Append(f"Hangfájl: {Path(self._audio_file).name}")
        if self.audio_ch.GetCount():
            self.audio_ch.SetSelection(0)
            self._announce(f"{len(mics)} mikrofon található. Választhatsz "
                           "hangfájlt is.")
        else:
            self.audio_ch.Append("(nincs mikrofon – válassz hangfájlt)")
            self.audio_ch.SetSelection(0)
            self._announce("Nem találtam mikrofont. Válassz hangfájlt a "
                           "Hangfájl gombbal.")

    def _audio_source(self):
        sel = self.audio_ch.GetStringSelection()
        if sel.startswith("Hangfájl:") and self._audio_file:
            return ("file", self._audio_file)
        if sel.startswith("Mikrofon:"):
            return ("dshow", sel[len("Mikrofon: "):])
        return None

    # ---- célok --------------------------------------------------------

    def _add_target(self):
        i = self.plat_ch.GetSelection()
        name = SS.PRESETS[i][0] if 0 <= i < len(SS.PRESETS) else "RTMP"
        srv = self.srv_txt.GetValue().strip()
        key = self.key_txt.GetValue().strip()
        if not srv:
            self._announce("Adj meg egy szerver-URL-t.")
            return
        url = srv + key
        if not url.lower().startswith(("rtmp://", "rtmps://")):
            self._announce("A szerver-URL-nek rtmp:// vagy rtmps://-sel kell "
                           "kezdődnie.")
            return
        self.targets.append(SS.Target(name, url))
        row = self.list.InsertItem(self.list.GetItemCount(), name)
        self.list.SetItem(row, 1, srv)        # a kulcsot NEM mutatjuk
        self.key_txt.SetValue("")
        self._announce(f"Hozzáadva: {name}. Összesen {len(self.targets)} cél.")

    def _on_list_key(self, e):
        if e.GetKeyCode() == wx.WXK_DELETE:
            self._remove_target()
        else:
            e.Skip()

    def _remove_target(self):
        i = self.list.GetFirstSelected()
        if 0 <= i < len(self.targets):
            t = self.targets.pop(i)
            self.list.DeleteItem(i)
            self._announce(f"Eltávolítva: {t.name}.")

    # ---- indítás/leállítás --------------------------------------------

    def _toggle(self):
        if self.streamer and self.streamer.is_running():
            self.streamer.stop()
            self._announce("Az adás leállítása…")
            return
        image = self.img_txt.GetValue().strip()
        if not image or not Path(image).is_file():
            self._announce("Válassz egy létező állóképet.")
            return
        audio = self._audio_source()
        if not audio:
            self._announce("Válassz hangforrást (mikrofon vagy hangfájl).")
            return
        if not self.targets:
            self._announce("Adj meg legalább egy adáscélt.")
            return
        self.go_btn.SetLabel("Élő adás &leállítása")
        self._announce(f"Adás indítása {len(self.targets)} platformra…")
        self.streamer = SS.Streamer(
            image, audio, self.targets,
            on_status=lambda m: wx.CallAfter(self._announce, m),
            on_done=lambda ok, m: wx.CallAfter(self._done, ok, m))
        self.streamer.start()

    def _done(self, ok, msg):
        self.go_btn.SetLabel("Élő adás &indítása")
        self._announce(msg)

    def _on_close(self, e):
        if self.streamer and self.streamer.is_running():
            self.streamer.stop()
        if getattr(self.main, "_superstream_win", None) is self:
            self.main._superstream_win = None
        self.Destroy()
