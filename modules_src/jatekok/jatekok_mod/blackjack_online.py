# -*- coding: utf-8 -*-
"""Blackjack – host-authoritative ONLINE motor (fejetlen, wx és hálózat nélkül).

A közös online-héj második motorja. A blackjackben a játékos-lapok NYÍLTAK, így
itt nincs bonyolult magánkéz – EGYETLEN rejtett elem az OSZTÓ lefordított lapja,
amit a host nem broadcastol, amíg le nem jön az osztó köre (`oszto_rejtett`).

Több játékos EGY közös osztó ellen: mindenki kap 2 lapot (az osztó 1 nyílt + 1
rejtett), sorban HÍV LAPOT / MEGÁLL / DUPLÁZ, majd az osztó 17-ig húz, és
mindenki külön elszámol az osztóval. Fix tét, egyszerű zseton-rendszer. A
szabályok közkincsek; a lap-összeg (ász 11/1) a helyi Blackjackkel azonos.
"""
import random

_SZINEK = ["pikk", "kör", "káró", "treff"]
_RANGOK = ["ász", "2", "3", "4", "5", "6", "7", "8", "9", "10",
           "bubi", "dáma", "király"]


def _ertek(rang):
    if rang == "ász":
        return 11
    if rang in ("bubi", "dáma", "király", "10"):
        return 10
    return int(rang)


def osszeg(kez):
    """A kéz blackjack-összege; az ászok 11→1-re csökkennek, amíg kell."""
    o = sum(_ertek(r) for _, r in kez)
    aszok = sum(1 for _, r in kez if r == "ász")
    while o > 21 and aszok:
        o -= 10
        aszok -= 1
    return o


def blackjack(kez):
    return len(kez) == 2 and osszeg(kez) == 21


def lap_nev(k):
    return "%s %s" % (k[1], k[0])


def kez_nev(kez):
    return ", ".join(lap_nev(k) for k in kez) if kez else "(nincs lap)"


