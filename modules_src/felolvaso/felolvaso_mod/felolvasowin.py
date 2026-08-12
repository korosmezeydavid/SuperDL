"""Felirat-felolvasó lejátszó: egy film (vagy hangfájl) lejátszása, közben a
MAGYAR (vagy bármely szöveges) felirat SZINKRONBAN, választható hanggal
felolvasva – vakon is „nézhető" az idegen nyelvű film.

Két hangfolyam: a film hangját a `film` Player adja, a felolvasást a `narr`
Player (a felirat épp aktuális sorát egy ideiglenes hangfájlból). A szinkront a
film lejátszási POZÍCIÓJA vezérli (a `CueScheduler`-en át), ezért szünet/ugrás
után is stimmel. Felolvasás alatt a film hangját lehalkítjuk (ducking).
"""

import os
import threading
import time

import wx

from . import narrator, subtitles, ytsource
from superdl.audioengine import Player


def _ensure_net(win, what):
    """Internet-elő-ellenőrzés VÉDETTEN, AKADÁLYMENTES kétgombos felugróval
    (Újratesztelés / OK). Ha van net, True; ha nincs, a felugró dönt. Régebbi
    Core-on (nincs netdialog) átengedjük. Bárhonnan hívható (a modálist a
    GUI-szálra marsallja)."""
    try:
        from superdl import netdialog
    except Exception:
        return True
    try:
        say = getattr(win, "_announce", None)
        return netdialog.ensure_online(
            win, what, speak=(lambda t: say(t)) if say else None)
    except Exception:
        return True


HELP = """FELIRAT-FELOLVASÓ LEJÁTSZÓ

MIRE VALÓ
Idegen nyelvű film (vagy hangfájl) lejátszása úgy, hogy a MAGYAR feliratot a
program SZINKRONBAN, választható hanggal felolvassa. Így vakon is követhető az
idegen nyelvű film: hallod az eredeti hangot, fölötte a felolvasott feliratot.

LÉPÉSRŐL LÉPÉSRE (vakon is)
1. „Média betöltése" – válaszd ki a filmet vagy hangfájlt. A program magától
   megkeresi a mellé tett feliratot (.srt/.vtt), és a fájlba ágyazott
   feliratsávokat is felkínálja. VAGY illessz be egy YOUTUBE-LINKET a
   „YouTube-link" mezőbe: a program letölti a videó feliratát (ha nincs magyar
   kézi felirat, a YouTube AUTOMATIKUS, magyarra fordított feliratát) és azt
   olvassa fel a videó hangja fölött.
2. „Felirat" lista: válaszd ki, melyik feliratot olvassa (a magyar előre van
   sorolva). Ha külön fájlból akarod, „Feliratfájl tallózása".
3. „Hang" lista: válaszd ki, milyen hanggal olvasson – helyi SAPI-hang, Edge
   neurális (online, szép), vagy a beépített eSpeak.
4. „Lejátszás" (vagy Szóköz). A felolvasás alatt a film hangja halkabb.

GYORSBILLENTYŰK
F1 – súgó.  F6 – a film hangjának átvezetése az aktuális hangeszközre (pl.
Bluetooth-ra váltás után).  F7 – a kiválasztott hang KIPRÓBÁLÁSA (film nélkül).
F8 – állapot bemondása (hibakereséshez).  Szóköz – lejátszás/szünet.  Bal/jobb
nyíl – 10 mp vissza/előre.  Ctrl+fel / Ctrl+le – hangerő.  Esc – leállítás.

HANGESZKÖZ VÁLTÁSA (pl. BLUETOOTH)
Ha lejátszás közben másik hangeszközre váltasz, a program igyekszik a film
hangját magától átvinni az új eszközre (a felolvasás hangja amúgy is követi).
Ha valamiért mégsem jönne át, nyomd meg az F6-ot: a film hangját azonnal
átvezeti az aktuális hangeszközre.

HA NEM SZÓLAL MEG A FELIRAT
- Először nyomd meg az F7-et: kipróbálja a kiválasztott hangot. Ha ezt sem
  hallod, a hanggal (vagy a hangeszközzel) van a gond – válts a „Hang” listában
  másik hangra (pl. a beépített eSpeak magyarra), és próbáld újra.
- Nyomd meg az F8-at: bemondja, halad-e az idő, be van-e töltve a felirat, épp
  mit olvas, melyik hang aktív, és mi volt az utolsó hanghiba.
- Ha a program azt mondja, „a film hangját nem tudom lejátszani", akkor is
  felolvassa a feliratot (film-hang nélkül, csend fölött) – a kép/hang formátuma
  volt szokatlan, de a felirat így is követhető.

TIPPEK
- A felirat legyen a film MELLETT, hasonló névvel (pl. Film.hu.srt) – a program
  automatikusan megtalálja.
- Az Edge neurális hang a legszebb (online, ingyenes, kulcs nélkül); ha nincs
  net, a SAPI vagy az eSpeak offline is megy."""

DUCK = 0.22          # a film hangereje a felolvasás alatt (halkítás)

# ALAP TEMPÓ: MÉRÉSSEL beállítva. Valósághű film-ritmusnál (45 karakteres sorok
# 3,1 másodpercenként) alap tempón (0) a felolvasás NEM tartja a lépést: a SAPI
# 4,7 mp/sor → 5 sor alatt 6 mp csúszás, ami egy egész filmen percekre nőne.
# +7-en a SAPI 2,1 mp/sor, az eSpeak 2,2 mp/sor → mindkettő HIBÁTLANUL bírja
# (nulla csúszás). Vakon amúgy is gyors beszédhez szokunk – de állítható.
DEFAULT_RATE = 7

