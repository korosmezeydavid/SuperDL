"""Super Recorder – akadálymentes felvevő-ablak (It.1: egyszerű felvevő).

Sallangmentes, billentyűzetről teljesen elérhető, KIMONDOTT visszajelzéssel –
nincs vizuális hullámforma. Eszközválasztás, felvétel/szünet/leállítás, élő
szint-kijelzés (és kérésre kimondott csúcs, automatikus telítés-jelzés),
mentés WAV/MP3-ba opcionális normalizálással / csend-vágással / be-kihalkítással.
"""

import threading

import wx

from . import superrec


class SuperRecorderFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Super Recorder (felvevő)",
                         size=(680, 460))
        self.main = main
        self.rec: superrec.Recorder | None = None
        self._busy = False
        self._last_clip_announced = False

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        # eszköz
        d = wx.BoxSizer(wx.HORIZONTAL)
        d.Add(wx.StaticText(p, label="&Bemenet (mikrofon):"), 0,
              wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        try:
            self._devs = superrec.input_devices()
        except Exception:
            self._devs = []
        choices = [n for _i, n in self._devs] or ["Alapértelmezett bemenet"]
        self.dev_ch = wx.Choice(p, choices=choices)
        self.dev_ch.SetSelection(0)
        self.dev_ch.SetName("Felvevő bemenet választása")
        d.Add(self.dev_ch, 1)
        v.Add(d, 0, wx.EXPAND | wx.ALL, 8)

        # vezérlőgombok
        c = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_rec = wx.Button(p, label="&Felvétel (F5)")
        self.btn_rec.Bind(wx.EVT_BUTTON, lambda e: self._on_record())
        self.btn_pause = wx.Button(p, label="&Szünet")
        self.btn_pause.Bind(wx.EVT_BUTTON, lambda e: self._on_pause())
        self.btn_pause.Disable()
        self.btn_stop = wx.Button(p, label="&Leállítás (F7)")
        self.btn_stop.Bind(wx.EVT_BUTTON, lambda e: self._on_stop())
        self.btn_stop.Disable()
        self.btn_new = wx.Button(p, label="Ú&j felvétel")
        self.btn_new.Bind(wx.EVT_BUTTON, lambda e: self._on_new())
        self.btn_new.Disable()
        for b in (self.btn_rec, self.btn_pause, self.btn_stop, self.btn_new):
            c.Add(b, 0, wx.RIGHT, 6)
        v.Add(c, 0, wx.LEFT | wx.BOTTOM, 8)

        # állapot + szint
        self.time_lbl = wx.StaticText(p, label="Idő: 00:00,0")
        self.time_lbl.SetName("Felvett idő")
        v.Add(self.time_lbl, 0, wx.LEFT, 8)
        self.level_lbl = wx.StaticText(p, label="Szint: – (csúcs)")
        self.level_lbl.SetName("Szint, csúcs decibelben")
        v.Add(self.level_lbl, 0, wx.LEFT | wx.BOTTOM, 4)
        self.gauge = wx.Gauge(p, range=100)
        self.gauge.SetName("Szintmérő")
        v.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        b_lvl = wx.Button(p, label="Szint ki&mondása (F8)")
        b_lvl.Bind(wx.EVT_BUTTON, lambda e: self._say_level())
        v.Add(b_lvl, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 8)

        # mentési beállítások
        box = wx.StaticBoxSizer(wx.VERTICAL, p, "Mentés")
        sb = box.GetStaticBox()
        r1 = wx.BoxSizer(wx.HORIZONTAL)
        r1.Add(wx.StaticText(sb, label="F&ormátum:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.fmt_ch = wx.Choice(sb, choices=["WAV (veszteségmentes)", "MP3"])
        self.fmt_ch.SetSelection(0)
        self.fmt_ch.SetName("Kimeneti formátum")
        r1.Add(self.fmt_ch, 0, wx.RIGHT, 16)
        self.norm_chk = wx.CheckBox(sb, label="&Normalizálás (egyenletes hangerő)")
        self.norm_chk.SetValue(True)
        r1.Add(self.norm_chk, 0, wx.ALIGN_CENTER_VERTICAL)
        box.Add(r1, 0, wx.ALL, 6)
        r2 = wx.BoxSizer(wx.HORIZONTAL)
        self.trim_chk = wx.CheckBox(sb, label="Csen&d levágása az elejéről/végéről")
        r2.Add(self.trim_chk, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)
        self.fade_chk = wx.CheckBox(sb, label="Be- és ki&halkítás (0,3 mp)")
        r2.Add(self.fade_chk, 0, wx.ALIGN_CENTER_VERTICAL)
        box.Add(r2, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        sr = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_save = wx.Button(sb, label="Men&tés…")
        self.btn_save.Bind(wx.EVT_BUTTON, lambda e: self._on_save())
        self.btn_save.Disable()
        self.btn_edit = wx.Button(sb, label="Tovább a sz&erkesztőbe…")
        self.btn_edit.Bind(wx.EVT_BUTTON, lambda e: self._on_edit())
        self.btn_edit.Disable()
        sr.Add(self.btn_save, 0, wx.RIGHT, 8)
        sr.Add(self.btn_edit, 0)
        box.Add(sr, 0, wx.ALL, 6)
        v.Add(box, 0, wx.EXPAND | wx.ALL, 8)

        p.SetSizer(v)
        self.CreateStatusBar()
        self.SetStatusText("Készen állok a felvételre.")

        self._build_menubar()
        self.dev_ch.SetFocus()        # kezdő fókusz (a JAWS innen indul)

        # élő frissítő időzítő (szint + idő)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_tick, self.timer)
        self.Bind(wx.EVT_CLOSE, self._on_close)

    # ---- menüsor (akadálymentes; biztonságos F-/Ctrl-gyorsbillentyűk) ------

    def _build_menubar(self):
        mb = wx.MenuBar()

        def mi(menu, label, fn):
            item = menu.Append(wx.ID_ANY, label)
            self.Bind(wx.EVT_MENU, lambda e: fn(), item)

        m_rec = wx.Menu()
        mi(m_rec, "&Felvétel\tF5", self._on_record)
        mi(m_rec, "&Szünet / folytatás\tF6", self._on_pause)
        mi(m_rec, "Le&állítás\tF7", self._on_stop)
        mi(m_rec, "Ú&j felvétel", self._on_new)
        mi(m_rec, "Szint &kimondása\tF8", self._say_level)
        mb.Append(m_rec, "&Felvétel")

        m_file = wx.Menu()
        mi(m_file, "Men&tés…\tCtrl+S", self._on_save)
        mi(m_file, "Tovább a sz&erkesztőbe…\tCtrl+E", self._on_edit)
        mb.Append(m_file, "&Fájl")

        self.SetMenuBar(mb)

    # ---- felvétel-vezérlés -------------------------------------------

    def _announce(self, text, force=True):
        self.SetStatusText(text)
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            try:
                sv.speak(text, force=force)
            except Exception:
                pass

    def _device_index(self) -> int:
        sel = self.dev_ch.GetSelection()
        if 0 <= sel < len(self._devs):
            return self._devs[sel][0]
        return -1

    def _on_record(self):
        if self.rec and self.rec.recording:
            return
        if self.rec is None:
            try:
                self.rec = superrec.Recorder(device=self._device_index())
            except Exception as e:
                self._announce(f"A felvevő nem indult: {e}")
                return
        try:
            self.rec.start()
        except Exception as e:
            self._announce(f"A felvétel nem indult: {e}")
            return
        self._last_clip_announced = False
        self.btn_rec.Disable()
        self.btn_pause.Enable()
        self.btn_pause.SetLabel("&Szünet")
        self.btn_stop.Enable()
        self.btn_new.Disable()
        self.btn_save.Disable()
        self.btn_edit.Disable()
        self.dev_ch.Disable()
        self.timer.Start(150)
        self._announce("Felvétel elindult.")

    def _on_pause(self):
        if not (self.rec and self.rec.recording):
            return
        if self.rec.paused:
            self.rec.resume()
            self.btn_pause.SetLabel("&Szünet")
            self._announce("Felvétel folytatva.")
        else:
            self.rec.pause()
            self.btn_pause.SetLabel("&Folytatás")
            self._announce("Felvétel szüneteltetve.")

    def _on_stop(self):
        if not (self.rec and self.rec.recording):
            return
        self.rec.stop()
        self.timer.Stop()
        self._refresh_time()
        self.btn_rec.Enable()
        self.btn_pause.Disable()
        self.btn_stop.Disable()
        self.btn_new.Enable()
        self.btn_save.Enable(self.rec.has_audio())
        self.btn_edit.Enable(self.rec.has_audio())
        self.dev_ch.Enable()
        dur = self.rec.duration()
        clip = " Figyelem: volt telítés a felvételben." if self.rec.clipped else ""
        self._announce(f"Felvétel leállítva. Hossz: {self._fmt_time(dur)}.{clip}")

    def _on_new(self):
        if self.rec:
            self.rec.reset()
        self.rec = None
        self.gauge.SetValue(0)
        self.time_lbl.SetLabel("Idő: 00:00,0")
        self.level_lbl.SetLabel("Szint: – (csúcs)")
        self.btn_save.Disable()
        self.btn_edit.Disable()
        self.btn_new.Disable()
        self._announce("Új felvétel. Nyomd meg a Felvétel gombot.")

    def _on_edit(self):
        if not (self.rec and self.rec.has_audio()):
            return
        from .supereditwin import SuperEditorFrame
        ed = SuperEditorFrame(self.main)
        ed.load_pcm(self.rec.pcm_bytes(), self.rec.freq, self.rec.channels,
                    "felvétel")
        ed.Show()
        self._announce("A felvétel megnyitva a szerkesztőben.")

    # ---- élő frissítés -----------------------------------------------

    def _on_tick(self, e):
        if not (self.rec and self.rec.recording):
            return
        self._refresh_time()
        pk = self.rec.peak
        self.gauge.SetValue(int(min(1.0, pk) * 100))
        self.level_lbl.SetLabel(f"Szint: {self.rec.peak_db(pk):.0f} dB (csúcs)")
        if self.rec.clipped and not self._last_clip_announced:
            self._last_clip_announced = True
            self._announce("Telítés! Halkítsd a bemenetet.", force=True)

    def _refresh_time(self):
        if self.rec:
            self.time_lbl.SetLabel(f"Idő: {self._fmt_time(self.rec.duration())}")

    def _say_level(self):
        if self.rec and self.rec.has_audio():
            self._announce(f"Csúcsszint: {self.rec.peak_db(self.rec.peak):.0f} "
                           "decibel.")
        else:
            self._announce("Még nincs jel.")

    @staticmethod
    def _fmt_time(sec: float) -> str:
        m = int(sec // 60)
        s = sec - m * 60
        return f"{m:02d}:{s:04.1f}".replace(".", ",")

    # ---- mentés ------------------------------------------------------

    def _on_save(self):
        if self._busy or not (self.rec and self.rec.has_audio()):
            return
        mp3 = self.fmt_ch.GetSelection() == 1
        ext = "mp3" if mp3 else "wav"
        wild = ("MP3 hangfájl (*.mp3)|*.mp3" if mp3
                else "WAV hangfájl (*.wav)|*.wav")
        dlg = wx.FileDialog(self, "Felvétel mentése", wildcard=wild,
                            defaultFile=f"felvetel.{ext}",
                            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        path = dlg.GetPath()
        dlg.Destroy()
        if not path.lower().endswith("." + ext):
            path += "." + ext
        norm = self.norm_chk.GetValue()
        trim = self.trim_chk.GetValue()
        fade = 300 if self.fade_chk.GetValue() else 0

        self._busy = True
        self.btn_save.Disable()
        self._announce("Mentés és feldolgozás…")

        def work():
            try:
                out = self.rec.save(path, normalize=norm, fade_ms=fade,
                                    trim_silence=trim)
            except Exception as ex:
                wx.CallAfter(self._save_done, None, str(ex))
                return
            wx.CallAfter(self._save_done, out, None)

        threading.Thread(target=work, daemon=True).start()

    def _save_done(self, out, err):
        self._busy = False
        self.btn_save.Enable()
        if err:
            self._announce(f"A mentés nem sikerült: {err}")
            wx.MessageBox(f"Nem sikerült menteni: {err}", "Super Recorder",
                          wx.OK | wx.ICON_ERROR, self)
        else:
            import os
            self._announce(f"Mentve: {os.path.basename(out)}")

    def _on_close(self, e):
        try:
            self.timer.Stop()
            if self.rec:
                self.rec.stop()
        except Exception:
            pass
        if getattr(self.main, "_superrec_win", None) is self:
            self.main._superrec_win = None
        e.Skip()
