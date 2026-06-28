"""iPhone csengőhang-készítő ablak: zene betöltése, lejátszás SZÓKÖZZEL, a
megállás pontja a kezdet, a vég bal/jobb nyíllal igazítható, a részlet
meghallgatható, végül mentés .m4r (iPhone) vagy MP3 formátumba.
"""

import os
import threading
from pathlib import Path

import wx

from . import ringtone as R                 # csengőhang-logika a MODULBAN
from superdl.audioengine import Player       # megosztott lejátszó a Core-ból
from superdl.videocompose import human_time, media_duration  # megosztott segédek

AUDIO_WILDCARD = ("Hang (*.mp3;*.m4a;*.wav;*.flac;*.ogg;*.opus;*.aac)|"
                  "*.mp3;*.m4a;*.wav;*.flac;*.ogg;*.opus;*.aac|Minden fájl|*.*")
SAVE_FORMATS = [("iPhone csengőhang (.m4r)", "m4r"), ("MP3", "mp3")]


class RingtoneFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – iPhone csengőhang-készítő",
                         size=(720, 460))
        self.main = main
        self.music = ""
        self.duration = 0.0
        self.start = None          # a kezdőpont (None = még nincs)
        self.length = R.RING_MAX
        self.player = Player()
        self.player.on_state = lambda s: wx.CallAfter(self._player_state, s)
        self._preview = False      # épp a részletet játsszuk-e

        self._build()
        self.CreateStatusBar()
        self._announce("Válassz egy zenét, majd a Szóközzel játszd le, és "
                       "állítsd meg ott, ahol a csengőhang kezdődjön.")
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.Bind(wx.EVT_CLOSE, self._on_close)

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        # zeneválasztó
        r0 = wx.BoxSizer(wx.HORIZONTAL)
        self.mus_txt = wx.TextCtrl(p, style=wx.TE_READONLY)
        self.mus_txt.SetName("Kiválasztott zene")
        b = wx.Button(p, label="&Zene kiválasztása…")
        b.Bind(wx.EVT_BUTTON, lambda e: self._pick_music())
        r0.Add(self.mus_txt, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        r0.Add(b, 0)
        v.Add(r0, 0, wx.EXPAND | wx.ALL, 8)

        v.Add(wx.StaticText(
            p, label="SZÓKÖZ: lejátszás/megállás. Ahol megállítod, ott kezdődik "
                     "a csengőhang. A véget a bal/jobb nyíllal igazíthatod."),
            0, wx.ALL, 8)

        # vezérlőgombok
        g = wx.BoxSizer(wx.HORIZONTAL)
        self.play_btn = wx.Button(p, label="&Lejátszás / megállás (Szóköz)")
        self.play_btn.Bind(wx.EVT_BUTTON, lambda e: self._toggle_play())
        self.restart_btn = wx.Button(p, label="Vissza az &elejére")
        self.restart_btn.Bind(wx.EVT_BUTTON, lambda e: self._restart())
        g.Add(self.play_btn, 0, wx.RIGHT, 6)
        g.Add(self.restart_btn, 0)
        v.Add(g, 0, wx.ALL, 6)

        g2 = wx.BoxSizer(wx.HORIZONTAL)
        self.minus_btn = wx.Button(p, label="Vég &– 1 mp")
        self.minus_btn.Bind(wx.EVT_BUTTON, lambda e: self._adjust(-1.0))
        self.plus_btn = wx.Button(p, label="Vég &+ 1 mp")
        self.plus_btn.Bind(wx.EVT_BUTTON, lambda e: self._adjust(1.0))
        self.prev_btn = wx.Button(p, label="Részlet meg&hallgatása")
        self.prev_btn.Bind(wx.EVT_BUTTON, lambda e: self._preview_segment())
        for btn in (self.minus_btn, self.plus_btn, self.prev_btn):
            g2.Add(btn, 0, wx.RIGHT, 6)
        v.Add(g2, 0, wx.ALL, 6)

        # kijelölés-kijelző
        self.info = wx.StaticText(p, label="Még nincs kijelölt szakasz.")
        v.Add(self.info, 0, wx.ALL, 8)

        self.save_btn = wx.Button(p, label="Csengőhang &mentése…")
        self.save_btn.Bind(wx.EVT_BUTTON, lambda e: self._save())
        v.Add(self.save_btn, 0, wx.ALL, 8)

        p.SetSizer(v)

    # ---- zene + lejátszás ---------------------------------------------

    def _pick_music(self):
        dlg = wx.FileDialog(self, "Zene kiválasztása", wildcard=AUDIO_WILDCARD,
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.music = dlg.GetPath()
            self.mus_txt.SetValue(self.music)
            self.duration = media_duration(self.music)
            self.start = None
            self._update_info()
            self._announce(f"Zene: {Path(self.music).name}, hossza "
                           f"{human_time(self.duration)}. Szóköz: lejátszás.")
        dlg.Destroy()

    def _toggle_play(self):
        if not self.music:
            self._announce("Előbb válassz egy zenét.")
            return
        if self.player.is_active() and not self._preview:
            paused = self.player.toggle_pause()
            if paused:
                self._set_start(self.player.position())
            else:
                self._announce("Lejátszás folytatása.")
        else:
            self._preview = False
            self.player.play(self.music, title=Path(self.music).name)
            self._announce("Lejátszás. A Szóközzel állítsd meg a "
                           "kezdőpontnál.")

    def _restart(self):
        if not self.music:
            return
        self._preview = False
        self.player.play(self.music, title=Path(self.music).name)
        self._announce("Lejátszás az elejéről.")

    def _set_start(self, pos: float):
        self.start = max(0.0, pos)
        avail = max(0.5, self.duration - self.start) if self.duration else R.RING_MAX
        self.length = min(R.RING_MAX, avail)
        self._update_info()
        self._announce(
            f"Kezdőpont: {human_time(self.start)}. Hossz: "
            f"{self.length:.0f} másodperc, vég: {human_time(self._end())}. "
            "A véget a bal/jobb nyíllal igazíthatod.")

    def _end(self) -> float:
        return (self.start or 0) + self.length

    def _max_len(self) -> float:
        if self.duration and self.start is not None:
            return max(R.RING_MIN, min(R.RING_MAX, self.duration - self.start))
        return R.RING_MAX

    def _adjust(self, delta: float):
        if self.start is None:
            self._announce("Előbb állítsd meg a zenét a kezdőpontnál "
                           "(Szóköz).")
            return
        lo = min(R.RING_MIN, self._max_len())
        self.length = max(lo, min(self._max_len(), self.length + delta))
        self._update_info()
        self._announce(f"Hossz: {self.length:.0f} másodperc, vég: "
                       f"{human_time(self._end())}.")

    def _update_info(self):
        if self.start is None:
            self.info.SetLabel("Még nincs kijelölt szakasz. Játszd le a zenét, "
                               "és állítsd meg a kezdőpontnál.")
        else:
            self.info.SetLabel(
                f"Kezdet: {human_time(self.start)}   Vég: "
                f"{human_time(self._end())}   Hossz: {self.length:.0f} mp")

    def _player_state(self, text: str):
        if text == "vége" and self._preview:
            self._preview = False
            self._announce("A részlet vége. Igazíthatsz, vagy mentheted.")
        elif text.startswith("hiba"):
            self._announce(f"Lejátszási hiba: {text}.")

    # ---- meghallgatás + mentés ----------------------------------------

    def _preview_segment(self):
        if self.start is None:
            self._announce("Előbb jelöld ki a kezdőpontot (Szóköz).")
            return
        self._announce("Részlet előkészítése…")
        out = R.preview_path("mp3")
        start, length = self.start, self.length

        def work():
            err = R.make_ringtone(self.music, out, start, length, fmt="mp3")
            wx.CallAfter(self._preview_ready, err, out)

        threading.Thread(target=work, daemon=True).start()

    def _preview_ready(self, err: str, out: str):
        if err:
            self._announce(f"A részlet nem készült el: {err}")
            return
        self._preview = True
        self.player.play(out, title="Részlet")
        self._announce(f"A kijelölt {self.length:.0f} másodperces részlet "
                       "lejátszása.")

    def _save(self):
        if self.start is None:
            self._announce("Előbb jelöld ki a kezdőpontot (Szóköz).")
            return
        fmt_dlg = wx.SingleChoiceDialog(
            self, "Milyen formátumban mentsük?", "Csengőhang mentése",
            [name for name, _ in SAVE_FORMATS])
        if fmt_dlg.ShowModal() != wx.ID_OK:
            fmt_dlg.Destroy()
            return
        fmt = SAVE_FORMATS[fmt_dlg.GetSelection()][1]
        fmt_dlg.Destroy()

        ext = R.FORMATS[fmt][0]
        stem = Path(self.music).stem if self.music else "csengohang"
        save = wx.FileDialog(
            self, "Csengőhang mentése", wildcard=f"*{ext}|*{ext}",
            defaultFile=f"{stem}{ext}",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if save.ShowModal() != wx.ID_OK:
            save.Destroy()
            return
        out = save.GetPath()
        if not out.lower().endswith(ext):
            out += ext
        save.Destroy()

        self.player.stop()
        self.save_btn.Disable()
        self._sv("ringtone", "start")
        self._announce("Mentés…")
        start, length = self.start, self.length

        def work():
            err = R.make_ringtone(self.music, out, start, length, fmt=fmt)
            wx.CallAfter(self._saved, err, out, fmt)

        threading.Thread(target=work, daemon=True).start()

    def _sv(self, key, state):
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            sv.announce(key, state)

    def _saved(self, err: str, out: str, fmt: str):
        self.save_btn.Enable()
        self._sv("ringtone", "error" if err else "done")
        if err:
            self._announce(f"A mentés nem sikerült: {err}")
            wx.MessageBox(err, "Hiba", wx.OK | wx.ICON_ERROR, self)
            return
        hint = ("\n\nAz iPhone-ra az .m4r fájlt a Finderrel/iTunes-szal vagy "
                "a GarageBand alkalmazással másolhatod át."
                if fmt == "m4r" else "")
        self._announce(f"Kész! Elmentve: {out}")
        if wx.MessageBox(f"A csengőhang elkészült:\n{out}{hint}\n\nMegnyitod a "
                         "tartalmazó mappát?", "Csengőhang kész",
                         wx.YES_NO | wx.ICON_INFORMATION, self) == wx.YES:
            try:
                os.startfile(str(Path(out).parent))
            except OSError:
                pass

    # ---- billentyű + zárás --------------------------------------------

    def _on_char_hook(self, e):
        focus = wx.Window.FindFocus()
        code = e.GetKeyCode()
        if isinstance(focus, wx.TextCtrl):
            e.Skip()
            return
        if code == wx.WXK_SPACE and not isinstance(focus, wx.Button):
            self._toggle_play()
            return
        if code == wx.WXK_LEFT:
            self._adjust(-1.0)
            return
        if code == wx.WXK_RIGHT:
            self._adjust(1.0)
            return
        e.Skip()

    def _announce(self, text: str):
        self.SetStatusText(text)

    def _on_close(self, e):
        try:
            self.player.stop()
        except Exception:
            pass
        self.main._ringtone_win = None
        self.Destroy()
