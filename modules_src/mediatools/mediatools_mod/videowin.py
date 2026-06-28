"""Videókészítő képből és zenéből: idővonalas, vakbarát szerkesztő.

Folyamat: (1) háttérkép + zene kiválasztása, (2) a zene lejátszása SZÓKÖZZEL
(megálláskor bemondja a pontos időpontot), (3) az aktuális időponthoz szöveg
vagy kép beszúrása (gombbal vagy a lista helyi menüjéből), (4) a beszúrt
elemek listája nyilakkal bejárható, Delete-tel törölhető, (5) mentés:
formátum + fájl, majd ffmpeg render folyamatjelzéssel. A renderelést a
videocompose modul végzi.
"""

import os
import threading
from pathlib import Path

import wx

from superdl import sounds                  # megosztott Core-modulok
from superdl import videocompose as VC
from superdl.audioengine import Player

IMAGE_WILDCARD = ("Képek (*.jpg;*.jpeg;*.png;*.bmp;*.gif;*.webp)|"
                  "*.jpg;*.jpeg;*.png;*.bmp;*.gif;*.webp|Minden fájl|*.*")
AUDIO_WILDCARD = ("Hang (*.mp3;*.m4a;*.wav;*.flac;*.ogg;*.opus;*.aac)|"
                  "*.mp3;*.m4a;*.wav;*.flac;*.ogg;*.opus;*.aac|Minden fájl|*.*")
SAVE_FORMATS = [("MP4 – ajánlott, mindenhol lejátszható", "mp4"),
                ("MKV", "mkv"), ("AVI", "avi")]


class VideoComposeFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main,
                         title="SuperDL – Videókészítő képből és zenéből",
                         size=(840, 620))
        self.main = main
        self.background = ""
        self.music = ""
        self.elements: list[VC.Element] = []
        self.player = Player()
        self.player.on_state = lambda s: wx.CallAfter(self._player_state, s)
        self._rendering = False
        self._composer = None

        self._build()
        self.CreateStatusBar()
        self._announce("Válaszd ki a háttérképet és a zenét, majd Tovább.")
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.Bind(wx.EVT_CLOSE, self._on_close)

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        self.panel = wx.Panel(self)
        self.outer = wx.BoxSizer(wx.VERTICAL)
        self._build_setup()
        self._build_edit()
        self.edit_panel.Hide()
        self.panel.SetSizer(self.outer)

    def _build_setup(self):
        self.setup_panel = wx.Panel(self.panel)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(
            self.setup_panel,
            label="1. lépés: válaszd ki a HÁTTÉRKÉPET és a ZENÉT."),
            0, wx.ALL, 8)

        self.bg_txt = wx.TextCtrl(self.setup_panel, style=wx.TE_READONLY)
        self.bg_txt.SetName("Kiválasztott háttérkép")
        bg_btn = wx.Button(self.setup_panel, label="&Háttérkép kiválasztása…")
        bg_btn.Bind(wx.EVT_BUTTON, lambda e: self._pick_background())
        r1 = wx.BoxSizer(wx.HORIZONTAL)
        r1.Add(self.bg_txt, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        r1.Add(bg_btn, 0)
        v.Add(r1, 0, wx.EXPAND | wx.ALL, 8)

        self.mus_txt = wx.TextCtrl(self.setup_panel, style=wx.TE_READONLY)
        self.mus_txt.SetName("Kiválasztott zene")
        mus_btn = wx.Button(self.setup_panel, label="&Zene kiválasztása…")
        mus_btn.Bind(wx.EVT_BUTTON, lambda e: self._pick_music())
        r2 = wx.BoxSizer(wx.HORIZONTAL)
        r2.Add(self.mus_txt, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        r2.Add(mus_btn, 0)
        v.Add(r2, 0, wx.EXPAND | wx.ALL, 8)

        self.next_btn = wx.Button(self.setup_panel, label="&Tovább a szerkesztéshez")
        self.next_btn.Bind(wx.EVT_BUTTON, lambda e: self._go_edit())
        self.next_btn.Disable()
        v.Add(self.next_btn, 0, wx.ALL, 8)

        self.setup_panel.SetSizer(v)
        self.outer.Add(self.setup_panel, 1, wx.EXPAND)

    def _build_edit(self):
        self.edit_panel = wx.Panel(self.panel)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(
            self.edit_panel,
            label="2. lépés: SZÓKÖZ = lejátszás/szünet. Szünetben add hozzá a "
                  "szöveget vagy a képet az aktuális időponthoz."),
            0, wx.ALL, 8)

        # vezérlőgombok
        b1 = wx.BoxSizer(wx.HORIZONTAL)
        self.play_btn = wx.Button(self.edit_panel, label="&Lejátszás / szünet (Szóköz)")
        self.play_btn.Bind(wx.EVT_BUTTON, lambda e: self._toggle_play())
        self.time_btn = wx.Button(self.edit_panel, label="Pillanatnyi &időpont")
        self.time_btn.Bind(wx.EVT_BUTTON, lambda e: self._announce_time())
        self.restart_btn = wx.Button(self.edit_panel, label="&Vissza az elejére")
        self.restart_btn.Bind(wx.EVT_BUTTON, lambda e: self._restart())
        for b in (self.play_btn, self.time_btn, self.restart_btn):
            b1.Add(b, 0, wx.RIGHT, 6)
        v.Add(b1, 0, wx.ALL, 6)

        b2 = wx.BoxSizer(wx.HORIZONTAL)
        self.addtext_btn = wx.Button(self.edit_panel, label="&Szöveg hozzáadása itt…")
        self.addtext_btn.Bind(wx.EVT_BUTTON, lambda e: self._add_text())
        self.addimg_btn = wx.Button(self.edit_panel, label="&Kép hozzáadása itt…")
        self.addimg_btn.Bind(wx.EVT_BUTTON, lambda e: self._add_image())
        for b in (self.addtext_btn, self.addimg_btn):
            b2.Add(b, 0, wx.RIGHT, 6)
        v.Add(b2, 0, wx.ALL, 6)

        # elem-lista
        v.Add(wx.StaticText(self.edit_panel,
              label="Beszúrt elemek (időpont szerint):"), 0, wx.LEFT | wx.TOP, 8)
        self.list = wx.ListCtrl(self.edit_panel,
                                style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
                                name="Jelenetek")
        self.list.InsertColumn(0, "Időpont", width=90)
        self.list.InsertColumn(1, "Típus", width=80)
        self.list.InsertColumn(2, "Tartalom", width=460)
        self.list.Bind(wx.EVT_KEY_DOWN, self._on_list_key)
        self.list.Bind(wx.EVT_CONTEXT_MENU, self._on_list_menu)
        v.Add(self.list, 1, wx.EXPAND | wx.ALL, 8)

        # mentés + folyamatjelző
        b3 = wx.BoxSizer(wx.HORIZONTAL)
        self.del_btn = wx.Button(self.edit_panel, label="Kijelölt elem &törlése (Delete)")
        self.del_btn.Bind(wx.EVT_BUTTON, lambda e: self._delete_selected())
        self.save_btn = wx.Button(self.edit_panel, label="Videó &mentése…")
        self.save_btn.Bind(wx.EVT_BUTTON, lambda e: self._save())
        b3.Add(self.del_btn, 0, wx.RIGHT, 6)
        b3.Add(self.save_btn, 0)
        v.Add(b3, 0, wx.ALL, 6)

        self.gauge = wx.Gauge(self.edit_panel, range=100)
        v.Add(self.gauge, 0, wx.EXPAND | wx.ALL, 8)

        self.edit_panel.SetSizer(v)
        self.outer.Add(self.edit_panel, 1, wx.EXPAND)

    # ---- 1. lépés: fájlválasztás --------------------------------------

    def _pick_background(self):
        dlg = wx.FileDialog(self, "Háttérkép kiválasztása",
                            wildcard=IMAGE_WILDCARD,
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.background = dlg.GetPath()
            self.bg_txt.SetValue(self.background)
            self._announce(f"Háttérkép: {Path(self.background).name}")
            self._update_next()
        dlg.Destroy()

    def _pick_music(self):
        dlg = wx.FileDialog(self, "Zene kiválasztása",
                            wildcard=AUDIO_WILDCARD,
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.music = dlg.GetPath()
            self.mus_txt.SetValue(self.music)
            self._announce(f"Zene: {Path(self.music).name}")
            self._update_next()
        dlg.Destroy()

    def _update_next(self):
        self.next_btn.Enable(bool(self.background and self.music))

    def _go_edit(self):
        if not (self.background and self.music):
            return
        self.setup_panel.Hide()
        self.edit_panel.Show()
        self.outer.Layout()
        dur = VC.media_duration(self.music)
        self._announce(
            f"Szerkesztés. A zene hossza {VC.human_time(dur)}. "
            "Nyomd meg a Szóközt a lejátszáshoz.")
        self.play_btn.SetFocus()

    # ---- 2. lépés: lejátszás + időpont --------------------------------

    def _toggle_play(self):
        if self.player.is_active():
            paused = self.player.toggle_pause()
            if paused:
                self._announce(f"Szünet itt: {self._pos_str()}. "
                               "Hozzáadhatsz szöveget vagy képet.")
            else:
                self._announce("Lejátszás.")
        else:
            self.player.play(self.music, title=Path(self.music).name)

    def _restart(self):
        self.player.play(self.music, title=Path(self.music).name)
        self._announce("Lejátszás az elejéről.")

    def _position(self) -> float:
        return self.player.position() if self.player.is_active() else 0.0

    def _pos_str(self) -> str:
        return VC.human_time(self._position())

    def _announce_time(self):
        if self.player.is_active():
            self._announce(f"Pillanatnyi időpont: {self._pos_str()}.")
        else:
            self._announce("A lejátszás áll. Szóköz: lejátszás.")

    def _player_state(self, text: str):
        if text == "vége":
            self._announce("A zene véget ért. Vissza az elejére: a megfelelő "
                           "gomb, vagy Szóköz az újrajátszáshoz.")
        elif text.startswith("hiba"):
            self._announce(f"Lejátszási hiba: {text}.")

    # ---- elem hozzáadása / törlése ------------------------------------

    def _add_text(self):
        pos = self._position()
        dlg = wx.TextEntryDialog(
            self, f"A megjelenítendő szöveg (időpont: {VC.human_time(pos)}):",
            "Szöveg hozzáadása")
        if dlg.ShowModal() == wx.ID_OK:
            txt = dlg.GetValue().strip()
            if txt:
                self._add_element(VC.Element(pos, "text", txt))
        dlg.Destroy()

    def _add_image(self):
        pos = self._position()
        dlg = wx.FileDialog(self, "Beszúrandó kép kiválasztása",
                            wildcard=IMAGE_WILDCARD,
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self._add_element(VC.Element(pos, "image", dlg.GetPath()))
        dlg.Destroy()

    def _add_element(self, el: VC.Element):
        self.elements.append(el)
        self.elements.sort(key=lambda e: e.at)
        self._refresh_list(select=self.elements.index(el))
        self._announce(f"Hozzáadva: {el.label()}")

    def _refresh_list(self, select: int = -1):
        self.list.DeleteAllItems()
        for el in self.elements:
            row = self.list.InsertItem(self.list.GetItemCount(),
                                       VC.human_time(el.at))
            self.list.SetItem(row, 1,
                              "Szöveg" if el.kind == "text" else "Kép")
            self.list.SetItem(
                row, 2,
                el.content if el.kind == "text" else Path(el.content).name)
        if 0 <= select < self.list.GetItemCount():
            self.list.Select(select)
            self.list.Focus(select)

    def _on_list_key(self, e):
        if e.GetKeyCode() == wx.WXK_DELETE:
            self._delete_selected()
        else:
            e.Skip()

    def _on_list_menu(self, e):
        m = wx.Menu()
        mi_t = m.Append(wx.ID_ANY, "&Szöveg hozzáadása az aktuális időponthoz…")
        mi_i = m.Append(wx.ID_ANY, "&Kép hozzáadása az aktuális időponthoz…")
        m.AppendSeparator()
        mi_d = m.Append(wx.ID_ANY, "Kijelölt elem &törlése")
        self.Bind(wx.EVT_MENU, lambda e: self._add_text(), mi_t)
        self.Bind(wx.EVT_MENU, lambda e: self._add_image(), mi_i)
        self.Bind(wx.EVT_MENU, lambda e: self._delete_selected(), mi_d)
        self.list.PopupMenu(m)
        m.Destroy()

    def _delete_selected(self):
        i = self.list.GetFirstSelected()
        if 0 <= i < len(self.elements):
            el = self.elements.pop(i)
            self._refresh_list(select=min(i, len(self.elements) - 1))
            self._announce(f"Törölve: {el.label()}")

    # ---- mentés / renderelés ------------------------------------------

    def _save(self):
        if self._rendering:
            self._announce("A renderelés már folyamatban van.")
            return
        if not (self.background and self.music):
            self._announce("Hiányzik a háttérkép vagy a zene.")
            return
        fmt_dlg = wx.SingleChoiceDialog(
            self, "Válaszd ki a kimeneti formátumot:", "Videó mentése",
            [name for name, _ in SAVE_FORMATS])
        if fmt_dlg.ShowModal() != wx.ID_OK:
            fmt_dlg.Destroy()
            return
        fmt = SAVE_FORMATS[fmt_dlg.GetSelection()][1]
        fmt_dlg.Destroy()

        save = wx.FileDialog(
            self, "Videó mentése másként", wildcard=f"*.{fmt}|*.{fmt}",
            defaultFile=f"sajat_videom.{fmt}",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if save.ShowModal() != wx.ID_OK:
            save.Destroy()
            return
        out = save.GetPath()
        if not out.lower().endswith("." + fmt):
            out += "." + fmt
        save.Destroy()

        self._start_render(out, fmt)

    def _sv(self, key, state):
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            sv.announce(key, state)

    def _start_render(self, out: str, fmt: str):
        self._rendering = True
        self.save_btn.Disable()
        self._beeper = sounds.ProgressBeeper()
        self._sv("video", "start")
        self._announce("Renderelés indul… ez a zene hosszától függően eltarthat "
                       "egy darabig.")
        self._composer = VC.VideoComposer(
            self.background, self.music, self.elements, out, fmt=fmt,
            progress=lambda p: wx.CallAfter(self._render_progress, p))
        self._last_pct = -10

        def work():
            ok = self._composer.render()
            wx.CallAfter(self._render_done, ok, out)

        threading.Thread(target=work, daemon=True).start()

    def _render_progress(self, p: float):
        pct = int(p * 100)
        self.gauge.SetValue(min(100, pct))
        self._beeper.update(pct)
        if pct >= self._last_pct + 10:
            self._last_pct = pct
            self._announce(f"Renderelés: {pct}%.")

    def _render_done(self, ok: bool, out: str):
        self._rendering = False
        self.save_btn.Enable()
        self.gauge.SetValue(100 if ok else 0)
        self._sv("video", "done" if ok else "error")
        if ok:
            self._announce(f"Kész! A videó elmentve: {out}")
            if wx.MessageBox(
                    f"A videó elkészült:\n{out}\n\nMegnyitod a tartalmazó "
                    "mappát?", "Videó kész",
                    wx.YES_NO | wx.ICON_INFORMATION, self) == wx.YES:
                try:
                    os.startfile(str(Path(out).parent))
                except OSError:
                    pass
        else:
            err = self._composer.error if self._composer else "ismeretlen hiba"
            self._announce(f"A renderelés nem sikerült: {err}")
            wx.MessageBox(err, "Renderelési hiba",
                          wx.OK | wx.ICON_ERROR, self)

    # ---- billentyű + zárás --------------------------------------------

    def _on_char_hook(self, e):
        focus = wx.Window.FindFocus()
        # Szóköz = lejátszás/szünet, kivéve szövegmezőben vagy gombon
        if (e.GetKeyCode() == wx.WXK_SPACE
                and not isinstance(focus, wx.TextCtrl)
                and not isinstance(focus, wx.Button)
                and self.edit_panel.IsShown()):
            self._toggle_play()
            return
        e.Skip()

    def _announce(self, text: str):
        self.SetStatusText(text)

    def _on_close(self, e):
        try:
            self.player.stop()
        except Exception:
            pass
        if self._composer:
            self._composer.stop()
        self.main._video_win = None
        self.Destroy()
