# -*- coding: utf-8 -*-
"""Ország-Város-Fiú-Lány – host-authoritative ONLINE motor (fejetlen).

A saját szó-játék többjátékos, egy gépről-több gépre változata. A valós idejű
rész (az ábécé HELYI pörgetése minden gépen + az időzítés) a UI-panelé; a
motor a hálózat-független, tesztelhető logikát tartja:

- betu_rogzit(betu): az ELSŐ beérkező „stop" betűje rögzül (a stoppoló saját
  betűje; a host first-come alapon dönt) – SOHA nem a gép/random.
- valasz_be(ki, valaszok): egy játékos kategóriánkénti szavai.
- ertekel(): pontozás. Alappont a szó jóságáért (a helyi játékkal AZONOS
  `_ertekel`: rossz betű/üres = 0, jó betű de nincs a szótárban = 1, szótári
  szó = 2), PLUSZ 2 EGYEDISÉGI bónusz, ha rajtad kívül más NEM írta ugyanazt.

A kategóriák, a szótár és az `_ertekel` a meglévő `jatekok/orszagvaros.py`-ból
jönnek (semmi duplikáció).
"""
from collections import Counter

from .jatekok import orszagvaros as OV


class OrszagVarosHost:
    """Host-oldali Ország-Város állapotgép. Fázisok:
    „varakozas" (kör előtt), „betuzes" (ábécé pörög, betűre vár),
    „iras" (mindenki ír), „eredmeny" (a kör kiértékelve)."""

    def __init__(self, jatekosok, kulcsok=None, custom=None):
        self.jatekosok = [j for j in jatekosok if j] or ["Játékos"]
        self.kulcsok = list(kulcsok or OV.ALAP_KULCSOK)
        self.custom = custom if custom is not None else OV.load_custom()
        self.keszletek = {k: OV.keszlet(k, self.custom) for k in self.kulcsok}
        self.osszpont = {n: 0 for n in self.jatekosok}
        self.kor = 0
        self.fazis = "varakozas"
        self.betu = ""
        self.valaszok = {}
        self.kor_eredmeny = {}

    # ---------------------------------------------------------------- kör
    def kor_indit(self):
        """Új kör: az ábécé pörgetése kezdődhet (a betűre várunk)."""
        self.kor += 1
        self.betu = ""
        self.valaszok = {}
        self.kor_eredmeny = {}
        self.fazis = "betuzes"

    def betu_rogzit(self, betu):
        """Az ELSŐ „stop" betűje rögzül (a többit eldobjuk). True, ha most
        rögzült; False, ha rossz fázis / már van betű / üres."""
        if self.fazis != "betuzes" or self.betu:
            return False
        b = OV.ekezet_nelkul(betu or "")[:1]
        if not b:
            return False
        self.betu = b
        self.fazis = "iras"
        return True

    def valasz_be(self, ki, valaszok):
        """Egy játékos kategóriánkénti szavai (felülírja a korábbit, ha volt)."""
        if self.fazis != "iras" or ki not in self.osszpont:
            return
        v = valaszok or {}
        self.valaszok[ki] = {k: str(v.get(k, "") or "").strip()
                             for k in self.kulcsok}

    def mindenki_beadott(self):
        return all(n in self.valaszok for n in self.jatekosok)

    def ertekel(self):
        """Kiértékelés: alappont (0/1/2) + egyediségi bónusz (+2). Feltölti az
        összpontot, fázis „eredmeny", visszaadja a kör-eredményt."""
        detail = {n: {} for n in self.jatekosok}
        korpont = {n: 0 for n in self.jatekosok}
        for k in self.kulcsok:
            elbiral = {}
            for n in self.jatekosok:
                w = (self.valaszok.get(n, {}) or {}).get(k, "")
                allap, base = OV._ertekel(w, self.betu, self.keszletek[k])
                elbiral[n] = (w, allap, base, OV.ekezet_nelkul(w))
            # egy kategórián belül a NORMALIZÁLT érvényes szavak darabszáma
            szamlalo = Counter(t[3] for t in elbiral.values()
                               if t[2] > 0 and t[3])
            for n in self.jatekosok:
                w, allap, base, norm = elbiral[n]
                pont = base
                egyedi = base > 0 and szamlalo.get(norm, 0) == 1
                if egyedi:
                    pont += 2
                korpont[n] += pont
                detail[n][k] = {"szo": w, "allapot": allap, "pont": pont,
                                "egyedi": egyedi}
        for n in self.jatekosok:
            self.osszpont[n] += korpont[n]
        self.fazis = "eredmeny"
        self.kor_eredmeny = {"betu": self.betu, "korpont": korpont,
                             "detail": detail}
        return self.kor_eredmeny

    # ---------------------------------------------------------------- állapot
    def allapot_publikus(self, uzenet=""):
        return {
            "fazis": self.fazis, "kor": self.kor, "betu": self.betu,
            "kulcsok": list(self.kulcsok),
            "kategoria_nevek": {k: OV.KATEGORIA_NEVEK.get(k, k)
                                for k in self.kulcsok},
            "jatekosok": list(self.jatekosok),
            "osszpont": dict(self.osszpont),
            "beadtak": sorted(self.valaszok.keys()),
            "eredmeny": self.kor_eredmeny, "uzenet": uzenet,
        }


