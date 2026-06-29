"""Super Recorder – akadálymentes fülre-szerkesztő ablak (It.2).

A videóvágó SZELLEMÉBEN: a hangot lejátszod, hallás után markert dobsz le, a
műveletek a KIJELÖLT marker és a következő közti SZAKASZRA hatnak. Billentyűzetes,
KIMONDOTT, nincs vizuális hullámforma.

Billentyűk: Szóköz=lejátszás/szünet, Esc=leállítás, bal/jobb nyíl=finomtekerés,
M=marker itt, Ctrl+Z/Ctrl+Y=visszavonás/újra.
"""

import os
import tempfile
import threading

import wx

from superdl.audioengine import Player
from . import supereditor, supereffects, superrec


def _human(sec: float) -> str:
    m = int(sec // 60)
    s = sec - m * 60
    return f"{m:02d}:{s:05.2f}".replace(".", ",")


class SuperEditorFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Super Recorder: fülre-szerkesztő",
                         size=(820, 600))
        self.main = main
        self.clip = supereditor.Clip()
        self._pos = 0.0                 # playhead (mp)
        self._busy = False
        self._tmp = os.path.join(tempfile.gettempdir(),
                                 f"superedit_{os.getpid()}.wav")
        self.player = Player()

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        # megnyitás + állapot
        top = wx.BoxSizer(wx.HORIZONTAL)
        b_open = wx.Button(p, label="Hang meg&nyitása…")
        b_open.Bind(wx.EVT_BUTTON, lambda e: self._on_open())
        self.title_lbl = wx.StaticText(p, label="Nincs betöltött hang.")
        top.Add(b_open, 0, wx.RIGHT, 8)
        top.Add(self.title_lbl, 1, wx.ALIGN_CENTER_VERTICAL)
        v.Add(top, 0, wx.EXPAND | wx.ALL, 8)

        # lejátszás-vezérlés
        c = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (
                ("&Lejátszás/szünet (szóköz)", lambda e: self._toggle_play()),
                ("&Elölről", lambda e: self._play_from(0.0)),
                ("Leállí&tás", lambda e: self._stop()),
                ("Ma&rker itt (M)", lambda e: self._add_marker()),
                ("M&ind töröl (marker)", lambda e: self._clear_markers())):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            c.Add(b, 0, wx.RIGHT, 5)
        v.Add(c, 0, wx.LEFT | wx.BOTTOM, 8)

        self.pos_lbl = wx.StaticText(p, label="Pozíció: 00:00,00 / 00:00,00")
        self.pos_lbl.SetName("Lejátszási pozíció és teljes hossz")
        v.Add(self.pos_lbl, 0, wx.LEFT | wx.BOTTOM, 6)

        # markerek
        v.Add(wx.StaticText(p, label="&Markerek (a kijelölthöz tartozó szakaszra "
                            "hatnak a műveletek; Delete = marker törlése):"),
              0, wx.LEFT, 8)
        self.mk_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
                                   size=(-1, 150))
        self.mk_list.SetName("Markerek listája")
        self.mk_list.InsertColumn(0, "Marker", width=140)
        self.mk_list.InsertColumn(1, "Szakasz hossza", width=160)
        self.mk_list.Bind(wx.EVT_LIST_KEY_DOWN, self._on_mk_key)
        self.mk_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED,
                          lambda e: self._play_from(self._sel_section()[0]
                                                    if self._sel_section() else 0.0))
        v.Add(self.mk_list, 0, wx.EXPAND | wx.ALL, 8)

        # szerkesztő-műveletek
        e1 = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn, name in (
                ("Szakasz &törlése", self._del_section, "del"),
                ("Csak a szakasz (&trim)", self._trim_section, "trim"),
                ("Szakasz né&mítása", self._mute_section, "mute"),
                ("Szakasz &másolása", self._copy_section, "copy"),
                ("&Beillesztés itt", self._paste_here, "paste"),
                ("Csen&d beszúrása itt", self._insert_silence, "sil")):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, lambda e, f=fn: f())
            e1.Add(b, 0, wx.RIGHT, 5)
        v.Add(e1, 0, wx.LEFT | wx.BOTTOM, 8)

        # effekt-rack (It.3)
        fx = wx.StaticBoxSizer(wx.HORIZONTAL, p, "Effektek")
        fb = fx.GetStaticBox()
        fx.Add(wx.StaticText(fb, label="E&ffekt:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.fx_ch = wx.Choice(fb, choices=[n for _k, n, _l, _d, _f
                                            in supereffects.EFFECTS])
        self.fx_ch.SetSelection(0)
        self.fx_ch.SetName("Effekt választása")
        self.fx_ch.Bind(wx.EVT_CHOICE, lambda e: self._fx_param_update())
        fx.Add(self.fx_ch, 0, wx.RIGHT, 8)
        self.fx_param_lbl = wx.StaticText(fb, label="")
        fx.Add(self.fx_param_lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.fx_param = wx.TextCtrl(fb, size=(70, -1))
        self.fx_param.SetName("Effekt paramétere")
        fx.Add(self.fx_param, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        b_fxsec = wx.Button(fb, label="Alkalmaz a sza&kaszra")
        b_fxsec.Bind(wx.EVT_BUTTON, lambda e: self._apply_effect(False))
        b_fxall = wx.Button(fb, label="Alkalmaz az e&gészre")
        b_fxall.Bind(wx.EVT_BUTTON, lambda e: self._apply_effect(True))
        fx.Add(b_fxsec, 0, wx.RIGHT, 6)
        fx.Add(b_fxall, 0)
        v.Add(fx, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # vokál-effektek + 2-sáv (It.4)
        vo = wx.StaticBoxSizer(wx.HORIZONTAL, p, "Vokál és 2-sáv")
        vb = vo.GetStaticBox()
        b_voc = wx.Button(vb, label="V&okóder")
        b_voc.Bind(wx.EVT_BUTTON, lambda e: self._vocoder())
        vo.Add(b_voc, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        vo.Add(wx.StaticText(vb, label="erő %:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 2)
        self.voc_amt = wx.TextCtrl(vb, value="100", size=(50, -1))
        self.voc_amt.SetName("Vokóder erőssége százalékban")
        vo.Add(self.voc_amt, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        b_harm = wx.Button(vb, label="&Harmonizer (terc+kvint)")
        b_harm.Bind(wx.EVT_BUTTON, lambda e: self._harmonizer())
        vo.Add(b_harm, 0, wx.RIGHT, 10)
        b_kar = wx.Button(vb, label="Ének el&távolítása (karaoke)")
        b_kar.Bind(wx.EVT_BUTTON, lambda e: self._remove_vocals())
        vo.Add(b_kar, 0, wx.RIGHT, 14)
        b_load = wx.Button(vb, label="Ala&p betöltése…")
        b_load.Bind(wx.EVT_BUTTON, lambda e: self._load_backing())
        vo.Add(b_load, 0, wx.RIGHT, 4)
        b_mix = wx.Button(vb, label="Ke&verés")
        b_mix.Bind(wx.EVT_BUTTON, lambda e: self._mix_backing())
        vo.Add(b_mix, 0)
        v.Add(vo, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self._backing = b""           # a betöltött 2. sáv (alap) PCM-je

        e2 = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_undo = wx.Button(p, label="&Visszavonás (Ctrl+Z)")
        self.btn_undo.Bind(wx.EVT_BUTTON, lambda e: self._undo())
        self.btn_redo = wx.Button(p, label="Új&ra (Ctrl+Y)")
        self.btn_redo.Bind(wx.EVT_BUTTON, lambda e: self._redo())
        self.btn_save = wx.Button(p, label="Men&tés…")
        self.btn_save.Bind(wx.EVT_BUTTON, lambda e: self._on_save())
        for b in (self.btn_undo, self.btn_redo, self.btn_save):
            e2.Add(b, 0, wx.RIGHT, 6)
        v.Add(e2, 0, wx.LEFT | wx.BOTTOM, 8)

        p.SetSizer(v)
        self.CreateStatusBar()
        self.SetStatusText("Nyiss meg egy hangfájlt a szerkesztéshez.")

        self._mk_accel()
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_tick, self.timer)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self._update_buttons()
        self._fx_param_update()

    # ---- gyorsbillentyűk ---------------------------------------------

    def _mk_accel(self):
        ids = {k: wx.NewIdRef() for k in
               ("play", "stop", "mark", "undo", "redo", "left", "right")}
        self.Bind(wx.EVT_MENU, lambda e: self._toggle_play(), id=ids["play"])
        self.Bind(wx.EVT_MENU, lambda e: self._stop(), id=ids["stop"])
        self.Bind(wx.EVT_MENU, lambda e: self._add_marker(), id=ids["mark"])
        self.Bind(wx.EVT_MENU, lambda e: self._undo(), id=ids["undo"])
        self.Bind(wx.EVT_MENU, lambda e: self._redo(), id=ids["redo"])
        self.Bind(wx.EVT_MENU, lambda e: self._nudge(-2.0), id=ids["left"])
        self.Bind(wx.EVT_MENU, lambda e: self._nudge(2.0), id=ids["right"])
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_NORMAL, wx.WXK_SPACE, ids["play"]),
            (wx.ACCEL_NORMAL, wx.WXK_ESCAPE, ids["stop"]),
            (wx.ACCEL_NORMAL, ord("M"), ids["mark"]),
            (wx.ACCEL_CTRL, ord("Z"), ids["undo"]),
            (wx.ACCEL_CTRL, ord("Y"), ids["redo"]),
            (wx.ACCEL_NORMAL, wx.WXK_LEFT, ids["left"]),
            (wx.ACCEL_NORMAL, wx.WXK_RIGHT, ids["right"]),
        ]))

    # ---- segéd -------------------------------------------------------

    def _announce(self, text):
        self.SetStatusText(text)
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            try:
                sv.speak(text, force=True)
            except Exception:
                pass

    def _render(self):
        """A pillanatnyi PCM kiírása a temp WAV-ba (lejátszáshoz/újratöltéshez)."""
        self.clip.to_wav(self._tmp)

    def _playhead(self) -> float:
        if self.player.is_active():
            return self.player.position()
        return self._pos

    # ---- megnyitás ---------------------------------------------------

    def _on_open(self):
        dlg = wx.FileDialog(
            self, "Hangfájl megnyitása",
            wildcard="Hang (*.wav;*.mp3;*.m4a;*.flac;*.ogg;*.opus)|"
                     "*.wav;*.mp3;*.m4a;*.flac;*.ogg;*.opus|Minden fájl|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        path = dlg.GetPath()
        dlg.Destroy()
        self.SetStatusText("Hang beolvasása…")

        def work():
            try:
                clip = supereditor.Clip.from_file(path)
            except Exception as ex:
                wx.CallAfter(self._announce, f"Nem nyitható meg: {ex}")
                return
            wx.CallAfter(self._loaded, clip, os.path.basename(path))

        threading.Thread(target=work, daemon=True).start()

    def load_pcm(self, pcm: bytes, freq: int, channels: int, name="felvétel"):
        """Kész PCM betöltése a szerkesztőbe (a felvevőből „Szerkesztés"-re)."""
        self._loaded(supereditor.Clip(pcm, freq, channels), name)

    def _loaded(self, clip, name):
        self._stop()
        self.clip = clip
        self._pos = 0.0
        self._render()
        self.title_lbl.SetLabel(f"Hang: {name}  ({_human(clip.duration())})")
        self._refresh_markers()
        self._refresh_pos()
        self._update_buttons()
        self._announce(f"Betöltve: {name}, hossz {_human(clip.duration())}.")

    # ---- lejátszás ---------------------------------------------------

    def _toggle_play(self):
        if not self.clip.has_audio():
            return
        if self.player.is_active():
            self.player.toggle_pause()
        else:
            self._play_from(self._pos)

    def _play_from(self, pos: float):
        if not self.clip.has_audio():
            return
        self._render()
        self.player.play(self._tmp, title="szerkesztő", start=max(0.0, pos))
        self.timer.Start(150)

    def _stop(self):
        try:
            if self.player.is_active():
                self._pos = self.player.position()
            self.player.stop()
        except Exception:
            pass
        self.timer.Stop()
        self._refresh_pos()

    def _nudge(self, delta: float):
        if self.player.is_active():
            self.player.relative_seek(delta)
        else:
            self._pos = max(0.0, min(self._pos + delta, self.clip.duration()))
            self._refresh_pos()

    def _on_tick(self, e):
        if self.player.is_active():
            self._pos = self.player.position()
            self._refresh_pos()
        else:
            self.timer.Stop()

    def _refresh_pos(self):
        self.pos_lbl.SetLabel(
            f"Pozíció: {_human(self._pos)} / {_human(self.clip.duration())}")

    # ---- markerek ----------------------------------------------------

    def _add_marker(self):
        if not self.clip.has_audio():
            return
        at = self._playhead()
        self.clip.add_marker(at)
        self._refresh_markers(select_time=at)
        self._announce(f"Marker: {_human(at)}.")

    def _clear_markers(self):
        self.clip.clear_markers()
        self._refresh_markers()
        self._announce("Markerek törölve.")

    def _on_mk_key(self, e):
        if e.GetKeyCode() == wx.WXK_DELETE:
            i = self.mk_list.GetFirstSelected()
            if i >= 0:
                self.clip.remove_marker(i)
                self._refresh_markers()
                self._announce("Marker törölve.")
        else:
            e.Skip()

    def _refresh_markers(self, select_time=None):
        self.mk_list.DeleteAllItems()
        for i, m in enumerate(self.clip.markers):
            self.mk_list.InsertItem(i, _human(m))
            sec = self.clip.section(i)
            self.mk_list.SetItem(i, 1, _human(sec[1] - sec[0]) if sec else "–")
        if select_time is not None:
            for i, m in enumerate(self.clip.markers):
                if abs(m - select_time) < 1e-4:
                    self.mk_list.Select(i)
                    self.mk_list.Focus(i)
                    break
        elif self.clip.markers:
            self.mk_list.Select(0)

    def _sel_section(self):
        i = self.mk_list.GetFirstSelected()
        return self.clip.section(i) if i >= 0 else None

    # ---- szerkesztő-műveletek ----------------------------------------

    def _need_section(self):
        sec = self._sel_section()
        if not sec:
            self._announce("Előbb tegyél le markereket, és jelölj ki egyet "
                           "a listában – a művelet az ahhoz tartozó szakaszra hat.")
        return sec

    def _after_edit(self, msg):
        self._stop()
        self._render()
        self._refresh_markers()
        self._pos = min(self._pos, self.clip.duration())
        self._refresh_pos()
        self._update_buttons()
        self.title_lbl.SetLabel(self.title_lbl.GetLabel().split("  (")[0]
                                + f"  ({_human(self.clip.duration())})")
        self._announce(msg)

    def _del_section(self):
        sec = self._need_section()
        if sec:
            self.clip.delete_range(*sec)
            self._after_edit(f"Szakasz törölve ({_human(sec[1]-sec[0])}).")

    def _trim_section(self):
        sec = self._need_section()
        if sec:
            self.clip.trim_to(*sec)
            self._after_edit(f"Megtartva a szakasz ({_human(sec[1]-sec[0])}).")

    def _mute_section(self):
        sec = self._need_section()
        if sec:
            self.clip.mute_range(*sec)
            self._after_edit("Szakasz elnémítva.")

    def _copy_section(self):
        sec = self._need_section()
        if sec:
            self.clip.copy_range(*sec)
            self._announce(f"Szakasz vágólapra ({_human(sec[1]-sec[0])}).")

    def _paste_here(self):
        if not self.clip.clipboard:
            self._announce("A vágólap üres – előbb másolj egy szakaszt.")
            return
        self.clip.paste(self._playhead())
        self._after_edit("Beillesztve.")

    def _insert_silence(self):
        dlg = wx.TextEntryDialog(self, "Csend hossza másodpercben:",
                                 "Csend beszúrása", "1")
        if dlg.ShowModal() == wx.ID_OK:
            try:
                dur = float(dlg.GetValue().replace(",", "."))
            except ValueError:
                dur = 0.0
            if dur > 0:
                self.clip.insert_silence(self._playhead(), dur)
                self._after_edit(f"{dur:g} mp csend beszúrva.")
        dlg.Destroy()

    # ---- effekt-rack (It.3) ------------------------------------------

    def _fx_param_update(self):
        """A kiválasztott effekthez tartozó paraméter-mező címkéje/alapja."""
        idx = self.fx_ch.GetSelection()
        if not (0 <= idx < len(supereffects.EFFECTS)):
            return
        _k, _n, lbl, dflt, _f = supereffects.EFFECTS[idx]
        if lbl:
            self.fx_param_lbl.SetLabel(lbl + ":")
            self.fx_param.Enable(True)
            self.fx_param.SetValue(f"{dflt:g}")
        else:
            self.fx_param_lbl.SetLabel("(nincs paraméter)")
            self.fx_param.SetValue("")
            self.fx_param.Enable(False)

    def _apply_effect(self, whole: bool):
        if self._busy or not self.clip.has_audio():
            return
        idx = self.fx_ch.GetSelection()
        key, name, lbl, _dflt, _f = supereffects.EFFECTS[idx]
        param = 0.0
        if lbl:
            try:
                param = float(self.fx_param.GetValue().replace(",", "."))
            except ValueError:
                self._announce("Hibás paraméter – adj meg egy számot.")
                return
        if whole:
            a, b = 0.0, self.clip.duration()
        else:
            sec = self._need_section()
            if not sec:
                return
            a, b = sec
        af = supereffects.build(key, param, b - a, self.clip.freq)
        if not af:
            return
        self._busy = True
        self._announce(f"Effekt alkalmazása: {name}…")

        def work():
            try:
                ok = self.clip.apply_filter(a, b, af)
            except Exception as ex:
                wx.CallAfter(self._fx_done, None, str(ex))
                return
            wx.CallAfter(self._fx_done, ok, None)

        threading.Thread(target=work, daemon=True).start()

    def _fx_done(self, ok, err, msg="Effekt alkalmazva."):
        self._busy = False
        if err:
            self._announce(f"Nem sikerült: {err}")
        elif ok:
            self._after_edit(msg)
        else:
            self._announce("Nincs mire alkalmazni.")

    # ---- vokál-effektek + 2-sáv (It.4) -------------------------------

    def _range(self):
        """A kijelölt szakasz, ha van; különben az EGÉSZ klip."""
        return self._sel_section() or (0.0, self.clip.duration())

    def _run_bg(self, fn, busy_msg, done_msg):
        if self._busy or not self.clip.has_audio():
            return
        self._busy = True
        self._announce(busy_msg)

        def work():
            try:
                ok = fn()
            except Exception as ex:
                wx.CallAfter(self._fx_done, None, str(ex))
                return
            wx.CallAfter(self._fx_done, ok, None, done_msg)

        threading.Thread(target=work, daemon=True).start()

    def _vocoder(self):
        try:
            amt = float(self.voc_amt.GetValue().replace(",", ".")) / 100.0
        except ValueError:
            amt = 1.0
        a, b = self._range()
        self._run_bg(lambda: self.clip.apply_vocoder(a, b, amt),
                     "Vokóder…", "Vokóder alkalmazva.")

    def _harmonizer(self):
        a, b = self._range()
        self._run_bg(lambda: self.clip.apply_harmonizer(a, b),
                     "Harmonizer…", "Harmónia hozzáadva.")

    def _remove_vocals(self):
        self._run_bg(self.clip.remove_vocals,
                     "Ének eltávolítása…", "Ének eltávolítva (karaoke-alap).")

    def _load_backing(self):
        dlg = wx.FileDialog(
            self, "Alap (háttérzene) betöltése",
            wildcard="Hang (*.wav;*.mp3;*.m4a;*.flac;*.ogg)|"
                     "*.wav;*.mp3;*.m4a;*.flac;*.ogg|Minden fájl|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        path = dlg.GetPath()
        dlg.Destroy()
        self._announce("Alap beolvasása…")

        def work():
            try:
                pcm = superrec.decode_to_pcm(path, self.clip.freq,
                                             self.clip.channels)
            except Exception as ex:
                wx.CallAfter(self._announce, f"Nem tölthető be: {ex}")
                return
            self._backing = pcm
            wx.CallAfter(self._announce, "Alap betöltve. Nyomd meg a Keverést.")

        threading.Thread(target=work, daemon=True).start()

    def _mix_backing(self):
        if not self._backing:
            self._announce("Előbb tölts be egy alapot.")
            return
        self._run_bg(lambda: self.clip.mix_with(self._backing, 0.0, -3.0),
                     "Keverés…", "Sávok összekeverve.")

    def _undo(self):
        if self.clip.undo():
            self._after_edit("Visszavonva.")
        else:
            self._announce("Nincs mit visszavonni.")

    def _redo(self):
        if self.clip.redo():
            self._after_edit("Újra alkalmazva.")
        else:
            self._announce("Nincs mit újra alkalmazni.")

    def _update_buttons(self):
        self.btn_undo.Enable(self.clip.can_undo())
        self.btn_redo.Enable(self.clip.can_redo())
        self.btn_save.Enable(self.clip.has_audio())

    # ---- mentés ------------------------------------------------------

    def _on_save(self):
        if self._busy or not self.clip.has_audio():
            return
        dlg = wx.FileDialog(
            self, "Szerkesztett hang mentése",
            wildcard="WAV (*.wav)|*.wav|MP3 (*.mp3)|*.mp3",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        path = dlg.GetPath()
        mp3 = dlg.GetFilterIndex() == 1
        dlg.Destroy()
        ext = ".mp3" if mp3 else ".wav"
        if not path.lower().endswith(ext):
            path += ext
        self._busy = True
        self.btn_save.Disable()
        self._announce("Mentés…")

        def work():
            try:
                out = self.clip.save(path, normalize=False)
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
        else:
            self._announce(f"Mentve: {os.path.basename(out)}")

    def _on_close(self, e):
        try:
            self.timer.Stop()
            self.player.stop()
            if os.path.isfile(self._tmp):
                os.remove(self._tmp)
        except Exception:
            pass
        if getattr(self.main, "_superedit_win", None) is self:
            self.main._superedit_win = None
        e.Skip()