class BlackjackHost:
    """Host-oldali blackjack több játékossal EGY osztó ellen. Fázisok:
    „jatek" (a játékosok sorban cselekszenek), „vege" (a kör elszámolva)."""

    def __init__(self, jatekosok, kezdo_zseton=100, tet=10):
        self.jatekosok = [j for j in jatekosok if j] or ["Játékos"]
        self.alap_tet = int(tet)
        self.zseton = {n: int(kezdo_zseton) for n in self.jatekosok}
        self.kor = 0
        self.fazis = "keszen"
        self.uj_leosztas()

    # ------------------------------------------------------------------ osztás
    def _uj_pakli(self):
        p = [(sz, r) for sz in _SZINEK for r in _RANGOK]
        random.shuffle(p)
        return p

    def uj_leosztas(self):
        """Új kör: tétlevonás, osztás, természetes blackjackek. A host hívja."""
        self.pakli = self._uj_pakli()
        self.kor += 1
        self.tet = {}
        self.kezek = {}
        self.statusz = {}          # jatszik / all / bust / blackjack / kihagy
        self.eredmeny = {}
        for n in self.jatekosok:
            if self.zseton[n] >= self.alap_tet:
                self.zseton[n] -= self.alap_tet
                self.tet[n] = self.alap_tet
                self.kezek[n] = [self.pakli.pop(), self.pakli.pop()]
                self.statusz[n] = "jatszik"
            else:
                self.tet[n] = 0
                self.kezek[n] = []
                self.statusz[n] = "kihagy"
        self.oszto = [self.pakli.pop(), self.pakli.pop()]   # [nyílt, rejtett]
        self.oszto_rejtett = True
        for n in self.jatekosok:
            if self.statusz[n] == "jatszik" and blackjack(self.kezek[n]):
                self.statusz[n] = "blackjack"
        self.fazis = "jatek"
        self.aktiv_idx = None
        for i, n in enumerate(self.jatekosok):
            if self.statusz[n] == "jatszik":
                self.aktiv_idx = i
                break
        if self.aktiv_idx is None:          # mindenki bj vagy kihagy
            self._oszto_es_zaras()

    # --------------------------------------------------------------- lekérdezők
    @property
    def soron(self):
        if self.fazis == "jatek" and self.aktiv_idx is not None:
            return self.jatekosok[self.aktiv_idx]
        return ""

    def allapot_publikus(self, uzenet=""):
        if self.oszto_rejtett:
            oszto_lapok = [self.oszto[0], ("rejtett", "rejtett")]
            oszto_osszeg = None
        else:
            oszto_lapok = list(self.oszto)
            oszto_osszeg = osszeg(self.oszto)
        return {
            "fazis": self.fazis, "kor": self.kor, "soron": self.soron,
            "oszto_lapok": [list(k) for k in oszto_lapok],
            "oszto_osszeg": oszto_osszeg,
            "kezek": {n: [list(k) for k in self.kezek[n]] for n in self.jatekosok},
            "osszegek": {n: (osszeg(self.kezek[n]) if self.kezek[n] else 0)
                         for n in self.jatekosok},
            "statusz": dict(self.statusz), "zseton": dict(self.zseton),
            "tet": dict(self.tet), "eredmeny": dict(self.eredmeny),
            "jatekosok": list(self.jatekosok), "uzenet": uzenet,
        }

    # ------------------------------------------------------------------ belső
    def _kov_aktiv(self):
        for i in range(self.aktiv_idx + 1, len(self.jatekosok)):
            if self.statusz[self.jatekosok[i]] == "jatszik":
                return i
        return None

    def _lep_kov(self):
        nxt = self._kov_aktiv()
        if nxt is None:
            self._oszto_es_zaras()
        else:
            self.aktiv_idx = nxt

    def _oszto_es_zaras(self):
        self.oszto_rejtett = False
        verseny = any(self.statusz[n] in ("all", "blackjack")
                      for n in self.jatekosok)
        if verseny:
            while osszeg(self.oszto) < 17:
                self.oszto.append(self.pakli.pop())
        self._elszamol()
        self.fazis = "vege"
        self.aktiv_idx = None

    def _elszamol(self):
        oo = osszeg(self.oszto)
        oszto_bj = blackjack(self.oszto)
        oszto_bust = oo > 21
        for n in self.jatekosok:
            st = self.statusz[n]
            if st == "kihagy":
                self.eredmeny[n] = "kihagyta (nincs elég zseton)"
                continue
            if st == "bust":
                self.eredmeny[n] = "vesztett – befuccsolt"
                continue
            if st == "blackjack":
                if oszto_bj:
                    self.zseton[n] += self.tet[n]
                    self.eredmeny[n] = "döntetlen – mindkettő blackjack"
                else:
                    self.zseton[n] += int(self.tet[n] * 2.5)
                    self.eredmeny[n] = "BLACKJACK! 3:2 nyeremény"
                continue
            jo = osszeg(self.kezek[n])            # st == "all"
            if oszto_bust or jo > oo:
                self.zseton[n] += self.tet[n] * 2
                self.eredmeny[n] = "nyert"
            elif jo == oo:
                self.zseton[n] += self.tet[n]
                self.eredmeny[n] = "döntetlen"
            else:
                self.eredmeny[n] = "vesztett"

    # ------------------------------------------------------------------ akció
    def akcio(self, ki, tipus, adat=None):
        if self.fazis != "jatek" or self.aktiv_idx is None:
            return None
        aktiv = self.jatekosok[self.aktiv_idx]
        if ki != aktiv or self.statusz[ki] != "jatszik":
            return None

        if tipus == "hit":
            self.kezek[ki].append(self.pakli.pop())
            o = osszeg(self.kezek[ki])
            uz = f"{ki} lapot kért: {lap_nev(self.kezek[ki][-1])}, összeg {o}."
            if o > 21:
                self.statusz[ki] = "bust"
                uz += f" {ki} túllépte a 21-et – befuccsolt!"
                self._lep_kov()
            return self.allapot_publikus(uz)

        if tipus == "stand":
            self.statusz[ki] = "all"
            uz = f"{ki} megáll {osszeg(self.kezek[ki])}-nél."
            self._lep_kov()
            return self.allapot_publikus(uz)

        if tipus == "dupla":
            if len(self.kezek[ki]) != 2 or self.zseton[ki] < self.tet[ki]:
                return self.allapot_publikus(
                    f"{ki}: duplázni csak az első két lappal és elég zsetonnal "
                    "lehet.")
            self.zseton[ki] -= self.tet[ki]
            self.tet[ki] *= 2
            self.kezek[ki].append(self.pakli.pop())
            o = osszeg(self.kezek[ki])
            uz = (f"{ki} DUPLÁZOTT, kapott: {lap_nev(self.kezek[ki][-1])}, "
                  f"összeg {o}.")
            if o > 21:
                self.statusz[ki] = "bust"
                uz += f" {ki} befuccsolt!"
            else:
                self.statusz[ki] = "all"
            self._lep_kov()
            return self.allapot_publikus(uz)

        return None


