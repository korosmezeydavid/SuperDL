# -*- coding: utf-8 -*-
"""Zene – a lehető legegyszerűbb lejátszó. Egy lista, és szól.

Ez a modul SZÁNDÉKOSAN nem tud mást: nincs lejátszási lista, keverés,
kedvencek, hangerő-csúszka, címke-szerkesztés. Egy mappát adsz meg, minden
alatta lévő szám bekerül egy listába, fel-le nyíllal lépkedsz, és szól.
"""

import os
import threading
import time

import wx

from . import konyvtar as KT

ALVAS_PERCEK = (5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60)
TEKERES_MP = 5.0
ALVAS_HALKULAS_MP = 10.0       # ennyivel a vége előtt kezd elhalkulni

SUGO = """ZENE – EGYSZERŰ LEJÁTSZÓ

MIRE VALÓ
Zenét játszik. Semmi mást nem tud.

INDULÁS
A „Zenemappa kiválasztása” gombbal adj meg EGY mappát. Ami alatta van –
akárhány almappában, akármilyen mélyen –, az mind bekerül a listába. A
választásod megjegyződik, legközelebb magától betölt.

BILLENTYŰK
  Fel, le nyíl ....... előző, következő szám (azonnal szól)
  Bal, jobb nyíl ..... tekerés a számon belül, 5 másodpercenként
  Szóköz ............. szünet, és újra szóköz: folytatás
  Ctrl+R ............. ismétlés be- és kikapcsolása
  Ctrl+E ............. a szám végén álljon meg / menjen a következőre
  Ctrl+S ............. elalvás időzítő (5-től 60 percig)
  Ctrl+I ............. hol tartunk (szám, idő, elalvás)
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
        self._alvas_percek = 0
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
            self._allapot("Válassz egy zenemappát. A gomb a lista alatt van, "
                          "vagy nyomd meg a Ctrl+O-t.")

    # ---- felépítés ----------------------------------------------------

    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        self.cimke = wx.StaticText(
            p, label="&Számok (fel-le nyíl: váltás és lejátszás):")
        v.Add(self.cimke, 0, wx.LEFT | wx.TOP, 8)

        self.lista = wx.ListBox(p, style=wx.LB_SINGLE)
        self._nev(self.lista, "Számok listája")
        self.lista.Bind(wx.EVT_LISTBOX, lambda e: self._kijelolt_indul())
        v.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        b = wx.Button(p, label="Zene&mappa kiválasztása…\tCtrl+O")
        b.Bind(wx.EVT_BUTTON, lambda e: self._mappat_valaszt())
        sor.Add(b, 0, wx.RIGHT, 6)
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

    def _beolvas(self, gyoker, csendes_kezdet=False):
        if not csendes_kezdet:
            self._allapot("Zenék keresése…")
        self._megall.clear()

        def munka():
            t0 = time.time()
            szamok, mappak = KT.beolvas(gyoker, self._megall)
            wx.CallAfter(self._betoltve, szamok, mappak, time.time() - t0)

        threading.Thread(target=munka, daemon=True).start()

    def _betoltve(self, szamok, mappak, mp):
        if self._closing:
            return
        self._szamok = szamok
        self.lista.Set([s.felirat() for s in szamok])
        self._index = -1
        if szamok:
            self.lista.SetSelection(0)
            self._allapot(f"{mappak} mappa, {len(szamok)} szám. "
                          f"A lejátszáshoz nyomj Entert vagy nyilazz.")
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
        kod, ctrl = e.GetKeyCode(), e.ControlDown()
        if kod == wx.WXK_ESCAPE:
            self.Close()
            return
        if kod == wx.WXK_F1:
            self._sugo()
            return
        if ctrl and kod in (ord("O"), ord("o")):
            self._mappat_valaszt()
            return
        if ctrl and kod in (ord("R"), ord("r")):
            self._ismetles = not self._ismetles
            self._allapot("Ismétlés bekapcsolva." if self._ismetles
                          else "Ismétlés kikapcsolva.")
            return
        if ctrl and kod in (ord("E"), ord("e")):
            self._tovabb = not self._tovabb
            self._allapot("A szám végén megy a következőre."
                          if self._tovabb else "A szám végén megáll.")
            return
        if ctrl and kod in (ord("S"), ord("s")):
            self._alvas_parbeszed()
            return
        if ctrl and kod in (ord("I"), ord("i")):
            self._hol_tartunk()
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

    def _hol_tartunk(self):
        if not self._szamok:
            self._allapot("Nincs betöltve zene.")
            return
        reszek = []
        if 0 <= self._index < len(self._szamok):
            reszek.append(self._szamok[self._index].felirat())
        if self._lejatszo is not None and self._lejatszo.szol():
            h = self._lejatszo.hossz()
            p = KT.ido_szoveg(self._lejatszo.pozicio())
            reszek.append(f"{p}" + (f", ebből {KT.ido_szoveg(h)}" if h else ""))
        reszek.append("ismétlés be" if self._ismetles else "ismétlés ki")
        reszek.append("a végén tovább" if self._tovabb else "a végén megáll")
        if self._alvas_vege:
            hatra = max(0, self._alvas_vege - time.time())
            reszek.append(f"elalvásig {KT.ido_szoveg(hatra)}")
        self._allapot(". ".join(reszek) + ".")

    # ---- elalvás ---------------------------------------------------------

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
            self._alvas_percek = 0
            if self._lejatszo is not None:
                self._lejatszo.hangero(1.0)
            self._allapot("Az elalvás kikapcsolva.")
            return
        perc = ALVAS_PERCEK[i - 1]
        self._alvas_percek = perc
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
        d = wx.Dialog(self, title="Zene – súgó", size=(760, 600))
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
