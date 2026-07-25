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
from . import katalogus
from . import jatekok as JR


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
        self.hang_kapcs.SetValue(bool(self.jatek.retro))
        self.hang_kapcs.Bind(wx.EVT_CHECKBOX, self._hang_kapcsol)
        sor.Add(self.hang_kapcs, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        if not self.jatek.retro:
            # a Saját játékok NEM a retró géphangon szólnak, hanem normál
            # rendszerhangon – a retró kapcsoló itt nem értelmes
            self.hang_kapcs.Hide()
        b_ki = wx.Button(self, label="&Kilépés a játékból")
        b_ki.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        sor.Add(b_ki, 0)
        v.Add(sor, 0, wx.ALL, 8)
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
            if typ == "hang":
                self._hang_tone(payload)
                continue
            if typ == "effekt":
                self._effekt(payload)
                continue
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
        self._var_bemenet(False)
        self._pump(szoveg)

    def _veget_er(self):
        self._gen = None
        self._var_bemenet(False)
        self._ki("")
        self._ki("A játéknak vége. Új játékhoz: Újra gomb. Kilépés: Escape.")

    # ---- kimenet / bemenet-állapot ------------------------------------

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

    def _effekt(self, nev):
        """Egy megnevezett játékhang (swish, érme, pörgetés…) lejátszása. A
        hullámformát a `hangok` modul szintetizálja (numpy), a beszédtől külön
        lejátszón szól."""
        if self._closing or not nev:
            return
        try:
            import os
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

    def _var_bemenet(self, van):
        self._var = van
        self.bemenet.Enable(van)
        self.kuld_gomb.Enable(van)
        if van and not self._closing:
            self.bemenet.SetFocus()

    def _hang_kapcsol(self, e):
        self._hang.enabled = self.hang_kapcs.GetValue()
        if not self._hang.enabled:
            self._hang.nema()

    # ---- billentyűk / zárás -------------------------------------------

    def _on_key(self, e):
        k = e.GetKeyCode()
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

    def kerdez(self, szoveg):
        return ("kerdez", str(szoveg))

    def vege(self, szoveg=""):
        return ("vege", str(szoveg))

    def hang(self, hangok):
        return ("hang", list(hangok))

    def effekt(self, nev):
        return ("effekt", str(nev))


# ---- a felület által hívott indítók -------------------------------------

def indithato(kulcs: str) -> bool:
    return JR.van(kulcs)


def indit_jatek(main, jatek, gep_getter):
    """Létrehozza és megjeleníti a játékkonzolt (nem-modális)."""
    kon = JatekKonzol(main, jatek, gep_getter)
    kon.Show()
    return kon