# a modul verziója – a felhasználó HALLJA (indításkor és F8-ra), hogy tényleg a
# friss változat fut-e (a manifest.json-nal kézzel szinkronban tartva)
MOD_VERSION = "1.4.6"


def _rovid_hiba(err: str) -> str:
    """A hangmotor-hiba RÖVID, felolvasható változata a bemondáshoz – hogy a
    felhasználó F8 nélkül is HALLJA, MIÉRT nem szólt a választott hang (nem csak
    annyit, hogy „részletek: F8"). A teljes hiba F8-ra és a diagnosztikában marad."""
    e = " ".join((err or "").split())
    return (e[:140] + "…") if len(e) > 140 else e


class FelolvasoFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Felirat-felolvasó lejátszó",
                         size=(880, 560))
        self.main = main
        self.media = ""
        self.cues: list = []
        self.sched = None
        self._sources: list = []          # (címke, típus, adat) felirat-források
        self._voices = narrator.voice_options()
        self._narrating = False
        self._film_vol = 0.8
        self._cur_temp = None
        self._ahead = {}          # ELŐRE legyártott hang: cue-index → fájl
        self._ahead_busy = False
        self._closing = False     # zárás alatt a háttérszálak ne nyúljanak hozzánk
        # a narrációt vezérlő INTEGRÁLÓ óra (lásd _clock): a film hang-pozícióját
        # követi, de ha az beragad, fali órával lép előre, hogy a felolvasás ne
        # álljon le némán
        self._clk_pos = 0.0
        self._clk_apos = 0.0
        self._clk_wall = 0.0
        self._clk_t0 = 0.0
        self._clk_started = False
        # ha a film HANGJA nem játszható le, a feliratot csend fölött, tisztán
        # fali órával akkor is felolvassuk (jobb a semminél)
        self._subs_only = False
        self._subs_paused = False
        # proaktív riasztás: ha a lejátszás elindul, de pár mp-ig EGYETLEN felirat
        # sem szólal meg, a program magától bemondja, mi az állapot (F8 nélkül is)
        self._play_t0 = 0.0
        self._fired_any = False
        self._warned = False
        # a felirat-hangosítás (TTS) diagnosztikájához: utolsó hiba / siker
        self._last_tts_err = ""
        self._last_ok = ""
        self._narr_fail = 0        # egymás utáni sikertelen narrációk száma
        # HANGESZKÖZ-KÖVETÉS: a film egy HOSSZÚ streamet nyit, ami az indításkori
        # eszközön ragad; a narráció rövid streamjei viszont az új alapeszközre
        # kerülnek. Ha váltasz (pl. Bluetooth), a filmet ÚJRANYITJUK az új eszközön,
        # hogy a kettő együtt szóljon. (F6-tal kézzel is átvezethető.)
        self._film_dev = ""        # az eszköz, amin a film épp szól
        self._dev_poll = 0         # ritkított eszköz-figyelés számlálója

        self.film = Player()
        self.film.on_state = lambda s: wx.CallAfter(self._on_film_state, s)
        self.narr = Player()
        self.narr.set_volume(1.0)
        self.narr.on_state = lambda s: wx.CallAfter(self._on_narr_state, s)

        self._build()
        self.CreateStatusBar()
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self._tick(), self.timer)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self._setup_accelerators()          # F1/F6/F7/F8, Ctrl+fel/le, Esc – MINDEN vezérlőn
        self._announce(f"Felirat-felolvasó {MOD_VERSION}. Tölts be egy filmet "
                       "vagy hangfájlt; a magyar feliratot szinkronban "
                       "felolvasom. Súgó: F1. Állapot: F8.")

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        top = wx.BoxSizer(wx.HORIZONTAL)
        b_load = wx.Button(p, label="Média &betöltése…")
        b_load.Bind(wx.EVT_BUTTON, lambda e: self._load())
        self.media_lbl = wx.StaticText(p, label="Nincs betöltött média.")
        self.media_lbl.SetName("Betöltött média")
        top.Add(b_load, 0, wx.RIGHT, 8)
        top.Add(self.media_lbl, 1, wx.ALIGN_CENTER_VERTICAL)
        v.Add(top, 0, wx.EXPAND | wx.ALL, 8)

        # online link (YouTube stb.): a hangot streameljük, a feliratot a
        # yt-dlp tölti le (manuális vagy AUTO – akár magyarra fordítva)
        yt = wx.BoxSizer(wx.HORIZONTAL)
        yt.Add(wx.StaticText(p, label="Y&ouTube-link:"), 0,
               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.url_entry = wx.TextCtrl(p, style=wx.TE_PROCESS_ENTER)
        self.url_entry.SetName("YouTube vagy más videó-link")
        self.url_entry.Bind(wx.EVT_TEXT_ENTER, lambda e: self._load_url())
        yt.Add(self.url_entry, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        b_url = wx.Button(p, label="Link be&töltése")
        b_url.Bind(wx.EVT_BUTTON, lambda e: self._load_url())
        yt.Add(b_url, 0)
        v.Add(yt, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        g = wx.FlexGridSizer(0, 3, 8, 8)
        g.AddGrowableCol(1)
        g.Add(wx.StaticText(p, label="&Felirat:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.sub_ch = wx.Choice(p, choices=["(előbb tölts be médiát)"],
                                name="Felirat forrása")
        self.sub_ch.SetSelection(0)
        g.Add(self.sub_ch, 0, wx.EXPAND)
        b_browse = wx.Button(p, label="Feliratfájl &tallózása…")
        b_browse.Bind(wx.EVT_BUTTON, lambda e: self._browse_sub())
        g.Add(b_browse, 0)

        g.Add(wx.StaticText(p, label="&Hang:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.voice_ch = wx.Choice(p, choices=[lbl for lbl, _e, _v in self._voices]
                                  or ["(nincs hang)"], name="Felolvasó hang")
        self.voice_ch.SetSelection(self._default_voice_index())
        g.Add(self.voice_ch, 0, wx.EXPAND)
        b_subload = wx.Button(p, label="Felirat be&töltése")
        b_subload.Bind(wx.EVT_BUTTON, lambda e: self._apply_sub())
        g.Add(b_subload, 0)

        g.Add(wx.StaticText(p, label="Felolvasás &tempója:"), 0,
              wx.ALIGN_CENTER_VERTICAL)
        self.rate_sp = wx.SpinCtrl(p, min=-10, max=10, initial=DEFAULT_RATE)
        self.rate_sp.SetName("Felolvasás tempója mínusz tíztől plusz tízig; "
                             "nagyobb érték gyorsabb beszéd. A filmfeliratok "
                             "gyorsan váltanak, ezért az alapérték gyors")
        g.Add(self.rate_sp, 0, wx.EXPAND)
        g.Add(wx.StaticText(p, label="(a filmfelirat gyorsan vált – a gyors "
                                     "tempó tartja a lépést)"), 0,
              wx.ALIGN_CENTER_VERTICAL)
        v.Add(g, 0, wx.EXPAND | wx.ALL, 8)

        ctl = wx.BoxSizer(wx.HORIZONTAL)
        for label, fn in (("Le&játszás / szünet", lambda e: self._toggle()),
                          ("&Leállítás", lambda e: self._stop()),
                          ("10 mp &vissza", lambda e: self._seek(-10)),
                          ("10 mp &előre", lambda e: self._seek(10)),
                          ("Hangerő &−", lambda e: self._vol(-0.1)),
                          ("Hangerő &+", lambda e: self._vol(0.1))):
            b = wx.Button(p, label=label)
            b.Bind(wx.EVT_BUTTON, fn)
            ctl.Add(b, 0, wx.RIGHT, 6)
        v.Add(ctl, 0, wx.LEFT | wx.BOTTOM, 8)

        self.now_lbl = wx.StaticText(p, label="Most nem szól semmi.")
        self.now_lbl.SetName("Lejátszás állapota")
        v.Add(self.now_lbl, 0, wx.LEFT | wx.BOTTOM, 8)

        v.Add(wx.StaticText(p, label="Épp felolvasott &felirat:"), 0, wx.LEFT, 8)
        self.cue_txt = wx.TextCtrl(
            p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP,
            size=(-1, 120))
        self.cue_txt.SetName("Épp felolvasott felirat")
        v.Add(self.cue_txt, 1, wx.EXPAND | wx.ALL, 8)
        p.SetSizer(v)

    # ---- segédek ------------------------------------------------------

    def _announce(self, text):
        self.SetStatusText(text)
        self.now_lbl.SetLabel(text)
        # FONTOS: vakon a státuszsor/címke változását a képernyőolvasó NEM olvassa
        # fel magától – ezért a program SAJÁT hangján (SAPI/eSpeak) is bemondjuk.
        # (force=True: akkor is szól, ha a self-voice alapból ki van kapcsolva.)
        sv = getattr(self.main, "selfvoice", None)
        if sv is not None and getattr(sv, "muted", False):
            return                       # TELJES némítás: egyetlen szót sem
        spoke = False
        # A BEJELENTŐ elsősorban a KÉPERNYŐOLVASÓ (ő az, akit a felhasználó a
        # saját beállításaival szabályoz) – csak ha nincs, jön a beépített hang.
        try:
            from superdl import screenreader
            spoke = bool(screenreader.speak(text))
        except Exception:
            spoke = False
        if not spoke and sv:
            try:
                sv.speak(text, force=True)
                spoke = True
            except Exception:
                pass
        # Ha a selfvoice NÉMÍTVA van (pl. képernyőolvasó-mód: a `muted` a force-ot
        # is felülírja) vagy hiányzik, akkor a FUTÓ képernyőolvasónak (NVDA/JAWS)
        # szólunk – különben az F8/állapot néma marad (Laci jelezte: „F8 csendben").
        if not spoke:
            try:
                from superdl import screenreader
                screenreader.speak(text, interrupt=True)
            except Exception:
                pass

    def _voice(self):
        i = self.voice_ch.GetSelection()
        return self._voices[i] if 0 <= i < len(self._voices) else \
            ("eSpeak", "espeak", "espeak:hu")

    def _default_voice_index(self) -> int:
        """Alapból MAGYAR hangot válasszunk, ne a lista első (gyakran ANGOL SAPI)
        hangját – különben a magyar feliratot angol kiejtéssel olvasná. Sorrend:
        magyar SAPI/Edge → a beépített eSpeak magyar → végső esetben az első."""
        hu = ("magyar", "hungar", "hu-", "hu_", "szabolcs", "espeak")
        for idx, (lbl, eng, vid) in enumerate(self._voices):
            hay = f"{lbl} {vid}".lower()
            if eng in ("sapi", "edge") and any(k in hay for k in hu):
                return idx
        for idx, (lbl, eng, vid) in enumerate(self._voices):
            if eng == "espeak":               # beépített magyar eSpeak
                return idx
        return 0

    # ---- média + felirat betöltése ------------------------------------

    def _load(self):
        wild = ("Film és hang|" + ";".join(
            "*" + e for e in subtitles.VIDEO_EXTS + subtitles.AUDIO_EXTS)
            + "|Minden fájl|*.*")
        dlg = wx.FileDialog(self, "Film vagy hangfájl betöltése", wildcard=wild,
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.media = dlg.GetPath()
            self.media_lbl.SetLabel(os.path.basename(self.media))
            self._scan_sources()
        dlg.Destroy()

    def open_file(self, path: str):
        """Fájltársításból hívva: a megadott médiát betölti, a legjobb feliratot
        (a magyar előre sorolt) magától kiválasztja és betölti, majd elindítja a
        lejátszást – így egy dupla kattintás azonnal „olvasható filmet" ad."""
        if not path or not os.path.isfile(path):
            return
        self.media = path
        self.media_lbl.SetLabel(os.path.basename(path))
        self._scan_sources()
        if self._sources:
            self.sub_ch.SetSelection(0)          # a legjobb (magyar) forrás
            self._apply_sub()
        # a felirat betöltése háttérszálon megy; a lejátszást kicsit később
        # indítjuk, hogy a scheduler már készen álljon
        wx.CallLater(700, self._start_if_ready)

    def _start_if_ready(self):
        if self.media and not self.film.is_active():
            self._toggle()

    def _load_url(self):
        """Online link (YouTube stb.) betöltése: a yt-dlp feloldja a hang-
        streamet és letölti a feliratot (manuális, vagy AUTO – magyarra fordítva
        is), majd a megszokott módon felolvassuk."""
        url = self.url_entry.GetValue().strip()
        if not ytsource.is_url(url):
            self._announce("Illessz be egy videó-linket (pl. YouTube).")
            return
        self._stop()
        self._announce("Link feloldása és felirat letöltése… (kis türelem)")

        def work():
            if not _ensure_net(self, "a videó-link megnyitásához"):
                return                       # nincs net / a felhasználó lemondta
            try:
                stream, cues, lang, title = ytsource.load_from_url(url)
            except Exception as e:
                wx.CallAfter(self._announce, f"A link nem tölthető be: {e}")
                return
            wx.CallAfter(self._url_ready, stream, cues, lang, title)

        threading.Thread(target=work, daemon=True).start()

    def _url_ready(self, stream, cues, lang, title):
        self.media = stream
        self.media_lbl.SetLabel(title[:90])
        self.cues = cues
        self.sched = subtitles.CueScheduler(cues)
        self._sources = []
        self.sub_ch.Set([f"YouTube-felirat: {lang}" if lang
                         else "(ehhez a videóhoz nincs felirat)"])
        self.sub_ch.SetSelection(0)
        if cues:
            self._announce(f"Betöltve: {title}. Felirat: {lang}, {len(cues)} "
                           "sor. Indíthatod a lejátszást (Szóköz).")
        else:
            self._announce(f"Betöltve: {title}. Ehhez a videóhoz NINCS "
                           "felolvasható felirat – a hang lejátszható, de nincs "
                           "mit felolvasni.")

    def _scan_sources(self):
        """A médiához tartozó feliratforrások összegyűjtése: mellé tett fájlok +
        beágyazott szöveges sávok."""
        self._sources = []
        for path in subtitles.find_sidecar_subs(self.media):
            self._sources.append((f"Fájl: {os.path.basename(path)}",
                                  "file", path))
        try:
            for tr in subtitles.embedded_text_tracks(self.media):
                self._sources.append((f"Beágyazott: {tr['label']}",
                                     "embedded", tr["index"]))
        except Exception:
            pass
        if self._sources:
            self.sub_ch.Set([lbl for lbl, _t, _d in self._sources])
            self.sub_ch.SetSelection(0)
            self._announce(f"{len(self._sources)} feliratforrás. Válassz, és "
                           "nyomd meg a „Felirat betöltése” gombot.")
        else:
            self.sub_ch.Set(["(nincs felirat – tallózz egyet)"])
            self.sub_ch.SetSelection(0)
            self._announce("Nem találtam feliratot a média mellett. Tallózz egy "
                           "feliratfájlt (.srt).")

    def _browse_sub(self):
        dlg = wx.FileDialog(
            self, "Feliratfájl kiválasztása",
            wildcard="Felirat|*.srt;*.vtt;*.ass;*.ssa;*.sub|Minden fájl|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self._sources.append((f"Fájl: {os.path.basename(path)}",
                                  "file", path))
            self.sub_ch.Set([lbl for lbl, _t, _d in self._sources])
            self.sub_ch.SetSelection(len(self._sources) - 1)
            self._announce("Feliratfájl hozzáadva. Nyomd meg a „Felirat "
                           "betöltése” gombot.")
        dlg.Destroy()

    def _apply_sub(self):
        i = self.sub_ch.GetSelection()
        if not (0 <= i < len(self._sources)):
            self._announce("Előbb válassz feliratforrást.")
            return
        _lbl, typ, data = self._sources[i]
        self._announce("Felirat betöltése…")

        def work():
            try:
                if typ == "file":
                    cues = subtitles.load_subtitle_file(data)
                else:
                    cues = subtitles.extract_embedded(self.media, data)
            except Exception as e:
                wx.CallAfter(self._announce, f"A felirat nem tölthető be: {e}")
                return
            wx.CallAfter(self._subs_ready, cues)

        threading.Thread(target=work, daemon=True).start()

    def _subs_ready(self, cues):
        self.cues = cues
        self.sched = subtitles.CueScheduler(cues)
        self._announce(f"{len(cues)} felirat betöltve. Indíthatod a lejátszást "
                       "(Szóköz).")

    # ---- lejátszás-vezérlés -------------------------------------------

    def _toggle(self):
        if not self.media:
            self._announce("Előbb tölts be egy médiát.")
            return
        if self._subs_only:                   # film-hang nélküli feliratolvasás
            self._subs_paused = not self._subs_paused
            if not self._subs_paused:
                self._clock_reset(self._clk_pos, fresh=False)
            self._announce("Szünet." if self._subs_paused else "Folytatás.")
            return
        if self.film.is_active():
            paused = self.film.toggle_pause()
            if not paused:
                self._clock_reset(self._clk_pos, fresh=False)   # folytatás
            self._announce("Szünet." if paused else "Folytatás.")
        else:
            if not self._voices:
                self._announce("Figyelem: nincs használható hangmotor (sem SAPI, "
                               "sem eSpeak), így a feliratot nem tudom "
                               "felolvasni. A film hangja megy. Súgó: F1.")
            self._subs_only = False
            self._subs_paused = False
            self._fired_any = False
            self._warned = False
            self._play_t0 = time.monotonic()
            self._film_dev = self._cur_out_name()   # amin a film most megszólal
            self._dev_poll = 0
            self.film.set_volume(self._film_vol)
            self.film.play(self.media)
            if self.sched:
                self.sched.reset_to(0.0)
            self._clock_reset(0.0)
            self.timer.Start(150)
            self._announce("Lejátszás.")

    def _stop(self):
        self.timer.Stop()
        self.narr.stop()
        self.film.stop()
        self._narrating = False
        self._subs_only = False
        self._subs_paused = False
        self._drop_ahead()
        self._clock_reset(0.0)
        self._announce("Leállítva.")

    def _seek(self, delta):
        if not self.film.is_active():
            return
        pos = max(0.0, self._clk_pos + delta)   # a felolvasott idővonalhoz mérten
        self.narr.stop()
        self._narrating = False
        self._drop_ahead()            # az előre gyártott hangok elavultak
        self.film.set_volume(self._film_vol)
        self.film.seek(pos)
        if self.sched:
            self.sched.reset_to(pos)
        self._clock_reset(pos)        # ugrás → ffmpeg-újraindulás → friss horgony
        self._announce(f"Ugrás: {int(pos // 60)} perc {int(pos % 60)} mp.")

    def _vol(self, delta):
        self._film_vol = max(0.0, min(1.0, self._film_vol + delta))
        if not self._narrating:
            self.film.set_volume(self._film_vol)
        self._announce(f"Hangerő: {round(self._film_vol * 100)} százalék.")

    # ---- a szinkron szíve: időzítő --------------------------------------

    def _tick(self):
        if not self.sched:
            return
        if self._subs_only:                   # film-hang nélküli feliratolvasás
            if self._subs_paused:
                return
        elif not self.film.is_active() or self.film.is_paused():
            return
        pos = self._clock()                   # a narrációt vezérlő idő
        # HANGESZKÖZ-KÖVETÉS (ritkítva, ~1,5 mp-enként, csak ha épp nem narrál):
        # ha az alapeszköz megváltozott (pl. Bluetooth), a filmet átvezetjük rá
        if not self._subs_only and not self._narrating and self.film.is_active():
            self._dev_poll += 1
            if self._dev_poll >= 10:
                self._dev_poll = 0
                dev = self._cur_out_name()
                if dev and self._film_dev and dev != self._film_dev:
                    self._reroute_audio(auto=True)
                    return
        # proaktív: ha ~6 mp lejátszás után SEMMI nem szólalt meg, mondjuk el, mi
        # az állapot – így a felhasználó F8 nélkül is tudja, hol akad (és halljuk,
        # halad-e az idő egyáltalán)
        if (not self._fired_any and not self._warned and self._play_t0
                and time.monotonic() - self._play_t0 > 6.0):
            self._warned = True
            self._diag(prefix="A felolvasás még nem indult el. ")
        self._prefetch()                      # a KÖVETKEZŐ sor előre legyártása
        if self._narrating:
            return
        cue = self.sched.next_due(pos)
        if cue:
            self._fired_any = True
            self._narrate(cue)

    def _clock_reset(self, pos, fresh=True):
        """A narráció-óra újrahorgonyzása. `fresh=True`: a film hangja ELÖLRŐL
        indul (lejátszás-indítás, ugrás → ffmpeg-újraindulás, indulási puffer);
        `fresh=False`: csak folytatás szünetből (a hang azonnal szól tovább)."""
        now = time.monotonic()
        self._clk_pos = max(0.0, pos)
        self._clk_apos = self.film.position()
        self._clk_wall = now
        if fresh:
            self._clk_started = False
            self._clk_t0 = now

    def _clock(self):
        """A narrációt vezérlő idő másodpercben. Amíg a film HANG-pozíciója
        egészségesen halad, azt követi (pontos szinkron); ha beragad (indulási
        puffer, nem dekódolható film-hang, stream-akadás), a fali óra lépteti
        ELŐRE – így a felolvasás sosem áll le némán. Sosem ugrik vissza."""
        now = time.monotonic()
        dt = now - self._clk_wall
        self._clk_wall = now
        if dt <= 0:
            return self._clk_pos
        if self._subs_only:                   # nincs film-hang → tisztán fali óra
            self._clk_pos += dt
            return self._clk_pos
        apos = self.film.position()
        da = apos - self._clk_apos
        self._clk_apos = apos
        if da > 0:
            self._clk_started = True
        if self._clk_started and 0 < da <= dt * 4.0:
            # a hang ténylegesen haladt → azt követjük, finom abszolút resynckel
            self._clk_pos += da
            self._clk_pos += (apos - self._clk_pos) * 0.15
        elif self._clk_started:
            # a hang elindult, de épp nem haladt (akadás) → fali óra viszi tovább
            self._clk_pos += dt
        elif now - self._clk_t0 > 2.5:
            # a hang ~2,5 mp után sem indult el (nem dekódolható film-hang):
            # a fali óra veszi át, hogy a felolvasás akkor is elinduljon
            self._clk_pos += dt
        # különben: normál indulási puffer alatt VÁRUNK (a pozíció 0 marad)
        return self._clk_pos

    def _prefetch(self):
        """A soron következő feliratot ELŐRE legyártjuk, amíg az előző szól.
        MÉRÉS: az Edge neurális hang soronként ~1,6 mp hálózati válaszidőt kér –
        e nélkül még gyors tempón sem tartja a lépést a film-ritmussal. Az
        időbélyegekből tudjuk, mi jön, így a késleltetés eltűnik."""
        if self._ahead_busy or not self.sched:
            return
        i = self.sched._i                     # a következő, még ki nem adott sor
        if i >= len(self.sched.cues) or i in self._ahead:
            return
        cue = self.sched.cues[i]
        # csak ha már „a láthatáron" van (ne gyártsunk feleslegesen előre)
        if cue.start - self._clk_pos > 12.0:
            return
        self._ahead_busy = True
        lbl, eng, vid = self._voice()
        rate = self.rate_sp.GetValue()

        def work():
            path, err = self._synth(eng, vid, cue.text, rate)
            if self._closing:                 # közben bezárták az ablakot
                self._safe_del(path) if path else None
                return
            try:
                wx.CallAfter(self._prefetch_done, i, path, err)
            except Exception:
                pass

        threading.Thread(target=work, daemon=True).start()

    def _synth(self, eng, vid, text, rate):
        """A felirat szövegének hangfájlba szintézise. Ha a választott motor
        hibázik (pl. SAPI-hiba, Edge hálózati hiba), AUTOMATIKUSAN a beépített
        magyar eSpeak-re vált – inkább szóljon, mint hogy néma maradjon. A hibát
        NEM nyeljük el: visszaadjuk, hogy a hívó bemondhassa és F8-ra megmutassa.
        Visszaad: (útvonal vagy None, hibaszöveg vagy '')."""
        try:
            return narrator.synth_to_file(eng, vid, text, rate=rate), ""
        except Exception as e:
            err = f"{eng}: {e}"
        if eng != "espeak":                   # tartalék: beépített magyar eSpeak
            try:
                return (narrator.synth_to_file("espeak", "espeak:hu", text,
                                               rate=rate), err)
            except Exception as e2:
                err = f"{err} | eSpeak-tartalék: {e2}"
        return None, err

    def _prefetch_done(self, i, path, err=""):
        self._ahead_busy = False
        if err:
            self._last_tts_err = err
        if self._closing:
            if path:
                self._safe_del(path)
            return
        if path:
            self._ahead[i] = path

    def _narrate(self, cue):
        self._narrating = True
        self.cue_txt.SetValue(cue.text)
        # az ELŐRE legyártott hang (a scheduler már továbblépett, ezért i-1)
        idx = self.sched._i - 1
        ready = self._ahead.pop(idx, None)
        if ready:
            self._play_narration(ready)       # azonnal szól: nincs késleltetés
            return
        lbl, eng, vid = self._voice()
        rate = self.rate_sp.GetValue()

        def work():
            path, err = self._synth(eng, vid, cue.text, rate)
            if self._closing:                 # közben bezárták az ablakot
                self._safe_del(path) if path else None
                return
            try:
                if path:
                    wx.CallAfter(self._narration_ok, path, err, eng)
                else:
                    wx.CallAfter(self._narration_failed, eng, err)
            except Exception:
                pass

        threading.Thread(target=work, daemon=True).start()

    def _narration_ok(self, path, err, eng):
        """Sikeres szintézis (esetleg eSpeak-tartalékkal). Ha tartalékra kellett
        váltani (err nem üres, de van hang), EGYSZER bemondjuk – hogy a felhasználó
        tudja: a választott hang nem ment, de mégis hall valamit."""
        self._narr_fail = 0
        self._last_ok = time.strftime("%H:%M:%S")
        if err:
            self._last_tts_err = err
            if not getattr(self, "_fallback_said", False):
                self._fallback_said = True
                self._announce("A választott hang nem működött (" +
                               _rovid_hiba(err) + "), átváltottam a beépített "
                               "magyar eSpeak hangra. Részletek: F8.")
        self._play_narration(path)

    def _narration_failed(self, eng, err):
        """A szintézis (a tartalékkal együtt) sem sikerült. NEM maradunk némán:
        bemondjuk az okot, és F8-ra megmutatjuk a technikai részletet."""
        self._last_tts_err = err or "ismeretlen hiba"
        self._narr_fail += 1
        self._narration_done()                # ducking vissza, narrating=False
        if self._narr_fail <= 2 or self._narr_fail % 10 == 0:
            self._announce(f"A felirat hangosítása nem sikerült. Hangmotor: "
                           f"{eng}. Próbálj másik hangot. Részletek: F8.")

    def _drop_ahead(self):
        """Az előre gyártott hangok eldobása (ugrás/leállítás után elavultak)."""
        for p in self._ahead.values():
            self._safe_del(p)
        self._ahead.clear()

    def _play_narration(self, path):
        if not self._subs_only and not self.film.is_active():   # közben leállt
            self._safe_del(path)
            self._narration_done()
            return
        self._cur_temp = path
        if not self._subs_only:
            self.film.set_volume(self._film_vol * DUCK)     # film halkítása
        self.narr.play(path)

    def _on_narr_state(self, s):
        if s.startswith("hiba"):
            # a narrációs Player hibája (pl. a MÁSODIK hangstream nem nyílik meg
            # egyes eszközökön) EDDIG „normál befejezésként" némán elveszett
            self._last_tts_err = f"narráció-lejátszás: {s}"
            self._narr_fail += 1
            self._narration_done()
            if self._narr_fail <= 2:
                self._announce("A felirat hangja nem szólaltatható meg ezen a "
                               "hangeszközön. Részletek: F8.")
        elif s.startswith("vége"):
            self._narration_done()

    def _narration_done(self):
        self.film.set_volume(self._film_vol)            # film vissza
        if self._cur_temp:
            self._safe_del(self._cur_temp)
            self._cur_temp = None
        self._narrating = False

    @staticmethod
    def _safe_del(path):
        try:
            os.remove(path)
        except OSError:
            pass

    def _on_film_state(self, s):
        if s.startswith("vége"):
            self.timer.Stop()
            self._subs_only = False
            self._announce("A média véget ért.")
        elif s.startswith("hiba"):
            # ha a film HANGJA nem játszható le, de VAN betöltött felirat:
            # ne álljunk le némán – olvassuk a feliratot csend fölött, fali
            # órával (ez pontosan a „megtalálja, de a mező üres" eset mentése)
            if self.cues and self.sched and not self._subs_only:
                self._subs_only = True
                self._subs_paused = False
                self._warned = False
                self._play_t0 = time.monotonic()
                self._clock_reset(self._clk_pos)
                if not self.timer.IsRunning():
                    self.timer.Start(150)
                self._announce("A film hangját nem tudom lejátszani, de a "
                               "feliratot felolvasom (film-hang nélkül). "
                               "Részletek: F8.")
            else:
                self.timer.Stop()
                self._announce(s)

    # ---- billentyűk / súgó / zárás ------------------------------------

    def _setup_accelerators(self):
        """GLOBÁLIS gyorsbillentyűk AcceleratorTable-lel, hogy MINDEN vezérlőn
        (a gombokon is!) elsüljenek. A CHAR_HOOK a gombokon (wxMSW) nem mindig
        sül el, ezért a hangerő „kiszökött" a modulból a főablakra (Laci jelezte).
        A Space és a bal/jobb nyíl a CHAR_HOOK-ban marad, mert azoknál a fókusz
        (szövegmező/legördülő) számít."""
        self._acc = {k: wx.NewIdRef() for k in
                     ("help", "f6", "f7", "f8", "volup", "voldn", "stop")}
        tbl = [
            (wx.ACCEL_NORMAL, wx.WXK_F1, self._acc["help"]),
            (wx.ACCEL_NORMAL, wx.WXK_F6, self._acc["f6"]),
            (wx.ACCEL_NORMAL, wx.WXK_F7, self._acc["f7"]),
            (wx.ACCEL_NORMAL, wx.WXK_F8, self._acc["f8"]),
            (wx.ACCEL_CTRL, wx.WXK_UP, self._acc["volup"]),
            (wx.ACCEL_CTRL, wx.WXK_DOWN, self._acc["voldn"]),
            (wx.ACCEL_NORMAL, wx.WXK_ESCAPE, self._acc["stop"]),
        ]
        self.SetAcceleratorTable(
            wx.AcceleratorTable([wx.AcceleratorEntry(*e) for e in tbl]))
        for key, fn in (("help", lambda e: self._help()),
                        ("f6", lambda e: self._reroute_audio(auto=False)),
                        ("f7", lambda e: self._test_voice()),
                        ("f8", lambda e: self._diag()),
                        ("volup", lambda e: self._vol(0.1)),
                        ("voldn", lambda e: self._vol(-0.1)),
                        ("stop", lambda e: self._stop())):
            self.Bind(wx.EVT_MENU, fn, id=self._acc[key])

    def _on_key(self, e):
        code = e.GetKeyCode()
        # a globális gyorsbillentyűket (F1/F6/F7/F8, Ctrl+fel/le, Esc) az
        # AcceleratorTable kezeli – itt CSAK a fókuszfüggő Space/nyíl marad
        if code == wx.WXK_SPACE and not isinstance(
                self.FindFocus(), (wx.TextCtrl,)):
            self._toggle()
        elif code == wx.WXK_LEFT and e.ControlDown() is False \
                and isinstance(self.FindFocus(), wx.Choice) is False:
            self._seek(-10)
        elif code == wx.WXK_RIGHT and isinstance(self.FindFocus(),
                                                 wx.Choice) is False:
            self._seek(10)
        else:
            e.Skip()

    def _cur_out_name(self) -> str:
        """A jelenlegi alapértelmezett KIMENETI hangeszköz neve (best-effort)."""
        try:
            import sounddevice as sd
            d = sd.query_devices(kind="output")
            return d.get("name", "") if isinstance(d, dict) else ""
        except Exception:
            return ""

    def _reroute_audio(self, auto: bool = False):
        """A film hangját ÁTVEZETI az aktuális alapértelmezett hangeszközre: a
        jelenlegi pozíción újranyitja a film streamjét (ez az új eszközre kerül,
        ahogy a narráció is). Így pl. Bluetooth-ra váltva a film hangja is átjön.
        `auto=True`: eszközváltás magától észlelve; False: F6-tal kézzel."""
        if self._subs_only or not self.film.is_active():
            if not auto:
                self._announce("Nincs mit átvezetni – előbb indítsd el egy film "
                               "lejátszását.")
            return
        pos = self._clk_pos
        self.narr.stop()
        self._narrating = False
        self._drop_ahead()
        self.film.set_volume(self._film_vol)
        self.film.seek(pos)                  # újranyitás → az AKTUÁLIS alapeszközre
        if self.sched:
            self.sched.reset_to(pos)
        self._clock_reset(pos)
        self._film_dev = self._cur_out_name()
        dev = f" ({self._film_dev})" if self._film_dev else ""
        self._announce((f"Hangeszköz-váltás: a film hangját átvezettem az új "
                        f"eszközre{dev}.") if auto else
                       (f"A film hangját átvezettem az aktuális hangeszközre{dev}."))

    def _test_voice(self):
        """F7: a KIVÁLASZTOTT felolvasó hang azonnali kipróbálása (film nélkül).
        Így a felhasználó egy gombnyomással ellenőrizheti, hogy a hangútvonal
        (szintézis + lejátszás) egyáltalán megszólal-e – ez a leggyorsabb módja a
        „miért néma?" kérdés eldöntésének."""
        if not self._voices:
            self._announce("Nincs használható hangmotor (sem SAPI, sem eSpeak). "
                           "A feliratot nem tudom felolvasni. Súgó: F1.")
            return
        lbl, eng, vid = self._voice()
        rate = self.rate_sp.GetValue()
        self._announce(f"Hang kipróbálása: {lbl}. Egy pillanat…")

        def work():
            path, err = self._synth(
                eng, vid, "Ez a felolvasó hang próbája. Ha ezt hallod, a "
                "felirat felolvasása működik.", rate)
            if self._closing:
                self._safe_del(path) if path else None
                return
            if path:
                wx.CallAfter(self._play_test, path, err)
            else:
                wx.CallAfter(self._announce, "A hang kipróbálása NEM sikerült. "
                             "Válassz másik hangot. Részletek: F8.")

        threading.Thread(target=work, daemon=True).start()

    def _play_test(self, path, err):
        if err and not getattr(self, "_fallback_said", False):
            self._fallback_said = True
            self._last_tts_err = err
            self._announce("A választott hang nem működött (" + _rovid_hiba(err) +
                           "), a beépített magyar eSpeak hanggal próbálom. "
                           "Részletek: F8.")
        self._cur_temp = path             # a narr „vége" majd törli
        self.narr.play(path)

    def _diag(self, prefix=""):
        """F8: a felolvasás állapotának bemondása – hibakereséshez. Egy
        gombnyomással kiderül, MELYIK VERZIÓ fut, halad-e az idő, be van-e
        töltve a felirat, és épp mit olvas – így egy elakadás pontosan
        behatárolható."""
        if not self.media:
            self._announce(f"{prefix}Felirat-felolvasó {MOD_VERSION}. Nincs "
                           "betöltve média. Tölts be egy filmet vagy hangfájlt.")
            return
        n = len(self.cues)
        if self._subs_only:
            state = "felirat felolvasása film-hang nélkül"
            if self._subs_paused:
                state += " (szünet)"
        elif not self.film.is_active():
            state = "áll (nincs lejátszás – nyomd meg a Szóközt)"
        elif self.film.is_paused():
            state = "szünet"
        else:
            state = "lejátszás"
        pos = self._clk_pos
        cur = self.cue_txt.GetValue().strip() or "most éppen semmi"
        subs = (f"{n} feliratsor betöltve" if n
                else "NINCS betöltött felirat – nyomd meg a „Felirat betöltése” "
                     "gombot")
        lbl, eng, vid = self._voice()
        hang = f"Hang: {lbl}." if self._voices else \
            "NINCS használható hangmotor (sem SAPI, sem eSpeak)."
        err = (f" Utolsó hanghiba: {self._last_tts_err}."
               if self._last_tts_err else "")
        outdev = self._cur_out_name()
        dev = f" Hangeszköz: {outdev}." if outdev else ""
        self._announce(f"{prefix}Felirat-felolvasó {MOD_VERSION}. Állapot: "
                       f"{state}. Idő: {int(pos // 60)} perc {int(pos % 60)} "
                       f"másodperc. {subs}. {hang}{err}{dev} Épp felolvasva: "
                       f"{cur}.")

    def _help(self):
        try:
            from superdl.helpdialog import show_help
            show_help(self, "Felirat-felolvasó lejátszó", HELP)
        except Exception:
            wx.MessageBox(HELP, "Súgó – Felirat-felolvasó",
                          wx.OK | wx.ICON_INFORMATION, self)

    def _on_close(self, e):
        self._closing = True          # a futó gyártó-szálak ne nyúljanak hozzánk
        try:
            self.timer.Stop()
            self.narr.stop()
            self.film.stop()
            self._drop_ahead()        # az ideiglenes hangfájlok takarítása
            if self._cur_temp:
                self._safe_del(self._cur_temp)
        except Exception:
            pass
        if getattr(self.main, "_felolvaso_win", None) is self:
            self.main._felolvaso_win = None
        self.Destroy()
