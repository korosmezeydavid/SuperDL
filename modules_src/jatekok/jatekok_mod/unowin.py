# -*- coding: utf-8 -*-
"""UNO – MODERN, akadálymentes ablak (nem konzolos!).

A kezed egy LISTA, amin fel/le nyíllal lépkedsz – a képernyőolvasó felolvassa
minden lapodat, és jelzi, melyik RAKHATÓ. Enter vagy „Kirakás”: leteszed a
kijelöltet. „Húzás”: húzol. Valódi játékélmény: KÖZÖNSÉGHANGOK (taps a
győzelemre, csalódás a rossz lapokra) és a GÉPI ELLENFELEK BESZÓLNAK neked.

A játék LOGIKÁJÁT a `sajat.py`-ból hozzuk (pakli, rakhatóság, gép-választás),
csak a felület új. A hangok a szerencsekerek_hang mappából (saját, jogtiszta).
"""
import os
import random

import wx

from superdl import store  # noqa: F401 (a mintához; nem kötelező)
from .jatekok import sajat as SJ


def _mond_sr(szoveg):
    """Felolvastatás a képernyőolvasóval (ha van), különben csendben tovább."""
    try:
        from superdl import screenreader
        return bool(screenreader.speak(szoveg))
    except Exception:
        return False


# a gépek beszólásai – nem száraz napló, hanem élő játék
_BESZOL_TAMAD = [
    "{n}: Na, ezt kapd ki!",
    "{n}: Húzhatsz, barátom!",
    "{n}: Erre nem számítottál, mi?",
    "{n}: Sajnálom… nem is. {t}, húzz csak!",
    "{n}: Ez necces volt, de bejött!",
]
_BESZOL_UNO = [
    "{n}: UNO! Már csak egy lapom van!",
    "{n}: Vigyázz, mindjárt nyerek!",
    "{n}: Egy lap, és vége – készülj!",
]
_BESZOL_ALT = [
    "{n}: Hmm, mit rakjak…",
    "{n}: Jó kis parti ez!",
    "{n}: Neked drukkolok… vagy mégsem.",
    "{n}: Mindjárt fordul a kocka!",
]
_BESZOL_HUZ = [
    "{n}: Ó, nekem sincs jobb… húzok.",
    "{n}: Passzolok, húzok egyet.",
]


