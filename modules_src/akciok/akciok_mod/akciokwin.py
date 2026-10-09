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

from . import beallitas as BE
from . import bevasarlo as B
from . import csoport as CS
from . import forrasok as F
from .termek import illik, lejart

MIND = "Minden bolt"
SAJAT = "Saját boltjaim"
OSSZES_KAT = "Minden kategória"
MIND_CSOP = "Minden termékcsoport"
RENDEZESEK = ("Bolt szerint", "Ár szerint, a legolcsóbb elöl", "Név szerint")

SUGO = """AKCIÓS ÚJSÁG – SÚGÓ

MIRE VALÓ
A boltok akcióit mutatja meg olvasható, nyilazható listában.
  Élelmiszer ......... Penny, Lidl, Aldi, Tesco, Spar és Interspar, Auchan
  Drogéria, kozmetika  Rossmann, dm, Müller (a parfümériával együtt), és az
                       Illatorium – a program készítőjének saját
                       parfümboltja (lásd lent)
  Vegyes áru ......... Pepco
  Könyv .............. Libri (a Könyvutca akciós könyvei)
  Műszaki, barkács ... Euronics, Praktiker
  Gyógyszertárak ...... BENU Gyógyszertár, PatikaPlus
Nem kép és nem
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
  Müller ............. a drogéria- és a parfüméria-prospektus (PDF). Az
                       egységárat itt nem mondjuk be, mert a prospektusból
                       nem olvasható ki pontosan
  Pepco .............. a heti újság a pepco.hu-n (csütörtökönként új)
  Libri .............. a Könyvutca akciós könyvei, szerzővel, borító árral
  Euronics ........... a heti ajánlatok és az éppen futó kampányok (pl.
                       „Jó árak jó helyen") az euronics.hu-n, eredeti
                       árral és érvényességgel
  Praktiker .......... az „Árzuhanás" oldal és a törzsvásárlói ajánlatok a
                       praktiker.hu-n; a törzsvásárlói árat kártyás árként
                       mondja, mellette a kártya nélküli árat
  BENU ............... a nyilvános akciós újság árkedvezményes termékei;
                       az ár az egyes gyógyszertárakban eltérhet
  PatikaPlus .......... a havi, patikában megvásárolható akciós termékek;
                       ár és készlet patikánként eltérhet
  MediaMarkt, OBI .... egyelőre nincsenek benne: az oldaluk az árakat csak
                       a böngészőben futó programmal rakja ki, szövegként
                       nem kapjuk meg
  Illatorium ......... Kőrösmezey Dávid, a SuperDL készítőjének saját
                       parfümboltja (illatorium.hu). Ez NEM akció, hanem a
                       bolt teljes kínálata, kb. 2400 illat árral és
                       kiszereléssel. A részleteknél ott áll, melyik ismert
                       parfüm ihlette, és ebben is kereshetsz: a „versace"
                       szóra kijönnek a Versace ihlette illatok. Ha a bolt
                       kínálata változik, a program magától követi.
A pultos áruk (felvágott, sajt a pultból) ára kilónként értendő.

BÖNGÉSZÉS
  Bolt ............... Alt+B – minden bolt, a SAJÁT boltjaid, egy boltfajta
                       egyszerre („Minden élelmiszerlánc", „Minden drogéria
                       és kozmetika", „Minden vegyes áru", „Minden
                       könyvesbolt", „Minden műszaki és barkácsbolt"),
                       vagy egyetlen bolt
  Saját boltjaim ..... Ctrl+Shift+B – pipáld ki, melyik boltok vannak a
                       településeden (pl. Spar, Lidl, Aldi). Utána a Bolt
                       választóban a „Saját boltjaim" csak ezekben keres,
                       és ez marad az alap, amíg mást nem választasz.
  Kedvencek .......... Ctrl+K – írd be, amit rendszeresen veszel („Mizse
                       ásványvíz", „Félix macskaeledel"). Minden frissítés
                       után a program szól, ha valamelyik akciós, és a
                       Kedvencek ablakban látod, hol mennyiért. Enter egy
                       kedvencen: a lista rögtön arra szűr.
  Lejárt akciók ...... az előző heti, már lejárt tételek nem jelennek meg
                       (a jövő hetiek igen, az érvényességnél látszik).
  Termékcsoport ...... Alt+C – KÖZÖS csoportok minden boltban: Tejtermék és
                       tojás, Hús, hal, felvágott, Pékáru, Zöldség és
                       gyümölcs, Ital, Édesség és snack, Alapvető élelmiszer,
                       Fagyasztott, Háztartás, Drogéria, Baba, Állateledel,
                       Műszaki cikk, Barkács és kert, Egyéb. Mindegyik
                       mellett ott a darabszám. A csoportot a
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

A BOLT OLDALA
  Ctrl+O ............. a kijelölt termék oldala a bolt honlapján (ha a bolt
                       ad ilyet), különben a bolt akciós oldala – a
                       böngésződben. Ahol a honlapon online is lehet
                       rendelni (Tesco, Auchan, Rossmann, dm, Libri,
                       Euronics, Praktiker), azt a
                       program kimondja, és a termék adatai közt is ott áll.
  Ctrl+Shift+C ....... ugyanez a cím a vágólapra – beillesztheted egy
                       levélbe vagy üzenetbe a segítődnek.

BEVÁSÁRLÓLISTA
  Ctrl+L ............. a kijelölt termék felkerül a listádra (a bolt nevével,
                       hogy tudd, hol van akcióban)
  Ctrl+B ............. a bevásárlólista megnyitása
A lista a gépen van, net nélkül is megmarad. A listában:
  Szóköz ............. megvan / még nincs meg
  Delete ............. törlés
  + és - ............. darabszám (Ctrl+D: beírva) – a végösszeg ár ×
                       darab
  Ctrl+Delete ........ a lista kiürítése (csak a megvan tételek, vagy az
                       egész)
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


class TermekLista(wx.ListCtrl):
    """VIRTUÁLIS terméklista – a ListBox helyett (szakember83, 2026-09-27).

    ⚠️ A 0.7.0-ban a „Minden bolt" nézet már kb. 12 000 terméket mutat
    (Rossmann, Libri, Illatorium…). A ListBox minden sort egyenként kap meg,
    és a képernyőolvasó minden sorról értesítést kér: nála a lista feltöltése
    több mint 20 másodpercre megakasztotta a programot – ráadásul minden
    beérkező boltnál újra. A virtuális lista a sorokat csak akkor kéri el,
    amikor megjelennek (vagy a képernyőolvasó rájuk lép), így a feltöltés
    azonnali, akármekkora a lista.

    A ListBox-nál megszokott hívásokat (Set, GetSelection, SetSelection,
    GetString, GetCount) ugyanúgy tudja, a kijelölés pedig EVT_LISTBOX-ot
    küld – a hívó kódnak nem kell tudnia a cseréről."""

    def __init__(self, szulo):
        super().__init__(szulo, style=wx.LC_REPORT | wx.LC_VIRTUAL
                         | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER)
        self.InsertColumn(0, "Termék")
        self._sorok = []
        self.Bind(wx.EVT_SIZE, self._meret)
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self._kijelolve)

    def _meret(self, e):
        try:
            self.SetColumnWidth(0, max(200, self.GetClientSize().width - 4))
        except Exception:
            pass
        e.Skip()

    def _kijelolve(self, e):
        ev = wx.CommandEvent(wx.wxEVT_LISTBOX, self.GetId())
        ev.SetEventObject(self)
        ev.SetInt(e.GetIndex())
        self.GetEventHandler().ProcessEvent(ev)
        e.Skip()

    def OnGetItemText(self, item, col):
        return self._sorok[item] if 0 <= item < len(self._sorok) else ""

    def Set(self, sorok):
        self._sorok = list(sorok)
        self.SetItemCount(len(self._sorok))
        self.Refresh()

    def GetCount(self):
        return len(self._sorok)

    def GetString(self, i):
        return self._sorok[i]

    def GetSelection(self):
        return self.GetFirstSelected()

    def SetSelection(self, i):
        if not (0 <= i < len(self._sorok)):
            return
        allapot = wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED
        regi = self.GetFirstSelected()
        if regi not in (-1, i):
            self.SetItemState(regi, 0, allapot)
        self.SetItemState(i, allapot, allapot)
        self.EnsureVisible(i)


def _nevelo(nev: str) -> str:
    """„a Penny", de „az Illatorium", „az Aldi"."""
    return ("az " if nev[:1].lower() in "aáeéiíoóöőuúüű" else "a ") + nev


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
        # MIND, a bolt-FAJTÁK (élelmiszer, drogéria, vegyes áru, könyv), majd
        # egyenként a boltok – Dávid ötlete (2026-09-27)
        self._bolt_ertekek = [None]
        cimkek = [MIND]
        self._be = BE.betolt()
        self._bolt_ertekek.append(("sajat", None))
        cimkek.append(SAJAT)
        for kulcs, cim in F.FAJTAK:
            if any(F.bolt_fajta(a) == kulcs for a, _n, _f in F.BOLTOK):
                self._bolt_ertekek.append(("fajta", kulcs))
                cimkek.append(cim)
        for a, n, _f in F.BOLTOK:
            self._bolt_ertekek.append(("bolt", a))
            cimkek.append(n)
        self.bolt = wx.Choice(p, choices=cimkek)
        self.bolt.SetName("Bolt")
        self.bolt.SetSelection(1 if self._sajat_boltok() else 0)
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
        self.lista = TermekLista(p)
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
                          ("&Megnyitás a bolt oldalán (Ctrl+O)",
                           self._megnyit),
                          ("&Hivatkozás másolása (Ctrl+Shift+C)",
                           self._masol),
                          ("Fri&ssítés (F5)", lambda: self._letolt(True)),
                          ("Saját bolt&jaim… (Ctrl+Shift+B)", self._boltjaim),
                          ("Ked&vencek… (Ctrl+K)", self._kedvencek),
                          ("Sú&gó (F1)", self._sugo),
                          ("Be&zárás", self.Close)):
            b = wx.Button(p, label=cimke)
            b.Bind(wx.EVT_BUTTON, lambda e, f=fv: f())
            sor.Add(b, 0, wx.RIGHT, 6)
        v.Add(sor, 0, wx.ALL, 8)
        p.SetSizer(v)

        ids = {k: wx.NewIdRef() for k in ("fel", "lista", "friss", "sugo",
                                          "nyit", "masol", "boltjaim", "kedv")}
        self.Bind(wx.EVT_MENU, lambda e: self._boltjaim(), id=ids["boltjaim"])
        self.Bind(wx.EVT_MENU, lambda e: self._kedvencek(), id=ids["kedv"])
        self.Bind(wx.EVT_MENU, lambda e: self._megnyit(), id=ids["nyit"])
        self.Bind(wx.EVT_MENU, lambda e: self._masol(), id=ids["masol"])
        self.Bind(wx.EVT_MENU, lambda e: self._felvesz(), id=ids["fel"])
        self.Bind(wx.EVT_MENU, lambda e: self._lista_ablak(), id=ids["lista"])
        self.Bind(wx.EVT_MENU, lambda e: self._letolt(True), id=ids["friss"])
        self.Bind(wx.EVT_MENU, lambda e: self._sugo(), id=ids["sugo"])
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord("L"), ids["fel"]),
            (wx.ACCEL_CTRL, ord("B"), ids["lista"]),
            (wx.ACCEL_NORMAL, wx.WXK_F5, ids["friss"]),
            (wx.ACCEL_NORMAL, wx.WXK_F1, ids["sugo"]),
            (wx.ACCEL_CTRL, ord("O"), ids["nyit"]),
            (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("C"), ids["masol"]),
            (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("B"), ids["boltjaim"]),
            (wx.ACCEL_CTRL, ord("K"), ids["kedv"]),
        ]))
        self.lista.SetFocus()

    # ---- saját boltjaim, kedvencek (Petrus József, 2026-09-28) ----------
    def _sajat_boltok(self) -> list:
        ismert = [a for a, _n, _f in F.BOLTOK]
        return [a for a in self._be.get("boltjaim", []) if a in ismert]

    def _boltjaim(self):
        d = SajatBoltjaimDialog(self, self._sajat_boltok())
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            valasztott = d.valasztott
        finally:
            d.Destroy()
        self._be["boltjaim"] = valasztott
        BE.ment(self._be)
        if valasztott:
            self.bolt.SetSelection(1)
            self._bolt_valt()
            self._mond("Saját boltjaim: %s. A lista most ezekben keres, %d termék."
                       % (", ".join(F.bolt_nev(a) for a in valasztott),
                          len(self._lathato)))
        else:
            if self.bolt.GetSelection() == 1:
                self.bolt.SetSelection(0)
                self._bolt_valt()
            self._mond("Nincs kijelölt saját bolt, minden boltban keresek.")

    def _minden_ervenyes(self) -> list:
        return [t for a, _n, _f in F.BOLTOK
                for t in self._adat.get(a, []) if not lejart(t.ervenyes)]

    def _kedvenc_talalatok(self) -> list:
        return BE.kedvenc_talalatok(self._be.get("kedvencek", []),
                                    self._minden_ervenyes())

    def _kedvencek_szol(self):
        """Frissítés után: melyik kedvenc akciós most."""
        if not self._be.get("kedvencek"):
            return
        szoveg = BE.kedvenc_osszefoglalo(self._kedvenc_talalatok())
        if szoveg:
            wx.CallLater(1500, self._mond, szoveg)

    def _kedvencek(self):
        d = KedvencekDialog(self)
        try:
            if d.ShowModal() == wx.ID_OK and d.valasztott:
                self.bolt.SetSelection(0)
                self._kategoriak()
                self.kereso.ChangeValue(d.valasztott)
                self.csop.SetSelection(0)
                self.kat.SetSelection(0)
                self._szur()
                self.lista.SetFocus()
        finally:
            d.Destroy()

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
            self._kedvencek_szol()
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
        if azon not in self._valasztott_boltok():
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
            self._kedvencek_szol()

    def _valasztott_bolt(self):
        """Az EGY kiválasztott bolt azonosítója – csoportnál és Mindennél
        None."""
        i = self.bolt.GetSelection()
        e = self._bolt_ertekek[i] if 0 <= i < len(self._bolt_ertekek) else None
        return e[1] if e and e[0] == "bolt" else None

    def _valasztott_boltok(self) -> list:
        i = self.bolt.GetSelection()
        e = self._bolt_ertekek[i] if 0 <= i < len(self._bolt_ertekek) else None
        if e is None:
            return [a for a, _n, _f in F.BOLTOK]
        if e[0] == "sajat":
            return self._sajat_boltok() or [a for a, _n, _f in F.BOLTOK]
        if e[0] == "fajta":
            return [a for a, _n, _f in F.BOLTOK if F.bolt_fajta(a) == e[1]]
        return [e[1]]

    def _forras(self):
        # a lejárt (előző heti) akciók nem kerülnek a listába
        return [t for a in self._valasztott_boltok()
                for t in self._adat.get(a, []) if not lejart(t.ervenyes)]

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
            arrend = self.rendez.GetSelection() == 1
            self.lista.Set([t.sor(bolttal, arrend) for t in self._lathato])
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
        tolt = [a for a in tolt if a in self._valasztott_boltok()]
        if b is None and tolt:
            return "%d termék. Még töltődik: %s." % (
                n, ", ".join(F.bolt_nev(a) for a in tolt))
        return "%d termék." % n

    def _kijelolt(self):
        i = self.lista.GetSelection()
        return self._lathato[i] if 0 <= i < len(self._lathato) else None

    def _reszlet(self):
        t = self._kijelolt()
        if not t:
            self.reszlet.SetValue("")
            return
        sorok = [t.reszletek()]
        azon = F.bolt_id_nevbol(t.bolt)
        if not t.hivatkozas() and F.bolt_oldal(azon):
            sorok.append("A bolt oldala: %s" % F.bolt_oldal(azon))
        if F.webshop(azon):
            sorok.append("A bolt honlapján online is rendelhetsz "
                         "(Ctrl+O: megnyitás).")
        self.reszlet.SetValue("\n".join(sorok))

    def _cim(self):
        """(cím, leírás) – a termék oldala, ha van, különben a bolt oldala."""
        t = self._kijelolt()
        if t is None:
            b = self._valasztott_bolt()
            return (F.bolt_oldal(b), "%s oldala" % _nevelo(F.bolt_nev(b))) \
                if b else ("", "")
        if t.hivatkozas():
            return t.hivatkozas(), "a termék oldala (%s)" % t.bolt
        azon = F.bolt_id_nevbol(t.bolt)
        return F.bolt_oldal(azon), "%s oldala" % _nevelo(t.bolt)

    def _megnyit(self):
        url, mi = self._cim()
        if not url:
            self._mond("Előbb válassz egy terméket vagy egy boltot.")
            return
        import webbrowser
        try:
            webbrowser.open(url)
        except Exception as ex:           # noqa: BLE001
            self._mond("Nem sikerült megnyitni a böngészőt: %s" % ex)
            return
        t = self._kijelolt()
        rendel = t is not None and F.webshop(F.bolt_id_nevbol(t.bolt))
        self._mond("Megnyitom a böngészőben: %s.%s" % (
            mi, " Itt online is rendelhetsz." if rendel else ""))

    def _masol(self):
        url, mi = self._cim()
        if not url:
            self._mond("Előbb válassz egy terméket vagy egy boltot.")
            return
        if wx.TheClipboard.Open():
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(url))
                wx.TheClipboard.Flush()     # a program bezárása után is maradjon
            finally:
                wx.TheClipboard.Close()
            self._mond("Kimásoltam a vágólapra: %s." % mi)
        else:
            self._mond("A vágólap most foglalt, próbáld újra.")

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


