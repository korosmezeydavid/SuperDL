"""Videóvágó és -összefűző ablak: vakbarát, „füllel vágás".

A videó HANGJÁT játssza le; Szóköz megállít. A pillanatnyi időponthoz marker
vagy MAGYARÁZÓ SZÖVEG tehető (a szöveg a kimenetre ráég). Két marker közötti
SZAKASZ menthető, vagy a teljes (akár több videóból összefűzött) anyag.
"""

import os
import threading
from pathlib import Path

import wx

from . import videoedit as VE
from .audioengine import Player

VIDEO_WILDCARD = ("Videók (*.mp4;*.mkv;*.avi;*.mov;*.webm;*.m4v)|"
                  "*.mp4;*.mkv;*.avi;*.mov;*.webm;*.m4v|Minden fájl|*.*")


class VideoEditFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Videóvágó és összefűző",
                         size=(880, 640))
        self.main = main
        self.editor = VE.VideoEditor()
        self.player = Player()
        self.player.on_state = lambda s: wx.CallAfter(self._player_state, s)
        self._rendering = False

        self._build()
        self.CreateStatusBar()
        self._announce("Tölts be egy videót. A Szóköz lejátssza/megállítja a "
                       "hangját; megállva tehetsz markert vagy szöveget.")
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.Bind(wx.EVT_CLOSE, self._on_close)

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        top = wx.BoxSizer(wx.HORIZONTAL)
        b_load = wx.Button(p, label="Videó &betöltése…")
        b_load.Bind(wx.EVT_BUTTON, lambda e: self._load_video())
        self.title_lbl = wx.StaticText(p, label="Nincs betöltött videó.")
        top.Add(b_load, 0, wx.RIGHT, 8)
        top.Add(self.title_lbl, 1, wx.ALIGN_CENTER_VERTICAL)
        v.Add(top, 0, wx.EXPAND | wx.ALL, 8)

        v.Add(wx.StaticText(p, label="SZÓKÖZ: lejátszás/megállás. Megállva: "
              "marker vagy magyarázó szöveg. Finomhangolás: bal/jobb nyíl."),
              0, wx.ALL, 8)

        c1 = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (
                ("&Lejátszás / megállás (Szóköz)", lambda e: self._toggle()),
                ("Vissza az &elejére", lambda e: self._restart()),
                ("Pillanatnyi &időpont", lambda e: self._say_time()),
                ("◄ −2 mp", lambda e: self._fine(-2.0)),
                ("+2 mp ►", lambda e: self._fine(2.0))):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            c1.Add(b, 0, wx.RIGHT, 5)
        v.Add(c1, 0, wx.ALL, 6)

        c2 = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (
                ("&Marker hozzáadása itt", lambda e: self._add_marker()),
                ("&Szöveg hozzáadása itt…", lambda e: self._add_note()),
                ("Videó &hozzáfűzése…", lambda e: self._append_video())):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            c2.Add(b, 0, wx.RIGHT, 5)
        v.Add(c2, 0, wx.ALL, 6)

        lists = wx.BoxSizer(wx.HORIZONTAL)
        lv = wx.BoxSizer(wx.VERTICAL)
        lv.Add(wx.StaticText(p, label="Mar&kerek (Delete: törlés). A „Szakasz "
               "mentése” a kijelölt és a következő marker közt ment:"),
               0, wx.LEFT | wx.TOP, 6)
        self.mk_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.mk_list.InsertColumn(0, "Marker időpont", width=180)
        self.mk_list.Bind(wx.EVT_KEY_DOWN, self._on_mk_key)
        lv.Add(self.mk_list, 1, wx.EXPAND | wx.ALL, 4)
        lists.Add(lv, 1, wx.EXPAND)

        nv = wx.BoxSizer(wx.VERTICAL)
        nv.Add(wx.StaticText(p, label="Magyarázó szöve&gek (Delete: törlés):"),
               0, wx.LEFT | wx.TOP, 6)
        self.nt_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.nt_list.InsertColumn(0, "Időpont", width=90)
        self.nt_list.InsertColumn(1, "Szöveg", width=300)
        self.nt_list.Bind(wx.EVT_KEY_DOWN, self._on_nt_key)
        nv.Add(self.nt_list, 1, wx.EXPAND | wx.ALL, 4)
        lists.Add(nv, 1, wx.EXPAND)
        v.Add(lists, 1, wx.EXPAND | wx.ALL, 6)

        s = wx.BoxSizer(wx.HORIZONTAL)
        b_sec = wx.Button(p, label="S&zakasz mentése…")
        b_sec.Bind(wx.EVT_BUTTON, lambda e: self._save_section())
        b_all = wx.Button(p, label="&Teljes videó mentése…")
        b_all.Bind(wx.EVT_BUTTON, lambda e: self._save_whole())
        s.Add(b_sec, 0, wx.RIGHT, 6)
        s.Add(b_all, 0)
        v.Add(s, 0, wx.ALL, 6)
        self.gauge = wx.Gauge(p, range=100)
        v.Add(self.gauge, 0, wx.EXPAND | wx.ALL, 8)

        p.SetSizer(v)

    # ---- betöltés / lejátszás -----------------------------------------

    def _pick_video(self, title):
        dlg = wx.FileDialog(self, title, wildcard=VIDEO_WILDCARD,
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        path = dlg.GetPath() if dlg.ShowModal() == wx.ID_OK else ""
        dlg.Destroy()
        return path

    def _load_video(self):
        path = self._pick_video("Videó betöltése")
        if not path:
            return
        self.player.stop()
        self.editor = VE.VideoEditor()
        self._announce("Videó vizsgálata…")

        def work():
            clip = self.editor.add_clip(path)
            wx.CallAfter(self._loaded, clip, path)

        threading.Thread(target=work, daemon=True).start()

    def _loaded(self, clip, path):
        if not clip:
            self._announce("Ezt a videót nem sikerült beolvasni.")
            return
        self.title_lbl.SetLabel(f"Videó: {Path(path).name} "
                                f"({VE.human_time(clip.duration)})")
        self._refresh_markers()
        self._refresh_notes()
        self._announce(f"Betöltve, hossza {VE.human_time(clip.duration)}. "
                       "Szóköz: a hang lejátszása.")

    def _append_video(self):
        if not self.editor.clips:
            self._announce("Előbb tölts be egy videót.")
            return
        path = self._pick_video("Videó hozzáfűzése a végéhez")
        if not path:
            return

        def work():
            clip = self.editor.add_clip(path)
            wx.CallAfter(self._appended, clip)

        threading.Thread(target=work, daemon=True).start()

    def _appended(self, clip):
        if not clip:
            self._announce("Ezt a videót nem sikerült hozzáfűzni.")
            return
        self._announce(f"Hozzáfűzve: {Path(clip.path).name}. Teljes hossz most "
                       f"{VE.human_time(self.editor.total_duration())}.")

    def _main_clip(self):
        return self.editor.clips[0].path if self.editor.clips else ""

    def _toggle(self):
        if not self.editor.clips:
            self._announce("Előbb tölts be egy videót.")
            return
        if self.player.is_active():
            paused = self.player.toggle_pause()
            self._announce(f"Megállítva itt: {self._pos_str()}." if paused
                           else "Lejátszás.")
        else:
            self.player.play(self._main_clip(), title="videó")

    def _restart(self):
        if self.editor.clips:
            self.player.play(self._main_clip(), title="videó")
            self._announce("Lejátszás az elejéről.")

    def _position(self) -> float:
        return self.player.position() if self.player.is_active() else 0.0

    def _pos_str(self) -> str:
        return VE.human_time(self._position())

    def _say_time(self):
        if self.player.is_active():
            self._announce(f"Pillanatnyi időpont: {self._pos_str()}.")
        else:
            self._announce("A lejátszás áll. Szóköz: lejátszás.")

    def _fine(self, delta):
        if not self.player.is_active():
            self._announce("Előbb játszd le és állítsd meg a hangot.")
            return
        self.player.relative_seek(delta)
        self._announce(f"Léptetve ide: {self._pos_str()}. (A pontos vágáshoz "
                       "hallgasd vissza, majd tegyél markert.)")

    def _player_state(self, text):
        if text == "vége":
            self._announce("A hang vége. Vissza az elejére vagy Szóköz.")
        elif text.startswith("hiba"):
            self._announce(f"Lejátszási hiba: {text}.")

    # ---- markerek / szövegek ------------------------------------------

    def _add_marker(self):
        if not self.editor.clips:
            return
        at = self._position()
        self.editor.add_marker(at)
        self._refresh_markers(select_at=at)
        self._announce(f"Marker hozzáadva: {VE.human_time(at)}.")

    def _add_note(self):
        if not self.editor.clips:
            return
        at = self._position()
        dlg = wx.TextEntryDialog(
            self, f"A megjelenítendő magyarázó szöveg (időpont: "
            f"{VE.human_time(at)}):", "Magyarázó szöveg hozzáadása")
        if dlg.ShowModal() == wx.ID_OK:
            txt = dlg.GetValue().strip()
            if txt:
                self.editor.add_note(at, txt)
                self._refresh_notes()
                self._announce(f"Szöveg hozzáadva {VE.human_time(at)}-nál: "
                               f"{txt}")
        dlg.Destroy()

    def _refresh_markers(self, select_at=None):
        self.mk_list.DeleteAllItems()
        sel = -1
        for i, m in enumerate(self.editor.markers):
            self.mk_list.InsertItem(i, VE.human_time(m.at))
            if select_at is not None and abs(m.at - select_at) < 0.01:
                sel = i
        if sel >= 0:
            self.mk_list.Select(sel)
            self.mk_list.Focus(sel)

    def _refresh_notes(self):
        self.nt_list.DeleteAllItems()
        for i, n in enumerate(self.editor.notes):
            self.nt_list.InsertItem(i, VE.human_time(n.at))
            self.nt_list.SetItem(i, 1, n.text)

    def _on_mk_key(self, e):
        if e.GetKeyCode() == wx.WXK_DELETE:
            i = self.mk_list.GetFirstSelected()
            if i >= 0:
                self.editor.remove_marker(i)
                self._refresh_markers()
                self._announce("Marker törölve.")
        else:
            e.Skip()

    def _on_nt_key(self, e):
        if e.GetKeyCode() == wx.WXK_DELETE:
            i = self.nt_list.GetFirstSelected()
            if i >= 0:
                self.editor.remove_note(i)
                self._refresh_notes()
                self._announce("Szöveg törölve.")
        else:
            e.Skip()

    # ---- mentés -------------------------------------------------------

    def _ask_format_and_path(self, default_stem):
        dlg = wx.SingleChoiceDialog(self, "Kimeneti formátum:", "Mentés",
                                    [n for n, _ in VE.OUT_FORMATS])
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return None
        fmt = VE.OUT_FORMATS[dlg.GetSelection()][1]
        dlg.Destroy()
        save = wx.FileDialog(self, "Mentés másként", wildcard=f"*.{fmt}|*.{fmt}",
                             defaultFile=f"{default_stem}.{fmt}",
                             style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        out = save.GetPath() if save.ShowModal() == wx.ID_OK else ""
        save.Destroy()
        if out and not out.lower().endswith("." + fmt):
            out += "." + fmt
        return out or None

    def _save_section(self):
        if self._rendering:
            return
        mk = self.editor.markers
        i = self.mk_list.GetFirstSelected()
        if len(mk) < 2 or i < 0 or i + 1 >= len(mk):
            self._announce("A szakasz-mentéshez jelölj ki egy markert, és "
                           "legyen utána még egy (a kettő közti rész menti).")
            return
        start, end = mk[i].at, mk[i + 1].at
        out = self._ask_format_and_path("szakasz")
        if out:
            self._start_export(start, end, out,
                               f"Szakasz mentése {VE.human_time(start)}–"
                               f"{VE.human_time(end)}…")

    def _save_whole(self):
        if self._rendering or not self.editor.clips:
            if not self.editor.clips:
                self._announce("Előbb tölts be egy videót.")
            return
        out = self._ask_format_and_path("teljes_videó")
        if out:
            self._start_export(0.0, self.editor.total_duration(), out,
                               "A teljes videó mentése…")

    def _sv(self, key, state):
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            sv.announce(key, state)

    def _start_export(self, start, end, out, msg):
        self._rendering = True
        self.player.stop()
        self._sv("video", "start")
        self.gauge.SetValue(0)
        self._last_pct = -10
        self._announce(msg + " Ez eltarthat egy darabig.")

        def work():
            ok = self.editor.export(
                start, end, out,
                progress=lambda p: wx.CallAfter(self._export_progress, p))
            wx.CallAfter(self._export_done, ok, out)

        threading.Thread(target=work, daemon=True).start()

    def _export_progress(self, p):
        pct = int(p * 100)
        self.gauge.SetValue(min(100, pct))
        if pct >= self._last_pct + 10:
            self._last_pct = pct
            self._announce(f"Mentés: {pct}%.")

    def _export_done(self, ok, out):
        self._rendering = False
        self.gauge.SetValue(100 if ok else 0)
        self._sv("video", "done" if ok else "error")
        if ok:
            self._announce(f"Kész! Elmentve: {out}")
            if wx.MessageBox(f"Elkészült:\n{out}\n\nMegnyitod a mappát?",
                             "Videó kész", wx.YES_NO | wx.ICON_INFORMATION,
                             self) == wx.YES:
                try:
                    os.startfile(str(Path(out).parent))
                except OSError:
                    pass
        else:
            self._announce(f"A mentés nem sikerült: {self.editor.error}")
            wx.MessageBox(self.editor.error or "ismeretlen hiba",
                          "Hiba", wx.OK | wx.ICON_ERROR, self)

    # ---- billentyű + zárás --------------------------------------------

    def _on_char_hook(self, e):
        focus = wx.Window.FindFocus()
        if isinstance(focus, wx.TextCtrl):
            e.Skip()
            return
        code = e.GetKeyCode()
        if code == wx.WXK_SPACE and not isinstance(focus, wx.Button):
            self._toggle()
            return
        if code == wx.WXK_LEFT:
            self._fine(-2.0)
            return
        if code == wx.WXK_RIGHT:
            self._fine(2.0)
            return
        e.Skip()

    def _announce(self, text):
        self.SetStatusText(text)

    def _on_close(self, e):
        try:
            self.player.stop()
            self.editor.stop()
            self.editor.cleanup()
        except Exception:
            pass
        if getattr(self.main, "_videoedit_win", None) is self:
            self.main._videoedit_win = None
        self.Destroy()