class UnoAblak(wx.Dialog):
    def __init__(self, main, jatek, gep_getter=None):
        super().__init__(main, title="Játék – UNO", size=(780, 600),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.main = main
        self.jatek = jatek
        self._closing = False
        self._player = None
        self._huztal = False        # ebben a körben már húztál-e (a passzhoz)
        self._build()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        wx.CallAfter(self._uj_jatek)

    # ------------------------------------------------------------------ UI
    def _build(self):
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(self, label=(
            "UNO – te és három játékos. Fel/le nyíllal lépkedsz a lapjaidon "
            "(a rakhatók jelölve), Enter vagy Kirakás: leteszed; Húzás: húzol. "
            "Súgó: F1.")), 0, wx.ALL, 8)

        self._felso = wx.TextCtrl(self, style=wx.TE_READONLY)
        self._felso.SetName("A felső lap és a soron lévő játékos")
        v.Add(self._felso, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        v.Add(wx.StaticText(self, label="A &lapjaid (fel/le nyíl, Enter = kirakás):"),
              0, wx.LEFT | wx.TOP, 8)
        self._kez_lst = wx.ListBox(self, style=wx.LB_SINGLE)
        self._kez_lst.SetName("A lapjaid")
        self._kez_lst.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._kirak())
        v.Add(self._kez_lst, 1, wx.EXPAND | wx.ALL, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        self._g_kirak = wx.Button(self, label="&Kirakás")
        self._g_kirak.Bind(wx.EVT_BUTTON, lambda e: self._kirak())
        sor.Add(self._g_kirak, 0, wx.RIGHT, 6)
        self._g_huz = wx.Button(self, label="&Húzás")
        self._g_huz.Bind(wx.EVT_BUTTON, lambda e: self._huz_akcio())
        sor.Add(self._g_huz, 0, wx.RIGHT, 6)
        self._g_uj = wx.Button(self, label="Ú&j játék")
        self._g_uj.Bind(wx.EVT_BUTTON, lambda e: self._uj_jatek())
        sor.Add(self._g_uj, 0, wx.RIGHT, 6)
        g_zar = wx.Button(self, label="Be&zárás")
        g_zar.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        sor.Add(g_zar, 0)
        v.Add(sor, 0, wx.ALL, 8)

        v.Add(wx.StaticText(self, label="&Játék menete:"), 0, wx.LEFT, 8)
        self._naplo = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 130))
        self._naplo.SetName("A játék menete, csak olvasható")
        v.Add(self._naplo, 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(v)

    # --------------------------------------------------------------- hang
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
        _mond_sr(szoveg)

    # --------------------------------------------------------------- játék
    def _uj_jatek(self):
        self.nevek = SJ._ellenfelek(3)
        self.nevlista = {0: "Te"}
        for i, n in enumerate(self.nevek, 1):
            self.nevlista[i] = n
        self.pakli = SJ._uno_pakli()
        self.dobo = []
        self.kezek = {i: [self.pakli.pop() for _ in range(7)] for i in range(4)}
        while True:
            top = self.pakli.pop()
            if top[0] != "szín" and top[1] not in ("kihagy", "irany", "+2"):
                break
            self.pakli.insert(0, top)
        self.dobo.append(top)
        self.szin, self.ertek = top
        self.irany, self.jatszo, self.gyoztes = 1, 0, None
        self._huztal = False
        self._mondd("Új UNO-parti! Ellenfeleid: " + ", ".join(self.nevek)
                    + ". Te kezdesz. Sok szerencsét!")
        self._frissit()
        self._sor()

    def _huz(self, ki, db=1):
        for _ in range(db):
            if not self.pakli:
                if len(self.dobo) <= 1:
                    return
                felso = self.dobo[-1]
                maradek = self.dobo[:-1]
                random.shuffle(maradek)
                self.pakli, self.dobo = maradek, [felso]
            self.kezek[ki].append(self.pakli.pop())

    def _rakhato_indexek(self):
        return [i for i, k in enumerate(self.kezek[0])
                if SJ._uno_rakhato(k, self.szin, self.ertek)]

    def _frissit(self):
        rak = set(self._rakhato_indexek())
        elemek = []
        for i, k in enumerate(self.kezek[0]):
            jel = "  ✅ rakható" if i in rak else ""
            elemek.append("%s%s" % (SJ._uno_nev(k), jel))
        kijel = self._kez_lst.GetSelection()
        self._kez_lst.Set(elemek)
        if elemek:
            self._kez_lst.SetSelection(min(max(kijel, 0), len(elemek) - 1))
        db = {n: len(self.kezek[i]) for i, n in self.nevlista.items()}
        self._felso.SetValue(
            "Felső lap: %s.  Soron: %s.  Lapok: %s"
            % (SJ._uno_top_nev(self.szin, self.ertek),
               self.nevlista[self.jatszo],
               ", ".join("%s: %d" % (n, db[n]) for n in self.nevlista.values())))

    def _sor(self):
        if self.gyoztes is not None:
            return
        sajat = (self.jatszo == 0)
        for g in (self._g_kirak, self._g_huz, self._kez_lst):
            g.Enable(sajat)
        if sajat:
            self._huztal = False
            rak = self._rakhato_indexek()
            if rak:
                self._mondd("Te jössz! Válassz egy rakható lapot (fel/le nyíl, "
                            "Enter), vagy húzz.")
            else:
                self._mondd("Te jössz, de nincs rakható lapod – húzz egyet "
                            "(Húzás).")
            wx.CallAfter(self._kez_lst.SetFocus)
        else:
            wx.CallLater(1100, self._gep_lep)

    # ---- a te lépésed ----
    def _kirak(self):
        if self.gyoztes is not None or self.jatszo != 0:
            return
        i = self._kez_lst.GetSelection()
        if i < 0 or i >= len(self.kezek[0]):
            return
        if i not in self._rakhato_indexek():
            self._mondd("Ezt a lapot nem rakhatod a(z) %s lapra."
                        % SJ._uno_top_nev(self.szin, self.ertek))
            self._hang("sikertelen_tipp")
            return
        kartya = self.kezek[0][i]
        self.kezek[0].pop(i)
        self._letesz(0, kartya)

    def _huz_akcio(self):
        if self.gyoztes is not None or self.jatszo != 0:
            return
        if self._huztal:
            self._mondd("Már húztál ebben a körben – passzolsz.")
            self._huztal = False
            self._lep_tovabb(SJ._uno_kov(0, self.irany, 4))
            return
        self._huz(0, 1)
        self._huztal = True
        uj = self.kezek[0][-1]
        self._frissit()
        if SJ._uno_rakhato(uj, self.szin, self.ertek):
            self._mondd("Húztál: %s – ez RAKHATÓ! Válaszd ki és Kirakás, vagy "
                        "Húzás = passz." % SJ._uno_nev(uj))
            self._kez_lst.SetSelection(len(self.kezek[0]) - 1)
            wx.CallAfter(self._kez_lst.SetFocus)
        else:
            self._mondd("Húztál: %s – nem rakható. Passzolsz." % SJ._uno_nev(uj))
            self._huztal = False
            self._lep_tovabb(SJ._uno_kov(0, self.irany, 4))

    # ---- egy lap letétele (bárki) + hatások ----
    def _letesz(self, aktiv, kartya):
        self._hang("maganhangzo_vasarlas")   # rövid „kártya-le” koppanás-jellegű
        # szín választás a wildhez
        if kartya[0] == "szín":
            if aktiv == 0:
                ujszin = self._szin_kerdes()
            else:
                ujszin = SJ._uno_gep_szin(self.kezek[aktiv])
            self.szin, self.ertek = ujszin, kartya[1]
            self._mondd("%s %s-t rakott. A kért szín: %s."
                        % (self.nevlista[aktiv], SJ._uno_nev(kartya), self.szin))
        else:
            self.szin, self.ertek = kartya
            self._mondd("%s kirakta: %s." % (self.nevlista[aktiv],
                                             SJ._uno_top_nev(self.szin, self.ertek)))
        self.dobo.append(kartya)

        # UNO! – egy lap maradt
        if len(self.kezek[aktiv]) == 1:
            if aktiv == 0:
                self._mondd("UNO! Egy lapod maradt!")
                self._hang("sikeres_tipp")
            else:
                self._mondd(random.choice(_BESZOL_UNO).format(n=self.nevlista[aktiv]))
                self._hang("nevetes1")
        # győzelem
        if len(self.kezek[aktiv]) == 0:
            self.gyoztes = aktiv
            self._veg()
            return

        kov = SJ._uno_kov(aktiv, self.irany, 4)
        ertek = kartya[1]
        # hatások
        if ertek == "irany":
            self.irany *= -1
            self._mondd("Irányváltó! Megfordul a kör.")
            kov = SJ._uno_kov(aktiv, self.irany, 4)
        elif ertek == "kihagy":
            kihagyott = kov
            kov = SJ._uno_kov(kov, self.irany, 4)
            self._mondd("%s kimarad ebből a körből." % self.nevlista[kihagyott])
            self._beszol_ha_gep(aktiv, kihagyott, _BESZOL_TAMAD)
        elif ertek == "+2":
            self._huz(kov, 2)
            self._mondd("%s húz két lapot és kimarad." % self.nevlista[kov])
            if kov == 0:
                self._hang("boo")
            self._beszol_ha_gep(aktiv, kov, _BESZOL_TAMAD)
            kov = SJ._uno_kov(kov, self.irany, 4)
        elif ertek == "+4":
            self._huz(kov, 4)
            self._mondd("%s húz NÉGY lapot és kimarad!" % self.nevlista[kov])
            if kov == 0:
                self._hang("boo")
            self._beszol_ha_gep(aktiv, kov, _BESZOL_TAMAD)
            kov = SJ._uno_kov(kov, self.irany, 4)

        self._lep_tovabb(kov)

    def _beszol_ha_gep(self, aktiv, cel, bank):
        if aktiv != 0 and random.random() < 0.7:
            self._mondd(random.choice(bank).format(
                n=self.nevlista[aktiv], t=self.nevlista.get(cel, "")))

    def _lep_tovabb(self, kov):
        self.jatszo = kov
        self._huztal = False
        self._frissit()
        self._sor()

    # ---- gép lépése ----
    def _gep_lep(self):
        if self.gyoztes is not None or self.jatszo == 0 or self._closing:
            return
        aktiv = self.jatszo
        kartya = SJ._uno_gep_valaszt(self.kezek[aktiv], self.szin, self.ertek)
        if kartya is None:
            self._huz(aktiv, 1)
            uj = self.kezek[aktiv][-1]
            if SJ._uno_rakhato(uj, self.szin, self.ertek):
                kartya = uj
            else:
                if random.random() < 0.5:
                    self._mondd(random.choice(_BESZOL_HUZ).format(n=self.nevlista[aktiv]))
                else:
                    self._mondd("%s húz és passzol." % self.nevlista[aktiv])
                self._lep_tovabb(SJ._uno_kov(aktiv, self.irany, 4))
                return
        if random.random() < 0.25:
            self._mondd(random.choice(_BESZOL_ALT).format(n=self.nevlista[aktiv]))
        self.kezek[aktiv].remove(kartya)
        self._letesz(aktiv, kartya)

    # ---- vége ----
    def _veg(self):
        for g in (self._g_kirak, self._g_huz, self._kez_lst):
            g.Enable(False)
        self._frissit()
        if self.gyoztes == 0:
            self._mondd("NYERTÉL! Kifogytál a lapokból – a közönség ünnepel! 🎉")
            self._hang("taps")
        else:
            self._mondd("%s nyert – kifogyott a lapokból. Sebaj, jövő körben "
                        "visszavágsz!" % self.nevlista[self.gyoztes])
            self._hang("ooo")
        wx.CallLater(400, lambda: self._mondd("Új játékhoz: Új játék gomb."))

    # ---- szín-kérdés (wild) ----
    def _szin_kerdes(self):
        dlg = wx.SingleChoiceDialog(self, "Milyen színt kérsz?", "Színkérő",
                                    SJ._SZINEK)
        szin = SJ._SZINEK[dlg.GetSelection()] if dlg.ShowModal() == wx.ID_OK \
            else random.choice(SJ._SZINEK)
        dlg.Destroy()
        return szin

    # ---- billentyűk / zárás ----
    _SUGO = (
        "UNO – SÚGÓ\n\n"
        "Te és három gépi játékos. A felső lapra SZÍNBEN vagy ÉRTÉKBEN egyezőt "
        "rakhatsz, vagy Színkérőt (bármire).\n\n"
        "• Fel/le nyíl: lépkedsz a lapjaidon. A rakhatók mellett „rakható” jel "
        "van, és a képernyőolvasó felolvassa mindet.\n"
        "• Enter vagy Kirakás: leteszed a kijelölt lapot.\n"
        "• Húzás: húzol egy lapot. Ha rakható, kiteheted; ha nem, passzolsz.\n"
        "• Ha egy lapod marad, az „UNO!”. Aki elsőként kifogy, nyer.\n\n"
        "A gépi ellenfelek beszólnak, és a közönség is él: taps a győzelemre, "
        "csalódás a rossz lapokra. F1: ez a súgó. Escape: bezárás."
    )

    def _on_key(self, e):
        k = e.GetKeyCode()
        if k == wx.WXK_F1:
            try:
                from superdl.helpdialog import show_help
                show_help(self, "Súgó – UNO", self._SUGO)
            except Exception:
                wx.MessageBox(self._SUGO, "Súgó – UNO", wx.OK | wx.ICON_INFORMATION, self)
        elif k in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and \
                self.FindFocus() is self._kez_lst:
            self._kirak()
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
