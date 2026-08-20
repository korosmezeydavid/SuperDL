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

# FONTOS: ez a lista szűri a MAPPÁBÓL beolvasott fájlokat is. Egy tesztelő
# jelezte, hogy a DVD-s .VOB fájlokat egyesével ki lehetett választani (és a
# konvertálás ment is), mappából viszont kimaradtak – mert ez a lista nem
# tartalmazta. A DVD/AVCHD-család ezért most itt van.
MEDIA_EXTS = (".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus",
              ".wma", ".mp4", ".mkv", ".avi", ".webm", ".mov", ".wmv",
              ".flv", ".m4v", ".mpg", ".mpeg", ".ts", ".3gp",
              ".vob", ".m2v", ".mpe", ".m2ts", ".mts",
              # RITKÁBB HANGFORMÁTUMOK – a beépített ffmpeg mindet olvassa.
              # Miki jelzésére (2026-08-20): egy .ape fájl nem volt a listában,
              # ezért kellett a „minden fájl" kerülőút. Inkább legyen benne
              # minden, amit tényleg meg tudunk nyitni.
              ".ape", ".wv", ".tta", ".tak", ".mpc", ".shn", ".dsf", ".dff",
              ".aiff", ".aif", ".aifc", ".au", ".amr", ".caf", ".spx",
              ".ra", ".ac3", ".dts", ".mka", ".m4b", ".oga", ".w64")
MEDIA_WILDCARD = ("Médiafájlok|" + ";".join(f"*{e}" for e in MEDIA_EXTS)
                  + "|Minden fájl|*.*")


def _jegyzet(szoveg):
    """Nyom az összeomlás-naplóban (régebbi Core-on egyszerűen nem csinál
    semmit – a modul így is működik)."""
    try:
        from superdl import osszeomlas
        osszeomlas.jegyzet(szoveg)
    except Exception:
        pass


def _beepitett_valaszto_kell() -> bool:
    """Használjuk-e a saját fájlválasztónkat a Windowsé helyett?

    Igen, ha a felhasználó ezt kérte a Beállításokban, VAGY ha a naplóból
    látszik, hogy a programot korábban natív összeomlás vitte el – akkor
    ugyanis nagy eséllyel épp a rendszer fájlválasztója a hibás, és nem
    engedjük még egyszer elszállni."""
    try:
        import json
        from pathlib import Path
        adat = json.loads((Path.home() / ".superdl.json").read_text(
            encoding="utf-8"))
        if bool(adat.get("beepitett_fajlvalaszto")):
            return True
    except Exception:
        pass
    try:
        from superdl import osszeomlas
        return bool(osszeomlas.volt_osszeomlas())
    except Exception:
        return False


def _beepitett_fajlvalaszto(szulo, kiterjesztesek):
    try:
        from superdl import fajlvalaszto
    except Exception:
        return []
    return fajlvalaszto.valassz_fajlokat(
        szulo, "Fájlok hozzáadása", kiterjesztesek, tobb=True)
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


HELP = """KÖTEGELT MÉDIAKONVERTÁLÓ

MIRE VALÓ
Hang- és videófájlok átalakítása más formátumba – egyszerre többet is.

LÉPÉSRŐL LÉPÉSRE (vakon is)
1. „Fájlok hozzáadása" gomb (vagy „Mappa hozzáadása") – gyűjtsd össze a
   konvertálandó fájlokat. A listából „Kijelölt eltávolítása" / „Lista törlése".
2. „Irány": hang vagy videó kimenet. „Formátum": a célformátum (pl. MP3, MP4).
   „Bitráta": a minőség.
3. „Kimeneti mappa" – hova kerüljön (a „Tallózás" gombbal is).
4. „Konvertálás indítása" – sorban feldolgozza; a haladást bemondja, a végén
   jelzi, kész. „Leállítás" gombbal megszakítható.

GYORSBILLENTYŰK
F1 – súgó.  Tab / Shift+Tab – mozgás.  Enter vagy Szóköz – gomb.  A fájllistában
Delete – kijelölt eltávolítása.

TIPP
Sok fájlnál a program egyenként dolgozik, és mindegyikről szól – nyugodtan
figyelheted a haladást."""


class BatchConvertFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Kötegelt médiakonvertáló",
                         size=(820, 600))
        self.main = main
        self.files: list[str] = []
        self._converter = None
        self._running = False
        self._closing = False        # zárás alatt a háttér-callbackek kilépnek

        self._build()
        self.CreateStatusBar()
        self._announce("Adj hozzá fájlokat, válassz formátumot, majd "
                       "Konvertálás. Súgó: F1.")
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_help_key)
        self._sync_format_choices()

    def _on_help_key(self, e):
        if e.GetKeyCode() == wx.WXK_F1:
            self._help()
        else:
            e.Skip()

    def _help(self):
        try:
            from superdl.helpdialog import show_help
            show_help(self, "Kötegelt médiakonvertáló", HELP)
        except Exception:
            wx.MessageBox(HELP, "Súgó – Médiakonvertáló",
                          wx.OK | wx.ICON_INFORMATION, self)

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

        # DVD: a film több VOB-darabban van (VTS_01_1, VTS_01_2 …) – ezeket
        # külön-külön konvertálni értelmetlen, a felhasználó EGY filmet szeretne.
        self.vob_chk = wx.CheckBox(
            p, label="A DVD &VOB-darabjait fűzze össze egy filmmé")
        self.vob_chk.SetName("A DVD VOB-darabjait (VTS_01_1, VTS_01_2 és így "
                             "tovább) egyetlen filmmé fűzi össze; a menü-fájlt "
                             "kihagyja")
        self.vob_chk.SetValue(True)
        v.Add(self.vob_chk, 0, wx.LEFT | wx.BOTTOM, 8)

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
        # NYOM A NAPLÓBAN: egy felhasználónál a program a Windows
        # fájlválasztójában, könyvtár megnyitásakor natívan kilépett. Ilyenkor
        # nincs Python-hiba, amit elkapnánk – de a napló utolsó sorából
        # kiderül, hogy pont itt tartott. [Miki jelzése, 2026-08-20]
        if _beepitett_valaszto_kell():
            _jegyzet("Beépített fájlválasztó megnyitása (médiakonvertáló)")
            utak = _beepitett_fajlvalaszto(self, MEDIA_EXTS)
            _jegyzet("Beépített fájlválasztó bezárva")
            if utak:
                self.add_paths(utak)
            return
        _jegyzet("Windows fájlválasztó megnyitása (médiakonvertáló)")
        dlg = wx.FileDialog(self, "Fájlok hozzáadása",
                            wildcard=MEDIA_WILDCARD,
                            style=wx.FD_OPEN | wx.FD_MULTIPLE
                            | wx.FD_FILE_MUST_EXIST)
        try:
            if dlg.ShowModal() == wx.ID_OK:
                self.add_paths(dlg.GetPaths())
        finally:
            dlg.Destroy()
            _jegyzet("Windows fájlválasztó bezárva")

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
        # DVD VOB-darabok összefűzése (ha kérték): a lista elemei ilyenkor
        # („VTS_01", [darab1, darab2…]) csoportok is lehetnek.
        bemenet = list(self.files)
        if self.vob_chk.GetValue():
            csoportok = C.vob_csoportok(bemenet)
            osszefuzott = [(nev, f) for nev, f in csoportok if len(f) > 1]
            if osszefuzott:
                bemenet = csoportok
                self._announce(
                    "%d DVD-film darabjait fűzöm össze: %s."
                    % (len(osszefuzott),
                       ", ".join("%s (%d darab)" % (nev, len(f))
                                 for nev, f in osszefuzott)))
        total = len(bemenet)

        self._running = True
        self.go_btn.Disable()
        self.stop_btn.Enable()
        self.gauge.SetValue(0)
        self._beeper = sounds.ProgressBeeper()
        self._sv("convert", "start")
        self._announce(f"Konvertálás indul: {total} fájl…")

        self._converter = C.Converter(
            bemenet, out_dir, mode, fmt, bitrate,
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
            # a bejelentésbe csak a hiba ELSŐ sora (a teljes ffmpeg-üzenet a
            # végi részletező ablakba kerül – ne mondja fel a képernyőolvasó
            # az egész naplót)
            short = (job.error or "").splitlines()[0] if job.status == "hiba" \
                else ""
            tag = "kész" if job.status == "kész" else f"HIBA: {short}"
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
        if self._closing:
            return
        self._running = False
        self.go_btn.Enable()
        self.stop_btn.Disable()
        self.gauge.SetValue(100 if failed == 0 else self.gauge.GetValue())
        msg = f"Kész: {done} sikeres, {failed} hibás."
        self._sv("convert", "error" if failed and not done else "done")
        self._announce(msg)
        if failed and self._converter:
            # a hibás fájlok RÉSZLETES ffmpeg-üzenete – olvasható ablakban, hogy
            # a felhasználó (és mi) lássuk a valódi okot (eddig néma volt)
            errs = [f"• {Path(j.src).name}:\n{j.error}"
                    for j in self._converter.jobs if j.status == "hiba"]
            detail = "\n\n".join(errs[:4])
            if len(errs) > 4:
                detail += f"\n\n… és további {len(errs) - 4} hibás fájl."
            wx.MessageBox(msg + "\n\nA hibák részletei:\n\n" + detail,
                          "Konvertálás – hibák", wx.OK | wx.ICON_WARNING, self)
        else:
            wx.MessageBox(msg, "Konvertálás befejezve",
                          wx.OK | wx.ICON_INFORMATION, self)

    # ---- egyéb --------------------------------------------------------

    def _announce(self, text: str):
        if self._closing:
            return
        self.SetStatusText(text)

    def _on_close(self, e):
        self._closing = True
        if self._converter:
            self._converter.stop()
        self.main._convert_win = None
        self.Destroy()
