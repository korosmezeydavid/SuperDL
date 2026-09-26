# -*- coding: utf-8 -*-
"""Akciós újság – az ablak.

Bolt → kategória → kereső → terméklista → részletek. A kijelölt termék
Ctrl+L-lel a saját bevásárlólistára kerül; a lista (Ctrl+B) a gépen van,
és egy mozdulattal összefésülhető a telefon bevásárlólistájával.

Minden a fő szálon marad, ami a felülethez nyúl; a letöltés háttérszálon.
"""
import os
import threading
import time

import wx

from . import bevasarlo as B
from . import csoport as CS
from . import forrasok as F
from .termek import illik

MIND = "Minden bolt"
OSSZES_KAT = "Minden kategória"
MIND_CSOP = "Minden termékcsoport"
RENDEZESEK = ("Bolt szerint", "Ár szerint, a legolcsóbb elöl", "Név szerint")

SUGO = """AKCIÓS ÚJSÁG – SÚGÓ

MIRE VALÓ
A boltok akcióit mutatja meg olvasható, nyilazható listában: Penny, Lidl,
Aldi, Tesco, Spar és Interspar, Auchan, Rossmann és dm. Nem kép és nem
találgatás: a boltok saját, nyilvános oldalairól és újságjaiból jön a
szöveg, ugyanaz, ami a papíron vagy a bolt honlapján áll.

HONNAN JÖN AZ ADAT
  Penny, Aldi ........ a bolt honlapjának akciós oldala (Aldinál az újság is)
  Lidl, Tesco, Spar .. a bolt saját akciós újságja (PDF). A Tescónál és a
                       Sparnál az árat a kiírt egységárból számoljuk – ez
                       a nyomtatott ár, sok darabos csomagnál pár forint
                       eltérés lehet
  Auchan ............. a heti és a tematikus katalógusok szövege; csak az
                       a termék marad, amelynek az ára az újságban is
                       szerepel (inkább kevesebb, mint rossz)
  Rossmann ........... a webshop akciós termékei és a Rossmann Plus
                       kártyás ajánlatai; ami csak online kapható, azt a
                       megjegyzés kimondja
  dm ................. a dm-nek nincs heti újsága; a kiárusított termékek
                       jönnek, a készlet erejéig
A pultos áruk (felvágott, sajt a pultból) ára kilónként értendő.

BÖNGÉSZÉS
  Bolt ............... Alt+B – egy bolt, vagy minden bolt egyszerre
  Termékcsoport ...... Alt+C – KÖZÖS csoportok minden boltban: Tejtermék és
                       tojás, Hús, hal, felvágott, Pékáru, Zöldség és
                       gyümölcs, Ital, Édesség és snack, Alapvető élelmiszer,
                       Fagyasztott, Háztartás, Drogéria, Baba, Állateledel,
                       Egyéb. Mindegyik mellett ott a darabszám. A csoportot a
                       program a termék nevéből állapítja meg; ami
                       bizonytalan, az az „Egyéb”-be kerül, nem rossz helyre.
  A bolt saját
  kategóriája ........ Alt+K – pl. Italok, Friss húsok (a Pennynél), Haj
                       (a Rossmannál), vagy az újság neve (Lidl, Tesco…)
  Keresés ............ Alt+E – gépelés közben szűr, ékezet nélkül is jó
                       („rantott” megtalálja a „Rántott”-at)
  Rendezés ........... Alt+R – bolt, ár vagy név szerint
  Termékek ........... Alt+T – a sor elején a név és az ár, utána a
                       kártyás ár, a kedvezmény és a kiszerelés. Ha minden
                       boltot nézel, a bolt neve rögtön az ár után jön.

HOL A LEGOLCSÓBB? Bolt: Minden bolt, Keresés: pl. joghurt, Rendezés: ár
szerint – a lista a legolcsóbbtól a legdrágábbig sorolja, bolttal együtt.
A kijelölt termék minden részlete (egységár, érvényesség, eredeti ár) az
alatta lévő mezőben olvasható.

BEVÁSÁRLÓLISTA
  Ctrl+L ............. a kijelölt termék felkerül a listádra (a bolt nevével,
                       hogy tudd, hol van akcióban)
  Ctrl+B ............. a bevásárlólista megnyitása
A lista a gépen van, net nélkül is megmarad. A listában:
  Szóköz ............. megvan / még nincs meg
  Delete ............. törlés
  Ctrl+N ............. új tétel kézzel
  Ctrl+T ............. összefésülés a TELEFON bevásárlólistájával
  Ctrl+E ............. a lista KIKÜLDÉSE: vágólapra (Messengerbe, e-mailbe
                       beilleszthető), fájlba (Word vagy szöveg), vagy
                       megnyitás a Super Editben. Ami már megvan, az a
                       végére kerül külön – a segítődnek csak az marad a
                       listán, amit még meg kell venni.
A telefonos összefésüléshez a telefonon kapcsold be a WiFi-portált (ugyanaz,
mint az Átjárónál), és add meg a telefon által bemondott PIN-t. A két lista
összeadódik: ami az egyiken van, a másikra is felkerül, és ami az egyik
helyen „megvan”, a másikon is az lesz. Semmit nem töröl.

FRISSÍTÉS
  F5 ................. az újságok letöltése újra
Megnyitáskor a legutóbbi letöltött újságok azonnal olvashatók, a friss adat
a háttérben jön. A Lidl, a Tesco és a Spar újságja nagy (több tíz
megabájt), a Rossmann pedig közel háromezer terméket ad, ezért az első
letöltés fél percig is eltarthat. A boltokat kíméletesen, szünetekkel
kérdezzük – ha valamelyik bolt épp lassítást kér, a program vár és újra
próbálja.

Az árak a boltok saját adatai; a program csak megmutatja őket. Nyomdai és
átvételi hibákért a program nem felel – vásárlás előtt a boltban nézd meg.
"""


