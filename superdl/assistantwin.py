"""Hang- vagy írás-vezérelt asszisztens ablak.

Beírod vagy bemondod a parancsot; az AI értelmezi (assistant modul), és a
SuperDL megfelelő eszközéhez/akciójához irányít. A visszajelzést a self-voice
mondja (kiegészítve a képernyőolvasót).
"""

import threading
import wave
from pathlib import Path

import wx

from . import assistant as A


class AssistantFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Asszisztens",
                         size=(720, 520))
        self.main = main
        self._rec_frames = []
        self._stream = None
        self._busy = False

        self._build()
        self.CreateStatusBar()
        self._announce("Írd be vagy mondd be, mit szeretnél. Például: töltsd "
                       "le ezt a linket; mi van ma a naptáramban; nyisd meg a "
                       "rádiót.")
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.cmd.SetFocus()

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="Mit szeretnél? (írd be, Enter = futtatás)"),
              0, wx.ALL, 8)
        self.cmd = wx.TextCtrl(p, style=wx.TE_PROCESS_ENTER)
        self.cmd.SetName("Parancs")
        self.cmd.Bind(wx.EVT_TEXT_ENTER, lambda e: self._run_text())
        v.Add(self.cmd, 0, wx.EXPAND | wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        b_run = wx.Button(p, label="&Futtatás")
        b_run.Bind(wx.EVT_BUTTON, lambda e: self._run_text())
        self.rec_btn = wx.Button(p, label="&Beszéd: felvétel indítása")
        self.rec_btn.Bind(wx.EVT_BUTTON, lambda e: self._toggle_record())
        row.Add(b_run, 0, wx.RIGHT, 6)
        row.Add(self.rec_btn, 0)
        v.Add(row, 0, wx.ALL, 6)

        v.Add(wx.StaticText(p, label="&Napló:"), 0, wx.LEFT | wx.TOP, 8)
        self.log = wx.TextCtrl(
            p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP)
        self.log.SetName("Asszisztens napló")
        v.Add(self.log, 1, wx.EXPAND | wx.ALL, 8)
        p.SetSizer(v)

    # ---- visszajelzés -------------------------------------------------

    def _announce(self, text):
        self.SetStatusText(text)

    def _say(self, text):
        """Hallható + naplózott visszajelzés."""
        self._announce(text)
        self.log.AppendText(text + "\n")
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            try:
                sv.speak(text, force=True)
            except Exception:
                pass

    # ---- szöveges parancs ---------------------------------------------

    def _run_text(self):
        text = self.cmd.GetValue().strip()
        if not text or self._busy:
            return
        self.log.AppendText(f"» {text}\n")
        self._busy = True
        self._announce("Értelmezem…")

        def work():
            result = A.parse_command(text)
            wx.CallAfter(self._execute, result)

        threading.Thread(target=work, daemon=True).start()

    def _execute(self, result):
        self._busy = False
        self.cmd.SetValue("")
        action = result.get("action", "none")
        params = result.get("params", {})
        say = result.get("say", "")
        if say:
            self._say(say)
        try:
            A.execute(self.main, action, params, self._say)
        except Exception as e:
            self._say(f"Nem sikerült végrehajtani: {e}")

    # ---- beszéd (push-to-talk) ----------------------------------------

    def _toggle_record(self):
        if self._stream is None:
            self._start_record()
        else:
            self._stop_record()

    def _start_record(self):
        try:
            import sounddevice as sd
        except Exception:
            self._say("A mikrofon nem érhető el ezen a gépen.")
            return
        self._rec_frames = []

        def cb(indata, frames, t, status):
            self._rec_frames.append(bytes(indata))

        try:
            self._stream = sd.RawInputStream(
                samplerate=16000, channels=1, dtype="int16", callback=cb)
            self._stream.start()
        except Exception as e:
            self._stream = None
            self._say(f"A felvétel nem indult el: {e}")
            return
        self.rec_btn.SetLabel("&Beszéd: felvétel leállítása")
        self._announce("Felvétel… mondd a parancsot, majd nyomd meg újra a "
                       "gombot a leállításhoz.")

    def _stop_record(self):
        st, self._stream = self._stream, None
        self.rec_btn.SetLabel("&Beszéd: felvétel indítása")
        try:
            st.stop()
            st.close()
        except Exception:
            pass
        data = b"".join(self._rec_frames)
        if len(data) < 16000:        # túl rövid (~0,5 mp alatt)
            self._say("Túl rövid felvétel – próbáld újra.")
            return
        self._announce("A beszéd feldolgozása…")
        self._busy = True

        def work():
            text = ""
            err = ""
            try:
                import tempfile
                wav = Path(tempfile.gettempdir()) / "superdl_cmd.wav"
                with wave.open(str(wav), "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(16000)
                    w.writeframes(data)
                from . import aiclient
                text = aiclient.transcribe(str(wav)).strip()
            except Exception as e:
                err = str(e)
            wx.CallAfter(self._heard, text, err)

        threading.Thread(target=work, daemon=True).start()

    def _heard(self, text, err):
        self._busy = False
        if err or not text:
            self._say(f"Nem értettem a beszédet{': ' + err if err else ''}.")
            return
        self.cmd.SetValue(text)
        self._run_text()

    def _on_close(self, e):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        if getattr(self.main, "_assistant_win", None) is self:
            self.main._assistant_win = None
        self.Destroy()