# ============================ ONLINE panel (fül) =============================

import wx

from . import netroom

BJ_ONLINE_SUGO = (
    "BLACKJACK ONLINE – SÚGÓ\n\n"
    "Több gépről játszotok EGY közös osztó ellen, csak internettel. A szobát "
    "nyitó játékos a HOST: nála fut a hiteles játék, ő oszt. A lapok NYÍLTAK "
    "(mindenki látja mindenkiét); csak az osztó egyik lapja rejtett, amíg le "
    "nem jön az ő köre.\n\n"
    "BELÉPÉS\n"
    "• Írd be a NEVED.\n"
    "• Ha TE szervezed: „Új szoba” → KÓD, „Kód másolása”, küldd el. Amikor mind "
    "bent vannak: „Játék indítása”.\n"
    "• Ha CSATLAKOZOL: írd a kód mezőbe a KÓDOT, majd „Csatlakozás”.\n\n"
    "AMIKOR TE JÖSSZ\n"
    "• „Lapot kérek” (Hit): húzol egy lapot; ha 21 fölé mész, befuccsolsz.\n"
    "• „Megállok” (Stand): lezárod a kezed.\n"
    "• „Duplázás”: csak az első két lappal – dupla tét, PONTOSAN egy lap, aztán "
    "megállsz.\n"
    "Amikor mindenki végzett, az osztó 17-ig húz, és mindenki külön elszámol "
    "(nyer/veszít/döntetlen; a természetes blackjack 3:2-t fizet). A HOST az „Új "
    "kör” gombbal oszthat újra.\n\n"
    "SZÜNET és CSEVEGÉS\n"
    "A HOST a „Szünet” gombbal megállíthatja a játékot; az ablak alján bármikor "
    "csevegtek. Minden lépés FELOLVASVA hangzik el. Csak internet kell."
)


