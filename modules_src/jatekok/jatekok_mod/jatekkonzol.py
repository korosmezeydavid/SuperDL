# -*- coding: utf-8 -*-
"""JatekKonzol – közös, akadálymentes játékablak a retró játékokhoz.

Minden retró játék generátor-korutin (lásd `jatekok/_util`). A konzol hajtja:
- a `mond`/`vege` kimenetet az átiratba írja ÉS hangosan felolvassa,
- a `kerdez`-nél megvárja a beírt választ, majd visszaküldi a játéknak.

AKADÁLYMENTESSÉG:
- Az indításkor elhangzik (retró hangon) és megjelenik a SZERZŐ-MEGJELÖLÉS.
- Görgethető átirat (a képernyőolvasó bármikor visszaolvassa) + beviteli mező.
- A retró hang a Hangbeállításban választott karakteren szól, háttérszálon,
  sorba állítva; Escape azonnal elnémítja. Kikapcsolva a képernyőolvasó
  (selfvoice) mondja a sorokat – így MINDIG pontosan egy hangcsatorna szól.
"""
import queue
import threading

import wx

from superdl import retrospeech as RS

_HANG_CFG = "jatekok.json"                 # közös a Hangbeállítással


def _retro_hang_be() -> bool:
    """A MEGŐRZÖTT „retró hang beszéljen" beállítás. ALAPBÓL KIKAPCSOLVA –
    akinek kell, a játékban vagy a Hangbeállításban bekapcsolja, és a választás
    megmarad a következő játékokra is."""
    try:
        from superdl import store
        cfg = store.load_json(store.CONFIG_DIR / _HANG_CFG, {})
        return bool(cfg.get("retro_hang", False))
    except Exception:
        return False


def _retro_hang_ment(be: bool) -> None:
    """A választás megőrzése (a jatekok.json-ban), hogy ne kapcsoljon vissza."""
    try:
        from superdl import store
        p = store.CONFIG_DIR / _HANG_CFG
        cfg = store.load_json(p, {})
        cfg["retro_hang"] = bool(be)
        store.save_json(p, cfg)
    except Exception:
        pass
from . import katalogus
from . import jatekok as JR

# a magyar ábécé, amit az `abcstop` parancs másodpercenként sorol (a játékos a
# szóközzel/Enterrel állítja meg – SOHA nem a gép dönti el a betűt)
_ABC = ("a", "á", "b", "c", "d", "e", "é", "f", "g", "h", "i", "í", "j", "k",
        "l", "m", "n", "o", "ó", "ö", "ő", "p", "r", "s", "t", "u", "ú", "ü",
        "ű", "v", "z")


class RetroHang:
    """A retró hang SORBA ÁLLÍTOTT lejátszója: minden bemondott szöveget a
    kiválasztott karakteren szintetizál és a többi után játszik le. Külön
    háttérszálon dolgozik, hogy a felület ne akadjon meg."""

    def __init__(self, gep_getter):
        self._q = queue.Queue()
        self._get_gep = gep_getter
        self._player = None
        self._done = threading.Event()
        self._worker = None
        self._stop = False
        self._skip = False
        self.enabled = True

    def _ensure(self):
        if self._player is None:
            from superdl.audioengine import Player
            self._player = Player()
            self._player.on_state = self._on_state
        if self._worker is None or not self._worker.is_alive():
            self._stop = False
            self._worker = threading.Thread(target=self._run, daemon=True)
            self._worker.start()

    def _on_state(self, s):
        if s.startswith("vége") or s.startswith("hiba"):
            self._done.set()

    def mond(self, szoveg):
        if not self.enabled or not (szoveg or "").strip():
            return
        self._ensure()
        self._q.put(szoveg)

    def _run(self):
        while not self._stop:
            try:
                szoveg = self._q.get(timeout=0.3)
            except queue.Empty:
                continue
            if self._stop or self._skip:
                self._skip = False
                continue
            beall = self._get_gep()
            if isinstance(beall, tuple):
                kulcs, tempo = beall
            else:
                kulcs, tempo = beall, 1.0
            try:
                try:
                    path = RS.synth(szoveg, "", kulcs, tempo_szorzo=tempo)
                except TypeError:
                    # régebbi Core: nincs tempo_szorzo – tempó nélkül, de NEM néma
                    path = RS.synth(szoveg, "", kulcs)
            except Exception:
                continue
            if self._stop or self._skip:
                self._skip = False
                continue
            self._done.clear()
            try:
                self._player.play(path, "")
            except Exception:
                continue
            while not self._done.wait(0.1):
                if self._stop:
                    break

    def nema(self):
        """Azonnali elnémítás: a sor ürítése + az aktuális leállítása."""
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass
        self._skip = True
        if self._player:
            try:
                self._player.stop()
            except Exception:
                pass
        self._done.set()

    def leallit(self):
        self._stop = True
        self.nema()