def _mondd(main, szoveg):
    """Képernyőolvasó ELŐBB, a beépített hang csak utána (kötelező sorrend)."""
    if not (szoveg or "").strip():
        return
    try:
        from superdl import screenreader
        if screenreader.speak(szoveg):
            return
    except Exception:
        pass
    sv = getattr(main, "selfvoice", None)
    if sv:
        try:
            sv.speak(szoveg, force=True)
        except Exception:
            pass


class AkciokFrame(wx.Frame):
    # ennyi bolt töltődik egyszerre (a PDF-es boltok gépet is dolgoztatnak)
    PARHUZAMOS = 3

    def __init__(self, parent, core=None):
        super().__init__(parent, title="SuperDL – Akciós újság",
                         size=(900, 640))
        self.main = parent
        self.core = core
        self._closing = False
        self._adat = {}              # bolt_id -> [Termek]
        self._ido = {}               # bolt_id -> letöltés ideje
        self._lathato = []           # a listában épp látszó termékek
        self._tolt = False
        self._folyamatban = set()    # a most töltődő boltok
        self._build()
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.CreateStatusBar()
        self.Centre()
        wx.CallAfter(self._indul)

    # ---- felület ------------------------------------------------------
    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        felso = wx.FlexGridSizer(cols=2, vgap=6, hgap=8)
        felso.AddGrowableCol(1)
        felso.Add(wx.StaticText(p, label="&Bolt:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.bolt = wx.Choice(p, choices=[MIND] + [n for _a, n, _f in F.BOLTOK])
        self.bolt.SetName("Bolt")
        self.bolt.SetSelection(0)
        self.bolt.Bind(wx.EVT_CHOICE, lambda e: self._bolt_valt())
        felso.Add(self.bolt, 1, wx.EXPAND)

        # KÖZÖS termékcsoport minden bolthoz (Petrus József, 2026-09-26):
        # a „Tejtermék" a Lidlben is ugyanazt jelenti, mint a Pennyben
        felso.Add(wx.StaticText(p, label="Termék&csoport:"), 0,
                  wx.ALIGN_CENTER_VERTICAL)
        self.csop = wx.Choice(p, choices=[MIND_CSOP])
        self.csop.SetName("Termékcsoport")
        self.csop.SetSelection(0)
        self._csop_nevek = [""]
        self.csop.Bind(wx.EVT_CHOICE, lambda e: self._szur())
        felso.Add(self.csop, 1, wx.EXPAND)

        felso.Add(wx.StaticText(p, label="A bolt saját &kategóriája:"), 0,
                  wx.ALIGN_CENTER_VERTICAL)
        self.kat = wx.Choice(p, choices=[OSSZES_KAT])
        self.kat.SetName("A bolt saját kategóriája (a PDF-újságos "
                         "boltoknál az újság neve)")
        self.kat.SetSelection(0)
        self.kat.Bind(wx.EVT_CHOICE, lambda e: self._szur())
        felso.Add(self.kat, 1, wx.EXPAND)

        felso.Add(wx.StaticText(p, label="K&eresés:"), 0,
                  wx.ALIGN_CENTER_VERTICAL)
        self.kereso = wx.TextCtrl(p)
        self.kereso.SetName("Keresés a termékek közt")
        self.kereso.Bind(wx.EVT_TEXT, lambda e: self._szur(mondja=False))
        felso.Add(self.kereso, 1, wx.EXPAND)

        felso.Add(wx.StaticText(p, label="&Rendezés:"), 0,
                  wx.ALIGN_CENTER_VERTICAL)
        self.rendez = wx.Choice(p, choices=list(RENDEZESEK))
        self.rendez.SetName("Rendezés")
        self.rendez.SetSelection(0)
        self.rendez.Bind(wx.EVT_CHOICE, lambda e: self._szur())
        felso.Add(self.rendez, 1, wx.EXPAND)
        v.Add(felso, 0, wx.EXPAND | wx.ALL, 8)

        v.Add(wx.StaticText(p, label="&Termékek (Ctrl+L: fel a bevásárló"
                                     "listára):"), 0, wx.LEFT, 8)
        self.lista = wx.ListBox(p, style=wx.LB_SINGLE)
        self.lista.SetName("Akciós termékek")
        self.lista.Bind(wx.EVT_LISTBOX, lambda e: self._reszlet())
        v.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)

        v.Add(wx.StaticText(p, label="A kijelölt termék &adatai:"), 0,
              wx.LEFT, 8)
        self.reszlet = wx.TextCtrl(
            p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 110))
        self.reszlet.SetName("A kijelölt termék részletei")
        v.Add(self.reszlet, 0, wx.EXPAND | wx.ALL, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        for cimke, fv in (("&Felvétel a bevásárlólistára (Ctrl+L)",
                           self._felvesz),
                          ("Bevásárló&lista… (Ctrl+B)", self._lista_ablak),
                          ("Fri&ssítés (F5)", lambda: self._letolt(True)),
                          ("Sú&gó (F1)", self._sugo),
                          ("Be&zárás", self.Close)):
            b = wx.Button(p, label=cimke)
            b.Bind(wx.EVT_BUTTON, lambda e, f=fv: f())
            sor.Add(b, 0, wx.RIGHT, 6)
        v.Add(sor, 0, wx.ALL, 8)
        p.SetSizer(v)

        ids = {k: wx.NewIdRef() for k in ("fel", "lista", "friss", "sugo")}
        self.Bind(wx.EVT_MENU, lambda e: self._felvesz(), id=ids["fel"])
        self.Bind(wx.EVT_MENU, lambda e: self._lista_ablak(), id=ids["lista"])
        self.Bind(wx.EVT_MENU, lambda e: self._letolt(True), id=ids["friss"])
        self.Bind(wx.EVT_MENU, lambda e: self._sugo(), id=ids["sugo"])
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord("L"), ids["fel"]),
            (wx.ACCEL_CTRL, ord("B"), ids["lista"]),
            (wx.ACCEL_NORMAL, wx.WXK_F5, ids["friss"]),
            (wx.ACCEL_NORMAL, wx.WXK_F1, ids["sugo"]),
        ]))
        self.lista.SetFocus()

    def _mond(self, szoveg, mondja=True):
        if self._closing:
            return
        try:
            self.SetStatusText((szoveg or "").split("\n")[0])
        except Exception:
            pass
        if mondja:
            _mondd(self.main, szoveg)

    # ---- adatok ---------------------------------------------------------
    def _indul(self):
        regi = []
        for azon, nev, _f in F.BOLTOK:
            termekek, ido = F.mentett(azon)
            if termekek:
                self._adat[azon], self._ido[azon] = termekek, ido
                regi.append("%s %d" % (nev, len(termekek)))
        self._kategoriak()
        self._szur(mondja=False)
        if regi:
            self._mond("Akciós újság. A legutóbb letöltött ajánlatok: %s "
                       "termék. Frissítés a háttérben. Súgó: F1."
                       % ", ".join(regi))
        else:
            self._mond("Akciós újság. Az újságok letöltése folyik, egy kis "
                       "türelmet – a Lidl újságja nagy. Súgó: F1.")
        self._letolt(False)

    def _letolt(self, eroltetett):
        if self._tolt:
            self._mond("A letöltés már folyik.")
            return
        kellenek = [a for a, _n, _f in F.BOLTOK
                    if eroltetett or not F.friss_e(self._ido.get(a, 0))]
        if not kellenek:
            return
        self._tolt = True
        if eroltetett:
            self._mond("Az újságok letöltése újra…")

        def jelez(s):
            wx.CallAfter(self._mond, s, False)

        # ⚠️ Stolmár Barbara (2026-09-26): „a Lidl és a dm mindig nullát
        # mond". Az ok: a boltok EGYMÁS UTÁN jöttek, a Lidl négy nagy PDF-je
        # egy-másfél percig tartott, és ami mögötte állt (Aldi … dm), addig
        # üres volt – a lista „0 termék"-et mondott, mintha nem lenne akció.
        # Most a boltok PÁRHUZAMOSAN töltődnek (egyszerre legfeljebb
        # PARHUZAMOS), és amíg egy bolt töltődik, azt mondjuk, nem a nullát.
        self._folyamatban = set(kellenek)
        eredmeny = []
        zar = threading.Lock()
        maradt = [len(kellenek)]
        kapu = threading.Semaphore(self.PARHUZAMOS)

        def egy(azon):
            with kapu:
                if self._closing:
                    t, hiba = None, None
                else:
                    try:
                        t, hiba = F.letolt(azon, jelez), None
                    except Exception as ex:       # noqa: BLE001
                        t, hiba = None, ex
            if not self._closing:
                wx.CallAfter(self._megjott, azon, t, hiba)
            with zar:
                if t:
                    eredmeny.append("%s %d" % (F.bolt_nev(azon), len(t)))
                maradt[0] -= 1
                utolso = maradt[0] == 0
            if utolso and not self._closing:
                wx.CallAfter(self._kesz, eredmeny)

        for azon in kellenek:
            threading.Thread(target=egy, args=(azon,), daemon=True,
                             name="akciok-" + azon).start()

    def _megjott(self, azon, termekek, hiba):
        if self._closing:
            return
        self._folyamatban.discard(azon)
        if hiba is not None or not termekek:
            ok = str(hiba) if hiba else "nem adott egyetlen terméket sem"
            van = " A legutóbb letöltött adatot mutatom." \
                if self._adat.get(azon) else ""
            self._mond("%s: most nem sikerült letölteni (%s).%s"
                       % (F.bolt_nev(azon), ok, van))
            return
        varta = not self._adat.get(azon)
        self._adat[azon], self._ido[azon] = termekek, time.time()
        valasztott = self._valasztott_bolt()
        if valasztott not in (None, azon):
            return            # más boltot nézel: a listádhoz nem nyúlunk
        self._kategoriak()
        self._szur(mondja=False, megtart=True)
        if valasztott == azon and varta:
            # erre vártál – szólunk, hogy megjött
            self._mond("Megjött: %s, %d termék." % (F.bolt_nev(azon),
                                                    len(self._lathato)))

    def _kesz(self, eredmeny):
        self._tolt = False
        self._folyamatban = set()
        if eredmeny and not self._closing:
            self._mond("Frissítve: %s akciós termék." % ", ".join(eredmeny))

    def _valasztott_bolt(self):
        i = self.bolt.GetSelection()
        return None if i <= 0 else F.BOLTOK[i - 1][0]

    def _forras(self):
        b = self._valasztott_bolt()
        if b:
            return list(self._adat.get(b, []))
        return [t for a, _n, _f in F.BOLTOK for t in self._adat.get(a, [])]

    def _csoportok(self):
        """A termékcsoport-választó, DARABSZÁMMAL („Tejtermék és tojás, 38"):
        vakon így már a választás előtt hallod, hol van mit keresni."""
        i = self.csop.GetSelection()
        regi = self._csop_nevek[i] if 0 <= i < len(self._csop_nevek) else ""
        db = {}
        for t in self._forras():
            c = CS.csoportja(t)
            db[c] = db.get(c, 0) + 1
        nevek = [""] + [c for c in CS.CSOPORTOK if db.get(c)]
        self._csop_nevek = nevek
        self.csop.Set([MIND_CSOP] + ["%s, %d" % (c, db[c]) for c in nevek[1:]])
        self.csop.SetSelection(nevek.index(regi) if regi in nevek else 0)

    def _valasztott_csoport(self) -> str:
        i = self.csop.GetSelection()
        return self._csop_nevek[i] if 0 < i < len(self._csop_nevek) else ""

    def _kategoriak(self):
        self._csoportok()
        regi = self.kat.GetStringSelection()
        katok = []
        for t in self._forras():
            if t.kategoria and t.kategoria not in katok:
                katok.append(t.kategoria)
        self.kat.Set([OSSZES_KAT] + katok)
        i = self.kat.FindString(regi) if regi else 0
        self.kat.SetSelection(i if i != wx.NOT_FOUND else 0)

    def _bolt_valt(self):
        self._kategoriak()
        self._szur()

    def szurt(self, termekek, kategoria, kereses, rendezes, csoport=""):
        """A szűrés és rendezés – külön, hogy tesztelhető legyen."""
        ki = [t for t in termekek
              if (not kategoria or kategoria == OSSZES_KAT
                  or t.kategoria == kategoria)
              and (not csoport or CS.csoportja(t) == csoport)
              and illik(t, kereses)]
        if rendezes == 1:
            ki.sort(key=lambda t: (t.legjobb_ar() is None, t.legjobb_ar() or 0))
        elif rendezes == 2:
            ki.sort(key=lambda t: t.nev.lower())
        return ki

    def _szur(self, mondja=True, megtart=False):
        # háttérből érkező frissítésnél a kijelölt termék maradjon kijelölve
        # (ne ugorjon a lista elejére, miközben valaki épp olvassa)
        elotte = self._kijelolt() if megtart else None
        self._lathato = self.szurt(self._forras(),
                                   self.kat.GetStringSelection(),
                                   self.kereso.GetValue(),
                                   self.rendez.GetSelection(),
                                   self._valasztott_csoport())
        self.lista.Freeze()
        try:
            bolttal = self._valasztott_bolt() is None
            self.lista.Set([t.sor(bolttal) for t in self._lathato])
        finally:
            self.lista.Thaw()
        if self._lathato:
            hely = 0
            if elotte is not None:
                hely = next((i for i, t in enumerate(self._lathato)
                             if t.bolt == elotte.bolt and t.nev == elotte.nev
                             and t.ar == elotte.ar), 0)
            self.lista.SetSelection(hely)
        self._reszlet()
        szoveg = self._darab_szoveg()
        if mondja:
            self._mond(szoveg)
        else:
            self.SetStatusText(szoveg)

    def _darab_szoveg(self) -> str:
        """„12 termék." – de ha a választott bolt még töltődik, azt mondjuk,
        nem a nullát (Barbara: „a Lidl mindig nullát mond")."""
        n = len(self._lathato)
        b = self._valasztott_bolt()
        tolt = [a for a, _n, _f in F.BOLTOK
                if a in self._folyamatban and not self._adat.get(a)]
        if b is not None and b in tolt:
            return ("%s: az ajánlatok még töltődnek, ez egy-két perc is "
                    "lehet. Szólok, ha megjöttek." % F.bolt_nev(b))
        if b is None and tolt:
            return "%d termék. Még töltődik: %s." % (
                n, ", ".join(F.bolt_nev(a) for a in tolt))
        return "%d termék." % n

    def _kijelolt(self):
        i = self.lista.GetSelection()
        return self._lathato[i] if 0 <= i < len(self._lathato) else None

    def _reszlet(self):
        t = self._kijelolt()
        self.reszlet.SetValue(t.reszletek() if t else "")

    # ---- bevásárlólista ---------------------------------------------------
    def _felvesz(self):
        t = self._kijelolt()
        if t is None:
            self._mond("Előbb válassz egy terméket a listából.")
            return
        adat = B.betolt()
        try:
            _tetel, uj = B.termek_hozzaad(adat, t)
        except ValueError as ex:
            self._mond(str(ex))
            return
        B.ment(adat)
        if uj:
            self._mond("Felvéve a bevásárlólistára: %s. A listán %d tétel van."
                       % (B.tetel_nev(t), len(B.tetelek(adat))))
        else:
            self._mond("Ez már rajta van a bevásárlólistán: %s."
                       % B.tetel_nev(t))

    def _lista_ablak(self):
        d = ListaDialog(self)
        d.ShowModal()
        d.Destroy()

    def _sugo(self):
        try:
            from superdl.helpdialog import show_help
            show_help(self, "Akciós újság", SUGO)
        except Exception:
            wx.MessageBox(SUGO, "Súgó – Akciós újság",
                          wx.OK | wx.ICON_INFORMATION, self)

    def _on_close(self, e):
        self._closing = True
        e.Skip()


