"""Super M – a SuperDL beépített rádió-/műsorszóró stúdiója.

1. MÉRFÖLDKŐ, A ITERÁCIÓ: stabil fájl-lejátszás (MP3/WAV/…) + akadálymentes
billentyűzet (fel/le: navigáció a listában, Szóköz: lejátszás/szünet, Enter:
a kijelölt indítása). A keverő, crossfade, dual-device, mikrofon-ducking,
jingle-pad és a Shoutcast/Icecast-enkóder a következő iterációkban épül erre.
"""

import datetime
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import wx

from superdl import selfvoice          # megosztott self-voice a Core-ból
from . import superm_audio as SM
from . import superm_playlist as PL
from . import superm_stream as ST

_NOWIN = 0x08000000 if os.name == "nt" else 0


def _render_tts_wav(text: str, voice: str = "hu") -> str:
    """A „Lusta Műsorvezető" bemondását WAV-ba rendereli a beágyazott
    eSpeak-NG-vel (offline, magyar, AI-kulcs nélkül). A WAV-ot a buszon
    játsszuk le, így a hallgatók is hallják. Visszaad: a WAV útja vagy None."""
    exe, data = selfvoice._espeak_paths()
    if not exe:
        return None
    out = os.path.join(tempfile.gettempdir(),
                       f"superm_dj_{int(time.time() * 1000)}.wav")
    cmd = [exe, "-v", voice, "-w", out]
    if data:
        cmd += ["--path", str(Path(data).parent)]
    cmd.append(text)
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, creationflags=_NOWIN,
                       timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return out if os.path.exists(out) else None

XFADE_DEFAULT = 10          # másodperc – a mester-prompt szerinti 10 mp-es automix


