# -*- coding: utf-8 -*-
"""UNO – host-authoritative ONLINE motor (fejetlen, wx és hálózat nélkül).

Ez a közös „online-héj" első alkalmazása a saját kártyajátékokra. A LÉNYEG a
MAGÁNKÉZ: a host oszt és a teljes állapotot ő tartja, de mindenki CSAK a saját
kezét kapja meg (`kez(nev)`), a többiektől csak a LAPSZÁMOT látja
(`allapot_publikus`). Így egy gépen sem lehet más lapjába lesni. A motor sem
wx-ről, sem Ably-ról nem tud → gépi teszttel teljesen ellenőrizhető, pontosan
mint a Szerencsekerék `OnlineHost`-ja.

A szabályok a `jatekok/sajat.py` konzolos `jatek_uno`-jával azonosak (ugyanazok
a segédfüggvények): színben/értékben egyező vagy Színkérő rakható; húzás után a
húzott lap LERAKHATÓ, ha illik; kihagyás/irányváltó/+2/+4; egy lapnál UNO, nulla
lapnál győzelem. Nincs laphúzás-stackelés és nincs +4-kihívás (egyszerű UNO).
"""
import random

import wx

from . import netroom
from .netpanel import NetPanelMixin
from .jatekok import sajat as SZK