class BlackjackOnlinePanel(wx.Panel):
    """Host-authoritative ONLINE Blackjack: több játékos egy közös osztó ellen.
    A lapok nyíltak → nincs magánkéz-routing, a host a teljes publikus állapotot
    broadcastolja. Lobbi + felolvasott játék + csevegés + (host) szünet/új kör."""

    def __init__(self, parent, main):
        super().__init__(parent)
        self.main = main
        self._closing = False
        self._szoba = None
        self._host = False
        self._motor = None
        self._nev = "Játékos"
        self._jatekosok = []
        self._soron = ""
        self._fazis = "lobbi"
        self._szunet = False
        self._allapot = {}
        self._hang_player = None
        self._build()
        wx.CallAfter(self._start_ellenoriz)

    # -------------------------------------------------------------- felület
    def _build(self):
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(self, label=(
            "Blackjack TÖBB gépről, egy közös osztó ellen – csak internet kell! "
            "A lapok nyíltak. Súgó: F1.")), 0, wx.ALL, 8)

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

        v.Add(wx.StaticText(self, label="Az &asztal (osztó és játékosok):"),
              0, wx.LEFT | wx.TOP, 8)
        self._tabla = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 150))
        self._tabla.SetName("Az asztal")
        v.Add(self._tabla, 1, wx.EXPAND | wx.ALL, 8)

        akc = wx.BoxSizer(wx.HORIZONTAL)
        self.g_hit = wx.Button(self, label="&Lapot kérek")
        self.g_hit.Bind(wx.EVT_BUTTON, lambda e: self._akcio("hit"))
        akc.Add(self.g_hit, 0, wx.RIGHT, 6)
        self.g_stand = wx.Button(self, label="&Megállok")
        self.g_stand.Bind(wx.EVT_BUTTON, lambda e: self._akcio("stand"))
        akc.Add(self.g_stand, 0, wx.RIGHT, 6)
        self.g_dupla = wx.Button(self, label="&Duplázás")
        self.g_dupla.Bind(wx.EVT_BUTTON, lambda e: self._akcio("dupla"))
        akc.Add(self.g_dupla, 0, wx.RIGHT, 6)
        self.g_ujkor = wx.Button(self, label="Ú&j kör")
        self.g_ujkor.Bind(wx.EVT_BUTTON, self._uj_kor)
        akc.Add(self.g_ujkor, 0, wx.RIGHT, 6)
        self.g_szunet = wx.Button(self, label="&Szünet")
        self.g_szunet.Bind(wx.EVT_BUTTON, self._szunet_valt)
        akc.Add(self.g_szunet, 0)
        v.Add(akc, 0, wx.ALL, 8)
        self._akc_sizer = akc

        self._chat_label = wx.StaticText(self, label="&Csevegés a játékosokkal:")
        v.Add(self._chat_label, 0, wx.LEFT | wx.TOP, 8)
        self.chat_atirat = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 56))
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
            size=(-1, 70))
        self._naplo.SetName("A játék menete, csak olvasható")
        v.Add(self._naplo, 0, wx.EXPAND | wx.ALL, 8)

        self.SetSizer(v)
        self._v = v
        self._jatek_widgetek = [self._tabla, self._chat_label, self.chat_atirat,
                                self._naplo]
        self._jatek_sizerek = [self._akc_sizer, self._csor_sizer]
        self._vezerlok_engedely(False)
        self._szoba_reszek_lathato(False)

    def _alap_nev(self):
        try:
            s = getattr(self.main, "settings", {}) or {}
            return (s.get("nev") or s.get("felhasznalo") or "").strip() or "Játékos"
        except Exception:
            return "Játékos"

    def _start_ellenoriz(self):
        if not netroom.ably_kulcs():
            self._mondd("Az online játék ebben a verzióban még nem elérhető. A "
                        "helyi Blackjack a másik fülön viszont mindig megy!")

    # -------------------------------------------------------------- lobbi
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
        self._szoba_reszek_lathato(True)
        self.kod_mezo.SetValue(kod)
        self.uj_gomb.Disable()
        self.csat_gomb.Disable()
        self.indit_gomb.Enable()
        self._mondd(f"Szoba nyitva! A kódod: {kod} (betűnként: {' '.join(kod)}). "
                    "Másold és küldd el a haverjaidnak, és ha mind bent vannak, "
                    "indítsd a játékot!")

    def _kod_masol(self, e):
        kod = (self.kod_mezo.GetValue() or "").strip()
        if not kod:
            self._mondd("Előbb nyiss egy szobát – akkor lesz kód a másoláshoz.")
            return
        try:
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(kod))
                wx.TheClipboard.Close()
                self._mondd(f"A(z) {kod} kód a vágólapon!")
        except Exception:
            self._mondd(f"A kód: {kod} – mondd be a többieknek.")

    def _csatlakozas(self, e):
        self._nev = (self.nev_mezo.GetValue() or "Játékos").strip()
        kod = (self.kod_mezo.GetValue() or "").strip().upper()
        if not kod:
            self._mondd("Írd be a szobakódot, amit a szervező mondott.")
            return
        self._szoba = netroom.NetSzoba(kod, self._nev)
        if not self._szoba.elerheto():
            self._mondd("Nincs online kulcs beállítva – nem tudok csatlakozni.")
            return
        self._host = False
        self._szoba.figyel(self._uzenet_jott)
        self._szoba_reszek_lathato(True)
        self._szoba.kuld("csatlakozott", {"nev": self._nev})
        self.uj_gomb.Disable()
        self.csat_gomb.Disable()
        self._mondd(f"Csatlakoztál a(z) {kod} szobához {self._nev} néven. "
                    "Várd, hogy a szervező elindítsa a játékot!")

    def _indit(self, e):
        if not self._host or not self._szoba:
            return
        if len(self._jatekosok) < 2:
            self._mondd("Legalább két játékos kell – várj, míg csatlakoznak!")
            return
        from .blackjack_online import BlackjackHost
        self._motor = BlackjackHost(self._jatekosok)
        self.indit_gomb.Disable()
        self._szoba.kuld("start", {"jatekosok": self._jatekosok})
        self._broadcast(f"Kezdődik a Blackjack {len(self._jatekosok)} "
                        "játékossal! Mindenki kapott két lapot.")

    def _broadcast(self, uzenet=""):
        if not (self._host and self._motor and self._szoba):
            return
        self._szoba.kuld("allapot", self._motor.allapot_publikus(uzenet))

    # -------------------------------------------------------------- hálózat
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
                    self._mondd(f"{nev} csatlakozott! Játékosok: "
                                + ", ".join(self._jatekosok) + ".")
        elif tipus == "start":
            self._jatekosok = adat.get("jatekosok", self._jatekosok)
            self._mondd("Indul a Blackjack! Játékosok: "
                        + ", ".join(self._jatekosok) + ".")
        elif tipus == "akcio":
            if self._host and self._motor and not self._szunet:
                allap = self._motor.akcio(ki, adat.get("tipus"),
                                          adat.get("adat"))
                if allap is not None:
                    self._szoba.kuld("allapot", allap)
        elif tipus == "uj_kor":
            if self._host and self._motor and not self._szunet:
                self._motor.uj_leosztas()
                self._broadcast("Új kör! Mindenki kapott két lapot.")
        elif tipus == "allapot":
            self._render_publikus(adat)
        elif tipus == "szunet":
            self._szunet = bool(adat.get("be"))
            if self._szunet:
                self._mondd("A játék SZÜNETEL (a host állította meg). "
                            "Addig csak csevegni lehet.")
            else:
                self._mondd("A játék FOLYTATÓDIK!")
            self._vezerlok_engedely_allapot()
        elif tipus == "csevej":
            self._chat_fogad(ki, adat)

    # -------------------------------------------------------------- render
    def _enyem(self):
        st = (self._allapot.get("statusz", {}) or {}).get(self._nev, "")
        return (self._fazis == "jatek" and self._soron == self._nev
                and st == "jatszik")

    def _lap_txt(self, k):
        if list(k) == ["rejtett", "rejtett"]:
            return "rejtett lap"
        return "%s %s" % (k[1], k[0])

    def _tabla_szoveg(self, a):
        sorok = []
        oo = a.get("oszto_osszeg")
        oszto = a.get("oszto_lapok", [])
        oszto_txt = ", ".join(self._lap_txt(k) for k in oszto) or "(nincs lap)"
        sorok.append("Osztó: %s%s" % (
            oszto_txt, "" if oo is None else " (összeg %d)" % oo))
        st = a.get("statusz", {})
        osszegek = a.get("osszegek", {})
        zseton = a.get("zseton", {})
        ered = a.get("eredmeny", {})
        cimkek = {"jatszik": "játszik", "all": "megállt", "bust": "befuccsolt",
                  "blackjack": "BLACKJACK", "kihagy": "kihagyja"}
        for n in a.get("jatekosok", []):
            kez = a.get("kezek", {}).get(n, [])
            kez_txt = ", ".join(self._lap_txt(k) for k in kez) or "(nincs lap)"
            reszek = ["%s: %s (összeg %d)" % (n, kez_txt, osszegek.get(n, 0))]
            reszek.append("[%s]" % cimkek.get(st.get(n, ""), st.get(n, "")))
            reszek.append("zseton %d" % zseton.get(n, 0))
            if ered.get(n):
                reszek.append("→ %s" % ered[n])
            jel = " ◄ TE" if n == self._nev else ""
            sorok.append("  ".join(reszek) + jel)
        return "\n".join(sorok)

    def _render_publikus(self, a):
        self._allapot = a
        self._fazis = a.get("fazis", "jatek")
        self._soron = a.get("soron", "")
        self._szoba_lobbi = (self._fazis == "lobbi")
        self._lobbi_lathato(self._fazis == "lobbi")
        uz = a.get("uzenet", "")
        self._hang_esemeny(uz, self._fazis)
        self._tabla.SetValue(self._tabla_szoveg(a))
        if uz:
            self._mondd(uz)
        self._vezerlok_engedely_allapot()
        if self._fazis == "vege":
            sajat = (a.get("eredmeny", {}) or {}).get(self._nev, "")
            if sajat:
                self._mondd("A te eredményed: %s. A host az „Új kör” gombbal "
                            "oszthat újra." % sajat)
            return
        if self._enyem() and not self._szunet:
            kez = a.get("kezek", {}).get(self._nev, [])
            self._mondd("TE JÖSSZ! Összeged %d. Lapot kérek, Megállok%s?"
                        % (a.get("osszegek", {}).get(self._nev, 0),
                           ", vagy Duplázás" if len(kez) == 2 else ""))
            try:
                self.g_hit.SetFocus()
            except Exception:
                pass

    def _vezerlok_engedely_allapot(self):
        enyem = self._enyem() and not self._szunet
        kez = (self._allapot.get("kezek", {}) or {}).get(self._nev, [])
        try:
            self.g_hit.Enable(enyem)
            self.g_stand.Enable(enyem)
            self.g_dupla.Enable(enyem and len(kez) == 2)
            self.g_ujkor.Enable(self._host and self._fazis == "vege"
                                and not self._szunet)
            self.g_szunet.Enable(self._host and self._fazis in ("jatek", "vege"))
        except Exception:
            pass

    def _vezerlok_engedely(self, be):
        for g in (self.g_hit, self.g_stand, self.g_dupla):
            try:
                g.Enable(be)
            except Exception:
                pass
        for g in (self.g_ujkor, self.g_szunet):
            try:
                g.Enable(False)
            except Exception:
                pass

    # -------------------------------------------------------------- akciók
    def _akcio(self, tipus):
        if not self._szoba or self._fazis != "jatek":
            return
        if self._szunet:
            self._mondd("A játék szünetel.")
            return
        if not self._enyem():
            self._mondd("Most nem te jössz – várj a köröodre.")
            return
        self._szoba.kuld("akcio", {"tipus": tipus, "adat": {}})

    def _uj_kor(self, e):
        if not self._host or not self._szoba:
            self._mondd("Új kört a szoba szervezője (host) oszthat.")
            return
        if self._fazis != "vege":
            self._mondd("Az új kör csak az aktuális kör vége után indítható.")
            return
        self._szoba.kuld("uj_kor", {})

    def _szunet_valt(self, e):
        if not self._host or not self._szoba:
            self._mondd("A szünetet a szoba szervezője (host) kapcsolhatja.")
            return
        self._szoba.kuld("szunet", {"be": not self._szunet})

    # -------------------------------------------------------------- csevegés
    def _chat_kuld(self):
        t = (self.chat_be.GetValue() or "").strip()
        if not t or not self._szoba:
            return
        self._szoba.kuld("csevej", {"szoveg": t})
        self.chat_be.SetValue("")
        self.chat_be.SetFocus()

    def _chat_fogad(self, ki, adat):
        szoveg = (adat.get("szoveg") or "").strip()
        if not szoveg:
            return
        sajat = (ki == self._nev)
        cimke = "Te" if sajat else (ki or "Valaki")
        try:
            self.chat_atirat.AppendText(f"{cimke}: {szoveg}\n")
        except Exception:
            pass
        if not sajat:
            self._mondd(f"{ki} üzenete: {szoveg}")

    # -------------------------------------------------------------- láthatóság
    def _szoba_reszek_lathato(self, latszik):
        try:
            for w in self._jatek_widgetek:
                w.Show(latszik)
            for s in self._jatek_sizerek:
                self._v.Show(s, latszik, recursive=True)
            self._v.Layout()
        except Exception:
            pass

    def _lobbi_lathato(self, latszik):
        try:
            self._v.Show(self._sor_nev, latszik, recursive=True)
            self._v.Show(self._sor_lob, latszik, recursive=True)
            self._v.Layout()
        except Exception:
            pass

    # -------------------------------------------------------------- hang
    def _hang(self, nev):
        try:
            import os
            from superdl.audioengine import Player
            mappa = os.path.join(os.path.dirname(__file__), "szerencsekerek_hang")
            ut = None
            for ext in (".wav", ".mp3"):
                p = os.path.join(mappa, nev + ext)
                if os.path.isfile(p):
                    ut = p
                    break
            if not ut:
                return
            if self._hang_player is None:
                self._hang_player = Player()
            self._hang_player.play(ut, "")
        except Exception:
            pass

    def _hang_esemeny(self, uzenet, fazis):
        u = uzenet or ""
        nev = None
        if "BLACKJACK! 3:2" in u:
            nev = "sikeres_tipp"
        elif "befuccsolt" in u:
            nev = "boo"
        elif fazis == "vege":
            nev = "taps"
        if nev:
            self._hang(nev)

    def _mondd(self, szoveg):
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
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            try:
                sv.speak(szoveg, force=True)
            except Exception:
                pass

    def leallit(self):
        self._closing = True
        try:
            if self._szoba:
                self._szoba.leallit()
        except Exception:
            pass
