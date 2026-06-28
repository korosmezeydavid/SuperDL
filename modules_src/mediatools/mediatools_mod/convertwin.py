"""Kötegelt médiakonvertáló ablak: fájlok gyűjtése, cél formátum + minőség,
majd ffmpeg-konvertálás sorban, felolvasott állapottal. A motort a converter
modul adja.
"""

import os
import threading
from pathlib import Path

import wx

from . import converter as C                # konverter-motor a MODULBAN
from superdl import sounds                   # megosztott earconok a Core-ból

MEDIA_EXTS = (".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus",
              ".wma", ".mp4", ".mkv", ".avi", ".webm", ".mov", ".wmv",
              ".flv", ".m4v", ".mpg", ".mpeg", ".ts", ".3gp")
MEDIA_WILDCARD = ("Médiafájlok|" + ";".join(f"*{e}" for e in MEDIA_EXTS)
                  + "|Minden fájl|*.*")
MODE_LABELS = [("Hang → hang (átkódolás)", "audio"),
               ("Videó → videó (konténer/kódolás)", "video"),
               ("Videó → hang (hangsáv kivonása)", "extract")]


class _Drop(wx.FileDropTarget):
    def __init__(self, win):
        super().__init__()
        self.win = win

    def OnDropFiles(self, x, y, files):
        self.win.add_paths(files)
        return True


class BatchConvertFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Kötegelt médiakonvertáló",
                         size=(820, 600))
        self.main = main
        self.files: list[str] = []
        self._converter = None
        self._running = False

        self._build()
        self.CreateStatusBar()
        self._announce("Adj hozzá fájlokat, válassz formátumot, majd "
                       "Konvertálás.")
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self._sync_format_choices()

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        # fájl-gyűjtő gombsor
        b1 = wx.BoxSizer(wx.HORIZONTAL)
        for label, handler in (
                ("&Fájlok hozzáadása…", self._add_files),
                ("&Mappa hozzáadása…", self._add_folder),
                ("Kijelölt &eltávolítása", lambda e: self._remove_selected()),
                ("&Lista törlése", lambda e: self._clear())):
            btn = wx.Button(p, label=label)
            btn.Bind(wx.EVT_BUTTON, handler)
            b1.Add(btn, 0, wx.RIGHT, 6)
        v.Add(b1, 0, wx.ALL, 6)

        # fájllista
        self.list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
                                name="Átalakítandó fájlok")
        self.list.InsertColumn(0, "Fájl", width=520)
        self.list.InsertColumn(1, "Állapot", width=160)
        self.list.Bind(wx.EVT_KEY_DOWN, self._on_list_key)
        self.list.SetDropTarget(_Drop(self))
        v.Add(self.list, 1, wx.EXPAND | wx.ALL, 8)

        # cél: mód + formátum + bitráta
        g = wx.BoxSizer(wx.HORIZONTAL)
        g.Add(wx.StaticText(p, label="&Irány:"), 0,
              wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.mode_ch = wx.Choice(p, choices=[m[0] for m in MODE_LABELS],
                                 name="Irány")
        self.mode_ch.SetSelection(0)
        self.mode_ch.Bind(wx.EVT_CHOICE, lambda e: self._sync_format_choices())
        g.Add(self.mode_ch, 0, wx.RIGHT, 12)

        g.Add(wx.StaticText(p, label="F&ormátum:"), 0,
              wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.fmt_ch = wx.Choice(p, choices=[], name="Formátum")
        self.fmt_ch.Bind(wx.EVT_CHOICE, lambda e: self._sync_bitrate())
        g.Add(self.fmt_ch, 0, wx.RIGHT, 12)

        g.Add(wx.StaticText(p, label="&Bitráta:"), 0,
              wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.br_ch = wx.Choice(p, choices=[f"{b} kbps"
                                           for b in C.AUDIO_BITRATES],
                               name="Bitráta")
        self.br_ch.SetSelection(1)
        g.Add(self.br_ch, 0)
        v.Add(g, 0, wx.ALL, 8)

        # kimeneti mappa
        h = wx.BoxSizer(wx.HORIZONTAL)
        h.Add(wx.StaticText(p, label="&Kimeneti mappa:"), 0,
              wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.out_txt = wx.TextCtrl(
            p, value=str(Path.home() / "Music" / "SuperDL_konvertalt"))
        self.out_txt.SetName("Kimeneti mappa")
        out_btn = wx.Button(p, label="&Tallózás…")
        out_btn.Bind(wx.EVT_BUTTON, self._pick_out)
        h.Add(self.out_txt, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        h.Add(out_btn, 0)
        v.Add(h, 0, wx.EXPAND | wx.ALL, 8)

        # indítás + folyamat
        r = wx.BoxSizer(wx.HORIZONTAL)
        self.go_btn = wx.Button(p, label="Kon&vertálás indítása")
        self.go_btn.Bind(wx.EVT_BUTTON, lambda e: self._start())
        self.stop_btn = wx.Button(p, label="Le&állítás")
        self.stop_btn.Bind(wx.EVT_BUTTON, lambda e: self._stop())
        self.stop_btn.Disable()
        r.Add(self.go_btn, 0, wx.RIGHT, 6)
        r.Add(self.stop_btn, 0)
        v.Add(r, 0, wx.ALL, 6)

        self.gauge = wx.Gauge(p, range=100)
        v.Add(self.gauge, 0, wx.EXPAND | wx.ALL, 8)

        p.SetSizer(v)

    # ---- formátum-választók szinkronja --------------------------------

    def _mode(self) -> str:
        return MODE_LABELS[self.mode_ch.GetSelection()][1]

    def _sync_format_choices(self):
        mode = self._mode()
        if mode == "video":
            fmts = list(C.VIDEO_TARGETS.keys())
        else:
            fmts = list(C.AUDIO_TARGETS.keys())
        self.fmt_ch.Set([f.upper() for f in fmts])
        self.fmt_ch.SetSelection(0)
        self._fmt_keys = fmts
        self._sync_bitrate()

    def _sync_bitrate(self):
        mode = self._mode()
        fmt = self._fmt_keys[self.fmt_ch.GetSelection()]
        # bitráta csak veszteséges hangformátumnál értelmes
        lossy_audio = mode in ("audio", "extract") and fmt not in ("flac", "wav")
        self.br_ch.Enable(lossy_audio)

    # ---- fájlgyűjtés --------------------------------------------------

    def add_paths(self, paths):
        added = 0
        for path in paths:
            if os.path.isdir(path):
                for root, _dirs, names in os.walk(path):
                    for n in names:
                        if n.lower().endswith(MEDIA_EXTS):
                            added += self._add_one(os.path.join(root, n))
            elif os.path.isfile(path):
                added += self._add_one(path)
        if added:
            self._announce(f"{added} fájl hozzáadva. Összesen "
                           f"{len(self.files)}.")

    def _add_one(self, path: str) -> int:
        if path in self.files:
            return 0
        self.files.append(path)
        row = self.list.InsertItem(self.list.GetItemCount(),
                                   Path(path).name)
        self.list.SetItem(row, 1, "várakozik")
        return 1

    def _add_files(self, e):
        dlg = wx.FileDialog(self, "Fájlok hozzáadása",
                            wildcard=MEDIA_WILDCARD,
                            style=wx.FD_OPEN | wx.FD_MULTIPLE
                            | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.add_paths(dlg.GetPaths())
        dlg.Destroy()

    def _add_folder(self, e):
        dlg = wx.DirDialog(self, "Mappa hozzáadása (az összes médiafájl)")
        if dlg.ShowModal() == wx.ID_OK:
            self.add_paths([dlg.GetPath()])
        dlg.Destroy()

    def _on_list_key(self, e):
        if e.GetKeyCode() == wx.WXK_DELETE:
            self._remove_selected()
        else:
            e.Skip()

    def _remove_selected(self):
        if self._running:
            return
        i = self.list.GetFirstSelected()
        if 0 <= i < len(self.files):
            self.files.pop(i)
            self.list.DeleteItem(i)
            self._announce("Eltávolítva a listából.")

    def _clear(self, e=None):
        if self._running:
            return
        self.files.clear()
        self.list.DeleteAllItems()
        self._announce("A lista kiürítve.")

    def _pick_out(self, e):
        dlg = wx.DirDialog(self, "Kimeneti mappa")
        if dlg.ShowModal() == wx.ID_OK:
            self.out_txt.SetValue(dlg.GetPath())
        dlg.Destroy()

    # ---- konvertálás --------------------------------------------------

    def _start(self):
        if self._running:
            return
        if not self.files:
            self._announce("Nincs egyetlen fájl sem a listában.")
            return
        out_dir = self.out_txt.GetValue().strip()
        if not out_dir:
            self._announce("Adj meg kimeneti mappát.")
            return
        mode = self._mode()
        fmt = self._fmt_keys[self.fmt_ch.GetSelection()]
        bitrate = C.AUDIO_BITRATES[self.br_ch.GetSelection()]
        total = len(self.files)

        self._running = True
        self.go_btn.Disable()
        self.stop_btn.Enable()
        self.gauge.SetValue(0)
        self._beeper = sounds.ProgressBeeper()
        self._sv("convert", "start")
        self._announce(f"Konvertálás indul: {total} fájl…")

        self._converter = C.Converter(
            list(self.files), out_dir, mode, fmt, bitrate,
            on_status=lambda i, job: wx.CallAfter(self._on_status, i, job,
                                                  total),
            on_progress=lambda i, fr: wx.CallAfter(self._on_progress, i, fr,
                                                   total))

        def work():
            done, failed = self._converter.run()
            wx.CallAfter(self._finished, done, failed)

        threading.Thread(target=work, daemon=True).start()

    def _on_status(self, i: int, job, total: int):
        if i < self.list.GetItemCount():
            self.list.SetItem(i, 1, job.status)
        if job.status in ("kész", "hiba"):
            n = self._converter.done + self._converter.failed
            tag = "kész" if job.status == "kész" else f"HIBA: {job.error}"
            self._announce(f"{n}/{total} – {Path(job.src).name}: {tag}")
            self.gauge.SetValue(int(n / total * 100))

    def _on_progress(self, i: int, fr: float, total: int):
        n = self._converter.done + self._converter.failed
        overall = (n + fr) / total
        self.gauge.SetValue(min(100, int(overall * 100)))
        self._beeper.update(overall * 100)

    def _sv(self, key, state):
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            sv.announce(key, state)

    def _stop(self):
        if self._converter:
            self._converter.stop()
        self._announce("Leállítás kérve…")

    def _finished(self, done: int, failed: int):
        self._running = False
        self.go_btn.Enable()
        self.stop_btn.Disable()
        self.gauge.SetValue(100 if failed == 0 else self.gauge.GetValue())
        msg = f"Kész: {done} sikeres, {failed} hibás."
        self._sv("convert", "error" if failed and not done else "done")
        self._announce(msg)
        wx.MessageBox(msg, "Konvertálás befejezve",
                      wx.OK | wx.ICON_INFORMATION, self)

    # ---- egyéb --------------------------------------------------------

    def _announce(self, text: str):
        self.SetStatusText(text)

    def _on_close(self, e):
        if self._converter:
            self._converter.stop()
        self.main._convert_win = None
        self.Destroy()
