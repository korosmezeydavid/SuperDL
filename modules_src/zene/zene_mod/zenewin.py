# -*- coding: utf-8 -*-
"""Zene – a lehető legegyszerűbb lejátszó. Egy lista, és szól.

Egy ablak, egy lista. Minden művelet elérhető BILLENTYŰVEL és a HELYI MENÜBŐL
is (Alkalmazások billentyű vagy Shift+F10) – aki nem tudja fejből a
gyorsbillentyűket, az is végignyilazhatja, mit tud a program.

Ez a modul továbbra sem tud lejátszási listát, keverés-módot, kedvenceket,
címke-szerkesztést. A hozzáadott műveletek mind EGYSZERI parancsok: ugrás,
keresés, hangerő – nem új üzemmódok, amiket észben kell tartani.
"""

import os
import random
import subprocess
import threading
import time

import wx

from . import konyvtar as KT

ALVAS_PERCEK = (5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60)
TEKERES_MP = 5.0
ALVAS_HALKULAS_MP = 10.0       # ennyivel a vége előtt kezd elhalkulni
HANGERO_LEPES = 0.1

SUGO = """ZENE – EGYSZERŰ LEJÁTSZÓ

MIRE VALÓ
Zenét játszik. Semmi mást nem tud.

INDULÁS
A „Zenemappa kiválasztása” gombbal (Ctrl+O) adj meg EGY mappát. Ami alatta
van – akárhány almappában, akármilyen mélyen –, az mind bekerül a listába. A
választásod megjegyződik, legközelebb magától betölt.

MINDEN MŰVELET ELÉRHETŐ A HELYI MENÜBŐL IS: Alkalmazások billentyű vagy
Shift+F10. Nem kell fejből tudni a gyorsbillentyűket.

LEJÁTSZÁS
  Fel, le nyíl ....... előző, következő szám (azonnal szól)
  Bal, jobb nyíl ..... tekerés a számon belül, 5 másodpercenként
  Szóköz ............. szünet, és újra szóköz: folytatás
  Ctrl+fel, Ctrl+le .. hangerő fel és le
  Ctrl+R ............. ismétlés be- és kikapcsolása
  Ctrl+E ............. a szám végén álljon meg / menjen a következőre
  Ctrl+S ............. elalvás időzítő (5-től 60 percig)

TÁJÉKOZÓDÁS EGY NAGY LISTÁBAN
  Ctrl+F ............. keresés a számok közt (a következő találat: F3)
  Ctrl+G ............. ugrás mappára – a mappák listájából választasz
  Ctrl+T ............. véletlen szám
  Ctrl+I ............. hol tartunk (szám, idő, kapcsolók, elalvás)

EGYÉB
  Ctrl+C ............. a szám neve és útja a vágólapra
  Ctrl+Shift+M ....... a szám mappájának megnyitása az Intézőben
  F5 ................. a lista újraolvasása
  Ctrl+O ............. másik zenemappa
  F1 ................. ez a súgó
  Escape ............. bezárás

ÁTTŰNÉS
A számok között három másodperces áttűnés van: az előző elhalkul, közben a
következő feljön. Ha a hangkártyád nem engedélyez két egyidejű hangfolyamot,
áttűnés nem lesz, de a következő szám akkor is elindul.

ELALVÁS
A Ctrl+S egy listát nyit 5-től 60 percig. A megadott idő vége előtt tíz
másodperccel a zene lassan elhalkul, nem hirtelen vág el.
"""


def _mondd(main, szoveg):
    """BEMONDÁS – a KÖTELEZŐ sorrendben: ELŐBB a képernyőolvasó, és CSAK utána
    a némítás-vizsgálat meg a beépített hang. Fordítva képernyőolvasó-módban
    néma maradna, mert a Core ilyenkor szándékosan némítja a saját hangját."""
    if not (szoveg or "").strip():
        return
    try:
        from superdl import screenreader
        if screenreader.speak(szoveg):
            return
    except Exception:
        pass
    sv = getattr(main, "selfvoice", None)
    if sv and not getattr(sv, "muted", False):
        try:
            sv.speak(szoveg, force=True)
        except Exception:
            pass


