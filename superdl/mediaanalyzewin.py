"""Beszélő médiaelemző ablak: egy média- vagy hangfájl ellenőrzése és
hangtechnikai elemzése (LUFS, csúcs, clipping…), valamint EBU R128
hangerő-normalizálás profilonként. A jelentés felolvasható és képernyőolvasóval
is jól bejárható.
"""

import os
import threading

import wx

from . import mediaanalyze as MA

WILDCARD = ("Média (hang/videó)|*.mp3;*.wav;*.flac;*.m4a;*.aac;*.ogg;*.opus;"
            "*.mp4;*.mkv;*.avi;*.mov;*.webm;*.m4v;*.m4b|Minden fájl|*.*")


class MediaAnalyzeFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Beszélő médiaelemző",
                         size=(820, 600))
        self.main = main
        self.src = ""
        self._busy = False
        self._build()
        self.CreateStatusBar()
        self._announce("Tölts be egy hang- vagy videófájlt, és elemzem: "
                       "ép-e, milyen a hangereje (LUFS), van-e torzítás – majd "
                       "ha kéred, normalizálom is.")
        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        top = wx.BoxSizer(wx.HORIZONTAL)
        b = wx.Button(p, label="Fájl &betöltése…")
        b.Bind(wx.EVT_BUTTON, lambda e: self._load())
        self.src_lbl = wx.StaticText(p, label="Nincs betöltött fájl.")
        self.src_lbl.SetName("Betöltött fájl")
        top.Add(b, 0, wx.RIGHT, 8)
        top.Add(self.src_lbl, 1, wx.ALIGN_CENTER_VERTICAL)
        v.Add(top, 0, wx.EXPAND | wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        self.deep = wx.CheckBox(p, label="&Alapos ellenőrzés (teljes "
                                "dekódolás – lassabb, de dekódolási hibát is talál)")
        self.deep.SetName("Alapos ellenőrzés")
        row.Add(self.deep, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        self.analyze_btn = wx.Button(p, label="&Elemzés")
        self.analyze_btn.Bind(wx.EVT_BUTTON, lambda e: self._analyze())
        row.Add(self.analyze_btn, 0)
        v.Add(row, 0, wx.LEFT | wx.BOTTOM, 8)

        v.Add(wx.StaticText(p, label="&Jelentés:"), 0, wx.LEFT, 8)
        self.report = wx.TextCtrl(
            p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP)
        self.report.SetName("Elemzési jelentés")
        v.Add(self.report, 1, wx.EXPAND | wx.ALL, 8)

        # normalizálás
        nb = wx.StaticBox(p, label="Hangerő-normalizálás (EBU R128)")
        ns = wx.StaticBoxSizer(nb, wx.HORIZONTAL)
        ns.Add(wx.StaticText(p, label="&Profil:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.profile = wx.Choice(p, choices=list(MA.NORM_PROFILES.keys()))
        self.profile.SetName("Normalizálási profil")
        self.profile.SetSelection(0)
        ns.Add(self.profile, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        self.norm_btn = wx.Button(p, label="&Normalizálás új fájlba…")
        self.norm_btn.Bind(wx.EVT_BUTTON, lambda e: self._normalize())
        ns.Add(self.norm_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        v.Add(ns, 0, wx.EXPAND | wx.ALL, 8)

        self.gauge = wx.Gauge(p, range=100)
        v.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
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

    def _set_report(self, text, speak=None):
        self.report.SetValue(text)
        self._announce(text.splitlines()[0] if text else "")
        if speak:
            self._say(speak)

    def _busy_on(self, on):
        self._busy = on
        for c in (self.analyze_btn, self.norm_btn):
            c.Enable(not on)
        if not on:
            self.gauge.SetValue(0)

    # ---- fájl ---------------------------------------------------------

    def _load(self):
        dlg = wx.FileDialog(self, "Hang- vagy videófájl", wildcard=WILDCARD,
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.src = dlg.GetPath()
            self.src_lbl.SetLabel(os.path.basename(self.src))
            self._announce(f"Betöltve: {os.path.basename(self.src)}. "
                           "Most nyomd meg az Elemzés gombot.")
        dlg.Destroy()

    def _need_file(self) -> bool:
        if not self.src:
            self._set_report("Előbb tölts be egy fájlt.",
                             speak="Előbb tölts be egy fájlt.")
            return False
        if self._busy:
            return False
        return True

    # ---- elemzés ------------------------------------------------------

    def _analyze(self):
        if not self._need_file():
            return
        ffexe = MA.ff()
        if not ffexe:
            self._set_report("Az ffmpeg nem érhető el.",
                             speak="Az ffmpeg nem érhető el.")
            return
        self._busy_on(True)
        self.gauge.Pulse()
        self._announce("Elemzés folyamatban…")
        deep = self.deep.IsChecked()
        src = self.src

        def work():
            try:
                rep, _data = MA.analyze(ffexe, src, deep=deep)
            except Exception as e:
                rep = f"Hiba az elemzéskor: {e}"
            wx.CallAfter(self._analyzed, rep)

        threading.Thread(target=work, daemon=True).start()

    def _analyzed(self, rep):
        self._busy_on(False)
        # a felolvasott összegzés a lényeg (a teljes jelentés a mezőben olvasható)
        self._set_report(rep, speak="Az elemzés kész. " +
                         " ".join(rep.splitlines()[1:]))

    # ---- normalizálás -------------------------------------------------

    def _normalize(self):
        if not self._need_file():
            return
        ffexe = MA.ff()
        if not ffexe:
            self._set_report("Az ffmpeg nem érhető el.")
            return
        root, ext = os.path.splitext(self.src)
        suggested = os.path.basename(root) + "_normalizalt" + (ext or ".wav")
        dlg = wx.FileDialog(self, "A normalizált fájl mentése",
                            defaultDir=os.path.dirname(self.src),
                            defaultFile=suggested, wildcard=WILDCARD,
                            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        out = dlg.GetPath()
        dlg.Destroy()
        profile = self.profile.GetStringSelection()
        self._busy_on(True)
        self._announce(f"Normalizálás ({profile})…")
        src = self.src

        def prog(f):
            wx.CallAfter(self.gauge.SetValue, int(f * 100))

        def work():
            try:
                ok, msg = MA.normalize(ffexe, src, out, profile, prog)
            except Exception as e:
                ok, msg = False, f"Hiba a normalizáláskor: {e}"
            wx.CallAfter(self._normalized, ok, msg)

        threading.Thread(target=work, daemon=True).start()

    def _normalized(self, ok, msg):
        self._busy_on(False)
        self._set_report(msg, speak=msg)

    def _on_close(self, e):
        if getattr(self.main, "_mediaanalyze_win", None) is self:
            self.main._mediaanalyze_win = None
        self.Destroy()
