# -*- coding: utf-8 -*-
"""Online, gépek közti Szerencsekerék (host-authoritative, Ably-szobán át).

- A szobát létrehozó játékos a HOST: nála fut a hiteles játékállapot
  (OnlineHost), ő húzza a rejtvényt és validál. A rejtvény SOSEM megy le a
  többiekhez, csak a felfedett betűk – így nem lehet csalni.
- Mindenki „akció"-t küld a szobába (pörget/betű/magánhangzó/megfejt); a host
  feldolgozza és teljes ÁLLAPOTOT broadcastol, amit minden gép felolvas.
- A hálózatot a netroom.NetSzoba adja (Ably REST + history-poll).

A tényleges Szerencsekerék-szabályokat/segédeket a jatekok.sajat modulból
hasznosítjuk újra.
"""
import wx

from . import netroom
from .jatekok import sajat as SZK


# ===================== HOST-oldali állapotgép (wx nélkül) =====================

class OnlineHost:
    """A host-authoritative Szerencsekerék. Akciókat kap, teljes állapotot ad.
    Nem tud sem wx-ről, sem hálózatról – így gépi teszttel ellenőrizhető."""

    def __init__(self, jatekosok, korok=None, valaszto=None):
        self.jatekosok = [j for j in jatekosok if j]
        if not self.jatekosok:
            self.jatekosok = ["Játékos"]
        self.korok = int(korok or SZK._SZK_FORDULO)
        self._valaszto = valaszto or SZK._szk_valaszt
        self.bank = {n: 0 for n in self.jatekosok}
        self.kor = 0
        self.megoldas = ""
        self.kategoria = ""
        self.felfedett = set()
        self.korpenz = {n: 0 for n in self.jatekosok}
        self.soron_idx = 0
        self.utolso_porgetes = None      # a pörgetett érték, amire betű vár
        self.fazis = "jatek"             # "jatek" | "vege"
        self._uj_fordulo()

    # ---- belső ----
    def _uj_fordulo(self):
        self.kor += 1
        kat, meg = self._valaszto(SZK._szk_rejtvenyek())
        self.kategoria, self.megoldas = kat, meg
        self.felfedett = set()
        self.korpenz = {n: 0 for n in self.jatekosok}
        self.utolso_porgetes = None
        self.soron_idx = 0

    @property
    def soron(self):
        return self.jatekosok[self.soron_idx]

    def _kovetkezo(self):
        self.soron_idx = (self.soron_idx + 1) % len(self.jatekosok)
        self.utolso_porgetes = None

    def allapot(self, uzenet=""):
        return {
            "fazis": self.fazis,
            "kor": self.kor, "korok": self.korok,
            "kategoria": self.kategoria,
            "tabla": SZK._szk_tabla(self.megoldas, self.felfedett),
            "soron": self.soron if self.fazis == "jatek" else "",
            "jatekosok": list(self.jatekosok),
            "bank": dict(self.bank),
            "korpenz": dict(self.korpenz),
            "utolso_porgetes": self.utolso_porgetes,
            "uzenet": uzenet,
        }

    def _veg(self, uz):
        self.fazis = "vege"
        gy = max(self.bank, key=lambda n: self.bank[n])
        return self.allapot(uz + f" VÉGE! A győztes: {gy}, {self.bank[gy]} forinttal.")

    # ---- egy akció feldolgozása ----
    def akcio(self, ki, tipus, ertek=None):
        """A soron lévő játékos akciója. Visszaad: állapot-dict, vagy None, ha
        érvénytelen (nem az ő köre, vagy vége a játéknak)."""
        if self.fazis != "jatek" or ki != self.soron:
            return None

        if tipus == "porget":
            p = SZK._szk_porget()
            if p[0] == "csod":
                self.korpenz[ki] = 0
                uz = (f"{ki} pörgetett: CSŐD! Elveszti a köri pénzét, "
                      "jön a következő.")
                self._kovetkezo()
                return self.allapot(uz)
            if p[0] == "passz":
                self._kovetkezo()
                return self.allapot(f"{ki} pörgetett: PASSZ! Jön a következő.")
            self.utolso_porgetes = p[1]
            return self.allapot(f"{ki} pörgetett: {p[1]} forint! Most mondj egy "
                                "mássalhangzót, vagy vegyél magánhangzót, vagy "
                                "fejtsd meg.")

        if tipus == "betu":
            betu = (ertek or "").strip().lower()[:1]
            if not betu.isalpha():
                return None
            if betu in self.felfedett:
                return self.allapot(f"A(z) {betu.upper()} már felfedve. "
                                    f"{ki} jöhet újra.")
            if SZK._szk_maganhangzo(betu):
                return self.allapot("Ez magánhangzó – azt VENNED kell, nem "
                                    "pörgetéssel.")
            if self.utolso_porgetes is None:
                return self.allapot("Előbb pörögj, aztán mondj mássalhangzót!")
            db = SZK._szk_elofordul(self.megoldas, betu)
            if db > 0:
                self.felfedett.add(betu)
                nyer = db * self.utolso_porgetes
                self.korpenz[ki] += nyer
                self.utolso_porgetes = None
                return self.allapot(f"{ki}: {betu.upper()} – {db}-szer, "
                                    f"{nyer} forint! {ki} jöhet újra.")
            self.utolso_porgetes = None
            uz = f"{ki}: {betu.upper()} – nincs a rejtvényben. Jön a következő."
            self._kovetkezo()
            return self.allapot(uz)

        if tipus == "maganhangzo":
            betu = (ertek or "").strip().lower()[:1]
            if not SZK._szk_maganhangzo(betu):
                return self.allapot("Ez nem magánhangzó.")
            if betu in self.felfedett:
                return self.allapot("Ezt a magánhangzót már felfedték.")
            if self.korpenz[ki] < SZK._SZK_MGH_AR:
                return self.allapot(f"Nincs elég köri pénzed – {SZK._SZK_MGH_AR} "
                                    "forint kell egy magánhangzóra.")
            self.korpenz[ki] -= SZK._SZK_MGH_AR
            self.felfedett.add(betu)
            db = SZK._szk_elofordul(self.megoldas, betu)
            return self.allapot(f"{ki} vett egy {betu.upper()} magánhangzót "
                                f"({SZK._SZK_MGH_AR} forint), {db}-szer szerepel. "
                                f"{ki} jöhet.")

        if tipus == "megfejt":
            if SZK._szk_egyezik(ertek or "", self.megoldas):
                self.bank[ki] += self.korpenz[ki]
                self.felfedett = set(ch.lower() for ch in self.megoldas
                                     if ch.isalpha())
                uz = (f"{ki} MEGFEJTETTE: {self.megoldas}! A köri pénze a "
                      "bankjába került.")
                if self.kor >= self.korok:
                    return self._veg(uz)
                self._uj_fordulo()
                return self.allapot(uz + f" Jön a(z) {self.kor}. forduló!")
            self._kovetkezo()
            return self.allapot(f"{ki} megfejtése nem jó. Jön a következő.")

        return None