def _hms(sec: float) -> str:
    sec = max(0, int(sec))
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class SuperMFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Super M műsorszóró stúdió",
                         size=(820, 600))
        self.main = main
        self.pl = PL.Playlist()
        self.air = SM.Mixer()         # a MŰSOR-BUSZ: ide keverünk mindent, EZT
        #                               hallja a kimenet és (M2) az enkóder
        self.player = SM.Player(mixer=self.air)   # az AKTÍV deck (a buszon)
        self.deck_b = SM.Player(mixer=self.air)   # a 2. deck a crossfade-hez
        self._target_vol = 1.0        # a felhasználó által kért mester-hangerő
        self._xfade_on = True         # áttűnés be/ki (NEM jelölőnégyzet – ld. lent)
        self._crossfading = False
        self._xfade_end = 0.0         # az áttűnés vége (monotonic idő)
        self._xfade_next = -1         # a bejövő szám indexe áttűnés alatt
        # PFL / súgó-csatorna (1/C): a kijelölt szám előhallgatása KÜLÖN
        # kimeneti eszközön (pl. fejhallgató), az adás zavarása nélkül
        self.cue = None               # SM.Player a súgó-csatornához (lazy)
        self._cue_devs = []           # a választó tételeihez tartozó indexek
        self._cue_device = None       # a kiválasztott súgó-eszköz indexe
        # adás / streaming (2/A): a műsor-busz kisugárzása Icecast/Shoutcastra
        self.caster = ST.Caster()
        # mikrofon (3/A): KÉZI reteszelő be/ki (NINCS zajkapu); a zene
        # determinisztikusan halkul beszéd közben (duck)
        self.mic = None               # SM.Mic (lazy, az első bekapcsoláskor)
        self._mic_on = False
        self._mic_devs = []
        self._mic_device = -1
        self._duck = 1.0              # 1.0 = nincs halkítás; beszédkor < 1.0
        # Jingle-Pad (4/A): 9 hely, Numpad 1-9 indítja, a buszra keverve
        self.jingle_files = [None] * 9
        self.jingle_players = [None] * 9
        # Lusta Műsorvezető (4/B): TTS-bemondás a buszra, idő/most szól
        self.dj_player = None
        self._dj_speaking = False
        self._dj_wav = None
        self._auto_dj_next = 0.0

        self._build()
        self._build_menu()
        self.CreateStatusBar()
        self._announce(f"Super M kész (BASS {SM.version()}). Adj hozzá zenét; "
                       "fel/le: navigáció, Enter: indítás, Szóköz: "
                       "lejátszás/szünet. A Vezérlés menüben minden funkció "
                       "gyorsbillentyűvel is elérhető (pl. Ctrl+T: áttűnés).")
        self.Bind(wx.EVT_CLOSE, self._on_close)
        # csak a Numpad 1-9 jingle-indításhoz (módosító nélkül, szövegmezőn
        # kívül); minden mást továbbenged → nem zavarja a gombokat/mezőket
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self._tick(), self.timer)
        self.timer.Start(500)

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        b1 = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (("&Fájlok hozzáadása…", self._add_files),
                          ("&Mappa hozzáadása…", self._add_folder),
                          ("Kijelölt &eltávolítása", lambda e: self._remove()),
                          ("&Lista törlése", lambda e: self._clear())):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            b1.Add(b, 0, wx.RIGHT, 6)
        v.Add(b1, 0, wx.ALL, 6)

        v.Add(wx.StaticText(p, label="&Lejátszási lista (fel/le: navigáció, "
              "Enter: indítás, Szóköz: lejátszás/szünet, bal/jobb: tekerés):"),
              0, wx.LEFT, 8)
        self.list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.list.SetName("Lejátszási lista")
        self.list.InsertColumn(0, "Cím", width=560)
        self.list.InsertColumn(1, "Sorszám", width=90)
        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED,
                       lambda e: self._play_selected())
        # a gyors-billentyűk CSAK a listára vannak kötve (nem keret-szintű
        # CHAR_HOOK), így a gombokat/léptetőt a Szóköz/Enter natívan, helyesen
        # aktiválja, és a Szóköz nem ütközik sehol a lejátszással
        self.list.Bind(wx.EVT_KEY_DOWN, self._on_list_key)
        v.Add(self.list, 1, wx.EXPAND | wx.ALL, 8)

        self.now_lbl = wx.StaticText(p, label="Most nem szól semmi.")
        self.now_lbl.SetName("Lejátszás állapota")
        v.Add(self.now_lbl, 0, wx.LEFT | wx.BOTTOM, 8)

        ctl = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (
                ("Le&játszás / szünet (Szóköz)", lambda e: self._toggle()),
                ("&Leállítás", lambda e: self._stop()),
                ("&Előző", lambda e: self._prev()),
                ("&Következő", lambda e: self._next()),
                ("Hangerő &−", lambda e: self._vol(-0.05)),
                ("Hangerő &+", lambda e: self._vol(0.05))):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            ctl.Add(b, 0, wx.RIGHT, 6)
        v.Add(ctl, 0, wx.LEFT | wx.BOTTOM, 8)

        # tekerés-sor (a számon belül)
        sk = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (("◄ &Vissza 5 mp", lambda e: self._seek(-5)),
                          ("&Előre 5 mp ►", lambda e: self._seek(5)),
                          ("◄◄ Vissza &30 mp", lambda e: self._seek(-30)),
                          ("Előre 30 mp ►►", lambda e: self._seek(30)),
                          ("&Hol tartok?", lambda e: self._say_pos())):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            sk.Add(b, 0, wx.RIGHT, 6)
        v.Add(sk, 0, wx.LEFT | wx.BOTTOM, 8)

        # áttűnés: GOMB (nem jelölőnégyzet – a Szóköz ütközne a lejátszással)
        xf = wx.BoxSizer(wx.HORIZONTAL)
        self.xfade_btn = wx.Button(p, label="")
        self.xfade_btn.Bind(wx.EVT_BUTTON, lambda e: self._toggle_xfade())
        xf.Add(self.xfade_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        xf.Add(wx.StaticText(p, label="Átmenet hossza (mp):"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.xfade_spin = wx.SpinCtrl(p, min=2, max=20, initial=XFADE_DEFAULT)
        self.xfade_spin.SetName("Áttűnés hossza másodpercben")
        xf.Add(self.xfade_spin, 0)
        v.Add(xf, 0, wx.LEFT | wx.BOTTOM, 8)
        self._update_xfade_btn()

        # súgó-csatorna / PFL: a kijelölt szám előhallgatása külön eszközön
        pf = wx.BoxSizer(wx.HORIZONTAL)
        self.pfl_btn = wx.Button(p, label="")
        self.pfl_btn.Bind(wx.EVT_BUTTON, lambda e: self._toggle_pfl())
        pf.Add(self.pfl_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        pf.Add(wx.StaticText(p, label="Súgó-csatorna (előhallgatás) eszköze:"),
               0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.cue_choice = wx.Choice(p)
        self.cue_choice.SetName("Súgó-csatorna kimeneti eszköze")
        self.cue_choice.Bind(wx.EVT_CHOICE, lambda e: self._on_cue_device())
        pf.Add(self.cue_choice, 0)
        v.Add(pf, 0, wx.LEFT | wx.BOTTOM, 8)
        self._fill_cue_devices()
        self._update_pfl_btn(False)

        # --- ADÁS / élő műsorszórás (2/A) ---
        v.Add(wx.StaticText(p, label="Élő adás (internetes műsorszórás "
              "Icecast/Shoutcast szerverre):"), 0, wx.LEFT | wx.TOP, 8)
        grid = wx.FlexGridSizer(cols=4, vgap=4, hgap=6)
        grid.AddGrowableCol(1)
        grid.AddGrowableCol(3)

        def field(label, ctrl, name):
            ctrl.SetName(name)
            grid.Add(wx.StaticText(p, label=label), 0,
                     wx.ALIGN_CENTER_VERTICAL)
            grid.Add(ctrl, 0, wx.EXPAND)
            return ctrl

        self.srv_type = wx.Choice(p, choices=["Icecast", "Shoutcast"])
        self.srv_type.SetSelection(0)
        field("Szerver típusa:", self.srv_type, "Szerver típusa")
        self.srv_host = wx.TextCtrl(p)
        field("Kiszolgáló (host):", self.srv_host, "Kiszolgáló címe")
        self.srv_port = wx.SpinCtrl(p, min=1, max=65535, initial=8000)
        field("Port:", self.srv_port, "Port")
        self.srv_mount = wx.TextCtrl(p, value="/stream")
        field("Mountpoint / SID:", self.srv_mount, "Mountpoint vagy SID")
        self.srv_pass = wx.TextCtrl(p, style=wx.TE_PASSWORD)
        field("Jelszó:", self.srv_pass, "Adás jelszó")
        self.srv_name = wx.TextCtrl(p, value="Super M rádió")
        field("Adás neve:", self.srv_name, "Az adás neve")
        self.srv_rate = wx.Choice(p, choices=["64", "96", "128", "192",
                                              "256", "320"])
        self.srv_rate.SetSelection(2)        # 128 kbps
        field("Bitráta (kbps):", self.srv_rate, "Bitráta")
        self.srv_genre = wx.TextCtrl(p, value="")
        field("Műfaj:", self.srv_genre, "Műfaj")
        v.Add(grid, 0, wx.EXPAND | wx.ALL, 8)

        self.cast_btn = wx.Button(p, label="")
        self.cast_btn.Bind(wx.EVT_BUTTON, lambda e: self._toggle_broadcast())
        v.Add(self.cast_btn, 0, wx.LEFT | wx.BOTTOM, 8)
        self._update_cast_btn()

        # --- MIKROFON (3/A): kézi reteszelő be/ki, NINCS zajkapu ---
        mc = wx.BoxSizer(wx.HORIZONTAL)
        self.mic_btn = wx.Button(p, label="")
        self.mic_btn.Bind(wx.EVT_BUTTON, lambda e: self._toggle_mic())
        mc.Add(self.mic_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        mc.Add(wx.StaticText(p, label="Mikrofon eszköze:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.mic_choice = wx.Choice(p)
        self.mic_choice.SetName("Mikrofon bemeneti eszköze")
        self.mic_choice.Bind(wx.EVT_CHOICE, lambda e: self._on_mic_device())
        mc.Add(self.mic_choice, 0, wx.RIGHT, 12)
        mc.Add(wx.StaticText(p, label="Zene halkítása beszéd közben (%):"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.duck_spin = wx.SpinCtrl(p, min=0, max=100, initial=70)
        self.duck_spin.SetName("Zene halkítása beszéd közben százalék")
        mc.Add(self.duck_spin, 0)
        v.Add(mc, 0, wx.LEFT | wx.BOTTOM, 8)
        self._fill_mic_devices()
        self._update_mic_btn()

        # --- JINGLE-PAD (4/A): Numpad 1-9 ---
        v.Add(wx.StaticText(p, label="Jingle-pad – gyors hangbejátszások "
              "(Numpad 1–9 indítja, a zene fölé keverve):"), 0, wx.LEFT, 8)
        self.jingle_list = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
                                       size=(-1, 150))
        self.jingle_list.SetName("Jingle-helyek")
        self.jingle_list.InsertColumn(0, "Hely", width=110)
        self.jingle_list.InsertColumn(1, "Hozzárendelt hangfájl", width=440)
        self.jingle_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED,
                              lambda e: self._jingle_test())
        v.Add(self.jingle_list, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        jb = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (("Hang&fájl hozzárendelése…", self._assign_jingle),
                          ("Hozzárendelés &törlése", self._clear_jingle),
                          ("&Kipróbálás (lejátszás)", self._jingle_test)):
            bt = wx.Button(p, label=label)
            bt.Bind(wx.EVT_BUTTON, lambda e, f=fn: f())
            jb.Add(bt, 0, wx.RIGHT, 6)
        v.Add(jb, 0, wx.LEFT | wx.BOTTOM, 8)
        self._refresh_jingles()

        # --- LUSTA MŰSORVEZETŐ (4/B): TTS idő + most szól ---
        dj = wx.BoxSizer(wx.HORIZONTAL)
        djbtn = wx.Button(p, label="&Műsorvezető: bemondás most (idő + most szól)")
        djbtn.Bind(wx.EVT_BUTTON, lambda e: self._dj_announce("both"))
        dj.Add(djbtn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        self.dj_auto = wx.CheckBox(p, label="Időjelzés automatikusan, percenként:")
        self.dj_auto.SetName("Automatikus időjelzés")
        self.dj_auto.Bind(wx.EVT_CHECKBOX, lambda e: self._on_dj_auto())
        dj.Add(self.dj_auto, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.dj_interval = wx.SpinCtrl(p, min=1, max=120, initial=15)
        self.dj_interval.SetName("Időjelzés perce")
        dj.Add(self.dj_interval, 0, wx.ALIGN_CENTER_VERTICAL)
        v.Add(dj, 0, wx.LEFT | wx.BOTTOM, 8)

        self._load_cfg()
        p.SetSizer(v)

    def _open_fx(self):
        """A valós idejű effekt-rack megnyitása a most szóló deckre (MK-A)."""
        if getattr(self, "_fx_dlg", None):
            try:
                self._fx_dlg.Raise()
                return
            except Exception:
                self._fx_dlg = None
        from .supermfxwin import EffectRackDialog
        self._fx_dlg = EffectRackDialog(
            self, lambda: self.player.handle, lambda t: self._announce(t))
        self._fx_dlg.Bind(
            wx.EVT_CLOSE,
            lambda e: (setattr(self, "_fx_dlg", None), e.Skip()))
        self._fx_dlg.Show()

    def _build_menu(self):
        """Akadálymentes menüsor: minden vezérlés MEGBÍZHATÓ gyorsbillentyűvel
        (a menü-gyorsbillentyűk keret-szinten mindig működnek, függetlenül a
        fókusztól – ezért bombabiztos a képernyőolvasóval is)."""
        mb = wx.MenuBar()
        m = wx.Menu()

        def add(label, fn):
            it = m.Append(wx.ID_ANY, label)
            self.Bind(wx.EVT_MENU, lambda e: fn(), it)
            return it

        self.mi_xfade = add("Á&ttűnés a számok közt be/ki\tCtrl+T",
                            self._toggle_xfade)
        self.mi_pfl = add("E&lőhallgatás (PFL) be/ki\tCtrl+L",
                          self._toggle_pfl)
        self.mi_cast = add("Élő adás &indítása / leállítása\tCtrl+G",
                           self._toggle_broadcast)
        self.mi_mic = add("&Mikrofon be/ki (Ctrl+Numpad 1)", self._toggle_mic)
        add("Mű&sorvezető bemondás (idő + most szól)\tCtrl+J",
            lambda: self._dj_announce("both"))
        add("Effekt-&rack…\tCtrl+E", self._open_fx)
        m.AppendSeparator()
        add("&Lejátszás / szünet\tCtrl+P", self._toggle)
        add("Le&állítás\tCtrl+S", self._stop)
        add("&Előző szám\tCtrl+B", self._prev)
        add("&Következő szám\tCtrl+N", self._next)
        m.AppendSeparator()
        add("Tekerés &vissza 5 mp\tCtrl+Left", lambda: self._seek(-5))
        add("Tekerés e&lőre 5 mp\tCtrl+Right", lambda: self._seek(5))
        add("Tekerés vissza 30 mp\tCtrl+Shift+Left", lambda: self._seek(-30))
        add("Tekerés előre 30 mp\tCtrl+Shift+Right", lambda: self._seek(30))
        add("&Hol tartok?\tCtrl+W", self._say_pos)

        mb.Append(m, "&Vezérlés")
        self.SetMenuBar(mb)

        # globális gyorsbillentyűk, amik a fókusztól függetlenül működnek
        # (a Ctrl+Numpad 1 a mikrofon-reteszhez – a kért gyors „adásgomb")
        self.SetAcceleratorTable(wx.AcceleratorTable([
            wx.AcceleratorEntry(wx.ACCEL_CTRL, wx.WXK_NUMPAD1,
                                self.mi_mic.GetId()),
        ]))

    # ---- lista kezelés ------------------------------------------------

    def _refresh(self, select=-1):
        self.list.DeleteAllItems()
        for i, t in enumerate(self.pl.tracks):
            row = self.list.InsertItem(self.list.GetItemCount(), t.title)
            self.list.SetItem(row, 1, str(i + 1))
        if 0 <= select < self.list.GetItemCount():
            self.list.Select(select)
            self.list.Focus(select)
            self.list.SetFocus()

    def _add_files(self, e):
        dlg = wx.FileDialog(
            self, "Zenefájlok hozzáadása",
            wildcard="Hang (*.mp3;*.wav;*.ogg;*.flac;*.m4a;*.aac)|"
                     "*.mp3;*.wav;*.ogg;*.flac;*.m4a;*.aac|Minden fájl|*.*",
            style=wx.FD_OPEN | wx.FD_MULTIPLE | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            n = self.pl.add_files(dlg.GetPaths())
            self._refresh(select=len(self.pl) - n if n else -1)
            self._announce(f"{n} szám hozzáadva. Összesen {len(self.pl)}.")
        dlg.Destroy()

    def _add_folder(self, e):
        dlg = wx.DirDialog(self, "Mappa hozzáadása (az összes zenefájl)")
        if dlg.ShowModal() == wx.ID_OK:
            n = self.pl.add_folder(dlg.GetPath())
            self._refresh()
            self._announce(f"{n} szám hozzáadva a mappából. Összesen "
                           f"{len(self.pl)}.")
        dlg.Destroy()

    def _remove(self):
        i = self.list.GetFirstSelected()
        if i >= 0:
            self.pl.remove(i)
            self._refresh(select=min(i, len(self.pl) - 1))
            self._announce("Eltávolítva a listából.")

    def _clear(self):
        self._cancel_crossfade()
        self.player.stop()
        self.pl.clear()
        self._refresh()
        self._announce("A lista kiürítve.")

    # ---- lejátszás ----------------------------------------------------

    def _play_index(self, i):
        self._cancel_crossfade()
        t = self.pl.select(i)
        if not t:
            return
        if not self.player.load(t.path):
            self._announce(f"Nem sikerült betölteni: {t.title}")
            return
        self.player.set_volume(self._music_vol())
        self.player.play()
        self._refresh(select=i)
        self._cast_title()
        self._announce(f"Most szól: {t.title}  "
                       f"({_hms(self.player.length())}, hangerő "
                       f"{round(self._target_vol * 100)}%).")

    def _play_selected(self):
        i = self.list.GetFirstSelected()
        if i >= 0:
            self._play_index(i)

    def _toggle(self):
        if self._crossfading:
            self._cancel_crossfade()
        if not self.player.is_active():
            # nincs betöltve / véget ért → a kijelöltet (vagy az elsőt) indítjuk
            i = self.list.GetFirstSelected()
            self._play_index(i if i >= 0 else 0)
            return
        paused = self.player.toggle_pause()
        cur = self.pl.current()
        self._announce("Szünet." if paused else
                       f"Folytatás: {cur.title if cur else ''}")

    def _stop(self):
        self._cancel_crossfade()
        if self.player.is_active():
            self.player.stop()
            self._announce("Leállítva.")

    def _next(self):
        if len(self.pl):
            self.pl.next()
            self._play_index(self.pl.index)

    def _prev(self):
        if len(self.pl):
            self.pl.prev()
            self._play_index(self.pl.index)

    def _music_vol(self) -> float:
        """A zene tényleges hangereje = a felhasználó mester-hangereje × a
        beszéd-halkítás (duck). Beszéd nélkül _duck=1.0."""
        return self._target_vol * self._duck

    def _vol(self, delta):
        self._target_vol = max(0.0, min(1.0, self._target_vol + delta))
        if not self._crossfading:
            self.player.set_volume(self._music_vol())
        self._announce(f"Hangerő: {round(self._target_vol * 100)} százalék.")

    # ---- tekerés a számon belül ---------------------------------------

    def _seek(self, delta: float):
        if not self.player.is_active():
            self._announce("Nincs mit tekerni – előbb indíts el egy számot.")
            return
        new = max(0.0, min(self.player.length() - 0.5,
                           self.player.position() + delta))
        self.player.seek(new)
        self._announce(f"{_hms(new)} / {_hms(self.player.length())}.")

    def _say_pos(self):
        if self.player.is_active():
            self._announce(f"Itt tartok: {_hms(self.player.position())} / "
                           f"{_hms(self.player.length())}.")
        else:
            self._announce("Most nem szól semmi.")

    # ---- áttűnés be/ki (gomb) -----------------------------------------

    def _toggle_xfade(self):
        self._xfade_on = not self._xfade_on
        if not self._xfade_on:
            self._cancel_crossfade()
        self._update_xfade_btn()
        self._announce("Áttűnés a számok közt: "
                       + ("bekapcsolva." if self._xfade_on else "kikapcsolva."))

    def _update_xfade_btn(self):
        self.xfade_btn.SetLabel("Á&ttűnés a számok közt: "
                                + ("BE" if self._xfade_on else "KI"))

    # ---- PFL / súgó-csatorna (előhallgatás külön eszközön) ------------

    def _fill_cue_devices(self):
        """A súgó-csatorna eszközválasztójának feltöltése. Az 1. tétel mindig a
        rendszer alap kimenete; utána a többi kimeneti eszköz (pl. fejhallgató)."""
        self._cue_devs = []
        self.cue_choice.Clear()
        try:
            devs = SM.devices()
            dflt = SM.default_device()
        except Exception:
            devs, dflt = [], 1
        self.cue_choice.Append("(alapértelmezett kimenet – a fő adással azonos)")
        self._cue_devs.append(dflt)
        for idx, name in devs:
            self.cue_choice.Append(name)
            self._cue_devs.append(idx)
        self.cue_choice.SetSelection(0)
        self._cue_device = dflt

    def _on_cue_device(self):
        self._stop_pfl()
        if self.cue:
            self.cue.unload()
            self.cue = None
        sel = self.cue_choice.GetSelection()
        self._cue_device = self._cue_devs[sel] if 0 <= sel < len(self._cue_devs) \
            else SM.default_device()
        self._announce(f"Súgó-csatorna: {self.cue_choice.GetStringSelection()}")

    def _toggle_pfl(self):
        # ha épp szól az előhallgatás → leállítjuk
        if self.cue and self.cue.is_active():
            self._stop_pfl()
            self._announce("Előhallgatás leállítva.")
            return
        i = self.list.GetFirstSelected()
        if i < 0:
            self._announce("Előhallgatáshoz előbb jelölj ki egy számot a "
                           "listában (fel/le nyíl).")
            return
        t = self.pl.tracks[i]
        dev = self._cue_device if self._cue_device is not None \
            else SM.default_device()
        if self.cue is None or self.cue.device != dev:
            if self.cue:
                self.cue.unload()
            try:
                self.cue = SM.Player(device=dev)
            except Exception as ex:
                self._announce(f"A súgó-csatorna nem indítható: {ex}")
                return
        if not self.cue.load(t.path):
            self._announce(f"Nem sikerült előhallgatni: {t.title}")
            return
        self.cue.play()
        self._update_pfl_btn(True)
        dev_name = self.cue_choice.GetStringSelection()
        self._announce(f"Előhallgatás a súgó-csatornán ({dev_name}): {t.title}. "
                       "A fő adást nem zavarja.")

    def _stop_pfl(self):
        if self.cue and self.cue.is_active():
            self.cue.stop()
        self._update_pfl_btn(False)

    def _update_pfl_btn(self, on: bool):
        self.pfl_btn.SetLabel("E&lőhallgatás (PFL): " + ("BE" if on else "KI"))

    # ---- adás / élő műsorszórás (2/A) ---------------------------------

    def _cfg_path(self):
        import os
        d = os.path.join(os.path.expanduser("~"), ".superdl")
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
        return os.path.join(d, "superm.json")

    def _load_cfg(self):
        import json
        try:
            with open(self._cfg_path(), encoding="utf-8") as f:
                c = json.load(f)
        except Exception:
            return
        self.srv_type.SetSelection(1 if c.get("shoutcast") else 0)
        self.srv_host.SetValue(c.get("host", ""))
        self.srv_port.SetValue(int(c.get("port", 8000)))
        self.srv_mount.SetValue(c.get("mount", "/stream"))
        self.srv_name.SetValue(c.get("name", "Super M rádió"))
        self.srv_genre.SetValue(c.get("genre", ""))
        r = str(c.get("bitrate", 128))
        if r in ("64", "96", "128", "192", "256", "320"):
            self.srv_rate.SetStringSelection(r)
        self.duck_spin.SetValue(int(c.get("duck", 70)))
        md = c.get("mic_device", -1)
        for k, dev in enumerate(self._mic_devs):
            if dev == md:
                self.mic_choice.SetSelection(k)
                self._mic_device = dev
                break
        js = c.get("jingles") or []
        for i in range(min(9, len(js))):
            self.jingle_files[i] = js[i] if js[i] else None
        self._refresh_jingles()
        self.dj_interval.SetValue(int(c.get("dj_interval", 15)))
        self.dj_auto.SetValue(bool(c.get("dj_auto", False)))
        if self.dj_auto.IsChecked():
            self._auto_dj_next = time.monotonic() + \
                self.dj_interval.GetValue() * 60
        # a jelszót NEM mentjük el fájlba (biztonság) – minden indításnál kérjük

    def _save_cfg(self):
        import json
        c = {"shoutcast": self.srv_type.GetSelection() == 1,
             "host": self.srv_host.GetValue().strip(),
             "port": self.srv_port.GetValue(),
             "mount": self.srv_mount.GetValue().strip(),
             "name": self.srv_name.GetValue().strip(),
             "genre": self.srv_genre.GetValue().strip(),
             "bitrate": int(self.srv_rate.GetStringSelection() or 128),
             "duck": self.duck_spin.GetValue(),
             "mic_device": self._mic_device,
             "jingles": self.jingle_files,
             "dj_interval": self.dj_interval.GetValue(),
             "dj_auto": self.dj_auto.IsChecked()}
        try:
            with open(self._cfg_path(), "w", encoding="utf-8") as f:
                json.dump(c, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _toggle_broadcast(self):
        if self.caster.is_live:
            self.caster.stop()
            self._update_cast_btn()
            self._announce("Az élő adás leállítva.")
            return
        host = self.srv_host.GetValue().strip()
        if not host:
            self._announce("Az adás indításához add meg a kiszolgáló címét "
                           "(host).")
            self.srv_host.SetFocus()
            return
        self._save_cfg()
        self._announce("Kapcsolódás a szerverhez…")
        ok = self.caster.start(
            self.air.handle,
            host=host,
            port=self.srv_port.GetValue(),
            mount=self.srv_mount.GetValue().strip(),
            password=self.srv_pass.GetValue(),
            bitrate=int(self.srv_rate.GetStringSelection() or 128),
            name=self.srv_name.GetValue().strip(),
            genre=self.srv_genre.GetValue().strip(),
            shoutcast=self.srv_type.GetSelection() == 1)
        if ok:
            self._update_cast_btn()
            cur = self.pl.current()
            if cur:
                self.caster.set_title(cur.title)
            self._announce("ÉLŐ ADÁS megy! A műsor most a szerverre megy. "
                           "Leállítás: Ctrl+G.")
        else:
            self._announce("Az adás nem indult: " + self.caster.last_error)

    def _update_cast_btn(self):
        live = self.caster.is_live
        self.cast_btn.SetLabel("Élő adás &indítása" if not live
                               else "Élő adás &leállítása (most ÉLŐ)")

    def _cast_title(self):
        """A „most szól" metaadat frissítése a hallgatóknak (ha él az adás)."""
        if self.caster.is_live:
            t = self.pl.current()
            if t:
                self.caster.set_title(t.title)

    # ---- mikrofon (3/A): kézi reteszelő be/ki + determinisztikus duck ----

    def _fill_mic_devices(self):
        self._mic_devs = []
        self.mic_choice.Clear()
        try:
            devs = SM.record_devices()
        except Exception:
            devs = []
        self.mic_choice.Append("(alapértelmezett mikrofon)")
        self._mic_devs.append(-1)
        for idx, name in devs:
            self.mic_choice.Append(name)
            self._mic_devs.append(idx)
        self.mic_choice.SetSelection(0)
        self._mic_device = -1

    def _on_mic_device(self):
        if self._mic_on:
            self._toggle_mic()           # előbb ki
        if self.mic:
            self.mic.stop()
            self.mic = None
        sel = self.mic_choice.GetSelection()
        self._mic_device = self._mic_devs[sel] \
            if 0 <= sel < len(self._mic_devs) else -1
        self._announce(f"Mikrofon eszköz: {self.mic_choice.GetStringSelection()}")

    def _recompute_duck(self):
        """A zene determinisztikus halkítása (NINCS érzékelő/zajkapu): ha a
        mikrofon ÉLŐ VAGY a műsorvezető épp beszél → halkít a beállított
        mértékkel; különben teljes hangerő. A tényleges hangerőt 0,25 mp alatt
        csúsztatja."""
        if self._mic_on or self._dj_speaking:
            self._duck = 1.0 - self.duck_spin.GetValue() / 100.0
        else:
            self._duck = 1.0
        if self._crossfading:
            self.deck_b.slide_volume(self._music_vol(), 250)
        else:
            self.player.slide_volume(self._music_vol(), 250)

    def _toggle_mic(self):
        if self._mic_on:                 # --- KIKAPCSOLÁS ---
            if self.mic:
                self.mic.slide_volume(0.0, 120)
            self._mic_on = False
            self._recompute_duck()       # zene vissza (ha más nem halkít)
            self._update_mic_btn()
            self._announce("Mikrofon KI. A zene vissza a teljes hangerőre.")
            return
        # --- BEKAPCSOLÁS (lazy megnyitás) ---
        if self.mic is None:
            try:
                self.mic = SM.Mic(self.air, device=self._mic_device)
                self.mic.start()
            except SM.BassError as ex:
                self.mic = None
                self._announce("A mikrofon nem indítható: " + str(ex))
                return
        self.mic.slide_volume(1.0, 120)
        self._mic_on = True
        self._recompute_duck()
        self._update_mic_btn()
        self._announce("Mikrofon ÉLŐ – beszélhetsz, a zene halkítva. "
                       "Kikapcsolás: ugyanez a gomb vagy Ctrl+Numpad 1.")

    # ---- Jingle-Pad (4/A) ---------------------------------------------

    def _refresh_jingles(self):
        self.jingle_list.DeleteAllItems()
        for i in range(9):
            row = self.jingle_list.InsertItem(i, f"Numpad {i + 1}")
            f = self.jingle_files[i]
            self.jingle_list.SetItem(row, 1,
                                     os.path.basename(f) if f else "(üres)")
        self.jingle_list.Select(0)

    def _assign_jingle(self):
        i = self.jingle_list.GetFirstSelected()
        if i < 0:
            self._announce("Előbb jelölj ki egy jingle-helyet a listában.")
            return
        dlg = wx.FileDialog(
            self, f"Hangfájl a(z) {i + 1}-es jingle-helyhez",
            wildcard="Hang (*.mp3;*.wav;*.ogg;*.flac;*.m4a;*.aac)|"
                     "*.mp3;*.wav;*.ogg;*.flac;*.m4a;*.aac|Minden fájl|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.jingle_files[i] = dlg.GetPath()
            if self.jingle_players[i]:
                self.jingle_players[i].unload()
                self.jingle_players[i] = None
            self._refresh_jingles()
            self.jingle_list.Select(i)
            self._save_cfg()
            self._announce(f"Numpad {i + 1}: {os.path.basename(dlg.GetPath())} "
                           "hozzárendelve.")
        dlg.Destroy()

    def _clear_jingle(self):
        i = self.jingle_list.GetFirstSelected()
        if i < 0:
            return
        self.jingle_files[i] = None
        if self.jingle_players[i]:
            self.jingle_players[i].unload()
            self.jingle_players[i] = None
        self._refresh_jingles()
        self.jingle_list.Select(i)
        self._save_cfg()
        self._announce(f"A(z) {i + 1}-es jingle-hely törölve.")

    def _jingle_test(self):
        i = self.jingle_list.GetFirstSelected()
        if i >= 0:
            self._play_jingle(i)

    def _play_jingle(self, i: int):
        if not (0 <= i < 9):
            return
        path = self.jingle_files[i]
        if not path:
            self._announce(f"A(z) {i + 1}-es jingle-hely üres – rendelj hozzá "
                           "hangfájlt.")
            return
        pl = self.jingle_players[i]
        if pl is None:
            pl = SM.Player(mixer=self.air)
            if not pl.load(path):
                self._announce(f"A jingle nem tölthető be: "
                               f"{os.path.basename(path)}")
                return
            self.jingle_players[i] = pl
        pl.set_volume(1.0)
        pl.play(restart=True)            # mindig az elejéről
        self._announce(f"Jingle {i + 1}: {os.path.basename(path)}")

    # ---- Lusta Műsorvezető (4/B): TTS idő + most szól -----------------

    def _dj_announce(self, kind="both"):
        parts = []
        if kind in ("track", "both"):
            t = self.pl.current()
            if t:
                parts.append(f"Most szól: {t.title}")
        if kind in ("time", "both"):
            now = datetime.datetime.now()
            parts.append(f"Pontos idő: {now.hour} óra {now.minute} perc")
        if not parts:
            return
        text = ". ".join(parts) + "."
        threading.Thread(target=self._dj_work, args=(text,),
                         daemon=True).start()

    def _dj_work(self, text):
        path = _render_tts_wav(text)
        if path:
            wx.CallAfter(self._dj_play, path)
        else:
            wx.CallAfter(self._announce, "A műsorvezető-hang nem érhető el "
                         "(eSpeak hiányzik).")

    def _dj_play(self, path):
        if self.dj_player is None:
            self.dj_player = SM.Player(mixer=self.air)
        if self._dj_wav:
            try:
                os.remove(self._dj_wav)
            except OSError:
                pass
        self._dj_wav = path
        if self.dj_player.load(path):
            self.dj_player.set_volume(1.0)
            self.dj_player.play(restart=True)
            self._dj_speaking = True
            self._recompute_duck()       # a zene halkul a bemondás alatt
            self._announce("Műsorvezető bemondás…")

    def _on_dj_auto(self):
        if self.dj_auto.IsChecked():
            self._auto_dj_next = time.monotonic() + \
                self.dj_interval.GetValue() * 60
            self._announce(f"Automatikus időjelzés bekapcsolva, "
                           f"{self.dj_interval.GetValue()} percenként.")
        else:
            self._announce("Automatikus időjelzés kikapcsolva.")
        self._save_cfg()

    def _update_mic_btn(self):
        self.mic_btn.SetLabel("&Mikrofon: "
                              + ("ÉLŐ – beszél" if self._mic_on else "KI"))

    # ---- időzítő: pozíció + automatikus továbblépés -------------------

    def _tick(self):
        # műsorvezető-bemondás vége → a zene halkítása vissza (fókusztól és
        # áttűnéstől függetlenül kell figyelni)
        if self._dj_speaking and self.dj_player and self.dj_player.ended():
            self._dj_speaking = False
            self._recompute_duck()
        # automatikus időjelzés (determinisztikus időzítő, nem érzékelő)
        if self.dj_auto.IsChecked() and not self._dj_speaking \
                and time.monotonic() >= self._auto_dj_next:
            self._auto_dj_next = time.monotonic() + \
                self.dj_interval.GetValue() * 60
            self._dj_announce("time")
        # áttűnés alatt: figyeljük a végét, mást nem csinálunk
        if self._crossfading:
            if time.monotonic() >= self._xfade_end:
                self._finish_crossfade()
            return
        # a szám véget ért (rövid szám / kikapcsolt áttűnés) → sima továbblépés
        if self.player.ended():
            self._advance_plain()
            return
        # közeledik a vég → indítsuk az áttűnést a következő számra
        if self.player.is_playing() and self._xfade_on \
                and len(self.pl) > 1:
            xfade = self.xfade_spin.GetValue()
            length = self.player.length()
            remaining = length - self.player.position()
            if length > 2 * xfade and 0.4 < remaining <= xfade:
                self._begin_crossfade()

    def _advance_plain(self):
        if len(self.pl) > 1 or self.pl.has_next():
            self.pl.next()
            self._play_index(self.pl.index)
        else:
            self.player.stop()

    def _begin_crossfade(self):
        """A 10 mp-es automix: a bejövő számot a 2. decken elindítjuk 0
        hangerőn, a kimenőt 0-ra, a bejövőt a mester-hangerőre csúsztatjuk."""
        xfade = self.xfade_spin.GetValue()
        nxt_i = (self.pl.index + 1) % len(self.pl)
        nxt = self.pl.tracks[nxt_i]
        if not self.deck_b.load(nxt.path):
            return                       # nem sikerült → marad a sima vég-csere
        self.deck_b.set_volume(0.0)
        self.deck_b.play()
        ms = int(xfade * 1000)
        self.player.slide_volume(0.0, ms)
        self.deck_b.slide_volume(self._music_vol(), ms)
        self._crossfading = True
        self._xfade_next = nxt_i
        self._xfade_end = time.monotonic() + xfade
        self._announce(f"Áttűnés a következő számra: {nxt.title}")

    def _finish_crossfade(self):
        """Az áttűnés vége: a kimenő deck eldobása, a deckek cseréje, hogy a
        most szóló (bejövő) szám legyen újra az aktív `player`."""
        self.player.stop()
        self.player.unload()
        self.player, self.deck_b = self.deck_b, self.player
        self.player.set_volume(self._music_vol())
        self.pl.index = self._xfade_next
        self._crossfading = False
        self._xfade_next = -1
        self._refresh(select=self.pl.index)
        self._cast_title()
        t = self.pl.current()
        if t:
            self._announce(f"Most szól: {t.title} "
                           f"({_hms(self.player.length())}).")

    def _cancel_crossfade(self):
        """Folyamatban lévő áttűnés megszakítása (pl. kézi Előző/Következő)."""
        if not self._crossfading:
            return
        self.deck_b.stop()
        self.deck_b.unload()
        self._crossfading = False
        self._xfade_next = -1
        self.player.set_volume(self._music_vol())

    # ---- billentyű + zárás --------------------------------------------

    def _on_char_hook(self, e):
        # KIZÁRÓLAG a Numpad 1-9 jingle-indításhoz. Módosítóval (pl. Ctrl+Numpad 1
        # = mikrofon) vagy szövegmezőben NEM avatkozik be → a szám beírható
        # marad, és a gombokat/gyorsbillentyűket sem zavarja.
        if e.HasModifiers():
            e.Skip()
            return
        focus = wx.Window.FindFocus()
        if isinstance(focus, (wx.TextCtrl, wx.SpinCtrl)):
            e.Skip()
            return
        code = e.GetKeyCode()
        if wx.WXK_NUMPAD1 <= code <= wx.WXK_NUMPAD9:
            self._play_jingle(code - wx.WXK_NUMPAD1)
        else:
            e.Skip()

    def _on_list_key(self, e):
        # CSAK akkor fut, ha a LISTA van fókuszban – a gombokat sosem zavarja.
        # A Ctrl/Alt-os kombinációkat a menü-gyorsbillentyűknek hagyjuk.
        if e.HasModifiers():
            e.Skip()
            return
        code = e.GetKeyCode()
        if code == wx.WXK_SPACE:          # a listán: lejátszás / szünet
            self._toggle()
        elif code == wx.WXK_LEFT:         # a listán: tekerés vissza
            self._seek(-5)
        elif code == wx.WXK_RIGHT:        # a listán: tekerés előre
            self._seek(5)
        else:
            e.Skip()

    def _announce(self, text):
        self.SetStatusText(text)
        self.now_lbl.SetLabel(text)

    def _on_close(self, e):
        try:
            self.timer.Stop()
            if getattr(self, "caster", None):
                self.caster.stop()
            if self.mic:
                self.mic.stop()
            for jp in self.jingle_players:
                if jp:
                    jp.unload()
            if self.dj_player:
                self.dj_player.unload()
            if self._dj_wav:
                try:
                    os.remove(self._dj_wav)
                except OSError:
                    pass
            self.player.unload()
            self.deck_b.unload()
            if self.cue:
                self.cue.unload()
            self.air.free()
        except Exception:
            pass
        if getattr(self.main, "_superm_win", None) is self:
            self.main._superm_win = None
        self.Destroy()
