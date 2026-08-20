# -*- coding: utf-8 -*-
"""INTERNET-TESZT ablak – vakon is teljes értékű hálózat-felmérés.

Tervezési elvek (ezek nem díszek, ezek a lényeg):
  • ELŐSZÖR ÍTÉLET, UTÁNA SZÁMOK. A felső mezőben egy emberi mondat áll:
    „Az interneted gyors: … Elég ehhez: …". A számhalom csak alatta jön.
  • MINDEN SOR ÖNMAGÁBAN ÉRTELMES, mert a képernyőolvasó SORONKÉNT olvas fel:
    nincs „Igen"/„Nem" önmagában, mindig ott a címke is.
  • MÉRÉS KÖZBEN NEM NÉMASÁG: halk, emelkedő pittyegés (a Core közös
    ProgressBeepere) + a fázisok bemondása. Esc bármikor megszakít.
  • AZ ABLAK NEM FAGY: a mérés háttérszálon fut, a felület csak `wx.CallAfter`-rel
    frissül, `_closing` őrrel (bezárás után egyetlen visszahívás sem nyúl a
    már megszűnt vezérlőkhöz).
  • ADATVÉDELEM: a publikus IP alapból MASZKOLT. Teljes alakban csak külön
    gombnyomásra – mert élő adás vagy Távsegítség közben fel is olvasódna.

A BEMONDÁS SORRENDJE KÖTELEZŐ: előbb a KÉPERNYŐOLVASÓ, és csak utána a némítás
vizsgálata és a beépített hang. Képernyőolvasó-módban ugyanis a Core
SZÁNDÉKOSAN némítja a saját hangját – ha a némítás-vizsgálat lenne elöl, az
egész ablak néma maradna (ez okozta korábban a P2P-nél a néma F8-at).
"""

import threading

import wx

from superdl import nettest

try:
    from superdl import screenreader as _sr
except Exception:                        # pragma: no cover
    _sr = None
try:
    from superdl import sounds as _sounds
except Exception:                        # pragma: no cover
    _sounds = None