class UnoHost:
    """Host-oldali UNO állapotgép. Akciókat kap, PUBLIKUS állapotot ad, a
    magánkezet külön (`kez`). Fázisok: „jatek", „huzas_utan", „vege"."""

    def __init__(self, jatekosok, kezdo_lapszam=7):
        self.jatekosok = [j for j in jatekosok if j] or ["Játékos"]
        self.n = len(self.jatekosok)
        self.kezdo_lapszam = int(kezdo_lapszam)
        self._oszt()

    # ------------------------------------------------------------------ osztás
    def _oszt(self):
        self.pakli = SZK._uno_pakli()
        self.dobo = []
        self.kezek = {nev: [self.pakli.pop() for _ in range(self.kezdo_lapszam)]
                      for nev in self.jatekosok}
        # kezdő felső lap: se akció, se Színkérő (ahogy a konzolban)
        while True:
            top = self.pakli.pop()
            if top[0] != "szín" and top[1] not in ("kihagy", "irany", "+2"):
                break
            self.pakli.insert(0, top)
        self.dobo.append(top)
        self.szin, self.ertek = top
        self.irany = 1
        self.aktiv_idx = 0
        self.fazis = "jatek"        # jatek / huzas_utan / vege
        self.gyoztes = None
        self._huzott = None         # a most húzott lap (huzas_utan fázisban)

    # --------------------------------------------------------------- lekérdezők
    @property
    def soron(self):
        return self.jatekosok[self.aktiv_idx]

    def kez(self, nev):
        """A NÉV játékos saját keze (csak neki küldendő)."""
        return list(self.kezek.get(nev, []))

    def allapot_publikus(self, uzenet=""):
        """Amit MINDENKI megkaphat – idegen lapok NÉLKÜL, csak lapszám."""
        return {
            "fazis": self.fazis,
            "soron": self.soron if self.fazis != "vege" else "",
            "felso": SZK._uno_top_nev(self.szin, self.ertek),
            "szin": self.szin, "ertek": self.ertek, "irany": self.irany,
            "lapszamok": {n: len(self.kezek[n]) for n in self.jatekosok},
            "jatekosok": list(self.jatekosok),
            "gyoztes": self.gyoztes, "pakli_db": len(self.pakli),
            "uzenet": uzenet,
        }

    # ------------------------------------------------------------------ belső
    def _huz(self, nev, db=1):
        for _ in range(db):
            if not self.pakli:
                if len(self.dobo) <= 1:
                    return
                felso = self.dobo[-1]
                maradek = self.dobo[:-1]
                random.shuffle(maradek)
                self.pakli, self.dobo = maradek, [felso]
            self.kezek[nev].append(self.pakli.pop())

    def _lep_kov(self, kihagy=False):
        self.aktiv_idx = (self.aktiv_idx + self.irany) % self.n
        if kihagy:
            self.aktiv_idx = (self.aktiv_idx + self.irany) % self.n

    def _lerak(self, nev, kartya, valasztott_szin=None):
        """Egy lap lerakása + a lap hatása. Visszaadja a felolvasandó üzenetet."""
        self.kezek[nev].remove(kartya)
        self.dobo.append(kartya)
        if kartya[0] == "szín":
            szin = valasztott_szin or SZK._uno_gep_szin(self.kezek[nev])
            self.szin, self.ertek = szin, kartya[1]
            uz = f"{nev} {SZK._uno_nev(kartya)}-t rakott. A kért szín: {szin}."
        else:
            self.szin, self.ertek = kartya
            uz = f"{nev} lerakott: {SZK._uno_nev(kartya)}."
        if len(self.kezek[nev]) == 1:
            uz += f" {nev}: UNO!"
        if len(self.kezek[nev]) == 0:
            self.gyoztes = nev
            self.fazis = "vege"
            return uz + f" {nev} KIFOGYOTT A LAPOKBÓL – NYERT!"
        kihagy = False
        e = kartya[1]
        if e == "kihagy":
            kihagy = True
        elif e == "irany":
            self.irany *= -1
        elif e == "+2":
            kov = self.jatekosok[(self.aktiv_idx + self.irany) % self.n]
            self._huz(kov, 2)
            kihagy = True
            uz += f" {kov} húz két lapot és kimarad."
        elif e == "+4":
            kov = self.jatekosok[(self.aktiv_idx + self.irany) % self.n]
            self._huz(kov, 4)
            kihagy = True
            uz += f" {kov} húz négy lapot és kimarad."
        self._lep_kov(kihagy)
        return uz

    # ------------------------------------------------------------------ akció
    def akcio(self, ki, tipus, adat=None):
        """A soron lévő játékos lépése. Visszaad: PUBLIKUS állapot (dict), vagy
        None, ha érvénytelen (nem ő van soron / rossz fázis / rossz akció)."""
        if self.fazis == "vege" or ki != self.soron:
            return None
        d = adat if isinstance(adat, dict) else {}

        if self.fazis == "jatek":
            if tipus == "rak":
                idx = d.get("index", adat if isinstance(adat, int) else None)
                kez = self.kezek[ki]
                if idx is None or not (0 <= idx < len(kez)):
                    return None
                kartya = kez[idx]
                if not SZK._uno_rakhato(kartya, self.szin, self.ertek):
                    return self.allapot_publikus(
                        f"{ki}: az a lap most nem rakható.")
                return self.allapot_publikus(
                    self._lerak(ki, kartya, d.get("szin")))
            if tipus == "huz":
                self._huz(ki, 1)
                uj = self.kezek[ki][-1]
                if SZK._uno_rakhato(uj, self.szin, self.ertek):
                    self.fazis = "huzas_utan"
                    self._huzott = uj
                    return self.allapot_publikus(
                        f"{ki} húzott egy lapot, amit le is rakhat, vagy passzol.")
                self._lep_kov(False)
                return self.allapot_publikus(f"{ki} húzott és passzol.")
            return None

        if self.fazis == "huzas_utan":
            if tipus == "rak":
                kartya = self._huzott
                self.fazis = "jatek"
                self._huzott = None
                if kartya is None or kartya not in self.kezek[ki]:
                    return None
                return self.allapot_publikus(
                    self._lerak(ki, kartya, d.get("szin")))
            if tipus == "passz":
                self.fazis = "jatek"
                self._huzott = None
                self._lep_kov(False)
                return self.allapot_publikus(f"{ki} nem rakja le, passzol.")
            return None

        return None


# ============================ ONLINE panel (fül) =============================

