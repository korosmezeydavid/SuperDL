"""Élő könyvolvasó ablak: a könyvet a programban olvastatja fel, és könyvenként
megjegyzi, hol tartottál (könyvjelző) – onnan folytatható.

Akadálymentes: logikus fókusz-sorrend, minden vezérlő gombbal ÉS billentyűvel
elérhető. A felolvasás SAPI vagy Edge neurális hanggal, fájlba konvertálás
nélkül szól.
"""

import os
import threading

import wx

from . import booktext, tts
from .readengine import ReadEngine

READ_ENGINE_KEYS = ["sapi", "edge"]     # csak az élő felolvasáshoz alkalmasak
WILDCARD = ("Könyvek|*.txt;*.docx;*.epub;*.pdf|Szöveg (*.txt)|*.txt|"
            "Word (*.docx)|*.docx|EPUB (*.epub)|*.epub|PDF (*.pdf)|*.pdf|"
            "Minden fájl|*.*")


class ReaderFrame(wx.Frame):
    def __init__(self, main, open_path: str = "", text: str = "", title=""):
        super().__init__(main, title="SuperDL – Könyvolvasó", size=(940, 720))
        self.main = main
        self.lib = main.library
        self.engine = ReadEngine(
            on_state=lambda d: wx.CallAfter(self._on_state, d))
        self._path = ""
        self._title = ""
        self._voices: list[tts.Voice] = []
        self.sleep = None                       # az aktív SleepTimer
        self._sleep_points: list[int] = []      # elalvási pontok (char-pozíciók)

        self._build()
        self._reload_library()
        self.CreateStatusBar()
        self.SetStatusText("Nyiss meg egy könyvet, vagy válassz a könyvtárból. "
                           "Lejátszás/Folytatás: F5. Szünet: Ctrl+szóköz.")
        self.Bind(wx.EVT_CLOSE, self._on_close)

        self.save_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self._save_bookmark(), self.save_timer)
        self.save_timer.Start(8000)

        self._load_voices()
        if text:
            self._set_book(open_path or f"(beillesztett) {title}", text,
                           title or "Beillesztett szöveg")
        elif open_path:
            self._open_path(open_path)

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        top = wx.BoxSizer(wx.HORIZONTAL)
        b_open = wx.Button(p, label="Könyv meg&nyitása…")
        b_open.Bind(wx.EVT_BUTTON, lambda e: self._on_open())
        self.title_lbl = wx.StaticText(p, label="Nincs megnyitott könyv.")
        top.Add(b_open, 0, wx.RIGHT, 8)
        top.Add(self.title_lbl, 1, wx.ALIGN_CENTER_VERTICAL)
        v.Add(top, 0, wx.EXPAND | wx.ALL, 8)

        # felolvasó + hang
        eng = wx.BoxSizer(wx.HORIZONTAL)
        eng.Add(wx.StaticText(p, label="&Felolvasó:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.engine_ch = wx.Choice(
            p, choices=[tts.ENGINES[k].name for k in READ_ENGINE_KEYS])
        self.engine_ch.SetSelection(1)       # alap: Edge (szép magyar hang)
        self.engine_ch.SetName("Felolvasó motor")
        self.engine_ch.Bind(wx.EVT_CHOICE, lambda e: self._load_voices())
        eng.Add(self.engine_ch, 0, wx.RIGHT, 10)
        eng.Add(wx.StaticText(p, label="&Hang:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.voice_ch = wx.Choice(p, choices=["(hangok betöltése…)"])
        self.voice_ch.SetName("Hang választása")
        eng.Add(self.voice_ch, 1, wx.RIGHT, 10)
        eng.Add(wx.StaticText(p, label="&Tempó:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.rate_spin = wx.SpinCtrl(p, min=-10, max=10, initial=0, size=(60, -1))
        self.rate_spin.SetName("Beszédtempó mínusz tíztől plusz tízig")
        eng.Add(self.rate_spin, 0, wx.RIGHT, 10)
        eng.Add(wx.StaticText(p, label="Hangma&gasság:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.pitch_spin = wx.SpinCtrl(p, min=-10, max=10, initial=0, size=(60, -1))
        self.pitch_spin.SetName("Hangmagasság mínusz tíztől plusz tízig")
        eng.Add(self.pitch_spin, 0)
        v.Add(eng, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # vezérlők
        ctl = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (
                ("&Folytatás / Lejátszás (F5)", lambda e: self._play_resume()),
                ("&Elölről", lambda e: self._play_from(0)),
                ("&Szünet (Ctrl+szóköz)", lambda e: self._toggle()),
                ("&Leállítás (Esc)", lambda e: self._stop()),
                ("Előző &mondat", lambda e: self.engine.skip(-1)),
                ("&Következő mondat", lambda e: self.engine.skip(1))):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            ctl.Add(b, 0, wx.RIGHT, 5)
        v.Add(ctl, 0, wx.LEFT | wx.BOTTOM, 8)

        self.now_lbl = wx.StaticText(p, label="")
        self.now_lbl.SetName("Most felolvasott mondat")
        v.Add(self.now_lbl, 0, wx.LEFT | wx.BOTTOM, 8)

        # alvás-időzítő: ennyi idő után lassan elhalkul és leáll; közben négy
        # „elalvási pontot" ment, amelyek közt reggel ugrálni lehet
        sl = wx.BoxSizer(wx.HORIZONTAL)
        sl.Add(wx.StaticText(p, label="&Alvás-időzítő:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.sleep_ch = wx.Choice(p, choices=[
            "Kikapcsolva", "15 perc", "30 perc", "45 perc", "60 perc",
            "90 perc"])
        self.sleep_ch.SetSelection(0)
        self.sleep_ch.SetName("Alvás-időzítő perc")
        self.sleep_ch.Bind(wx.EVT_CHOICE, lambda e: self._on_sleep_choice())
        sl.Add(self.sleep_ch, 0, wx.RIGHT, 10)
        b_sp_prev = wx.Button(p, label="Előző elalvási &pont")
        b_sp_prev.Bind(wx.EVT_BUTTON, lambda e: self._jump_sleep_point(-1))
        b_sp_next = wx.Button(p, label="Következő elalvási p&ont")
        b_sp_next.Bind(wx.EVT_BUTTON, lambda e: self._jump_sleep_point(1))
        sl.Add(b_sp_prev, 0, wx.RIGHT, 5)
        sl.Add(b_sp_next, 0)
        v.Add(sl, 0, wx.LEFT | wx.BOTTOM, 8)

        v.Add(wx.StaticText(p, label="Könyv s&zövege (csak olvasható):"),
              0, wx.LEFT, 8)
        self.text = wx.TextCtrl(
            p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP)
        self.text.SetName("Könyv szövege")
        v.Add(self.text, 3, wx.EXPAND | wx.ALL, 8)

        v.Add(wx.StaticText(p, label="Köny&vtár (Enter: megnyitás és "
              "folytatás, Delete: törlés):"), 0, wx.LEFT, 8)
        self.lib_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.lib_list.SetName("Könyvtár")
        self.lib_list.InsertColumn(0, "Könyv", width=560)
        self.lib_list.InsertColumn(1, "Hol tartok", width=120)
        self.lib_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED,
                           lambda e: self._open_from_library())
        self.lib_list.Bind(wx.EVT_KEY_DOWN, self._on_lib_key)
        v.Add(self.lib_list, 2, wx.EXPAND | wx.ALL, 8)
        p.SetSizer(v)

        ids = {k: wx.NewIdRef() for k in
               ("play", "pause", "stop", "prev", "next")}
        self.Bind(wx.EVT_MENU, lambda e: self._play_resume(), id=ids["play"])
        self.Bind(wx.EVT_MENU, lambda e: self._toggle(), id=ids["pause"])
        self.Bind(wx.EVT_MENU, lambda e: self._stop(), id=ids["stop"])
        self.Bind(wx.EVT_MENU, lambda e: self.engine.skip(-1), id=ids["prev"])
        self.Bind(wx.EVT_MENU, lambda e: self.engine.skip(1), id=ids["next"])
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_NORMAL, wx.WXK_F5, ids["play"]),
            (wx.ACCEL_CTRL, wx.WXK_SPACE, ids["pause"]),
            (wx.ACCEL_NORMAL, wx.WXK_ESCAPE, ids["stop"]),
            (wx.ACCEL_CTRL, wx.WXK_LEFT, ids["prev"]),
            (wx.ACCEL_CTRL, wx.WXK_RIGHT, ids["next"]),
        ]))

    # ---- hangok -------------------------------------------------------

    def _engine_key(self) -> str:
        return READ_ENGINE_KEYS[self.engine_ch.GetSelection()]

    def _load_voices(self):
        key = self._engine_key()
        self.voice_ch.Set(["(hangok betöltése…)"])
        self.voice_ch.SetSelection(0)

        def work():
            try:
                vs = tts.ENGINES[key].voices("")
            except Exception as e:
                wx.CallAfter(self.SetStatusText, f"Hangok hiba: {e}")
                return
            wx.CallAfter(self._show_voices, key, vs)

        threading.Thread(target=work, daemon=True).start()

    def _show_voices(self, key, vs):
        if key != self._engine_key():
            return
        self._voices = vs
        self.voice_ch.Set([v.name for v in vs] or ["(nincs hang)"])
        # alapból egy magyar hangot választunk
        idx = next((i for i, v in enumerate(vs)
                    if v.lang.lower().startswith("hu")
                    or "hungar" in v.name.lower()
                    or "magyar" in v.name.lower()), 0)
        if vs:
            self.voice_ch.SetSelection(idx)
        self.SetStatusText(f"{len(vs)} hang betöltve.")

    def _voice_id(self) -> str:
        i = self.voice_ch.GetSelection()
        return self._voices[i].id if 0 <= i < len(self._voices) else ""

    # ---- könyv megnyitása ---------------------------------------------

    def _on_open(self):
        dlg = wx.FileDialog(self, "Könyv megnyitása", wildcard=WILDCARD,
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self._open_path(dlg.GetPath())
        dlg.Destroy()

    def _open_path(self, path):
        self.SetStatusText(f"Könyv beolvasása: {os.path.basename(path)} …")

        def work():
            try:
                book = booktext.extract(path)
                text = book.text
                title = book.title or os.path.basename(path)
            except Exception as e:
                wx.CallAfter(self.SetStatusText, f"Nem olvasható: {e}")
                return
            wx.CallAfter(self._set_book, path, text, title)

        threading.Thread(target=work, daemon=True).start()

    def _set_book(self, path, text, title):
        self.engine.stop()
        if self.sleep and self.sleep.active():   # új könyv → futó időzítő lemond
            self.sleep.cancel()
            self.sleep = None
            self.sleep_ch.SetSelection(0)
        self._path, self._title = path, title
        self.engine.load(text)
        self.title_lbl.SetLabel(f"Könyv: {title}  "
                                f"({self.engine.chunk_count()} mondat)")
        self.text.SetValue(text)
        self.text.SetInsertionPoint(0)
        bm = self.lib.get(path)
        self._sleep_points = list(bm.sleep_points) if bm else []
        if bm and bm.pos_char > 0:
            sp = (f" {len(self._sleep_points)} elalvási pont mentve."
                  if self._sleep_points else "")
            self.SetStatusText(f"„{title}” megnyitva. Korábban itt tartottál: "
                               f"kb. {bm.percent()}%. Folytatás: F5.{sp}")
            # a korábbi motor/hang/beállítás visszaállítása
            if bm.engine_key in READ_ENGINE_KEYS:
                self.engine_ch.SetSelection(READ_ENGINE_KEYS.index(bm.engine_key))
                self._load_voices()
            self.rate_spin.SetValue(bm.rate)
            self.pitch_spin.SetValue(bm.pitch)
        else:
            self.SetStatusText(f"„{title}” megnyitva, "
                               f"{self.engine.chunk_count()} mondat. "
                               "Lejátszás: F5.")

    # ---- vezérlés -----------------------------------------------------

    def _start_at(self, from_char):
        vid = self._voice_id()
        if not vid:
            self.SetStatusText("Még töltődnek a hangok – egy pillanat, "
                               "majd nyomd újra az F5-öt.")
            return
        self.engine.start(
            from_char=from_char, engine_key=self._engine_key(),
            voice_id=vid, rate=self.rate_spin.GetValue(),
            pitch=self.pitch_spin.GetValue())

    def _play_resume(self):
        if self.engine.is_active() and self.engine.is_paused():
            self.engine.resume()
            self.SetStatusText("Folytatás.")
            return
        if self.engine.is_active():
            return
        bm = self.lib.get(self._path) if self._path else None
        self._start_at(bm.pos_char if bm else 0)

    def _play_from(self, from_char):
        self._start_at(from_char)

    # ---- alvás-időzítő ------------------------------------------------

    SLEEP_MIN = [0, 15, 30, 45, 60, 90]

    def _on_sleep_choice(self):
        if self.sleep and self.sleep.active():
            self.sleep.cancel()
            self.sleep = None
        mins = self.SLEEP_MIN[self.sleep_ch.GetSelection()]
        if mins <= 0:
            self.SetStatusText("Alvás-időzítő kikapcsolva.")
            return
        from .sleeptimer import SleepTimer
        self._base_vol = self.engine.player.volume or 0.7
        self.sleep = SleepTimer(
            mins * 60,
            on_mark=lambda q: wx.CallAfter(self._sleep_mark, q),
            on_fade=lambda lv: self.engine.player.set_volume(self._base_vol * lv),
            on_finish=lambda: wx.CallAfter(self._sleep_finish),
            fade_s=25.0)
        self.sleep.start()
        self.SetStatusText(
            f"Alvás-időzítő bekapcsolva: {mins} perc. A vége előtt lassan "
            "elhalkul, és négy elalvási pontot ment, amelyek közt reggel "
            "ugrálhatsz.")

    def _sleep_mark(self, q):
        pos = self.engine.position_char()
        if pos not in self._sleep_points:
            self._sleep_points.append(pos)
        self._save_bookmark()                  # létrehozza/frissíti a könyvjelzőt
        bm = self.lib.get(self._path) if self._path else None
        if bm:
            bm.sleep_points = sorted(set(self._sleep_points))
            self.lib.save()
        pct = round(pos / max(1, self.engine.total_chars) * 100)
        self.SetStatusText(f"Elalvási pont {q} a négyből elmentve "
                           f"(kb. {pct}%).")

    def _sleep_finish(self):
        self._save_bookmark()
        self.engine.stop()
        self.engine.player.set_volume(self._base_vol)   # vissza normál hangerőre
        self.sleep = None
        self.sleep_ch.SetSelection(0)
        self.SetStatusText(
            "Az alvás-időzítő letelt, a felolvasás leállt. Reggel ugyanezt a "
            "könyvet megnyitva az „Előző/Következő elalvási pont” gombbal "
            "ugrálhatsz a mentett pontok között.")

    def _jump_sleep_point(self, direction):
        pts = sorted(set(self._sleep_points))
        if not pts:
            self.SetStatusText("Ehhez a könyvhöz még nincsenek elalvási "
                               "pontok (az alvás-időzítő menti őket).")
            return
        cur = self.engine.position_char()
        if direction > 0:
            target = next((p for p in pts if p > cur + 5), pts[-1])
        else:
            target = next((p for p in reversed(pts) if p < cur - 5), pts[0])
        self._play_from(target)
        idx = pts.index(target) + 1
        pct = round(target / max(1, self.engine.total_chars) * 100)
        self.SetStatusText(f"Ugrás a(z) {idx}. elalvási pontra a "
                           f"{len(pts)}-ből (kb. {pct}%).")

    def _toggle(self):
        if not self.engine.is_active():
            return
        paused = self.engine.toggle_pause()
        self.SetStatusText("Szünet." if paused else "Folytatás.")
        if paused:
            self._save_bookmark()

    def _stop(self):
        if self.engine.is_active():
            self._save_bookmark()
            self.engine.stop()
            self.SetStatusText("Leállítva. A könyvjelző elmentve.")

    # ---- állapot / könyvjelző -----------------------------------------

    def _on_state(self, d):
        if d.get("error"):
            self.SetStatusText(f"Felolvasási hiba: {d['error']}")
            return
        if d.get("done"):
            self.now_lbl.SetLabel("")
            self.SetStatusText("A könyv végére értem.")
            if self._path:
                self.lib.upsert(
                    self._path, title=self._title, engine_key=self._engine_key(),
                    voice_id=self._voice_id(), rate=self.rate_spin.GetValue(),
                    pitch=self.pitch_spin.GetValue(),
                    pos_char=self.engine.total_chars,
                    total_chars=self.engine.total_chars)
                self._reload_library()
            return
        if d.get("playing"):
            i, n, pct = d.get("idx", 0), d.get("total", 0), d.get("pct", 0)
            self.SetStatusText(f"Felolvasás: {i + 1} / {n} mondat, kb. {pct}%.")
            snippet = (d.get("text", "") or "")[:120]
            self.now_lbl.SetLabel(snippet)

    def _save_bookmark(self):
        if not self._path or not self.engine.chunk_count():
            return
        self.lib.upsert(
            self._path, title=self._title, engine_key=self._engine_key(),
            voice_id=self._voice_id(), rate=self.rate_spin.GetValue(),
            pitch=self.pitch_spin.GetValue(),
            pos_char=self.engine.position_char(),
            total_chars=self.engine.total_chars)

    # ---- könyvtár -----------------------------------------------------

    def _reload_library(self):
        self._recent = self.lib.recent()
        self.lib_list.DeleteAllItems()
        for b in self._recent:
            i = self.lib_list.InsertItem(self.lib_list.GetItemCount(),
                                         b.title or b.path)
            self.lib_list.SetItem(i, 1, f"kb. {b.percent()}%")

    def _open_from_library(self):
        i = self.lib_list.GetFirstSelected()
        if 0 <= i < len(self._recent):
            b = self._recent[i]
            if os.path.isfile(b.path):
                self._open_path(b.path)
            else:
                self.SetStatusText(f"A fájl nem található: {b.path}")

    def _on_lib_key(self, e):
        if e.GetKeyCode() == wx.WXK_DELETE:
            i = self.lib_list.GetFirstSelected()
            if 0 <= i < len(self._recent):
                self.lib.remove(self._recent[i].path)
                self._reload_library()
        else:
            e.Skip()

    def _on_close(self, e):
        self.save_timer.Stop()
        if self.sleep and self.sleep.active():
            self.sleep.cancel()
        self._save_bookmark()
        try:
            self.engine.stop()
        except Exception:
            pass
        if getattr(self.main, "_reader_win", None) is self:
            self.main._reader_win = None
        e.Skip()
