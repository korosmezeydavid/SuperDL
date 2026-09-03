"""Lapfüles (notebook) beállítás-ablak – akadálymentes, tematikus fülekkel.

A főablakból a „Beállítások…” gomb (Ctrl+,) nyitja meg. Csak a célmappa és a
„Csak hang” marad kint a főablakon; minden más ide, fülekre rendezve kerül,
hogy ne legyen zsúfolt és könnyű legyen képernyőolvasóval bejárni.
"""

import wx

AUDIO_FORMATS = ["MP3", "M4A", "OPUS", "FLAC", "WAV", "AAC"]
VIDEO_FORMATS = ["MP4", "MKV", "WEBM"]
AUDIO_BITRATES = ["128", "192", "256", "320"]
SAMPLERATES = [("Eredeti", ""), ("44100 Hz", "44100"), ("48000 Hz", "48000")]
# Rádiófelvétel: formátum (címke, tárolt kulcs) és választható bitráták
RADIO_REC_FORMATS = [("MP3 (univerzális)", "mp3"),
                     ("Opus, OGG (kisebb fájl, jobb minőség)", "opus")]
RADIO_REC_BITRATES = ["64", "96", "128", "160", "192", "256", "320"]
COOKIE_CHOICES = ["Nincs", "Chrome", "Firefox", "Edge", "Brave", "Opera",
                  "Vivaldi", "Chromium", "cookies.txt fájl…"]
VOICE_LABELS = [
    ("Automatikus (Edge magyar, tartalék rendszerhang)", "auto"),
    ("Edge magyar (online)", "edge"),
    ("Rendszerhang (offline)", "system")]
AI_PROVIDERS = [("OpenAI (GPT)", "openai"), ("Google Gemini", "gemini"),
                ("Anthropic (Claude)", "anthropic"), ("xAI (Grok)", "xai")]


class _NamedAccessible(wx.Accessible):
    """A vezérlő akadálymentességi NEVÉT KÖZVETLENÜL adja meg (a képernyőolvasó
    ezt olvassa) – függetlenül a natív „előtte álló StaticText a név" heurisztikától
    és a Z-sorrendtől. Csak a nevet írja felül; a szerep/érték/állapot a natív
    vezérlőé marad (a többi metódus alapból ACC_NOT_IMPLEMENTED-et ad vissza).
    Ez javítja a fülek eggyel-elcsúszott címkéit (az első mező névtelen volt, a
    többi az ELŐZŐ mező címkéjét mondta be)."""

    def __init__(self, name: str):
        super().__init__()
        self._name = name

    def GetName(self, childId):
        return (wx.ACC_OK, self._name)


