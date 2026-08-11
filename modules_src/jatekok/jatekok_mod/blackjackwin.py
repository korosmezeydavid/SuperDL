# -*- coding: utf-8 -*-
"""Blackjack – MODERN, akadálymentes ablak (saját játék, nem konzolos).

Kaszinó blackjack az osztó ellen. A lapjaidat és az összeget a képernyőolvasó
felolvassa; gombokkal (vagy H/M/D billentyűkkel) játszol: Lapot kérek,
Megállok, Duplázás. Valódi élmény: KÖZÖNSÉGHANGOK (győzelem/vereség/blackjack)
és az OSZTÓ beszól. Egyszerű zseton-rendszer a kaszinó-hangulatért.

A szabályok közkincs; a kód és a hangok sajátok (szerencsekerek_hang).
"""
import os
import random

import wx

_SZINEK = ["pikk", "kör", "káró", "treff"]
_RANGOK = ["ász", "2", "3", "4", "5", "6", "7", "8", "9", "10",
           "bubi", "dáma", "király"]
_TET = 10          # fix tét leosztásonként

_OSZTO_BESZOL_NYER = [
    "Osztó: Ügyes! Kifogtál rajtam.",
    "Osztó: Na, ezt megnyerted. Gratulálok!",
    "Osztó: Ma szerencsés napod van.",
]
_OSZTO_BESZOL_VESZT = [
    "Osztó: A ház nyer. Legközelebb több szerencsét!",
    "Osztó: Sajnálom, ez az enyém.",
    "Osztó: Necces volt, de a ház vitte.",
]
_OSZTO_BESZOL_BUST = [
    "Osztó: Ajaj, túllépted a huszonegyet!",
    "Osztó: Több lett a kelleténél – befuccsolt.",
]


def _ertek(rang):
    if rang == "ász":
        return 11
    if rang in ("bubi", "dáma", "király", "10"):
        return 10
    return int(rang)


def _osszeg(kez):
    o = sum(_ertek(r) for _, r in kez)
    aszok = sum(1 for _, r in kez if r == "ász")
    while o > 21 and aszok:
        o -= 10
        aszok -= 1
    return o


def _bj(kez):
    return len(kez) == 2 and _osszeg(kez) == 21


def _lap_nev(k):
    return "%s %s" % (k[1], k[0])


def _kez_nev(kez):
    return ", ".join(_lap_nev(k) for k in kez)


