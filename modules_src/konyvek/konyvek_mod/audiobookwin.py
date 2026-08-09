# -*- coding: utf-8 -*-
"""Hangoskönyv-ablak: egy hangfájl vagy egy mappa (több sáv) mint könyv,
folytatható pozícióval és NEVESÍTETT, szinkronizálható idő-könyvjelzőkkel.

A könyvjelzők a közös `main.bookmarks` (superdl.bookmarks) tárba kerülnek –
ugyanaz, amit az Átjáró a telefonnal szinkronizál. Így a felhasználó a PC-n
letesz egy könyvjelzőt a sorozat hangsávjában, és a mobilján onnan folytathatja.
"""
import os

import wx

from .audiobook_player import (AudioBookPlayer, AudioLibrary, konyv_kulcs,
                               mappa_savok, audio_fajl, ido_str)

_HANG_WILDCARD = ("Hangfájl (*.mp3;*.m4a;*.aac;*.ogg;*.opus;*.wav;*.flac)|"
                  "*.mp3;*.m4a;*.aac;*.ogg;*.oga;*.opus;*.wav;*.flac;*.wma;"
                  "*.mp2;*.mka|Minden fájl|*.*")

_SUGO = (
    "HANGOSKÖNYV – SÚGÓ\n\n"
    "Egy hangfájlt vagy egy egész mappát (több sáv) tudsz megnyitni "
    "hangoskönyvként, és a program megjegyzi, hol tartottál – onnan "
    "folytatható. Könyvjelzőt tehetsz le, és ezek a könyvjelzők "
    "szinkronizálhatók a telefonoddal (Eszközök → Átjáró → Könyvjelzők), így a "
    "másik eszközön onnan folytathatod, ahol abbahagytad.\n\n"
    "MEGNYITÁS\n"
    "• 🎧 Hangfájl: egyetlen hangfájl (pl. egy nagy MP3).\n"
    "• 📁 Mappa: egy mappányi hangfájl – természetes sorrendben egy "
    "hangoskönyvnek számít (több sáv).\n\n"
    "POLC\n"
    "• Amit megnyitsz, felkerül a Polcra (a teljes elérési úttal), és kilépés "
    "után is ott marad. A polcon Enter: az adott hangoskönyv megnyitása és "
    "folytatása onnan, ahol abbahagytad – nem kell újra kikeresned a mappát. "
    "Delete: levétel a polcról.\n\n"
    "VEZÉRLÉS\n"
    "• F5: lejátszás / folytatás.  Ctrl+szóköz: szünet.  Esc: leállítás.\n"
    "• Ctrl+balra / Ctrl+jobbra: 15 másodperc vissza / előre.\n"
    "• Előző/Következő sáv gomb: sávok közt lépés. A sáv vége magától a "
    "következőre lép.\n\n"
    "KÖNYVJELZŐK\n"
    "• Ctrl+B: könyvjelző az aktuális helyre (sáv + időpont).\n"
    "• Ctrl+Shift+B: a könyv könyvjelzőinek listája (ugrás / törlés).\n\n"
    "Csak a saját, jogtisztán birtokolt hanganyagodhoz. F1: ez a súgó. "
    "Escape: leállítás."
)


def _mondd(main, szoveg):
    if not (szoveg or "").strip():
        return
    try:
        from superdl import screenreader
        if screenreader.speak(szoveg):
            return
    except Exception:
        pass
    sv = getattr(main, "selfvoice", None)
    if sv:
        try:
            sv.speak(szoveg, force=True)
        except Exception:
            pass