class SettingsDialog(wx.Dialog):
    def __init__(self, parent, settings: dict, ai_config: dict):
        super().__init__(parent, title="SuperDL – Beállítások", size=(620, 560))
        self.s = dict(settings)
        self.ai = dict(ai_config)
        self.result_settings = None
        self.result_ai = None
        self._accessibles = []      # GC-védelem: a C++ oldal használja a nevet adó
                                    # wx.Accessible objektumokat, tartsuk életben

        outer = wx.BoxSizer(wx.VERTICAL)
        self.nb = wx.Notebook(self)
        self.nb.AddPage(self._page_download(), "Letöltés")
        self.nb.AddPage(self._page_radiorec(), "Rádió felvétel")
        self.nb.AddPage(self._page_cookies(), "Fiók / Sütik")
        self.nb.AddPage(self._page_general(), "Általános")
        self.nb.AddPage(self._page_sound(), "Hangjelzések / Beszéd")
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
        from superdl.uihelp import bind_help
        bind_help(self, "Súgó – Beállítások",
                  "BEÁLLÍTÁSOK\n\nA program testreszabása lapfülekre rendezve "
                  "(célmappa, hang, felolvasás, hálózat, biztonság stb.).\n"
                  "• Ctrl+Tab: váltás a lapok között.\n"
                  "• Tab / nyilak: mozgás a beállítások között; a "
                  "jelölőnégyzeteket Szóközzel kapcsolod.\n"
                  "• OK: mentés; Mégse: elvetés.\n\n"
                  "A saját hang (SelfVoice) itt kapcsolható be azoknak, akik "
                  "nem futtatnak képernyőolvasót.")
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

    # ---- segéd: címke + vezérlő egy sorban ----------------------------

    def _row(self, panel, sizer, label, ctrl, name=""):
        lbl = wx.StaticText(panel, label=label)
        # a vezérlő címkéje (& és záró kettőspont nélkül)
        acc_name = name or (label.replace("&", "").rstrip(":") if label else "")
        if acc_name:
            ctrl.SetName(acc_name)
            # A GOND: a címke a vezérlő UTÁN jön létre, ezért a natív „a Z-sorrendben
            # előtte álló StaticText a név" heurisztika EGGYEL ELCSÚSZIK – az első
            # mező névtelen, a többi az ELŐZŐ mező címkéjét mondja (Dorina + a fülek
            # elcsúszott címkéi). MEGOLDÁS: a nevet közvetlenül, wx.Accessible-lel
            # adjuk meg – ez Z-sorrendtől függetlenül a HELYES nevet olvastatja fel.
            try:
                acc = _NamedAccessible(acc_name)
                ctrl.SetAccessible(acc)
                self._accessibles.append(acc)      # ne GC-zze el a Python
            except Exception:
                pass
            # tartaléknak a tab-/Z-sorrendet is a címke elé rendezzük
            try:
                lbl.MoveBeforeInTabOrder(ctrl)
            except Exception:
                pass
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
        self.c_vfmt = wx.Choice(p, choices=VIDEO_FORMATS)
        if self.c_vfmt.SetStringSelection(
                str(self.s.get("video_format", "MP4")).upper()) is False:
            self.c_vfmt.SetSelection(0)
        self._row(p, v, "&Videóformátum (letöltött videóhoz):", self.c_vfmt)
        self.c_fmt = wx.Choice(p, choices=AUDIO_FORMATS)
        if self.c_fmt.SetStringSelection(
                str(self.s.get("audio_format", "MP3"))) is False:
            self.c_fmt.SetSelection(0)
        self._row(p, v, "Hang&formátum (Csak hang módhoz):", self.c_fmt)
        self.c_abr = wx.Choice(p, choices=AUDIO_BITRATES)
        if self.c_abr.SetStringSelection(
                str(self.s.get("audio_bitrate", "192"))) is False:
            self.c_abr.SetStringSelection("192")
        self._row(p, v, "Hang-&bitráta (kbps):", self.c_abr)
        self.c_asr = wx.Choice(p, choices=[t for t, _ in SAMPLERATES])
        cur_sr = str(self.s.get("audio_samplerate", ""))
        self.c_asr.SetSelection(
            next((i for i, (_, val) in enumerate(SAMPLERATES) if val == cur_sr),
                 0))
        self._row(p, v, "&Mintavétel (kHz):", self.c_asr)
        self.c_seedfor = wx.CheckBox(
            p, label="A kész torrent &kézi leállításig ossza meg "
                     "(ilyenkor a seed-arány nem számít)")
        self.c_seedfor.SetValue(bool(self.s.get("seed_forever", True)))
        v.Add(self.c_seedfor, 0, wx.ALL, 10)
        self.c_seed = wx.TextCtrl(p, value=str(self.s.get("seed_ratio", "1.0")))
        self._row(p, v, "Seed-&arány (torrent):", self.c_seed,
                  name="Torrent megosztási arány")
        self.c_uplimit = wx.TextCtrl(p, value=str(self.s.get("upload_limit", "")))
        self._row(p, v, "&Feltöltési sávkorlát (pl. 500K, 2M; üres = nincs):",
                  self.c_uplimit, name="Feltöltési sávkorlát")
        self.c_hely = wx.CheckBox(
            p, label="Szabad &hely ellenőrzése a letöltés indítása előtt")
        self.c_hely.SetValue(bool(self.s.get("hely_ellenorzes", True)))
        self.c_hely.SetToolTip(
            "Ha nincs elég hely, a letöltés el sem indul, és a program "
            "megmondja, mennyi hiányzik. Hálózati vagy virtuális meghajtón "
            "előfordul, hogy a szabad hely rosszul látszik – akkor kapcsold ki.")
        v.Add(self.c_hely, 0, wx.ALL, 10)
        # MK9: időzített sebességkorlát
        self.c_savrend = wx.TextCtrl(
            p, value=str(self.s.get("savszelesseg_rend", "")))
        self._row(p, v, "&Időzített sebességkorlát (pl. 22:00-06:00=0; "
                        "06:00-22:00=500K):", self.c_savrend,
                  name="Időzített sebességkorlát")
        self.c_savrend.SetToolTip(
            "Pontosvesszővel elválasztott szabályok. A 0 korlátlant jelent. "
            "Az éjfélen átnyúló sáv (22:00-06:00) az éjszakát jelenti. "
            "Üresen hagyva nincs időzítés, csak a fenti állandó korlát.")
        # MK10
        self.c_dup = wx.CheckBox(
            p, label="&Kérdezzen rá, ha ezt már letöltöttem egyszer")
        self.c_dup.SetValue(bool(self.s.get("duplikatum_kerdes", True)))
        self.c_dup.SetToolTip(
            "A mappában nem látszik, hogy a fájl már ott van, a névütközés "
            "pedig csak a letöltés végén derülne ki – addigra elment a "
            "sávszélesség és az idő.")
        v.Add(self.c_dup, 0, wx.ALL, 10)
        self.c_rendez = wx.CheckBox(
            p, label="Kész letöltés &rendezése típus szerinti almappába "
                     "(Videók, Zene, Képek, Dokumentumok, Csomagok)")
        self.c_rendez.SetValue(bool(self.s.get("auto_rendezes", False)))
        self.c_rendez.SetToolTip(
            "A program a kész fájlt a célmappán BELÜL rakja almappába, és "
            "kimondja, hova. Meglévő fájlt soha nem ír felül. Alapból ki van "
            "kapcsolva: a fájlmozgatás nem vonható vissza.")
        v.Add(self.c_rendez, 0, wx.ALL, 10)
        self.c_playlist = wx.CheckBox(p, label="Lejátszási &lista külön, "
                                      "sorszámozott mappába")
        self.c_playlist.SetValue(bool(self.s.get("playlist_folders", True)))
        v.Add(self.c_playlist, 0, wx.ALL, 10)
        p.SetSizer(v)
        return p

    # ---- Rádió felvétel fül -------------------------------------------

    def _page_radiorec(self):
        p = wx.Panel(self.nb)
        v = wx.BoxSizer(wx.VERTICAL)
        rr = self.s.get("radiorec", {}) or {}
        v.Add(wx.StaticText(p, label="A rádiófelvételek formátuma, minősége és "
                            "darabolása. A hosszú adást egyben vagy percenkénti "
                            "darabokban is rögzítheted."), 0, wx.ALL, 8)

        self.c_rrfmt = wx.Choice(p, choices=[t for t, _ in RADIO_REC_FORMATS])
        cur_fmt = str(rr.get("format", "mp3")).lower()
        self.c_rrfmt.SetSelection(next(
            (i for i, (_, val) in enumerate(RADIO_REC_FORMATS)
             if val == cur_fmt), 0))
        self._row(p, v, "&Formátum:", self.c_rrfmt)

        self.c_rrbr = wx.Choice(p, choices=RADIO_REC_BITRATES)
        if self.c_rrbr.SetStringSelection(
                str(rr.get("bitrate_kbps", 192))) is False:
            self.c_rrbr.SetStringSelection("192")
        self._row(p, v, "&Bitráta (kbps – nagyobb = jobb minőség):", self.c_rrbr)

        self.c_rrsr = wx.Choice(p, choices=[t for t, _ in SAMPLERATES])
        cur_sr = str(rr.get("sample_rate", "") or "")
        self.c_rrsr.SetSelection(next(
            (i for i, (_, val) in enumerate(SAMPLERATES) if val == cur_sr), 0))
        self._row(p, v, "&Mintavétel:", self.c_rrsr)

        self.c_rrsplit = wx.RadioBox(
            p, label="Felvétel módja",
            choices=["Egyben – egyetlen fájl (akár 6 óra is)",
                     "Darabolva – percenkénti fájlok"],
            majorDimension=1, style=wx.RA_SPECIFY_COLS)
        self.c_rrsplit.SetName("Felvétel módja")
        self.c_rrsplit.SetSelection(
            1 if int(rr.get("chunk_minutes", 0) or 0) > 0 else 0)
        self.c_rrsplit.Bind(wx.EVT_RADIOBOX, lambda e: self._rr_split_toggle())
        v.Add(self.c_rrsplit, 0, wx.EXPAND | wx.ALL, 8)

        init_min = int(rr.get("chunk_minutes", 0) or 0)
        self.c_rrmin = wx.SpinCtrl(p, min=1, max=360,
                                   initial=init_min if init_min >= 1 else 30)
        self._row(p, v, "Egy &darab hossza (perc):", self.c_rrmin)
        self._rr_split_toggle()
        p.SetSizer(v)
        return p

    def _rr_split_toggle(self):
        self.c_rrmin.Enable(self.c_rrsplit.GetSelection() == 1)

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
            path = dlg.GetPath()
            # azonnali visszajelzés: használható-e a fájl? (a tényleges
            # letöltés is így ellenőrzi majd)
            from .cookies import prepare_cookiefile, CookieFileError
            try:
                prepare_cookiefile(path)
            except CookieFileError as e:
                wx.MessageBox(
                    f"{e}\n\nVálassz másik, helyes cookies.txt fájlt.",
                    "A süti-fájl nem használható",
                    wx.OK | wx.ICON_WARNING, self)
                dlg.Destroy()
                return
            self.cookies_file = path
            self.c_cookfile.SetValue(self.cookies_file)
            self.c_cookies.SetStringSelection("cookies.txt fájl…")
            wx.MessageBox(
                "A cookies.txt fájl rendben, elmentve. A Sütik forrása "
                "automatikusan „cookies.txt fájl…”-ra állt.",
                "Süti-fájl elfogadva", wx.OK | wx.ICON_INFORMATION, self)
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
        # FEJLESZTŐI kapcsoló (alapból KI): csak bekapcsolva érvényesül a
        # frissítési forrás átállítása (repo.txt / SUPERDL_REPO). Kikapcsolva a
        # program KIZÁRÓLAG a hivatalos helyről frissül – egy odacsempészett
        # repo.txt így nem térítheti el (biztonsági audit-javaslat).
        self.c_devrepo = wx.CheckBox(
            p, label="Fe&jlesztői mód: egyéni frissítési forrás engedélyezése "
                     "(repo.txt) – csak ha tudod, mit csinálsz!")
        self.c_devrepo.SetName(
            "Fejlesztői mód: egyéni frissítési forrás engedélyezése. "
            "Kikapcsolva a program kizárólag a hivatalos helyről frissül. "
            "Csak akkor kapcsold be, ha tudod, mit csinálsz.")
        self.c_devrepo.SetValue(bool(self.s.get("dev_custom_repo", False)))
        v.Add(self.c_devrepo, 0, wx.ALL, 10)
        p.SetSizer(v)
        return p

    # ---- Hangjelzések / Beszéd fül ------------------------------------

    def _page_sound(self):
        from .selfvoice import SelfVoice, ESPEAK_VOICES, espeak_available
        p = wx.Panel(self.nb)
        v = wx.BoxSizer(wx.VERTICAL)

        # legfelül, a legfontosabb: csak a képernyőolvasó beszéljen
        v.Add(wx.StaticText(p, label="KÉPERNYŐOLVASÓ-MÓD – ha képernyőolvasót "
              "(NVDA, JAWS) használsz, ez minden EGYÉB program-beszédet elnémít, "
              "hogy semmi ne beszéljen bele."), 0, wx.LEFT | wx.TOP, 10)
        self.c_sronly = wx.CheckBox(
            p, label="&Csak a képernyőolvasó beszéljen "
                     "(a program saját hangja és minden gépi felolvasás kikapcsol)")
        self.c_sronly.SetName("Csak a képernyőolvasó beszéljen; a program saját "
                              "hangja és minden gépi felolvasás elnémul, a "
                              "visszajelzéseket a képernyőolvasó mondja")
        self.c_sronly.SetValue(bool(self.s.get("screenreader_only", False)))
        v.Add(self.c_sronly, 0, wx.ALL, 8)
        v.Add(wx.StaticLine(p), 0, wx.EXPAND | wx.ALL, 8)

        v.Add(wx.StaticText(p, label="SZÁZALÉK-PITTYEGÉS – hosszú "
              "műveleteknél (letöltés, konvertálás, renderelés…)"), 0,
              wx.LEFT | wx.TOP, 10)
        self.c_beep = wx.CheckBox(
            p, label="&Pittyegés bekapcsolva (minden 2%-nál egyre magasabb hang)")
        self.c_beep.SetValue(bool(self.s.get("beep_enabled", True)))
        v.Add(self.c_beep, 0, wx.ALL, 8)
        self.c_beepvol = wx.SpinCtrl(p, min=0, max=100,
                                     initial=int(self.s.get("beep_volume", 30)))
        self.c_beepvol.SetName("Pittyegés hangereje")
        self._row(p, v, "Pittyegés &hangereje (0–100):", self.c_beepvol)

        v.Add(wx.StaticLine(p), 0, wx.EXPAND | wx.ALL, 8)
        v.Add(wx.StaticText(p, label="MŰVELET-BEJELENTÉSEK saját hanggal – "
              "kiegészíti a képernyőolvasót (nem helyettesíti). A program "
              "bemondja a műveletek kezdetét/végét."), 0, wx.LEFT, 10)
        self.c_sv = wx.CheckBox(
            p, label="Művelet-be&jelentések bekapcsolva")
        self.c_sv.SetValue(bool(self.s.get("selfvoice_enabled", False)))
        v.Add(self.c_sv, 0, wx.ALL, 8)

        self.c_sv_off = wx.CheckBox(
            p, label="&Teljes némítás: a program semmit ne mondjon ki "
                     "(a bejelentkező üdvözlést se)")
        self.c_sv_off.SetName("Teljes némítás – a program egyetlen szöveget se "
                              "mondjon ki, az induló üdvözlést sem")
        self.c_sv_off.SetValue(bool(self.s.get("selfvoice_off", False)))
        v.Add(self.c_sv_off, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.c_hide_url = wx.CheckBox(
            p, label="Induláskor ne mutassa a letöltési &URL-mezőt "
                     "(a Fájl → Új letöltés vagy Ctrl+N előhozza)")
        self.c_hide_url.SetName("Induláskor a letöltési URL-mező elrejtése; a "
                                "Fájl menü Új letöltés pontja vagy a Ctrl+N "
                                "bármikor előhozza")
        self.c_hide_url.SetValue(bool(self.s.get("hide_url_row", False)))
        v.Add(self.c_hide_url, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # BEÉPÍTETT FÁJLVÁLASZTÓ: a Windows fájlválasztójába idegen bővítmények
        # épülnek be (kodek-csomag, felhő-szinkron, vírusirtó); ha azok egyike
        # elszáll, viszi az egész programot – ezt Pythonból nem lehet elkapni.
        # A miénk semmilyen ilyen bővítményt nem használ. [Miki jelzése]
        self.c_sajatfv = wx.CheckBox(
            p, label="Beépített &fájlválasztó használata a Windowsé helyett "
                     "(ha a fájl megnyitásakor kilép a program)")
        self.c_sajatfv.SetName(
            "Beépített fájlválasztó. Kapcsold be, ha a Windows fájlválasztója "
            "összeomlik a gépeden – a beépített nem használ "
            "rendszerbővítményeket, és teljesen billentyűzetről kezelhető.")
        self.c_sajatfv.SetValue(bool(self.s.get("beepitett_fajlvalaszto",
                                                False)))
        v.Add(self.c_sajatfv, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.c_startsig = wx.CheckBox(
            p, label="&Induló szignál (hangjelzés a program indulásakor, a "
                     "teljes némítás mellett is)")
        self.c_startsig.SetName("Induló szignál: rövid hangjelzés a program "
                                "indulásakor, a teljes némítás mellett is szól")
        self.c_startsig.SetValue(bool(self.s.get("startup_signal", True)))
        v.Add(self.c_startsig, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        pairs = [("(alapértelmezett rendszerhang)", "")]
        try:
            for d in SelfVoice().list_voices():
                pairs.append((d, d))
        except Exception:
            pass
        if espeak_available():
            pairs += ESPEAK_VOICES        # beépített magyar eSpeak-hangok
        self._sv_voice_pairs = pairs
        self.c_svvoice = wx.Choice(p, choices=[lab for lab, _ in pairs])
        cur = self.s.get("selfvoice_voice", "") or ""
        self.c_svvoice.SetSelection(
            next((i for i, (_l, v) in enumerate(pairs) if v == cur), 0))
        self.c_svvoice.SetName("Bejelentő hang")
        self._row(p, v, "Bejelentő ha&ng:", self.c_svvoice)
        self.c_svrate = wx.SpinCtrl(p, min=-10, max=10,
                                    initial=int(self.s.get("selfvoice_rate", 0)))
        self.c_svrate.SetName("Beszédtempó")
        self._row(p, v, "&Tempó (-10–10):", self.c_svrate)
        self.c_svpitch = wx.SpinCtrl(
            p, min=-10, max=10, initial=int(self.s.get("selfvoice_pitch", 0)))
        self.c_svpitch.SetName("Hangmagasság")
        self._row(p, v, "Hang&magasság (-10–10):", self.c_svpitch)
        self.c_svvol = wx.SpinCtrl(
            p, min=0, max=100, initial=int(self.s.get("selfvoice_volume", 100)))
        self.c_svvol.SetName("Beszéd hangereje")
        self._row(p, v, "Beszéd hangere&je (0–100):", self.c_svvol)

        b_test = wx.Button(p, label="Hang ki&próbálása")
        b_test.Bind(wx.EVT_BUTTON, lambda e: self._test_voice())
        v.Add(b_test, 0, wx.ALL, 8)
        p.SetSizer(v)
        return p

    def _test_voice(self):
        from .selfvoice import SelfVoice
        sv = SelfVoice()
        i = self.c_svvoice.GetSelection()
        voice = self._sv_voice_pairs[i][1] if 0 <= i < len(self._sv_voice_pairs) else ""
        sv.configure(enabled=True, voice_desc=voice,
                     rate=self.c_svrate.GetValue(),
                     pitch=self.c_svpitch.GetValue(),
                     volume=self.c_svvol.GetValue())
        sv.speak("Letöltés befejezve. Konvertálás megkezdődött.", force=True)

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
        # A kulcs-mezők MASZKOLVA jelennek meg (jelszó-mód): a képernyőn ne
        # látsszon a kulcs (Tibi-audit 5.2) – a felolvasó „védett" mezőt mond.
        # Az alábbi pipa kérésre felfedi (pl. ellenőrzéshez, gépeléshez).
        self.ai_show = wx.CheckBox(p, label="Kulcsok meg&jelenítése (látható "
                                            "szövegként)")
        self.ai_show.SetName("Kulcsok megjelenítése látható szövegként; "
                             "kikapcsolva a kulcsok maszkolva, pontokként "
                             "jelennek meg")
        self.ai_show.Bind(wx.EVT_CHECKBOX, self._on_show_keys)
        v.Add(self.ai_show, 0, wx.LEFT | wx.BOTTOM, 8)
        self.ai_openai = wx.TextCtrl(p, value=self.ai.get("openai_key", ""),
                                     style=wx.TE_PASSWORD)
        self._row(p, v, "&OpenAI (GPT) kulcs:", self.ai_openai)
        self.ai_gemini = wx.TextCtrl(p, value=self.ai.get("gemini_key", ""),
                                     style=wx.TE_PASSWORD)
        self._row(p, v, "Google &Gemini kulcs:", self.ai_gemini)
        self.ai_anthropic = wx.TextCtrl(p, value=self.ai.get("anthropic_key", ""),
                                        style=wx.TE_PASSWORD)
        self._row(p, v, "&Anthropic (Claude) kulcs:", self.ai_anthropic)
        self.ai_xai = wx.TextCtrl(p, value=self.ai.get("xai_key", ""),
                                  style=wx.TE_PASSWORD)
        self._row(p, v, "&xAI (Grok) kulcs:", self.ai_xai)
        self._ai_panel = p
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

    _AI_KEY_ATTRS = ("ai_openai", "ai_gemini", "ai_anthropic", "ai_xai")

    def _on_show_keys(self, evt=None):
        """A kulcs-mezők maszkolásának váltása. A TE_PASSWORD stílus futás
        közben nem váltható, ezért a mezőt AZONOS értékkel/névvel/fókusszal
        újraépítjük, és a helyére tesszük (tab-sorrend megőrizve)."""
        show = self.ai_show.GetValue()
        for attr in self._AI_KEY_ATTRS:
            self._swap_secret_style(attr, show)
        self._ai_panel.Layout()

    def _swap_secret_style(self, attr: str, show: bool):
        old = getattr(self, attr)
        parent = old.GetParent()
        new = wx.TextCtrl(parent, value=old.GetValue(),
                          style=0 if show else wx.TE_PASSWORD)
        new.SetName(old.GetName())
        try:
            acc = _NamedAccessible(old.GetName())
            new.SetAccessible(acc)
            self._accessibles.append(acc)
        except Exception:
            pass
        new.MoveAfterInTabOrder(old)       # a tab-sorrendbeli helyét örökli
        sizer = old.GetContainingSizer()
        if sizer:
            sizer.Replace(old, new)
        had_focus = wx.Window.FindFocus() is old
        old.Destroy()
        setattr(self, attr, new)
        if had_focus:
            new.SetFocus()

    # ---- mentés -------------------------------------------------------

    def _on_ok(self, evt):
        self.result_settings = {
            "connections": self.c_conn.GetValue(),
            "parallel": self.c_par.GetValue(),
            "limit": self.c_limit.GetValue().strip(),
            "audio_format": self.c_fmt.GetStringSelection() or "MP3",
            "video_format": self.c_vfmt.GetStringSelection() or "MP4",
            "audio_bitrate": self.c_abr.GetStringSelection() or "192",
            "audio_samplerate": SAMPLERATES[self.c_asr.GetSelection()][1],
            "radiorec": {
                "format": RADIO_REC_FORMATS[self.c_rrfmt.GetSelection()][1],
                "bitrate_kbps": int(self.c_rrbr.GetStringSelection() or "192"),
                "sample_rate":
                    int(SAMPLERATES[self.c_rrsr.GetSelection()][1] or 0),
                "chunk_minutes": (self.c_rrmin.GetValue()
                                  if self.c_rrsplit.GetSelection() == 1 else 0),
            },
            "seed_ratio": self.c_seed.GetValue().strip() or "1.0",
            "seed_forever": self.c_seedfor.GetValue(),
            "upload_limit": self.c_uplimit.GetValue().strip(),
            "hely_ellenorzes": self.c_hely.GetValue(),
            "savszelesseg_rend": self.c_savrend.GetValue().strip(),
            "duplikatum_kerdes": self.c_dup.GetValue(),
            "auto_rendezes": self.c_rendez.GetValue(),
            "playlist_folders": self.c_playlist.GetValue(),
            "cookies": self.c_cookies.GetStringSelection() or "Nincs",
            "cookies_file": self.cookies_file or "",
            "clipboard": self.c_clip.GetValue(),
            "notify": self.c_notify.GetValue(),
            "dev_custom_repo": self.c_devrepo.GetValue(),
            "city": self.c_city.GetValue().strip(),
            "voice_mode": VOICE_LABELS[self.c_voice.GetSelection()][1],
            "beep_enabled": self.c_beep.GetValue(),
            "beep_volume": self.c_beepvol.GetValue(),
            "screenreader_only": self.c_sronly.GetValue(),
            "selfvoice_enabled": self.c_sv.GetValue(),
            "selfvoice_off": self.c_sv_off.GetValue(),
            "hide_url_row": self.c_hide_url.GetValue(),
            "startup_signal": self.c_startsig.GetValue(),
            "beepitett_fajlvalaszto": self.c_sajatfv.GetValue(),
            "selfvoice_voice":
                self._sv_voice_pairs[self.c_svvoice.GetSelection()][1],
            "selfvoice_rate": self.c_svrate.GetValue(),
            "selfvoice_pitch": self.c_svpitch.GetValue(),
            "selfvoice_volume": self.c_svvol.GetValue(),
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
