# -*- coding: utf-8 -*-
"""Póker – MODERN, akadálymentes ablak (saját játék, ötlapos húzós póker).

Öt lapot kapsz, eldobhatsz belőle amennyit akarsz (Space jelöli a kijelöltet),
és húzol helyettük. A legjobb kéz viszi a kasszát. Modern, felolvasott felület:
a lapjaidat és a kéz értékét a program felmondja; közönséghangok és a gépi
ellenfelek beszólnak. A szabályok és a póker-rangsor közkincs; a kód és a
hangok sajátok.
"""
import os
import random
from collections import Counter

import wx

_SZINEK = ["pikk", "kör", "káró", "treff"]
_RANGOK = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "bubi", "dáma",
           "király", "ász"]
_RE = {r: i + 2 for i, r in enumerate(_RANGOK)}     # 2..14 (ász=14)
_ANTE = 10

_KEZ_NEV = {8: "SZÍNSOR", 7: "PÓKER (négy egyforma)", 6: "FULL HOUSE",
            5: "SZÍN (flöss)", 4: "SOR", 3: "DRILL (három egyforma)",
            2: "KÉT PÁR", 1: "EGY PÁR", 0: "MAGAS LAP"}

_BESZOL = [
    "{n}: Blöffölök… vagy mégsem!",
    "{n}: Ez a kéz nem semmi.",
    "{n}: Meglátjuk, kinek van jobb lapja.",
    "{n}: Érzem, hogy most nyerek.",
    "{n}: Hmm, cserélek párat.",
]