class AudioBookFrame(wx.Frame):
    def __init__(self, main, open_path: str = ""):
        super().__init__(main, title="SuperDL – Hangoskönyv", size=(900, 640))
        self.main = main
        self._closing = False
        self.store = getattr(main, "bookmarks", None)
        self.lib = AudioLibrary()  # a megnyitott hangoskönyvek POLCA (teljes úttal)
        self._book = ""            # a hangoskönyv kulcsa (mappa- vagy fájlnév)
        self._bookkey = ""         # a polc-kulcs (az AudioLibrary-hez)
        self._title = ""
        self._resume_at = None     # (sáv-index, ms) a mentett folytatáshoz
        self.player = AudioBookPlayer(on_track_end=self._on_track_end_bg,
                                      on_error=self._on_error_bg)
        self._build()
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.CreateStatusBar()
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._tick, self.timer)
        self.timer.Start(500)
        self.Centre()
        if open_path:
            wx.CallAfter(self._open_any, open_path)
        else:
            wx.CallAfter(self._indul)

    def _indul(self):
        self._refresh_shelf()
        if self.polc.GetCount():
            self.polc.SetSelection(0)
            self.polc.SetFocus()
            self._mond("Hangoskönyv. A polcon vannak a korábban megnyitott "
                       "hangoskönyveid – válassz egyet, és Enter: folytatás "
                       "onnan, ahol abbahagytad. Vagy nyiss meg újat. Súgó: F1.")
        else:
            self._mond("Hangoskönyv. Nyiss meg egy hangfájlt vagy egy mappát – "
                       "felkerül a polcra, és legközelebb egy Enterrel "
                       "folytathatod. Súgó: F1.")

    # ---- felépítés ----
    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        top = wx.BoxSizer(wx.HORIZONTAL)
        b_f = wx.Button(p, label="🎧 &Hangfájl megnyitása…")
        b_f.Bind(wx.EVT_BUTTON, lambda e: self._open_file())
        b_m = wx.Button(p, label="📁 &Mappa megnyitása…")
        b_m.Bind(wx.EVT_BUTTON, lambda e: self._open_folder())
        self.cim_lbl = wx.StaticText(p, label="Nincs megnyitott hangoskönyv.")
        top.Add(b_f, 0, wx.RIGHT, 8)
        top.Add(b_m, 0, wx.RIGHT, 8)
        top.Add(self.cim_lbl, 1, wx.ALIGN_CENTER_VERTICAL)
        v.Add(top, 0, wx.EXPAND | wx.ALL, 8)

        ctl = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (
                ("&Lejátszás / Folytatás (F5)", lambda e: self._play()),
                ("&Szünet (Ctrl+szóköz)", lambda e: self._toggle()),
                ("Le&állítás (Esc)", lambda e: self._stop()),
                ("−15 mp", lambda e: self._relseek(-15)),
                ("+15 mp", lambda e: self._relseek(15)),
                ("&Előző sáv", lambda e: self._prev_track()),
                ("&Következő sáv", lambda e: self._next_track()),
                ("Köny&vjelző (Ctrl+B)", lambda e: self._add_bookmark()),
                ("Könyvj&elzők… (Ctrl+Shift+B)",
                 lambda e: self._show_bookmarks())):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            ctl.Add(b, 0, wx.RIGHT, 4)
        v.Add(ctl, 0, wx.LEFT | wx.BOTTOM, 8)

        self.poz_lbl = wx.StaticText(p, label="")
        self.poz_lbl.SetName("Lejátszási pozíció")
        v.Add(self.poz_lbl, 0, wx.LEFT | wx.BOTTOM, 8)

        v.Add(wx.StaticText(p, label="&Polc – megnyitott hangoskönyvek (Enter: "
              "megnyitás és folytatás onnan, ahol abbahagytad; Delete: "
              "eltávolítás):"), 0, wx.LEFT, 8)
        self.polc = wx.ListBox(p)
        self.polc.SetName("Polc – megnyitott hangoskönyvek")
        self.polc.Bind(wx.EVT_LISTBOX_DCLICK,
                       lambda e: self._open_shelf_selected())
        self.polc.Bind(wx.EVT_KEY_DOWN, self._on_shelf_key)
        v.Add(self.polc, 1, wx.EXPAND | wx.ALL, 8)

        v.Add(wx.StaticText(p, label="Sá&vok (Enter: az adott sáv lejátszása):"),
              0, wx.LEFT, 8)
        self.sav_lista = wx.ListBox(p)
        self.sav_lista.SetName("Sávok")
        self.sav_lista.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._play_selected())
        self.sav_lista.Bind(wx.EVT_KEY_DOWN, self._on_list_key)
        v.Add(self.sav_lista, 1, wx.EXPAND | wx.ALL, 8)

        footer = wx.BoxSizer(wx.HORIZONTAL)
        b_s = wx.Button(p, label="&Súgó (F1)")
        b_s.Bind(wx.EVT_BUTTON, lambda e: self._help())
        footer.Add(b_s, 0, wx.RIGHT, 6)
        b_t = wx.Button(p, label="❤ &Támogatás")
        b_t.Bind(wx.EVT_BUTTON, lambda e: self._tamogatas())
        footer.Add(b_t, 0)
        v.Add(footer, 0, wx.ALL, 8)
        p.SetSizer(v)

        # Az Entert CHAR_HOOK-kal fogjuk el: a wx/Windows a ListBox Enterjét nem
        # mindig adja tovább EVT_KEY_DOWN-on, ezért a polcon/sávlistán az Enter
        # enélkül „néma" lenne.
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

        ids = {k: wx.NewIdRef() for k in
               ("play", "pause", "stop", "back", "fwd", "bm", "bmlist", "help")}
        self.Bind(wx.EVT_MENU, lambda e: self._play(), id=ids["play"])
        self.Bind(wx.EVT_MENU, lambda e: self._toggle(), id=ids["pause"])
        self.Bind(wx.EVT_MENU, lambda e: self._stop(), id=ids["stop"])
        self.Bind(wx.EVT_MENU, lambda e: self._relseek(-15), id=ids["back"])
        self.Bind(wx.EVT_MENU, lambda e: self._relseek(15), id=ids["fwd"])
        self.Bind(wx.EVT_MENU, lambda e: self._add_bookmark(), id=ids["bm"])
        self.Bind(wx.EVT_MENU, lambda e: self._show_bookmarks(), id=ids["bmlist"])
        self.Bind(wx.EVT_MENU, lambda e: self._help(), id=ids["help"])
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_NORMAL, wx.WXK_F5, ids["play"]),
            (wx.ACCEL_CTRL, wx.WXK_SPACE, ids["pause"]),
            (wx.ACCEL_NORMAL, wx.WXK_ESCAPE, ids["stop"]),
            (wx.ACCEL_CTRL, wx.WXK_LEFT, ids["back"]),
            (wx.ACCEL_CTRL, wx.WXK_RIGHT, ids["fwd"]),
            (wx.ACCEL_CTRL, ord('B'), ids["bm"]),
            (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('B'), ids["bmlist"]),
            (wx.ACCEL_NORMAL, wx.WXK_F1, ids["help"]),
        ]))

    # ---- megnyitás ----
    def _open_file(self):
        with wx.FileDialog(self, "Hangfájl megnyitása", wildcard=_HANG_WILDCARD,
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self._open_any(dlg.GetPath())

    def _open_folder(self):
        with wx.DirDialog(self, "Hangoskönyv-mappa megnyitása") as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self._open_any(dlg.GetPath())

    def _open_any(self, path):
        if self._closing:
            return
        self.player.stop()
        is_dir = os.path.isdir(path)
        if is_dir:
            savok = mappa_savok(path)
            if not savok:
                self._mond("Ebben a mappában nincs lejátszható hangfájl.")
                return
            self._book = os.path.basename(path.rstrip("/\\")) or path
            self._title = self._book
        else:
            if not os.path.isfile(path) or not audio_fajl(path):
                self._mond("Ez a hangfájl nem található, vagy nem hangfájl.")
                return
            savok = [path]
            self._book = os.path.basename(path)
            self._title = os.path.splitext(self._book)[0]
        self._bookkey = konyv_kulcs(path, is_dir)
        self.player.load(savok, book_root=(path if is_dir else ""))
        self._resume_at = None
        self._fill_tracklist()
        self.cim_lbl.SetLabel(f"Hangoskönyv: {self._title}  ({len(savok)} sáv)")
        # felkerül a POLCRA (teljes úttal); a meglévő folytatást megtartja
        self.lib.upsert(path, self._title, is_dir)
        self._refresh_shelf()
        uzenet = (f"Hangoskönyv megnyitva: {self._title}, {len(savok)} sáv. "
                  "Lejátszás: F5. Könyvjelző: Ctrl+B.")
        it = self.lib.get(self._bookkey)
        if it and (it.get("ms") or it.get("track")):
            i = self.player.track_index_of(it.get("track", ""))
            if i is None:
                i = 0
            self._resume_at = (i, int(it.get("ms", 0)))
            self.player.idx = i
            self.sav_lista.SetSelection(i)
            uzenet = (f"Hangoskönyv: {self._title}. Korábban itt tartottál: "
                      f"{i + 1}. sáv, {ido_str(int(it.get('ms', 0)) / 1000)}. "
                      "F5: folytatás onnan. Ctrl+B: könyvjelző.")
        self._mond(uzenet)

    def _fill_tracklist(self):
        self.sav_lista.Clear()
        for i, ut in enumerate(self.player.tracks):
            # a relatív út a kötet-almappát is mutatja (pl. „1. kötet/03.mp3")
            self.sav_lista.Append(f"{i + 1}. {self.player.track_id(ut)}")
        if self.player.tracks:
            self.sav_lista.SetSelection(self.player.idx)

    # ---- vezérlés ----
    def _play(self):
        if not self.player.tracks:
            self._mond("Előbb nyiss meg egy hangfájlt vagy mappát.")
            return
        if self.player.is_active():
            if self.player.is_paused():
                self.player.player.resume()
                self.SetStatusText("Folytatás.")
            return
        if self._resume_at:
            i, ms = self._resume_at
            self._resume_at = None
            self.player.play_track(i, ms / 1000.0)
        else:
            self.player.play_track(self.player.idx, 0.0)
        self.SetStatusText("Lejátszás.")

    def _toggle(self):
        if not self.player.is_active():
            self._play()
            return
        szunet = self.player.toggle_pause()
        self.SetStatusText("Szünet." if szunet else "Folytatás.")
        if szunet:
            self._save_resume()

    def _stop(self):
        if self.player.is_active():
            self._save_resume()
        self.player.stop()
        self.SetStatusText("Leállítva. A helyet megjegyeztem.")

    def _relseek(self, delta):
        if self.player.is_active():
            self.player.relative_seek(delta)
            self._mond(("Előre " if delta > 0 else "Vissza ")
                       + f"{abs(delta)} másodperc.")

    def _prev_track(self):
        if self.player.prev_track():
            self.sav_lista.SetSelection(self.player.idx)
            self._mond(f"{self.player.idx + 1}. sáv: "
                       f"{os.path.basename(self.player.current_path())}")
        else:
            self._mond("Ez az első sáv.")

    def _next_track(self):
        if self.player.next_track():
            self.sav_lista.SetSelection(self.player.idx)
            self._mond(f"{self.player.idx + 1}. sáv: "
                       f"{os.path.basename(self.player.current_path())}")
        else:
            self._mond("Ez volt az utolsó sáv.")

    def _play_selected(self):
        i = self.sav_lista.GetSelection()
        if 0 <= i < self.player.track_count():
            self.player.play_track(i, 0.0)
            self.SetStatusText(f"{i + 1}. sáv lejátszása.")

    def _on_list_key(self, e):
        if e.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._play_selected()
        else:
            e.Skip()

    # ---- a lejátszó háttér-visszahívásai (más szálról) ----
    def _on_track_end_bg(self):
        wx.CallAfter(self._on_track_end)

    def _on_error_bg(self, txt):
        wx.CallAfter(lambda: self.SetStatusText(f"Lejátszási hiba: {txt}"))

    def _on_track_end(self):
        if self._closing:
            return
        if self.player.next_track():
            self.sav_lista.SetSelection(self.player.idx)
            self.SetStatusText(f"{self.player.idx + 1}. sáv.")
        else:
            self.SetStatusText("A hangoskönyv végére értem.")

    def _tick(self, e):
        if self._closing or not self.player.tracks:
            return
        if self.player.is_active():
            poz = self.player.position()
            hossz = self.player.duration()
            n = self.player.track_count()
            self.poz_lbl.SetLabel(
                f"{self.player.idx + 1}/{n}. sáv – {ido_str(poz)}"
                + (f" / {ido_str(hossz)}" if hossz else ""))

    # ---- könyvjelzők ----
    def _savszoveg(self):
        return (f"{self.player.idx + 1}. sáv • "
                f"{ido_str(self.player.position())}")

    def _add_bookmark(self):
        if not self.store or not self._book:
            self._mond("Nincs megnyitott hangoskönyv.")
            return
        track = self.player.track_id()      # relatív út (kötet-almappával együtt)
        pos_ms = int(max(0.0, self.player.position()) * 1000)
        prev = self._savszoveg()
        self.store.add(self._book, title=self._title, kind="audio",
                       track=track, pos_ms=pos_ms, preview=prev)
        self._save_resume()
        self._mond(f"Hang-könyvjelző elmentve: {prev}. Az Átjáróban "
                   "szinkronizálhatod a telefonnal.")

    def _show_bookmarks(self):
        if not self.store or not self._book:
            self._mond("Nincs megnyitott hangoskönyv.")
            return
        from .readerwin import _BookmarkDialog
        if not self.store.for_book(self._book):
            self._mond("Ehhez a hangoskönyvhöz még nincs könyvjelző – tegyél le "
                       "egyet a Ctrl+B-vel.")
            return
        dlg = _BookmarkDialog(self, self.store, self._book)
        rc = dlg.ShowModal()
        cel = dlg.valasztott
        dlg.Destroy()
        if rc == wx.ID_OK and cel is not None:
            self._jump_bookmark(cel)

    def _jump_bookmark(self, bm):
        i = self.player.track_index_of(bm.track) if bm.track else None
        if i is None:
            i = self.player.idx
        self.player.play_track(i, max(0, int(bm.pos_ms)) / 1000.0)
        self.sav_lista.SetSelection(i)
        self._mond(f"Ugrás ide: {bm.preview or (str(i + 1) + '. sáv')}.")

    # ---- polc + folytatás (a polc a teljes utat és a folytatást is tárolja) ----
    def _save_resume(self):
        if not self._bookkey:
            return
        try:
            self.lib.set_resume(
                self._bookkey, self.player.track_id(),
                int(max(0.0, self.player.position()) * 1000))
            self._refresh_shelf()
        except Exception:
            pass

    def _refresh_shelf(self):
        self._shelf_items = self.lib.recent()
        self.polc.Clear()
        for it in self._shelf_items:
            hol = ""
            if it.get("ms") or it.get("track"):
                hol = f"  – {ido_str(int(it.get('ms', 0)) / 1000)}"
            jel = "📁 " if it.get("is_dir") else "🎧 "
            self.polc.Append(f"{jel}{it.get('title') or it.get('key')}{hol}")

    def _open_shelf_selected(self):
        items = getattr(self, "_shelf_items", [])
        if not items:
            self._mond("A polc üres – nyiss meg egy hangfájlt vagy mappát.")
            return
        i = self.polc.GetSelection()
        if i < 0:
            i = 0                      # ha nincs kijelölés, az elsőt nyitjuk
        it = items[i]
        path = it.get("path", "")
        if not path or not os.path.exists(path):
            self._mond(f"„{it.get('title') or it.get('key')}” már nem található "
                       "ezen a helyen – lehet, hogy áthelyezted vagy törölted. "
                       "A Delete-tel leveheted a polcról.")
            return
        self._open_any(path)

    def _on_shelf_key(self, e):
        kc = e.GetKeyCode()
        items = getattr(self, "_shelf_items", [])
        if kc in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._open_shelf_selected()
        elif kc == wx.WXK_DELETE:
            i = self.polc.GetSelection()
            if 0 <= i < len(items):
                self.lib.remove(items[i]["key"])
                self._refresh_shelf()
                self._mond("Levéve a polcról.")
        else:
            e.Skip()

    def _on_char_hook(self, e):
        """Az Enter megbízható elkapása: a fókuszált listán megnyitja/lejátssza a
        kijelöltet (a ListBox az Entert nem mindig adja tovább EVT_KEY_DOWN-on)."""
        if e.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            foc = self.FindFocus()
            if foc is self.polc:
                self._open_shelf_selected()
                return
            if foc is self.sav_lista:
                self._play_selected()
                return
        e.Skip()

    # ---- súgó / támogatás / zárás ----
    def _help(self):
        try:
            from superdl.helpdialog import show_help
            show_help(self, "Hangoskönyv", _SUGO)
        except Exception:
            wx.MessageBox(_SUGO, "Súgó – Hangoskönyv",
                          wx.OK | wx.ICON_INFORMATION, self)

    def _tamogatas(self):
        try:
            from superdl.supportwin import SupportDialog
            SupportDialog(self).ShowModal()
        except Exception:
            self._mond("A támogatási ablak most nem érhető el.")

    def _mond(self, szoveg):
        _mondd(self.main, szoveg)
        self.SetStatusText((szoveg or "").split("\n")[0])

    def _on_close(self, e):
        self._closing = True
        try:
            self.timer.Stop()
        except Exception:
            pass
        self._save_resume()
        try:
            self.player.close()
        except Exception:
            pass
        if getattr(self.main, "_audiobook_win", None) is self:
            self.main._audiobook_win = None
        e.Skip()