class ListaDialog(wx.Dialog):
    """A saját bevásárlólista: pipálás, törlés, kézi tétel, telefon."""

    def __init__(self, szulo):
        super().__init__(szulo, title="Bevásárlólista", size=(640, 520))
        self.szulo = szulo
        self.adat = B.betolt()
        self._fut = False
        v = wx.BoxSizer(wx.VERTICAL)
        self.cim = wx.StaticText(self, label="")
        v.Add(self.cim, 0, wx.ALL, 8)
        v.Add(wx.StaticText(self, label="&Tételek (Szóköz: megvan / még "
                                        "nincs; Delete: törlés):"), 0, wx.LEFT, 8)
        self.lista = wx.ListBox(self, style=wx.LB_SINGLE)
        self.lista.SetName("Bevásárlólista tételei")
        self.lista.Bind(wx.EVT_KEY_DOWN, self._billentyu)
        v.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)
        sor = wx.BoxSizer(wx.HORIZONTAL)
        for cimke, fv in (("&Megvan / még nincs (Szóköz)", self._pipa),
                          ("T&örlés (Delete)", self._torol),
                          ("Ú&j tétel… (Ctrl+N)", self._uj),
                          ("Összefésülés a tele&fonnal… (Ctrl+T)",
                           self._telefon),
                          ("Lista &kiküldése… (Ctrl+E)", self._kuldes),
                          ("&Bezárás", lambda: self.EndModal(wx.ID_OK))):
            b = wx.Button(self, label=cimke)
            b.Bind(wx.EVT_BUTTON, lambda e, f=fv: f())
            sor.Add(b, 0, wx.RIGHT, 6)
        v.Add(sor, 0, wx.ALL, 8)
        self.SetSizer(v)
        ids = {k: wx.NewIdRef() for k in ("uj", "tel", "kuld")}
        self.Bind(wx.EVT_MENU, lambda e: self._uj(), id=ids["uj"])
        self.Bind(wx.EVT_MENU, lambda e: self._telefon(), id=ids["tel"])
        self.Bind(wx.EVT_MENU, lambda e: self._kuldes(), id=ids["kuld"])
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord("N"), ids["uj"]),
            (wx.ACCEL_CTRL, ord("T"), ids["tel"]),
            (wx.ACCEL_CTRL, ord("E"), ids["kuld"]),
        ]))
        self.SetEscapeId(wx.ID_OK)
        self._frissit()
        self.lista.SetFocus()
        n = len(B.tetelek(self.adat))
        wx.CallAfter(self.szulo._mond,
                     "Bevásárlólista, %d tétel." % n if n else
                     "A bevásárlólista üres. Az akciós termékek közül Ctrl+L-lel "
                     "vehetsz fel, vagy itt Ctrl+N-nel kézzel.")

    def _frissit(self, marad=None):
        lst = B.tetelek(self.adat)
        megvan = sum(1 for t in lst if t.get("checked"))
        self.cim.SetLabel("%s – %d tétel, ebből %d megvan. Összesen %d forint."
                          % (B.aktiv_nev(self.adat), len(lst), megvan,
                             B.osszeg(lst)))
        self.lista.Set([B.tetel_sor(t) for t in lst])
        if lst:
            i = marad if marad is not None else 0
            self.lista.SetSelection(max(0, min(i, len(lst) - 1)))

    def _kijelolt(self):
        i = self.lista.GetSelection()
        lst = B.tetelek(self.adat)
        return (i, lst[i]) if 0 <= i < len(lst) else (i, None)

    def _billentyu(self, e):
        k = e.GetKeyCode()
        if k == wx.WXK_SPACE:
            self._pipa()
        elif k in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            self._torol()
        else:
            e.Skip()

    def _pipa(self):
        i, t = self._kijelolt()
        if not t:
            return
        B.megvan_valt(self.adat, t["id"])
        B.ment(self.adat)
        self._frissit(i)
        self.szulo._mond(("Megvan: %s." if t.get("checked")
                          else "Még nincs meg: %s.") % t.get("name", ""))

    def _torol(self):
        i, t = self._kijelolt()
        if not t:
            return
        B.torol(self.adat, t["id"])
        B.ment(self.adat)
        self._frissit(i)
        self.szulo._mond("Törölve: %s." % t.get("name", ""))

    def _uj(self):
        d = wx.TextEntryDialog(self, "Mit vegyél fel a listára?", "Új tétel")
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            nev = d.GetValue().strip()
        finally:
            d.Destroy()
        if not nev:
            return
        try:
            _t, uj = B.hozzaad(self.adat, nev)
        except ValueError as ex:
            self.szulo._mond(str(ex))
            return
        B.ment(self.adat)
        self._frissit(len(B.tetelek(self.adat)) - 1)
        self.szulo._mond("Felvéve: %s." % nev if uj
                         else "Ez már rajta van: %s." % nev)

    # ---- kiküldés (Petrus József kérése, 2026-09-26) ---------------------

    def _super_edit_van(self) -> bool:
        main = getattr(self.szulo, "main", None)
        host = getattr(main, "_module_host", None)
        return "superedit_module" in (getattr(host, "_openers", None) or {})

    def _kuldes(self):
        if not B.tetelek(self.adat):
            self.szulo._mond("A lista üres, nincs mit kiküldeni.")
            return
        valasztek = [("vagolap", "Másolás a vágólapra – utána beillesztheted "
                                 "Messengerbe, e-mailbe"),
                     ("fajl", "Mentés fájlba (Word vagy szövegfájl)")]
        if self._super_edit_van():
            valasztek.append(("superedit", "Megnyitás a Super Editben – ott "
                                           "szerkesztheted, mentheted"))
        d = wx.SingleChoiceDialog(self, "Hogyan küldjem ki a listát?",
                                  "Lista kiküldése",
                                  [c for _k, c in valasztek])
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            mit = valasztek[d.GetSelection()][0]
        finally:
            d.Destroy()
        szoveg = B.szoveges(self.adat)
        if mit == "vagolap":
            if wx.TheClipboard.Open():
                try:
                    wx.TheClipboard.SetData(wx.TextDataObject(szoveg))
                finally:
                    wx.TheClipboard.Close()
                self.szulo._mond("A lista a vágólapon van – most beillesztheted "
                                 "(Ctrl+V) bárhová.")
            else:
                self.szulo._mond("A vágólap most foglalt, próbáld újra.")
            return
        if mit == "fajl":
            ut = self._fajlt_valaszt()
            if not ut:
                return
        else:
            ut = os.path.join(self._dokumentumok(), self._alap_nev() + ".txt")
        try:
            B.ment_fajlba(szoveg, ut)
        except Exception as ex:                  # noqa: BLE001
            self.szulo._mond("A mentés nem sikerült: %s" % ex)
            return
        if mit == "fajl":
            self.szulo._mond("Elmentve: %s, a %s mappába."
                             % (os.path.basename(ut),
                                os.path.basename(os.path.dirname(ut))))
            return
        nyit = getattr(getattr(self.szulo, "main", None), "open_media_file", None)
        if nyit is None:
            self.szulo._mond("Elmentve, de a Super Editet nem tudtam megnyitni: %s."
                             % ut)
            return
        self.EndModal(wx.ID_OK)
        nyit(ut)

    @staticmethod
    def _dokumentumok() -> str:
        d = os.path.join(os.path.expanduser("~"), "Documents")
        return d if os.path.isdir(d) else os.path.expanduser("~")

    def _alap_nev(self) -> str:
        return "Bevásárlólista %s" % time.strftime("%Y-%m-%d")

    def _fajlt_valaszt(self) -> str:
        with wx.FileDialog(
                self, "A lista mentése", defaultDir=self._dokumentumok(),
                defaultFile=self._alap_nev() + ".docx",
                wildcard="Word-dokumentum (*.docx)|*.docx|"
                         "Szövegfájl (*.txt)|*.txt",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as d:
            if d.ShowModal() != wx.ID_OK:
                return ""
            ut = d.GetPath()
            if not os.path.splitext(ut)[1]:
                ut += (".docx", ".txt")[max(0, d.GetFilterIndex())]
            return ut

    def _telefon(self):
        if self._fut:
            self.szulo._mond("Az összefésülés már folyik.")
            return
        ip, port = B.telefon_cim()
        d = wx.TextEntryDialog(
            self, "A telefon címe (ugyanaz, mint az Átjárónál; a telefon "
                  "WiFi-portálja bemondja):", "Telefon", ip)
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            ip = d.GetValue().strip()
        finally:
            d.Destroy()
        if not ip:
            return
        d = wx.TextEntryDialog(self, "A telefon által bemondott négyjegyű "
                                     "PIN:", "PIN")
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            pin = d.GetValue().strip()
        finally:
            d.Destroy()
        B.telefon_cim_ment(ip, port)
        self._fut = True
        self.szulo._mond("Összefésülés a telefonnal…")
        lista = B.aktiv_nev(self.adat)

        def munka():
            try:
                eredmeny = B.Telefon(ip, pin, port).szinkron(self.adat, lista)
                wx.CallAfter(self._telefon_kesz, eredmeny, None)
            except Exception as ex:               # noqa: BLE001
                wx.CallAfter(self._telefon_kesz, None, ex)

        threading.Thread(target=munka, daemon=True).start()

    def _telefon_kesz(self, eredmeny, hiba):
        self._fut = False
        if hiba is not None:
            if isinstance(hiba, B.RosszPin):
                ok = "rossz a PIN. Nézd meg, mit mond a telefon, és próbáld újra."
            else:
                ok = "nem érem el a telefont (%s). Be van kapcsolva a telefonon " \
                     "a WiFi-portál, és ugyanazon a WiFi-n vagytok?" % hiba
            self.szulo._mond("Az összefésülés nem sikerült: " + ok)
            return
        B.ment(self.adat)
        try:
            self._frissit()
        except RuntimeError:
            return                  # közben bezárták az ablakot
        self.szulo._mond(
            "Kész. A telefonról %d új tétel jött, a telefonra %d ment fel, "
            "%d tétel „megvan” jelzése egyezett össze. A telefonon ugyanez a "
            "lista: %s." % (eredmeny["le"], eredmeny["fel"], eredmeny["pipa"],
                            B.aktiv_nev(self.adat)))