def poker_ertek(kez):
    """Egy 5 lapos kéz értéke: (kategória 0..8, döntetlen-lista). Nagyobb a jobb."""
    ertekek = sorted((_RE[r] for _, r in kez), reverse=True)
    szinek = [s for s, _ in kez]
    c = Counter(ertekek)
    # a Counter.items() (érték, darab) párokat ad; darab, majd érték szerint
    # csökkenően rendezzük
    csoportok = sorted(c.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    szamok = [g[1] for g in csoportok]        # a csoport-darabszámok (pl. [4,1])
    rend = [g[0] for g in csoportok]          # döntetlen-sorrend (értékek)
    floss = len(set(szinek)) == 1
    egyedi = sorted(set(ertekek), reverse=True)
    sor_teto = None
    if len(egyedi) == 5:
        if egyedi[0] - egyedi[4] == 4:
            sor_teto = egyedi[0]
        elif set(egyedi) == {14, 5, 4, 3, 2}:     # ász-alsó sor (A-2-3-4-5)
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


def _lap_nev(k):
    return "%s %s" % (k[1], k[0])


def _kez_nev(kez):
    return ", ".join(_lap_nev(k) for k in kez)


def _gep_eldob(kez):
    """Egyszerű gép-stratégia: a párt/drillt/… megtartja, a magányos lapokat
    (a legmagasabb 1-2 kivételével, ha nincs pár) eldobja. Visszaad: eldobandó
    indexek."""
    ertekek = [_RE[r] for _, r in kez]
    c = Counter(ertekek)
    # ha van legalább pár: tartsd a csoportban lévőket, dobd a magányosokat
    if any(v >= 2 for v in c.values()):
        return [i for i, e in enumerate(ertekek) if c[e] < 2]
    # nincs pár: tartsd a 2 legmagasabbat, a többit dobd
    rang = sorted(range(5), key=lambda i: ertekek[i], reverse=True)
    return sorted(rang[2:])


class PokerAblak(wx.Dialog):
    def __init__(self, main, jatek, gep_getter=None):
        super().__init__(main, title="Játék – Póker", size=(760, 580),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.main = main
        self.jatek = jatek
        self._closing = False
        self._player = None
        self._zseton = 100
        self._jatekosszam = 4
        self._build()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        wx.CallAfter(self._uj_leosztas)

    def _build(self):
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(self, label=(
            "Ötlapos húzós póker: dobd el a rossz lapokat (Space jelöli a "
            "kijelöltet), Csere = húzol helyettük, a legjobb kéz nyer. Súgó: F1.")),
            0, wx.ALL, 8)
        self._allapot = wx.TextCtrl(self, style=wx.TE_READONLY)
        self._allapot.SetName("A kéz értéke, a kassza és a zsetonjaid")
        v.Add(self._allapot, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        v.Add(wx.StaticText(self, label="A &lapjaid (Space = eldobom / meggondolom):"),
              0, wx.LEFT | wx.TOP, 8)
        self._kez_lst = wx.ListBox(self, style=wx.LB_SINGLE)
        self._kez_lst.SetName("A lapjaid")
        self._kez_lst.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._jelol_valt())
        v.Add(self._kez_lst, 1, wx.EXPAND | wx.ALL, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        self._g_csere = wx.Button(self, label="&Csere (a jelölteket eldobod)")
        self._g_csere.Bind(wx.EVT_BUTTON, lambda e: self._csere())
        sor.Add(self._g_csere, 0, wx.RIGHT, 6)
        self._g_uj = wx.Button(self, label="Ú&j leosztás")
        self._g_uj.Bind(wx.EVT_BUTTON, lambda e: self._uj_leosztas())
        sor.Add(self._g_uj, 0, wx.RIGHT, 6)
        g_zar = wx.Button(self, label="Be&zárás")
        g_zar.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        sor.Add(g_zar, 0)
        v.Add(sor, 0, wx.ALL, 8)

        v.Add(wx.StaticText(self, label="&Játék menete:"), 0, wx.LEFT, 8)
        self._naplo = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 170))
        self._naplo.SetName("A játék menete, csak olvasható")
        v.Add(self._naplo, 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(v)

    def _hang(self, nev):
        try:
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
            if self._player is None:
                self._player = Player()
            self._player.play(ut, "")
        except Exception:
            pass

    def _mondd(self, szoveg):
        if self._closing or not (szoveg or "").strip():
            return
        self._naplo.AppendText(szoveg + "\n")
        try:
            from superdl import screenreader
            screenreader.speak(szoveg)
        except Exception:
            pass

    def _uj_pakli(self):
        p = [(sz, r) for sz in _SZINEK for r in _RANGOK]
        random.shuffle(p)
        return p

    def _uj_leosztas(self):
        from .jatekok import sajat as SJ
        if self._zseton < _ANTE:
            self._zseton = 100
            self._mondd("Kaptál 100 friss zsetont – folytatódhat a játék!")
        self.nevek = SJ._ellenfelek(self._jatekosszam - 1)
        self.pakli = self._uj_pakli()
        self._zseton -= _ANTE
        self.kassza = _ANTE * self._jatekosszam        # mindenki beteszi az antét
        self.kezek = {0: [self.pakli.pop() for _ in range(5)]}
        for i in range(1, self._jatekosszam):
            self.kezek[i] = [self.pakli.pop() for _ in range(5)]
        self._jeloltek = set()
        self._csereltel = False
        self._g_csere.Enable(True)
        self._kez_lst.Enable(True)
        self._frissit_kez()
        self._mondd("Új leosztás. Antéd: %d zseton, a kassza: %d. Dobd el a "
                    "rossz lapokat (Space), majd Csere. A kezed most: %s (%s)."
                    % (_ANTE, self.kassza, _kez_nev(self.kezek[0]),
                       _KEZ_NEV[poker_ertek(self.kezek[0])[0]]))

    def _frissit_kez(self):
        elemek = []
        for i, k in enumerate(self.kezek[0]):
            jel = "  🗑 eldobom" if i in self._jeloltek else ""
            elemek.append(_lap_nev(k) + jel)
        kij = self._kez_lst.GetSelection()
        self._kez_lst.Set(elemek)
        if elemek:
            self._kez_lst.SetSelection(min(max(kij, 0), len(elemek) - 1))
        kat, _ = poker_ertek(self.kezek[0])
        self._allapot.SetValue("A kezed: %s.   Kassza: %d.   Zsetonjaid: %d."
                               % (_KEZ_NEV[kat], self.kassza, self._zseton))

    def _jelol_valt(self):
        i = self._kez_lst.GetSelection()
        if i < 0 or self._csereltel:
            return
        if i in self._jeloltek:
            self._jeloltek.discard(i)
            allapot = "megtartod"
        else:
            self._jeloltek.add(i)
            allapot = "eldobod"
        self._frissit_kez()
        self._mondd("%s: %s." % (_lap_nev(self.kezek[0][i]), allapot))

    def _csere(self):
        if self._csereltel:
            return
        self._csereltel = True
        self._g_csere.Enable(False)
        self._kez_lst.Enable(False)
        # a te cseréd
        dobandok = sorted(self._jeloltek)
        if dobandok:
            uj = []
            for i in range(5):
                if i in self._jeloltek:
                    uj.append(self.pakli.pop())
                else:
                    uj.append(self.kezek[0][i])
            self.kezek[0] = uj
            self._mondd("Eldobtál %d lapot és húztál helyettük. Az új kezed: %s."
                        % (len(dobandok), _kez_nev(self.kezek[0])))
        else:
            self._mondd("Nem cseréltél – maradsz a lapjaiddal.")
        # a gépek cseréje
        for i in range(1, self._jatekosszam):
            dob = _gep_eldob(self.kezek[i])
            uj = [self.pakli.pop() if j in dob else self.kezek[i][j]
                  for j in range(5)]
            self.kezek[i] = uj
            if random.random() < 0.5:
                self._mondd(random.choice(_BESZOL).format(n=self.nevek[i - 1]))
            else:
                self._mondd("%s %d lapot cserél." % (self.nevek[i - 1], len(dob)))
        self._frissit_kez()
        wx.CallAfter(self._leleplezes)

    def _leleplezes(self):
        ered = [(poker_ertek(self.kezek[i]), i) for i in range(self._jatekosszam)]
        for (kat, _), i in sorted(ered, key=lambda x: x[0], reverse=True):
            nev = "Te" if i == 0 else self.nevek[i - 1]
            self._mondd("%s kártyái: %s — %s."
                        % (nev, _kez_nev(self.kezek[i]), _KEZ_NEV[kat]))
        legjobb = max(ered, key=lambda x: x[0])
        gyoztes = legjobb[1]
        if gyoztes == 0:
            self._zseton += self.kassza
            self._mondd("NYERTED a kasszát (%d zseton) a(z) %s kezeddel! 🎉"
                        % (self.kassza, _KEZ_NEV[legjobb[0][0]]))
            self._hang("taps")
        else:
            self._mondd("%s nyert a(z) %s kezével. Legközelebb visszavágsz!"
                        % (self.nevek[gyoztes - 1], _KEZ_NEV[legjobb[0][0]]))
            self._hang("ooo")
        self._frissit_kez()
        self._mondd("Zsetonjaid: %d. Új leosztás: Új leosztás gomb (vagy J)."
                    % self._zseton)
        wx.CallAfter(self._g_uj.SetFocus)

    _SUGO = (
        "PÓKER (ötlapos húzós) – SÚGÓ\n\n"
        "Öt lapot kapsz. Egy csere-körben eldobhatod a rossz lapjaidat, és "
        "húzol helyettük. A legjobb póker-kéz viszi a kasszát.\n\n"
        "• Fel/le nyíl: lépkedsz a lapjaidon (a képernyőolvasó felolvassa őket "
        "és a kezed jelenlegi értékét).\n"
        "• Space (vagy dupla kattintás): a kijelölt lapot ELDOBOD / meggondolod.\n"
        "• Csere: a jelölt lapokat eldobod, húzol helyettük, majd leleplezés.\n\n"
        "Rangsor (gyengétől erősig): magas lap, egy pár, két pár, drill, sor, "
        "szín, full house, póker (négy egyforma), színsor. A gépek beszólnak, a "
        "közönség él. J: új leosztás. F1: ez a súgó. Escape: bezárás."
    )

    def _on_key(self, e):
        k = e.GetKeyCode()
        if k == wx.WXK_F1:
            try:
                from superdl.helpdialog import show_help
                show_help(self, "Súgó – Póker", self._SUGO)
            except Exception:
                wx.MessageBox(self._SUGO, "Súgó – Póker", wx.OK | wx.ICON_INFORMATION, self)
        elif k == wx.WXK_SPACE and self.FindFocus() is self._kez_lst:
            self._jelol_valt()
        elif 32 < k < 256 and chr(k).lower() == "j":
            self._uj_leosztas()
        elif k == wx.WXK_ESCAPE:
            self.Close()
        else:
            e.Skip()

    def _on_close(self, e):
        self._closing = True
        try:
            if self._player is not None:
                self._player.stop()
        except Exception:
            pass
        e.Skip()
