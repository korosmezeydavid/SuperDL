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
        self._hang = None                 # HangHalozat, ha az élő hang be van kapcsolva
        self._host_timer = None           # hostként a cím ismételt hirdetése
        self._zene = None                 # Zenelejatszo, ha közös zene megy

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
        self._mi_beszed = hg.Append(wx.ID_ANY, "&Beszéd – élő hang be/ki\tF4",
                                    kind=wx.ITEM_CHECK)
        mi_hely = hg.Append(wx.ID_ANY, "&Hol ülj a térben…\tCtrl+H")
        hg.AppendSeparator()
        mi_nemit = hg.Append(wx.ID_ANY, "Admin: résztvevő &némítása vagy feloldása…")
        mi_kirug = hg.Append(wx.ID_ANY, "Admin: résztvevő &kirúgása…")
        hg.AppendSeparator()
        mi_zene = hg.Append(wx.ID_ANY, "Közös &zene betöltése…\tCtrl+Z")
        mi_zene_ki = hg.Append(wx.ID_ANY, "Közös zene &leállítása")
        self._mi_zene_eng = hg.Append(
            wx.ID_ANY, "Admin: a tagok is tölthetnek zenét", kind=wx.ITEM_CHECK)
        hg.AppendSeparator()
        # HANGERŐ (Dávid jelzése: „halkan lehet hallani a másikat")
        mi_mik = hg.Append(wx.ID_ANY, "&Mikrofon-erősítés…\tCtrl+M")
        mi_fo = hg.Append(wx.ID_ANY, "&Fő hangerő…\tCtrl+Shift+H")
        mi_egyeni = hg.Append(
            wx.ID_ANY, "Egy résztvevő han&gereje…\tCtrl+G")
        self._mi_monitor = hg.Append(
            wx.ID_ANY, "Halljam ma&gam (mikrofon-próba)\tF8", kind=wx.ITEM_CHECK)
        mi_szint = hg.Append(wx.ID_ANY, "Milyen a mikrofonom &szintje?\tF9")
        hg.AppendSeparator()
        mi_demo = hg.Append(wx.ID_ANY, "&Térhang bemutató (körbejáró hang)\tF6")
        mb.Append(hg, "&Hang")
        h = wx.Menu()
        mi_sugo = h.Append(wx.ID_ANY, "&Súgó\tF1")
        mb.Append(h, "&Súgó")
        self.SetMenuBar(mb)
        self.Bind(wx.EVT_MENU, lambda e: self._mikrofon_eros_allit(), mi_mik)
        self.Bind(wx.EVT_MENU, lambda e: self._fo_hangero_allit(), mi_fo)
        self.Bind(wx.EVT_MENU, lambda e: self._resztvevo_hangero(), mi_egyeni)
        self.Bind(wx.EVT_MENU, lambda e: self._monitor_valt(), self._mi_monitor)
        self.Bind(wx.EVT_MENU, lambda e: self._szint_mond(), mi_szint)
        self.Bind(wx.EVT_MENU, lambda e: self._terhang_bemutato(), mi_demo)
        self.Bind(wx.EVT_MENU, lambda e: self._hely_valaszt(), mi_hely)
        self.Bind(wx.EVT_MENU, lambda e: self._admin_nemit(), mi_nemit)
        self.Bind(wx.EVT_MENU, lambda e: self._admin_kirug(), mi_kirug)
        self.Bind(wx.EVT_MENU, lambda e: self._zene_betolt(), mi_zene)
        self.Bind(wx.EVT_MENU, lambda e: self._zene_leallit(), mi_zene_ki)
        self.Bind(wx.EVT_MENU, lambda e: self._zene_engedely_valt(), self._mi_zene_eng)
        self.Bind(wx.EVT_MENU, lambda e: self._beszed_valt(), self._mi_beszed)
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
        self._beszed_gomb = wx.ToggleButton(p, label="&Beszéd (élő hang)")
        self._beszed_gomb.SetName("Élő hang be- és kikapcsolása")
        self._beszed_gomb.Bind(wx.EVT_TOGGLEBUTTON, lambda e: self._beszed_valt())
        also.Add(self._beszed_gomb, 0, wx.RIGHT, 6)
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
        szoba.on_hely = lambda ki, pan: wx.CallAfter(self._on_hely, ki, pan)
        szoba.on_kirugva = lambda: wx.CallAfter(self._on_kirugva)
        szoba.on_nemitva = lambda be: wx.CallAfter(self._on_nemitva, be)
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
        if self._hang is not None:
            self._beszed_le()
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
        self._frissit_ulesek(nevek)

    def _on_hely(self, ki, pan):
        """Valaki áthelyezte magát a sztereó térben – frissítjük a keverést."""
        if self.szoba is not None:
            self._frissit_ulesek(self.szoba.tagok())

    def _frissit_ulesek(self, nevek):
        if self._hang is not None and self.szoba is not None:
            try:
                self._hang.set_resztvevok(nevek, self.szoba.helyek())
            except Exception:
                pass

    _HELYEK = [("Bal szél", -1.0), ("Balra", -0.5), ("Középen", 0.0),
               ("Jobbra", 0.5), ("Jobb szél", 1.0)]

    def _hely_valaszt(self):
        """A felhasználó megválasztja, HOL üljön a sztereó térben – mindenki
        gépén ide kerül a hangja. Öt diszkrét pozíció, akadálymentes választóval."""
        if not self.szoba:
            self._mond("Előbb lépj be egy szobába.")
            return
        cimkek = [c for c, _ in self._HELYEK]
        akt = self.szoba.sajat_pan()
        sel = min(range(len(self._HELYEK)),
                  key=lambda i: abs(self._HELYEK[i][1] - akt))
        dlg = wx.SingleChoiceDialog(
            self, "Hol ülj a sztereó térben? A többiek innen fognak hallani "
            "téged. Fejhallgatóban a legjobb.", "Hely a térben", cimkek)
        dlg.SetSelection(sel)
        if dlg.ShowModal() == wx.ID_OK:
            cimke, pan = self._HELYEK[dlg.GetSelection()]
            self.szoba.hirdet_hely(pan)
            self._frissit_ulesek(self.szoba.tagok())
            self.SetStatusText("A helyed a térben: %s" % cimke)
            self._mond("A helyed a térben: %s. A többiek innen hallanak." % cimke)
        dlg.Destroy()

    # --- admin (a szoba HÁZIGAZDÁJA szabályozhat) ---------------------
    def _admin_ok(self):
        if self._hang is None or not self._hang.is_host():
            self._mond("Admin-műveletek csak a szoba házigazdájánál érhetők el, "
                       "és csak ha az élő hang be van kapcsolva.")
            return False
        return True

    def _valassz_resztvevo(self, kerdes):
        nevek = [n for n in (self.szoba.tagok() if self.szoba else [])
                 if n != self.szoba.nev]
        if not nevek:
            self._mond("Rajtad kívül nincs más a szobában.")
            return None
        dlg = wx.SingleChoiceDialog(self, kerdes, "Résztvevő", nevek)
        nev = nevek[dlg.GetSelection()] if dlg.ShowModal() == wx.ID_OK else None
        dlg.Destroy()
        return nev

    def _admin_nemit(self):
        if not self._admin_ok():
            return
        nev = self._valassz_resztvevo("Kit némítasz vagy oldasz fel?")
        if not nev:
            return
        be = not self._hang.nemitott_e(nev)
        self._hang.nemit_tag(nev, be)
        self.szoba.nemit_jelzes(nev, be)
        self._mond(("%s némítva – őt most senki nem hallja." if be
                    else "%s némítása feloldva.") % nev)

    def _admin_kirug(self):
        if not self._admin_ok():
            return
        nev = self._valassz_resztvevo("Kit rúgsz ki a szobából?")
        if not nev:
            return
        if wx.MessageBox("Biztosan kirúgod: %s? A hangját azonnal kizárom, és "
                         "szólok neki, hogy kilépjen." % nev, "Kirúgás",
                         wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
            return
        self._hang.tilt_tag(nev)
        self.szoba.kirug(nev)
        self._mond("%s kirúgva a szobából." % nev)

    def _on_kirugva(self):
        self._mond("A házigazda kirúgott a szobából.")
        self._kilep_szoba()

    def _on_nemitva(self, be):
        self._mond("A házigazda némított – téged most nem hallanak."
                   if be else "A házigazda feloldotta a némításodat.")

    # --- közös zene ---------------------------------------------------
    def _zene_betolt(self):
        if self._hang is None:
            self._mond("Előbb kapcsold be az élő hangot (Beszéd), hogy legyen "
                       "kinek szólnia a közös zenének.")
            return
        if not self._hang.is_host() and not (
                self.szoba and self.szoba.zene_engedelyezett()):
            self._mond("Közös zenét csak a házigazda tölthet be. A házigazda a "
                       "menüből engedélyezheti a tagoknak is.")
            return
        with wx.FileDialog(
                self, "Közös zene kiválasztása (mindenki ezt fogja hallani)",
                wildcard=("Hang (*.mp3;*.wav;*.m4a;*.flac;*.ogg;*.opus)|"
                          "*.mp3;*.wav;*.m4a;*.flac;*.ogg;*.opus|Minden fájl|*.*"),
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            ut = dlg.GetPath()
        from .zenelejatszo import Zenelejatszo
        z = Zenelejatszo(
            on_kocka=lambda pcm: self._hang and self._hang.zene_kocka(pcm),
            on_vege=lambda: wx.CallAfter(self._zene_veget_ert))
        if not z.elerheto():
            self._mond("A közös zenéhez az ffmpeg kell, ami most nem érhető el.")
            return
        self._zene_leallit()               # ha már ment egy, azt előbb leállítjuk
        try:
            z.indit(ut)
        except Exception as ex:
            self._mond("A közös zene nem indult: %s" % ex)
            return
        self._zene = z
        self.SetStatusText("Közös zene megy: %s" % os.path.basename(ut))
        self._mond("Közös zene elindult – mindenki hallja a szobában. "
                   "Leállítás: Közös zene leállítása.")

    def _zene_leallit(self):
        if self._zene is not None:
            z = self._zene
            self._zene = None
            try:
                z.leallit()
            except Exception:
                pass
            self._mond("Közös zene leállítva.")

    def _zene_veget_ert(self):
        if self._zene is not None:
            self._zene = None
            self._mond("A közös zene véget ért.")

    def _zene_engedely_valt(self):
        if self.szoba is None:
            return
        if self._hang is None or not self._hang.is_host():
            self._mond("A közös zene engedélyét csak a házigazda állíthatja.")
            self._mi_zene_eng.Check(self.szoba.zene_engedelyezett())
            return
        be = self._mi_zene_eng.IsChecked()
        self.szoba.hirdet_zene_engedely(be)
        self._mond("Mostantól a tagok is tölthetnek közös zenét."
                   if be else "A tagok közös-zene betöltése kikapcsolva.")

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

    # ---- HANGERŐ ------------------------------------------------------
    #
    # Dávid jelzése (2026-09-01): „halkan lehet hallani a másikat". Három oka
    # volt, és a legfontosabb a keverőben ült (lásd terhang.py) – de a
    # szabályzók nélkül a javítás fele lenne csak meg: ha valakinek eleve halk
    # a mikrofonja, azt máshonnan nem lehet felhozni.

    _MIK_LEPES = 0.5            # egy lépés a mikrofon-erősítésben
    _HANGERO_LEPES = 0.1

    def _hang_beall_betolt(self):
        """A mentett hangerő-beállítások (mikrofon, fő hangerő, résztvevőnként)."""
        try:
            return dict(self.core.store.load("csevej_hangero", {}) or {})
        except Exception:
            return {}

    def _hang_beall_ment(self, adat: dict):
        try:
            self.core.store.save("csevej_hangero", adat)
        except Exception:
            pass

    def _hang_kell(self) -> bool:
        if self._hang is None:
            self._mond("Előbb kapcsold be az élő hangot: Beszéd, F4.")
            return False
        return True

    def _mikrofon_eros_allit(self):
        """A saját mikrofon erősítése. Ez a KÜLDÉSI oldal: ettől hallanak
        téged hangosabban a többiek."""
        if not self._hang_kell():
            return
        from .terhang import MIK_EROS_MIN, MIK_EROS_MAX
        akt = self._hang.mikrofon_eros()
        ertek = wx.GetNumberFromUser(
            "Mennyivel erősítsük a mikrofonodat?\n\n"
            "100 százalék az eredeti. Ha halkan hallanak, emeld. A program a "
            "csúcsokat lágyan visszafogja, tehát nem fog recsegni.\n\n"
            "Tipp: az F8 – Halljam magam – bekapcsolásával meg is hallgathatod "
            "magad, az F9 pedig megmondja, jó szinten vagy-e.",
            "Erősítés (százalék):", "Mikrofon-erősítés",
            int(round(akt * 100)), int(MIK_EROS_MIN * 100),
            int(MIK_EROS_MAX * 100), self)
        if ertek < 0:
            return
        uj = self._hang.set_mikrofon_eros(ertek / 100.0)
        b = self._hang_beall_betolt()
        b["mikrofon"] = uj
        self._hang_beall_ment(b)
        self._mond("Mikrofon-erősítés: %d százalék." % round(uj * 100))

    def _fo_hangero_allit(self):
        """A FŐ hangerő: mindenkire hat, akit hallasz."""
        if not self._hang_kell():
            return
        from .terhang import HANGERO_MAX
        akt = self._hang.fo_hangero()
        ertek = wx.GetNumberFromUser(
            "Milyen hangosan szóljon a többiek hangja?\n\n"
            "100 százalék az eredeti. Ha CSAK EGY valakit hallasz halkan, ne "
            "ezt emeld, hanem az ő hangerejét külön (Ctrl+G) – így a többiek "
            "nem lesznek fájdalmasan hangosak.",
            "Fő hangerő (százalék):", "Fő hangerő",
            int(round(akt * 100)), 0, int(HANGERO_MAX * 100), self)
        if ertek < 0:
            return
        uj = self._hang.set_fo_hangero(ertek / 100.0)
        b = self._hang_beall_betolt()
        b["fo"] = uj
        self._hang_beall_ment(b)
        self._mond("Fő hangerő: %d százalék." % round(uj * 100))

    def _resztvevo_hangero(self):
        """EGY résztvevő hangereje – a kérés magva. Névre mentve, tehát
        legközelebb is annyi lesz."""
        if not self._hang_kell():
            return
        nev = self._valassz_resztvevo("Kinek a hangerejét állítod?")
        if not nev:
            return
        from .terhang import HANGERO_MAX
        akt = self._hang.hangero(nev)
        ertek = wx.GetNumberFromUser(
            "Milyen hangosan szóljon %s?\n\n"
            "100 százalék az eredeti, 0 elnémítja. A beállítás megjegyződik, "
            "tehát legközelebb is ennyi lesz." % nev,
            "Hangerő (százalék):", "%s hangereje" % nev,
            int(round(akt * 100)), 0, int(HANGERO_MAX * 100), self)
        if ertek < 0:
            return
        uj = self._hang.set_hangero(nev, ertek / 100.0)
        b = self._hang_beall_betolt()
        tagok = dict(b.get("tagok", {}))
        tagok[nev] = uj
        b["tagok"] = tagok
        self._hang_beall_ment(b)
        self._mond("%s hangereje: %d százalék."
                   % (nev, round(uj * 100))
                   + (" Elnémítva." if uj == 0 else ""))

    def _monitor_valt(self):
        """„Halljam magam" – vakon ez az EGYETLEN mód arra, hogy tudd, mit
        hallanak a többiek. Szintmérőt nem lehet nézni."""
        if self._hang is None:
            self._mi_monitor.Check(False)
            self._mond("Előbb kapcsold be az élő hangot: Beszéd, F4.")
            return
        be = self._mi_monitor.IsChecked()
        self._hang.set_monitor(be)
        if be:
            self._mond("Halljam magam bekapcsolva: most a saját hangodat is "
                       "hallod, úgy, ahogy a többiek. FEJHALLGATÓ kell hozzá, "
                       "különben a hangszóró visszasípol.")
        else:
            self._mond("Halljam magam kikapcsolva.")

    def _szint_mond(self):
        """Kimondja, jó szinten van-e a mikrofon – és MIT tegyen a felhasználó."""
        if not self._hang_kell():
            return
        from .terhang import szint_tanacs
        cs = self._hang.mikrofon_csucs()
        self._mond(szint_tanacs(cs)
                   + " (Mikrofon-erősítés: %d százalék.)"
                   % round(self._hang.mikrofon_eros() * 100))

    def _hangero_visszaallit(self):
        """A mentett hangerő-beállítások visszatöltése az élő hangra."""
        if self._hang is None:
            return
        b = self._hang_beall_betolt()
        try:
            if "mikrofon" in b:
                self._hang.set_mikrofon_eros(float(b["mikrofon"]))
            if "fo" in b:
                self._hang.set_fo_hangero(float(b["fo"]))
            for nev, ertek in (b.get("tagok") or {}).items():
                self._hang.set_hangero(nev, float(ertek))
        except Exception:
            pass

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

    # ---- élő hang (helyi háló, host-modell) ---------------------------
    def _beszed_valt(self):
        if not self.szoba:
            self._beszed_sync(False)
            return
        if self._hang is not None:           # már megy → kikapcsolás
            self._beszed_le()
            return
        from .lanhang import HangHalozat
        h = HangHalozat(self.szoba.nev)
        if not h.elerheto():
            wx.MessageBox(
                "Az élő hanghoz mikrofon és hangkimenet kell. A hangeszköz nem "
                "érhető el ezen a gépen.", "Élő hang",
                wx.OK | wx.ICON_WARNING, self)
            self._beszed_sync(False)
            return
        hh = self.szoba.hang_host()
        tagok = self.szoba.tagok()
        try:
            if hh and hh.get("ki") in tagok and hh.get("ki") != self.szoba.nev:
                # KLIENS: a host jelöltjeire csatlakozunk, és hirdetjük a
                # sajátjainkat, hogy a host is tudjon felénk hole-punchingolni
                cand = h.kliens_indit(hh["cimek"])
                self.szoba.hirdet_tag(cand)
                self._mond("Élő hang: csatlakozás a házigazdához (%s). "
                           "Fejhallgatóban a legjobb!" % hh["ki"])
            else:
                # HOST: bejelentjük a jelöltjeinket (LAN + publikus/STUN), és a
                # már jelentkezett kliensek jelöltjeire elkezdünk punch-olni
                cand = h.host_indit()
                self._host_cim = cand
                self.szoba.hirdet_host(cand)
                for ki, ccand in self.szoba.hang_tagok().items():
                    if ki != self.szoba.nev:
                        h.punch_hozzaad(ccand)
                self._host_timer = wx.Timer(self)
                self.Bind(wx.EVT_TIMER, self._host_ujrahirdet, self._host_timer)
                self._host_timer.Start(5000)
                self._mond("Élő hang elindult – te vagy a házigazda. A többiek "
                           "a Beszéd gombbal csatlakoznak. Fejhallgatóban a legjobb!")
        except Exception as ex:
            wx.MessageBox(
                "Az élő hang nem indult: %s\n\nHa a Windows tűzfal rákérdez, "
                "engedélyezd a SuperDL-t a HELYI hálón. A résztvevőknek ugyanazon "
                "a WiFi-n/hálón kell lenniük." % ex,
                "Élő hang", wx.OK | wx.ICON_ERROR, self)
            try:
                h.leallit()
            except Exception:
                pass
            self._beszed_sync(False)
            return
        self._hang = h
        # hostként: az élőben belépő új kliensek jelöltjeire is punch-olunk
        self.szoba.on_hang_tag = lambda ki, cc: wx.CallAfter(self._on_hang_tag, ki, cc)
        self._hang.set_resztvevok(tagok, self.szoba.helyek())
        # a korábban beállított hangerők visszatöltése – enélkül minden
        # bekapcsoláskor elölről kellene beállítani, ami vakon sok lépés
        self._hangero_visszaallit()
        self._beszed_sync(True)

    def _on_hang_tag(self, ki, cimek):
        if self._hang is not None and getattr(self._hang, "_host", False) \
                and self.szoba is not None and ki != self.szoba.nev:
            self._hang.punch_hozzaad(cimek)

    def _host_ujrahirdet(self, e):
        if self._hang is not None and self.szoba is not None \
                and getattr(self, "_host_cim", None):
            self.szoba.hirdet_host(self._host_cim)

    def _beszed_le(self):
        self._zene_leallit()               # a hang nélkül nincs kinek szólni a zene
        if self._host_timer is not None:
            try:
                self._host_timer.Stop()
            except Exception:
                pass
            self._host_timer = None
        if self._hang is not None:
            try:
                self._hang.leallit()
            except Exception:
                pass
            self._hang = None
        try:
            self._mi_monitor.Check(False)   # a mikrofon-próba is véget ér
        except Exception:
            pass
        self._mond("Élő hang kikapcsolva.")
        self._beszed_sync(False)

    def _beszed_sync(self, be):
        try:
            self._beszed_gomb.SetValue(bool(be))
        except Exception:
            pass
        try:
            self._mi_beszed.Check(bool(be))
        except Exception:
            pass

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
        try:
            self._zene_leallit()
        except Exception:
            pass
        if self._hang is not None:
            try:
                self._beszed_le()
            except Exception:
                pass
        if self.szoba:
            try:
                self.szoba.kilep()
            except Exception:
                pass
            self.szoba = None
        e.Skip()
