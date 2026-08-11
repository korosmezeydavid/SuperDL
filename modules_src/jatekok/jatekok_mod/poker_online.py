# -*- coding: utf-8 -*-
"""Póker (ötlapos húzós) – host-authoritative ONLINE motor (fejetlen).

A közös online-héj legösszetettebb motorja: PRIVÁT kéz (mint az UNO) + TÉTKÖRÖK.
Menet: ante → 1. tétkör → csere (eldobás/húzás) → 2. tétkör → leleplezés.
Akciók a tétkörben: „dob" (bedob/fold), „megad" (passz/check vagy megadás/call),
„emel" (nyit/emel fix egységgel). A kéz-értékelő (`poker_ertek`) a helyi
Pókerrel AZONOS – ide másolva, hogy a motor wx-mentes és önállóan tesztelhető
legyen (mint a Blackjack-motornál).
"""
import random
from collections import Counter

_SZINEK = ["pikk", "kör", "káró", "treff"]
_RANGOK = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "bubi", "dáma",
           "király", "ász"]
_RE = {r: i + 2 for i, r in enumerate(_RANGOK)}     # 2..14 (ász=14)

KEZ_NEV = {8: "SZÍNSOR", 7: "PÓKER (négy egyforma)", 6: "FULL HOUSE",
           5: "SZÍN (flöss)", 4: "SOR", 3: "DRILL (három egyforma)",
           2: "KÉT PÁR", 1: "EGY PÁR", 0: "MAGAS LAP"}


