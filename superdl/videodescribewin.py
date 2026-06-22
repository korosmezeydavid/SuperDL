"""AI hangalámondás ablak: videó betöltése, beállítások, becsült költség,
majd a hangalámondással ellátott videó elkészítése. A motort a videodescribe
modul adja.
"""

import os
import threading
from pathlib import Path

import wx

from . import videodescribe as VD

VIDEO_WILDCARD = ("Videók (*.mp4;*.mkv;*.avi;*.mov;*.webm;*.m4v)|"
                  "*.mp4;*.mkv;*.avi;*.mov;*.webm;*.m4v|Minden fájl|*.*")
VOICES = [("Beépített magyar hang (eSpeak, internet nélkül)", "espeak"),
          ("Edge neurális magyar (szebb, internet kell)", "edge")]
DETAILS = [("Rövid (egy mondat / jelenet)", "short"),
           ("Részletes (egy-két mondat / jelenet)", "detailed")]


class VideoDescribeFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – AI hangalámondás videóhoz",
                         size=(820, 560))
        self.main = main
        self.src = ""
        self._desc = None
        self._running = False

        self._build()
        self.CreateStatusBar()
        self._announce("Tölts be egy videót. Az AI leírja a képi tartalmát, és "
                       "hanggal beleszövi – így vakon is nézhető lesz.")
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self._check_ai()

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        top = wx.BoxSizer(wx.HORIZONTAL)
        b = wx.Button(p, label="Videó &betöltése…")
        b.Bind(wx.EVT_BUTTON, lambda e: self._load())
        self.src_lbl = wx.StaticText(p, label="Nincs betöltött videó.")
        top.Add(b, 0, wx.RIGHT, 8)
        top.Add(self.src_lbl, 1, wx.ALIGN_CENTER_VERTICAL)
        v.Add(top, 0, wx.EXPAND | wx.ALL, 8)

        self.ai_lbl = wx.StaticText(p, label="")
        v.Add(self.ai_lbl, 0, wx.ALL, 8)

        g = wx.FlexGridSizer(0, 2, 8, 8)
        g.Add(wx.StaticText(p, label="Bejelentő &hang:"), 0,
              wx.ALIGN_CENTER_VERTICAL)
        self.voice_ch = wx.Choice(p, choices=[n for n, _ in VOICES],
                                  name="Bejelentő hang")
        self.voice_ch.SetSelection(0)
        g.Add(self.voice_ch, 0, wx.EXPAND)
        g.Add(wx.StaticText(p, label="&Részletesség:"), 0,
              wx.ALIGN_CENTER_VERTICAL)
        self.detail_ch = wx.Choice(p, choices=[n for n, _ in DETAILS],
                                   name="Részletesség")
        self.detail_ch.SetSelection(0)
        g.Add(self.detail_ch, 0, wx.EXPAND)
        g.Add(wx.StaticText(p, label="&Beszédtempó (-10 lassú … +10 gyors):"),
              0, wx.ALIGN_CENTER_VERTICAL)
        self.rate_spin = wx.SpinCtrl(p, min=-10, max=10, initial=0)
        self.rate_spin.SetName("Beszédtempó")
        g.Add(self.rate_spin, 0)
        v.Add(g, 0, wx.ALL, 10)

        self.duck_chk = wx.CheckBox(
            p, label="Az eredeti hang &halkítása a leírás alatt (ajánlott)")
        self.duck_chk.SetValue(True)
        v.Add(self.duck_chk, 0, wx.ALL, 8)

        b_est = wx.Button(p, label="&Jelenetek és költség megbecslése")
        b_est.Bind(wx.EVT_BUTTON, lambda e: self._estimate())
        v.Add(b_est, 0, wx.ALL, 8)

        v.Add(wx.StaticText(
            p, label="Megjegyzés: a képleírások az AI-szolgáltatódat (a saját "
                     "kulcsodat) használják – minél több a jelenet, annál több "
                     "a hívás. A becsléssel előre láthatod a mennyiséget."),
            0, wx.ALL, 8)

        self.go_btn = wx.Button(p, label="Hangalámondás &készítése…")
        self.go_btn.Bind(wx.EVT_BUTTON, lambda e: self._start())
        v.Add(self.go_btn, 0, wx.ALL, 8)
        self.gauge = wx.Gauge(p, range=100)
        v.Add(self.gauge, 0, wx.EXPAND | wx.ALL, 8)

        p.SetSizer(v)

    # ---- AI-ellenőrzés ------------------------------------------------

    def _check_ai(self):
        try:
            from . import aiclient
            provs = aiclient.available_providers()
        except Exception:
            provs = []
        if provs:
            self.ai_lbl.SetLabel(f"AI-szolgáltató rendben ({', '.join(provs)}).")
        else:
            self.ai_lbl.SetLabel("⚠ Nincs beállított AI-kulcs. A képleíráshoz "
                                 "add meg egy szolgáltató kulcsát a "
                                 "Beállítások → AI fülön.")

    # ---- betöltés / becslés -------------------------------------------

    def _load(self):
        dlg = wx.FileDialog(self, "Videó betöltése", wildcard=VIDEO_WILDCARD,
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.src = dlg.GetPath()
            self.src_lbl.SetLabel(f"Videó: {Path(self.src).name}")
            self._announce("Videó betöltve. Becsüld meg a jelenetek számát, "
                           "vagy indítsd a hangalámondást.")
        dlg.Destroy()

    def _new_describer(self, out=""):
        voice = VOICES[self.voice_ch.GetSelection()][1]
        detail = DETAILS[self.detail_ch.GetSelection()][1]
        return VD.VideoDescriber(
            self.src, out, voice=voice, detail=detail,
            duck=self.duck_chk.GetValue(), rate=self.rate_spin.GetValue(),
            on_status=lambda s: wx.CallAfter(self._announce, s),
            on_progress=lambda f: wx.CallAfter(self.gauge.SetValue,
                                               int(f * 100)))

    def _say(self, text, sound=None):
        """Hallható visszajelzés: állapotsor + saját hang (akkor is, ha a
        bejelentések ki vannak kapcsolva) + opcionális hanghatás."""
        self._announce(text)
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            try:
                sv.speak(text, force=True)
            except Exception:
                pass
        if sound:
            try:
                from . import sounds
                sounds.play(sound)
            except Exception:
                pass

    def _estimate(self):
        if not self.src:
            self._say("Előbb tölts be egy videót.")
            return
        self._say("Számolom a jelenetek számát, egy pillanat…", sound="start")

        def work():
            try:
                n = self._new_describer().estimate_scenes()
            except Exception as e:
                wx.CallAfter(self._say, f"A becslés nem sikerült: {e}", "error")
                return
            wx.CallAfter(self._estimate_done, n)

        threading.Thread(target=work, daemon=True).start()

    def _estimate_done(self, n):
        msg = (f"Körülbelül {n} képkockát ír le az AI ennél a videónál – "
               f"ennyi vízió-hívás lesz a saját kulcsoddal.")
        self._say(msg, sound="done")
        wx.MessageBox(msg, "Becsült AI-hívások",
                      wx.OK | wx.ICON_INFORMATION, self)

    # ---- készítés -----------------------------------------------------

    def _start(self):
        if self._running:
            return
        if not self.src:
            self._announce("Előbb tölts be egy videót.")
            return
        try:
            from . import aiclient
            if not aiclient.available_providers():
                wx.MessageBox("Nincs beállított AI-kulcs. Add meg egy "
                              "szolgáltató kulcsát a Beállítások → AI fülön.",
                              "AI-kulcs kell", wx.OK | wx.ICON_WARNING, self)
                return
        except Exception:
            pass
        stem = Path(self.src).stem + "_hangalamondas"
        save = wx.FileDialog(
            self, "A hangalámondott videó mentése", wildcard="*.mp4|*.mp4",
            defaultFile=f"{stem}.mp4",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if save.ShowModal() != wx.ID_OK:
            save.Destroy()
            return
        out = save.GetPath()
        if not out.lower().endswith(".mp4"):
            out += ".mp4"
        save.Destroy()

        self._running = True
        self.go_btn.Disable()
        self.gauge.SetValue(0)
        self._desc = self._new_describer(out)
        self._sv("video", "start")
        self._announce("A hangalámondás készítése elindult. Ez a videó "
                       "hosszától és a jelenetek számától függően eltarthat.")

        def work():
            ok = self._desc.run()
            wx.CallAfter(self._done, ok, out)

        threading.Thread(target=work, daemon=True).start()

    def _sv(self, key, state):
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            sv.announce(key, state)

    def _done(self, ok, out):
        self._running = False
        self.go_btn.Enable()
        self.gauge.SetValue(100 if ok else 0)
        self._sv("video", "done" if ok else "error")
        if ok:
            self._announce(f"Kész! A hangalámondott videó elmentve: {out}")
            if wx.MessageBox(f"Elkészült:\n{out}\n\nMegnyitod a mappát?",
                             "Hangalámondás kész",
                             wx.YES_NO | wx.ICON_INFORMATION, self) == wx.YES:
                try:
                    os.startfile(str(Path(out).parent))
                except OSError:
                    pass
        else:
            err = self._desc.error if self._desc else "ismeretlen hiba"
            self._announce(f"Nem sikerült: {err}")
            wx.MessageBox(err, "Hiba", wx.OK | wx.ICON_ERROR, self)

    def _announce(self, text):
        self.SetStatusText(text)

    def _on_close(self, e):
        if self._desc:
            self._desc.stop()
        if getattr(self.main, "_videodescribe_win", None) is self:
            self.main._videodescribe_win = None
        self.Destroy()
