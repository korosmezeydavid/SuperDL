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


HELP = """VIDEÓKÉSZÍTŐ (kép + zene)

MIRE VALÓ
Videó egy képből vagy képsorozatból és zenéből. A műveletek az Alt-menüben
vannak. A Tab a jelenetek listáját járja.

LÉPÉSEK
Alt+B Betöltés: képek a zenébe, háttérkép, zene, tovább a szerkesztéshez.
A szerkesztésben a Szóköz lejátssza vagy megállítja a zenét.
Bal és jobb nyíl: lépés, alapból 2 másodperc.
Ctrl+nyíl: a lépésköz 0,1 és 10 másodperc között.
Shift+nyíl: kijelöli az időtartományt, és bemondja.
Alt+S: szöveg vagy kép az aktuális időpontra. A listában a kijelölt elemet
Ctrl+C másolja, Ctrl+X kivágja, Ctrl+V az aktuális időpontra illeszti.
Delete töröl. Alt+S, Videó mentése kéri a formátumot és a helyet.
F1 súgó.  Alt+F4 vagy Alt+B, Kilépés bezárja az ablakot."""


class VideoComposeFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main,
                         title="SuperDL – Videókészítő képből és zenéből",
                         size=(840, 620))
        self.main = main
        self.background = ""
        self.music = ""
        self.slideshow: tuple[str, ...] = ()
        self.duration = 0.0
        self.elements: list[VC.Element] = []
        self.player = Player()
        self._closing = False        # zárás alatt a háttér-callbackek kilépnek
        self.player.on_state = lambda s: wx.CallAfter(self._player_state, s)
        self._rendering = False
        self._composer = None
        self._pos = 0.0
        self._step = 2.0
        self._anchor = None
        self._sel = None
        self._clip_el = None

        self._build()
        self._build_menu()
        self.CreateStatusBar()
        self._announce("Válassz képeket vagy háttérképet, majd zenét.")
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
            label="1. lépés: válassz képeket vagy háttérképet, majd zenét."),
            0, wx.ALL, 8)

        v.Add(wx.StaticText(
            self.setup_panel,
            label="Alt+B: képek, háttérkép, zene, majd tovább a szerkesztéshez."),
            0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.bg_txt = wx.StaticText(self.setup_panel, label="Nincs kép.")
        self.bg_txt.SetName("Kiválasztott képek vagy háttérkép")
        v.Add(self.bg_txt, 0, wx.EXPAND | wx.ALL, 8)
        self.mus_txt = wx.StaticText(self.setup_panel, label="Nincs zene.")
        self.mus_txt.SetName("Kiválasztott zene")
        v.Add(self.mus_txt, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.setup_panel.SetSizer(v)
        self.outer.Add(self.setup_panel, 1, wx.EXPAND)

    def _build_edit(self):
        self.edit_panel = wx.Panel(self.panel)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(
            self.edit_panel,
            label="Szóköz: lejátszás. Nyíl: lépés. Shift+nyíl: kijelölés. "
                  "Ctrl+nyíl: lépésköz. Alt+S: szöveg, kép, másolás, mentés."),
            0, wx.ALL, 8)

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

        self.gauge = wx.Gauge(self.edit_panel, range=100)
        v.Add(self.gauge, 0, wx.EXPAND | wx.ALL, 8)

        self.edit_panel.SetSizer(v)
        self.outer.Add(self.edit_panel, 1, wx.EXPAND)

    def _build_menu(self):
        bar = wx.MenuBar()

        def mi(menu, label, fn):
            item = menu.Append(wx.ID_ANY, label)
            self.Bind(wx.EVT_MENU, lambda e, f=fn: f(), item)
            return item

        betolt = wx.Menu()
        self.slides_item = betolt.Append(wx.ID_ANY, "Képek &beillesztése a zenébe…")
        self.Bind(wx.EVT_MENU, lambda e: self._pick_slideshow(), self.slides_item)
        self.mi_bg = mi(betolt, "&Háttérkép kiválasztása…", self._pick_background)
        self.mi_music = mi(betolt, "&Zene kiválasztása…", self._pick_music)
        betolt.AppendSeparator()
        self.mi_next = mi(betolt, "&Tovább a szerkesztéshez", self._go_edit)
        self.mi_next.Enable(False)
        betolt.AppendSeparator()
        mi(betolt, "&Kilépés\tAlt+F4", self.Close)
        bar.Append(betolt, "&Betöltés")

        lejatszas = wx.Menu()
        mi(lejatszas, "&Lejátszás / szünet", self._toggle_play)
        mi(lejatszas, "Pillanatnyi &időpont", self._announce_time)
        mi(lejatszas, "&Vissza az elejére", self._restart)
        bar.Append(lejatszas, "&Lejátszás")

        szerk = wx.Menu()
        mi(szerk, "&Szöveg hozzáadása itt…", self._add_text)
        mi(szerk, "&Kép hozzáadása itt…", self._add_image)
        mi(szerk, "Kijelölt elem &törlése", self._delete_selected)
        szerk.AppendSeparator()
        mi(szerk, "Más&olás\tCtrl+C", self._copy_element)
        mi(szerk, "Ki&vágás\tCtrl+X", self._cut_element)
        mi(szerk, "&Beillesztés\tCtrl+V", self._paste_element)
        szerk.AppendSeparator()
        self.mi_save = mi(szerk, "Videó &mentése…", self._save)
        bar.Append(szerk, "&Szerkesztés")
        self.SetMenuBar(bar)

    # ---- 1. lépés: fájlválasztás --------------------------------------

    def _pick_slideshow(self):
        if not self.setup_panel.IsShown():
            return
        with wx.FileDialog(self, "Képek beillesztése a zenébe",
                           wildcard=IMAGE_WILDCARD,
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            self.slideshow = tuple(dlg.GetPaths())
        self.background = ""
        self.bg_txt.SetLabel("; ".join(Path(p).name for p in self.slideshow))
        self._announce(f"{len(self.slideshow)} kép kiválasztva. A program időzíti a képeket.")
        self._update_next()

    def _pick_background(self):
        dlg = wx.FileDialog(self, "Háttérkép kiválasztása",
                            wildcard=IMAGE_WILDCARD,
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.slideshow = ()
            self.background = dlg.GetPath()
            self.bg_txt.SetLabel(Path(self.background).name)
            self._announce(f"Háttérkép: {Path(self.background).name}")
            self._update_next()
        dlg.Destroy()

    def _pick_music(self):
        dlg = wx.FileDialog(self, "Zene kiválasztása",
                            wildcard=AUDIO_WILDCARD,
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.music = dlg.GetPath()
            self.mus_txt.SetLabel(Path(self.music).name)
            self._announce(f"Zene: {Path(self.music).name}")
            self._update_next()
        dlg.Destroy()

    def _update_next(self):
        self.mi_next.Enable(bool((self.background or self.slideshow) and self.music))

    def _go_edit(self):
        if not ((self.background or self.slideshow) and self.music):
            return
        self.slides_item.Enable(False)
        self.mi_bg.Enable(False)
        self.mi_music.Enable(False)
        self.mi_next.Enable(False)
        self.setup_panel.Hide()
        self.edit_panel.Show()
        self.outer.Layout()
        self.duration = VC.media_duration(self.music)
        self._announce(
            f"Szerkesztés. A zene hossza {VC.human_time(self.duration)}. "
            "A Szóköz lejátssza. A nyíl léptet, a Shift kijelöl.")
        self.list.SetFocus()

    # ---- 2. lépés: lejátszás + időpont --------------------------------

    def _toggle_play(self):
        if not self.music:
            self._announce("Előbb válassz zenét.")
            return
        if self.player.is_active():
            paused = self.player.toggle_pause()
            self._pos = self.player.position()
            if paused:
                self._announce(f"Szünet itt: {self._pos_str()}. "
                               "Hozzáadhatsz szöveget vagy képet.")
            else:
                self._announce("Lejátszás.")
        else:
            self.player.play(self.music, title=Path(self.music).name,
                             start=max(0.0, self._pos))

    def _restart(self):
        if not self.music:
            self._announce("Előbb válassz zenét.")
            return
        self._pos = 0.0
        self._anchor = None
        self._sel = None
        self.player.play(self.music, title=Path(self.music).name)
        self._announce("Lejátszás az elejéről.")

    def _position(self) -> float:
        if self.player.is_active():
            return self.player.position()
        return self._pos

    def _pos_str(self) -> str:
        return VC.human_time(self._position())

    def _announce_time(self):
        if self.music:
            self._announce(
                f"Pillanatnyi időpont: {self._pos_str()}. "
                f"Lépés: {self._lepes_szoveg()}.")
        else:
            self._announce("Nincs zene.")

    def _lepes_szoveg(self) -> str:
        t = f"{self._step:.1f}".replace(".", ",")
        if t.endswith(",0"):
            t = t[:-2]
        return f"{t} másodperc"

    def _on_arrow(self, direction: int, ctrl: bool, shift: bool):
        if not self.edit_panel.IsShown():
            return False
        if ctrl:
            self._adjust_step(direction)
            return True
        if not self.music:
            self._announce("Előbb válassz zenét.")
            return True
        if shift:
            if self._anchor is None:
                self._anchor = self._position()
            self._move_by(direction * self._step)
            new = self._position()
            a, b = sorted((self._anchor, new))
            self._sel = (a, b) if b - a > 0.05 else None
            self._announce(
                f"Kijelölve: {VC.human_time(a)}-tól {VC.human_time(b)}-ig.")
            return True
        self._anchor = None
        self._sel = None
        self._move_by(direction * self._step)
        self._announce(
            f"Pozíció: {self._pos_str()}. Lépés: {self._lepes_szoveg()}.")
        return True

    def _move_by(self, delta: float):
        if self.player.is_active() and not self.player.is_paused():
            self.player.relative_seek(delta)
            self._pos = self.player.position()
            return
        if self.player.is_active():
            self._pos = self.player.position()
            self.player.stop()
        dur = self.duration or 0.0
        if dur <= 0:
            self._pos = 0.0
            return
        self._pos = max(0.0, min(self._pos + delta, dur))

    def _adjust_step(self, direction: int):
        nxt = round(min(10.0, max(0.1, self._step + direction * 0.1)), 1)
        if abs(nxt - self._step) < 1e-6:
            szel = "legkisebb" if direction < 0 else "legnagyobb"
            self._announce(f"A lépés {self._lepes_szoveg()}, ez a {szel}.")
            return
        self._step = nxt
        self._announce(f"Lépés: {self._lepes_szoveg()}.")

    def _player_state(self, text: str):
        if text == "vége":
            self._announce("A zene véget ért. Vissza az elejére: a megfelelő "
                           "gomb, vagy Szóköz az újrajátszáshoz.")
        elif text.startswith("hiba"):
            self._announce(f"Lejátszási hiba: {text}.")

    # ---- elem hozzáadása / törlése ------------------------------------

    def _add_text(self):
        pos = self._position()
        if self.slideshow:
            with wx.TextEntryDialog(self, "A felirat kezdete másodpercben:",
                                    "Felirat időpontja", f"{pos:.2f}") as time_dlg:
                if time_dlg.ShowModal() != wx.ID_OK:
                    return
                try:
                    pos = float(time_dlg.GetValue().replace(",", "."))
                    if not 0 <= pos < self.duration:
                        raise ValueError
                except ValueError:
                    wx.MessageBox("A kezdőpont a zeneszámon belül legyen.",
                                  "Érvénytelen időpont", wx.OK | wx.ICON_WARNING, self)
                    return
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

    def _selected_element(self):
        i = self.list.GetFirstSelected()
        if 0 <= i < len(self.elements):
            return i, self.elements[i]
        return -1, None

    def _copy_element(self):
        _i, el = self._selected_element()
        if el is None:
            self._announce("Nincs kijelölt elem a listában.")
            return
        self._clip_el = VC.Element(el.at, el.kind, el.content)
        self._announce(f"Másolva: {el.label()}")

    def _cut_element(self):
        i, el = self._selected_element()
        if el is None:
            self._announce("Nincs kijelölt elem a listában.")
            return
        self._clip_el = VC.Element(el.at, el.kind, el.content)
        self.elements.pop(i)
        self._refresh_list(select=min(i, len(self.elements) - 1))
        self._announce(f"Kivágva: {el.label()}")

    def _paste_element(self):
        if self._clip_el is None:
            self._announce("A vágólap üres.")
            return
        if not self.edit_panel.IsShown():
            self._announce("Előbb lépj tovább a szerkesztéshez.")
            return
        el = VC.Element(self._position(), self._clip_el.kind, self._clip_el.content)
        self._add_element(el)

    def _delete_selected(self):
        i = self.list.GetFirstSelected()
        if 0 <= i < len(self.elements):
            el = self.elements.pop(i)
            self._refresh_list(select=min(i, len(self.elements) - 1))
            self._announce(f"Törölve: {el.label()}")
        else:
            self._announce("Nincs kijelölt elem.")

    # ---- mentés / renderelés ------------------------------------------

    def _save(self):
        if self._rendering:
            self._announce("A renderelés már folyamatban van.")
            return
        if not ((self.background or self.slideshow) and self.music):
            self._announce("Válassz legalább egy képet és egy zeneszámot.")
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
        self.mi_save.Enable(False)
        self._beeper = sounds.ProgressBeeper()
        self._sv("video", "start")
        self._announce("Renderelés indul… ez a zene hosszától függően eltarthat "
                       "egy darabig.")
        options = {"slideshow": self.slideshow} if self.slideshow else {}
        self._composer = VC.VideoComposer(
            self.background, self.music, self.elements, out, fmt=fmt,
            progress=lambda p: wx.CallAfter(self._render_progress, p), **options)
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
        self.mi_save.Enable(True)
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

    def _help(self):
        try:
            from superdl.helpdialog import show_help
            show_help(self, "Videókészítő (kép + zene)", HELP)
        except Exception:
            wx.MessageBox(HELP, "Súgó – Videókészítő",
                          wx.OK | wx.ICON_INFORMATION, self)

    def _on_char_hook(self, e):
        if e.GetKeyCode() == wx.WXK_F1:
            self._help()
            return
        code = e.GetKeyCode()
        focus = wx.Window.FindFocus()
        if isinstance(focus, (wx.TextCtrl, wx.Slider, wx.SpinCtrl)):
            e.Skip()
            return
        if (code == wx.WXK_SPACE
                and not isinstance(focus, wx.Button)
                and self.edit_panel.IsShown()):
            self._toggle_play()
            return
        if code in (wx.WXK_LEFT, wx.WXK_RIGHT) and self.edit_panel.IsShown():
            self._on_arrow(-1 if code == wx.WXK_LEFT else 1,
                           e.ControlDown(), e.ShiftDown())
            return
        e.Skip()

    def _announce(self, text: str):
        if self._closing:
            return
        self.SetStatusText(text)

    def _on_close(self, e):
        self._closing = True
        try:
            self.player.stop()
        except Exception:
            pass
        try:
            if self._composer:
                self._composer.stop()
        except Exception:
            pass
        main = self.main
        if main is not None and getattr(main, "_video_win", None) is self:
            main._video_win = None
        self.Destroy()