UNO_ONLINE_SUGO = (
    "UNO ONLINE – SÚGÓ\n\n"
    "Több gépről játszotok, egymástól távol, csak internettel. A szobát nyitó "
    "játékos a HOST: nála fut a hiteles játék, ő oszt. MINDENKI CSAK A SAJÁT "
    "kezét látja – más lapjaiból csak a DARABSZÁMOT.\n\n"
    "BELÉPÉS\n"
    "• Írd be a NEVED.\n"
    "• Ha TE szervezed: „Új szoba” → kapsz egy KÓDOT, „Kód másolása”, küldd el a "
    "többieknek. Amikor mind bent vannak: „Játék indítása”.\n"
    "• Ha CSATLAKOZOL: írd a kód mezőbe a KÓDOT, majd „Csatlakozás”.\n\n"
    "AMIKOR TE JÖSSZ\n"
    "• A „Lapjaid” listában fel/le nyíllal lépkedsz (a rakhatók jelölve). "
    "„Kirakás” (vagy Enter) leteszi a kijelöltet; Színkérőnél megkérdezi, "
    "milyen színt kérsz.\n"
    "• „Húzás”: húzol egy lapot. Ha rakható, utána „Kirakás”-sal leteheted, "
    "vagy „Passz”.\n\n"
    "SZÜNET\n"
    "A HOST a „Szünet”/„Folytatás” gombbal megállíthatja a játékot (pl. ha "
    "valakinek ki kell mennie); addig csak csevegni lehet.\n\n"
    "CSEVEGÉS\n"
    "Az ablak alján bármikor írhattok egymásnak (Enter vagy „Küldés”).\n\n"
    "Minden lépés minden gépen FELOLVASVA hangzik el. A körök közt pár másodperc "
    "hálózati késés normális. Csak internet kell – semmit nem kell beállítanod."
)


