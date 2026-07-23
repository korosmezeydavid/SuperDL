"""Játékok ablak – Retró játékok és SuperDL saját játékok.

Akadálymentes-first: natív wx vezérlők, minden elem címkézett, teljesen
billentyűzetről kezelhető, és minden fontos állapot HALLHATÓ (nem csak a
státuszsorban jelenik meg).
"""

import threading

import wx

from superdl import retrospeech as RS     # a Core SAJÁT formánsszintetizátora
from . import katalogus


HELP = """JÁTÉKOK

MIRE VALÓ
Akadálymentes játékok két csoportban:
• RETRÓ JÁTÉKOK – a 80-as/90-es évek magyar beszélő gépeinek hangulatában,
  korhű, „gépi” beszédhanggal.
• SUPERDL SAJÁT JÁTÉKOK – a program saját, mai játékai.

LÉPÉSRŐL LÉPÉSRE (vakon is)
1. A fülek között Ctrl+Tab-bal válts (Retró játékok / Saját játékok /
   Hangbeállítás).
2. A listában fel/le nyíllal válassz játékot – a program felolvassa a nevét és
   a rövid leírását.
3. Enter vagy az „Indítás” gomb: a játék elindul.
4. A HANGBEÁLLÍTÁS fülön kiválaszthatod a retró hangkaraktert, és a
   „Hangpróba” gombbal meg is hallgathatod, mielőtt játszanál.

GYORSBILLENTYŰK
F1 – ez a súgó.  Ctrl+Tab – fülváltás.  Enter – a kijelölt játék indítása.
F8 – a kijelölt játék leírásának megismétlése.  Escape – hang leállítása.

A RETRÓ HANGRÓL
A hangot a SuperDL SAJÁT formáns-alapú motorja készíti, a korszak
beszédszintézisének akusztikai jellemzői alapján. Nem tartalmaz és nem használ
fel semmilyen eredeti gépi ROM-ot vagy idegen kódot."""


class JatekokFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Játékok", size=(880, 620))
        self.main = main
        self._closing = False       # zárás alatt a háttér-callbackek kilépnek
        self._busy = False
        self._player = None
        self._hang = RS.ALAP_GEP
        self._tempo = 1.0            # a beszéd időtartam-szorzója (1.0 = alap)

        self._build()
        self.CreateStatusBar()
        self._announce("Válassz játékot a listából. Fülváltás: Ctrl+Tab. "
                       "Súgó: F1.")
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        self.nb = wx.Notebook(self)
        self._lista_retro = self._build_lista(
            "Retró játékok", katalogus.RETRO,
            "A 80-as/90-es évek hangulatában, korhű beszédhanggal.")
        self._lista_sajat = self._build_lista(
            "Saját játékok", katalogus.SAJAT,
            "A SuperDL saját, mai akadálymentes játékai.")
        self._build_hang()

    def _build_lista(self, cim, tetelek, alcim):
        p = wx.Panel(self.nb)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label=alcim), 0, wx.ALL, 8)
        v.Add(wx.StaticText(p, label="&Játékok (fel/le nyíl, Enter: indítás):"),
              0, wx.LEFT, 8)
        lst = wx.ListCtrl(p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        lst.SetName(f"{cim} listája")
        lst.InsertColumn(0, "Játék", width=260)
        lst.InsertColumn(1, "Miről szól", width=520)
        for j in tetelek:
            r = lst.InsertItem(lst.GetItemCount(), j.nev)
            lst.SetItem(r, 1, j.leiras)
        if tetelek:
            lst.Select(0)
            lst.Focus(0)
        lst.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._indit())
        lst.Bind(wx.EVT_LIST_ITEM_SELECTED, lambda e: self._kijelolve())
        v.Add(lst, 1, wx.EXPAND | wx.ALL, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        b = wx.Button(p, label="&Indítás")
        b.Bind(wx.EVT_BUTTON, lambda e: self._indit())
        sor.Add(b, 0, wx.RIGHT, 6)
        b2 = wx.Button(p, label="&Leírás felolvasása (F8)")
        b2.Bind(wx.EVT_BUTTON, lambda e: self._felolvas_leiras())
        sor.Add(b2, 0, wx.RIGHT, 6)
        b3 = wx.Button(p, label="Hang leállí&tása")
        b3.Bind(wx.EVT_BUTTON, lambda e: self._hang_stop())
        sor.Add(b3, 0)
        v.Add(sor, 0, wx.ALL, 8)
        p.SetSizer(v)
        self.nb.AddPage(p, cim)
        lst._tetelek = tetelek           # a laphoz tartozó katalógus
        return lst

    def _build_hang(self):
        p = wx.Panel(self.nb)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label=
              "Itt választhatod ki, milyen hangon szóljanak a retró játékok."),
              0, wx.ALL, 8)
        v.Add(wx.StaticText(p, label="&Hangkarakter (fel/le nyíl):"), 0,
              wx.LEFT, 8)
        self.hang_lst = wx.ListBox(
            p, choices=[x.nev for x in RS.GEPEK], style=wx.LB_SINGLE)
        self.hang_lst.SetName("Retró hangkarakter")
        self.hang_lst.SetSelection(0)
        self.hang_lst.Bind(wx.EVT_LISTBOX, lambda e: self._hang_valaszt())
        v.Add(self.hang_lst, 0, wx.EXPAND | wx.ALL, 8)

        v.Add(wx.StaticText(
            p, label="&Beszédtempó (nagyobb = gyorsabb):"), 0, wx.LEFT, 8)
        self.tempo_cs = wx.Slider(p, value=100, minValue=50, maxValue=160,
                                  style=wx.SL_HORIZONTAL | wx.SL_LABELS)
        self.tempo_cs.SetName("Beszédtempó százalékban")
        self.tempo_cs.Bind(wx.EVT_SLIDER, lambda e: self._tempo_valaszt())
        v.Add(self.tempo_cs, 0, wx.EXPAND | wx.ALL, 8)

        v.Add(wx.StaticText(p, label="&Próbaszöveg:"), 0, wx.LEFT, 8)
        self.proba_txt = wx.TextCtrl(
            p, value="Üdvözöllek a Super D L retro játékok menüjében!")
        self.proba_txt.SetName("Próbaszöveg a hangpróbához")
        v.Add(self.proba_txt, 0, wx.EXPAND | wx.ALL, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        b = wx.Button(p, label="Hang&próba")
        b.Bind(wx.EVT_BUTTON, lambda e: self._hangproba())
        sor.Add(b, 0, wx.RIGHT, 6)
        b2 = wx.Button(p, label="Hang leállí&tása")
        b2.Bind(wx.EVT_BUTTON, lambda e: self._hang_stop())
        sor.Add(b2, 0)
        v.Add(sor, 0, wx.ALL, 8)
        p.SetSizer(v)
        self.nb.AddPage(p, "Hangbeállítás")

    # ---- akadálymentes visszajelzés -----------------------------------

    def _announce(self, text, beszel=False):
        """Státuszsor + (fontos állapotnál) AKTÍV bemondás. A státuszsor
        változását a képernyőolvasó nem feltétlenül mondja be."""
        if self._closing:
            return
        self.SetStatusText(text)
        if beszel:
            sv = getattr(self.main, "selfvoice", None)
            if sv:
                try:
                    sv.speak(text, force=True)
                except Exception:
                    pass

    # ---- kijelölés / leírás -------------------------------------------

    def _aktiv_lista(self):
        i = self.nb.GetSelection()
        if i == 0:
            return self._lista_retro
        if i == 1:
            return self._lista_sajat
        return None

    def _kijelolt(self):
        lst = self._aktiv_lista()
        if lst is None:
            return None
        i = lst.GetFirstSelected()
        tetelek = getattr(lst, "_tetelek", [])
        return tetelek[i] if 0 <= i < len(tetelek) else None

    def _kijelolve(self):
        j = self._kijelolt()
        if j:
            self._announce(f"{j.nev}. {j.leiras}")

    def _felolvas_leiras(self):
        j = self._kijelolt()
        if not j:
            self._announce("Előbb válassz játékot a listából.", beszel=True)
            return
        self._retro_mond(f"{j.nev}. {j.leiras}")

    # ---- retró hang ---------------------------------------------------

    def _hang_valaszt(self):
        i = self.hang_lst.GetSelection()
        if 0 <= i < len(RS.GEPEK):
            self._hang = RS.GEPEK[i].kulcs
            self._announce(f"Hangkarakter: {RS.GEPEK[i].nev}", beszel=True)

    def _tempo_valaszt(self):
        # a csúszka „sebesség %", ebből lesz az időtartam-szorzó (nagyobb
        # sebesség = rövidebb idő = gyorsabb beszéd)
        szazalek = max(50, self.tempo_cs.GetValue())
        self._tempo = 100.0 / szazalek
        self._announce(f"Beszédtempó: {szazalek} százalék.", beszel=True)

    def _hangproba(self):
        szoveg = self.proba_txt.GetValue().strip()
        if not szoveg:
            self._announce("Írj be próbaszöveget.", beszel=True)
            return
        self._retro_mond(szoveg)

    def _retro_mond(self, szoveg: str):
        """A szöveg megszólaltatása a RETRÓ hangon, háttérben."""
        if self._busy:
            self._announce("Egy hang már készül, várd meg a végét.")
            return
        if not RS.available():
            self._announce("A retró hanghoz szükséges beszédmotor nem érhető "
                           "el ezen a gépen.", beszel=True)
            return
        self._busy = True
        self._announce("Hang készítése…")
        hang = self._hang
        tempo = self._tempo

        def work():
            try:
                path = RS.synth(szoveg, "", hang, tempo_szorzo=tempo)
            except Exception as e:
                wx.CallAfter(self._hang_kesz, "", str(e))
                return
            wx.CallAfter(self._hang_kesz, path, "")

        threading.Thread(target=work, daemon=True).start()

    def _hang_kesz(self, path, hiba):
        if self._closing:
            return
        self._busy = False
        if hiba:
            self._announce(f"A hang nem készült el: {hiba}", beszel=True)
            return
        try:
            if self._player is None:
                from superdl.audioengine import Player
                self._player = Player()
            self._player.play(path, "")
            self._announce("Szól a retró hang. Leállítás: Escape.")
        except Exception as e:
            self._announce(f"A lejátszás nem sikerült: {e}", beszel=True)

    def _hang_stop(self):
        try:
            if self._player:
                self._player.stop()
        except Exception:
            pass
        self._announce("Hang leállítva.")

    # ---- játék indítása ------------------------------------------------

    def _indit(self):
        j = self._kijelolt()
        if not j:
            self._announce("Előbb válassz játékot a listából.", beszel=True)
            return
        from .jatekkonzol import indithato, indit_jatek
        if not indithato(j.kulcs):
            # A keretrendszer kész, a játék maga még nem – ezt MEGMONDJUK,
            # nem teszünk úgy, mintha elindult volna.
            self._announce(
                f"A(z) „{j.nev}” még készül – hamarosan játszható lesz.",
                beszel=True)
            return
        try:
            indit_jatek(self, j, lambda: (self._hang, self._tempo))
        except Exception as e:
            self._announce(f"A játék nem indult el: {e}", beszel=True)

    # ---- súgó / billentyűk / zárás -------------------------------------

    def _on_key(self, e):
        k = e.GetKeyCode()
        if k == wx.WXK_F1:
            self._help()
        elif k == wx.WXK_F8:
            self._felolvas_leiras()
        elif k == wx.WXK_ESCAPE:
            self._hang_stop()
        else:
            e.Skip()

    def _help(self):
        try:
            from superdl.helpdialog import show_help
            show_help(self, "Játékok", HELP)
        except Exception:
            wx.MessageBox(HELP, "Súgó – Játékok",
                          wx.OK | wx.ICON_INFORMATION, self)

    def _on_close(self, e):
        self._closing = True
        try:
            if self._player:
                self._player.stop()
        except Exception:
            pass
        if getattr(self.main, "_jatekok_win", None) is self:
            self.main._jatekok_win = None
        e.Skip()
