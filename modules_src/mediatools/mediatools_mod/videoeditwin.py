"""Videóvágó és -összefűző ablak: vakbarát, „füllel vágás".

A videó HANGJÁT játssza le; Szóköz megállít. A pillanatnyi időponthoz marker
vagy MAGYARÁZÓ SZÖVEG tehető (a szöveg a kimenetre ráég). Két marker közötti
SZAKASZ menthető, vagy a teljes (akár több videóból összefűzött) anyag.
"""

import math
import os
import subprocess
import tempfile
import threading
from pathlib import Path

import wx

from .videowin import AUDIO_WILDCARD, IMAGE_WILDCARD
from . import videoedit as VE               # a vágó-motor a MODULBAN
from superdl.audioengine import Player       # megosztott lejátszó a Core-ból

_VIDEO_VEGEK = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".vob",
                 ".mpg", ".mpeg", ".m2ts", ".mts", ".m2v"}

VIDEO_WILDCARD = ("Videók (*.mp4;*.mkv;*.avi;*.mov;*.webm;*.m4v;*.vob;*.mpg)|"
                  "*.mp4;*.mkv;*.avi;*.mov;*.webm;*.m4v;*.vob;*.mpg;*.mpeg;"
                  "*.m2ts;*.mts;*.m2v|Minden fájl|*.*")

HELP = """VIDEÓVÁGÓ ÉS ÖSSZEFŰZŐ

MIRE VALÓ
Videó vágása füllel. A műveletek az Alt-menüben vannak, a Tab a három
listát járja: markerek, magyarázó szövegek, beszúrt képek és hangok.

LÉPÉS ÉS KIJELÖLÉS
Szóköz: a videó hangjának lejátszása vagy megállítása.
Bal és jobb nyíl: ennyit lépsz. Az alap 2 másodperc.
Ctrl+bal és Ctrl+jobb: a lépésköz, 0,1 másodperctől 10 másodpercig.
Shift+nyíl: kijelöli az érintett szakaszt. A kijelölés megmarad, amíg
sima nyíllal tovább nem lépsz.
Ctrl+C a kijelölt szakaszt külön fájlba menti.
Ctrl+X kiveszi a köztes részt, és a szerkesztés folytatható. Nem kér mentést.
A mentés az Alt+F, Teljes videó mentése.
Ctrl+V a fájlkezelőből másolt videót a pillanatnyi pontra teszi, akár közben is.
A végére fűzés külön menüpont.

HANG ÉS KÉP
A hang rákeverhető, vagy beszúrható. A beszúrt hang helyén a videó szétnyílik,
és gondolatbuborék látszik. Ha ugyanoda képet teszel, az a buborék helyett
vagy rajta látszik, ahogy a helyét választod.
A kép lehet a videó mellett a jobb felső sarokban, középen fókuszban,
vagy teljes képernyőn, annyi másodpercig, amennyit megadsz. A méret a
képkocka százaléka.

MENÜK
Alt+F Fájl: betöltés, hozzáfűzés, beszúrás ide, szakasz mentése, kivágás, teljes mentés.
Alt+L Lejátszás.  Alt+S Szerkesztés: marker, szöveg, kép, hang rákeverése vagy beszúrása.
F1 súgó. A listákban Delete töröl."""


class VideoEditFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Videóvágó és összefűző",
                         size=(880, 640))
        self.main = main
        self.editor = VE.VideoEditor()
        self.player = Player()
        self.preview_player = Player()
        self.preview_player.on_state = lambda state: wx.CallAfter(self._preview_state, state)
        self._preview_dir = None
        self.player.on_state = lambda s: wx.CallAfter(self._player_state, s)
        self._rendering = False
        self._closing = False        # zárás alatt a háttér-callbackek kilépnek
        self._pos = 0.0
        self._step = 2.0
        self._anchor = None
        self._sel = None
        self._video_name = ""
        self._seg_index = None
        self._seg_origin = 0.0
        self._seg_src = 0.0

        self._build()
        self._build_menu()
        self.CreateStatusBar()
        self._announce("Tölts be egy videót az Alt+F menüből. A Szóköz lejátssza "
                       "a hangját. A nyíl léptet, a Shift kijelöl, a Ctrl a lépésközt állítja.")
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.play_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_play_tick, self.play_timer)

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        self.title_lbl = wx.StaticText(p, label="Nincs betöltött videó.")
        self.title_lbl.SetName("A betöltött videó")
        v.Add(self.title_lbl, 0, wx.EXPAND | wx.ALL, 8)
        v.Add(wx.StaticText(p, label=(
            "Alt+F fájl, Alt+L lejátszás, Alt+S szerkesztés. "
            "Szóköz: lejátszás. Nyíl: lépés. Shift+nyíl: kijelölés. "
            "Ctrl+nyíl: lépésköz.")), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        lists = wx.BoxSizer(wx.HORIZONTAL)
        lv = wx.BoxSizer(wx.VERTICAL)
        lv.Add(wx.StaticText(p, label="Markerek (Delete: törlés). A szakasz "
               "mentése a kijelölt és a következő marker közt ment:"),
               0, wx.LEFT | wx.TOP, 6)
        self.mk_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
                                   name="Markerek")
        self.mk_list.InsertColumn(0, "Marker időpont", width=180)
        self.mk_list.Bind(wx.EVT_KEY_DOWN, self._on_mk_key)
        lv.Add(self.mk_list, 1, wx.EXPAND | wx.ALL, 4)
        lists.Add(lv, 1, wx.EXPAND)

        nv = wx.BoxSizer(wx.VERTICAL)
        nv.Add(wx.StaticText(p, label="Magyarázó szövegek (Delete: törlés):"),
               0, wx.LEFT | wx.TOP, 6)
        self.nt_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
                                   name="Magyarázó szövegek")
        self.nt_list.InsertColumn(0, "Időpont", width=90)
        self.nt_list.InsertColumn(1, "Szöveg", width=300)
        self.nt_list.Bind(wx.EVT_KEY_DOWN, self._on_nt_key)
        nv.Add(self.nt_list, 1, wx.EXPAND | wx.ALL, 4)
        lists.Add(nv, 1, wx.EXPAND)
        v.Add(lists, 1, wx.EXPAND | wx.ALL, 6)
        v.Add(wx.StaticText(p, label="Képek és hangok (Delete: törlés):"), 0, wx.LEFT, 8)
        self.layer_list = wx.ListBox(p, name="Beszúrt képek és hangok")
        self.layer_list.Bind(wx.EVT_KEY_DOWN, self._on_layer_key)
        v.Add(self.layer_list, 1, wx.EXPAND | wx.ALL, 6)

        self.gauge = wx.Gauge(p, range=100)
        v.Add(self.gauge, 0, wx.EXPAND | wx.ALL, 8)

        p.SetSizer(v)

    def _build_menu(self):
        mb = wx.MenuBar()

        def mi(menu, label, fn):
            item = menu.Append(wx.ID_ANY, label)
            self.Bind(wx.EVT_MENU, lambda e, f=fn: f(), item)
            return item

        m_file = wx.Menu()
        mi(m_file, "Videó &betöltése…", self._load_video)
        mi(m_file, "Videó &hozzáfűzése…", self._append_video)
        mi(m_file, "Videó be&szúrása ide…\tCtrl+V", self._paste_or_insert_video)
        m_file.AppendSeparator()
        mi(m_file, "Szakasz &mentése…\tCtrl+C", self._save_section)
        mi(m_file, "Szakasz &kivágása (a többi marad)\tCtrl+X", self._cut_section)
        mi(m_file, "&Teljes videó mentése…", self._save_whole)
        mb.Append(m_file, "&Fájl")

        m_play = wx.Menu()
        mi(m_play, "&Lejátszás / megállás", self._toggle)
        mi(m_play, "Vissza az &elejére", self._restart)
        mi(m_play, "Pillanatnyi &időpont", self._say_time)
        mi(m_play, "&Vissza egy lépés", lambda: self._on_arrow(-1, False, False))
        mi(m_play, "Elő&re egy lépés", lambda: self._on_arrow(1, False, False))
        mb.Append(m_play, "&Lejátszás")

        m_edit = wx.Menu()
        mi(m_edit, "&Marker hozzáadása itt", self._add_marker)
        mi(m_edit, "&Szöveg hozzáadása itt…", self._add_note)
        mi(m_edit, "Ké&p hozzáadása itt…", lambda: self._add_layer("image"))
        mi(m_edit, "H&ang rákeverése itt…", lambda: self._add_layer("audio"))
        mi(m_edit, "Hang &beszúrása itt…", self._insert_audio)
        mi(m_edit, "Hangkeverés meghall&gatása", self._preview_audio)
        mi(m_edit, "Beszúrás idő&zítése…", self._edit_layer)
        mi(m_edit, "Kijelölés &eldobása", self._clear_selection)
        mb.Append(m_edit, "&Szerkesztés")

        self.SetMenuBar(mb)

    # ---- betöltés / lejátszás -----------------------------------------

    def _pick_video(self, title):
        dlg = wx.FileDialog(self, title, wildcard=VIDEO_WILDCARD,
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        path = dlg.GetPath() if dlg.ShowModal() == wx.ID_OK else ""
        dlg.Destroy()
        return path

    def _load_video(self):
        if self._rendering:
            return
        path = self._pick_video("Videó betöltése")
        if not path:
            return
        self.player.stop()
        self.preview_player.stop()
        self.editor.cleanup()
        self.editor = VE.VideoEditor()
        self._rendering = True
        self.title_lbl.SetLabel("Videó vizsgálata…")
        self._refresh_markers()
        self._refresh_notes()
        self._refresh_layers()
        self._announce("Videó vizsgálata…")

        def work():
            clip = self.editor.add_clip(path)
            wx.CallAfter(self._loaded, clip, path)

        threading.Thread(target=work, daemon=True).start()

    def _loaded(self, clip, path):
        self._rendering = False
        if self._closing:
            self._cleanup()
            return
        if not clip:
            self.title_lbl.SetLabel("Nincs betöltött videó.")
            self._announce("Ezt a videót nem sikerült beolvasni.")
            return
        self._video_name = Path(path).name
        self._refresh_title()
        self._refresh_markers()
        self._refresh_notes()
        self._announce(f"Betöltve, hossza {VE.human_time(clip.duration)}. "
                       "Szóköz: a hang lejátszása.")

    def _append_video(self):
        if self._rendering:
            return
        if not self.editor.clips:
            self._cannot("Előbb tölts be egy videót, utána fűzhetsz hozzá "
                         "továbbiakat a végére.")
            return
        path = self._pick_video("Videó hozzáfűzése a végéhez")
        if not path:
            return
        self._rendering = True
        self.preview_player.stop()

        def work():
            clip = self.editor.add_clip(path)
            wx.CallAfter(self._appended, clip)

        threading.Thread(target=work, daemon=True).start()

    def _appended(self, clip):
        self._rendering = False
        if self._closing:
            self._cleanup()
            return
        if not clip:
            self._announce("Ezt a videót nem sikerült hozzáfűzni.")
            return
        self._refresh_layers(self._selected_layer())
        self._announce(f"Hozzáfűzve: {Path(clip.path).name}. Teljes hossz most "
                       f"{VE.human_time(self.editor.total_duration())}. Az "
                       "összefűzött videót az Alt+F, Teljes videó mentése menüvel "
                       "mentheted el.")

    def _refresh_title(self):
        if not self.editor.clips:
            self.title_lbl.SetLabel("Nincs betöltött videó.")
            return
        nev = self._video_name or "Videó"
        if len(self.editor.clips) > 1:
            nev = f"{nev}, {len(self.editor.clips)} rész"
        self.title_lbl.SetLabel(
            f"Videó: {nev} ({VE.human_time(self.editor.total_duration())})")

    def _segment_at(self, t: float):
        acc = 0.0
        clips = self.editor.clips
        last = len(clips) - 1
        for i, clip in enumerate(clips):
            if t < acc + clip.duration - 0.03 or i == last:
                return i, acc, clip
            acc += clip.duration
        return 0, 0.0, clips[0]

    def _play_at(self, pos: float):
        total = self.editor.total_duration()
        if total <= 0:
            return
        pos = min(max(0.0, pos), max(0.0, total - 0.05))
        index, origin, clip = self._segment_at(pos)
        self._seg_index = index
        self._seg_origin = origin
        self._seg_src = clip.src_start
        self._pos = pos
        self.player.play(clip.path, title="videó",
                         start=max(0.0, clip.src_start + pos - origin))
        if not self.play_timer.IsRunning():
            self.play_timer.Start(200)

    def _timeline_from_player(self) -> float:
        if self._seg_index is None:
            return self.player.position()
        return self._seg_origin + max(0.0, self.player.position() - self._seg_src)

    def _on_play_tick(self, _event):
        if not self.player.is_active() or self._seg_index is None:
            self.play_timer.Stop()
            return
        pos = self._timeline_from_player()
        self._pos = pos
        clip = self.editor.clips[self._seg_index]
        if pos < self._seg_origin + clip.duration - 0.12:
            return
        nxt = self._seg_origin + clip.duration
        if nxt < self.editor.total_duration() - 0.05:
            self._play_at(nxt)
        else:
            self.player.stop()
            self.play_timer.Stop()
            self._pos = self.editor.total_duration()

    def _toggle(self):
        if self._rendering:
            return
        self.preview_player.stop()
        if not self.editor.clips:
            self._announce("Előbb tölts be egy videót.")
            return
        if self.player.is_active():
            self._pos = self._timeline_from_player()
            paused = self.player.toggle_pause()
            self._announce(f"Megállítva itt: {self._pos_str()}." if paused
                           else "Lejátszás.")
        else:
            self._play_at(self._pos)

    def _restart(self):
        if self._rendering:
            return
        self.preview_player.stop()
        self._pos = 0.0
        self._anchor = None
        self._sel = None
        if self.editor.clips:
            self._play_at(0.0)
            self._announce("Lejátszás az elejéről.")

    def _position(self) -> float:
        if self.player.is_active():
            return self._timeline_from_player()
        return self._pos

    def _pos_str(self) -> str:
        return VE.human_time(self._position())

    def _say_time(self):
        if self.editor.clips:
            hol = ""
            _i, origin, clip = self._segment_at(self._position())
            if clip.kind == "audio_insert":
                hol = " Beszúrt hang, a képen gondolatbuborék."
            self._announce(
                f"Pillanatnyi időpont: {self._pos_str()}. "
                f"Lépés: {self._lepes_szoveg()}.{hol}")
        else:
            self._announce("Nincs betöltött videó.")

    def _lepes_szoveg(self) -> str:
        t = f"{self._step:.1f}".replace(".", ",")
        if t.endswith(",0"):
            t = t[:-2]
        return f"{t} másodperc"

    def _on_arrow(self, direction: int, ctrl: bool, shift: bool):
        if self._rendering:
            return
        if ctrl:
            self._adjust_step(direction)
            return
        if not self.editor.clips:
            self._announce("Előbb tölts be egy videót.")
            return
        self.preview_player.stop()
        if shift:
            if self._anchor is None:
                self._anchor = self._position()
            self._move_by(direction * self._step)
            new = self._position()
            a, b = sorted((self._anchor, new))
            self._sel = (a, b) if b - a > 0.05 else None
            self._announce(
                f"Kijelölve: {VE.human_time(a)}-tól {VE.human_time(b)}-ig.")
            return
        self._anchor = None
        self._sel = None
        self._move_by(direction * self._step)
        self._announce(
            f"Léptetve ide: {self._pos_str()}. Lépés: {self._lepes_szoveg()}.")

    def _move_by(self, delta: float):
        pos = self._position()
        folytat = self.player.is_active() and not self.player.is_paused()
        if self.player.is_active():
            self.player.stop()
            self.play_timer.Stop()
        dur = self.editor.total_duration() or 0.0
        self._pos = max(0.0, min(pos + delta, dur))
        if folytat:
            self._play_at(self._pos)

    def _adjust_step(self, direction: int):
        nxt = round(min(10.0, max(0.1, self._step + direction * 0.1)), 1)
        if abs(nxt - self._step) < 1e-6:
            szel = "legkisebb" if direction < 0 else "legnagyobb"
            self._announce(f"A lépés {self._lepes_szoveg()}, ez a {szel}.")
            return
        self._step = nxt
        self._announce(f"Lépés: {self._lepes_szoveg()}.")

    def _clear_selection(self):
        self._anchor = None
        self._sel = None
        self._announce("Kijelölés eldobva.")

    def _player_state(self, text):
        if self._closing:
            return
        if text == "vége":
            if self.player.is_active():
                return
            if self._seg_index is not None and self.editor.clips:
                nxt = self._seg_origin + self.editor.clips[self._seg_index].duration
                if nxt < self.editor.total_duration() - 0.05:
                    self._play_at(nxt)
                    return
            self.play_timer.Stop()
            self._announce("A hang vége. Vissza az elejére vagy Szóköz.")
        elif text.startswith("hiba"):
            self._announce(f"Lejátszási hiba: {text}.")

    # ---- markerek / szövegek ------------------------------------------

    def _add_marker(self):
        if self._rendering:
            return
        if not self.editor.clips:
            self._cannot("Előbb tölts be egy videót, hogy markert tehess.")
            return
        at = self._position()
        self.editor.add_marker(at)
        self._refresh_markers(select_at=at)
        n = len(self.editor.markers)
        msg = f"Marker hozzáadva: {VE.human_time(at)}. Összesen {n} marker."
        if n == 2:
            msg += (" Két marker van: Alt+F, Szakasz kivágása a köztük lévő "
                    "részt kiveszi, Szakasz mentése csak azt a részt menti. "
                    "Shift+nyíllal marker nélkül is kijelölhetsz.")
        self._announce(msg)

    def _add_note(self):
        if self._rendering:
            return
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
        if self._rendering:
            return
        if e.GetKeyCode() == wx.WXK_DELETE:
            i = self.mk_list.GetFirstSelected()
            if i >= 0:
                self.editor.remove_marker(i)
                self._refresh_markers()
                self._announce("Marker törölve.")
        else:
            e.Skip()

    def _on_nt_key(self, e):
        if self._rendering:
            return
        if e.GetKeyCode() == wx.WXK_DELETE:
            i = self.nt_list.GetFirstSelected()
            if i >= 0:
                self.editor.remove_note(i)
                self._refresh_notes()
                self._announce("Szöveg törölve.")
        else:
            e.Skip()


    def _ask_seconds(self, title, label, default, *, minimum, unit="másodpercet"):
        while True:
            with wx.TextEntryDialog(self, label, title, f"{default:g}") as dialog:
                if dialog.ShowModal() != wx.ID_OK:
                    return None
                try:
                    value = float(dialog.GetValue().strip().replace(",", "."))
                except ValueError:
                    value = -1
            if math.isfinite(value) and value >= minimum:
                return value
            self._cannot(f"Adj meg legalább {minimum:g} {unit} számmal.")

    def _add_layer(self, kind):
        if self._rendering:
            return
        if not self.editor.clips:
            self._cannot("Előbb tölts be egy videót.")
            return
        if self.player.is_active():
            self.player.pause()
        self.preview_player.stop()
        at = self._position()
        title = "Kép hozzáadása" if kind == "image" else "Hang hozzáadása"
        wildcard = IMAGE_WILDCARD if kind == "image" else AUDIO_WILDCARD
        with wx.FileDialog(self, title, wildcard=wildcard,
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        duration = None
        place, scale = "corner", 0.4
        if kind == "image":
            duration = self._ask_seconds(
                title, "Hány másodpercig látszódjon a kép?", 4, minimum=0.1)
            if duration is None:
                return
            look = self._ask_image_look()
            if look is None:
                return
            place, scale = look
        self._rendering = True
        self._announce("A beszúrandó fájl ellenőrzése…")

        def work():
            try:
                layer = self.editor.add_layer(
                    kind, path, at, duration, place=place, scale=scale)
                wx.CallAfter(self._layer_added, layer, "")
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                wx.CallAfter(self._layer_added, None, str(error))

        threading.Thread(target=work, daemon=True).start()

    def _layer_added(self, layer, error):
        self._rendering = False
        if self._closing:
            self.editor.cleanup()
            return
        if layer is None:
            self._cannot(error)
            return
        self._refresh_layers(layer)
        self._announce("Hozzáadva. " + self._layer_label(layer))

    def _layer_label(self, layer):
        kind = "Kép" if layer.kind == "image" else "Rákevert hang"
        end = min(self.editor.total_duration(), layer.at + layer.duration)
        hely = ""
        if layer.kind == "image":
            szoveg = {"corner": "jobb felső sarok", "center": "középen",
                      "full": "teljes képernyő"}.get(layer.place, "jobb felső sarok")
            if layer.place == "full":
                hely = f", {szoveg}"
            else:
                hely = f", {szoveg}, {int(round((layer.scale or 0.4) * 100))} százalék"
        return (f"{kind}: {Path(layer.path).name}. Kezdete {layer.at:.2f} mp, "
                f"vége {end:.2f} mp{hely}.")

    def _refresh_layers(self, selected=None):
        self.layer_list.Set([self._layer_label(layer) for layer in self.editor.layers])
        if selected is None:
            return
        for index, layer in enumerate(self.editor.layers):
            if layer is selected:
                self.layer_list.SetSelection(index)
                self.layer_list.SetFocus()
                return

    def _selected_layer(self):
        index = self.layer_list.GetSelection()
        return self.editor.layers[index] if 0 <= index < len(self.editor.layers) else None

    def _edit_layer(self):
        if self._rendering:
            return
        layer = self._selected_layer()
        if layer is None:
            self._cannot("Válassz egy képet vagy hangot a beszúrások listájából.")
            return
        at = self._ask_seconds("Beszúrás időzítése", "Kezdőpont másodpercben:", layer.at,
                               minimum=0)
        if at is None:
            return
        if at >= self.editor.total_duration():
            self._cannot("A kezdőpontnak a videón belül kell lennie.")
            return
        duration = layer.duration
        if layer.kind == "image":
            duration = self._ask_seconds(
                "Kép időtartama", "Hány másodpercig látszódjon a kép?",
                duration, minimum=0.1)
            if duration is None:
                return
            look = self._ask_image_look(layer.place, layer.scale)
            if look is None:
                return
            layer.place, layer.scale = look
        self.preview_player.stop()
        layer.at, layer.duration = at, duration
        self.editor.layers.sort(key=lambda item: item.at)
        self._refresh_layers(layer)
        self._announce("Időzítés módosítva. " + self._layer_label(layer))

    def _on_layer_key(self, event):
        if event.GetKeyCode() != wx.WXK_DELETE:
            event.Skip()
            return
        index = self.layer_list.GetSelection()
        if not self._rendering and index != wx.NOT_FOUND:
            self.preview_player.stop()
            del self.editor.layers[index]
            self._refresh_layers()
            if self.editor.layers:
                self.layer_list.SetSelection(min(index, len(self.editor.layers) - 1))
            self._announce("A beszúrás törölve.")

    _PLACES = (
        ("corner", "A videó mellett, jobb felső sarokban"),
        ("center", "Középen, fókuszban"),
        ("full", "Teljes képernyőn, kitakarja a videót"),
    )

    def _ask_image_look(self, place="corner", scale=0.4):
        cimkek = [szoveg for _kulcs, szoveg in self._PLACES]
        aktualis = next((i for i, (kulcs, _sz) in enumerate(self._PLACES)
                         if kulcs == place), 0)
        dlg = wx.SingleChoiceDialog(self, "Hol látszódjon a kép?",
                                    "A kép helye", cimkek)
        dlg.SetSelection(aktualis)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return None
        place = self._PLACES[dlg.GetSelection()][0]
        dlg.Destroy()
        if place == "full":
            return place, 1.0
        alap = 40 if place == "corner" else 70
        if scale:
            alap = int(round(scale * 100))
        szazalek = self._ask_seconds(
            "A kép mérete",
            "A képkocka hány százaléka legyen? 10 és 100 között.",
            alap, minimum=10, unit="százalékot")
        if szazalek is None:
            return None
        return place, min(1.0, szazalek / 100.0)

    def _insert_audio(self):
        if self._rendering or not self._need_video():
            return
        at = self._position()
        with wx.FileDialog(self, "Hang beszúrása ide", wildcard=AUDIO_WILDCARD,
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        self._rendering = True
        self.player.stop()
        self._announce("A hang ellenőrzése…")

        def work():
            try:
                clip = self.editor.insert_audio(path, at)
                wx.CallAfter(self._inserted, clip, self.editor.error)
            except (OSError, subprocess.SubprocessError) as error:
                wx.CallAfter(self._inserted, None, str(error))

        threading.Thread(target=work, daemon=True).start()

    def _paste_or_insert_video(self):
        if self._rendering or not self._need_video():
            return
        utak = self._clipboard_files()
        videok = [ut for ut in utak if Path(ut).suffix.lower() in _VIDEO_VEGEK]
        if videok:
            self._insert_paths(videok, self._position())
            return
        path = self._pick_video("Videó beszúrása a pillanatnyi pontra")
        if path:
            self._insert_paths([path], self._position())

    def _clipboard_files(self):
        nevek = []
        if not wx.TheClipboard.Open():
            return nevek
        adat = wx.FileDataObject()
        try:
            if wx.TheClipboard.GetData(adat):
                nevek = list(adat.GetFilenames())
        finally:
            wx.TheClipboard.Close()
        return nevek

    def _insert_paths(self, paths, at):
        self._rendering = True
        self.player.stop()
        self.play_timer.Stop()
        self._announce("A videó beillesztése…")

        def work():
            beillesztett = []
            hiba = ""
            pont = at
            for path in paths:
                clip = self.editor.insert_video(path, pont)
                if clip is None:
                    hiba = self.editor.error or "Ezt a videót nem sikerült beilleszteni."
                    break
                beillesztett.append(clip)
                pont += clip.duration
            wx.CallAfter(self._videos_inserted, beillesztett, hiba)

        threading.Thread(target=work, daemon=True).start()

    def _need_video(self) -> bool:
        if self.editor.clips:
            return True
        self._cannot("Előbb tölts be egy videót.")
        return False

    def _inserted(self, clip, kind):
        self._rendering = False
        if self._closing:
            self._cleanup()
            return
        if clip is None:
            self._cannot(kind or "A hangot nem sikerült beszúrni.")
            return
        self._refresh_title()
        self._refresh_markers()
        self._refresh_notes()
        self._refresh_layers(self._selected_layer())
        self._announce(
            f"Hang beszúrva: {Path(clip.path).name}, "
            f"hossz {VE.human_time(clip.duration)}. "
            "A videó itt szétnyílt, gondolatbuborék látszik. "
            "Ha képet teszel ugyanide, az látszik a buborék helyett vagy rajta. "
            f"Teljes hossz {VE.human_time(self.editor.total_duration())}.")

    def _videos_inserted(self, clips, error):
        self._rendering = False
        if self._closing:
            self._cleanup()
            return
        if not clips:
            self._cannot(error or "Nem sikerült beilleszteni.")
            return
        self._refresh_title()
        self._refresh_markers()
        self._refresh_notes()
        nevek = ", ".join(Path(clip.path).name for clip in clips)
        self._announce(
            f"Beillesztve a pillanatnyi pontra: {nevek}. "
            "A régi folytatás utána jön. "
            f"Teljes hossz {VE.human_time(self.editor.total_duration())}. "
            "Menteni az Alt+F, Teljes videó mentése menüvel lehet.")
        if error:
            self._announce(error)

    def _preview_audio(self):
        if self._rendering:
            return
        if self.preview_player.is_active():
            self.preview_player.stop()
            self._announce("Hangkeverés előnézete leállítva.")
            return
        if not self.editor.clips:
            self._cannot("Előbb tölts be egy videót.")
            return
        layer = self._selected_layer()
        at = layer.at if layer is not None and layer.kind == "audio" else self._position()
        if self.player.is_active():
            self.player.pause()
        try:
            if self._preview_dir is None:
                self._preview_dir = tempfile.TemporaryDirectory(prefix="superdl_mix_")
        except OSError as error:
            self._cannot(str(error))
            return
        path = str(Path(self._preview_dir.name) / "preview.wav")
        self._rendering = True
        self._announce(f"Hangkeverés előnézete készül, kezdőpont {at:.2f} mp.")

        def work():
            ok = self.editor.preview_audio(at, path)
            wx.CallAfter(self._preview_done, ok, path)

        threading.Thread(target=work, daemon=True).start()

    def _preview_done(self, ok, path):
        self._rendering = False
        if self._closing:
            self._cleanup()
            return
        if ok:
            self._announce("Hangkeverés előnézete. Az Alt+S, Hangkeverés "
                           "meghallgatása menüvel leállíthatod.")
            self.preview_player.play(path, title="Hangkeverés előnézete")
        else:
            self._cannot(self.editor.error or "A hangelőnézet nem sikerült.")

    def _preview_state(self, state):
        if state.startswith("hiba"):
            self._announce(f"A hangelőnézet lejátszása sikertelen: {state}.")
        elif state == "vége":
            self._announce("A hangkeverés előnézete véget ért.")

    def _cleanup(self):
        self.editor.cleanup()
        if self._preview_dir is not None:
            self._preview_dir.cleanup()
            self._preview_dir = None

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

    def _section_markers(self):
        """A Shift-kijelölés az elsődleges. Különben két marker: ha pontosan
        kettő van, kijelölés nélkül is; többnél a listában kijelölt és a
        rákövetkező. None, ha nincs érvényes pár."""
        if self._sel and self._sel[1] - self._sel[0] > 0.05:
            a, b = self._sel
            return min(a, b), max(a, b)
        mk = self.editor.markers
        if len(mk) < 2:
            return None
        i = self.mk_list.GetFirstSelected()
        if i < 0:
            if len(mk) == 2:
                i = 0
            else:
                return None
        if i + 1 >= len(mk):
            return None
        return mk[i].at, mk[i + 1].at

    _NEED_MARKERS = ("Ehhez Shift+nyilas kijelölés kell, vagy két marker. "
                     "Játszd le a hangot (Szóköz), és jelölj ki, vagy tedd le "
                     "a markert az Alt+S menüből. Ha kettőnél több markered van, "
                     "a listában jelöld ki a szakasz kezdő markerét.")

    def _save_section(self):
        if self._rendering:
            return
        pair = self._section_markers()
        if not pair:
            self._cannot("A szakasz mentéséhez " + self._NEED_MARKERS)
            return
        start, end = pair
        out = self._ask_format_and_path("szakasz")
        if out:
            self._start_export(start, end, out,
                               f"Szakasz mentése {VE.human_time(start)}–"
                               f"{VE.human_time(end)}…")

    def _cut_section(self):
        """A kijelölt szakasz kiesik a projektből. Nem ment fájlt."""
        if self._rendering:
            return
        pair = self._section_markers()
        if not pair:
            self._cannot("A kivágáshoz " + self._NEED_MARKERS
                         + " A kettő közti rész esik ki, a többi marad.")
            return
        cut_start, cut_end = pair
        if self.player.is_active():
            self._pos = self._timeline_from_player()
            self.player.stop()
            self.play_timer.Stop()
        hiba = self.editor.apply_cut(cut_start, cut_end)
        if hiba:
            self._cannot(hiba)
            return
        self._pos = min(self._pos, cut_start)
        self._anchor = None
        self._sel = None
        self._seg_index = None
        self._refresh_title()
        self._refresh_markers()
        self._refresh_notes()
        self._refresh_layers(self._selected_layer())
        self._announce(
            f"Kivágva {VE.human_time(cut_start)}-tól {VE.human_time(cut_end)}-ig. "
            f"A videó most {VE.human_time(self.editor.total_duration())}. "
            "A szerkesztés folytatható. Menteni az Alt+F, Teljes videó mentése menüvel lehet.")

    def _save_whole(self):
        if self._rendering:
            return
        if not self.editor.clips:
            self._cannot("Előbb tölts be egy videót az Alt+F menüből.")
            return
        out = self._ask_format_and_path("teljes_videó")
        if out:
            self._start_export(0.0, self.editor.total_duration(), out,
                               "A teljes videó mentése…")

    def _sv(self, key, state):
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            sv.announce(key, state)

    def _start_export(self, start, end, out, msg, cut=False):
        self._rendering = True
        self.player.stop()
        self.preview_player.stop()
        self._sv("video", "start")
        self.gauge.SetValue(0)
        self._last_pct = -10
        self._announce(msg + " Ez eltarthat egy darabig.")
        render = self.editor.export_cut if cut else self.editor.export

        def work():
            ok = render(
                start, end, out,
                progress=lambda p: wx.CallAfter(self._export_progress, p))
            wx.CallAfter(self._export_done, ok, out)

        threading.Thread(target=work, daemon=True).start()

    def _export_progress(self, p):
        if self._closing:
            return
        pct = int(p * 100)
        self.gauge.SetValue(min(100, pct))
        if pct >= self._last_pct + 10:
            self._last_pct = pct
            self._announce(f"Mentés: {pct}%.")

    def _export_done(self, ok, out):
        self._rendering = False
        if self._closing:
            self._cleanup()
            return
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

    def _help(self):
        try:
            from superdl.helpdialog import show_help
            show_help(self, "Videóvágó és összefűző", HELP)
        except Exception:
            wx.MessageBox(HELP, "Súgó – Videóvágó",
                          wx.OK | wx.ICON_INFORMATION, self)

    def _on_char_hook(self, e):
        if e.GetKeyCode() == wx.WXK_F1:      # súgó bárhonnan (szövegmezőből is)
            self._help()
            return
        focus = wx.Window.FindFocus()
        if isinstance(focus, (wx.TextCtrl, wx.Slider, wx.SpinCtrl)):
            e.Skip()
            return
        code = e.GetKeyCode()
        if code == wx.WXK_SPACE and not isinstance(focus, wx.Button):
            self._toggle()
            return
        if code in (wx.WXK_LEFT, wx.WXK_RIGHT):
            self._on_arrow(-1 if code == wx.WXK_LEFT else 1,
                           e.ControlDown(), e.ShiftDown())
            return
        e.Skip()

    def _speak(self, text):
        """A visszajelzés KIMONDÁSA a Core self-voice-án át – hogy a vak
        felhasználó tényleg HALLJA (a státuszsort a képernyőolvasó nem olvassa)."""
        sv = getattr(self.main, "selfvoice", None)
        # 1) A BEJELENTŐ a KÉPERNYŐOLVASÓ – ELŐSZÖR mindig ŐT kérjük.
        #    FONTOS: képernyőolvasó-módban a Core a saját hangot NÉMÍTJA
        #    (muted=True) ÉPP AZÉRT, hogy az olvasó beszéljen – ezért a
        #    némítás-ellenőrzés CSAK a beépített hangra vonatkozhat, ide nem.
        try:
            from superdl import screenreader
            if screenreader.speak(text):
                return
        except Exception:
            pass
        # 2) Nincs képernyőolvasó → a beépített hang segít ki, DE a Teljes
        #    némítás ilyenkor is némít
        if sv is not None and getattr(sv, "muted", False):
            return
        if sv:
            try:
                sv.speak(text, force=True)
            except Exception:
                pass

    def _announce(self, text):
        if self._closing:
            return
        self.SetStatusText(text)
        self._speak(text)                    # hallható is, ne csak a státuszsorban

    def _cannot(self, text):
        """Egy művelet MIÉRT nem indulhat – felolvasott MessageBox-szal, hogy a
        teljes némítás mellett is (JAWS olvassa) megtudja a felhasználó, nem csak
        némán ‚nem történik semmi'."""
        self.SetStatusText(text)
        self._speak(text)
        wx.MessageBox(text, "Videóvágó", wx.OK | wx.ICON_INFORMATION, self)

    def _on_close(self, e):
        self._closing = True
        try:
            self.play_timer.Stop()
            self.player.stop()
            self.preview_player.stop()
            self.editor.stop()
            if not self._rendering:
                self._cleanup()
        except Exception:
            pass
        if getattr(self.main, "_videoedit_win", None) is self:
            self.main._videoedit_win = None
        self.Destroy()
