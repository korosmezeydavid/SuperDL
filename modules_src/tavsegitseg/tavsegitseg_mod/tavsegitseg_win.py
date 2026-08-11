# -*- coding: utf-8 -*-
"""Távsegítség – a FELÜLET (akadálymentes ablak).

Két szerep: „Segítséget kérek" (téged irányítanak) és „Segítek" (te irányítasz).
A segített szobát nyit (kap egy kódot), a segítő a kóddal csatlakozik. Amint a
kapcsolat él, a segítő HALLJA a segített gépét (benne a képernyőolvasót). Az
IRÁNYÍTÁST a segített KÜLÖN, beleegyezés után engedélyezi; pánik (Ctrl+Alt+Pause
rendszer-hotkey vagy gomb) bármikor azonnal bontja. Minden lépés felolvasva.
"""
import ctypes
import threading
import time

import wx

from . import szovegek as SZ
from .kapcsolat import Kapcsolat
from .session import Munkamenet
from .elkapas import Elkapo
from .hangfelvetel import HangFelvevo
from .hanglejatszo import HangLejatszo


class TavsegitsegWin(wx.Frame):
    def __init__(self, parent, core):
        super().__init__(parent, title="Távsegítség",
                         size=(720, 560),
                         style=wx.DEFAULT_FRAME_STYLE)
        self.core = core
        self._closing = False
        self._szerep = None
        self._kapcsolat = None
        self._munkamenet = None
        self._felvevo = None
        self._lejatszo = None
        self._elkapo = None
        self._panik_fut = False
        self._emlekezteto_fut = False
        self._build()
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._char_hook)
        wx.CallAfter(self._start_ellenoriz)

    # ------------------------------------------------------------ felület
    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label=(
            "Távsegítség – egy megbízható ember távolról segíthet a gépeden, "
            "vagy te segíthetsz valakinek. Csak internet kell. F1: súgó.")),
            0, wx.ALL, 8)

        # szerep
        self._szerep_valaszto = wx.RadioBox(
            p, label="Mit szeretnél?", choices=[
                "Segítséget kérek (engem irányítanak)",
                "Segítek valakinek (én irányítok)"],
            style=wx.RA_SPECIFY_ROWS)
        self._szerep_valaszto.Bind(wx.EVT_RADIOBOX, self._szerep_valt)
        v.Add(self._szerep_valaszto, 0, wx.EXPAND | wx.ALL, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        sor.Add(wx.StaticText(p, label="A &neved:"),
                0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._nev = wx.TextCtrl(p, value=self._alap_nev())
        self._nev.SetName("A neved")
        sor.Add(self._nev, 1)
        v.Add(sor, 0, wx.EXPAND | wx.ALL, 8)

        # lobbi (a szerep szerint)
        lob = wx.BoxSizer(wx.HORIZONTAL)
        self.g_szoba = wx.Button(p, label="Szoba &nyitása (kód kérése)")
        self.g_szoba.Bind(wx.EVT_BUTTON, self._uj_szoba)
        lob.Add(self.g_szoba, 0, wx.RIGHT, 6)
        lob.Add(wx.StaticText(p, label="&kód:"),
                0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.kod_mezo = wx.TextCtrl(p, size=(90, -1))
        self.kod_mezo.SetName("Szobakód")
        lob.Add(self.kod_mezo, 0, wx.RIGHT, 4)
        self.g_masol = wx.Button(p, label="Kód &másolása")
        self.g_masol.Bind(wx.EVT_BUTTON, self._kod_masol)
        lob.Add(self.g_masol, 0, wx.RIGHT, 6)
        self.g_csat = wx.Button(p, label="&Csatlakozás")
        self.g_csat.Bind(wx.EVT_BUTTON, self._csatlakozas)
        lob.Add(self.g_csat, 0)
        v.Add(lob, 0, wx.ALL, 8)

        # állapot + irányítás-vezérlés
        self._allapot = wx.TextCtrl(p, style=wx.TE_READONLY)
        self._allapot.SetName("Állapot")
        v.Add(self._allapot, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

        akc = wx.BoxSizer(wx.HORIZONTAL)
        self.g_engedely = wx.Button(p, label="Irányítás &engedélyezése")
        self.g_engedely.Bind(wx.EVT_BUTTON, self._iranyitas_engedelyez)
        self.g_engedely.Disable()
        akc.Add(self.g_engedely, 0, wx.RIGHT, 6)
        self.g_panik = wx.Button(p, label="Vezérlés AZONNALI &leállítása (pánik)")
        self.g_panik.Bind(wx.EVT_BUTTON, lambda e: self._panik("gomb"))
        self.g_panik.Disable()
        akc.Add(self.g_panik, 0)
        v.Add(akc, 0, wx.ALL, 8)

        # billentyű-elkapó mező (a SEGÍTŐ ebbe fókuszálva ad billentyűt a másiknak)
        self._elkapo_cimke = wx.StaticText(p, label=(
            "Billentyű-terület: ha te irányítasz, ide fókuszálva a billentyűid a "
            "MÁSIK gépre mennek (a képernyőolvasó-parancsok is)."))
        v.Add(self._elkapo_cimke, 0, wx.LEFT | wx.TOP, 8)
        self._elkapo_mezo = wx.Window(p, size=(-1, 28),
                                      style=wx.WANTS_CHARS | wx.BORDER_SIMPLE)
        self._elkapo_mezo.SetName("Billentyű-elkapó terület")
        v.Add(self._elkapo_mezo, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        v.Add(wx.StaticText(p, label="&Napló:"), 0, wx.LEFT, 8)
        self._naplo = wx.TextCtrl(
            p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 150))
        self._naplo.SetName("Napló, csak olvasható")
        v.Add(self._naplo, 1, wx.EXPAND | wx.ALL, 8)

        p.SetSizer(v)
        self._panel = p
        self._szerep_valt(None)

    def _alap_nev(self):
        try:
            return (self.core.store.load("nev", "") or "").strip() or "Névtelen"
        except Exception:
            return "Névtelen"

    def _start_ellenoriz(self):
        from . import netroom
        if not netroom.ably_kulcs():
            self._mond("A távsegítség ebben a verzióban még nem elérhető (nincs "
                       "online kulcs).")

    def _szerep_valt(self, e):
        seg = (self._szerep_valaszto.GetSelection() == 0)   # segítséget kér
        # segített: szoba nyitása; segítő: kód + csatlakozás
        self.g_szoba.Show(seg)
        self.g_masol.Show(seg)
        self.kod_mezo.Show(not seg)
        self.g_csat.Show(not seg)
        self._panel.Layout()

    # ------------------------------------------------------------ lobbi
    def _uj_szoba(self, e):
        if self._kapcsolat:
            return
        self._szerep = "segitett"
        nev = (self._nev.GetValue() or "Névtelen").strip()
        self._kapcsolat = Kapcsolat(nev)
        self._kapcsolat.figyeld_kesz(lambda: wx.CallAfter(self._kapcsolat_kesz))
        kod = self._kapcsolat.uj_szoba()
        if not kod:
            self._mond("Nem sikerült szobát nyitni (nincs online kulcs).")
            self._kapcsolat = None
            return
        self._munkamenet = Munkamenet(
            self._kapcsolat, "segitett", nev,
            on_allapot=lambda k, a: wx.CallAfter(self._on_allapot, k, a))
        self.kod_mezo.SetValue(kod)
        self.kod_mezo.Show(True)
        self.g_szoba.Disable()
        self._szerep_valaszto.Disable()
        self._panik_figyelo_indit()
        self._panel.Layout()
        self._mond("Szoba nyitva! A kódod: %s (betűnként: %s). Mondd be vagy "
                   "küldd el a SEGÍTŐDNEK, akiben megbízol. Amint csatlakozik, "
                   "hallani fogja a géped." % (kod, " ".join(kod)))

    def _csatlakozas(self, e):
        if self._kapcsolat:
            return
        kod = (self.kod_mezo.GetValue() or "").strip().upper()
        if not kod:
            self._mond("Írd be a kódot, amit a segítségre szorulótól kaptál.")
            return
        # az IRÁNYÍTÓ felelősség-figyelmeztetése (leokézós)
        if not self._beleegyezes("Segítek – felelősség", SZ.BELEEGYEZO_IRANYITO):
            return
        self._szerep = "iranyito"
        nev = (self._nev.GetValue() or "Névtelen").strip()
        self._kapcsolat = Kapcsolat(nev)
        self._kapcsolat.figyeld_kesz(lambda: wx.CallAfter(self._kapcsolat_kesz))
        if not self._kapcsolat.csatlakozas(kod):
            self._mond("Nem sikerült csatlakozni (nincs online kulcs).")
            self._kapcsolat = None
            return
        self._munkamenet = Munkamenet(
            self._kapcsolat, "iranyito", nev,
            on_allapot=lambda k, a: wx.CallAfter(self._on_allapot, k, a))
        self._elkapo = Elkapo(self._elkapo_mezo, self._munkamenet.esemeny_kuld)
        self.g_csat.Disable()
        self._szerep_valaszto.Disable()
        self._panik_figyelo_indit()
        self._mond("Csatlakozás folyamatban a(z) %s szobához… várd a kapcsolatot."
                   % kod)

    def _kod_masol(self, e):
        kod = (self.kod_mezo.GetValue() or "").strip()
        if not kod:
            self._mond("Előbb nyiss szobát – akkor lesz kód.")
            return
        try:
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(kod))
                wx.TheClipboard.Close()
                self._mond("A(z) %s kód a vágólapon." % kod)
        except Exception:
            self._mond("A kód: %s" % kod)

    # ------------------------------------------------------------ kapcsolat kész
    def _kapcsolat_kesz(self):
        if self._closing:
            return
        self._allapot.SetValue("A kapcsolat ÉL.")
        if self._szerep == "segitett":
            # a mi hangunkat streameljük a segítőnek (benne a felolvasás)
            self._felvevo = HangFelvevo(on_pcm=self._kapcsolat.hang_kuld)
            self._felvevo.indit()
            self.g_engedely.Enable()
            self._mond("A segítő csatlakozott, és MOSTANTÓL HALLJA a géped "
                       "hangját (a felolvasást is). Ha irányítást is szeretnél "
                       "adni neki, nyomd meg az Irányítás engedélyezése gombot. "
                       "Bármikor leállíthatod: Ctrl+Alt+Pause.")
        else:
            # a másik gép hangját lejátsszuk
            self._lejatszo = HangLejatszo()
            if self._lejatszo.indit():
                self._kapcsolat.set_hang_fogado(self._lejatszo.jatszd)
                self._mond("Kapcsolat létrejött – mostantól HALLOD a másik "
                           "gépet. Az irányítást neki kell engedélyeznie; ha "
                           "megtette, a Billentyű-területre fókuszálva "
                           "irányíthatsz.")
            else:
                self._mond("Kapcsolat létrejött, de a hang lejátszása nem indult "
                           "el ezen a gépen.")

    # ------------------------------------------------------------ irányítás
    def _iranyitas_engedelyez(self, e):
        if not self._munkamenet or self._szerep != "segitett":
            return
        if self._munkamenet.iranyit:
            return
        if not self._beleegyezes("Irányítás engedélyezése",
                                  SZ.BELEEGYEZO_SEGITETT):
            return
        self._munkamenet.iranyitas_engedelyez()

    def _panik(self, forras="gomb"):
        if self._munkamenet:
            self._munkamenet.iranyitas_leallit(panik=True)

    def _beleegyezes(self, cim, szoveg):
        dlg = wx.MessageDialog(self, szoveg, cim,
                               wx.YES_NO | wx.ICON_WARNING)
        dlg.SetYesNoLabels("Elfogadom", "Mégse")
        valasz = dlg.ShowModal()
        dlg.Destroy()
        return valasz == wx.ID_YES

    # ------------------------------------------------------------ állapot-jelzés
    def _on_allapot(self, kulcs, adat):
        if self._closing:
            return
        if kulcs == "iranyitas_be":
            self.g_panik.Enable()
            if self._szerep == "segitett":
                self.g_engedely.Disable()
                self._allapot.SetValue("IRÁNYÍTÁS ALATT vagy. Pánik: Ctrl+Alt+Pause.")
                self._mond("Az irányítás ENGEDÉLYEZVE – a segítő mostantól "
                           "vezérelheti a géped. Ha bármi nem tetszik: "
                           "Ctrl+Alt+Pause, vagy a pánik gomb.")
                self._emlekezteto_indit()
            else:
                self._allapot.SetValue("MOST TE IRÁNYÍTASZ. A Billentyű-területre "
                                       "fókuszálj!")
                if self._elkapo:
                    self._elkapo.aktiv = True
                self._elkapo_mezo.SetFocus()
                self._mond("Mostantól TE IRÁNYÍTASZ. Fókuszálj a Billentyű-"
                           "területre, és a billentyűid a másik gépre mennek. "
                           "Leállítás: Ctrl+Alt+Pause.")
        elif kulcs == "iranyitas_ki":
            self.g_panik.Disable()
            self._emlekezteto_fut = False
            if self._elkapo:
                self._elkapo.aktiv = False
            if self._szerep == "segitett":
                self.g_engedely.Enable()
            self._allapot.SetValue("A kapcsolat ÉL (irányítás leállítva).")
            self._mond(SZ.IRANYITAS_VEGE
                       + (" (Pánikkal állították le.)" if adat.get("panik") else ""))
        elif kulcs == "csevej":
            self._mond("%s: %s" % (adat.get("ki") or "Társ", adat.get("szoveg")))

    def _emlekezteto_indit(self):
        self._emlekezteto_fut = True

        def tik():
            if self._emlekezteto_fut and not self._closing:
                self._mond(SZ.IRANYITAS_AKTIV.format(ki="a segítő"))
                wx.CallLater(20000, tik)
        wx.CallLater(20000, tik)

    # ------------------------------------------------------------ pánik-hotkey
    def _panik_figyelo_indit(self):
        if self._panik_fut:
            return
        self._panik_fut = True
        threading.Thread(target=self._panik_figyelo, daemon=True).start()

    def _panik_figyelo(self):
        try:
            u = ctypes.windll.user32
        except Exception:
            return
        VK_CONTROL, VK_MENU, VK_PAUSE = 0x11, 0x12, 0x13
        while self._panik_fut and not self._closing:
            try:
                if (u.GetAsyncKeyState(VK_CONTROL) & 0x8000
                        and u.GetAsyncKeyState(VK_MENU) & 0x8000
                        and u.GetAsyncKeyState(VK_PAUSE) & 0x8000):
                    wx.CallAfter(self._panik, "hotkey")
                    time.sleep(1.0)
            except Exception:
                pass
            time.sleep(0.05)

    # ------------------------------------------------------------ egyéb
    def _char_hook(self, e):
        # F1 a súgóhoz; a többit tovább (az elkapó-mező külön kezeli)
        if e.GetKeyCode() == wx.WXK_F1:
            self._sugo()
        else:
            e.Skip()

    def _sugo(self):
        szoveg = ("TÁVSEGÍTSÉG – SÚGÓ\n\n" + SZ.BELEEGYEZO_SEGITETT
                  + "\n\n— — —\n\n" + SZ.BELEEGYEZO_IRANYITO)
        try:
            from superdl.helpdialog import show_help
            show_help(self, "Súgó – Távsegítség", szoveg)
        except Exception:
            wx.MessageBox(szoveg, "Súgó – Távsegítség",
                          wx.OK | wx.ICON_INFORMATION, self)

    def _mond(self, szoveg):
        if self._closing or not (szoveg or "").strip():
            return
        try:
            self._naplo.AppendText(szoveg + "\n")
        except Exception:
            pass
        try:
            from superdl import screenreader
            if screenreader.speak(szoveg):
                return
        except Exception:
            pass
        v = getattr(self.core, "voice", None)
        if v:
            try:
                v.speak(szoveg, force=True)
            except Exception:
                pass

    def _on_close(self, e):
        self._closing = True
        self._panik_fut = False
        self._emlekezteto_fut = False
        for obj in (self._munkamenet, self._felvevo, self._lejatszo,
                    self._kapcsolat):
            try:
                if obj:
                    obj.leallit()
            except Exception:
                pass
        e.Skip()