def poker_ertek(kez):
    """Egy 5 lapos kéz értéke: (kategória 0..8, döntetlen-lista). Nagyobb a jobb."""
    ertekek = sorted((_RE[r] for _, r in kez), reverse=True)
    szinek = [s for s, _ in kez]
    c = Counter(ertekek)
    csoportok = sorted(c.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    szamok = [g[1] for g in csoportok]
    rend = [g[0] for g in csoportok]
    floss = len(set(szinek)) == 1
    egyedi = sorted(set(ertekek), reverse=True)
    sor_teto = None
    if len(egyedi) == 5:
        if egyedi[0] - egyedi[4] == 4:
            sor_teto = egyedi[0]
        elif set(egyedi) == {14, 5, 4, 3, 2}:
            sor_teto = 5
    if sor_teto and floss:
        return (8, [sor_teto])
    if szamok == [4, 1]:
        return (7, rend)
    if szamok == [3, 2]:
        return (6, rend)
    if floss:
        return (5, ertekek)
    if sor_teto:
        return (4, [sor_teto])
    if szamok == [3, 1, 1]:
        return (3, rend)
    if szamok == [2, 2, 1]:
        return (2, rend)
    if szamok == [2, 1, 1, 1]:
        return (1, rend)
    return (0, ertekek)


def lap_nev(k):
    return "%s %s" % (k[1], k[0])


def kez_nev(kez):
    return ", ".join(lap_nev(k) for k in kez) if kez else "(nincs lap)"


class PokerHost:
    """Host-oldali ötlapos húzós póker. Fázisok: „tet1", „csere", „tet2",
    „vege". A privát kezet a panel címzetten küldi (mint az UNO-nál)."""

    def __init__(self, jatekosok, kezdo_zseton=200, ante=10, tet_egyseg=20):
        self.jatekosok = [j for j in jatekosok if j] or ["Játékos"]
        self.zseton = {n: int(kezdo_zseton) for n in self.jatekosok}
        self.ante = int(ante)
        self.tet_egyseg = int(tet_egyseg)
        self.kor = 0
        self.fazis = "keszen"
        self.osztas()

    # ------------------------------------------------------------------ osztás
    def _uj_pakli(self):
        p = [(sz, r) for sz in _SZINEK for r in _RANGOK]
        random.shuffle(p)
        return p

    def osztas(self):
        self.pakli = self._uj_pakli()
        self.kor += 1
        self.pot = 0
        self.kezek = {}
        self.statusz = {}          # jatszik / passzolt / kiul
        self.cserelt = set()
        self.gyoztes = []
        self.nyeremeny = 0
        self.leleplezes_kezek = {}
        for n in self.jatekosok:
            if self.zseton[n] >= self.ante:
                self.zseton[n] -= self.ante
                self.pot += self.ante
                self.kezek[n] = [self.pakli.pop() for _ in range(5)]
                self.statusz[n] = "jatszik"
            else:
                self.kezek[n] = []
                self.statusz[n] = "kiul"
        akt = self._aktivak()
        if len(akt) <= 1:
            # nincs kivel játszani → az egyetlen aktív viszi a potot (vagy senki)
            self.fazis = "tet1"
            self._tetkor_indit()
            if len(akt) == 1:
                self._fold_veg(akt[0])
            else:
                self.fazis = "vege"
            return
        self.fazis = "tet1"
        self._tetkor_indit()

    # --------------------------------------------------------------- lekérdezők
    def _aktivak(self):
        return [n for n in self.jatekosok if self.statusz.get(n) == "jatszik"]

    @property
    def soron(self):
        if self.fazis in ("tet1", "tet2", "csere") and self.aktiv_idx is not None:
            return self.jatekosok[self.aktiv_idx]
        return ""

    def kez(self, nev):
        return list(self.kezek.get(nev, []))

    def allapot_publikus(self, uzenet=""):
        return {
            "fazis": self.fazis, "kor": self.kor, "pot": self.pot,
            "soron": self.soron, "tet_szint": getattr(self, "tet_szint", 0),
            "tet_egyseg": self.tet_egyseg, "ante": self.ante,
            "korbe": dict(getattr(self, "korbe", {})),
            "zseton": dict(self.zseton), "statusz": dict(self.statusz),
            "lapszamok": {n: len(self.kezek[n]) for n in self.jatekosok},
            "jatekosok": list(self.jatekosok),
            "gyoztes": list(self.gyoztes), "nyeremeny": self.nyeremeny,
            "leleplezes": {n: [list(k) for k in self.leleplezes_kezek[n]]
                           for n in self.leleplezes_kezek},
            "leleplezes_nev": {n: KEZ_NEV[poker_ertek(self.leleplezes_kezek[n])[0]]
                               for n in self.leleplezes_kezek},
            "uzenet": uzenet,
        }

    # ------------------------------------------------------------------ belső
    def _kov_aktiv_idx(self, tol):
        n = len(self.jatekosok)
        i = tol
        for _ in range(n):
            i = (i + 1) % n
            nev = self.jatekosok[i]
            if self.statusz.get(nev) == "jatszik" and self.zseton[nev] > 0:
                return i
        return tol

    def _elso_aktiv_idx(self):
        for i, nev in enumerate(self.jatekosok):
            if self.statusz.get(nev) == "jatszik":
                return i
        return None

    def _tetkor_indit(self):
        self.tet_szint = 0
        self.korbe = {n: 0 for n in self.jatekosok}
        self.lepett = set()
        self.aktiv_idx = self._elso_aktiv_idx()

    def _tetkor_kesz(self):
        for n in self._aktivak():
            kell_lepnie = self.zseton[n] > 0
            if kell_lepnie and (n not in self.lepett
                                or self.korbe[n] != self.tet_szint):
                return False
        return True

    def _tovabb_vagy_zar(self):
        if self._tetkor_kesz():
            self._tetkor_zar()
        else:
            self.aktiv_idx = self._kov_aktiv_idx(self.aktiv_idx)

    def _tetkor_zar(self):
        if self.fazis == "tet1":
            self.fazis = "csere"
            self.cserelt = set()
            self.aktiv_idx = self._elso_aktiv_idx()
        else:                       # tet2 → leleplezés
            self._leleplezes()

    def _fold_veg(self, gyoztes):
        self.zseton[gyoztes] += self.pot
        self.nyeremeny = self.pot
        self.gyoztes = [gyoztes]
        self.fazis = "vege"
        self.aktiv_idx = None

    def _leleplezes(self):
        akt = self._aktivak()
        self.leleplezes_kezek = {n: list(self.kezek[n]) for n in akt}
        ertekek = {n: poker_ertek(self.kezek[n]) for n in akt}
        legjobb = max(ertekek.values())
        gyoztesek = [n for n in akt if ertekek[n] == legjobb]
        resz = self.pot // len(gyoztesek)
        maradek = self.pot - resz * len(gyoztesek)
        for i, n in enumerate(gyoztesek):
            self.zseton[n] += resz + (maradek if i == 0 else 0)
        self.nyeremeny = resz
        self.gyoztes = gyoztesek
        self.fazis = "vege"
        self.aktiv_idx = None

    # ------------------------------------------------------------------ akció
    def akcio(self, ki, tipus, adat=None):
        d = adat if isinstance(adat, dict) else {}

        if self.fazis in ("tet1", "tet2"):
            if self.aktiv_idx is None or ki != self.jatekosok[self.aktiv_idx]:
                return None
            if self.statusz.get(ki) != "jatszik":
                return None
            if tipus == "dob":
                self.statusz[ki] = "passzolt"
                akt = self._aktivak()
                if len(akt) == 1:
                    self._fold_veg(akt[0])
                    return self.allapot_publikus(
                        f"{ki} bedobta a lapjait. {akt[0]} viszi a potot!")
                self._tovabb_vagy_zar()
                return self.allapot_publikus(f"{ki} bedobta a lapjait.")
            if tipus == "megad":
                diff = self.tet_szint - self.korbe[ki]
                pay = min(diff, self.zseton[ki])
                self.zseton[ki] -= pay
                self.pot += pay
                self.korbe[ki] += pay
                self.lepett.add(ki)
                uz = (f"{ki} passzol." if diff == 0
                      else f"{ki} megadja ({pay}).")
                self._tovabb_vagy_zar()
                return self.allapot_publikus(uz)
            if tipus == "emel":
                diff = self.tet_szint - self.korbe[ki]
                total = diff + self.tet_egyseg
                pay = min(total, self.zseton[ki])
                self.zseton[ki] -= pay
                self.pot += pay
                self.korbe[ki] += pay
                self.tet_szint = max(self.tet_szint, self.korbe[ki])
                self.lepett = {ki}
                self._tovabb_vagy_zar()
                return self.allapot_publikus(
                    f"{ki} {'nyit' if diff == 0 else 'emel'} {self.tet_egyseg}-t "
                    f"(a körben {self.korbe[ki]}).")
            return None

        if self.fazis == "csere":
            if self.aktiv_idx is None or ki != self.jatekosok[self.aktiv_idx]:
                return None
            if self.statusz.get(ki) != "jatszik" or ki in self.cserelt:
                return None
            if tipus != "csere":
                return None
            idxek = sorted({int(i) for i in (d.get("indexek") or [])
                            if isinstance(i, int) and 0 <= int(i) < 5})
            for i in reversed(idxek):
                self.kezek[ki].pop(i)
            for _ in idxek:
                if self.pakli:
                    self.kezek[ki].append(self.pakli.pop())
            self.cserelt.add(ki)
            uz = (f"{ki} {len(idxek)} lapot cserélt."
                  if idxek else f"{ki} nem cserélt.")
            if all(n in self.cserelt for n in self._aktivak()):
                self.fazis = "tet2"
                self._tetkor_indit()
            else:
                self.aktiv_idx = self._kov_aktiv_idx(self.aktiv_idx)
            return self.allapot_publikus(uz)

        return None


# ============================ ONLINE panel (fül) =============================

import wx

from . import netroom
from .netpanel import NetPanelMixin

POKER_ONLINE_SUGO = (
    "PÓKER ONLINE – SÚGÓ\n\n"
    "Ötlapos húzós póker több gépről, csak internettel. A szobát nyitó játékos a "
    "HOST: nála fut a hiteles játék, ő oszt. MINDENKI CSAK A SAJÁT lapjait látja "
    "(a leleplezésig); a többiektől a tétet és a zsetont látod.\n\n"
    "BELÉPÉS\n"
    "• Írd be a NEVED. Ha TE szervezed: „Új szoba” → KÓD, „Kód másolása”, majd "
    "„Játék indítása”. Ha CSATLAKOZOL: kód + „Csatlakozás”.\n\n"
    "EGY LEOSZTÁS\n"
    "Mindenki beteszi az antét, és kap 5 lapot. Két tétkör van (a csere előtt és "
    "után), köztük a csere.\n"
    "• Tétkörben: „Passz/Megadás” (ha nincs tét: passzolsz; ha van: megadod), "
    "„Emel” (nyitsz vagy emelsz egy fix egységgel), „Bedob” (feladod a lapjaid). "
    "Ha mindenki más bedob, te viszed a potot.\n"
    "• Cserében: a lapjaid listáján fel/le nyíllal lépkedsz, SZÓKÖZ jelöli/veszi "
    "le az eldobandót, majd „Csere” – a jelölteket lecseréled újakra.\n"
    "• Leleplezés: a legjobb kéz viszi a potot (döntetlennél osztott). A HOST az "
    "„Új leosztás” gombbal oszthat újra.\n\n"
    "Kéz-rangsor (erősödő): magas lap, pár, két pár, drill, sor, szín, full "
    "house, póker (négy egyforma), színsor. Csevegés az ablak alján; szünetet a "
    "host kapcsolhat. Csak internet kell."
)


class PokerOnlinePanel(NetPanelMixin, wx.Panel):
    """Host-authoritative ONLINE póker (ötlapos húzós), MAGÁNKÉZZEL (mint az
    UNO): a host a publikus állapotot broadcastolja, a privát kezet címzetten
    küldi. Tétkörök + csere + leleplezés; lobbi + csevegés + (host) szünet."""

    HELYI_NEV = "helyi Póker"

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
        self._eldobando = set()
        self._allapot = {}
        self._hang_player = None
        self._build()
        wx.CallAfter(self._start_ellenoriz)

    # -------------------------------------------------------------- felület
    def _build(self):
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(self, label=(
            "Ötlapos húzós PÓKER több gépről – csak internet kell! Mindenki csak "
            "a SAJÁT lapjait látja a leleplezésig. Súgó: F1.")), 0, wx.ALL, 8)

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

        # asztal (pot + játékosok) + saját kéz
        self._asztal = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 96))
        self._asztal.SetName("Az asztal: pot, tét, zsetonok")
        v.Add(self._asztal, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

        v.Add(wx.StaticText(self, label="A &lapjaid (fel/le nyíl; SZÓKÖZ = "
                            "eldobandó jelölése cserénél):"),
              0, wx.LEFT | wx.TOP, 8)
        self._kez_lst = wx.ListBox(self, style=wx.LB_SINGLE)
        self._kez_lst.SetName("A lapjaid")
        self._kez_lst.Bind(wx.EVT_KEY_DOWN, self._kez_key)
        v.Add(self._kez_lst, 1, wx.EXPAND | wx.ALL, 8)

        akc = wx.BoxSizer(wx.HORIZONTAL)
        self.g_megad = wx.Button(self, label="&Passz / Megadás")
        self.g_megad.Bind(wx.EVT_BUTTON, lambda e: self._akcio("megad"))
        akc.Add(self.g_megad, 0, wx.RIGHT, 6)
        self.g_emel = wx.Button(self, label="&Emel")
        self.g_emel.Bind(wx.EVT_BUTTON, lambda e: self._akcio("emel"))
        akc.Add(self.g_emel, 0, wx.RIGHT, 6)
        self.g_dob = wx.Button(self, label="&Bedob")
        self.g_dob.Bind(wx.EVT_BUTTON, lambda e: self._akcio("dob"))
        akc.Add(self.g_dob, 0, wx.RIGHT, 6)
        self.g_csere = wx.Button(self, label="&Csere (a jelölteket)")
        self.g_csere.Bind(wx.EVT_BUTTON, lambda e: self._csere())
        akc.Add(self.g_csere, 0, wx.RIGHT, 6)
        self.g_ujleoszt = wx.Button(self, label="Ú&j leosztás (host)")
        self.g_ujleoszt.Bind(wx.EVT_BUTTON, self._uj_leosztas)
        akc.Add(self.g_ujleoszt, 0, wx.RIGHT, 6)
        self.g_szunet = wx.Button(self, label="&Szünet")
        self.g_szunet.Bind(wx.EVT_BUTTON, self._szunet_valt)
        akc.Add(self.g_szunet, 0)
        v.Add(akc, 0, wx.ALL, 8)
        self._akc_sizer = akc

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
        self._jatek_widgetek = [self._asztal, self._kez_lst, self._chat_label,
                                self.chat_atirat, self._naplo]
        self._jatek_sizerek = [self._akc_sizer, self._csor_sizer]
        self._vez(False)
        self._szoba_reszek_lathato(False)

    # -------------------------------------------------------------- lobbi
    def _indit(self, e):
        if not self._host or not self._szoba:
            return
        if len(self._jatekosok) < 2:
            self._mondd("Legalább két játékos kell – várj, míg csatlakoznak!")
            return
        from .poker_online import PokerHost
        self._motor = PokerHost(self._jatekosok)
        self.indit_gomb.Disable()
        self._szoba.kuld("start", {"jatekosok": self._jatekosok})
        self._broadcast(f"Kezdődik a Póker {len(self._jatekosok)} játékossal! "
                        "Mindenki betette az antét, itt az 5 lapod.")

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
            self._mondd("Indul a Póker! Játékosok: "
                        + ", ".join(self._jatekosok) + ".")
        elif tipus == "akcio":
            if self._host and self._motor and not self._szunet:
                allap = self._motor.akcio(ki, adat.get("tipus"),
                                          adat.get("adat"))
                if allap is not None:
                    self._broadcast(allap.get("uzenet", ""))
        elif tipus == "uj_leosztas":
            if self._host and self._motor and not self._szunet:
                self._motor.osztas()
                self._broadcast("Új leosztás! Mindenki betette az antét.")
        elif tipus == "allapot":
            self._render_publikus(adat)
        elif tipus == "kez":
            if adat.get("cimzett") == self._nev:
                self._kezem = [tuple(x) for x in adat.get("lapok", [])]
                self._frissit_kez()
        elif tipus == "szunet":
            self._szunet = bool(adat.get("be"))
            self._mondd("A játék SZÜNETEL (a host állította meg)." if self._szunet
                        else "A játék FOLYTATÓDIK!")
            self._vez_allapot()
        elif tipus == "csevej":
            self._chat_fogad(ki, adat)

    # -------------------------------------------------------------- render
    def _enyem(self):
        st = (self._allapot.get("statusz", {}) or {}).get(self._nev, "")
        return (self._soron == self._nev and st == "jatszik" and not self._szunet)

    def _lap_txt(self, k):
        return "%s %s" % (k[1], k[0])

    def _asztal_szoveg(self, a):
        sorok = ["Pot: %d.  Kör-tét: %d." % (a.get("pot", 0),
                                             a.get("tet_szint", 0))]
        st = a.get("statusz", {})
        zseton = a.get("zseton", {})
        korbe = a.get("korbe", {})
        lapszam = a.get("lapszamok", {})
        lel = a.get("leleplezes", {})
        lelnev = a.get("leleplezes_nev", {})
        cimkek = {"jatszik": "játszik", "passzolt": "bedobta", "kiul": "kimarad"}
        gy = a.get("gyoztes", [])
        for n in a.get("jatekosok", []):
            reszek = ["%s: zseton %d" % (n, zseton.get(n, 0))]
            reszek.append("[%s]" % cimkek.get(st.get(n, ""), st.get(n, "")))
            if korbe.get(n):
                reszek.append("a körben %d" % korbe[n])
            if n in lel:
                kez = ", ".join(self._lap_txt(k) for k in lel[n])
                reszek.append("→ %s (%s)" % (kez, lelnev.get(n, "")))
            else:
                reszek.append("%d lap" % lapszam.get(n, 0))
            if n in gy:
                reszek.append("🏆 NYERT")
            jel = " ◄ TE" if n == self._nev else ""
            sorok.append("  ".join(reszek) + jel)
        return "\n".join(sorok)

    def _render_publikus(self, a):
        self._allapot = a
        self._fazis = a.get("fazis", "tet1")
        self._soron = a.get("soron", "")
        self._lobbi_lathato(self._fazis == "lobbi")
        uz = a.get("uzenet", "")
        self._hang_esemeny(uz, self._fazis, a)
        if self._fazis == "csere" and not getattr(self, "_csere_faz_volt", False):
            self._eldobando = set()
        self._csere_faz_volt = (self._fazis == "csere")
        self._asztal.SetValue(self._asztal_szoveg(a))
        if uz:
            self._mondd(uz)
        self._frissit_kez()
        self._vez_allapot()
        if self._fazis == "vege":
            gy = a.get("gyoztes", [])
            enyertem = self._nev in gy
            self._mondd(("NYERTÉL %d zsetont! " % a.get("nyeremeny", 0)
                         if enyertem else "A leosztás vége. Győztes: %s. "
                         % ", ".join(gy))
                        + ("Oszthatsz újat!" if self._host
                           else "Várd a host új leosztását!"))
            return
        if self._enyem():
            if self._fazis == "csere":
                self._mondd("TE JÖSSZ – CSERE! Jelöld a SZÓKÖZZEL az eldobandó "
                            "lapokat, aztán „Csere”.")
            else:
                tetszint = a.get("tet_szint", 0)
                diff = tetszint - (a.get("korbe", {}) or {}).get(self._nev, 0)
                self._mondd("TE JÖSSZ! %s Emelhetsz, vagy bedobhatsz."
                            % ("Nincs tét, passzolhatsz."
                               if diff <= 0 else "Megadáshoz %d kell." % diff))
            try:
                (self._kez_lst if self._fazis == "csere"
                 else self.g_megad).SetFocus()
            except Exception:
                pass

    def _frissit_kez(self):
        elemek = []
        for i, k in enumerate(self._kezem):
            jel = "  🗑 eldobom" if i in self._eldobando else ""
            elemek.append(self._lap_txt(k) + jel)
        kijel = self._kez_lst.GetSelection()
        self._kez_lst.Set(elemek)
        if elemek:
            self._kez_lst.SetSelection(min(max(kijel, 0), len(elemek) - 1))

    def _vez_allapot(self):
        enyem = self._enyem()
        bet = enyem and self._fazis in ("tet1", "tet2")
        csere = enyem and self._fazis == "csere"
        try:
            # dinamikus feliratok a tétkörben (mit csinál a Megadás/Emel gomb)
            if bet:
                a = self._allapot
                diff = a.get("tet_szint", 0) - (a.get("korbe", {}) or {}).get(
                    self._nev, 0)
                self.g_megad.SetLabel("&Passz (nem teszek be)" if diff <= 0
                                      else "&Megadás (%d)" % diff)
                self.g_emel.SetLabel("&Emel (+%d)" % a.get("tet_egyseg", 0))
            self.g_megad.Enable(bet)
            self.g_emel.Enable(bet)
            self.g_dob.Enable(bet)
            self.g_csere.Enable(csere)
            self.g_ujleoszt.Enable(self._host and self._fazis == "vege"
                                   and not self._szunet)
            self.g_szunet.Enable(self._host and self._fazis in (
                "tet1", "tet2", "csere", "vege"))
        except Exception:
            pass

    def _vez(self, be):
        for g in (self.g_megad, self.g_emel, self.g_dob, self.g_csere):
            try:
                g.Enable(be)
            except Exception:
                pass
        for g in (self.g_ujleoszt, self.g_szunet):
            try:
                g.Enable(False)
            except Exception:
                pass

    # -------------------------------------------------------------- akciók
    def _kez_key(self, e):
        if e.GetKeyCode() == wx.WXK_SPACE and self._fazis == "csere" \
                and self._enyem():
            i = self._kez_lst.GetSelection()
            if 0 <= i < len(self._kezem):
                if i in self._eldobando:
                    self._eldobando.discard(i)
                    self._mondd("%s – marad." % self._lap_txt(self._kezem[i]))
                else:
                    self._eldobando.add(i)
                    self._mondd("%s – eldobom." % self._lap_txt(self._kezem[i]))
                self._frissit_kez()
        else:
            e.Skip()

    def _akcio(self, tipus):
        if not self._szoba or self._fazis not in ("tet1", "tet2"):
            return
        if self._szunet:
            self._mondd("A játék szünetel.")
            return
        if not self._enyem():
            self._mondd("Most nem te jössz – várj a köröodre.")
            return
        self._szoba.kuld("akcio", {"tipus": tipus, "adat": {}})

    def _csere(self):
        if not self._szoba or self._fazis != "csere" or not self._enyem():
            return
        self._szoba.kuld("akcio", {"tipus": "csere",
                                   "adat": {"indexek": sorted(self._eldobando)}})
        self._eldobando = set()

    def _uj_leosztas(self, e):
        if not self._host or not self._szoba:
            self._mondd("Új leosztást a szoba szervezője (host) oszthat.")
            return
        if self._fazis != "vege":
            self._mondd("Új leosztás csak a mostani vége után.")
            return
        self._szoba.kuld("uj_leosztas", {})

    def _szunet_valt(self, e):
        if not self._host or not self._szoba:
            self._mondd("A szünetet a szoba szervezője (host) kapcsolhatja.")
            return
        self._szoba.kuld("szunet", {"be": not self._szunet})

    # -------------------------------------------------------------- csevegés
    # -------------------------------------------------------------- hang
    def _hang_esemeny(self, uzenet, fazis, a):
        nev = None
        if fazis == "vege":
            nev = "taps" if self._nev in a.get("gyoztes", []) else "ooo"
        elif "emel" in (uzenet or "") or "nyit" in (uzenet or ""):
            nev = "maganhangzo_vasarlas"
        if nev:
            self._hang(nev)

    # a lobbi/chat/net/hang/_mondd/leallit közös részét a NetPanelMixin adja
