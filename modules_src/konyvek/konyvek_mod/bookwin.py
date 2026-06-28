"""Hangoskönyv készítő ablak: könyv (TXT/DOCX/EPUB/PDF) → MP3, választható
TTS-motorral és hanggal, pitch/sebesség beállítással, hang-előhallgatással,
egyben vagy percenként darabolva.

Akadálymentes: minden vezérlő címkézett és billentyűzetről elérhető.
"""

import os
import tempfile
import threading
from pathlib import Path

import wx

from superdl import audiobook, booktext, store, tts   # megosztott backend a Core-ból
from superdl.audioengine import Player                 # megosztott lejátszó a Core-ból

ENGINE_ORDER = ["sapi", "edge", "gemini", "cloud"]


class BookFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Hangoskönyv készítő",
                         size=(820, 640))
        self.main = main
        self.book: booktext.Book | None = None
        self.voices: list[tts.Voice] = []
        self.keys = store.load_tts_keys()
        self.preview = Player()
        self._busy = False

        self._build()
        self.CreateStatusBar()
        self._on_engine()                  # induló motor beállítása
        self.SetStatusText("Válassz könyvet, motort és hangot, majd készítsd "
                           "el a hangoskönyvet. Súgó: F1.")
        self.Bind(wx.EVT_CLOSE, self._on_close)

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        # könyv
        r1 = wx.BoxSizer(wx.HORIZONTAL)
        r1.Add(wx.StaticText(p, label="&Könyv:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.book_txt = wx.TextCtrl(p, style=wx.TE_READONLY)
        self.book_txt.SetName("A kiválasztott könyv")
        b_open = wx.Button(p, label="Tall&ózás…")
        b_open.Bind(wx.EVT_BUTTON, self._on_pick_book)
        r1.Add(self.book_txt, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        r1.Add(b_open, 0)
        v.Add(r1, 0, wx.EXPAND | wx.ALL, 8)
        self.info_lbl = wx.StaticText(p, label="Nincs könyv betöltve. "
                                      "Támogatott: TXT, DOCX, EPUB, PDF.")
        v.Add(self.info_lbl, 0, wx.LEFT | wx.BOTTOM, 8)

        # vagy beillesztett szöveg (ha van benne, ezt használja a fájl helyett)
        v.Add(wx.StaticText(p, label="Vagy &illeszd be a szöveget ide (ha "
              "ide írsz, ezt használja a betallózott fájl helyett):"), 0,
              wx.LEFT, 8)
        self.paste_txt = wx.TextCtrl(p, style=wx.TE_MULTILINE, size=(-1, 90))
        self.paste_txt.SetName("Beillesztett szöveg a hangoskönyvhöz")
        v.Add(self.paste_txt, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        rt = wx.BoxSizer(wx.HORIZONTAL)
        rt.Add(wx.StaticText(p, label="A beillesztett szöveg cí&me:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.paste_title = wx.TextCtrl(p)
        self.paste_title.SetName("A beillesztett szöveg címe")
        self.paste_title.SetHint("pl. Cikk, jegyzet")
        rt.Add(self.paste_title, 1)
        v.Add(rt, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # motor + kulcs
        r2 = wx.BoxSizer(wx.HORIZONTAL)
        r2.Add(wx.StaticText(p, label="&Motor:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.engine_ch = wx.Choice(
            p, choices=[self._engine_label(k) for k in ENGINE_ORDER])
        self.engine_ch.SetSelection(1)     # alapból Edge (ingyenes, magyar)
        self.engine_ch.SetName("TTS-motor")
        self.engine_ch.Bind(wx.EVT_CHOICE, lambda e: self._on_engine())
        r2.Add(self.engine_ch, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        v.Add(r2, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        self.key_lbl = wx.StaticText(p, label="API-&kulcs:")
        self.key_txt = wx.TextCtrl(p)
        self.key_txt.SetName("API-kulcs (a Gemini és a Cloud motorhoz)")
        self.key_txt.Bind(wx.EVT_KILL_FOCUS, lambda e: (self._save_key(),
                                                        e.Skip()))
        rk = wx.BoxSizer(wx.HORIZONTAL)
        rk.Add(self.key_lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        rk.Add(self.key_txt, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        b_voices = wx.Button(p, label="Hangok &frissítése")
        b_voices.Bind(wx.EVT_BUTTON, lambda e: self._load_voices())
        rk.Add(b_voices, 0)
        v.Add(rk, 0, wx.EXPAND | wx.ALL, 8)

        self.limit_lbl = wx.StaticText(p, label="")
        v.Add(self.limit_lbl, 0, wx.LEFT | wx.BOTTOM, 8)

        # hang
        v.Add(wx.StaticText(p, label="&Hang (a listából válassz):"), 0,
              wx.LEFT, 8)
        self.voice_list = wx.ListBox(p, style=wx.LB_SINGLE)
        self.voice_list.SetName("Választható hangok")
        v.Add(self.voice_list, 1, wx.EXPAND | wx.ALL, 8)

        # pitch / rate / előhallgatás
        r3 = wx.BoxSizer(wx.HORIZONTAL)
        r3.Add(wx.StaticText(p, label="Ma&gasság:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.pitch_sp = wx.SpinCtrl(p, min=-10, max=10, initial=0, size=(60, -1))
        self.pitch_sp.SetName("Hangmagasság, mínusz tíztől plusz tízig")
        r3.Add(self.pitch_sp, 0, wx.RIGHT, 12)
        r3.Add(wx.StaticText(p, label="Se&besség:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.rate_sp = wx.SpinCtrl(p, min=-10, max=10, initial=0, size=(60, -1))
        self.rate_sp.SetName("Sebesség, mínusz tíztől plusz tízig")
        r3.Add(self.rate_sp, 0, wx.RIGHT, 12)
        b_test = wx.Button(p, label="Hang&teszt (előhallgatás)")
        b_test.Bind(wx.EVT_BUTTON, lambda e: self._on_preview())
        r3.Add(b_test, 0, wx.RIGHT, 6)
        b_pstop = wx.Button(p, label="Előhallgatás &leállítása")
        b_pstop.Bind(wx.EVT_BUTTON, lambda e: self.preview.stop())
        r3.Add(b_pstop, 0)
        v.Add(r3, 0, wx.LEFT | wx.BOTTOM, 8)

        # szöveg-tisztítás (felesleges üres sorok és sortörések eltávolítása)
        self.clean_chk = wx.CheckBox(
            p, label="Felesleges üres sorok és sortörések &tisztítása")
        self.clean_chk.SetName(
            "A felolvasás előtt összevonja a kettévágott szavakat és a "
            "kemény sortöréseket, és kihagyja az üres sorokat és oldalszámokat")
        self.clean_chk.SetValue(True)
        v.Add(self.clean_chk, 0, wx.LEFT | wx.BOTTOM, 8)

        # kimenet
        r4 = wx.BoxSizer(wx.HORIZONTAL)
        self.split_chk = wx.CheckBox(p, label="&Darabolva, percenként:")
        self.split_chk.SetName("Több MP3-ra darabolja a megadott percenként")
        self.split_sp = wx.SpinCtrl(p, min=1, max=240, initial=30, size=(70, -1))
        self.split_sp.SetName("Darab hossza percben")
        r4.Add(self.split_chk, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        r4.Add(self.split_sp, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)
        r4.Add(wx.StaticText(p, label="Cél&mappa:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.out_txt = wx.TextCtrl(p, value=str(Path.home() / "Downloads"),
                                   size=(220, -1))
        self.out_txt.SetName("Célmappa")
        b_dir = wx.Button(p, label="…", size=(32, -1))
        b_dir.Bind(wx.EVT_BUTTON, self._on_pick_dir)
        r4.Add(self.out_txt, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        r4.Add(b_dir, 0)
        v.Add(r4, 0, wx.EXPAND | wx.ALL, 8)

        self.gauge = wx.Gauge(p, range=100)
        v.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        self.make_btn = wx.Button(p, label="Hangoskönyv &készítése")
        self.make_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_make())
        v.Add(self.make_btn, 0, wx.ALL, 8)

        p.SetSizer(v)

        ids = {k: wx.NewIdRef() for k in ("help",)}
        self.Bind(wx.EVT_MENU, lambda e: self._help(), id=ids["help"])
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_NORMAL, wx.WXK_F1, ids["help"])]))

    # ---- motor / hangok ----------------------------------------------

    @staticmethod
    def _engine_label(k: str) -> str:
        e = tts.ENGINES[k]
        lim = ("nincs karakterkorlát" if not e.char_limit
               else f"max {e.char_limit} karakter/hívás")
        return f"{e.name} — {lim}"

    def _engine_key(self) -> str:
        return ENGINE_ORDER[self.engine_ch.GetSelection()]

    def _on_engine(self):
        eng = tts.ENGINES[self._engine_key()]
        lim = ("nincs gyakorlati korlát (automatikus darabolás)"
               if not eng.char_limit
               else f"{eng.char_limit} karakter / hívás (automatikus "
                    "darabolás)")
        self.limit_lbl.SetLabel(f"Karakterkorlát: {lim}.")
        # az állapotsorba is – így a képernyőolvasó felolvassa
        self.SetStatusText(f"Motor: {eng.name.split(' (')[0]}. "
                           f"Karakterkorlát: {lim}.")
        need = eng.needs_key
        self.key_lbl.Show(need)
        self.key_txt.Show(need)
        if need:
            self.key_txt.SetValue(self.keys.get(self._engine_key(), ""))
        self.pitch_sp.Enable(eng.supports_pitch)
        self.rate_sp.Enable(eng.supports_rate)
        self.Layout()
        self._load_voices()

    def _save_key(self):
        eng = tts.ENGINES[self._engine_key()]
        if eng.needs_key:
            self.keys[self._engine_key()] = self.key_txt.GetValue().strip()
            try:
                store.save_tts_keys(self.keys)
            except store.SecretStoreError as e:
                wx.MessageBox(str(e), "Titkosítás nem érhető el",
                              wx.OK | wx.ICON_WARNING, self)

    def _load_voices(self):
        eng = tts.ENGINES[self._engine_key()]
        key = self.keys.get(self._engine_key(), "")
        if eng.needs_key and not key:
            self.voice_list.Set(["(Adj meg API-kulcsot, majd „Hangok "
                                  "frissítése”.)"])
            self.voices = []
            return
        self.voice_list.Set(["Hangok betöltése…"])
        self.SetStatusText("Hangok betöltése…")

        def work():
            try:
                vs = eng.voices(api_key=key)
            except Exception as ex:
                wx.CallAfter(self._show_voices, None, str(ex))
                return
            wx.CallAfter(self._show_voices, vs, None)

        threading.Thread(target=work, daemon=True).start()

    def _show_voices(self, vs, err):
        if vs is None:
            self.voice_list.Set([f"(Hiba: {err})"])
            self.voices = []
            return
        self.voices = vs
        self.voice_list.Set([v.name for v in vs])
        if vs:
            self.voice_list.SetSelection(0)
        self.SetStatusText(f"{len(vs)} hang betöltve.")

    def _selected_voice(self) -> tts.Voice | None:
        i = self.voice_list.GetSelection()
        return self.voices[i] if 0 <= i < len(self.voices) else None

    # ---- könyv --------------------------------------------------------

    def _on_pick_book(self, e):
        dlg = wx.FileDialog(
            self, "Könyv kiválasztása",
            wildcard="Könyvek (*.txt;*.docx;*.epub;*.pdf)|"
                     "*.txt;*.docx;*.epub;*.pdf|Minden fájl|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self.book_txt.SetValue(path)
            self.info_lbl.SetLabel("Könyv beolvasása…")

            def work():
                try:
                    bk = booktext.extract(path)
                except Exception as ex:
                    wx.CallAfter(self.info_lbl.SetLabel, f"Hiba: {ex}")
                    return
                wx.CallAfter(self._book_loaded, bk)

            threading.Thread(target=work, daemon=True).start()
        dlg.Destroy()

    def _book_loaded(self, bk):
        self.book = bk
        self.info_lbl.SetLabel(
            f"„{bk.title}” – {len(bk.sections)} szakasz, "
            f"{bk.chars} karakter.")

    def _on_pick_dir(self, e):
        dlg = wx.DirDialog(self, "Célmappa", self.out_txt.GetValue())
        if dlg.ShowModal() == wx.ID_OK:
            self.out_txt.SetValue(dlg.GetPath())
        dlg.Destroy()

    # ---- előhallgatás -------------------------------------------------

    def _on_preview(self):
        v = self._selected_voice()
        if not v:
            self.SetStatusText("Előbb válassz hangot.")
            return
        eng = tts.ENGINES[self._engine_key()]
        key = self.keys.get(self._engine_key(), "")
        pitch, rate = self.pitch_sp.GetValue(), self.rate_sp.GetValue()
        self.SetStatusText("Hangminta készítése…")

        def work():
            try:
                base = os.path.join(tempfile.gettempdir(), "sdl_voicetest")
                path = eng.synth(
                    "Sziasztok! Így szól ez a hang. Ezzel készül a "
                    "hangoskönyved.", v.id, base, pitch=pitch, rate=rate,
                    api_key=key)
            except Exception as ex:
                wx.CallAfter(self.SetStatusText, f"Hangteszt hiba: {ex}")
                return
            wx.CallAfter(self._play_preview, path, v.name)

        threading.Thread(target=work, daemon=True).start()

    def _play_preview(self, path, name):
        self.SetStatusText(f"Hangminta: {name}")
        self.preview.play(path, title=name)

    # ---- készítés -----------------------------------------------------

    def _on_make(self):
        if self._busy:
            return
        # forrás: a beillesztett szöveg elsőbbséget élvez a fájllal szemben
        paste = self.paste_txt.GetValue().strip()
        if paste:
            title = self.paste_title.GetValue().strip() or "Beillesztett szöveg"
            book = booktext.Book(title=title, sections=[paste])
        elif self.book:
            book = self.book
        else:
            self.SetStatusText("Előbb válassz könyvet, vagy illessz be szöveget.")
            return
        if self.clean_chk.GetValue():
            book = audiobook.clean_book(book)   # felesleges sorok/sortörések ki
        v = self._selected_voice()
        if not v:
            self.SetStatusText("Előbb válassz hangot.")
            return
        eng_key = self._engine_key()
        key = self.keys.get(eng_key, "")
        pitch, rate = self.pitch_sp.GetValue(), self.rate_sp.GetValue()
        split = self.split_sp.GetValue() if self.split_chk.GetValue() else 0
        safe = "".join(c for c in book.title
                       if c.isalnum() or c in " -_").strip() or "hangoskonyv"
        out = os.path.join(self.out_txt.GetValue(), safe + ".mp3")

        self._busy = True
        self.make_btn.Disable()
        self.SetStatusText("Hangoskönyv készítése… ez hosszabb könyvnél "
                           "eltarthat egy ideig.")

        def prog(done, total, state):
            pct = int(done / total * 100) if total else 0
            wx.CallAfter(self.gauge.SetValue, pct)
            wx.CallAfter(self.SetStatusText,
                         f"{state}: {done}/{total} ({pct}%)")

        def work():
            try:
                res = audiobook.build(
                    book, eng_key, v.id, out, pitch=pitch, rate=rate,
                    api_key=key, split_minutes=split, progress=prog)
            except Exception as ex:
                wx.CallAfter(self._done, None, str(ex))
                return
            wx.CallAfter(self._done, res, None)

        threading.Thread(target=work, daemon=True).start()

    def _done(self, res, err):
        self._busy = False
        self.make_btn.Enable()
        self.gauge.SetValue(0)
        if err:
            self.SetStatusText(f"Hiba a készítés során: {err}")
            wx.MessageBox(f"Nem sikerült: {err}", "Hangoskönyv készítő",
                          wx.OK | wx.ICON_ERROR, self)
            return
        msg = (f"Kész! {len(res)} fájl: " + ", ".join(os.path.basename(r)
                                                      for r in res))
        self.SetStatusText(msg)
        if hasattr(self.main, "_sfx"):
            self.main._sfx("done")
        wx.MessageBox(msg + f"\n\nMappa: {os.path.dirname(res[0])}",
                      "Hangoskönyv készítő", wx.OK | wx.ICON_INFORMATION, self)

    # ---- súgó / zárás -------------------------------------------------

    def _help(self):
        wx.MessageBox(
            "Hangoskönyv készítő\n\n"
            "1. Tallózd be a könyvet (TXT, DOCX, EPUB, PDF).\n"
            "2. Válassz motort: SAPI (offline), Edge (ingyenes, magyar, "
            "kulcs nélkül), Gemini vagy Google Cloud (saját API-kulccsal).\n"
            "3. Frissítsd/válaszd ki a hangot; állítsd a magasságot és "
            "sebességet (ahol a motor engedi); a „Hangteszt” gombbal "
            "meghallgathatod.\n"
            "4. Válaszd: egyben vagy percenként darabolva, és a célmappát.\n"
            "5. „Hangoskönyv készítése”. Hosszú könyvnél türelem – a végén "
            "egy fix bevezető és egy záró nyilatkozat is rákerül.",
            "Súgó", wx.OK | wx.ICON_INFORMATION, self)

    def _on_close(self, e):
        try:
            self.preview.stop()
        except Exception:
            pass
        if getattr(self.main, "_book_win", None) is self:
            self.main._book_win = None
        e.Skip()