class JatekKonzol(wx.Dialog):
    def __init__(self, main, jatek, gep_getter):
        super().__init__(main, title=f"Játék – {jatek.nev}",
                         size=(760, 560),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.main = main
        self.jatek = jatek
        self._closing = False
        self._gen = None
        self._var = False               # épp bemenetre várunk-e
        # az „ábécé-megállítás" (abcstop) valós idejű állapota
        self._abc_active = False
        self._abc_betuk = []
        self._abc_idx = 0
        self._abc_koz = 1000
        self._hang = RetroHang(gep_getter)
        self._tone_player = None
        self._sapi = None            # rendszer-TTS tartalék (lusta)

        self._build()
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        wx.CallAfter(self._indul)

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        v = wx.BoxSizer(wx.VERTICAL)
        self.atirat = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.atirat.SetName(f"{self.jatek.nev} – játék szövege")
        v.Add(self.atirat, 1, wx.EXPAND | wx.ALL, 8)

        v.Add(wx.StaticText(self, label="&Válaszod (írd be, majd Enter):"),
              0, wx.LEFT, 8)
        self.bemenet = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.bemenet.SetName("Válaszod")
        self.bemenet.Bind(wx.EVT_TEXT_ENTER, lambda e: self._kuld())
        v.Add(self.bemenet, 0, wx.EXPAND | wx.ALL, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        self.kuld_gomb = wx.Button(self, label="&Küldés")
        self.kuld_gomb.Bind(wx.EVT_BUTTON, lambda e: self._kuld())
        sor.Add(self.kuld_gomb, 0, wx.RIGHT, 6)
        b_ujra = wx.Button(self, label="Ú&jra")
        b_ujra.Bind(wx.EVT_BUTTON, lambda e: self._indul())
        sor.Add(b_ujra, 0, wx.RIGHT, 6)
        self.hang_kapcs = wx.CheckBox(self, label="&Retró hang beszéljen")
        # A retró hang ALAPBÓL KIKAPCSOLVA; a felhasználó választását MEGŐRIZZÜK
        # (nem kapcsol vissza magától minden játéknál – korábbi bosszúság).
        self.hang_kapcs.SetValue(bool(self.jatek.retro) and _retro_hang_be())
        self._hang.enabled = self.hang_kapcs.GetValue()
        self.hang_kapcs.Bind(wx.EVT_CHECKBOX, self._hang_kapcsol)
        sor.Add(self.hang_kapcs, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        if not self.jatek.retro:
            # a Saját játékok NEM a retró géphangon szólnak, hanem normál
            # rendszerhangon – a retró kapcsoló itt nem értelmes
            self.hang_kapcs.Hide()
        # az ábécé-megállító gomb (csak pörgetés közben látszik); a szóköz/Enter
        # is megállítja, de a gombot a képernyőolvasó is bemondja
        self.allj_gomb = wx.Button(self, label="&ÁLLJ! (szóköz vagy Enter)")
        self.allj_gomb.Bind(wx.EVT_BUTTON, lambda e: self._abcstop_stop())
        self.allj_gomb.Hide()
        sor.Add(self.allj_gomb, 0, wx.RIGHT, 6)
        b_ki = wx.Button(self, label="&Kilépés a játékból")
        b_ki.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        sor.Add(b_ki, 0)
        v.Add(sor, 0, wx.ALL, 8)
        # A „megfejtendő sor" MINDIG a mező alján, külön csak-olvasható mezőben:
        # így hallás után nem kell felfelé nyilazni és szavanként odaugrálni hozzá.
        # Csak akkor jelenik meg, ha a játék használja (ctx.tabla).
        self.tabla_mezo = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 58))
        self.tabla_mezo.SetName("Megfejtendő sor")
        self.tabla_mezo.Hide()
        v.Add(self.tabla_mezo, 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(v)

    # ---- a játék hajtása ----------------------------------------------

    def _indul(self):
        """(Újra)indítja a játékot: szerző-intro, majd az első kérdésig fut."""
        self._hang.nema()
        self.atirat.SetValue("")
        fugg = JR.get(self.jatek.kulcs)
        if fugg is None:
            self._ki("Ez a játék még készül.")
            return
        if self.jatek.retro and (self.jatek.szerzo or True):
            intro = katalogus.attribucio_szoveg(self.jatek)
            self._ki(intro)
            self._ki("")
        if self.jatek.felnott:
            self._ki("Figyelem: ez a játék felnőtt, humoros hangvételű – "
                     "18 éven felülieknek ajánlott.")
            self._ki("")
        self._gen = fugg(_KonzolCtx())
        self._pump(None)

    def _pump(self, send):
        if self._gen is None or self._closing:
            return
        while True:
            try:
                cmd = self._gen.send(send)
            except StopIteration:
                self._veget_er()
                return
            except Exception as e:
                self._ki(f"Hiba a játékban: {e}")
                self._veget_er()
                return
            send = None
            typ = cmd[0]
            payload = cmd[1] if len(cmd) > 1 else ""
            if typ == "mond":
                self._ki(payload)
                continue
            if typ == "tabla":
                self._tabla(payload)
                continue
            if typ == "hang":
                self._hang_tone(payload)
                continue
            if typ == "effekt":
                self._effekt(payload)
                continue
            if typ == "effekt_var":
                # lejátssza a hangot, majd MEGVÁRJA a végét (max 8 mp), hogy a
                # hangok NE olvadjanak össze; a hosszt a felület méri.
                self._effekt(payload)
                ms = min(self._hang_hossz_ms(payload), 8000)
                if ms > 0 and not self._closing:
                    wx.CallLater(ms, lambda: self._pump(None))
                    return
                continue
            if typ == "szunet":
                # NEM-BLOKKOLÓ várakozás (pl. amíg a kerékpörgés-hang lejátszódik):
                # ütemezzük a folytatást, és kilépünk a hurokból, hogy a felület ne
                # fagyjon be. A várakozás után a _pump(None) folytatja a generátort.
                ms = int(payload) if payload else 0
                if ms > 0 and not self._closing:
                    wx.CallLater(ms, lambda: self._pump(None))
                    return
                continue
            if typ == "enek":
                self._enek(payload)
                continue
            if typ == "abcstop":
                # a gép SOROLJA az ábécét (másodpercenként), a játékos a
                # szóközzel/Enterrel megállítja – a megállított betű megy vissza
                self._abcstop_start(payload)
                return
            if typ == "kerdez":
                self._ki(payload)
                self._var_bemenet(True)
                return
            if typ == "vege":
                if payload:
                    self._ki(payload)
                self._veget_er()
                return

    def _kuld(self):
        if not self._var or self._closing:
            return
        szoveg = self.bemenet.GetValue().strip()
        self.bemenet.SetValue("")
        if szoveg:
            self._ki(f"➤ {szoveg}", felolvas=False)
        # CSAK az őrt állítjuk (ne dolgozzon fel újabb Entert); a mezőt NEM
        # tiltjuk le, mert az áthelyezné a fókuszt egy gombra, és a képernyő-
        # olvasó felolvasná a nevét (ez okozta az ábécé-indítás előtti „kis
        # kommentárt"). A következő lépés úgyis beállítja a helyes bevitel-állapotot.
        self._var = False
        self._pump(szoveg)

    def _veget_er(self):
        self._gen = None
        self._var_bemenet(False)
        self._ki("")
        self._ki("A játéknak vége. Új játékhoz: Újra gomb. Kilépés: Escape.")

    # ---- kimenet / bemenet-állapot ------------------------------------

    def _tabla(self, szoveg):
        """A megfejtendő sort a MINDIG-ALUL lévő külön mezőbe teszi, és fel is
        olvassa (az átiratba is bekerül, utolsó sorként)."""
        if self._closing:
            return
        if not self.tabla_mezo.IsShown():
            self.tabla_mezo.Show()
            self.Layout()
        self.tabla_mezo.SetValue(szoveg or "")
        self._ki(szoveg)

    def _ki(self, szoveg, felolvas=True):
        """Egy sor az átiratba + (retró hang VAGY képernyőolvasó) felolvasás."""
        if self._closing:
            return
        self.atirat.AppendText((szoveg or "") + "\n")
        if not felolvas or not (szoveg or "").strip():
            return
        if self.hang_kapcs.GetValue():
            self._hang.mond(szoveg)
        else:
            self._beszel_rendszer(szoveg)

    def _beszel_rendszer(self, szoveg):
        """Normál (nem retró) felolvasás. ELŐBB a FUTÓ képernyőolvasó (Tolk) –
        így a felhasználó a saját, megszokott, magyar hangján hallja (Farkas nem
        érti a retrót; Áron kérte a Tolkot). Ha nincs képernyőolvasó, marad az
        app SelfVoice, különben a rendszer-TTS (SAPI)."""
        try:
            from superdl import screenreader
            if screenreader.speak(szoveg):
                return
        except Exception:
            pass
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            try:
                sv.speak(szoveg, force=True)
                return
            except Exception:
                pass
        if self._sapi is None:
            try:
                from superdl.speech import Speaker
                sp = Speaker()
                self._sapi = sp if getattr(sp, "available", False) else False
            except Exception:
                self._sapi = False
        if self._sapi:
            try:
                self._sapi.speak(szoveg)
            except Exception:
                pass

    def _hang_tone(self, hangok):
        """Rövid szinuszhangok lejátszása (Zongora). WAV-ba szintetizálja és a
        beszédtől külön lejátszón szólaltatja meg."""
        if self._closing or not hangok:
            return
        try:
            import os
            import tempfile
            import uuid
            import wave
            import numpy as np
            fs = 22050
            reszek = []
            for freq, ms in hangok:
                n = max(1, int(fs * ms / 1000.0))
                t = np.arange(n) / fs
                jel = 0.35 * np.sin(2 * np.pi * float(freq) * t)
                burk = np.minimum(1.0, np.minimum(np.arange(n), n - np.arange(n))
                                  / (0.02 * fs + 1))    # kattanás-mentes
                reszek.append(jel * burk)
                reszek.append(np.zeros(int(fs * 0.03)))
            pcm = (np.clip(np.concatenate(reszek), -1, 1) * 32767).astype("<i2")
            out = os.path.join(tempfile.gettempdir(),
                               f"superdl_zongora_{uuid.uuid4().hex[:8]}.wav")
            with wave.open(out, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(fs)
                w.writeframes(pcm.tobytes())
            if self._tone_player is None:
                from superdl.audioengine import Player
                self._tone_player = Player()
            self._tone_player.play(out, "")
        except Exception:
            pass

    _hang_hossz_cache = {}

    def _hang_fajl(self, nev):
        """A megnevezett hanghoz tartozó, modulba CSOMAGOLT fájl útvonala (WAV vagy
        MP3) a hangmappákból; vagy None, ha nincs ilyen."""
        import os
        for mappa in ("milliomos_hang", "szerencsekerek_hang"):
            for kit in (".wav", ".mp3"):
                p = os.path.join(os.path.dirname(__file__), mappa, f"{nev}{kit}")
                if os.path.isfile(p):
                    return p
        return None

    def _hang_hossz_ms(self, nev):
        """A csomagolt hangeffekt hossza ms-ban (mérve, gyorsítótárazva) – ennyit
        vár az `effekt_var`, hogy a hang ne olvadjon a következőbe. WAV-nál a wave
        modul, egyébként a Core ffmpeg-je (Duration). Ha nem mérhető: 0."""
        if nev in self._hang_hossz_cache:
            return self._hang_hossz_cache[nev]
        ms = 0
        p = self._hang_fajl(nev)
        try:
            if p and p.lower().endswith(".wav"):
                import wave
                with wave.open(p) as w:
                    ms = int(w.getnframes() / float(w.getframerate()) * 1000)
            elif p:
                ms = self._ffmpeg_hossz_ms(p)
        except Exception:
            ms = 0
        self._hang_hossz_cache[nev] = max(0, ms)
        return self._hang_hossz_cache[nev]

    @staticmethod
    def _ffmpeg_hossz_ms(path):
        """Egy hangfájl hossza ms-ban a Core ffmpeg-jével (a Duration sort olvassuk
        ki az ffmpeg stderr-jéből). Ha nem érhető el: 0."""
        import re
        import subprocess
        try:
            from superdl.ffmpeg import find_ffmpeg
            ff = find_ffmpeg()
        except Exception:
            ff = None
        if not ff:
            return 0
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            r = subprocess.run([ff, "-i", path], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, creationflags=flags, timeout=15)
            txt = (r.stderr or b"").decode("utf-8", "replace")
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", txt)
            if m:
                h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                return int((h * 3600 + mi * 60 + s) * 1000)
        except Exception:
            pass
        return 0

    def _effekt(self, nev):
        """Egy megnevezett játékhang (swish, érme, pörgetés…) lejátszása. A
        hullámformát a `hangok` modul szintetizálja (numpy), a beszédtől külön
        lejátszón szól."""
        if self._closing or not nev:
            return
        try:
            # 1) a modulba CSOMAGOLT hangfájl (pl. a Milliomos vagy a Szerencsekerék
            #    saját, jogtiszta hangjai) – közvetlenül, változatlanul lejátszva.
            csomagolt = self._hang_fajl(nev)
            if csomagolt:
                if self._tone_player is None:
                    from superdl.audioengine import Player
                    self._tone_player = Player()
                self._tone_player.play(csomagolt, "")
                return
            import os
            # 2) különben SAJÁT SZINTÉZIS (a többi játék hangjai + a még nem
            #    lecserélt Milliomos-hangok)
            import tempfile
            import uuid
            import wave
            import numpy as np
            from . import hangok
            x, fs = hangok.keszit(str(nev))
            if x is None or not len(x):
                return
            pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
            out = os.path.join(tempfile.gettempdir(),
                               f"superdl_sfx_{uuid.uuid4().hex[:8]}.wav")
            with wave.open(out, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(fs)
                w.writeframes(pcm.tobytes())
            if self._tone_player is None:
                from superdl.audioengine import Player
                self._tone_player = Player()
            self._tone_player.play(out, "")
        except Exception:
            pass

    def _enek(self, payload):
        """A gép ELÉNEKLI a dalt (a SAJÁT formáns-szintetizátorral). A payload:
        (sorok, gépkulcs). WAV-ba rendereljük, és a hang-lejátszón szólaltatjuk."""
        if self._closing:
            return
        try:
            sorok, gep = payload
        except Exception:
            return
        if not sorok:
            return
        try:
            import os
            import tempfile
            import uuid
            import wave
            import numpy as np
            from . import enek as EN
            y, fs = EN.enekel(sorok, gep)
            if y is None or not len(y):
                return
            pcm = (np.clip(y, -1, 1) * 32767).astype("<i2")
            out = os.path.join(tempfile.gettempdir(),
                               f"superdl_enek_{uuid.uuid4().hex[:8]}.wav")
            with wave.open(out, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(fs)
                w.writeframes(pcm.tobytes())
            if self._tone_player is None:
                from superdl.audioengine import Player
                self._tone_player = Player()
            self._tone_player.play(out, "")
        except Exception:
            pass

    def _var_bemenet(self, van):
        self._var = van
        self.bemenet.Enable(van)
        self.kuld_gomb.Enable(van)
        if van and not self._closing:
            self.bemenet.SetFocus()

    # ---- ábécé-megállítás (abcstop): a JÁTÉKOS dönti el a betűt --------

    def _mond_csak(self, szoveg):
        """Felolvasás átiratba írás NÉLKÜL (az ábécé-sorolás betűihez)."""
        if self._closing:
            return
        if self.hang_kapcs.GetValue():
            self._hang.mond(szoveg)
        else:
            self._beszel_rendszer(szoveg)

    def _abcstop_start(self, koz_ms):
        self._abc_betuk = list(_ABC)
        self._abc_idx = -1
        self._abc_koz = max(250, int(koz_ms) if koz_ms else 1000)
        self._abc_active = True
        self._var = False                 # ne dolgozzon fel Entert küldésként
        # a bevitelt NEM tiltjuk le (az fókuszt ugratna + nevet mondatna); a
        # leütéseket a pörgetés alatt az EVT_CHAR_HOOK nyeli el
        self.allj_gomb.Show()             # látszik, de NEM kap fókuszt
        try:
            self.Layout()
        except Exception:
            pass
        # SEMMI bemondás és SEMMI késleltetés indítás előtt (felhasználói kérés):
        # nem fókuszáljuk a gombot (különben a képernyőolvasó felolvasná a
        # nevét), és nincs kezdő-várakozás – a betűk AZONNAL indulnak. A
        # szóköz/Enter az EVT_CHAR_HOOK-on át állítja meg (a fókusz bárhol lehet
        # a párbeszéden belül).
        self._abc_tick()

    def _abc_tick(self):
        if not self._abc_active or self._closing:
            return
        self._abc_idx = (self._abc_idx + 1) % len(self._abc_betuk)
        self._mond_csak(self._abc_betuk[self._abc_idx])
        if self._abc_active and not self._closing:
            wx.CallLater(self._abc_koz, self._abc_tick)

    def _abcstop_stop(self):
        if not self._abc_active:
            return
        self._abc_active = False
        self.allj_gomb.Hide()
        try:
            self.Layout()
        except Exception:
            pass
        betu = ""
        if 0 <= self._abc_idx < len(self._abc_betuk):
            betu = self._abc_betuk[self._abc_idx]
        self._pump(betu)

    def _hang_kapcsol(self, e):
        self._hang.enabled = self.hang_kapcs.GetValue()
        if not self._hang.enabled:
            self._hang.nema()
        _retro_hang_ment(self._hang.enabled)   # a választás MEGŐRZÉSE

    # ---- billentyűk / zárás -------------------------------------------

    def _on_key(self, e):
        k = e.GetKeyCode()
        if self._abc_active:
            # pörgetés közben: szóköz/Enter = ÁLLJ; Escape = megszakítás
            if k in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                self._abcstop_stop()
                return
            if k == wx.WXK_ESCAPE:
                self._abc_active = False
                self.allj_gomb.Hide()
                self._hang.nema()
                self.Close()
                return
            return                     # egyéb billentyűt nyeljünk el pörgetés alatt
        if k == wx.WXK_ESCAPE:
            # először némít; ha már néma, bezár
            self._hang.nema()
            if not self._var:
                self.Close()
        elif k == wx.WXK_F1:
            self._sugo()
        else:
            e.Skip()

    def _sugo(self):
        szoveg = (
            f"{self.jatek.nev}\n\n{self.jatek.leiras}\n\n"
            "Írd be a válaszod a mezőbe, majd nyomj Entert. A retró hang "
            "beszéljen jelölőnégyzettel ki- és bekapcsolhatod a gépi hangot. "
            "Escape: elnémítás, majd kilépés. Újra gomb: új játék.")
        try:
            from superdl.helpdialog import show_help
            show_help(self, f"Súgó – {self.jatek.nev}", szoveg)
        except Exception:
            wx.MessageBox(szoveg, f"Súgó – {self.jatek.nev}",
                          wx.OK | wx.ICON_INFORMATION, self)

    def _on_close(self, e):
        self._closing = True
        try:
            self._hang.leallit()
        except Exception:
            pass
        try:
            if self._tone_player:
                self._tone_player.stop()
        except Exception:
            pass
        e.Skip()


class _KonzolCtx:
    """A játék felé mutatott „beszélő" felület (ugyanaz, mint a teszt Ctx-je)."""

    def mond(self, szoveg):
        return ("mond", str(szoveg))

    def tabla(self, szoveg):
        """A megfejtendő sor a felület aljára, külön mezőbe (és felolvasva)."""
        return ("tabla", str(szoveg))

    def kerdez(self, szoveg):
        return ("kerdez", str(szoveg))

    def vege(self, szoveg=""):
        return ("vege", str(szoveg))

    def hang(self, hangok):
        return ("hang", list(hangok))

    def effekt(self, nev):
        return ("effekt", str(nev))

    def effekt_var(self, nev):
        """Effekt lejátszása ÉS a végének kivárása (a hangok ne olvadjanak össze).
        A hossz mérését és a várakozást a felület intézi."""
        return ("effekt_var", str(nev))

    def szunet(self, ms):
        return ("szunet", int(ms))

    def abcstop(self, koz_ms=1000):
        """A gép SOROLJA az ábécét (koz_ms-enként egy betű), a játékos a
        szóközzel/Enterrel megállítja. A megállított betűt kapja vissza a játék –
        SOHA nem a gép dönti el, melyik betű."""
        return ("abcstop", int(koz_ms))

    def enek(self, sorok, gep="brailab"):
        return ("enek", (list(sorok), str(gep)))


# ---- a felület által hívott indítók -------------------------------------

# a saját, lapfüles ABLAKOS játékok – ezek külön wx-ablakot nyitnak
_ABLAK_JATEKOK = {"orszagvaros", "szerencsekerek", "uno"}


def indithato(kulcs: str) -> bool:
    return JR.van(kulcs) or kulcs in _ABLAK_JATEKOK


def indit_jatek(main, jatek, gep_getter):
    """Létrehozza és megjeleníti a játék ablakát (nem-modális). Az Ország-Város
    a saját, lapfüles indító/tanító ablakát kapja (Játszunk! + A játék
    tanítása); minden más a közös JatekKonzolt."""
    if jatek.kulcs == "orszagvaros":
        try:
            from .orszagvaroswin import OrszagVarosAblak
            ablak = OrszagVarosAblak(main, jatek, gep_getter)
            ablak.Show()
            return ablak
        except Exception:
            pass                          # ha bármi gond van, essen vissza a konzolra
    if jatek.kulcs == "szerencsekerek":
        try:
            from .szerencsekerek_online import SzerencseAblak
            ablak = SzerencseAblak(main, jatek, gep_getter)
            ablak.Show()
            return ablak
        except Exception:
            pass
    if jatek.kulcs == "uno":
        try:
            from .unowin import UnoAblak
            ablak = UnoAblak(main, jatek, gep_getter)
            ablak.Show()
            return ablak
        except Exception:
            pass                          # baj esetén essen vissza a konzolra
    kon = JatekKonzol(main, jatek, gep_getter)
    kon.Show()
    return kon
