"""Gépről gépre fájlküldés ablak: két gomb (Küldök / Fogadok) és egy könnyen
bemondható szó-kód. A tényleges átvitelt a p2p modul (magic-wormhole) végzi.
"""

from pathlib import Path

import wx
import wx.adv

from . import p2p


class P2PFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Fájlküldés gépről gépre",
                         size=(720, 560))
        self.main = main
        self.send_session = None
        self.recv_session = None
        self._send_name = ""             # a küldött fájl neve a visszaigazoláshoz

        self._build()
        self.CreateStatusBar()
        self.SetStatusText("Küldéshez: Fájl kiválasztása. Fogadáshoz: írd be a "
                           "küldőtől kapott kódot.")
        self.Bind(wx.EVT_CLOSE, self._on_close)

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        v.Add(wx.StaticText(p, label=(
            "Nagy fájlt is egyszerűen küldhetsz egy másik gépre felhő nélkül. "
            "A küldő kap egy rövid, bemondható kódot (pl. 7-alma-traktor); a "
            "fogadó beírja ugyanazt, és a fájl titkosítva, gépről gépre megy "
            "át.")), 0, wx.ALL, 10)

        # --- KÜLDÉS ---
        sb1 = wx.StaticBoxSizer(wx.StaticBox(p, label="Küldés"), wx.VERTICAL)
        self.send_btn = wx.Button(p, label="&Fájl kiválasztása és küldése…")
        self.send_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_send())
        sb1.Add(self.send_btn, 0, wx.ALL, 6)
        sb1.Add(wx.StaticText(p, label="A küldés &kódja (mondd be a másiknak):"),
                0, wx.LEFT, 6)
        self.code_out = wx.TextCtrl(p, style=wx.TE_READONLY)
        self.code_out.SetName("A küldés kódja")
        f = self.code_out.GetFont()
        f.SetPointSize(f.GetPointSize() + 4)
        self.code_out.SetFont(f)
        sb1.Add(self.code_out, 0, wx.EXPAND | wx.ALL, 6)
        brow = wx.BoxSizer(wx.HORIZONTAL)
        self.copy_btn = wx.Button(p, label="Kód &másolása a vágólapra")
        self.copy_btn.Bind(wx.EVT_BUTTON, lambda e: self._copy_code(manual=True))
        self.copy_btn.Disable()
        self.send_cancel = wx.Button(p, label="Küldés meg&szakítása")
        self.send_cancel.Bind(wx.EVT_BUTTON, lambda e: self._cancel_send())
        self.send_cancel.Disable()
        brow.Add(self.copy_btn, 0, wx.RIGHT, 6)
        brow.Add(self.send_cancel, 0)
        sb1.Add(brow, 0, wx.ALL, 6)
        v.Add(sb1, 0, wx.EXPAND | wx.ALL, 10)

        # --- FOGADÁS ---
        sb2 = wx.StaticBoxSizer(wx.StaticBox(p, label="Fogadás"), wx.VERTICAL)
        cr = wx.BoxSizer(wx.HORIZONTAL)
        cr.Add(wx.StaticText(p, label="A kapott &kód:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.code_in = wx.TextCtrl(p, style=wx.TE_PROCESS_ENTER)
        self.code_in.SetName("A kapott kód")
        self.code_in.Bind(wx.EVT_TEXT_ENTER, lambda e: self._on_receive())
        cr.Add(self.code_in, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.recv_btn = wx.Button(p, label="Fo&gadás")
        self.recv_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_receive())
        cr.Add(self.recv_btn, 0)
        sb2.Add(cr, 0, wx.EXPAND | wx.ALL, 6)

        dr = wx.BoxSizer(wx.HORIZONTAL)
        dr.Add(wx.StaticText(p, label="Hova &mentse:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.dir_txt = wx.TextCtrl(p, value=str(Path.home() / "Downloads"))
        self.dir_txt.SetName("Cél mappa")
        db = wx.Button(p, label="&Tallózás…")
        db.Bind(wx.EVT_BUTTON, lambda e: self._pick_dir())
        dr.Add(self.dir_txt, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        dr.Add(db, 0)
        sb2.Add(dr, 0, wx.EXPAND | wx.ALL, 6)
        v.Add(sb2, 0, wx.EXPAND | wx.ALL, 10)

        p.SetSizer(v)

    # ---- küldés -------------------------------------------------------

    def _on_send(self):
        if self.send_session:
            self.SetStatusText("Már folyamatban van egy küldés.")
            return
        dlg = wx.FileDialog(self, "Küldendő fájl kiválasztása",
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        path = dlg.GetPath()
        dlg.Destroy()
        self._send_name = Path(path).name
        self.code_out.SetValue("")
        self.send_btn.Disable()
        self.send_cancel.Enable()
        self._sv("send", "start")
        self.SetStatusText(f"Küldés előkészítése: {Path(path).name} … "
                           "mindjárt megjelenik a kód.")
        self.send_session = p2p.SendSession(
            path,
            on_code=lambda c: wx.CallAfter(self._send_code, c),
            on_done=lambda ok, msg: wx.CallAfter(self._send_done, ok, msg))
        self.send_session.start()

    def _send_code(self, code):
        self.code_out.SetValue(code)
        self.copy_btn.Enable()
        copied = self._copy_code()       # rögtön a vágólapra is tesszük
        extra = (" A kódot a vágólapra is másoltam – beillesztheted "
                 "Messengerbe, e-mailbe stb. a másiknak."
                 if copied else
                 " (A vágólapra másoláshoz nyomd meg a „Kód másolása” gombot.)")
        self.SetStatusText(f"A küldés kódja: {code}.{extra} Tartsd nyitva az "
                           "ablakot, amíg átmegy a fájl.")

    def _copy_code(self, manual: bool = False) -> bool:
        code = self.code_out.GetValue().strip()
        if not code:
            return False
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(code))
            wx.TheClipboard.Flush()      # marad a vágólapon az ablak után is
            wx.TheClipboard.Close()
            if manual:
                self.SetStatusText(f"A kód a vágólapra másolva: {code}. "
                                   "Beillesztheted a másiknak.")
            return True
        return False

    def _sv(self, key, state):
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            sv.announce(key, state)

    def _notify(self, title: str, text: str):
        """Aktív, figyelemfelkeltő értesítés a küldőnek – akkor is megjelenik
        (és a képernyőolvasó felolvassa), ha épp más ablakban vársz, plusz
        kimondjuk az önhanggal. Ez Farkas István kérése: »a fájl megérkezésekor
        nálam is jelezzen«."""
        try:
            if getattr(self.main, "settings", {}).get("notify", True):
                wx.adv.NotificationMessage(title, text).Show(timeout=10)
        except Exception:
            pass
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            try:
                sv.speak(text, force=True)
            except Exception:
                pass

    def _send_done(self, ok, msg):
        self.send_session = None
        self.send_btn.Enable()
        self.send_cancel.Disable()
        self.copy_btn.Disable()
        self._sv("send", "done" if ok else "error")
        if ok:
            self.code_out.SetValue("")
            name = self._send_name or "A fájl"
            # FONTOS (magyar idézőjel-csapda): a nyitó „ után ZÁRÓ ” kell, nem
            # ASCII " – az előre lezárná az f-stringet
            confirm = f"Kézbesítve: „{name}” megérkezett a másik géphez."
            self.SetStatusText(confirm)
            self._notify("SuperDL – fájl kézbesítve", confirm)
        else:
            self.SetStatusText(msg)
            self._notify("SuperDL – a küldés nem fejeződött be", msg)

    def _cancel_send(self):
        if self.send_session:
            self.send_session.cancel()
            self.SetStatusText("Küldés megszakítása…")

    # ---- fogadás ------------------------------------------------------

    def _on_receive(self):
        if self.recv_session:
            self.SetStatusText("Már folyamatban van egy fogadás.")
            return
        code = self.code_in.GetValue().strip()
        if not code:
            self.SetStatusText("Írd be a küldőtől kapott kódot.")
            return
        out_dir = self.dir_txt.GetValue().strip() or str(Path.home() / "Downloads")
        self.recv_btn.Disable()
        self._sv("receive", "start")
        self.SetStatusText("Csatlakozás a küldőhöz… egy pillanat.")
        self.recv_session = p2p.ReceiveSession(
            code, out_dir,
            on_done=lambda ok, msg: wx.CallAfter(self._recv_done, ok, msg))
        self.recv_session.start()

    def _recv_done(self, ok, msg):
        self.recv_session = None
        self.recv_btn.Enable()
        self._sv("receive", "done" if ok else "error")
        self.SetStatusText(msg)
        if ok and wx.MessageBox(msg + "\n\nMegnyitod a mappát?", "Fájl megérkezett",
                                wx.YES_NO | wx.ICON_INFORMATION, self) == wx.YES:
            import os
            try:
                os.startfile(self.dir_txt.GetValue().strip())
            except OSError:
                pass

    def _pick_dir(self):
        dlg = wx.DirDialog(self, "Cél mappa")
        if dlg.ShowModal() == wx.ID_OK:
            self.dir_txt.SetValue(dlg.GetPath())
        dlg.Destroy()

    def _on_close(self, e):
        if self.send_session:
            self.send_session.cancel()
        if self.recv_session:
            self.recv_session.cancel()
        if getattr(self.main, "_p2p_win", None) is self:
            self.main._p2p_win = None
        self.Destroy()
