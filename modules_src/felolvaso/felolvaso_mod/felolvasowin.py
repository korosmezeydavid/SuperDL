"""Felirat-felolvasó lejátszó: egy film (vagy hangfájl) lejátszása, közben a
MAGYAR (vagy bármely szöveges) felirat SZINKRONBAN, választható hanggal
felolvasva – vakon is „nézhető" az idegen nyelvű film.

Két hangfolyam: a film hangját a `film` Player adja, a felolvasást a `narr`
Player (a felirat épp aktuális sorát egy ideiglenes hangfájlból). A szinkront a
film lejátszási POZÍCIÓJA vezérli (a `CueScheduler`-en át), ezért szünet/ugrás
után is stimmel. Felolvasás alatt a film hangját lehalkítjuk (ducking).
"""

import os
import threading

import wx

from . import narrator, subtitles
from superdl.audioengine import Player

HELP = """FELIRAT-FELOLVASÓ LEJÁTSZÓ

MIRE VALÓ
Idegen nyelvű film (vagy hangfájl) lejátszása úgy, hogy a MAGYAR feliratot a
program SZINKRONBAN, választható hanggal felolvassa. Így vakon is követhető az
idegen nyelvű film: hallod az eredeti hangot, fölötte a felolvasott feliratot.

LÉPÉSRŐL LÉPÉSRE (vakon is)
1. „Média betöltése" – válaszd ki a filmet vagy hangfájlt. A program magától
   megkeresi a mellé tett feliratot (.srt/.vtt), és a fájlba ágyazott
   feliratsávokat is felkínálja.
2. „Felirat" lista: válaszd ki, melyik feliratot olvassa (a magyar előre van
   sorolva). Ha külön fájlból akarod, „Feliratfájl tallózása".
3. „Hang" lista: válaszd ki, milyen hanggal olvasson – helyi SAPI-hang, Edge
   neurális (online, szép), vagy a beépített eSpeak.
4. „Lejátszás" (vagy Szóköz). A felolvasás alatt a film hangja halkabb.

GYORSBILLENTYŰK
F1 – súgó.  Szóköz – lejátszás/szünet.  Bal/jobb nyíl – 10 mp vissza/előre.
Ctrl+fel / Ctrl+le – hangerő.  Esc – leállítás.

TIPPEK
- A felirat legyen a film MELLETT, hasonló névvel (pl. Film.hu.srt) – a program
  automatikusan megtalálja.
- Az Edge neurális hang a legszebb (online, ingyenes, kulcs nélkül); ha nincs
  net, a SAPI vagy az eSpeak offline is megy."""

DUCK = 0.22          # a film hangereje a felolvasás alatt (halkítás)


class FelolvasoFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Felirat-felolvasó lejátszó",
                         size=(880, 560))
        self.main = main
        self.media = ""
        self.cues: list = []
        self.sched = None
        self._sources: list = []          # (címke, típus, adat) felirat-források
        self._voices = narrator.voice_options()
        self._narrating = False
        self._film_vol = 0.8
        self._cur_temp = None

        self.film = Player()
        self.film.on_state = lambda s: wx.CallAfter(self._on_film_state, s)
        self.narr = Player()
        self.narr.set_volume(1.0)
        self.narr.on_state = lambda s: wx.CallAfter(self._on_narr_state, s)

        self._build()
        self.CreateStatusBar()
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self._tick(), self.timer)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self._announce("Tölts be egy filmet vagy hangfájlt; a magyar feliratot "
                       "szinkronban felolvasom. Súgó: F1.")

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        top = wx.BoxSizer(wx.HORIZONTAL)
        b_load = wx.Button(p, label="Média &betöltése…")
        b_load.Bind(wx.EVT_BUTTON, lambda e: self._load())
        self.media_lbl = wx.StaticText(p, label="Nincs betöltött média.")
        self.media_lbl.SetName("Betöltött média")
        top.Add(b_load, 0, wx.RIGHT, 8)
        top.Add(self.media_lbl, 1, wx.ALIGN_CENTER_VERTICAL)
        v.Add(top, 0, wx.EXPAND | wx.ALL, 8)

        g = wx.FlexGridSizer(0, 3, 8, 8)
        g.AddGrowableCol(1)
        g.Add(wx.StaticText(p, label="&Felirat:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.sub_ch = wx.Choice(p, choices=["(előbb tölts be médiát)"],
                                name="Felirat forrása")
        self.sub_ch.SetSelection(0)
        g.Add(self.sub_ch, 0, wx.EXPAND)
        b_browse = wx.Button(p, label="Feliratfájl &tallózása…")
        b_browse.Bind(wx.EVT_BUTTON, lambda e: self._browse_sub())
        g.Add(b_browse, 0)

        g.Add(wx.StaticText(p, label="&Hang:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.voice_ch = wx.Choice(p, choices=[lbl for lbl, _e, _v in self._voices]
                                  or ["(nincs hang)"], name="Felolvasó hang")
        self.voice_ch.SetSelection(0)
        g.Add(self.voice_ch, 0, wx.EXPAND)
        b_subload = wx.Button(p, label="Felirat be&töltése")
        b_subload.Bind(wx.EVT_BUTTON, lambda e: self._apply_sub())
        g.Add(b_subload, 0)
        v.Add(g, 0, wx.EXPAND | wx.ALL, 8)

        ctl = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (("Le&játszás / szünet", lambda e: self._toggle()),
                          ("&Leállítás", lambda e: self._stop()),
                          ("10 mp &vissza", lambda e: self._seek(-10)),
                          ("10 mp &előre", lambda e: self._seek(10)),
                          ("Hangerő &−", lambda e: self._vol(-0.1)),
                          ("Hangerő &+", lambda e: self._vol(0.1))):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            ctl.Add(b, 0, wx.RIGHT, 6)
        v.Add(ctl, 0, wx.LEFT | wx.BOTTOM, 8)

        self.now_lbl = wx.StaticText(p, label="Most nem szól semmi.")
        self.now_lbl.SetName("Lejátszás állapota")
        v.Add(self.now_lbl, 0, wx.LEFT | wx.BOTTOM, 8)

        v.Add(wx.StaticText(p, label="Épp felolvasott &felirat:"), 0, wx.LEFT, 8)
        self.cue_txt = wx.TextCtrl(
            p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP,
            size=(-1, 120))
        self.cue_txt.SetName("Épp felolvasott felirat")
        v.Add(self.cue_txt, 1, wx.EXPAND | wx.ALL, 8)
        p.SetSizer(v)

    # ---- segédek ------------------------------------------------------

    def _announce(self, text):
        self.SetStatusText(text)
        self.now_lbl.SetLabel(text)

    def _voice(self):
        i = self.voice_ch.GetSelection()
        return self._voices[i] if 0 <= i < len(self._voices) else \
            ("eSpeak", "espeak", "espeak:hu")

    # ---- média + felirat betöltése ------------------------------------

    def _load(self):
        wild = ("Film és hang|" + ";".join(
            "*" + e for e in subtitles.VIDEO_EXTS + subtitles.AUDIO_EXTS)
            + "|Minden fájl|*.*")
        dlg = wx.FileDialog(self, "Film vagy hangfájl betöltése", wildcard=wild,
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.media = dlg.GetPath()
            self.media_lbl.SetLabel(os.path.basename(self.media))
            self._scan_sources()
        dlg.Destroy()

    def _scan_sources(self):
        """A médiához tartozó feliratforrások összegyűjtése: mellé tett fájlok +
        beágyazott szöveges sávok."""
        self._sources = []
        for path in subtitles.find_sidecar_subs(self.media):
            self._sources.append((f"Fájl: {os.path.basename(path)}",
                                  "file", path))
        try:
            for tr in subtitles.embedded_text_tracks(self.media):
                self._sources.append((f"Beágyazott: {tr['label']}",
                                     "embedded", tr["index"]))
        except Exception:
            pass
        if self._sources:
            self.sub_ch.Set([lbl for lbl, _t, _d in self._sources])
            self.sub_ch.SetSelection(0)
            self._announce(f"{len(self._sources)} feliratforrás. Válassz, és "
                           "nyomd meg a „Felirat betöltése” gombot.")
        else:
            self.sub_ch.Set(["(nincs felirat – tallózz egyet)"])
            self.sub_ch.SetSelection(0)
            self._announce("Nem találtam feliratot a média mellett. Tallózz egy "
                           "feliratfájlt (.srt).")

    def _browse_sub(self):
        dlg = wx.FileDialog(
            self, "Feliratfájl kiválasztása",
            wildcard="Felirat|*.srt;*.vtt;*.ass;*.ssa;*.sub|Minden fájl|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self._sources.append((f"Fájl: {os.path.basename(path)}",
                                  "file", path))
            self.sub_ch.Set([lbl for lbl, _t, _d in self._sources])
            self.sub_ch.SetSelection(len(self._sources) - 1)
            self._announce("Feliratfájl hozzáadva. Nyomd meg a „Felirat "
                           "betöltése” gombot.")
        dlg.Destroy()

    def _apply_sub(self):
        i = self.sub_ch.GetSelection()
        if not (0 <= i < len(self._sources)):
            self._announce("Előbb válassz feliratforrást.")
            return
        _lbl, typ, data = self._sources[i]
        self._announce("Felirat betöltése…")

        def work():
            try:
                if typ == "file":
                    cues = subtitles.load_subtitle_file(data)
                else:
                    cues = subtitles.extract_embedded(self.media, data)
            except Exception as e:
                wx.CallAfter(self._announce, f"A felirat nem tölthető be: {e}")
                return
            wx.CallAfter(self._subs_ready, cues)

        threading.Thread(target=work, daemon=True).start()

    def _subs_ready(self, cues):
        self.cues = cues
        self.sched = subtitles.CueScheduler(cues)
        self._announce(f"{len(cues)} felirat betöltve. Indíthatod a lejátszást "
                       "(Szóköz).")

    # ---- lejátszás-vezérlés -------------------------------------------

    def _toggle(self):
        if not self.media:
            self._announce("Előbb tölts be egy médiát.")
            return
        if self.film.is_active():
            paused = self.film.toggle_pause()
            self._announce("Szünet." if paused else "Folytatás.")
        else:
            self.film.set_volume(self._film_vol)
            self.film.play(self.media)
            if self.sched:
                self.sched.reset_to(0.0)
            self.timer.Start(150)
            self._announce("Lejátszás.")

    def _stop(self):
        self.timer.Stop()
        self.narr.stop()
        self.film.stop()
        self._narrating = False
        self._announce("Leállítva.")

    def _seek(self, delta):
        if not self.film.is_active():
            return
        pos = max(0.0, self.film.position() + delta)
        self.narr.stop()
        self._narrating = False
        self.film.set_volume(self._film_vol)
        self.film.seek(pos)
        if self.sched:
            self.sched.reset_to(pos)
        self._announce(f"Ugrás: {int(pos // 60)} perc {int(pos % 60)} mp.")

    def _vol(self, delta):
        self._film_vol = max(0.0, min(1.0, self._film_vol + delta))
        if not self._narrating:
            self.film.set_volume(self._film_vol)
        self._announce(f"Hangerő: {round(self._film_vol * 100)} százalék.")

    # ---- a szinkron szíve: időzítő --------------------------------------

    def _tick(self):
        if self._narrating or not self.film.is_active() \
                or self.film.is_paused() or not self.sched:
            return
        cue = self.sched.next_due(self.film.position())
        if cue:
            self._narrate(cue)

    def _narrate(self, cue):
        self._narrating = True
        self.cue_txt.SetValue(cue.text)
        lbl, eng, vid = self._voice()

        def work():
            try:
                path = narrator.synth_to_file(eng, vid, cue.text)
            except Exception:
                wx.CallAfter(self._narration_done)
                return
            wx.CallAfter(self._play_narration, path)

        threading.Thread(target=work, daemon=True).start()

    def _play_narration(self, path):
        if not self.film.is_active():        # közben leállt → eldobjuk
            self._safe_del(path)
            self._narration_done()
            return
        self._cur_temp = path
        self.film.set_volume(self._film_vol * DUCK)     # film halkítása
        self.narr.play(path)

    def _on_narr_state(self, s):
        if s.startswith("vége") or s.startswith("hiba"):
            self._narration_done()

    def _narration_done(self):
        self.film.set_volume(self._film_vol)            # film vissza
        if self._cur_temp:
            self._safe_del(self._cur_temp)
            self._cur_temp = None
        self._narrating = False

    @staticmethod
    def _safe_del(path):
        try:
            os.remove(path)
        except OSError:
            pass

    def _on_film_state(self, s):
        if s.startswith("vége"):
            self.timer.Stop()
            self._announce("A média véget ért.")
        elif s.startswith("hiba"):
            self.timer.Stop()
            self._announce(s)

    # ---- billentyűk / súgó / zárás ------------------------------------

    def _on_key(self, e):
        code = e.GetKeyCode()
        if code == wx.WXK_F1:
            self._help()
        elif code == wx.WXK_SPACE and not isinstance(
                self.FindFocus(), (wx.TextCtrl,)):
            self._toggle()
        elif code == wx.WXK_LEFT and e.ControlDown() is False \
                and isinstance(self.FindFocus(), wx.Choice) is False:
            self._seek(-10)
        elif code == wx.WXK_RIGHT and isinstance(self.FindFocus(),
                                                 wx.Choice) is False:
            self._seek(10)
        elif code == wx.WXK_ESCAPE:
            self._stop()
        else:
            e.Skip()

    def _help(self):
        try:
            from superdl.helpdialog import show_help
            show_help(self, "Felirat-felolvasó lejátszó", HELP)
        except Exception:
            wx.MessageBox(HELP, "Súgó – Felirat-felolvasó",
                          wx.OK | wx.ICON_INFORMATION, self)

    def _on_close(self, e):
        try:
            self.timer.Stop()
            self.narr.stop()
            self.film.stop()
        except Exception:
            pass
        if getattr(self.main, "_felolvaso_win", None) is self:
            self.main._felolvaso_win = None
        self.Destroy()