# ============================ ONLINE panel (fül) =============================

import wx

from . import netroom
from .netpanel import NetPanelMixin

# a helyben pörgetett magyar ábécé (a stoppoló SAJÁT betűje számít – nulla
# hálózati késés, mert minden gép magának pörgeti)
_ABECE = ("a", "á", "b", "c", "d", "e", "é", "f", "g", "h", "i", "í", "j", "k",
          "l", "m", "n", "o", "ó", "ö", "ő", "p", "q", "r", "s", "t", "u", "ú",
          "ü", "ű", "v", "w", "x", "y", "z")

OV_ONLINE_SUGO = (
    "ORSZÁG-VÁROS ONLINE – SÚGÓ\n\n"
    "Több gépről játszotok, csak internettel. A szobát nyitó játékos a HOST: ő "
    "indítja a köröket és nála fut a hiteles pontozás.\n\n"
    "BELÉPÉS\n"
    "• Írd be a NEVED. Ha TE szervezed: „Új szoba” → KÓD, „Kód másolása”, küldd "
    "el. A HOST beállíthatja a kategóriákat (klasszikus 4 vagy bővített), majd "
    "„Játék indítása”. Ha CSATLAKOZOL: kód + „Csatlakozás”.\n\n"
    "EGY KÖR\n"
    "1) A HOST „Kör indítása”. MINDEN gépen pörögni kezd az ábécé (a, á, b, c…) "
    "– mindenki a SAJÁT gépén hallja.\n"
    "2) Amikor jó betűnél jársz, nyomd meg a STOP-ot (vagy a szóközt). Aki "
    "ELSŐNEK állít meg, annak a betűje lesz a köré – SOHA nem a gép dönt!\n"
    "3) Írj MINDEN kategóriához egy azzal a betűvel kezdődő szót, majd „Kész!”. "
    "Aki elsőként végez, elindít egy rövid visszaszámlálást a többieknek.\n"
    "4) Pontozás: rossz betű vagy üres = 0; jó betű = 1; ha a szótárban is "
    "benne van = 2; és +2 EGYEDISÉGI bónusz, ha rajtad kívül más nem írta "
    "ugyanazt! Mindent felolvasunk, az összpont körönként gyűlik.\n\n"
    "Csevegés az ablak alján. Csak internet kell."
)


