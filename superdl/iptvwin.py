"""Internetes TV (IPTV) ablak – akadálymentes, KIZÁRÓLAG legális forrásokhoz.

A felhasználó a saját, jogtiszta hozzáférését tölti be: m3u/m3u8 lista (fájl vagy
URL), vagy Xtream Codes belépés (cím + név + jelszó). A program ezt teszi
akadálymentessé: csatornalista csoportokkal és kereséssel, kedvencek, lejátszás
csak-hang módban, és felolvasott műsorújság (EPG: most megy / utána jön / teljes
műsor). NEM kerül meg DRM-et, és NEM tartalmaz semmilyen kész csatornalistát.
"""

import datetime as _dt
import os
import re
import threading

import wx

from . import iptv
from . import organizer as O
from . import store
from .audioengine import Player


class IPTVFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Internetes TV (legális IPTV)",
                         size=(900, 680))
        self.main = main
        self.channels: list[iptv.Channel] = []
        self.filtered: list[iptv.Channel] = []
        self.favorites: list[iptv.Channel] = [
            iptv.Channel.from_record(r) for r in store.load_iptv_favorites()]
        self.epg: iptv.EPG | None = None
        self._busy = False
        self.player = Player()
        self.player.on_state = lambda s: wx.CallAfter(self._on_state, s)
        self._cur = None
        self._rec_proc = None              # futó felvétel (D)
        self._rec_name = ""
        self._sub_reader = None            # élő felirat-felolvasó (E)
        self._audio_tracks = []            # a lekért hangsávok
        self._sub_tracks = []              # a lekért feliratsávok

        self._build()
        self.CreateStatusBar()
        self._load_conf()
        self._announce("Tölts be egy m3u listát vagy lépj be Xtream-adatokkal "
                       "(saját, legális hozzáférés). Enter: lejátszás, "
                       "E: mi megy most.")
        self.Bind(wx.EVT_CLOSE, self._on_close)

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        # m3u forrás
        r1 = wx.BoxSizer(wx.HORIZONTAL)
        b_file = wx.Button(p, label="m3u &fájl…")
        b_file.Bind(wx.EVT_BUTTON, lambda e: self._load_m3u_file())
        r1.Add(b_file, 0, wx.RIGHT, 6)
        r1.Add(wx.StaticText(p, label="m3u &URL:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.m3u_url = wx.TextCtrl(p, name="m3u lista címe")
        r1.Add(self.m3u_url, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        b_url = wx.Button(p, label="&Betöltés")
        b_url.Bind(wx.EVT_BUTTON, lambda e: self._load_m3u_url())
        r1.Add(b_url, 0)
        v.Add(r1, 0, wx.EXPAND | wx.ALL, 6)

        # Xtream belépés
        xb = wx.StaticBox(p, label="Xtream Codes belépés (saját, legális "
                          "előfizetés)")
        xs = wx.StaticBoxSizer(xb, wx.HORIZONTAL)
        xs.Add(wx.StaticText(p, label="&Kiszolgáló:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.xt_host = wx.TextCtrl(p, name="Xtream kiszolgáló címe")
        xs.Add(self.xt_host, 1, wx.RIGHT, 6)
        xs.Add(wx.StaticText(p, label="F&elhasználó:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.xt_user = wx.TextCtrl(p, name="Xtream felhasználónév")
        xs.Add(self.xt_user, 0, wx.RIGHT, 6)
        xs.Add(wx.StaticText(p, label="&Jelszó:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.xt_pass = wx.TextCtrl(p, style=wx.TE_PASSWORD,
                                   name="Xtream jelszó")
        xs.Add(self.xt_pass, 0, wx.RIGHT, 6)
        b_login = wx.Button(p, label="Be&jelentkezés")
        b_login.Bind(wx.EVT_BUTTON, lambda e: self._xtream_login())
        xs.Add(b_login, 0)
        v.Add(xs, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        # EPG (műsorújság)
        er = wx.BoxSizer(wx.HORIZONTAL)
        er.Add(wx.StaticText(p, label="Műsorújság (XML&TV URL, nem kötelező):"),
               0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.epg_url = wx.TextCtrl(p, name="Műsorújság XMLTV címe")
        er.Add(self.epg_url, 1, wx.RIGHT, 4)
        b_epg = wx.Button(p, label="Műso&rújság betöltése")
        b_epg.Bind(wx.EVT_BUTTON, lambda e: self._load_epg())
        er.Add(b_epg, 0)
        v.Add(er, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        # szűrő
        fr = wx.BoxSizer(wx.HORIZONTAL)
        fr.Add(wx.StaticText(p, label="Cso&port:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.group_ch = wx.Choice(p, choices=["Összes csatorna"],
                                  name="Csoport szűrő")
        self.group_ch.SetSelection(0)
        self.group_ch.Bind(wx.EVT_CHOICE, lambda e: self._refresh_list())
        fr.Add(self.group_ch, 0, wx.RIGHT, 10)
        fr.Add(wx.StaticText(p, label="Ke&resés:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.search = wx.TextCtrl(p, name="Csatorna keresése")
        self.search.Bind(wx.EVT_TEXT, lambda e: self._refresh_list())
        fr.Add(self.search, 1, wx.RIGHT, 10)
        self.fav_only = wx.CheckBox(p, label="Csak &kedvencek")
        self.fav_only.SetName("Csak kedvencek")
        self.fav_only.Bind(wx.EVT_CHECKBOX, lambda e: self._refresh_list())
        fr.Add(self.fav_only, 0, wx.ALIGN_CENTER_VERTICAL)
        v.Add(fr, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        # csatornalista
        self.list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
                                name="Csatornalista")
        self.list.InsertColumn(0, "Csatorna", width=320)
        self.list.InsertColumn(1, "Csoport", width=180)
        self.list.InsertColumn(2, "Most megy", width=340)
        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._play())
        self.list.Bind(wx.EVT_KEY_DOWN, self._on_key)
        v.Add(self.list, 1, wx.EXPAND | wx.ALL, 6)

        self.now_lbl = wx.StaticText(p, label="Most nem szól semmi.")
        self.now_lbl.SetName("Lejátszás állapota")
        v.Add(self.now_lbl, 0, wx.LEFT | wx.BOTTOM, 6)

        b1 = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (
                ("Le&játszás (Enter)", lambda e: self._play()),
                ("Le&állítás", lambda e: self._stop()),
                ("&Szünet", lambda e: self._toggle()),
                ("Hangerő &−", lambda e: self._vol(-0.05)),
                ("Hangerő &+", lambda e: self._vol(0.05)),
                ("Kedvenc be/ki (&F)", lambda e: self._toggle_fav())):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            b1.Add(b, 0, wx.RIGHT, 5)
        v.Add(b1, 0, wx.LEFT | wx.BOTTOM, 6)

        b2 = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (
                ("&Mi megy most? (E)", lambda e: self._now_next()),
                ("&Teljes műsor", lambda e: self._schedule()),
                ("Mi megy most az ö&sszesen", lambda e: self._overview())):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            b2.Add(b, 0, wx.RIGHT, 5)
        v.Add(b2, 0, wx.LEFT | wx.BOTTOM, 6)

        # felvétel + emlékeztető (D)
        rec = wx.BoxSizer(wx.HORIZONTAL)
        self.rec_btn = wx.Button(p, label="Fel&vétel indítása (R)")
        self.rec_btn.Bind(wx.EVT_BUTTON, lambda e: self._toggle_record())
        rec.Add(self.rec_btn, 0, wx.RIGHT, 6)
        b_rem = wx.Button(p, label="E&mlékeztető a következő műsorra")
        b_rem.Bind(wx.EVT_BUTTON, lambda e: self._reminder())
        rec.Add(b_rem, 0)
        v.Add(rec, 0, wx.LEFT | wx.BOTTOM, 6)

        # hangsáv (hangalámondás) + felirat-felolvasás (E)
        av = wx.BoxSizer(wx.HORIZONTAL)
        av.Add(wx.StaticText(p, label="Hang&sáv:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.audio_ch = wx.Choice(p, choices=["Alapértelmezett"],
                                  name="Hangsáv (pl. hangalámondás)")
        self.audio_ch.SetSelection(0)
        av.Add(self.audio_ch, 0, wx.RIGHT, 4)
        b_at = wx.Button(p, label="Hangsávok &lekérése")
        b_at.Bind(wx.EVT_BUTTON, lambda e: self._get_audio_tracks())
        av.Add(b_at, 0, wx.RIGHT, 14)
        av.Add(wx.StaticText(p, label="Felira&t:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.sub_ch = wx.Choice(p, choices=["(nincs)"], name="Feliratsáv")
        self.sub_ch.SetSelection(0)
        av.Add(self.sub_ch, 0, wx.RIGHT, 4)
        b_st = wx.Button(p, label="Feliratok l&ekérése")
        b_st.Bind(wx.EVT_BUTTON, lambda e: self._get_sub_tracks())
        av.Add(b_st, 0, wx.RIGHT, 6)
        self.subread_btn = wx.Button(p, label="Felirat felol&vasása: KI")
        self.subread_btn.Bind(wx.EVT_BUTTON, lambda e: self._toggle_subread())
        av.Add(self.subread_btn, 0)
        v.Add(av, 0, wx.LEFT | wx.BOTTOM, 6)

        v.Add(wx.StaticText(p, label="Műso&rújság / információ:"), 0, wx.LEFT, 6)
        self.report = wx.TextCtrl(
            p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP,
            size=(-1, 110), name="Műsorújság")
        v.Add(self.report, 0, wx.EXPAND | wx.ALL, 6)
        p.SetSizer(v)

    # ---- visszajelzés -------------------------------------------------

    def _announce(self, text):
        self.SetStatusText(text)

    def _say(self, text):
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            try:
                sv.speak(text, force=True)
            except Exception:
                pass

    def _report(self, text):
        self.report.SetValue(text)
        self._announce(text.splitlines()[0] if text else "")
        self._say(text)

    # ---- forrás betöltése ---------------------------------------------

    def _bg(self, label, fn, done):
        if self._busy:
            return
        self._busy = True
        self._announce(label)

        def work():
            try:
                res = fn()
            except Exception as ex:
                wx.CallAfter(self._load_failed, ex)
                return
            wx.CallAfter(done, res)
        threading.Thread(target=work, daemon=True).start()

    def _load_failed(self, ex):
        self._busy = False
        self._announce(f"Hiba a betöltéskor: {ex}")
        self._report(f"Nem sikerült betölteni: {ex}")

    def _load_m3u_file(self):
        dlg = wx.FileDialog(self, "m3u lejátszási lista",
                            wildcard="m3u lista|*.m3u;*.m3u8|Minden fájl|*.*",
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self._bg("Lista betöltése…", lambda: iptv.load_playlist(path),
                     self._channels_loaded)
        dlg.Destroy()

    def _load_m3u_url(self):
        url = self.m3u_url.GetValue().strip()
        if not url:
            return
        self._save_conf()
        self._bg("Lista betöltése…", lambda: iptv.load_playlist(url),
                 self._channels_loaded)

    def _xtream_login(self):
        host = self.xt_host.GetValue().strip()
        user = self.xt_user.GetValue().strip()
        pwd = self.xt_pass.GetValue()
        if not (host and user and pwd):
            self._announce("Add meg a kiszolgálót, a felhasználónevet és a "
                           "jelszót.")
            return
        # az EPG-mezőt is feltöltjük a szerver XMLTV-címével
        self.epg_url.SetValue(iptv.xtream_epg_url(host, user, pwd))
        self._save_conf()
        self._bg("Bejelentkezés és csatornák lekérése…",
                 lambda: iptv.xtream_channels(host, user, pwd),
                 self._channels_loaded)

    def _channels_loaded(self, channels):
        self._busy = False
        self.channels = channels
        groups = iptv.groups(channels)
        self.group_ch.Set(groups)
        self.group_ch.SetSelection(0)
        self._refresh_list()
        self._announce(f"{len(channels)} csatorna betöltve.")
        if not channels:
            self._report("A lista üres, vagy nem értelmezhető.")

    def _load_epg(self):
        url = self.epg_url.GetValue().strip()
        if not url:
            self._announce("Add meg a műsorújság (XMLTV) címét, vagy lépj be "
                           "Xtream-mel (akkor magától kitöltődik).")
            return
        self._bg("Műsorújság betöltése… (ez nagyobb fájl lehet)",
                 lambda: iptv.EPG.load(url), self._epg_loaded)

    def _epg_loaded(self, epg):
        self._busy = False
        self.epg = epg
        n = len(epg.by_channel)
        self._refresh_list()
        self._announce(f"Műsorújság betöltve: {n} csatornához van adat.")

    # ---- lista szűrés -------------------------------------------------

    def _refresh_list(self):
        group = self.group_ch.GetStringSelection()
        q = self.search.GetValue().strip().lower()
        favs = {(c.name, c.url) for c in self.favorites}
        only_fav = self.fav_only.IsChecked()
        src = self.favorites if only_fav else self.channels
        self.filtered = []
        for c in src:
            if group and group != "Összes csatorna" and c.group != group:
                continue
            if q and q not in c.name.lower():
                continue
            self.filtered.append(c)
        self.list.DeleteAllItems()
        now = _dt.datetime.now()
        for c in self.filtered:
            row = self.list.InsertItem(self.list.GetItemCount(),
                                       ("★ " if (c.name, c.url) in favs else "")
                                       + c.name)
            self.list.SetItem(row, 1, c.group)
            if self.epg and c.tvg_id:
                cur, _n = self.epg.now_next(c.tvg_id, now)
                if cur:
                    self.list.SetItem(row, 2, cur.title)
        if self.filtered:
            self.list.Select(0)
            self.list.Focus(0)

    def _selected(self) -> iptv.Channel | None:
        i = self.list.GetFirstSelected()
        return self.filtered[i] if 0 <= i < len(self.filtered) else None

    # ---- lejátszás ----------------------------------------------------

    def _play(self):
        c = self._selected()
        if not c:
            return
        self._cur = c
        self._announce(f"Kapcsolódás: {c.name} …")
        self.player.play(c.url, c.name, audio_track=self._selected_audio_track())

    def _selected_audio_track(self):
        i = self.audio_ch.GetSelection()
        if i <= 0 or i - 1 >= len(self._audio_tracks):
            return None                     # alapértelmezett sáv
        return self._audio_tracks[i - 1]["index"]

    def _on_state(self, text):
        if text == "lejátszás" and self._cur:
            extra = ""
            if self.epg and self._cur.tvg_id:
                cur, nxt = self.epg.now_next(self._cur.tvg_id)
                if cur:
                    extra = f" – most: {cur.title}"
            self._announce(f"Most szól: {self._cur.name}{extra} "
                           f"(hangerő {round(self.player.volume * 100)}%)")
        elif text.startswith("hiba"):
            self._announce(f"Nem játszható le ({text}). DRM-es vagy zárt adás?")
        elif text == "vége":
            self._announce("Az adás megszakadt.")

    def _toggle(self):
        if not self.player.is_active():
            return
        paused = self.player.toggle_pause()
        self._announce("Szünet." if paused else
                       f"Folytatás: {self._cur.name if self._cur else ''}")

    def _stop(self):
        if self.player.is_active():
            self.player.stop()
            self._announce("Leállítva.")

    def _vol(self, d):
        self.player.set_volume(self.player.volume + d)
        self._announce(f"Hangerő: {round(self.player.volume * 100)} százalék.")

    # ---- kedvencek ----------------------------------------------------

    def _toggle_fav(self):
        c = self._selected()
        if not c:
            return
        key = (c.name, c.url)
        if any((f.name, f.url) == key for f in self.favorites):
            self.favorites = [f for f in self.favorites
                              if (f.name, f.url) != key]
            self._announce(f"Eltávolítva a kedvencekből: {c.name}")
        else:
            self.favorites.append(c)
            self._announce(f"Hozzáadva a kedvencekhez: {c.name}")
        store.save_iptv_favorites([f.to_record() for f in self.favorites])
        self._refresh_list()

    # ---- felvétel + emlékeztető (D) -----------------------------------

    def _download_dir(self) -> str:
        d = getattr(self.main, "dir_entry", None)
        if d is not None:
            try:
                val = d.GetValue().strip()
                if val and os.path.isdir(val):
                    return val
            except Exception:
                pass
        return os.path.join(os.path.expanduser("~"), "Downloads")

    def _toggle_record(self):
        if self._rec_proc is not None:
            iptv.stop_recording(self._rec_proc)
            self._rec_proc = None
            self.rec_btn.SetLabel("Fel&vétel indítása (R)")
            self._announce(f"Felvétel leállítva: {self._rec_name}")
            return
        c = self._selected()
        if not c:
            self._announce("Előbb válassz egy csatornát a felvételhez.")
            return
        safe = re.sub(r'[<>:"/\\|?*]', "_", c.name).strip() or "felvetel"
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(self._download_dir(), f"{safe}_{stamp}.ts")
        try:
            self._rec_proc = iptv.start_recording(c.url, out)
        except Exception as ex:
            self._announce(f"A felvétel nem indult: {ex}")
            return
        self._rec_name = os.path.basename(out)
        self.rec_btn.SetLabel("Felvétel le&állítása")
        self._announce(f"Felvétel indítva: {c.name} → {self._rec_name}. "
                       "A leállításhoz nyomd meg újra.")

    def _reminder(self):
        c = self._selected()
        if not c:
            return
        org = getattr(self.main, "_organizer", None)
        if org is None:
            self._announce("A naptár nem érhető el.")
            return
        if not (self.epg and c.tvg_id):
            self._announce("Ehhez töltsd be a műsorújságot, és válassz "
                           "műsorújság-azonosítóval rendelkező csatornát.")
            return
        cur, nxt = self.epg.now_next(c.tvg_id)
        pr = nxt or cur
        if not pr:
            self._announce(f"{c.name}: nincs következő műsoradat.")
            return
        ev = O.Event(
            id=O.new_id(), title=f"TV: {c.name} – {pr.title}",
            date=pr.start.date().isoformat(), time=pr.start.strftime("%H:%M"),
            note="SuperDL TV-emlékeztető", reminder_min=2,
            action_type="speak",
            action_data=f"Mindjárt kezdődik: {pr.title} a {c.name} csatornán.")
        org.add_event(ev)
        self._announce(f"Emlékeztető beállítva: {pr.title} – "
                       f"{pr.start.strftime('%H:%M')}, {c.name}.")

    # ---- hangsáv + felirat-felolvasás (E) -----------------------------

    def _get_audio_tracks(self):
        c = self._selected()
        if not c or self._busy:
            return
        self._busy = True
        self._announce("Hangsávok lekérése… (pár másodperc)")

        def work():
            tracks = iptv.audio_tracks(c.url)
            wx.CallAfter(self._audio_tracks_done, tracks)
        threading.Thread(target=work, daemon=True).start()

    def _audio_tracks_done(self, tracks):
        self._busy = False
        self._audio_tracks = tracks
        self.audio_ch.Set(["Alapértelmezett"] + [t["label"] for t in tracks])
        self.audio_ch.SetSelection(0)
        ad = next((t for t in tracks if t["is_ad"]), None)
        if ad:
            self._announce(f"{len(tracks)} hangsáv – van hangalámondás-sáv! "
                           "Válaszd ki a Hangsáv listából, majd Lejátszás.")
        else:
            self._announce(f"{len(tracks)} hangsáv található." if tracks
                           else "Nem találtam külön hangsávot.")

    def _get_sub_tracks(self):
        c = self._selected()
        if not c or self._busy:
            return
        self._busy = True
        self._announce("Feliratsávok lekérése… (pár másodperc)")

        def work():
            tracks = iptv.subtitle_tracks(c.url)
            wx.CallAfter(self._sub_tracks_done, tracks)
        threading.Thread(target=work, daemon=True).start()

    def _sub_tracks_done(self, tracks):
        self._busy = False
        self._sub_tracks = tracks
        self.sub_ch.Set(["(nincs)"] + [t["label"] for t in tracks])
        self.sub_ch.SetSelection(0)
        self._announce(f"{len(tracks)} feliratsáv található." if tracks
                       else "Nem találtam feliratot.")

    def _toggle_subread(self):
        if self._sub_reader is not None:
            self._sub_reader.stop()
            self._sub_reader = None
            self.subread_btn.SetLabel("Felirat felol&vasása: KI")
            self._announce("Felirat-felolvasás kikapcsolva.")
            return
        c = self._selected()
        i = self.sub_ch.GetSelection()
        if not c or i <= 0 or i - 1 >= len(self._sub_tracks):
            self._announce("Előbb kérd le a feliratokat, és válassz egy "
                           "szöveges feliratsávot.")
            return
        track = self._sub_tracks[i - 1]
        if not track["is_text"]:
            self._announce("Ez képi felirat (DVB/PGS) – ahhoz OCR kellene, ami "
                           "egy későbbi bővítés. Válassz szöveges feliratot.")
            return
        reader = iptv.SubtitleReader(c.url, track["index"], self._say)
        if reader.start():
            self._sub_reader = reader
            self.subread_btn.SetLabel("Felirat felol&vasása: BE")
            self._announce("Felirat-felolvasás bekapcsolva – felolvasom a "
                           "feliratokat, ahogy megjelennek.")
        else:
            self._announce("A felirat-felolvasás nem indult (ffmpeg?).")

    # ---- EPG (műsorújság) ---------------------------------------------

    def _fmt(self, pr) -> str:
        return f"{pr.start.strftime('%H:%M')}–{pr.stop.strftime('%H:%M')}  {pr.title}"

    def _now_next(self):
        c = self._selected()
        if not c:
            return
        if not self.epg:
            self._report("Nincs betöltött műsorújság. Töltsd be az XMLTV-t "
                         "(vagy lépj be Xtream-mel).")
            return
        if not c.tvg_id:
            self._report(f"{c.name}: ehhez a csatornához nincs műsorújság-"
                         "azonosító a listában.")
            return
        cur, nxt = self.epg.now_next(c.tvg_id)
        if not cur and not nxt:
            self._report(f"{c.name}: nincs aktuális műsoradat.")
            return
        lines = [f"{c.name}:"]
        if cur:
            lines.append("Most megy: " + self._fmt(cur)
                         + (f" – {cur.desc}" if cur.desc else ""))
        if nxt:
            lines.append("Utána jön: " + self._fmt(nxt))
        self._report("\n".join(lines))

    def _schedule(self):
        c = self._selected()
        if not (c and self.epg and c.tvg_id):
            self._report("Ehhez töltsd be a műsorújságot, és válassz egy "
                         "csatornát műsorújság-azonosítóval.")
            return
        progs = self.epg.schedule(c.tvg_id)
        if not progs:
            self._report(f"{c.name}: nincs további műsoradat.")
            return
        self._report(f"{c.name} – műsor:\n"
                     + "\n".join(self._fmt(p) for p in progs))

    def _overview(self):
        if not self.epg:
            self._report("Nincs betöltött műsorújság.")
            return
        now = _dt.datetime.now()
        lines = ["Most megy az összes (látható) csatornán:"]
        for c in self.filtered[:40]:
            if not c.tvg_id:
                continue
            cur, _n = self.epg.now_next(c.tvg_id, now)
            if cur:
                lines.append(f"{c.name}: {cur.title}")
        self._report("\n".join(lines) if len(lines) > 1
                     else "Nincs aktuális műsoradat a látható csatornákhoz.")

    # ---- billentyű + tárolás + zárás ----------------------------------

    def _on_key(self, e):
        code = e.GetKeyCode()
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._play()
        elif code in (ord('E'), ord('e')):
            self._now_next()
        elif code in (ord('F'), ord('f')):
            self._toggle_fav()
        elif code in (ord('R'), ord('r')):
            self._toggle_record()
        elif code == wx.WXK_SPACE:
            self._toggle()
        else:
            e.Skip()

    def _load_conf(self):
        c = store.load_iptv_conf()
        self.m3u_url.SetValue(c.get("m3u_url", ""))
        self.epg_url.SetValue(c.get("epg_url", ""))
        self.xt_host.SetValue(c.get("xt_host", ""))
        self.xt_user.SetValue(c.get("xt_user", ""))
        if self.favorites:
            self._refresh_list()

    def _save_conf(self):
        store.save_iptv_conf({
            "m3u_url": self.m3u_url.GetValue().strip(),
            "epg_url": self.epg_url.GetValue().strip(),
            "xt_host": self.xt_host.GetValue().strip(),
            "xt_user": self.xt_user.GetValue().strip()})

    def _on_close(self, e):
        try:
            self.player.stop()
            if self._sub_reader:
                self._sub_reader.stop()
            if self._rec_proc:
                iptv.stop_recording(self._rec_proc)
        except Exception:
            pass
        self._save_conf()
        if getattr(self.main, "_iptv_win", None) is self:
            self.main._iptv_win = None
        self.Destroy()
