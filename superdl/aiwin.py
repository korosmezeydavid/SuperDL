"""Közös, akadálymentes „AI eredmény" ablak.

Minden AI-eszköz ezt használja: egy csak olvasható szövegmező az eredménnyel,
amely a magyar hanggal felolvastatható és fájlba menthető. A számítás a
háttérben fut, így a felület nem fagy meg.
"""

import threading

import wx


class AIResultFrame(wx.Frame):
    def __init__(self, main, title: str, busy: str = "AI feldolgozás "
                 "folyamatban…"):
        super().__init__(main, title=f"SuperDL – {title}", size=(780, 560))
        self.main = main
        self.speaker = getattr(main, "speaker", None)

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        self.status = wx.StaticText(p, label=busy)
        self.status.SetName("Állapot")
        v.Add(self.status, 0, wx.ALL, 8)
        self.text = wx.TextCtrl(
            p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP)
        self.text.SetName("AI eredmény")
        v.Add(self.text, 1, wx.EXPAND | wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        self.b_speak = wx.Button(p, label="&Felolvasás")
        self.b_speak.Bind(wx.EVT_BUTTON, lambda e: self._speak())
        b_stop = wx.Button(p, label="Némí&tás")
        b_stop.Bind(wx.EVT_BUTTON, lambda e: self._stop())
        b_save = wx.Button(p, label="&Mentés…")
        b_save.Bind(wx.EVT_BUTTON, lambda e: self._save())
        b_close = wx.Button(p, wx.ID_CANCEL, "&Bezárás")
        b_close.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        for b in (self.b_speak, b_stop, b_save, b_close):
            row.Add(b, 0, wx.RIGHT, 6)
        v.Add(row, 0, wx.ALL, 8)
        p.SetSizer(v)

        sid = wx.NewIdRef()
        self.Bind(wx.EVT_MENU, lambda e: self._stop(), id=sid)
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_NORMAL, wx.WXK_ESCAPE, sid)]))
        self.Bind(wx.EVT_CLOSE, self._on_close)

    # ---- állapot ------------------------------------------------------

    def set_text(self, text: str):
        self.status.SetLabel("Kész. Felolvasás: a gomb. Mentés: Mentés gomb.")
        self.text.SetValue(text or "(üres válasz)")
        self.text.SetInsertionPoint(0)
        self.text.SetFocus()

    def set_error(self, msg: str):
        self.status.SetLabel("Hiba.")
        self.text.SetValue(msg)
        self.text.SetFocus()

    # ---- műveletek ----------------------------------------------------

    def _speak(self):
        if self.speaker and getattr(self.speaker, "available", False):
            t = self.text.GetValue().strip()
            if t:
                self.speaker.speak(t)
                self.status.SetLabel("Felolvasás… (némítás: Escape)")

    def _stop(self):
        if self.speaker:
            try:
                self.speaker.stop()
            except Exception:
                pass

    def _save(self):
        dlg = wx.FileDialog(
            self, "Mentés szövegfájlba", wildcard="Szöveg (*.txt)|*.txt",
            defaultFile="ai-eredmeny.txt",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            try:
                with open(dlg.GetPath(), "w", encoding="utf-8") as f:
                    f.write(self.text.GetValue())
                self.status.SetLabel(f"Elmentve: {dlg.GetPath()}")
            except OSError as e:
                self.status.SetLabel(f"Mentési hiba: {e}")
        dlg.Destroy()

    def _on_close(self, e):
        self._stop()
        e.Skip()


def run_ai(main, title: str, worker, busy: str = "AI feldolgozás folyamatban…"):
    """Megnyit egy AI-eredmény ablakot, és háttérben lefuttatja a `worker`
    függvényt (amely szöveget ad vissza vagy kivételt dob). Az eredmény vagy a
    hibaüzenet a fő szálon kerül a mezőbe."""
    frame = AIResultFrame(main, title, busy=busy)
    frame.Show()

    def work():
        try:
            result = worker()
        except Exception as e:
            wx.CallAfter(frame.set_error, f"Nem sikerült: {e}")
            return
        wx.CallAfter(frame.set_text, result)

    threading.Thread(target=work, daemon=True).start()
    return frame


def run_ai_progress(main, title: str, worker,
                    busy: str = "AI feldolgozás folyamatban…"):
    """Mint a run_ai, de a `worker(report)` egy `report(üzenet)` függvényt is
    kap, amellyel menet közben frissítheti az állapotsort (pl. hány rész kész)."""
    frame = AIResultFrame(main, title, busy=busy)
    frame.Show()

    def report(msg):
        wx.CallAfter(frame.status.SetLabel, msg)

    def work():
        try:
            result = worker(report)
        except Exception as e:
            wx.CallAfter(frame.set_error, f"Nem sikerült: {e}")
            return
        wx.CallAfter(frame.set_text, result)

    threading.Thread(target=work, daemon=True).start()
    return frame