class UnoOnlinePanel(NetPanelMixin, wx.Panel):
    """Host-authoritative ONLINE UNO – a Szerencsekerék online mintájára, de
    MAGÁNKÉZZEL: a host a publikus állapotot mindenkinek, a privát kezet
    címzetten küldi. Lobbi + felolvasott játék + csevegés + (host) szünet.
    A közös lobbi/chat/net/hang plumbing a NetPanelMixin-ből jön."""

    HELYI_NEV = "helyi UNO"

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
        self._kezem = []
        self._szin = ""
        self._ertek = ""
        self._hang_player = None
        self._build()
        wx.CallAfter(self._start_ellenoriz)

    # -------------------------------------------------------------- felület
    def _build(self):
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(self, label=(
            "Játssz UNO-t TÖBB gépről, egymástól távol – csak internet kell! "
            "Mindenki csak a SAJÁT lapjait látja. Súgó: F1.")), 0, wx.ALL, 8)

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

        self._felso = wx.TextCtrl(self, style=wx.TE_READONLY)
        self._felso.SetName("A felső lap és a soron lévő játékos")
        v.Add(self._felso, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

        v.Add(wx.StaticText(self, label="A &lapjaid (fel/le nyíl, Enter = kirakás):"),
              0, wx.LEFT | wx.TOP, 8)
        self._kez_lst = wx.ListBox(self, style=wx.LB_SINGLE)
        self._kez_lst.SetName("A lapjaid")
        self._kez_lst.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._kirak())
        self._kez_lst.Bind(wx.EVT_KEY_DOWN, self._kez_key)
        v.Add(self._kez_lst, 1, wx.EXPAND | wx.ALL, 8)

        akc = wx.BoxSizer(wx.HORIZONTAL)
        self.g_kirak = wx.Button(self, label="&Kirakás")
        self.g_kirak.Bind(wx.EVT_BUTTON, lambda e: self._kirak())
        akc.Add(self.g_kirak, 0, wx.RIGHT, 6)
        self.g_huz = wx.Button(self, label="&Húzás")
        self.g_huz.Bind(wx.EVT_BUTTON, lambda e: self._akcio("huz"))
        akc.Add(self.g_huz, 0, wx.RIGHT, 6)
        self.g_passz = wx.Button(self, label="&Passz")
        self.g_passz.Bind(wx.EVT_BUTTON, lambda e: self._akcio("passz"))
        akc.Add(self.g_passz, 0, wx.RIGHT, 6)
        self.g_szunet = wx.Button(self, label="&Szünet")
        self.g_szunet.Bind(wx.EVT_BUTTON, self._szunet_valt)
        akc.Add(self.g_szunet, 0)
        v.Add(akc, 0, wx.ALL, 8)
        self._akc_sizer = akc

        self._chat_label = wx.StaticText(self, label="&Csevegés a játékosokkal:")
        v.Add(self._chat_label, 0, wx.LEFT | wx.TOP, 8)
        self.chat_atirat = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 60))
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
            size=(-1, 80))
        self._naplo.SetName("A játék menete, csak olvasható")
        v.Add(self._naplo, 0, wx.EXPAND | wx.ALL, 8)

        self.SetSizer(v)
        self._v = v
        self._jatek_widgetek = [self._felso, self._kez_lst, self._chat_label,
                                self.chat_atirat, self._naplo]
        self._jatek_sizerek = [self._akc_sizer, self._csor_sizer]
        self._vezerlok_engedely(False)
        self._szoba_reszek_lathato(False)

    # -------------------------------------------------------------- lobbi
    def _indit(self, e):
        if not self._host or not self._szoba:
            return
        if len(self._jatekosok) < 2:
            self._mondd("Legalább két játékos kell – várj, míg csatlakoznak!")
            return
        self._motor = UnoHost(self._jatekosok)
        self.indit_gomb.Disable()
        self._szoba.kuld("start", {"jatekosok": self._jatekosok})
        self._broadcast(f"Kezdődik az UNO {len(self._jatekosok)} játékossal! "
                        f"A felső lap: {self._motor.allapot_publikus()['felso']}.")

    def _broadcast(self, uzenet=""):
        if not (self._host and self._motor and self._szoba):
            return
        self._szoba.kuld("allapot", self._motor.allapot_publikus(uzenet))
        for nev in self._motor.jatekosok:
            self._szoba.kuld("kez", {"cimzett": nev,
                                     "lapok": self._motor.kez(nev)})

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
            self._mondd("Indul az UNO! Játékosok: "
                        + ", ".join(self._jatekosok) + ".")
        elif tipus == "akcio":
            if self._host and self._motor and not self._szunet:
                allap = self._motor.akcio(ki, adat.get("tipus"),
                                          adat.get("adat"))
                if allap is not None:
                    self._broadcast(allap.get("uzenet", ""))
        elif tipus == "allapot":
            self._render_publikus(adat)
        elif tipus == "kez":
            if adat.get("cimzett") == self._nev:
                self._kezem = [tuple(x) for x in adat.get("lapok", [])]
                self._frissit_kez()
        elif tipus == "szunet":
            self._szunet = bool(adat.get("be"))
            if self._szunet:
                self._mondd("A játék SZÜNETEL (a host állította meg). "
                            "Addig csak csevegni lehet.")
            else:
                self._mondd("A játék FOLYTATÓDIK!")
            self._vezerlok_engedely(self._enyem() and not self._szunet)
        elif tipus == "csevej":
            self._chat_fogad(ki, adat)

    # -------------------------------------------------------------- render
    def _enyem(self):
        return (self._fazis in ("jatek", "huzas_utan")
                and self._soron == self._nev)

    def _render_publikus(self, a):
        self._fazis = a.get("fazis", "jatek")
        self._soron = a.get("soron", "")
        self._szin = a.get("szin", "")
        self._ertek = a.get("ertek", "")
        self._lobbi_lathato(self._fazis == "lobbi")
        uz = a.get("uzenet", "")
        self._hang_esemeny(uz, self._fazis)
        lapszamok = a.get("lapszamok", {})
        felso = a.get("felso", "")
        szamsor = ", ".join(f"{n}: {lapszamok.get(n, 0)}"
                            for n in a.get("jatekosok", []))
        if self._fazis == "vege":
            gy = a.get("gyoztes", "")
            self._felso.SetValue(f"VÉGE! Győztes: {gy}. Lapok – {szamsor}.")
        else:
            self._felso.SetValue(
                f"Felső lap: {felso}.  Soron: {self._soron}.  Lapok: {szamsor}")
        self._mondd(uz)
        self._frissit_kez()
        if self._fazis == "vege":
            self._vezerlok_engedely(False)
            return
        enyem = self._enyem() and not self._szunet
        self._vezerlok_engedely(enyem)
        if self._enyem():
            if self._fazis == "huzas_utan":
                self._mondd("Húztál egy rakható lapot – „Kirakás” leteszi, vagy "
                            "„Passz”.")
            else:
                self._mondd("TE JÖSSZ! Válassz egy rakható lapot és „Kirakás”, "
                            "vagy „Húzás”.")
            try:
                self._kez_lst.SetFocus()
            except Exception:
                pass

    def _frissit_kez(self):
        elemek = []
        for k in self._kezem:
            rak = SZK._uno_rakhato(k, self._szin, self._ertek)
            jel = "  ✅ rakható" if (rak and self._enyem()) else ""
            elemek.append(SZK._uno_nev(k) + jel)
        kijel = self._kez_lst.GetSelection()
        self._kez_lst.Set(elemek)
        if elemek:
            self._kez_lst.SetSelection(min(max(kijel, 0), len(elemek) - 1))

    # -------------------------------------------------------------- akciók
    def _kez_key(self, e):
        if e.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._kirak()
        else:
            e.Skip()

    def _kirak(self):
        if not self._enyem() or self._szunet:
            self._mondd("Most nem te jössz.")
            return
        if self._fazis == "huzas_utan":
            kartya = self._kezem[-1] if self._kezem else None
            szin = self._szin_ha_wild(kartya)
            self._akcio("rak", {"szin": szin} if szin else {})
            return
        i = self._kez_lst.GetSelection()
        if i < 0 or i >= len(self._kezem):
            return
        kartya = self._kezem[i]
        if not SZK._uno_rakhato(kartya, self._szin, self._ertek):
            self._mondd(f"Azt a lapot nem rakhatod a(z) "
                        f"{SZK._uno_top_nev(self._szin, self._ertek)} lapra.")
            self._hang("sikertelen_tipp")
            return
        szin = self._szin_ha_wild(kartya)
        adat = {"index": i}
        if szin:
            adat["szin"] = szin
        self._akcio("rak", adat)

    def _szin_ha_wild(self, kartya):
        if not kartya or kartya[0] != "szín":
            return None
        valaszok = ["piros", "sárga", "zöld", "kék"]
        dlg = wx.SingleChoiceDialog(self, "Színkérő! Milyen színt kérsz?",
                                    "Szín választása",
                                    [c.capitalize() for c in valaszok])
        if dlg.ShowModal() == wx.ID_OK:
            v = valaszok[dlg.GetSelection()]
            dlg.Destroy()
            return v
        dlg.Destroy()
        return "piros"

    def _akcio(self, tipus, adat=None):
        if not self._szoba or self._fazis == "vege":
            return
        if self._szunet:
            self._mondd("A játék szünetel.")
            return
        if not self._enyem():
            self._mondd("Most nem te jössz – várj a köröodre.")
            return
        self._szoba.kuld("akcio", {"tipus": tipus, "adat": adat or {}})

    def _szunet_valt(self, e):
        if not self._host or not self._szoba:
            self._mondd("A szünetet a szoba szervezője (host) kapcsolhatja.")
            return
        uj = not self._szunet
        self._szoba.kuld("szunet", {"be": uj})

    def _vezerlok_engedely(self, be):
        for g in (self.g_kirak, self.g_huz, self.g_passz, self._kez_lst):
            try:
                g.Enable(be)
            except Exception:
                pass
        try:
            self.g_szunet.Enable(self._host and self._fazis in ("jatek",
                                                                "huzas_utan"))
        except Exception:
            pass

    # -------------------------------------------------------------- csevegés
    # -------------------------------------------------------------- hang
    def _hang_esemeny(self, uzenet, fazis):
        u = uzenet or ""
        nev = None
        if "NYERT" in u:
            nev = "taps"
        elif "húz négy" in u or "húz két" in u:
            nev = "boo"
        elif "UNO!" in u:
            nev = "sikeres_tipp"
        elif "rakott" in u or "lerakott" in u:
            nev = "maganhangzo_vasarlas"
        if nev:
            self._hang(nev)

    # a lobbi/chat/net/hang/_mondd/leallit közös részét a NetPanelMixin adja
