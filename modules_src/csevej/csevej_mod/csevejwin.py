# -*- coding: utf-8 -*-
"""Csevejcenter – akadálymentes wx-felület (lobbi + szoba).

Egyablakos: előbb a LOBBI (név megadása, új szoba nyitása vagy csatlakozás
kóddal), belépés után a SZOBA (beszélgetés-napló, beviteli mező Enterrel,
résztvevő-lista, kilépés). Az érkező üzeneteket és a be-/kilépéseket a
képernyőolvasó azonnal felolvassa (core.voice), minden vezérlőnek olvasható
neve van. A hálózati munka háttérszálon fut, a UI-t `wx.CallAfter` frissíti.
"""
import os

import wx

from .csevejcenter import Csevejszoba, szobakod

_HANG_DIR = os.path.join(os.path.dirname(__file__), "hang")


class _Hangok:
    """Rövid értesítő-hangok (WAV) lejátszása. Elsőként a natív, könnyű
    `wx.adv.Sound` (nincs ffmpeg-folyamat); ha az nem elérhető, a Core
    `audioengine.Player`-e a tartalék. Külön példány az érkező és a küldött
    hangnak, hogy ne vágják el egymást; a Sound-referenciákat megtartjuk (az
    aszinkron lejátszás alatt élniük kell)."""

    def __init__(self):
        self._sounds = {}
        self._players = {}

    def _ut(self, nev):
        p = os.path.join(_HANG_DIR, nev + ".wav")
        return p if os.path.isfile(p) else ""

    def jatszd(self, nev):
        ut = self._ut(nev)
        if not ut:
            return
        try:
            import wx.adv
            snd = self._sounds.get(nev)
            if snd is None:
                snd = wx.adv.Sound(ut)
                self._sounds[nev] = snd
            if snd.IsOk():
                snd.Play(wx.adv.SOUND_ASYNC)
                return
        except Exception:
            pass
        # tartalék: a Core audioengine-je (ffmpeg + sounddevice)
        try:
            from superdl.audioengine import Player
            pl = self._players.get(nev)
            if pl is None:
                pl = Player()
                self._players[nev] = pl
            pl.play(ut, "")
        except Exception:
            pass


