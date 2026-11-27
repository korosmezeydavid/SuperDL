"""Super Recorder – akadálymentes fülre-szerkesztő ablak (It.2).

A videóvágó SZELLEMÉBEN: a hangot lejátszod, hallás után markert dobsz le, a
műveletek a KIJELÖLT marker és a következő közti SZAKASZRA hatnak. Billentyűzetes,
KIMONDOTT, nincs vizuális hullámforma.

Billentyűk: bal és jobb nyíl a lépés, Shift+nyíl a kijelölés, Ctrl+nyíl a
lépésköz. A műveletek az Alt-menüben vannak.
"""

import os
import tempfile
import uuid
import threading

import wx

from superdl.audioengine import Player
from . import supereditor, supereffects, superrec


def _human(sec: float) -> str:
    m = int(sec // 60)
    s = sec - m * 60
    return f"{m:02d}:{s:05.2f}".replace(".", ",")


HELP = """SUPER RECORDER – FÜLRE-SZERKESZTŐ (hangszerkesztő)

MIRE VALÓ
Akadálymentes hangszerkesztő. A műveletek az Alt-menüben vannak, a Tab
csak a markerlistát járja.

LÉPÉS ÉS KIJELÖLÉS
Bal nyíl és jobb nyíl: ennyit lépsz a hangban. Az alap 2 másodperc.
Ctrl+bal és Ctrl+jobb: a lépésközt állítja, 0,1 másodperctől 10 másodpercig.
Shift+bal és Shift+jobb: a lenyomott Shift alatt kijelöli az érintett szakaszt.
A kijelölés megmarad, amíg sima nyíllal tovább nem lépsz.
Ctrl+C másol, Ctrl+X kivág, Ctrl+V beilleszt a pillanatnyi helyre.

MENÜK
Alt+F Fájl: megnyitás, mentés, mintavétel, MP3-bitráta.
Alt+L Lejátszás.  Alt+S Szerkesztés.  Alt+E Effektek.  Alt+V Vokál.
F1 súgó. F5 lejátszás. F6 leállítás. F7 és F8 egy lépés. F9 marker.

A mentésnél az Eredeti mintavétel a forrásé marad. MP3-nál 128–320 kbps."""


class SuperEditorFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Super Recorder: fülre-szerkesztő",
                         size=(820, 600))
        self.main = main
        self.clip = supereditor.Clip()
        self._pos = 0.0                 # playhead (mp)
        self._step = 2.0                # bal/jobb nyíl lépése, 0,1–10 mp
        self._anchor = None             # Shift-kijelölés kezdete
        self._sel = None                # (kezdet, vég) másodperc
        self._busy = False
        self._closing = False           # zárás alatt a háttér-callbackek kilépnek
        self._saved = True              # van-e MENTETLEN szerkesztés? [EDIT-P0-06]
        # ABLAKONKÉNT egyedi: a régi, csak PID-alapú név ugyanazon folyamat
        # MINDEN szerkesztőablakában azonos volt → két ablak egymás lejátszási
        # fájlját írta/törölte (rossz hang szólalt meg). [Herman Tibi EDIT-P0-05]
        self._tmp = os.path.join(tempfile.gettempdir(),
                                 f"superedit_{os.getpid()}_"
                                 f"{uuid.uuid4().hex[:8]}.wav")
        self.player = Player()

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        self.title_lbl = wx.StaticText(p, label="Nincs betöltött hang.")
        self.title_lbl.SetName("A betöltött hang")
        v.Add(self.title_lbl, 0, wx.EXPAND | wx.ALL, 8)
        v.Add(wx.StaticText(p, label=(
            "Alt+F fájl, Alt+L lejátszás, Alt+S szerkesztés, Alt+E effektek, "
            "Alt+V vokál. Nyíl: lépés. Shift+nyíl: kijelölés. Ctrl+nyíl: lépésköz.")),
            0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

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

        self._backing = b""           # a betöltött 2. sáv (alap) PCM-je
        # A mentési választók a Fájl menü rádióiból töltődnek; a tesztek a
        # nevükre és a _on_save olvasására épülnek, a Tab sorrendből kikerülnek.
        self.sr_ch = wx.Choice(self, choices=["Eredeti", "44100 Hz", "48000 Hz"],
                               name="Mentési mintavétel")
        self.sr_ch.SetSelection(0)
        self.sr_ch.Hide()
        self.br_ch = wx.Choice(
            self, choices=["128 kbps", "192 kbps", "256 kbps", "320 kbps"],
            name="MP3 bitráta")
        self.br_ch.SetSelection(2)                 # 256 kbps az alap
        self.br_ch.Hide()

        p.SetSizer(v)
        self.CreateStatusBar()
        self.SetStatusText("Nyiss meg egy hangfájlt a szerkesztéshez.")

        self._build_menubar()
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_tick, self.timer)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_help_key)
        self._update_buttons()
        self.mk_list.SetFocus()

    def _on_help_key(self, e):
        code = e.GetKeyCode()
        if code == wx.WXK_F1:
            try:
                from superdl.helpdialog import show_help
                show_help(self, "Super Recorder – fülre-szerkesztő", HELP)
            except Exception:
                wx.MessageBox(HELP, "Súgó – Fülre-szerkesztő",
                              wx.OK | wx.ICON_INFORMATION, self)
            return
        if code in (wx.WXK_LEFT, wx.WXK_RIGHT):
            focus = self.FindFocus()
            if isinstance(focus, (wx.TextCtrl, wx.Slider, wx.SpinCtrl)):
                e.Skip()
                return
            self._on_arrow(-1 if code == wx.WXK_LEFT else 1,
                           e.ControlDown(), e.ShiftDown())
            return
        e.Skip()

    # ---- menüsor: a műveletek Alt-tal, a Tab csak a markerlistát járja ----

    def _build_menubar(self):
        mb = wx.MenuBar()

        def mi(menu, label, fn):
            item = menu.Append(wx.ID_ANY, label)
            self.Bind(wx.EVT_MENU, lambda e, f=fn: f(), item)
            return item

        m_file = wx.Menu()
        mi(m_file, "Hang meg&nyitása…\tCtrl+O", self._on_open)
        self.mi_save = mi(m_file, "Men&tés…\tCtrl+S", self._on_save)
        m_sr = wx.Menu()
        for i, label in enumerate(("&Eredeti", "44&100 Hz", "4&8000 Hz")):
            item = m_sr.AppendRadioItem(wx.ID_ANY, label)
            if i == 0:
                item.Check(True)
            self.Bind(wx.EVT_MENU, lambda e, n=i: self._set_sr(n), item)
        m_file.AppendSubMenu(m_sr, "&Mintavétel")
        m_br = wx.Menu()
        for i, label in enumerate(("&128 kbps", "1&92 kbps", "&256 kbps",
                                   "&320 kbps")):
            item = m_br.AppendRadioItem(wx.ID_ANY, label)
            if i == 2:
                item.Check(True)
            self.Bind(wx.EVT_MENU, lambda e, n=i: self._set_br(n), item)
        m_file.AppendSubMenu(m_br, "MP3-&bitráta")
        mb.Append(m_file, "&Fájl")

        m_play = wx.Menu()
        mi(m_play, "&Lejátszás / szünet\tF5", self._toggle_play)
        mi(m_play, "&Elölről", lambda: self._play_from(0.0))
        mi(m_play, "Le&állítás\tF6", self._stop)
        mi(m_play, "&Vissza egy lépés\tF7",
           lambda: self._on_arrow(-1, False, False))
        mi(m_play, "Elő&re egy lépés\tF8",
           lambda: self._on_arrow(1, False, False))
        mb.Append(m_play, "&Lejátszás")

        m_edit = wx.Menu()
        mi(m_edit, "&Marker itt\tF9", self._add_marker)
        mi(m_edit, "Minden marker &törlése", self._clear_markers)
        mi(m_edit, "Kijelölés &eldobása", self._clear_selection)
        m_edit.AppendSeparator()
        mi(m_edit, "Szakasz tör&lése", self._del_section)
        mi(m_edit, "Csak a szakasz (t&rim)", self._trim_section)
        mi(m_edit, "Szakasz &némítása", self._mute_section)
        mi(m_edit, "Má&solás\tCtrl+C", self._copy_section)
        mi(m_edit, "Ki&vágás\tCtrl+X", self._cut_section)
        mi(m_edit, "&Beillesztés itt\tCtrl+V", self._paste_here)
        mi(m_edit, "&Csend beszúrása itt", self._insert_silence)
        m_edit.AppendSeparator()
        self.mi_undo = mi(m_edit, "Visszav&onás\tCtrl+Z", self._undo)
        self.mi_redo = mi(m_edit, "Ú&jra\tCtrl+Y", self._redo)
        mb.Append(m_edit, "&Szerkesztés")

        m_fx = wx.Menu()
        mi(m_fx, "Alkalmaz a sza&kaszra", lambda: self._apply_effect(False))
        mi(m_fx, "Alkalmaz az e&gészre", lambda: self._apply_effect(True))
        mb.Append(m_fx, "&Effektek")

        m_voc = wx.Menu()
        mi(m_voc, "&Vokóder", self._vocoder)
        mi(m_voc, "&Harmonizer (terc+kvint)", self._harmonizer)
        mi(m_voc, "Ének &eltávolítása (karaoke)", self._remove_vocals)
        m_voc.AppendSeparator()
        mi(m_voc, "Alap &betöltése…", self._load_backing)
        mi(m_voc, "&Keverés", self._mix_backing)
        mb.Append(m_voc, "&Vokál")

        self.SetMenuBar(mb)

    def _set_sr(self, n):
        self.sr_ch.SetSelection(n)
        self._announce(f"Mintavétel: {self.sr_ch.GetString(n)}.")

    def _set_br(self, n):
        self.br_ch.SetSelection(n)
        self._announce(f"MP3 bitráta: {self.br_ch.GetString(n)}.")

    # ---- segéd -------------------------------------------------------

    def _announce(self, text):
        if self._closing:
            return
        self.SetStatusText(text)
        sv = getattr(self.main, "selfvoice", None)
        # 1) A BEJELENTŐ a KÉPERNYŐOLVASÓ – ELŐSZÖR mindig ŐT kérjük.
        #    FONTOS: képernyőolvasó-módban a Core a saját hangot NÉMÍTJA
        #    (muted=True) ÉPP AZÉRT, hogy az olvasó beszéljen – ezért a
        #    némítás-ellenőrzés CSAK a beépített hangra vonatkozhat, ide nem.
        try:
            from superdl import screenreader
            if screenreader.speak(text):
                return
        except Exception:
            pass
        # 2) Nincs képernyőolvasó → a beépített hang segít ki, DE a Teljes
        #    némítás ilyenkor is némít
        if sv is not None and getattr(sv, "muted", False):
            return
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
        self._saved = True              # frissen betöltve: nincs mentetlen munka
        self._pos = 0.0
        self._anchor = None
        self._sel = None
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

    def _lepes_szoveg(self) -> str:
        t = f"{self._step:.1f}".replace(".", ",")
        if t.endswith(",0"):
            t = t[:-2]
        return f"{t} másodperc"

    def _on_arrow(self, direction: int, ctrl: bool, shift: bool):
        """Bal/jobb: lépés. Ctrl: a lépésköz 0,1–10 mp. Shift: kijelölés."""
        if ctrl:
            self._adjust_step(direction)
            return
        if not self.clip.has_audio():
            self._announce("Nincs betöltött hang.")
            return
        if shift:
            if self._anchor is None:
                self._anchor = self._playhead()
            self._move_by(direction * self._step)
            new = self._playhead()
            a, b = sorted((self._anchor, new))
            self._sel = (a, b) if b - a > 1e-4 else None
            self._refresh_pos()
            self._announce(
                f"Kijelölve: {_human(a)}-tól {_human(b)}-ig, "
                f"hossz {_human(b - a)}.")
            return
        self._anchor = None
        self._sel = None
        self._move_by(direction * self._step)
        self._refresh_pos()
        self._announce(
            f"Pozíció: {_human(self._playhead())}. "
            f"Lépés: {self._lepes_szoveg()}.")

    def _move_by(self, delta: float):
        if self.player.is_active() and not self.player.is_paused():
            self.player.relative_seek(delta)
            self._pos = self.player.position()
            return
        if self.player.is_active():
            self._pos = self.player.position()
            self.player.stop()
            self.timer.Stop()
        self._pos = max(0.0, min(self._pos + delta, self.clip.duration()))

    def _adjust_step(self, direction: int):
        nxt = round(min(10.0, max(0.1, self._step + direction * 0.1)), 1)
        if abs(nxt - self._step) < 1e-6:
            szel = "legkisebb" if direction < 0 else "legnagyobb"
            self._announce(f"A lépés {self._lepes_szoveg()}, ez a {szel}.")
            return
        self._step = nxt
        self._refresh_pos()
        self._announce(f"Lépés: {self._lepes_szoveg()}.")

    def _clear_selection(self):
        self._anchor = None
        self._sel = None
        self._refresh_pos()
        self._announce("Kijelölés eldobva.")

    def _on_tick(self, e):
        if self.player.is_active():
            self._pos = self.player.position()
            self._refresh_pos()
        else:
            self.timer.Stop()

    def _refresh_pos(self):
        extra = ""
        if self._sel and self._sel[1] - self._sel[0] > 1e-4:
            a, b = self._sel
            extra = f"  Kijelölés: {_human(a)}–{_human(b)}"
        self.pos_lbl.SetLabel(
            f"Pozíció: {_human(self._pos)} / {_human(self.clip.duration())}  "
            f"Lépés: {self._lepes_szoveg()}{extra}")

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

    def _active_section(self):
        """A Shift-kijelölés az elsődleges; különben a markerlistáé."""
        if self._sel and self._sel[1] - self._sel[0] > 1e-4:
            a, b = self._sel
            return (min(a, b), max(a, b))
        return self._sel_section()

    def _need_section(self):
        sec = self._active_section()
        if not sec:
            self._announce(
                "Jelölj ki Shift+jobb nyíllal, vagy tegyél le egy markert "
                "és válaszd ki a listában.")
        return sec

    def _after_edit(self, msg):
        self._saved = False   # mostantól van mentetlen szerkesztés
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

    def _cut_section(self):
        sec = self._need_section()
        if not sec:
            return
        self.clip.copy_range(*sec)
        self.clip.delete_range(*sec)
        self._anchor = None
        self._sel = None
        self._after_edit(f"Kivágva ({_human(sec[1]-sec[0])}).")

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

    # ---- effekt-rack: a választás párbeszéd, nem a fő Tab-sorrend --------

    def _pick_effect(self):
        names = [n for _k, n, _l, _d, _f in supereffects.EFFECTS]
        dlg = wx.SingleChoiceDialog(self, "Melyik effektet alkalmazzam?",
                                    "Effekt", names)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return None
        idx = dlg.GetSelection()
        dlg.Destroy()
        key, name, lbl, dflt, _f = supereffects.EFFECTS[idx]
        param = 0.0
        rng = supereffects.param_range(key)
        if lbl and rng:
            lo, hi, _scale = rng
            alap = f"{dflt:g}".replace(".", ",")
            ask = wx.TextEntryDialog(
                self, f"{name}: {lbl} ({lo:g} és {hi:g} között).",
                "Effekt paramétere", alap)
            if ask.ShowModal() != wx.ID_OK:
                ask.Destroy()
                return None
            try:
                param = float(ask.GetValue().replace(",", "."))
            except ValueError:
                param = dflt
            param = min(hi, max(lo, param))
            ask.Destroy()
        return key, name, param

    def _apply_effect(self, whole: bool):
        if self._busy or not self.clip.has_audio():
            return
        if whole:
            a, b = 0.0, self.clip.duration()
        else:
            sec = self._need_section()
            if not sec:
                return
            a, b = sec
        picked = self._pick_effect()
        if not picked:
            return
        key, name, param = picked
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
        """A Shift- vagy marker-kijelölés, ha van; különben az egész klip."""
        return self._active_section() or (0.0, self.clip.duration())

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
        dlg = wx.TextEntryDialog(
            self, "Vokóder erőssége százalékban, 0 és 100 között:",
            "Vokóder", "100")
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        try:
            amt = float(dlg.GetValue().replace(",", ".")) / 100.0
        except ValueError:
            amt = 1.0
        dlg.Destroy()
        amt = min(1.0, max(0.0, amt))
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
        van = self.clip.has_audio()
        self.mi_undo.Enable(self.clip.can_undo())
        self.mi_redo.Enable(self.clip.can_redo())
        self.mi_save.Enable(van)

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
        # MENTÉSI mintavétel + MP3-bitráta a választókból (a GUI-szálon olvasva)
        out_freq = {0: 0, 1: 44100, 2: 48000}.get(self.sr_ch.GetSelection(), 0)
        mp3_bitrate = ["128k", "192k", "256k", "320k"][
            max(0, self.br_ch.GetSelection())]
        eff = out_freq or self.clip.freq
        self._busy = True
        self.mi_save.Enable(False)
        self._announce(f"Mentés… ({eff} Hz"
                       + (f", MP3 {mp3_bitrate}" if mp3 else "") + ")")

        def work():
            try:
                out = self.clip.save(path, normalize=False, out_freq=out_freq,
                                     mp3_bitrate=mp3_bitrate)
            except Exception as ex:
                wx.CallAfter(self._save_done, None, str(ex))
                return
            wx.CallAfter(self._save_done, out, None)

        threading.Thread(target=work, daemon=True).start()

    def _save_done(self, out, err):
        self._busy = False
        self.mi_save.Enable(self.clip.has_audio())
        if err:
            self._announce(f"A mentés nem sikerült: {err}")
        else:
            self._saved = True
            self._announce(f"Mentve: {os.path.basename(out)}")

    def _has_unsaved_edit(self) -> bool:
        """Történt-e olyan szerkesztés, amit még nem mentettünk ki?
        A visszavonási előzmény léte jelzi, hogy dolgoztunk a hangon."""
        if self._saved:
            return False
        try:
            return bool(self.clip.pcm) and self.clip.can_undo()
        except Exception:
            return False

    def _on_close(self, e):
        # MENTETLEN SZERKESZTÉS VÉDELME: eddig egy véletlen Alt+F4 az összes
        # vágást és effektet eldobta kérdés nélkül. [Herman Tibi EDIT-P0-06]
        if not self._closing and self._has_unsaved_edit():
            ans = wx.MessageBox(
                "A szerkesztéseidet még nem mentetted el. Ha most bezárod, "
                "ELVESZNEK.\n\nBiztosan bezárod mentés nélkül?",
                "Fülre-szerkesztő – mentetlen munka",
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self)
            if ans != wx.YES:
                if e.CanVeto():
                    e.Veto()
                return
        self._closing = True
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