class _NevAccessible(wx.Accessible):
    """A vezérlő akadálymentességi NEVÉT közvetlenül adja meg."""

    def __init__(self, name: str):
        super().__init__()
        self._name = name

    def GetName(self, childId):
        return (wx.ACC_OK, self._name)


class ZeneFrame(wx.Frame):

    def __init__(self, main):
        super().__init__(main, title="SuperDL – Zene", size=(880, 620))
        self.main = main
        self._closing = False
        self._szamok = []
        self._index = -1
        self._ismetles = False
        self._tovabb = True          # a szám végén menjen a következőre
        self._alvas_vege = 0.0       # időbélyeg; 0 = nincs elalvás
        self._hangero = 1.0
        self._keresett = ""
        self._megall = threading.Event()
        self._accessibles = []
        self._lejatszo = None

        self._build()
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

        self._ora = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_ora, self._ora)
        self._ora.Start(1000)

        gyoker = KT.gyoker_betolt()
        if gyoker:
            self._beolvas(gyoker, csendes_kezdet=True)
        else:
            self._allapot("Válassz egy zenemappát: Ctrl+O. Minden művelet "
                          "elérhető a helyi menüből is, Shift+F10.")

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        self.cimke = wx.StaticText(
            p, label="&Számok (fel-le nyíl: váltás és lejátszás; "
                     "helyi menü: Shift+F10):")
        v.Add(self.cimke, 0, wx.LEFT | wx.TOP, 8)

        self.lista = wx.ListBox(p, style=wx.LB_SINGLE)
        self._nev(self.lista, "Számok listája")
        self.lista.Bind(wx.EVT_LISTBOX, lambda e: self._kijelolt_indul())
        self.lista.Bind(wx.EVT_CONTEXT_MENU, self._helyi_menu)
        v.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        b = wx.Button(p, label="Zene&mappa kiválasztása…  (Ctrl+O)")
        b.Bind(wx.EVT_BUTTON, lambda e: self._mappat_valaszt())
        sor.Add(b, 0, wx.RIGHT, 6)
        bm = wx.Button(p, label="Mű&veletek…  (Shift+F10)")
        bm.Bind(wx.EVT_BUTTON, lambda e: self._helyi_menu(None))
        sor.Add(bm, 0, wx.RIGHT, 6)
        bs = wx.Button(p, label="&Súgó (F1)")
        bs.Bind(wx.EVT_BUTTON, lambda e: self._sugo())
        sor.Add(bs, 0)
        v.Add(sor, 0, wx.LEFT | wx.BOTTOM, 8)

        p.SetSizer(v)
        self.CreateStatusBar()
        self.lista.SetFocus()

    def _nev(self, ctrl, nev):
        ctrl.SetName(nev)
        try:
            acc = _NevAccessible(nev)
            ctrl.SetAccessible(acc)
            self._accessibles.append(acc)
        except Exception:
            pass

    def _allapot(self, szoveg, mondja=True):
        if self._closing:
            return
        try:
            self.SetStatusText(szoveg)
        except Exception:
            pass
        if mondja:
            _mondd(self.main, szoveg)

    # ---- helyi menü ------------------------------------------------------

    def _helyi_menu(self, e=None):
        """Minden művelet egy helyen, végignyilazhatóan.

        A gyorsbillentyűket nem kell fejből tudni: itt minden ott van, és a
        menüsor a képernyőolvasónak a gyorsbillentyűt is bemondja."""
        m = wx.Menu()

        def tetel(cimke, fv, kapcsolo=None):
            if kapcsolo is None:
                i = m.Append(wx.ID_ANY, cimke)
            else:
                i = m.AppendCheckItem(wx.ID_ANY, cimke)
                i.Check(bool(kapcsolo))
            self.Bind(wx.EVT_MENU, lambda _e: fv(), i)
            return i

        szol = self._lejatszo is not None and self._lejatszo.szol()
        szunetel = szol and self._lejatszo.szunetel()
        tetel("Folytatás\tSzóköz" if szunetel else "Szünet\tSzóköz",
              self._szunet)
        tetel("Előző szám\tFel nyíl", lambda: self._lep(-1))
        tetel("Következő szám\tLe nyíl", lambda: self._lep(1))
        m.AppendSeparator()
        tetel("Vissza 5 másodpercet\tBal nyíl", lambda: self._teker(-TEKERES_MP))
        tetel("Előre 5 másodpercet\tJobb nyíl", lambda: self._teker(TEKERES_MP))
        tetel("Hangerő fel\tCtrl+Fel", lambda: self._hangero_allit(HANGERO_LEPES))
        tetel("Hangerő le\tCtrl+Le", lambda: self._hangero_allit(-HANGERO_LEPES))
        m.AppendSeparator()
        tetel("&Ismétlés\tCtrl+R", self._ismetles_valt, self._ismetles)
        tetel("A szám végén menjen tovább\tCtrl+E", self._tovabb_valt,
              self._tovabb)
        tetel(("Elalvás… (most: %d perc van hátra)" % self._alvas_hatra_perc())
              if self._alvas_vege else "Elalvás…\tCtrl+S", self._alvas_parbeszed)
        m.AppendSeparator()
        tetel("&Keresés a számok közt…\tCtrl+F", self._keres)
        tetel("Következő találat\tF3", self._kovetkezo_talalat)
        tetel("Ugrás &mappára…\tCtrl+G", self._ugras_mappara)
        tetel("Véletlen szám\tCtrl+T", self._veletlen)
        tetel("Hol tartunk?\tCtrl+I", self._hol_tartunk)
        m.AppendSeparator()
        tetel("A szám neve és útja a vágólapra\tCtrl+C", self._vagolapra)
        tetel("A szám mappája az Intézőben\tCtrl+Shift+M", self._intezoben)
        tetel("A lista újraolvasása\tF5", self._ujraolvas)
        tetel("Másik zenemappa…\tCtrl+O", self._mappat_valaszt)
        m.AppendSeparator()
        tetel("Súgó\tF1", self._sugo)

        self.PopupMenu(m)
        m.Destroy()

    # ---- a zenetár betöltése -------------------------------------------

    def _mappat_valaszt(self):
        # A BEÉPÍTETT választó: a Windowsé idegen bővítményeket tölt be, és
        # azok viszik magukkal az egész programot (Dr. Kiss István naplója).
        mappa = ""
        try:
            from superdl import fajlvalaszto
            mappa = fajlvalaszto.valassz_mappat(
                self, "Zenemappa kiválasztása", KT.gyoker_betolt(),
                mondd=lambda s: _mondd(self.main, s)) or ""
        except Exception:
            with wx.DirDialog(self, "Zenemappa kiválasztása") as d:
                mappa = d.GetPath() if d.ShowModal() == wx.ID_OK else ""
        if mappa:
            KT.gyoker_ment(mappa)
            self._beolvas(mappa)

    def _ujraolvas(self):
        gyoker = KT.gyoker_betolt()
        if gyoker:
            self._beolvas(gyoker)
        else:
            self._allapot("Előbb válassz zenemappát: Ctrl+O.")

    def _beolvas(self, gyoker, csendes_kezdet=False):
        if not csendes_kezdet:
            self._allapot("Zenék keresése…")
        self._megall.clear()

        def munka():
            szamok, mappak = KT.beolvas(gyoker, self._megall)
            wx.CallAfter(self._betoltve, szamok, mappak)

        threading.Thread(target=munka, daemon=True).start()

    def _betoltve(self, szamok, mappak):
        if self._closing:
            return
        self._szamok = szamok
        self.lista.Set([s.felirat() for s in szamok])
        self._index = -1
        if szamok:
            self.lista.SetSelection(0)
            self._allapot(f"{mappak} mappa, {len(szamok)} szám. "
                          f"A lejátszáshoz nyilazz, vagy nyomj Entert.")
        else:
            self._allapot("Ebben a mappában nincs lejátszható zene.")

    # ---- lejátszás ------------------------------------------------------

    def _motor(self):
        if self._lejatszo is None:
            from .keverolejatszo import KeveroLejatszo
            self._lejatszo = KeveroLejatszo(
                on_vege=lambda: wx.CallAfter(self._szam_vege),
                on_attunes_ido=lambda: wx.CallAfter(self._attunes_ideje),
                on_hiba=lambda s: wx.CallAfter(self._hiba, s))
            self._lejatszo.fo_hangero = self._hangero
        return self._lejatszo

    def _kijelolt_indul(self):
        i = self.lista.GetSelection()
        if 0 <= i < len(self._szamok) and i != self._index:
            self._indit(i)

    def _indit(self, i, attunessel=False):
        if not (0 <= i < len(self._szamok)):
            return
        self._index = i
        szam = self._szamok[i]
        if self.lista.GetSelection() != i:
            self.lista.SetSelection(i)
        h = KT.hossz(szam.ut)
        m = self._motor()
        if attunessel:
            m.attunes_ra(szam.ut, h)
        else:
            m.jatszik(szam.ut, h)
        self._allapot(szam.felirat())

    def _lep(self, irany):
        if not self._szamok:
            self._allapot("Nincs betöltve zene.")
            return
        alap = self._index if self._index >= 0 else self.lista.GetSelection()
        self._indit((max(0, alap) + irany) % len(self._szamok))

    def _kovetkezo_index(self):
        if not self._szamok:
            return -1
        return (self._index + 1) % len(self._szamok)

    def _attunes_ideje(self):
        """Három másodperccel a vége előtt: jöhet a következő."""
        if self._closing or self._ismetles or not self._tovabb:
            return
        k = self._kovetkezo_index()
        if k >= 0:
            self._indit(k, attunessel=True)

    def _szam_vege(self):
        """A szám a végére ért ÁTTŰNÉS NÉLKÜL (nincs hossz, vagy nem ment)."""
        if self._closing:
            return
        if self._ismetles:
            self._indit(self._index)
            return
        if not self._tovabb:
            self._allapot("A szám véget ért.")
            return
        k = self._kovetkezo_index()
        if k >= 0:
            self._indit(k)

    def _hiba(self, szoveg):
        if self._closing:
            return
        self._allapot(f"Ez a szám nem játszható le. {szoveg}")

    # ---- billentyűk ------------------------------------------------------

    def _on_key(self, e):
        kod, ctrl, shift = e.GetKeyCode(), e.ControlDown(), e.ShiftDown()
        if kod == wx.WXK_ESCAPE:
            self.Close()
            return
        if kod == wx.WXK_F1:
            self._sugo()
            return
        if kod == wx.WXK_F3:
            self._kovetkezo_talalat()
            return
        if kod == wx.WXK_F5:
            self._ujraolvas()
            return
        if kod == wx.WXK_WINDOWS_MENU or (shift and kod == wx.WXK_F10):
            self._helyi_menu()
            return
        if ctrl and kod == wx.WXK_UP:
            self._hangero_allit(HANGERO_LEPES)
            return
        if ctrl and kod == wx.WXK_DOWN:
            self._hangero_allit(-HANGERO_LEPES)
            return
        if ctrl and shift and kod in (ord("M"), ord("m")):
            self._intezoben()
            return
        if ctrl and kod in (ord("O"), ord("o")):
            self._mappat_valaszt()
            return
        if ctrl and kod in (ord("R"), ord("r")):
            self._ismetles_valt()
            return
        if ctrl and kod in (ord("E"), ord("e")):
            self._tovabb_valt()
            return
        if ctrl and kod in (ord("S"), ord("s")):
            self._alvas_parbeszed()
            return
        if ctrl and kod in (ord("I"), ord("i")):
            self._hol_tartunk()
            return
        if ctrl and kod in (ord("F"), ord("f")):
            self._keres()
            return
        if ctrl and kod in (ord("G"), ord("g")):
            self._ugras_mappara()
            return
        if ctrl and kod in (ord("T"), ord("t")):
            self._veletlen()
            return
        if ctrl and kod in (ord("C"), ord("c")):
            self._vagolapra()
            return
        if kod == wx.WXK_SPACE:
            self._szunet()
            return
        if kod == wx.WXK_LEFT:
            self._teker(-TEKERES_MP)
            return
        if kod == wx.WXK_RIGHT:
            self._teker(TEKERES_MP)
            return
        e.Skip()

    # ---- műveletek -------------------------------------------------------

    def _szunet(self):
        if self._lejatszo is None or not self._lejatszo.szol():
            i = self.lista.GetSelection()
            if 0 <= i < len(self._szamok):
                self._indit(i)
            return
        self._allapot("Szünet." if self._lejatszo.szunet_valt()
                      else "Folytatás.")

    def _teker(self, delta):
        if self._lejatszo is None or not self._lejatszo.szol():
            return
        self._lejatszo.teker(delta)
        self._allapot(KT.ido_szoveg(self._lejatszo.pozicio()))

    def _hangero_allit(self, delta):
        self._hangero = max(0.0, min(1.0, self._hangero + delta))
        if self._lejatszo is not None:
            self._lejatszo.fo_hangero_allit(self._hangero)
        self._allapot("Hangerő %d százalék." % round(self._hangero * 100))

    def _ismetles_valt(self):
        self._ismetles = not self._ismetles
        self._allapot("Ismétlés bekapcsolva." if self._ismetles
                      else "Ismétlés kikapcsolva.")

    def _tovabb_valt(self):
        self._tovabb = not self._tovabb
        self._allapot("A szám végén megy a következőre." if self._tovabb
                      else "A szám végén megáll.")

    def _keres(self):
        d = wx.TextEntryDialog(self, "Mit keresel a számok között?",
                               "Keresés", self._keresett)
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            self._keresett = d.GetValue().strip()
        finally:
            d.Destroy()
        if not self._keresett:
            return
        self._talalat_keres(self.lista.GetSelection(), elsotol=True)

    def _kovetkezo_talalat(self):
        if not self._keresett:
            self._keres()
            return
        self._talalat_keres(self.lista.GetSelection() + 1)

    def _talalat_keres(self, tol, elsotol=False):
        """A keresés KÖRBEFORDUL, és megmondja, hányadik találat."""
        minta = self._keresett.lower()
        n = len(self._szamok)
        if not n:
            self._allapot("Nincs betöltve zene.")
            return
        kezdet = 0 if elsotol else max(0, tol)
        for eltolas in range(n):
            i = (kezdet + eltolas) % n
            if minta in self._szamok[i].felirat().lower():
                self.lista.SetSelection(i)
                self.lista.SetFocus()
                self._indit(i)
                return
        self._allapot(f"Nincs találat erre: {self._keresett}.")

    def _ugras_mappara(self):
        mappak = []
        for s in self._szamok:
            if not mappak or mappak[-1] != s.mappa:
                if s.mappa not in mappak:
                    mappak.append(s.mappa)
        if not mappak:
            self._allapot("Nincs betöltve zene.")
            return
        nevek = [m or "(a gyökérmappában)" for m in mappak]
        d = wx.SingleChoiceDialog(self, "Melyik mappára ugorjunk?",
                                  "Ugrás mappára", nevek)
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            cel = mappak[d.GetSelection()]
        finally:
            d.Destroy()
        for i, s in enumerate(self._szamok):
            if s.mappa == cel:
                self._indit(i)
                self.lista.SetFocus()
                return

    def _veletlen(self):
        if not self._szamok:
            self._allapot("Nincs betöltve zene.")
            return
        if len(self._szamok) == 1:
            self._indit(0)
            return
        i = self._index
        while i == self._index:
            i = random.randrange(len(self._szamok))
        self._indit(i)
        self.lista.SetFocus()

    def _vagolapra(self):
        i = self._index if self._index >= 0 else self.lista.GetSelection()
        if not (0 <= i < len(self._szamok)):
            self._allapot("Nincs kiválasztott szám.")
            return
        s = self._szamok[i]
        if wx.TheClipboard.Open():
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(
                    f"{s.felirat()}\n{s.ut}"))
            finally:
                wx.TheClipboard.Close()
            self._allapot("A szám neve és útja a vágólapon.")
        else:
            self._allapot("A vágólap most nem érhető el.")

    def _intezoben(self):
        i = self._index if self._index >= 0 else self.lista.GetSelection()
        if not (0 <= i < len(self._szamok)):
            self._allapot("Nincs kiválasztott szám.")
            return
        ut = self._szamok[i].ut
        try:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(ut)])
            self._allapot("A mappa megnyílt az Intézőben.")
        except Exception as ex:
            self._allapot(f"A mappát nem sikerült megnyitni. {ex}")

    def _hol_tartunk(self):
        if not self._szamok:
            self._allapot("Nincs betöltve zene.")
            return
        reszek = []
        if 0 <= self._index < len(self._szamok):
            s = self._szamok[self._index]
            reszek.append(f"{self._index + 1}. a {len(self._szamok)}-ból: "
                          f"{s.felirat()}")
        if self._lejatszo is not None and self._lejatszo.szol():
            h = self._lejatszo.hossz()
            p = KT.ido_szoveg(self._lejatszo.pozicio())
            reszek.append(p + (f", ebből {KT.ido_szoveg(h)}" if h else ""))
            if self._lejatszo.szunetel():
                reszek.append("szünetel")
        reszek.append("hangerő %d százalék" % round(self._hangero * 100))
        reszek.append("ismétlés be" if self._ismetles else "ismétlés ki")
        reszek.append("a végén tovább" if self._tovabb else "a végén megáll")
        if self._alvas_vege:
            hatra = max(0, self._alvas_vege - time.time())
            reszek.append(f"elalvásig {KT.ido_szoveg(hatra)}")
        self._allapot(". ".join(reszek) + ".")

    # ---- elalvás ---------------------------------------------------------

    def _alvas_hatra_perc(self) -> int:
        if not self._alvas_vege:
            return 0
        return max(0, int((self._alvas_vege - time.time()) / 60) + 1)

    def _alvas_parbeszed(self):
        valasztek = ["Kikapcsolás"] + [f"{p} perc" for p in ALVAS_PERCEK]
        d = wx.SingleChoiceDialog(self, "Mennyi idő múlva álljon le a zene?",
                                  "Elalvás", valasztek)
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            i = d.GetSelection()
        finally:
            d.Destroy()
        if i <= 0:
            self._alvas_vege = 0.0
            if self._lejatszo is not None:
                self._lejatszo.hangero(1.0)
            self._allapot("Az elalvás kikapcsolva.")
            return
        perc = ALVAS_PERCEK[i - 1]
        self._alvas_vege = time.time() + perc * 60
        if self._lejatszo is not None:
            self._lejatszo.hangero(1.0)
        self._allapot(f"Elalvás {perc} perc múlva.")

    def _on_ora(self, e):
        """Másodpercenként. CSAK bemondás és hangerő – ablakot NEM nyit.

        (4.6.7 tanulsága: időzítő-visszahívásból indított ablak vagy értesítés
        összeomlást okozott. Itt semmi ilyen nincs.)
        """
        if self._closing or not self._alvas_vege:
            return
        hatra = self._alvas_vege - time.time()
        if hatra <= 0:
            self._alvas_vege = 0.0
            if self._lejatszo is not None:
                self._lejatszo.leallit()
                self._lejatszo.hangero(1.0)
            wx.CallAfter(self._allapot, "Az elalvás ideje letelt, a zene leállt.")
            return
        if hatra <= ALVAS_HALKULAS_MP and self._lejatszo is not None:
            # lassú elhalkulás: kellemesebb, mint a hirtelen csend
            self._lejatszo.hangero(max(0.0, hatra / ALVAS_HALKULAS_MP))

    # ---- súgó, zárás ------------------------------------------------------

    def _sugo(self):
        d = wx.Dialog(self, title="Zene – súgó", size=(760, 620))
        v = wx.BoxSizer(wx.VERTICAL)
        t = wx.TextCtrl(d, value=SUGO,
                        style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        t.SetName("Zene súgó szövege")
        v.Add(t, 1, wx.EXPAND | wx.ALL, 8)
        v.Add(d.CreateStdDialogButtonSizer(wx.OK), 0,
              wx.ALIGN_CENTER | wx.ALL, 8)
        d.SetSizer(v)
        t.SetFocus()
        d.ShowModal()
        d.Destroy()

    def _on_close(self, e):
        self._closing = True
        self._megall.set()
        try:
            self._ora.Stop()
        except Exception:
            pass
        if self._lejatszo is not None:
            try:
                self._lejatszo.bezar()
            except Exception:
                pass
        e.Skip()