class CsevejFrame(wx.Frame):
    def __init__(self, parent, core):
        super().__init__(parent, title="Csevejcenter", size=(720, 560))
        self.core = core
        self.szoba = None                 # aktív Csevejszoba vagy None
        self._kod = ""
        self._hangok = _Hangok()          # incoming / outgoing értesítő-hangok

        self._menusav()
        root = wx.Panel(self)
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        root.SetSizer(self._sizer)
        self._root = root

        self._lobbi = self._epit_lobbi(root)
        self._szobalap = self._epit_szoba(root)
        self._sizer.Add(self._lobbi, 1, wx.EXPAND | wx.ALL, 10)
        self._sizer.Add(self._szobalap, 1, wx.EXPAND | wx.ALL, 10)
        self._szobalap.Hide()

        self.CreateStatusBar()
        self.SetStatusText("Adj meg egy nevet, majd nyiss új szobát vagy "
                           "csatlakozz egy kóddal.")
        self._nev_mezo.SetValue(self._mentett_nev())
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self._segitseg()
        wx.CallAfter(self._nev_mezo.SetFocus)

    # ================================================================
    #  Menü + súgó
    # ================================================================
    def _menusav(self):
        mb = wx.MenuBar()
        m = wx.Menu()
        self._mi_uj = m.Append(wx.ID_ANY, "&Új szoba\tCtrl+N")
        self._mi_csat = m.Append(wx.ID_ANY, "&Csatlakozás kóddal\tCtrl+J")
        m.AppendSeparator()
        self._mi_kod = m.Append(wx.ID_ANY, "Szoba&kód másolása\tCtrl+C")
        self._mi_kik = m.Append(wx.ID_ANY, "Kik vannak &itt?\tCtrl+R")
        self._mi_ki = m.Append(wx.ID_ANY, "Kilépés a szo&bából")
        m.AppendSeparator()
        mi_bezar = m.Append(wx.ID_ANY, "Ablak be&zárása\tCtrl+W")
        mb.Append(m, "&Szoba")
        hg = wx.Menu()
        mi_demo = hg.Append(wx.ID_ANY, "&Térhang bemutató (körbejáró hang)\tF6")
        mb.Append(hg, "&Hang")
        h = wx.Menu()
        mi_sugo = h.Append(wx.ID_ANY, "&Súgó\tF1")
        mb.Append(h, "&Súgó")
        self.SetMenuBar(mb)
        self.Bind(wx.EVT_MENU, lambda e: self._terhang_bemutato(), mi_demo)
        self.Bind(wx.EVT_MENU, lambda e: self._uj_szoba(), self._mi_uj)
        self.Bind(wx.EVT_MENU, lambda e: self._fokusz_kod(), self._mi_csat)
        self.Bind(wx.EVT_MENU, lambda e: self._kod_masolas(), self._mi_kod)
        self.Bind(wx.EVT_MENU, lambda e: self._kik_vannak(), self._mi_kik)
        self.Bind(wx.EVT_MENU, lambda e: self._kilep_szoba(), self._mi_ki)
        self.Bind(wx.EVT_MENU, lambda e: self.Close(), mi_bezar)
        self.Bind(wx.EVT_MENU, lambda e: self._sugo_mutat(), mi_sugo)

    def _segitseg(self):
        try:
            from superdl.uihelp import bind_help
            bind_help(self, "Súgó – Csevejcenter", self._SUGO)
        except Exception:
            self.Bind(wx.EVT_CHAR_HOOK, self._f1)

    _SUGO = (
        "CSEVEJCENTER\n\n"
        "Valós idejű, akadálymentes csevegő – gépek között, szoba-kóddal, "
        "szerver és beállítás nélkül. Csak internet kell.\n\n"
        "• Írd be a neved, majd Ctrl+N: ÚJ szoba. Kapsz egy rövid kódot "
        "(pl. GK7QP) – ezt oszd meg azzal, akivel beszélgetni szeretnél.\n"
        "• Ctrl+J: CSATLAKOZÁS – írd be a kapott kódot.\n"
        "• A szobában: gépelj a beviteli mezőbe, Enter a küldés.\n"
        "• Ctrl+C: a szobakód a vágólapra (könnyű megosztani).\n"
        "• Ctrl+R: felolvassa, kik vannak most a szobában.\n"
        "• Az érkező üzeneteket és a be-/kilépéseket a program felolvassa.\n\n"
        "Semmit nem tárolunk – az üzenetek átmennek a szobán és eltűnnek. "
        "Hamarosan térbeli, sztereó hangos konferencia is épül rá.")

    def _f1(self, e):
        if e.GetKeyCode() == wx.WXK_F1:
            self._sugo_mutat()
        else:
            e.Skip()

    def _sugo_mutat(self):
        wx.MessageBox(self._SUGO, "Súgó – Csevejcenter", wx.OK | wx.ICON_INFORMATION, self)

    # ================================================================
    #  Lobbi
    # ================================================================
    def _epit_lobbi(self, szulo):
        p = wx.Panel(szulo)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="Üdv a Csevejcenterben! Írj be egy nevet, "
              "majd nyiss új szobát, vagy csatlakozz egy kóddal."),
              0, wx.ALL, 6)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        sor.Add(wx.StaticText(p, label="A te &neved:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._nev_mezo = wx.TextCtrl(p)
        self._nev_mezo.SetName("A te neved")
        sor.Add(self._nev_mezo, 1)
        v.Add(sor, 0, wx.EXPAND | wx.ALL, 6)

        uj = wx.Button(p, label="&Új szoba nyitása")
        uj.Bind(wx.EVT_BUTTON, lambda e: self._uj_szoba())
        v.Add(uj, 0, wx.ALL, 6)

        sor2 = wx.BoxSizer(wx.HORIZONTAL)
        sor2.Add(wx.StaticText(p, label="Csatlakozás &kóddal:"), 0,
                 wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._kod_mezo = wx.TextCtrl(p, style=wx.TE_PROCESS_ENTER)
        self._kod_mezo.SetName("Szoba kódja")
        self._kod_mezo.Bind(wx.EVT_TEXT_ENTER, lambda e: self._csatlakozas_gomb())
        sor2.Add(self._kod_mezo, 1, wx.RIGHT, 6)
        csat = wx.Button(p, label="&Csatlakozás")
        csat.Bind(wx.EVT_BUTTON, lambda e: self._csatlakozas_gomb())
        sor2.Add(csat, 0)
        v.Add(sor2, 0, wx.EXPAND | wx.ALL, 6)

        p.SetSizer(v)
        return p

    def _mentett_nev(self) -> str:
        try:
            return str(self.core.store.load("nev", "") or "")
        except Exception:
            return ""

    def _nev_ment(self, nev):
        try:
            self.core.store.save("nev", nev)
        except Exception:
            pass

    def _nev_ellenoriz(self) -> str:
        nev = self._nev_mezo.GetValue().strip()
        if not nev:
            wx.MessageBox("Előbb írj be egy nevet.", "Csevejcenter",
                          wx.OK | wx.ICON_INFORMATION, self)
            self._nev_mezo.SetFocus()
            return ""
        return nev

    def _uj_szoba(self):
        if self.szoba:
            self._fokusz_bevitel()
            return
        nev = self._nev_ellenoriz()
        if not nev:
            return
        self._csatlakozas(nev, szobakod())

    def _fokusz_kod(self):
        if not self.szoba:
            self._kod_mezo.SetFocus()

    def _csatlakozas_gomb(self):
        if self.szoba:
            return
        nev = self._nev_ellenoriz()
        if not nev:
            return
        kod = self._kod_mezo.GetValue().strip().upper()
        if not kod:
            wx.MessageBox("Írd be a szoba kódját.", "Csevejcenter",
                          wx.OK | wx.ICON_INFORMATION, self)
            self._kod_mezo.SetFocus()
            return
        self._csatlakozas(nev, kod)

    # ================================================================
    #  Szoba
    # ================================================================
    def _epit_szoba(self, szulo):
        p = wx.Panel(szulo)
        v = wx.BoxSizer(wx.VERTICAL)

        self._fejlec = wx.StaticText(p, label="")
        v.Add(self._fejlec, 0, wx.ALL, 6)

        kozep = wx.BoxSizer(wx.HORIZONTAL)
        # beszélgetés-napló
        bal = wx.BoxSizer(wx.VERTICAL)
        bal.Add(wx.StaticText(p, label="&Beszélgetés:"), 0, wx.BOTTOM, 2)
        self._naplo = wx.TextCtrl(
            p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self._naplo.SetName("Beszélgetés, csak olvasható")
        bal.Add(self._naplo, 1, wx.EXPAND)
        kozep.Add(bal, 3, wx.EXPAND | wx.RIGHT, 8)
        # résztvevők
        jobb = wx.BoxSizer(wx.VERTICAL)
        jobb.Add(wx.StaticText(p, label="&Résztvevők:"), 0, wx.BOTTOM, 2)
        self._taglista = wx.ListBox(p)
        self._taglista.SetName("Résztvevők a szobában")
        jobb.Add(self._taglista, 1, wx.EXPAND)
        kozep.Add(jobb, 1, wx.EXPAND)
        v.Add(kozep, 1, wx.EXPAND | wx.ALL, 6)

        # beviteli sor
        also = wx.BoxSizer(wx.HORIZONTAL)
        also.Add(wx.StaticText(p, label="Ü&zenet:"), 0,
                 wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._bevitel = wx.TextCtrl(p, style=wx.TE_PROCESS_ENTER)
        self._bevitel.SetName("Írj üzenetet, Enter a küldés")
        self._bevitel.Bind(wx.EVT_TEXT_ENTER, lambda e: self._kuld())
        also.Add(self._bevitel, 1, wx.RIGHT, 6)
        kuld = wx.Button(p, label="&Küldés")
        kuld.Bind(wx.EVT_BUTTON, lambda e: self._kuld())
        also.Add(kuld, 0, wx.RIGHT, 6)
        ki = wx.Button(p, label="Ki&lépés")
        ki.Bind(wx.EVT_BUTTON, lambda e: self._kilep_szoba())
        also.Add(ki, 0)
        v.Add(also, 0, wx.EXPAND | wx.ALL, 6)

        p.SetSizer(v)
        return p

    def _csatlakozas(self, nev, kod):
        self._nev_ment(nev)
        try:
            szoba = Csevejszoba(kod, nev)
        except Exception as ex:
            wx.MessageBox("Nem sikerült létrehozni a szobát: %s" % ex,
                          "Csevejcenter", wx.OK | wx.ICON_ERROR, self)
            return
        if not szoba.elerheto():
            wx.MessageBox(
                "A csevegéshez internet és egy Ably-kulcs kell. A kiadott "
                "SuperDL-ben ez be van építve; fejlesztői futtatásnál tedd a "
                "kulcsot a ~/.superdl/ably_key.txt fájlba.",
                "Csevejcenter", wx.OK | wx.ICON_WARNING, self)
            return
        # callbackek – MIND wx.CallAfter-rel a UI-szálra
        szoba.on_uzenet = lambda n, sz, s: wx.CallAfter(self._on_uzenet, n, sz, s)
        szoba.on_belepett = lambda n: wx.CallAfter(self._on_belepett, n)
        szoba.on_kilepett = lambda n: wx.CallAfter(self._on_kilepett, n)
        szoba.on_tagok = lambda lst: wx.CallAfter(self._on_tagok, lst)
        self.szoba = szoba
        self._kod = kod
        # felület átváltása a szobára
        self._naplo.SetValue("")
        self._taglista.Set([])
        self._fejlec.SetLabel("Szoba: %s  –  te: %s" % (kod, nev))
        self._lobbi.Hide()
        self._szobalap.Show()
        self._root.Layout()
        self.SetStatusText("Szobában: %s. Ctrl+C: kód másolása, Ctrl+R: kik "
                           "vannak itt." % kod)
        self._mond("Beléptél a(z) %s szobába. A kódot Ctrl+C-vel másolhatod." % kod)
        szoba.belep()
        wx.CallAfter(self._bevitel.SetFocus)

    def _kuld(self):
        if not self.szoba:
            return
        szoveg = self._bevitel.GetValue().strip()
        if not szoveg:
            return
        try:
            self.szoba.kuld(szoveg)
        except Exception as ex:
            self._naplo_sor("(nem sikerült elküldeni: %s)" % ex)
            return
        self._bevitel.SetValue("")
        self._bevitel.SetFocus()

    def _kilep_szoba(self):
        if not self.szoba:
            return
        try:
            self.szoba.kilep()
        except Exception:
            pass
        self.szoba = None
        self._kod = ""
        self._szobalap.Hide()
        self._lobbi.Show()
        self._root.Layout()
        self.SetStatusText("Kiléptél a szobából.")
        self._mond("Kiléptél a szobából.")
        wx.CallAfter(self._nev_mezo.SetFocus)

    # --- eseménykezelők (UI-szálon) ---
    def _on_uzenet(self, nev, szoveg, sajat):
        cimke = "Én" if sajat else nev
        self._naplo_sor("%s: %s" % (cimke, szoveg))
        # értesítő-hang: saját küldés → outgoing, érkező üzenet → incoming
        self._hangok.jatszd("outgoing" if sajat else "incoming")
        if not sajat:
            self._mond("%s: %s" % (nev, szoveg))

    def _on_belepett(self, nev):
        self._naplo_sor("* %s belépett a szobába *" % nev)
        self._mond("%s belépett a szobába." % nev)

    def _on_kilepett(self, nev):
        self._naplo_sor("* %s kilépett *" % nev)
        self._mond("%s kilépett." % nev)

    def _on_tagok(self, nevek):
        self._taglista.Set(nevek)

    def _naplo_sor(self, szoveg):
        if self._naplo.GetValue():
            self._naplo.AppendText("\n")
        self._naplo.AppendText(szoveg)

    # --- műveletek ---
    def _kod_masolas(self):
        if not self._kod:
            return
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(self._kod))
            wx.TheClipboard.Close()
            self.SetStatusText("Szobakód a vágólapon: %s" % self._kod)
            self._mond("A szobakód a vágólapon: %s" % " ".join(self._kod))

    def _kik_vannak(self):
        if not self.szoba:
            return
        nevek = self.szoba.tagok()
        if nevek:
            self._mond("A szobában: " + ", ".join(nevek))
        else:
            self._mond("Rajtad kívül még senki nincs a szobában.")

    def _terhang_bemutato(self):
        """A térbeli hang ÉLMÉNY-bemutatója (hálózat nélkül): egy hang körbejár
        a fejed körül – ez mutatja, hogy a konferenciában mindenki onnan szól
        majd, ahol „ül”. Fejhallgatóban a legjobb!"""
        self._mond("Térhang bemutató: egy hang most körbejár a fejed körül. "
                   "Fejhallgatóban hallod a legjobban.")
        try:
            import sounddevice as sd
            from .terhang import bemutato_jel, FS
            sd.play(bemutato_jel(6.0), FS)
        except Exception as ex:
            wx.MessageBox("A hang-bemutató nem indult: %s\n\nEllenőrizd, hogy "
                          "van-e hangkimenet (fejhallgató/hangszóró)." % ex,
                          "Térhang bemutató", wx.OK | wx.ICON_INFORMATION, self)

    def _fokusz_bevitel(self):
        if self.szoba:
            self._bevitel.SetFocus()

    def _mond(self, szoveg):
        v = getattr(self.core, "voice", None)
        if v:
            try:
                v.speak(szoveg)
            except Exception:
                pass

    def _on_close(self, e):
        if self.szoba:
            try:
                self.szoba.kilep()
            except Exception:
                pass
            self.szoba = None
        e.Skip()