class BlackjackAblak(wx.Dialog):
    def __init__(self, main, jatek, gep_getter=None):
        super().__init__(main, title="Játék – Blackjack", size=(720, 560),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.main = main
        self.jatek = jatek
        self._closing = False
        self._player = None
        self._zseton = 100
        self._tet = 0
        self._elso = True          # az első döntésed (dupla csak ekkor)
        self._build()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        wx.CallAfter(self._uj_leosztas)

    def _build(self):
        nb = wx.Notebook(self)
        helyi = wx.Panel(nb)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(helyi, label=(
            "Blackjack az osztó ellen: kerülj 21-hez közel túllépés nélkül! "
            "Lapot kérek (H), Megállok (M), Duplázás (D). Súgó: F1.")),
            0, wx.ALL, 8)

        self._allapot = wx.TextCtrl(helyi, style=wx.TE_READONLY)
        self._allapot.SetName("A lapjaid, az összeg, az osztó lapja és a zsetonjaid")
        v.Add(self._allapot, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        self._g_hit = wx.Button(helyi, label="&Lapot kérek")
        self._g_hit.Bind(wx.EVT_BUTTON, lambda e: self._hit())
        sor.Add(self._g_hit, 0, wx.RIGHT, 6)
        self._g_stand = wx.Button(helyi, label="&Megállok")
        self._g_stand.Bind(wx.EVT_BUTTON, lambda e: self._stand())
        sor.Add(self._g_stand, 0, wx.RIGHT, 6)
        self._g_dupla = wx.Button(helyi, label="&Duplázás")
        self._g_dupla.Bind(wx.EVT_BUTTON, lambda e: self._dupla())
        sor.Add(self._g_dupla, 0, wx.RIGHT, 6)
        self._g_uj = wx.Button(helyi, label="Ú&j leosztás")
        self._g_uj.Bind(wx.EVT_BUTTON, lambda e: self._uj_leosztas())
        sor.Add(self._g_uj, 0, wx.RIGHT, 6)
        g_zar = wx.Button(helyi, label="Be&zárás")
        g_zar.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        sor.Add(g_zar, 0)
        v.Add(sor, 0, wx.ALL, 8)

        v.Add(wx.StaticText(helyi, label="&Játék menete:"), 0, wx.LEFT, 8)
        self._naplo = wx.TextCtrl(
            helyi, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 200))
        self._naplo.SetName("A játék menete, csak olvasható")
        v.Add(self._naplo, 1, wx.EXPAND | wx.ALL, 8)
        helyi.SetSizer(v)

        nb.AddPage(helyi, "Helyben – osztó ellen")
        from .blackjack_online import BlackjackOnlinePanel
        self._online = BlackjackOnlinePanel(nb, self.main)
        nb.AddPage(self._online, "Online – közös osztó ellen!")
        self._nb = nb
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(nb, 1, wx.EXPAND | wx.ALL, 6)
        self.SetSizer(s)

    # --- hang + felolvasás ---
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

    # --- játék ---
    def _uj_pakli(self):
        p = [(sz, r) for sz in _SZINEK for r in _RANGOK]
        random.shuffle(p)
        return p

    def _uj_leosztas(self):
        if self._zseton < _TET:
            self._zseton = 100
            self._mondd("Kaptál 100 friss zsetont a háztól – folytatódhat a játék!")
        self.pakli = self._uj_pakli()
        self._tet = _TET
        self._zseton -= self._tet
        self.jatekos = [self.pakli.pop(), self.pakli.pop()]
        self.oszto = [self.pakli.pop(), self.pakli.pop()]
        self._elso = True
        self._vege = False
        self._akciok(True)
        self._frissit(oszto_rejtve=True)
        self._mondd("Új leosztás. Tét: %d zseton. A lapjaid: %s (összeg %d). "
                    "Az osztó felső lapja: %s."
                    % (self._tet, _kez_nev(self.jatekos), _osszeg(self.jatekos),
                       _lap_nev(self.oszto[0])))
        # természetes blackjack?
        if _bj(self.jatekos):
            self._mondd("BLACKJACK! Huszonegy két lapból!")
            self._hang("sikeres_tipp")
            self._oszto_kor(jatekos_bj=True)

    def _frissit(self, oszto_rejtve):
        if oszto_rejtve:
            oszto_txt = "%s és egy lefordított lap" % _lap_nev(self.oszto[0])
        else:
            oszto_txt = "%s (összeg %d)" % (_kez_nev(self.oszto), _osszeg(self.oszto))
        self._allapot.SetValue(
            "A lapjaid: %s — összeg %d.   Osztó: %s.   Zsetonjaid: %d."
            % (_kez_nev(self.jatekos), _osszeg(self.jatekos), oszto_txt,
               self._zseton))

    def _akciok(self, be, dupla=None):
        self._g_hit.Enable(be)
        self._g_stand.Enable(be)
        self._g_dupla.Enable(be if dupla is None else dupla)

    def _hit(self):
        if self._vege:
            return
        self._elso = False
        self._akciok(True, dupla=False)
        self.jatekos.append(self.pakli.pop())
        uj = self.jatekos[-1]
        o = _osszeg(self.jatekos)
        self._frissit(oszto_rejtve=True)
        self._mondd("Húztál: %s. Az összeged: %d." % (_lap_nev(uj), o))
        if o > 21:
            self._mondd(random.choice(_OSZTO_BESZOL_BUST))
            self._hang("boo")
            self._veszit(bust=True)

    def _stand(self):
        if self._vege:
            return
        self._mondd("Megállsz %d-nél. Most az osztó következik."
                    % _osszeg(self.jatekos))
        self._oszto_kor()

    def _dupla(self):
        if self._vege or not self._elso:
            self._mondd("Duplázni csak az első döntésnél lehet.")
            return
        if self._zseton < self._tet:
            self._mondd("Nincs elég zsetonod a duplázáshoz.")
            return
        self._zseton -= self._tet
        self._tet *= 2
        self._elso = False
        self.jatekos.append(self.pakli.pop())
        uj = self.jatekos[-1]
        o = _osszeg(self.jatekos)
        self._frissit(oszto_rejtve=True)
        self._mondd("Duplázás! A tét most %d. Húztál: %s. Az összeged: %d."
                    % (self._tet, _lap_nev(uj), o))
        if o > 21:
            self._mondd(random.choice(_OSZTO_BESZOL_BUST))
            self._hang("boo")
            self._veszit(bust=True)
        else:
            self._oszto_kor()

    def _oszto_kor(self, jatekos_bj=False):
        self._akciok(False)
        self._mondd("Az osztó felfordítja a lapját: %s. Az osztó lapjai: %s "
                    "(összeg %d)." % (_lap_nev(self.oszto[1]),
                                      _kez_nev(self.oszto), _osszeg(self.oszto)))
        while _osszeg(self.oszto) < 17:
            self.oszto.append(self.pakli.pop())
            self._mondd("Az osztó húz: %s (összeg %d)."
                        % (_lap_nev(self.oszto[-1]), _osszeg(self.oszto)))
        self._frissit(oszto_rejtve=False)
        self._dont(jatekos_bj)

    def _dont(self, jatekos_bj):
        jo = _osszeg(self.jatekos)
        oo = _osszeg(self.oszto)
        oszto_bj = _bj(self.oszto)
        if jatekos_bj and not oszto_bj:
            nyeremeny = int(self._tet * 2.5)      # blackjack 3:2 (tét + 1.5×)
            self._nyer(nyeremeny, "BLACKJACK! Fizet másfélszeresen!")
        elif oszto_bj and not jatekos_bj:
            self._veszit(uzenet="Az osztónak BLACKJACKje van.")
        elif oo > 21:
            self._nyer(self._tet * 2, "Az osztó túllépte a 21-et – NYERTÉL!")
        elif jo > oo:
            self._nyer(self._tet * 2, "A te %d-ed jobb az osztó %d-énél – NYERTÉL!"
                       % (jo, oo))
        elif jo < oo:
            self._veszit(uzenet="Az osztó %d-je jobb a te %d-ednél." % (oo, jo))
        else:
            self._zseton += self._tet
            self._mondd("Döntetlen (%d) – visszakapod a téted." % jo)
            self._veg_kozos()

    def _nyer(self, jovairas, uzenet):
        self._zseton += jovairas
        self._mondd(uzenet + " Nyeremény: %d zseton." % jovairas)
        self._mondd(random.choice(_OSZTO_BESZOL_NYER))
        self._hang("taps")
        self._veg_kozos()

    def _veszit(self, bust=False, uzenet=""):
        if uzenet:
            self._mondd(uzenet)
        if not bust:
            self._mondd(random.choice(_OSZTO_BESZOL_VESZT))
            self._hang("ooo")
        self._veg_kozos()

    def _veg_kozos(self):
        self._vege = True
        self._akciok(False)
        self._frissit(oszto_rejtve=False)
        self._mondd("Zsetonjaid: %d. Új leosztás: Új leosztás gomb (vagy J)."
                    % self._zseton)
        wx.CallAfter(self._g_uj.SetFocus)

    # --- billentyűk / zárás ---
    _SUGO = (
        "BLACKJACK – SÚGÓ\n\n"
        "Cél: kerülj minél közelebb a 21-hez, de ne lépd túl! Az ász 1 vagy 11, "
        "a figurák és a 10-esek 10-et érnek.\n\n"
        "• Lapot kérek (H): húzol egy lapot.\n"
        "• Megállok (M): nem húzol többet, jön az osztó (16-ig húz, 17-nél megáll).\n"
        "• Duplázás (D): csak az első döntésnél – megduplázod a tétet, húzol EGY "
        "lapot, és megállsz.\n"
        "• Blackjack (21 két lapból) másfélszeresen fizet.\n\n"
        "A lapjaidat és az összeget a program felolvassa; az osztó beszól, a "
        "közönség él. J: új leosztás. F1: ez a súgó. Escape: bezárás."
    )

    def _on_key(self, e):
        k = e.GetKeyCode()
        if k == wx.WXK_F1:
            online = False
            try:
                online = (self._nb.GetSelection() == 1)
            except Exception:
                pass
            if online:
                from .blackjack_online import BJ_ONLINE_SUGO
                cim, szoveg = "Súgó – Blackjack online", BJ_ONLINE_SUGO
            else:
                cim, szoveg = "Súgó – Blackjack", self._SUGO
            try:
                from superdl.helpdialog import show_help
                show_help(self, cim, szoveg)
            except Exception:
                wx.MessageBox(szoveg, cim, wx.OK | wx.ICON_INFORMATION, self)
            return
        if k == wx.WXK_ESCAPE:
            self.Close()
            return
        # A H/M/D/J gyorsbillentyűk CSAK a helyi fülön hatnak – különben az
        # online fül csevegő-mezőjébe gépelt betűket nyelnék el helyi lépésként.
        helyi = True
        try:
            helyi = (self._nb.GetSelection() == 0)
        except Exception:
            pass
        ch = chr(k).lower() if 32 < k < 256 else ""
        if helyi and ch == "h" and self._g_hit.IsEnabled():
            self._hit()
        elif helyi and ch == "m" and self._g_stand.IsEnabled():
            self._stand()
        elif helyi and ch == "d" and self._g_dupla.IsEnabled():
            self._dupla()
        elif helyi and ch == "j":
            self._uj_leosztas()
        else:
            e.Skip()

    def _on_close(self, e):
        self._closing = True
        try:
            if self._player is not None:
                self._player.stop()
        except Exception:
            pass
        try:
            if getattr(self, "_online", None):
                self._online.leallit()
        except Exception:
            pass
        e.Skip()