class NetTestDialog(wx.Dialog):
    def __init__(self, parent, settings=None, selfvoice=None):
        super().__init__(parent, title="Internet-teszt",
                         size=(760, 620),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._settings = settings if isinstance(settings, dict) else {}
        self._selfvoice = selfvoice
        self._closing = False
        self._stop = None
        self._szal = None
        self._eredmeny = None
        self._teljes_ip = False
        self._beeper = None

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        cimke = wx.StaticText(p, label="&Összefoglaló:")
        self.osszefoglalo = wx.TextCtrl(
            p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP,
            size=(-1, 130))
        self.osszefoglalo.SetName("Összefoglaló, csak olvasható")
        self.osszefoglalo.SetValue(
            "Nyomd meg a Teljes teszt gombot (Enter). A mérés kb. 25 másodperc, "
            "és %s adatforgalmat használ.\n\n"
            "Ha mobilneten vagy, válaszd a Takarékos tesztet (%s), vagy a Gyors "
            "ellenőrzést, ami sebességet nem mér, de mindent mást megnéz."
            % (nettest.becsult_forgalom("teljes"),
               nettest.becsult_forgalom("takarekos")))
        v.Add(cimke, 0, wx.LEFT | wx.TOP, 8)
        v.Add(self.osszefoglalo, 0, wx.EXPAND | wx.ALL, 8)

        cimke2 = wx.StaticText(p, label="&Részletek (fel-le nyíllal olvasható):")
        self.lista = wx.ListBox(p, style=wx.LB_SINGLE)
        self.lista.SetName("Részletes eredmények listája")
        v.Add(cimke2, 0, wx.LEFT, 8)
        v.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)

        sor1 = wx.BoxSizer(wx.HORIZONTAL)
        self.b_teljes = wx.Button(p, label="&Teljes teszt")
        self.b_teljes.SetName("Teljes teszt indítása")
        self.b_teljes.SetDefault()
        self.b_takarekos = wx.Button(p, label="Ta&karékos teszt")
        self.b_takarekos.SetName("Takarékos teszt, kevés adatforgalommal")
        self.b_gyors = wx.Button(p, label="&Gyors ellenőrzés")
        self.b_gyors.SetName("Gyors ellenőrzés sebességmérés nélkül")
        self.b_megszakit = wx.Button(p, label="&Megszakítás")
        self.b_megszakit.SetName("A futó mérés megszakítása")
        self.b_megszakit.Enable(False)
        for b in (self.b_teljes, self.b_takarekos, self.b_gyors,
                  self.b_megszakit):
            sor1.Add(b, 0, wx.RIGHT, 6)
        v.Add(sor1, 0, wx.LEFT | wx.RIGHT, 8)

        sor2 = wx.BoxSizer(wx.HORIZONTAL)
        self.b_ip = wx.Button(p, label="Teljes &IP megjelenítése")
        self.b_ip.SetName("A teljes publikus IP-cím megjelenítése")
        self.b_masol = wx.Button(p, label="&Vágólapra")
        self.b_masol.SetName("A jelentés vágólapra másolása")
        self.b_naplo = wx.Button(p, label="Ko&rábbi mérések")
        self.b_naplo.SetName("Korábbi mérések listája")
        self.b_wifi = wx.Button(p, label="&Wi-Fi jelerősség figyelése…")
        self.b_wifi.SetName("Wi-Fi jelerősség figyelése dBm-ben – "
                            "mesh-hálózat építéséhez, járkálás közben is")
        self.b_wifi.Bind(wx.EVT_BUTTON, lambda e: self._wifi_figyelo())
        b_zar = wx.Button(p, wx.ID_CANCEL, "&Bezárás")
        for b in (self.b_ip, self.b_masol, self.b_naplo, self.b_wifi, b_zar):
            sor2.Add(b, 0, wx.RIGHT, 6)
        v.Add(sor2, 0, wx.ALL, 8)

        # HALADÓKNAK: saját mérő-forrás. Azért van itt és nem elrejtve, mert
        # élesben kiderült, hogy egy kiszolgáló időnként visszafogja a mérést –
        # ilyenkor jó, ha a felhasználó megadhat egy hozzá közeli forrást.
        sor3 = wx.BoxSizer(wx.HORIZONTAL)
        cimke3 = wx.StaticText(p, label="Saját mérő-&forrás (haladóknak, "
                                        "üresen hagyható):")
        self.forras = wx.TextCtrl(p, value=str(
            self._settings.get("nettest_le_url", "") or ""))
        self.forras.SetName("Saját letöltési mérő-forrás webcíme")
        self.forras.SetHint("https://…  – üresen az alapértelmezett forrásokat "
                            "használjuk")
        sor3.Add(cimke3, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        sor3.Add(self.forras, 1, wx.ALIGN_CENTER_VERTICAL)
        v.Add(sor3, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        p.SetSizer(v)

        self.b_teljes.Bind(wx.EVT_BUTTON, lambda e: self._indit("teljes"))
        self.b_takarekos.Bind(wx.EVT_BUTTON, lambda e: self._indit("takarekos"))
        self.b_gyors.Bind(wx.EVT_BUTTON, lambda e: self._indit("gyors"))
        self.b_megszakit.Bind(wx.EVT_BUTTON, self._on_megszakit)
        self.b_ip.Bind(wx.EVT_BUTTON, self._on_ip)
        self.b_masol.Bind(wx.EVT_BUTTON, self._on_masol)
        self.b_naplo.Bind(wx.EVT_BUTTON, self._on_naplo)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.lista.Bind(wx.EVT_KEY_DOWN, self._on_key)

        self.CentreOnParent()
        wx.CallAfter(self._mondd,
                     "Internet-teszt. Enter: teljes teszt. A részletek listáját "
                     "a nyilakkal olvashatod.")

    # ------------------------------------------------------------ bemondás

    def _wifi_figyelo(self) -> None:
        """A mesh-hálózat építéséhez: folyamatos jelerősség-figyelés dBm-ben."""
        from . import wifiwin
        wifiwin.mutasd(self, self._mondd)

    def _mondd(self, szoveg: str) -> None:
        """KÖTELEZŐ SORREND: előbb a képernyőolvasó, utána a némítás-vizsgálat és
        a beépített hang (lásd az ablak fejlécében, és a tests/
        test_bemondas_sorrend.py őrzi)."""
        if self._closing or not szoveg:
            return
        try:
            if _sr is not None and _sr.speak(szoveg):
                return
        except Exception:
            pass
        try:
            sv = self._selfvoice
            if sv is not None and not getattr(sv, "muted", False):
                sv.speak(szoveg, force=True)
        except Exception:
            pass

    def _pittyeg(self, szazalek: float) -> None:
        try:
            if self._beeper is None and _sounds is not None:
                self._beeper = _sounds.ProgressBeeper()
            if self._beeper is not None:
                self._beeper.update(szazalek)
        except Exception:
            pass

    # -------------------------------------------------------------- mérés

    def _indit(self, mod: str) -> None:
        if self._szal is not None and self._szal.is_alive():
            self._mondd("Egy mérés már fut. Előbb szakítsd meg.")
            return
        if mod == "teljes" and not self._mehet_sok_adat():
            return
        self._stop = threading.Event()
        self._utolso_fazis = ""
        if self._beeper is not None:
            try:
                self._beeper.reset()
            except Exception:
                pass
        for b in (self.b_teljes, self.b_takarekos, self.b_gyors):
            b.Enable(False)
        self.b_megszakit.Enable(True)
        self.lista.Clear()
        nev = {"teljes": "Teljes", "takarekos": "Takarékos",
               "gyors": "Gyors"}.get(mod, mod)
        self.osszefoglalo.SetValue("%s mérés folyamatban…" % nev)
        self._mondd("%s mérés indul. Megszakítás: Escape." % nev)
        le_url = self.forras.GetValue().strip()
        if le_url != str(self._settings.get("nettest_le_url", "") or ""):
            self._settings["nettest_le_url"] = le_url
            szulo = self.GetParent()
            if hasattr(szulo, "_save_settings"):
                try:
                    szulo._save_settings()
                except Exception:
                    pass

        def munka():
            try:
                e = nettest.merj(mod, stop=self._stop, halad=self._halad,
                                 le_url=le_url)
            except Exception as ex:            # sose maradjon néma a hiba
                e = nettest.Eredmeny(mod=mod)
                e.hibak.append("váratlan hiba: %s" % ex)
            wx.CallAfter(self._kesz, e)

        self._szal = threading.Thread(target=munka, daemon=True)
        self._szal.start()

    def _mehet_sok_adat(self) -> bool:
        """MOBILNET-VÉDELEM: a teljes mérés valódi adatot tölt. Ha korlátozott
        (mért) kapcsolat gyanúja van, RÁKÉRDEZÜNK – mert ott ez pénz."""
        try:
            gyanus = nettest.merten_gyanu(nettest.adapterek())
        except Exception:
            gyanus = False
        if not gyanus:
            return True
        uzenet = ("Úgy tűnik, korlátozott (mért) kapcsolaton vagy – például "
                  "mobilneten. A teljes teszt %s adatforgalmat használ.\n\n"
                  "Biztosan a teljes tesztet indítod? A Takarékos teszt %s-ot "
                  "használ." % (nettest.becsult_forgalom("teljes"),
                                nettest.becsult_forgalom("takarekos")))
        self._mondd(uzenet)
        d = wx.MessageDialog(self, uzenet, "Korlátozott kapcsolat",
                             wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        d.SetYesNoLabels("Igen, teljes teszt", "Mégsem")
        valasz = d.ShowModal()
        d.Destroy()
        return valasz == wx.ID_YES

    def _halad(self, fazis: str, szazalek: float) -> None:
        """Háttérszálról hívódik – a felülethez CSAK CallAfter-en át nyúlunk."""
        if self._closing:
            return
        wx.CallAfter(self._halad_gui, fazis, szazalek)

    def _halad_gui(self, fazis: str, szazalek: float) -> None:
        if self._closing:
            return
        self._pittyeg(szazalek)
        if fazis != getattr(self, "_utolso_fazis", ""):
            self._utolso_fazis = fazis
            self.osszefoglalo.SetValue("%s… (%d százalék)"
                                       % (fazis, int(szazalek)))
            self._mondd(fazis)

    def _kesz(self, e) -> None:
        if self._closing:
            return
        self._eredmeny = e
        for b in (self.b_teljes, self.b_takarekos, self.b_gyors):
            b.Enable(True)
        self.b_megszakit.Enable(False)
        self._mutat()
        try:
            if not e.megszakitva:
                nettest.naplo_ment(e)
        except Exception:
            pass
        szoveg = nettest.osszefoglalo(e)
        atlag = ""
        try:
            atlag = nettest.naplo_atlag()
        except Exception:
            pass
        self._mondd(szoveg + ((" " + atlag) if atlag else ""))
        self.lista.SetFocus()
        if self.lista.GetCount():
            self.lista.SetSelection(0)

    def _mutat(self) -> None:
        e = self._eredmeny
        if e is None:
            return
        self.osszefoglalo.SetValue(nettest.osszefoglalo(e))
        kijelolt = self.lista.GetSelection()
        self.lista.Set(nettest.sorok(e, teljes_ip=self._teljes_ip))
        if 0 <= kijelolt < self.lista.GetCount():
            self.lista.SetSelection(kijelolt)

    # ------------------------------------------------------------- gombok

    def _on_megszakit(self, event=None) -> None:
        if self._stop is not None:
            self._stop.set()
            self._mondd("Mérés megszakítva.")

    def _on_ip(self, event=None) -> None:
        if self._eredmeny is None or not self._eredmeny.publikus.ip:
            self._mondd("Előbb futtass egy mérést.")
            return
        self._teljes_ip = not self._teljes_ip
        self.b_ip.SetLabel("IP el&rejtése" if self._teljes_ip
                           else "Teljes &IP megjelenítése")
        self._mutat()
        if self._teljes_ip:
            self._mondd("A teljes publikus IP-címed: %s. Vigyázz vele: élő "
                        "adásban vagy Távsegítség közben ez elhangzik."
                        % _betuzve(self._eredmeny.publikus.ip))
        else:
            self._mondd("Az IP-cím újra elrejtve.")

    def _on_masol(self, event=None) -> None:
        if self._eredmeny is None:
            self._mondd("Előbb futtass egy mérést.")
            return
        szoveg = nettest.jelentes(self._eredmeny, teljes_ip=self._teljes_ip)
        try:
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(szoveg))
                wx.TheClipboard.Close()
                self._mondd("A jelentés a vágólapon. Beillesztheted egy levélbe."
                            + ("" if self._teljes_ip else
                               " A publikus IP-cím maszkolva került bele."))
                return
        except Exception:
            pass
        self._mondd("A vágólapra másolás nem sikerült.")

    def _on_naplo(self, event=None) -> None:
        sorok = nettest.naplo_sorok()
        self.lista.Set(sorok)
        self.osszefoglalo.SetValue("Korábbi mérések (legújabb elöl). %s\n\n"
                                   "Ebből derül ki, ha a sebesség rendszeresen "
                                   "beesik – például minden este."
                                   % (nettest.naplo_atlag() or ""))
        self._mondd("Korábbi mérések: %d darab. %s"
                    % (len(sorok), nettest.naplo_atlag() or ""))
        self.lista.SetFocus()
        if sorok:
            self.lista.SetSelection(0)

    def _on_key(self, event) -> None:
        kod = event.GetKeyCode()
        if kod == wx.WXK_ESCAPE:
            if self._stop is not None and self._szal is not None \
                    and self._szal.is_alive():
                self._on_megszakit()
                return
        event.Skip()

    def _on_close(self, event=None) -> None:
        self._closing = True
        if self._stop is not None:
            self._stop.set()
        if self._szal is not None and self._szal.is_alive():
            self._szal.join(timeout=2.0)
        self.Destroy()


def _betuzve(ip: str) -> str:
    """Az IP-t pontonként tagolva mondjuk, hogy hallás után is leírható legyen."""
    return (ip or "").replace(".", " pont ").replace(":", " kettőspont ")


def mutasd(parent, settings=None, selfvoice=None) -> None:
    """A főablak ezt hívja (gomb, menü, Ctrl+Alt+I)."""
    d = NetTestDialog(parent, settings=settings, selfvoice=selfvoice)
    d.ShowModal()
