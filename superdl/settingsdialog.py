"""Lapfüles (notebook) beállítás-ablak – akadálymentes, tematikus fülekkel.

A főablakból a „Beállítások…” gomb (Ctrl+,) nyitja meg. Csak a célmappa és a
„Csak hang” marad kint a főablakon; minden más ide, fülekre rendezve kerül,
hogy ne legyen zsúfolt és könnyű legyen képernyőolvasóval bejárni.
"""

import wx

AUDIO_FORMATS = ["MP3", "M4A", "OPUS", "FLAC", "WAV", "AAC"]
COOKIE_CHOICES = ["Nincs", "Chrome", "Firefox", "Edge", "Brave", "Opera",
                  "Vivaldi", "Chromium", "cookies.txt fájl…"]
VOICE_LABELS = [
    ("Automatikus (Edge magyar, tartalék rendszerhang)", "auto"),
    ("Edge magyar (online)", "edge"),
    ("Rendszerhang (offline)", "system")]
AI_PROVIDERS = [("OpenAI (GPT)", "openai"), ("Google Gemini", "gemini"),
                ("Anthropic (Claude)", "anthropic"), ("xAI (Grok)", "xai")]


class SettingsDialog(wx.Dialog):
    def __init__(self, parent, settings: dict, ai_config: dict):
        super().__init__(parent, title="SuperDL – Beállítások", size=(620, 560))
        self.s = dict(settings)
        self.ai = dict(ai_config)
        self.result_settings = None
        self.result_ai = None

        outer = wx.BoxSizer(wx.VERTICAL)
        self.nb = wx.Notebook(self)
        self.nb.AddPage(self._page_download(), "Letöltés")
        self.nb.AddPage(self._page_cookies(), "Fiók / Sütik")
        self.nb.AddPage(self._page_general(), "Általános")
        self.nb.AddPage(self._page_ai(), "AI")
        outer.Add(self.nb, 1, wx.EXPAND | wx.ALL, 8)

        btns = wx.StdDialogButtonSizer()
        ok = wx.Button(self, wx.ID_OK, "&Mentés")
        ok.SetDefault()
        btns.AddButton(ok)
        btns.AddButton(wx.Button(self, wx.ID_CANCEL, "Mé&gse"))
        btns.Realize()
        outer.Add(btns, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.SetSizer(outer)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

    # ---- segéd: címke + vezérlő egy sorban ----------------------------

    @staticmethod
    def _row(panel, sizer, label, ctrl, name=""):
        lbl = wx.StaticText(panel, label=label)
        if name:
            ctrl.SetName(name)
        elif label:
            ctrl.SetName(label.replace("&", "").rstrip(":"))
        r = wx.BoxSizer(wx.HORIZONTAL)
        r.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        r.Add(ctrl, 1, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(r, 0, wx.EXPAND | wx.ALL, 8)
        return ctrl

    # ---- Letöltés fül -------------------------------------------------

    def _page_download(self):
        p = wx.Panel(self.nb)
        v = wx.BoxSizer(wx.VERTICAL)
        self.c_conn = wx.SpinCtrl(p, min=1, max=32,
                                  initial=int(self.s.get("connections", 8)))
        self._row(p, v, "&Szálak (letöltésenként):", self.c_conn)
        self.c_par = wx.SpinCtrl(p, min=1, max=10,
                                 initial=int(self.s.get("parallel", 3)))
        self._row(p, v, "&Párhuzamos letöltés:", self.c_par)
        self.c_limit = wx.TextCtrl(p, value=str(self.s.get("limit", "")))
        self.c_limit.SetHint("pl. 2M vagy 500K – üresen nincs korlát")
        self._row(p, v, "Sebesség&korlát:", self.c_limit)
        self.c_fmt = wx.Choice(p, choices=AUDIO_FORMATS)
        if self.c_fmt.SetStringSelection(
                str(self.s.get("audio_format", "MP3"))) is False:
            self.c_fmt.SetSelection(0)
        self._row(p, v, "Hang&formátum (Csak hang módhoz):", self.c_fmt)
        self.c_seed = wx.TextCtrl(p, value=str(self.s.get("seed_ratio", "1.0")))
        self._row(p, v, "Seed-&arány (torrent):", self.c_seed,
                  name="Torrent megosztási arány")
        self.c_playlist = wx.CheckBox(p, label="Lejátszási &lista külön, "
                                      "sorszámozott mappába")
        self.c_playlist.SetValue(bool(self.s.get("playlist_folders", True)))
        v.Add(self.c_playlist, 0, wx.ALL, 10)
        p.SetSizer(v)
        return p

    # ---- Fiók / Sütik fül ---------------------------------------------

    def _page_cookies(self):
        p = wx.Panel(self.nb)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="Bejelentkezés sütikkel a fiókod mögötti "
              "(korhatáros, tagsági, régiózárt) tartalmakhoz. Jelszót a "
              "program nem tárol."), 0, wx.ALL, 8)
        self.c_cookies = wx.Choice(p, choices=COOKIE_CHOICES)
        if self.c_cookies.SetStringSelection(
                str(self.s.get("cookies", "Nincs"))) is False:
            self.c_cookies.SetSelection(0)
        self._row(p, v, "&Sütik forrása:", self.c_cookies)
        self.cookies_file = self.s.get("cookies_file", "") or ""
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.c_cookfile = wx.TextCtrl(p, value=self.cookies_file,
                                      style=wx.TE_READONLY)
        self.c_cookfile.SetName("Kiválasztott cookies.txt fájl")
        b = wx.Button(p, label="cookies.txt &kiválasztása…")
        b.Bind(wx.EVT_BUTTON, lambda e: self._pick_cookies())
        row.Add(self.c_cookfile, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        row.Add(b, 0)
        v.Add(row, 0, wx.EXPAND | wx.ALL, 8)
        p.SetSizer(v)
        return p

    def _pick_cookies(self):
        dlg = wx.FileDialog(
            self, "cookies.txt fájl kiválasztása",
            wildcard="cookies.txt (*.txt)|*.txt|Minden fájl|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.cookies_file = dlg.GetPath()
            self.c_cookfile.SetValue(self.cookies_file)
            self.c_cookies.SetStringSelection("cookies.txt fájl…")
        dlg.Destroy()

    # ---- Általános fül ------------------------------------------------

    def _page_general(self):
        p = wx.Panel(self.nb)
        v = wx.BoxSizer(wx.VERTICAL)
        self.c_clip = wx.CheckBox(p, label="&Vágólap figyelése "
                                  "(másolt hivatkozás automatikus letöltése)")
        self.c_clip.SetValue(bool(self.s.get("clipboard", False)))
        v.Add(self.c_clip, 0, wx.ALL, 10)
        self.c_notify = wx.CheckBox(p, label="&Rendszerértesítések "
                                    "(elkészült letöltésekről)")
        self.c_notify.SetValue(bool(self.s.get("notify", True)))
        v.Add(self.c_notify, 0, wx.ALL, 10)
        self.c_city = wx.TextCtrl(p, value=str(self.s.get("city", "Budapest")))
        self.c_city.SetHint("pl. Budapest")
        self._row(p, v, "Vá&ros (napi időjárás):", self.c_city)
        self.c_voice = wx.Choice(p, choices=[t for t, _ in VOICE_LABELS])
        mode = self.s.get("voice_mode", "auto")
        self.c_voice.SetSelection(
            next((i for i, (_, m) in enumerate(VOICE_LABELS) if m == mode), 0))
        self._row(p, v, "Beszéd&hang (üdvözlés, felolvasás):", self.c_voice)
        p.SetSizer(v)
        return p

    # ---- AI fül -------------------------------------------------------

    def _page_ai(self):
        p = wx.Panel(self.nb)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="AI-szolgáltatók API-kulcsai. A kulcsok a "
              "GÉPEDEN tárolódnak (~/.superdl/ai.json), és csak a választott "
              "szolgáltatóhoz kerülnek, amikor használod."), 0, wx.ALL, 8)
        b_help = wx.Button(p, label="&Hogyan szerzem be a kulcsokat?")
        b_help.Bind(wx.EVT_BUTTON, lambda e: self._keys_help())
        v.Add(b_help, 0, wx.LEFT | wx.BOTTOM, 8)
        self.ai_openai = wx.TextCtrl(p, value=self.ai.get("openai_key", ""))
        self._row(p, v, "&OpenAI (GPT) kulcs:", self.ai_openai)
        self.ai_gemini = wx.TextCtrl(p, value=self.ai.get("gemini_key", ""))
        self._row(p, v, "Google &Gemini kulcs:", self.ai_gemini)
        self.ai_anthropic = wx.TextCtrl(p, value=self.ai.get("anthropic_key", ""))
        self._row(p, v, "&Anthropic (Claude) kulcs:", self.ai_anthropic)
        self.ai_xai = wx.TextCtrl(p, value=self.ai.get("xai_key", ""))
        self._row(p, v, "&xAI (Grok) kulcs:", self.ai_xai)
        self.ai_provider = wx.Choice(p, choices=[t for t, _ in AI_PROVIDERS])
        prov = self.ai.get("provider", "openai")
        self.ai_provider.SetSelection(
            next((i for i, (_, k) in enumerate(AI_PROVIDERS) if k == prov), 0))
        self._row(p, v, "Alapértelmezett &szolgáltató:", self.ai_provider)
        self.ai_model = wx.TextCtrl(p, value=self.ai.get("model", ""))
        self.ai_model.SetHint("pl. gpt-4o / gemini-2.5-pro / claude-opus-4 …")
        self._row(p, v, "&Modell (opcionális):", self.ai_model)
        p.SetSizer(v)
        return p

    def _keys_help(self):
        from .aikeyshelp import AIKeysHelpDialog
        dlg = AIKeysHelpDialog(self)
        dlg.ShowModal()
        dlg.Destroy()

    # ---- mentés -------------------------------------------------------

    def _on_ok(self, evt):
        self.result_settings = {
            "connections": self.c_conn.GetValue(),
            "parallel": self.c_par.GetValue(),
            "limit": self.c_limit.GetValue().strip(),
            "audio_format": self.c_fmt.GetStringSelection() or "MP3",
            "seed_ratio": self.c_seed.GetValue().strip() or "1.0",
            "playlist_folders": self.c_playlist.GetValue(),
            "cookies": self.c_cookies.GetStringSelection() or "Nincs",
            "cookies_file": self.cookies_file or "",
            "clipboard": self.c_clip.GetValue(),
            "notify": self.c_notify.GetValue(),
            "city": self.c_city.GetValue().strip(),
            "voice_mode": VOICE_LABELS[self.c_voice.GetSelection()][1],
        }
        self.result_ai = {
            "openai_key": self.ai_openai.GetValue().strip(),
            "gemini_key": self.ai_gemini.GetValue().strip(),
            "anthropic_key": self.ai_anthropic.GetValue().strip(),
            "xai_key": self.ai_xai.GetValue().strip(),
            "provider": AI_PROVIDERS[self.ai_provider.GetSelection()][1],
            "model": self.ai_model.GetValue().strip(),
        }
        evt.Skip()       # ID_OK-kal zárja a párbeszédet