class OrszagVarosOnlinePanel(NetPanelMixin, wx.Panel):
    """Host-authoritative ONLINE Ország-Város. Valós idejű: az ábécét minden gép
    HELYBEN pörgeti, az első STOP betűje a köré; utána mindenki űrlapba ír, a
    host begyűjt és pontoz (alappont + egyediségi bónusz)."""

    HELYI_NEV = "helyi Ország-Város"

    def __init__(self, parent, main):
        super().__init__(parent)
        self.main = main
        self._closing = False
        self._szoba = None
        self._host = False
        self._motor = None
        self._nev = "Játékos"
        self._jatekosok = []
        self._fazis = "lobbi"
        self._kulcsok = []
        self._katnev = {}
        self._betu = ""
        self._mezok = {}
        self._beadtam = False
        self._abc_idx = 0
        self._abc_fut = False
        self._siet_hatra = 0
        self._hang_player = None
        self._build()
        wx.CallAfter(self._start_ellenoriz)

    # -------------------------------------------------------------- felület
    def _build(self):
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(self, label=(
            "Ország-Város-Fiú-Lány TÖBB gépről – aki elsőként állítja meg az "
            "ábécét, annak a betűje jön! Súgó: F1.")), 0, wx.ALL, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        sor.Add(wx.StaticText(self, label="A &neved:"),
                0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.nev_mezo = wx.TextCtrl(self, value=self._alap_nev())
        self.nev_mezo.SetName("A neved")
        sor.Add(self.nev_mezo, 1)
        v.Add(sor, 0, wx.EXPAND | wx.ALL, 8)
        self._sor_nev = sor

        lob = wx.BoxSizer(wx.HORIZONTAL)
        self.uj_gomb = wx.Button(self, label="Ú&j szoba (én szervezem)")
        self.uj_gomb.Bind(wx.EVT_BUTTON, self._uj_szoba)
        lob.Add(self.uj_gomb, 0, wx.RIGHT, 6)
        lob.Add(wx.StaticText(self, label="&kód:"),
                0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.kod_mezo = wx.TextCtrl(self, size=(90, -1))
        self.kod_mezo.SetName("Szobakód")
        lob.Add(self.kod_mezo, 0, wx.RIGHT, 4)
        self.masol_gomb = wx.Button(self, label="Kód &másolása")
        self.masol_gomb.Bind(wx.EVT_BUTTON, self._kod_masol)
        lob.Add(self.masol_gomb, 0, wx.RIGHT, 6)
        self.csat_gomb = wx.Button(self, label="&Csatlakozás")
        self.csat_gomb.Bind(wx.EVT_BUTTON, self._csatlakozas)
        lob.Add(self.csat_gomb, 0, wx.RIGHT, 6)
        self.indit_gomb = wx.Button(self, label="Játék &indítása")
        self.indit_gomb.Bind(wx.EVT_BUTTON, self._indit)
        self.indit_gomb.Disable()
        lob.Add(self.indit_gomb, 0)
        v.Add(lob, 0, wx.ALL, 8)
        self._sor_lob = lob

        # kategória-mód (a HOST állítja indítás előtt)
        mod = wx.BoxSizer(wx.HORIZONTAL)
        mod.Add(wx.StaticText(self, label="&Kategóriák:"),
                0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.mod_valaszto = wx.Choice(self, choices=[
            "Klasszikus (Ország, Város, Fiú, Lány)",
            "Bővített (mind a 11 kategória)"])
        self.mod_valaszto.SetSelection(0)
        self.mod_valaszto.SetName("Kategóriák módja")
        mod.Add(self.mod_valaszto, 0)
        v.Add(mod, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self._sor_mod = mod

        # állás + kör-vezérlés
        self._allapot_mezo = wx.TextCtrl(self, style=wx.TE_READONLY)
        self._allapot_mezo.SetName("Állás")
        v.Add(self._allapot_mezo, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

        vez = wx.BoxSizer(wx.HORIZONTAL)
        self.g_korindit = wx.Button(self, label="&Kör indítása (host)")
        self.g_korindit.Bind(wx.EVT_BUTTON, self._kor_indit)
        vez.Add(self.g_korindit, 0, wx.RIGHT, 6)
        self.g_stop = wx.Button(self, label="&STOP – állítsd meg az ábécét!")
        self.g_stop.Bind(wx.EVT_BUTTON, lambda e: self._stop())
        vez.Add(self.g_stop, 0, wx.RIGHT, 6)
        self.g_kesz = wx.Button(self, label="Ké&sz! (beadom)")
        self.g_kesz.Bind(wx.EVT_BUTTON, lambda e: self._kesz())
        vez.Add(self.g_kesz, 0)
        v.Add(vez, 0, wx.ALL, 8)
        self._vez_sizer = vez

        # ŰRLAP (kategóriánként egy mező) – a start után épül fel
        self._urlap_cimke = wx.StaticText(self, label="A &szavaid:")
        v.Add(self._urlap_cimke, 0, wx.LEFT | wx.TOP, 8)
        self._urlap_sizer = wx.BoxSizer(wx.VERTICAL)
        v.Add(self._urlap_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        # eredmény
        self._eredmeny_mezo = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 90))
        self._eredmeny_mezo.SetName("A kör eredménye")
        v.Add(self._eredmeny_mezo, 0, wx.EXPAND | wx.ALL, 8)

        # csevegés
        self._chat_label = wx.StaticText(self, label="&Csevegés a játékosokkal:")
        v.Add(self._chat_label, 0, wx.LEFT | wx.TOP, 8)
        self.chat_atirat = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 48))
        self.chat_atirat.SetName("Csevegés a játékosokkal")
        v.Add(self.chat_atirat, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        csor = wx.BoxSizer(wx.HORIZONTAL)
        self.chat_be = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.chat_be.SetName("Írj a többieknek, Enter a küldés")
        self.chat_be.Bind(wx.EVT_TEXT_ENTER, lambda e: self._chat_kuld())
        csor.Add(self.chat_be, 1, wx.RIGHT, 6)
        self.chat_gomb = wx.Button(self, label="Kül&dés")
        self.chat_gomb.Bind(wx.EVT_BUTTON, lambda e: self._chat_kuld())
        csor.Add(self.chat_gomb, 0)
        v.Add(csor, 0, wx.EXPAND | wx.ALL, 8)
        self._csor_sizer = csor

        self._naplo = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 60))
        self._naplo.SetName("A játék menete, csak olvasható")
        v.Add(self._naplo, 0, wx.EXPAND | wx.ALL, 8)

        self.SetSizer(v)
        self._v = v
        self._jatek_widgetek = [self._allapot_mezo, self._urlap_cimke,
                                self._eredmeny_mezo, self._chat_label,
                                self.chat_atirat, self._naplo]
        self._jatek_sizerek = [self._vez_sizer, self._urlap_sizer,
                               self._csor_sizer]
        self._gomb_allapot("lobbi")
        self._szoba_reszek_lathato(False)

    # -------------------------------------------------------------- lobbi
    def _indit(self, e):
        if not self._host or not self._szoba:
            return
        if len(self._jatekosok) < 2:
            self._mondd("Legalább két játékos kell – várj, míg csatlakoznak!")
            return
        from .orszagvaros_online import OrszagVarosHost
        from .jatekok import orszagvaros as OV
        if self.mod_valaszto.GetSelection() == 1:
            kulcsok = list(OV.ALAP_KULCSOK) + list(OV.EXTRA_KULCSOK)
        else:
            kulcsok = list(OV.ALAP_KULCSOK)
        self._motor = OrszagVarosHost(self._jatekosok, kulcsok=kulcsok)
        self.indit_gomb.Disable()
        self.mod_valaszto.Disable()
        self._szoba.kuld("start", {
            "jatekosok": self._jatekosok, "kulcsok": kulcsok,
            "katnev": self._motor.allapot_publikus()["kategoria_nevek"]})

    # -------------------------------------------------------------- hálózat
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
                    self._mondd(f"{nev} csatlakozott! Játékosok: "
                                + ", ".join(self._jatekosok) + ".")
        elif tipus == "start":
            self._jatekosok = adat.get("jatekosok", self._jatekosok)
            self._kulcsok = adat.get("kulcsok", [])
            self._katnev = adat.get("katnev", {})
            self._urlap_epit()
            self._fazis = "keszen"
            self._gomb_allapot("keszen")
            self._mondd("Indul az Ország-Város! Játékosok: "
                        + ", ".join(self._jatekosok) + ". Kategóriák: "
                        + ", ".join(self._katnev.get(k, k)
                                    for k in self._kulcsok)
                        + ". A host indítja az első kört!")
        elif tipus == "korkezd":
            self._kor_kezdodik()
        elif tipus == "stop":
            if self._host and self._motor and self._fazis == "betuzes":
                if self._motor.betu_rogzit(adat.get("betu", "")):
                    self._szoba.kuld("betu", {"betu": self._motor.betu,
                                              "ki": ki})
        elif tipus == "betu":
            self._betu_jott(adat.get("betu", ""), adat.get("ki", ""))
        elif tipus == "valasz":
            if self._host and self._motor and self._fazis == "iras":
                elso = len(self._motor.valaszok) == 0
                self._motor.valasz_be(ki, adat.get("valaszok", {}))
                if elso:
                    self._szoba.kuld("siet", {"mp": 20, "ki": ki})
                    self._host_zar_idozit()
                if self._motor.mindenki_beadott():
                    self._host_zar()
        elif tipus == "siet":
            self._siet_jott(adat.get("mp", 20), adat.get("ki", ""))
        elif tipus == "eredmeny":
            self._eredmeny_jott(adat)
        elif tipus == "csevej":
            self._chat_fogad(ki, adat)

    # -------------------------------------------------------------- kör
    def _kor_indit(self, e):
        if not self._host or not self._szoba or not self._motor:
            self._mondd("A kört a szoba szervezője (host) indítja.")
            return
        if self._fazis not in ("keszen", "eredmeny"):
            return
        self._motor.kor_indit()
        self._szoba.kuld("korkezd", {"kor": self._motor.kor})

    def _kor_kezdodik(self):
        self._fazis = "betuzes"
        self._betu = ""
        self._beadtam = False
        self._eredmeny_mezo.SetValue("")
        for m in self._mezok.values():
            m.SetValue("")
        self._gomb_allapot("betuzes")
        self._mondd("Pörög az ábécé! Nyomd meg a STOP-ot (vagy a szóközt), "
                    "amikor jó betűnél jársz!")
        self._abc_start()

    def _abc_start(self):
        self._abc_idx = 0
        self._abc_fut = True
        self._abc_tick()

    def _abc_tick(self):
        if self._closing or not self._abc_fut or self._fazis != "betuzes":
            return
        betu = _ABECE[self._abc_idx % len(_ABECE)]
        self._allapot_mezo.SetValue("Ábécé pörög… most: %s" % betu.upper())
        self._mondd(betu.upper())
        self._abc_idx += 1
        wx.CallLater(750, self._abc_tick)

    def _stop(self):
        if self._fazis != "betuzes" or not self._abc_fut:
            return
        self._abc_fut = False
        betu = _ABECE[(self._abc_idx - 1) % len(_ABECE)]
        self._mondd("Megállítottad: %s! Küldöm a hostnak…" % betu.upper())
        if self._szoba:
            self._szoba.kuld("stop", {"betu": betu})

    def _betu_jott(self, betu, ki):
        self._abc_fut = False
        self._betu = (betu or "").lower()
        self._fazis = "iras"
        self._beadtam = False
        self._gomb_allapot("iras")
        kie = "Te állítottad meg" if ki == self._nev else ("%s állította meg" % ki)
        self._allapot_mezo.SetValue(
            "A KÖR BETŰJE: %s (%s). Írj minden kategóriához egy %s-vel kezdődő "
            "szót!" % (self._betu.upper(), kie, self._betu.upper()))
        self._mondd("A kör betűje: %s! %s. Írj minden kategóriához egy %s "
                    "betűvel kezdődő szót, aztán Kész!"
                    % (self._betu.upper(), kie, self._betu.upper()))
        # fókusz az első mezőre
        try:
            if self._kulcsok:
                self._mezok[self._kulcsok[0]].SetFocus()
        except Exception:
            pass

    def _kesz(self):
        if self._fazis != "iras" or self._beadtam:
            return
        valaszok = {k: (self._mezok[k].GetValue() or "").strip()
                    for k in self._kulcsok}
        self._beadtam = True
        self._gomb_allapot("beadva")
        if self._szoba:
            self._szoba.kuld("valasz", {"valaszok": valaszok})
        self._mondd("Beadtad a szavaidat! Várjuk a többieket…")

    def _siet_jott(self, mp, ki):
        if self._beadtam or self._fazis != "iras":
            return
        if ki != self._nev:
            self._mondd("%s végzett! %d másodperced van befejezni!"
                        % (ki or "Valaki", mp))
        self._siet_hatra = int(mp)
        self._siet_tick()

    def _siet_tick(self):
        if self._closing or self._beadtam or self._fazis != "iras":
            return
        if self._siet_hatra <= 0:
            self._mondd("Lejárt az idő – beadom, amit eddig beírtál!")
            self._kesz()
            return
        if self._siet_hatra in (10, 5, 3, 2, 1):
            self._mondd("%d…" % self._siet_hatra)
        self._siet_hatra -= 1
        wx.CallLater(1000, self._siet_tick)

    # ---- host oldali zárás ----
    def _host_zar_idozit(self):
        wx.CallLater(26000, self._host_zar)

    def _host_zar(self):
        if not (self._host and self._motor) or self._fazis != "iras":
            return
        # aki nem adott be, üres válasszal zárul
        for n in self._motor.jatekosok:
            if n not in self._motor.valaszok:
                self._motor.valasz_be(n, {})
        self._motor.ertekel()
        self._szoba.kuld("eredmeny", self._motor.allapot_publikus(
            "Vége a körnek – itt az eredmény!"))

    def _eredmeny_jott(self, a):
        self._fazis = "eredmeny"
        self._betu = a.get("betu", "")
        self._gomb_allapot("eredmeny")
        er = a.get("eredmeny", {}) or {}
        korpont = er.get("korpont", {})
        detail = er.get("detail", {})
        osszpont = a.get("osszpont", {})
        katnev = a.get("kategoria_nevek", self._katnev)
        kulcsok = a.get("kulcsok", self._kulcsok)
        sorok = ["A(z) %s betűs kör eredménye:" % (self._betu.upper() or "?")]
        for n in a.get("jatekosok", []):
            reszek = []
            for k in kulcsok:
                d = (detail.get(n, {}) or {}).get(k, {})
                szo = d.get("szo", "") or "—"
                reszek.append("%s: %s (%d)" % (katnev.get(k, k), szo,
                                               d.get("pont", 0)))
            sorok.append("%s – %d pont ebben a körben. %s"
                         % (n, korpont.get(n, 0), "; ".join(reszek)))
        # összesített állás
        rangsor = sorted(osszpont.items(), key=lambda kv: kv[1], reverse=True)
        sorok.append("Összesített állás: "
                     + ", ".join("%s %d" % (nn, pp) for nn, pp in rangsor))
        szoveg = "\n".join(sorok)
        self._eredmeny_mezo.SetValue(szoveg)
        self._allapot_mezo.SetValue(
            "Kör vége. " + ("A host indíthat új kört." if not self._host
                            else "Indíthatsz új kört!"))
        # a saját eredmény + vezető felolvasása
        enyem = korpont.get(self._nev, 0)
        vezeto = rangsor[0][0] if rangsor else ""
        self._mondd("Vége a körnek! Te %d pontot szereztél. Összesítve %d "
                    "pontod van. Jelenleg %s vezet. %s"
                    % (enyem, osszpont.get(self._nev, 0), vezeto,
                       "Indíthatsz új kört!" if self._host
                       else "Várd a host új körét!"))
        self._hang("taps")

    # -------------------------------------------------------------- gombok
    def _gomb_allapot(self, fazis):
        # melyik gomb aktív melyik fázisban
        try:
            self.g_korindit.Enable(self._host and fazis in ("keszen", "eredmeny"))
            self.g_stop.Enable(fazis == "betuzes")
            irhat = (fazis == "iras")
            self.g_kesz.Enable(irhat)
            for m in self._mezok.values():
                m.Enable(irhat)
        except Exception:
            pass

    def _urlap_epit(self):
        # a kategória-mezők felépítése (a start után, a kulcsok ismeretében)
        self._urlap_sizer.Clear(delete_windows=True)
        self._mezok = {}
        for k in self._kulcsok:
            sor = wx.BoxSizer(wx.HORIZONTAL)
            cimke = wx.StaticText(self, label=self._katnev.get(k, k) + ":",
                                  size=(120, -1))
            sor.Add(cimke, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
            mezo = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
            mezo.SetName(self._katnev.get(k, k))
            mezo.Bind(wx.EVT_TEXT_ENTER, lambda e: self._kesz())
            mezo.Enable(False)
            sor.Add(mezo, 1)
            self._urlap_sizer.Add(sor, 0, wx.EXPAND | wx.BOTTOM, 4)
            self._mezok[k] = mezo
        self._v.Layout()

    # -------------------------------------------------------------- csevegés
    # a lobbi/chat/net/hang/_mondd közös részét a NetPanelMixin adja
    def leallit(self):
        self._abc_fut = False          # az ábécé-pörgetés leállítása
        super().leallit()