class SajatBoltjaimDialog(wx.Dialog):
    """A kijelölés állapotát minden sor neve kimondhatóan tartalmazza."""

    def __init__(self, parent, valasztott):
        super().__init__(parent, title="Saját boltjaim", size=(510, 520))
        self._boltok = [(a, n) for a, n, _f in F.BOLTOK]
        self._valasztott = set(valasztott)
        panel = wx.Panel(self)
        elrendezes = wx.BoxSizer(wx.VERTICAL)
        elrendezes.Add(wx.StaticText(
            panel, label="Fel és le nyíllal válassz boltot; szóközzel jelöld ki "
                         "vagy töröld a kijelölést. Tab: Mentés vagy Mégse."),
            0, wx.ALL | wx.EXPAND, 10)
        self.lista = wx.ListBox(panel, choices=[self._sor(i)
                                                for i in range(len(self._boltok))])
        self.lista.SetName("Saját boltjaim, szóköz: kijelölés váltása")
        self.lista.Bind(wx.EVT_KEY_DOWN, self._billentyu)
        elrendezes.Add(self.lista, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)
        gombok = wx.StdDialogButtonSizer()
        mentes = wx.Button(panel, wx.ID_OK, "Mentés")
        megse = wx.Button(panel, wx.ID_CANCEL, "Mégse")
        gombok.AddButton(mentes)
        gombok.AddButton(megse)
        gombok.Realize()
        elrendezes.Add(gombok, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        panel.SetSizer(elrendezes)
        keret = wx.BoxSizer(wx.VERTICAL)
        keret.Add(panel, 1, wx.EXPAND)
        self.SetSizer(keret)
        self.lista.SetSelection(0)
        self.lista.SetFocus()

    def _sor(self, index):
        azonosito, nev = self._boltok[index]
        return f"{nev}, {'kijelölve' if azonosito in self._valasztott else 'nincs kijelölve'}"

    def _billentyu(self, event):
        if event.GetKeyCode() != wx.WXK_SPACE:
            event.Skip()
            return
        self._valt()

    def _valt(self):
        index = self.lista.GetSelection()
        if index == wx.NOT_FOUND:
            return
        azonosito, _nev = self._boltok[index]
        if azonosito in self._valasztott:
            self._valasztott.remove(azonosito)
        else:
            self._valasztott.add(azonosito)
        self.lista.SetString(index, self._sor(index))
        self.lista.SetSelection(index)
        self.lista.SetFocus()
        _mondd(self, self._sor(index))

    @property
    def valasztott(self):
        return [a for a, _n in self._boltok if a in self._valasztott]


class KedvencekDialog(wx.Dialog):
    """Kedvencek: amit rendszeresen veszel – a program szól, ha akciós.
    Enter egy kedvencen: a főablak listája arra szűr (`valasztott`)."""

    def __init__(self, szulo):
        super().__init__(szulo, title="Kedvencek", size=(640, 480))
        self.szulo = szulo
        self.valasztott = ""
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(self, label="&Kedvenceid és hogy most hol "
                                        "akciósak (Enter: mutasd a listában; "
                                        "Delete: törlés):"), 0, wx.ALL, 8)
        self.lista = wx.ListBox(self, style=wx.LB_SINGLE)
        self.lista.SetName("Kedvencek")
        self.lista.Bind(wx.EVT_KEY_DOWN, self._billentyu)
        self.lista.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._mutat())
        v.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)
        sor = wx.BoxSizer(wx.HORIZONTAL)
        for cimke, fv in (("Ú&j kedvenc… (Ctrl+N)", self._uj),
                          ("&Mutasd a listában (Enter)", self._mutat),
                          ("T&örlés (Delete)", self._torol),
                          ("&Bezárás", lambda: self.EndModal(wx.ID_CANCEL))):
            b = wx.Button(self, label=cimke)
            b.Bind(wx.EVT_BUTTON, lambda e, f=fv: f())
            sor.Add(b, 0, wx.RIGHT, 6)
        v.Add(sor, 0, wx.ALL, 8)
        self.SetSizer(v)
        uj_id = wx.NewIdRef()
        self.Bind(wx.EVT_MENU, lambda e: self._uj(), id=uj_id)
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord("N"), uj_id)]))
        self.SetEscapeId(wx.ID_CANCEL)
        self._frissit()
        self.lista.SetFocus()
        n = len(self._talalatok)
        akcios = sum(1 for _k, l in self._talalatok if l)
        wx.CallAfter(self.szulo._mond,
                     "Kedvencek: %d, ebből most %d akciós." % (n, akcios) if n
                     else "Még nincs kedvenced. Ctrl+N-nel írd be, amit "
                          "rendszeresen veszel, például: Mizse ásványvíz.")

    def _frissit(self, marad=None):
        self._talalatok = self.szulo._kedvenc_talalatok()
        sorok = []
        for k, lista in self._talalatok:
            if not lista:
                sorok.append("%s – most nem akciós" % k)
                continue
            boltok, latott = [], set()
            for t in lista:
                if t.bolt in latott:
                    continue
                latott.add(t.bolt)
                ar = t.legjobb_ar()
                boltok.append("%s %d forint" % (t.bolt, ar) if ar is not None
                              else t.bolt)
            sorok.append("%s – %d akció: %s" % (k, len(lista), ", ".join(boltok)))
        self.lista.Set(sorok)
        if sorok:
            i = marad if marad is not None else 0
            self.lista.SetSelection(max(0, min(i, len(sorok) - 1)))

    def _kijelolt(self):
        i = self.lista.GetSelection()
        return (i, self._talalatok[i][0]) if 0 <= i < len(self._talalatok) \
            else (i, None)

    def _billentyu(self, e):
        k = e.GetKeyCode()
        if k in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._mutat()
        elif k in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            self._torol()
        else:
            e.Skip()

    def _uj(self):
        d = wx.TextEntryDialog(self, "Mit veszel rendszeresen? (Egy-két szó, "
                                     "ahogy a boltban hívják, például: Mizse "
                                     "ásványvíz)", "Új kedvenc")
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            szo = d.GetValue().strip()
        finally:
            d.Destroy()
        if not szo:
            return
        if not BE.kedvenc_hozzaad(self.szulo._be, szo):
            self.szulo._mond("Ez már a kedvenceid közt van: %s." % szo)
            return
        BE.ment(self.szulo._be)
        self._frissit(len(self.szulo._be["kedvencek"]) - 1)
        _k, lista = self._talalatok[-1]
        self.szulo._mond("Felvéve a kedvencek közé: %s. %s" % (
            szo, "Most %d akciós ajánlat van rá." % len(lista) if lista
            else "Most nem akciós; szólok, ha az lesz."))

    def _torol(self):
        i, k = self._kijelolt()
        if not k:
            return
        BE.kedvenc_torol(self.szulo._be, k)
        BE.ment(self.szulo._be)
        self._frissit(i)
        self.szulo._mond("Törölve a kedvencek közül: %s." % k)

    def _mutat(self):
        _i, k = self._kijelolt()
        if not k:
            return
        self.valasztott = k
        self.EndModal(wx.ID_OK)


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
                                        "nincs; Delete: törlés; + és -: "
                                        "darabszám):"), 0, wx.LEFT, 8)
        self.lista = wx.ListBox(self, style=wx.LB_SINGLE)
        self.lista.SetName("Bevásárlólista tételei")
        self.lista.Bind(wx.EVT_KEY_DOWN, self._billentyu)
        v.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)
        sor = wx.BoxSizer(wx.HORIZONTAL)
        for cimke, fv in (("&Megvan / még nincs (Szóköz)", self._pipa),
                          ("T&örlés (Delete)", self._torol),
                          ("&Darabszám… (Ctrl+D)", self._darab),
                          ("Ú&j tétel… (Ctrl+N)", self._uj),
                          ("Lista kiü&rítése… (Ctrl+Delete)", self._kiurit),
                          ("Összefésülés a tele&fonnal… (Ctrl+T)",
                           self._telefon),
                          ("Lista &kiküldése… (Ctrl+E)", self._kuldes),
                          ("&Bezárás", lambda: self.EndModal(wx.ID_OK))):
            b = wx.Button(self, label=cimke)
            b.Bind(wx.EVT_BUTTON, lambda e, f=fv: f())
            sor.Add(b, 0, wx.RIGHT, 6)
        v.Add(sor, 0, wx.ALL, 8)
        self.SetSizer(v)
        ids = {k: wx.NewIdRef() for k in ("uj", "tel", "kuld", "db", "urit")}
        self.Bind(wx.EVT_MENU, lambda e: self._uj(), id=ids["uj"])
        self.Bind(wx.EVT_MENU, lambda e: self._darab(), id=ids["db"])
        self.Bind(wx.EVT_MENU, lambda e: self._kiurit(), id=ids["urit"])
        self.Bind(wx.EVT_MENU, lambda e: self._telefon(), id=ids["tel"])
        self.Bind(wx.EVT_MENU, lambda e: self._kuldes(), id=ids["kuld"])
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord("N"), ids["uj"]),
            (wx.ACCEL_CTRL, ord("T"), ids["tel"]),
            (wx.ACCEL_CTRL, ord("E"), ids["kuld"]),
            (wx.ACCEL_CTRL, ord("D"), ids["db"]),
            (wx.ACCEL_CTRL, wx.WXK_DELETE, ids["urit"]),
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
            if e.ControlDown():
                self._kiurit()
            else:
                self._torol()
        elif k in (wx.WXK_ADD, wx.WXK_NUMPAD_ADD) or e.GetUnicodeKey() == ord("+"):
            self._darab_lep(1)
        elif k in (wx.WXK_SUBTRACT, wx.WXK_NUMPAD_SUBTRACT) \
                or e.GetUnicodeKey() == ord("-"):
            self._darab_lep(-1)
        else:
            e.Skip()

    def _darab_lep(self, mennyi):
        i, t = self._kijelolt()
        if not t:
            return
        uj = B.darab(t) + mennyi
        if uj < 1:
            self.szulo._mond("Egynél kevesebb nem lehet. Törölni a Delete-tel tudod.")
            return
        B.darab_allit(self.adat, t["id"], uj)
        B.ment(self.adat)
        self._frissit(i)
        self.szulo._mond("%d darab: %s." % (uj, t.get("name", "")))

    def _darab(self):
        i, t = self._kijelolt()
        if not t:
            return
        d = wx.TextEntryDialog(self, "Hány darab kell ebből? (%s)"
                               % t.get("name", ""), "Darabszám",
                               str(B.darab(t)))
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            ertek = d.GetValue().strip()
        finally:
            d.Destroy()
        try:
            db = int(ertek)
            if db < 1:
                raise ValueError
        except ValueError:
            self.szulo._mond("Egész számot írj, legalább egyet.")
            return
        B.darab_allit(self.adat, t["id"], db)
        B.ment(self.adat)
        self._frissit(i)
        self.szulo._mond("%d darab: %s." % (db, t.get("name", "")))

    def _kiurit(self):
        lst = B.tetelek(self.adat)
        if not lst:
            self.szulo._mond("A lista már üres.")
            return
        megvan = sum(1 for t in lst if t.get("checked"))
        valasztek = ["Az egész lista törlése (%d tétel)" % len(lst)]
        if megvan:
            valasztek.insert(0, "Csak a már megvan tételek törlése (%d)" % megvan)
        d = wx.SingleChoiceDialog(self, "Mit töröljek a bevásárlólistáról?",
                                  "Lista kiürítése", valasztek)
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            csak_megvan = megvan and d.GetSelection() == 0
        finally:
            d.Destroy()
        if not csak_megvan and wx.MessageBox(
                "Biztosan törlöd az egész listát? Ezt nem lehet visszavonni.",
                "Lista kiürítése", wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
            return
        n = B.kiurit(self.adat, csak_megvan=bool(csak_megvan))
        B.ment(self.adat)
        self._frissit()
        self.szulo._mond("%d tétel törölve. %s" % (
            n, "A listán %d tétel maradt." % len(B.tetelek(self.adat))
            if B.tetelek(self.adat) else "A lista üres."))

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
                    wx.TheClipboard.Flush()
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