# ============================ wx: lobbi + játék ==============================

class SzerencseOnlineAblak(wx.Dialog):
    def __init__(self, main, jatek, gep_getter):
        super().__init__(main, title="Szerencsekerék – online",
                         size=(760, 580),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.main = main
        self._closing = False
        self._szoba = None
        self._host = False
        self._onlinehost = None
        self._nev = self._alap_nev()
        self._jatekosok = []             # a hostnál: a szoba tagjai
        self._soron = ""                 # kié a kör (a legutóbbi állapotból)
        self._fazis = "lobbi"
        self._build()
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    def _alap_nev(self):
        try:
            s = getattr(self.main, "settings", {}) or {}
            n = (s.get("nev") or s.get("felhasznalo") or "").strip()
            return n or "Játékos"
        except Exception:
            return "Játékos"

    # ---- felépítés ----
    def _build(self):
        v = wx.BoxSizer(wx.VERTICAL)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        sor.Add(wx.StaticText(self, label="A &neved:"),
                0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.nev_mezo = wx.TextCtrl(self, value=self._nev)
        self.nev_mezo.SetName("A neved")
        sor.Add(self.nev_mezo, 1, wx.RIGHT, 12)
        v.Add(sor, 0, wx.EXPAND | wx.ALL, 8)

        # lobbi gombok
        lob = wx.BoxSizer(wx.HORIZONTAL)
        self.uj_gomb = wx.Button(self, label="Ú&j szoba (én vagyok a host)")
        self.uj_gomb.Bind(wx.EVT_BUTTON, self._uj_szoba)
        lob.Add(self.uj_gomb, 0, wx.RIGHT, 6)
        lob.Add(wx.StaticText(self, label="vagy &szobakód:"),
                0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.kod_mezo = wx.TextCtrl(self, size=(90, -1))
        self.kod_mezo.SetName("Szobakód")
        lob.Add(self.kod_mezo, 0, wx.RIGHT, 6)
        self.csat_gomb = wx.Button(self, label="&Csatlakozás")
        self.csat_gomb.Bind(wx.EVT_BUTTON, self._csatlakozas)
        lob.Add(self.csat_gomb, 0, wx.RIGHT, 6)
        self.indit_gomb = wx.Button(self, label="Játék &indítása")
        self.indit_gomb.Bind(wx.EVT_BUTTON, self._indit)
        self.indit_gomb.Disable()
        lob.Add(self.indit_gomb, 0)
        v.Add(lob, 0, wx.ALL, 8)

        # átirat
        self.atirat = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.atirat.SetName("Játék szövege")
        v.Add(self.atirat, 1, wx.EXPAND | wx.ALL, 8)

        # akció-sor
        akc = wx.BoxSizer(wx.HORIZONTAL)
        akc.Add(wx.StaticText(self, label="&Betű / megfejtés:"),
                0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.be = wx.TextCtrl(self, size=(180, -1))
        self.be.SetName("Betű vagy megfejtés")
        akc.Add(self.be, 0, wx.RIGHT, 8)
        self.g_porget = wx.Button(self, label="&Pörgetés")
        self.g_porget.Bind(wx.EVT_BUTTON, lambda e: self._akcio("porget"))
        akc.Add(self.g_porget, 0, wx.RIGHT, 4)
        self.g_betu = wx.Button(self, label="Be&tű")
        self.g_betu.Bind(wx.EVT_BUTTON, lambda e: self._akcio("betu", self.be.GetValue()))
        akc.Add(self.g_betu, 0, wx.RIGHT, 4)
        self.g_mgh = wx.Button(self, label="&Magánhangzó vétele")
        self.g_mgh.Bind(wx.EVT_BUTTON, lambda e: self._akcio("maganhangzo", self.be.GetValue()))
        akc.Add(self.g_mgh, 0, wx.RIGHT, 4)
        self.g_megfejt = wx.Button(self, label="Me&gfejtés")
        self.g_megfejt.Bind(wx.EVT_BUTTON, lambda e: self._akcio("megfejt", self.be.GetValue()))
        akc.Add(self.g_megfejt, 0)
        v.Add(akc, 0, wx.ALL, 8)
        self._akciok_engedely(False)
        self.SetSizer(v)
        wx.CallAfter(self._start_ellenoriz)

    def _start_ellenoriz(self):
        if not netroom.ably_kulcs():
            self._mondd("Figyelem: nincs beállítva az online kulcs "
                        "(~/.superdl/ably_key.txt), így az online játék nem "
                        "működik. A helyi Szerencsekerék a Saját játékokban megy.")

    # ---- lobbi ----
    def _uj_szoba(self, e):
        self._nev = (self.nev_mezo.GetValue() or "Játékos").strip()
        kod = netroom.szobakod()
        self._szoba = netroom.NetSzoba(kod, self._nev)
        if not self._szoba.elerheto():
            self._mondd("Nincs online kulcs beállítva – nem tudok szobát nyitni.")
            return
        self._host = True
        self._jatekosok = [self._nev]
        self._szoba.figyel(self._uzenet_jott)
        self.kod_mezo.SetValue(kod)
        self.uj_gomb.Disable()
        self.csat_gomb.Disable()
        self.indit_gomb.Enable()
        self._mondd(f"Szoba létrehozva! A szobakódod: {kod}. Mondd be a "
                    f"többieknek, csatlakozzanak, majd nyomd meg a Játék "
                    f"indítása gombot. (Betűnként: {' '.join(kod)})")

    def _csatlakozas(self, e):
        self._nev = (self.nev_mezo.GetValue() or "Játékos").strip()
        kod = (self.kod_mezo.GetValue() or "").strip().upper()
        if not kod:
            self._mondd("Írd be a szobakódot, amit a host mondott.")
            return
        self._szoba = netroom.NetSzoba(kod, self._nev)
        if not self._szoba.elerheto():
            self._mondd("Nincs online kulcs beállítva – nem tudok csatlakozni.")
            return
        self._host = False
        self._szoba.figyel(self._uzenet_jott)
        self._szoba.kuld("csatlakozott", {"nev": self._nev})
        self.uj_gomb.Disable()
        self.csat_gomb.Disable()
        self._mondd(f"Csatlakoztál a(z) {kod} szobához {self._nev} néven. "
                    "Várd, hogy a host elindítsa a játékot!")

    def _indit(self, e):
        if not self._host or not self._szoba:
            return
        self._onlinehost = OnlineHost(self._jatekosok)
        self.indit_gomb.Disable()
        self._szoba.kuld("start", {"jatekosok": self._jatekosok})
        allap = self._onlinehost.allapot(
            f"Kezdődik a játék {len(self._jatekosok)} játékossal! "
            f"Első forduló, kategória: {self._onlinehost.kategoria}.")
        self._szoba.kuld("allapot", allap)

    # ---- hálózati üzenet ----
    def _uzenet_jott(self, u):
        if not self._closing:
            wx.CallAfter(self._kezeld, u)

    def _kezeld(self, u):
        if self._closing:
            return
        tipus = u.get("tipus")
        ki = u.get("ki")
        adat = u.get("adat") or {}
        if tipus == "csatlakozott":
            if self._host:
                nev = (adat.get("nev") or ki or "").strip()
                if nev and nev not in self._jatekosok:
                    self._jatekosok.append(nev)
                    self._mondd(f"{nev} csatlakozott. Játékosok: "
                                + ", ".join(self._jatekosok) + ".")
            return
        if tipus == "start":
            self._jatekosok = adat.get("jatekosok", self._jatekosok)
            self._mondd("A host elindította a játékot! Játékosok: "
                        + ", ".join(self._jatekosok) + ".")
            return
        if tipus == "akcio":
            if self._host and self._onlinehost:
                allap = self._onlinehost.akcio(
                    ki, adat.get("tipus"), adat.get("ertek"))
                if allap is not None:
                    self._szoba.kuld("allapot", allap)
            return
        if tipus == "allapot":
            self._render(adat)
            return

    def _render(self, a):
        self._fazis = a.get("fazis", "jatek")
        self._soron = a.get("soron", "")
        uz = a.get("uzenet", "")
        pontok = a.get("bank", {})
        pont_szoveg = ", ".join(f"{n}: {pontok.get(n, 0)}"
                                for n in a.get("jatekosok", []))
        sorok = []
        if uz:
            sorok.append(uz)
        sorok.append(a.get("tabla", ""))
        if self._fazis == "jatek":
            sorok.append(f"Soron: {self._soron}. Bank – {pont_szoveg}.")
        else:
            sorok.append(f"Végeredmény – {pont_szoveg}.")
        self._mondd("  ".join(s for s in sorok if s))
        # akciók: csak ha én vagyok soron és megy a játék
        enyem = (self._fazis == "jatek" and self._soron == self._nev)
        self._akciok_engedely(enyem)
        if enyem:
            self._mondd("TE JÖSSZ! Pörgetés, vagy betű, vagy magánhangzó "
                        "vétele, vagy megfejtés.")

    # ---- akció küldése ----
    def _akcio(self, tipus, ertek=None):
        if not self._szoba or self._fazis != "jatek":
            return
        if self._soron != self._nev:
            self._mondd("Most nem te vagy soron.")
            return
        self._szoba.kuld("akcio", {"tipus": tipus, "ertek": ertek})
        if tipus in ("betu", "maganhangzo", "megfejt"):
            self.be.SetValue("")

    def _akciok_engedely(self, be):
        for g in (self.g_porget, self.g_betu, self.g_mgh, self.g_megfejt, self.be):
            g.Enable(be)

    # ---- kimenet / billentyűk / zárás ----
    def _mondd(self, szoveg):
        if self._closing or not (szoveg or "").strip():
            return
        self.atirat.AppendText(szoveg + "\n")
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
            except Exception:
                pass

    def _on_key(self, e):
        if e.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        else:
            e.Skip()

    def _on_close(self, e):
        self._closing = True
        try:
            if self._szoba:
                self._szoba.leallit()
        except Exception:
            pass
        e.Skip()
