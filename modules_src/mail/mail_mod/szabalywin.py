# -*- coding: utf-8 -*-
"""Super Mail – a SZABÁLYOK felülete (vak-first).

A logika a `szabalyok.py`-ban van; itt csak az ablakok. Három belépő:
  • Szabályok kezelése        – lista, sorrend, be/ki, próba, futtatás
  • Szabály ebből a levélből  – a leggyorsabb út: a kijelölt levélből
  • Szabály szerkesztése      – feltételek és műveletek

VAK-FIRST DÖNTÉSEK
  • A szabálylista SOROK helyett MONDATOK: „ha a feladó tartalmazza: bolt.hu →
    áthelyezés ide: Hírlevelek”. Így a képernyőolvasó egy sorban elmond
    mindent, nem kell oszlopok közt tájékozódni.
  • A szóköz kapcsolja ki-be a szabályt, a Fel/Le gomb a sorrendet – a
    változást KI IS MONDJUK, mert a listaelem szövege ilyenkor átíródik.
  • A PRÓBA gomb megmondja, hány levélre illeszkedne, és felsorolja az elsőket
    – anélkül, hogy bármi megmozdulna.
"""

from __future__ import annotations

import wx

from . import autovalasz as AV
from . import szabalyok as SZ


def _mondd(main, szoveg):
    """Bemondás: ELŐBB a futó képernyőolvasó, aztán a program saját hangja."""
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


class _Alap(wx.Dialog):
    """Közös: felolvasott címke-hozzárendelés és bemondás."""

    def __init__(self, parent, main, cim, meret=(640, -1)):
        super().__init__(parent, title=cim, size=meret)
        self.main = main

    def _mond(self, szoveg):
        _mondd(self.main, szoveg)

    @staticmethod
    def _cimkezett(szulo, sizer, cimke, vezerlo, aranyos=0):
        st = wx.StaticText(szulo, label=cimke)
        vezerlo.SetName(cimke.replace("&", "").rstrip(":"))
        sizer.Add(st, 0, wx.LEFT | wx.TOP, 8)
        sizer.Add(vezerlo, aranyos, wx.EXPAND | wx.ALL, 8)
        return vezerlo


# ======================================================================
#  Egy feltétel szerkesztése
# ======================================================================
class FeltetelDialog(_Alap):
    MEZO_SORREND = [SZ.MEZO_FELADO, SZ.MEZO_CIMZETT, SZ.MEZO_TARGY,
                    SZ.MEZO_TORZS, SZ.MEZO_LISTA, SZ.MEZO_MARKETING,
                    SZ.MEZO_CSATOLMANY, SZ.MEZO_MERET, SZ.MEZO_FEJLEC]

    # melyik mezőhöz milyen viszony illik
    SZOVEGES = [SZ.VISZ_TARTALMAZZA, SZ.VISZ_NEM_TARTALMAZZA, SZ.VISZ_PONTOSAN,
                SZ.VISZ_KEZDODIK, SZ.VISZ_VEGZODIK]
    LOGIKAI = [SZ.VISZ_IGAZ, SZ.VISZ_HAMIS]
    SZAMOS = [SZ.VISZ_NAGYOBB]

    def __init__(self, parent, main, feltetel=None):
        super().__init__(parent, main, "Feltétel", (600, -1))
        f = feltetel or SZ.Feltetel()
        v = wx.BoxSizer(wx.VERTICAL)

        self.mezo = wx.Choice(self, choices=[SZ.MEZO_NEVEK[m]
                                             for m in self.MEZO_SORREND])
        self.mezo.SetSelection(self.MEZO_SORREND.index(f.mezo)
                               if f.mezo in self.MEZO_SORREND else 0)
        self.mezo.Bind(wx.EVT_CHOICE, lambda e: self._mezo_valt())
        self._cimkezett(self, v, "&Mit nézzünk:", self.mezo)

        self.viszony = wx.Choice(self, choices=[])
        self._cimkezett(self, v, "&Hogyan:", self.viszony)

        self.fejlec = wx.TextCtrl(self, value=f.fejlec_nev)
        self.fejlec_cimke = wx.StaticText(self, label="A &fejléc neve:")
        v.Add(self.fejlec_cimke, 0, wx.LEFT, 8)
        self.fejlec.SetName("A fejléc neve")
        v.Add(self.fejlec, 0, wx.EXPAND | wx.ALL, 8)

        self.ertek = wx.TextCtrl(self, value=f.ertek)
        self.ertek_cimke = wx.StaticText(self, label="&Érték:")
        v.Add(self.ertek_cimke, 0, wx.LEFT, 8)
        self.ertek.SetName("Érték")
        v.Add(self.ertek, 0, wx.EXPAND | wx.ALL, 8)

        gs = wx.BoxSizer(wx.HORIZONTAL)
        ok = wx.Button(self, wx.ID_OK, "&Rendben")
        ok.SetDefault()
        gs.Add(ok, 0, wx.RIGHT, 8)
        gs.Add(wx.Button(self, wx.ID_CANCEL, "&Mégsem"), 0)
        v.Add(gs, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        self.SetSizerAndFit(v)
        self.CentreOnParent()
        self._mezo_valt(f.viszony)
        self.mezo.SetFocus()

    def _viszonyok(self, mezo):
        if mezo in (SZ.MEZO_MARKETING, SZ.MEZO_CSATOLMANY, SZ.MEZO_LISTA):
            return self.LOGIKAI + (self.SZOVEGES if mezo == SZ.MEZO_LISTA
                                   else [])
        if mezo == SZ.MEZO_MERET:
            return self.SZAMOS
        return self.SZOVEGES

    def _mezo_valt(self, megtart=""):
        mezo = self.MEZO_SORREND[max(0, self.mezo.GetSelection())]
        lehet = self._viszonyok(mezo)
        self.viszony.Set([SZ.VISZONY_NEVEK[v] for v in lehet])
        self.viszony.SetSelection(lehet.index(megtart) if megtart in lehet else 0)
        self._lehet = lehet
        # ami nem kell, azt ELREJTJÜK (nem tiltjuk): így a tabulátor-sorrendben
        # sincs útban egy használhatatlan mező
        fejlec_kell = mezo == SZ.MEZO_FEJLEC
        self.fejlec.Show(fejlec_kell)
        self.fejlec_cimke.Show(fejlec_kell)
        ertek_kell = self._lehet[max(0, self.viszony.GetSelection())] not in (
            SZ.VISZ_IGAZ, SZ.VISZ_HAMIS)
        self.ertek.Show(ertek_kell)
        self.ertek_cimke.Show(ertek_kell)
        self.viszony.Bind(wx.EVT_CHOICE, lambda e: self._viszony_valt())
        self.Layout()
        self.Fit()

    def _viszony_valt(self):
        kell = self._lehet[max(0, self.viszony.GetSelection())] not in (
            SZ.VISZ_IGAZ, SZ.VISZ_HAMIS)
        self.ertek.Show(kell)
        self.ertek_cimke.Show(kell)
        self.Layout()
        self.Fit()

    def eredmeny(self) -> SZ.Feltetel:
        mezo = self.MEZO_SORREND[max(0, self.mezo.GetSelection())]
        return SZ.Feltetel(
            mezo=mezo,
            viszony=self._lehet[max(0, self.viszony.GetSelection())],
            ertek=self.ertek.GetValue().strip(),
            fejlec_nev=self.fejlec.GetValue().strip())


# ======================================================================
#  Egy szabály szerkesztése
# ======================================================================
class SzabalyDialog(_Alap):
    def __init__(self, parent, main, szabaly=None, mappak=(), fiokok=(),
                 proba=None):
        super().__init__(parent, main, "Szabály", (700, -1))
        self._sz = SZ.szabaly_be(SZ.szabaly_ki(szabaly)) if szabaly \
            else SZ.Szabaly()
        self._proba = proba
        v = wx.BoxSizer(wx.VERTICAL)

        self.nev = wx.TextCtrl(self, value=self._sz.nev)
        self._cimkezett(self, v, "A szabály &neve:", self.nev)

        self.mind = wx.Choice(self, choices=[
            "MINDEN feltétel teljesüljön", "BÁRMELYIK feltétel elég"])
        self.mind.SetSelection(0 if self._sz.mind else 1)
        self._cimkezett(self, v, "&Mikor fusson:", self.mind)

        v.Add(wx.StaticText(self, label="&Feltételek (fel/le nyíl):"), 0,
              wx.LEFT | wx.TOP, 8)
        self.felt_lista = wx.ListBox(self, style=wx.LB_SINGLE)
        self.felt_lista.SetName("Feltételek")
        v.Add(self.felt_lista, 1, wx.EXPAND | wx.ALL, 8)
        fs = wx.BoxSizer(wx.HORIZONTAL)
        for cimke, kez in (("Ú&j feltétel", self._felt_uj),
                           ("&Szerkesztés", self._felt_szerk),
                           ("&Törlés", self._felt_torol)):
            b = wx.Button(self, label=cimke)
            b.Bind(wx.EVT_BUTTON, kez)
            fs.Add(b, 0, wx.RIGHT, 6)
        v.Add(fs, 0, wx.LEFT | wx.BOTTOM, 8)

        # --- MŰVELETEK: LISTA, nem pipa-oszlop (MK3, 2026-09-05) ---
        # Miért lista: nyolc pipánál még elfért egy oszlopban, tizenháromnál
        # már nem – főleg felolvasva, ahol minden pipa egy külön nyíl-lépés,
        # akkor is, ha nem érdekel. A lista végignyilazható, és minden sor EGY
        # MONDAT: „áthelyezés ide: Számlák”, „emlékeztess rá holnap ilyenkor”.
        self._mappak = list(mappak)
        v.Add(wx.StaticText(self, label="Mi történjen – mű&veletek "
                                        "(fel/le nyíl):"), 0, wx.LEFT | wx.TOP, 8)
        self.muv_lista = wx.ListBox(self, style=wx.LB_SINGLE)
        self.muv_lista.SetName("Műveletek")
        v.Add(self.muv_lista, 1, wx.EXPAND | wx.ALL, 8)
        ms = wx.BoxSizer(wx.HORIZONTAL)
        for cimke, kez in (("Ú&j művelet", self._muv_uj),
                           ("Művelet sze&rkesztése", self._muv_szerk),
                           ("Művelet tör&lése", self._muv_torol)):
            b = wx.Button(self, label=cimke)
            b.Bind(wx.EVT_BUTTON, kez)
            ms.Add(b, 0, wx.RIGHT, 6)
        v.Add(ms, 0, wx.LEFT | wx.BOTTOM, 8)

        cimek = ["minden fiókra"] + [f.get("email", "") for f in fiokok]
        self.fiok = wx.Choice(self, choices=cimek)
        self.fiok.SetSelection(cimek.index(self._sz.fiok)
                               if self._sz.fiok in cimek else 0)
        self._cimkezett(self, v, "Melyik fiók&ra vonatkozzon:", self.fiok)

        gs = wx.BoxSizer(wx.HORIZONTAL)
        pb = wx.Button(self, label="&Próba (nem mozdít semmit)")
        pb.Bind(wx.EVT_BUTTON, lambda e: self._proba_gomb())
        gs.Add(pb, 0, wx.RIGHT, 8)
        ok = wx.Button(self, wx.ID_OK, "&Mentés")
        ok.SetDefault()
        gs.Add(ok, 0, wx.RIGHT, 8)
        gs.Add(wx.Button(self, wx.ID_CANCEL, "Még&sem"), 0)
        v.Add(gs, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        self.SetSizerAndFit(v)
        self.CentreOnParent()
        self._felt_frissit()
        self._muv_frissit()
        self.nev.SetFocus()

    # ---- feltételek
    def _felt_frissit(self, kijelol=-1):
        self.felt_lista.Set([f.leiras() for f in self._sz.feltetelek])
        if self._sz.feltetelek:
            self.felt_lista.SetSelection(
                min(max(0, kijelol), len(self._sz.feltetelek) - 1))

    def _felt_uj(self, e):
        d = FeltetelDialog(self, self.main)
        if d.ShowModal() == wx.ID_OK:
            self._sz.feltetelek.append(d.eredmeny())
            self._felt_frissit(len(self._sz.feltetelek) - 1)
            self._mond("Feltétel hozzáadva: "
                       + self._sz.feltetelek[-1].leiras())
        d.Destroy()

    def _felt_szerk(self, e):
        i = self.felt_lista.GetSelection()
        if i < 0:
            self._mond("Előbb válassz egy feltételt.")
            return
        d = FeltetelDialog(self, self.main, self._sz.feltetelek[i])
        if d.ShowModal() == wx.ID_OK:
            self._sz.feltetelek[i] = d.eredmeny()
            self._felt_frissit(i)
        d.Destroy()

    def _felt_torol(self, e):
        i = self.felt_lista.GetSelection()
        if i < 0:
            self._mond("Előbb válassz egy feltételt.")
            return
        del self._sz.feltetelek[i]
        self._felt_frissit(i - 1)
        self._mond("Feltétel törölve.")

    # ---- műveletek (MK3)
    def _muv_kulcsok(self) -> list:
        """A műveletek a FELKÍNÁLT sorrendben – hogy a lista sorrendje stabil
        legyen, ne a szótár beszúrási sorrendjétől függjön."""
        m = self._sz.muveletek or {}
        return [k for k in SZ.VALASZTHATO_MUVELETEK if k in m]

    def _muv_frissit(self, kijelol=-1):
        kulcsok = self._muv_kulcsok()
        self.muv_lista.Set([SZ.muvelet_leiras(k, self._sz.muveletek[k])
                            for k in kulcsok])
        if kulcsok:
            self.muv_lista.SetSelection(min(max(0, kijelol), len(kulcsok) - 1))

    def _muv_uj(self, e):
        d = MuveletDialog(self, self.main, self._mappak)
        if d.ShowModal() == wx.ID_OK:
            kulcs, ertek, targy = d.eredmeny()
            if kulcs:
                self._sz.muveletek[kulcs] = ertek
                if kulcs == SZ.MUV_AUTOVALASZ:
                    if targy:
                        self._sz.muveletek[SZ.MUV_AUTOVALASZ_TARGY] = targy
                    else:
                        self._sz.muveletek.pop(SZ.MUV_AUTOVALASZ_TARGY, None)
                kulcsok = self._muv_kulcsok()
                self._muv_frissit(kulcsok.index(kulcs))
                self._mond("Művelet hozzáadva: "
                           + SZ.muvelet_leiras(kulcs, ertek))
        d.Destroy()

    def _muv_szerk(self, e):
        kulcsok = self._muv_kulcsok()
        i = self.muv_lista.GetSelection()
        if not (0 <= i < len(kulcsok)):
            self._mond("Előbb válassz egy műveletet.")
            return
        kulcs = kulcsok[i]
        d = MuveletDialog(self, self.main, self._mappak, kulcs,
                          self._sz.muveletek.get(kulcs),
                          self._sz.muveletek.get(SZ.MUV_AUTOVALASZ_TARGY, ""))
        if d.ShowModal() == wx.ID_OK:
            uj_kulcs, ertek, targy = d.eredmeny()
            if uj_kulcs:
                if uj_kulcs != kulcs:
                    self._sz.muveletek.pop(kulcs, None)
                self._sz.muveletek[uj_kulcs] = ertek
                if uj_kulcs == SZ.MUV_AUTOVALASZ:
                    if targy:
                        self._sz.muveletek[SZ.MUV_AUTOVALASZ_TARGY] = targy
                    else:
                        self._sz.muveletek.pop(SZ.MUV_AUTOVALASZ_TARGY, None)
                self._muv_frissit(i)
        d.Destroy()

    def _muv_torol(self, e):
        kulcsok = self._muv_kulcsok()
        i = self.muv_lista.GetSelection()
        if not (0 <= i < len(kulcsok)):
            self._mond("Előbb válassz egy műveletet.")
            return
        kulcs = kulcsok[i]
        self._sz.muveletek.pop(kulcs, None)
        if kulcs == SZ.MUV_AUTOVALASZ:
            self._sz.muveletek.pop(SZ.MUV_AUTOVALASZ_TARGY, None)
        self._muv_frissit(i - 1)
        self._mond("Művelet törölve.")

    def _proba_gomb(self):
        if self._proba is None:
            self._mond("A próba csak a főablakból érhető el.")
            return
        self._proba(self.eredmeny())

    # ---- eredmény
    def eredmeny(self) -> SZ.Szabaly:
        # A műveletek MÁR a szabályban vannak (a Műveletek listája közvetlenül
        # azt szerkeszti) – itt csak a szabály többi mezője kerül a helyére.
        self._sz.nev = self.nev.GetValue().strip()
        self._sz.mind = self.mind.GetSelection() == 0
        i = self.fiok.GetSelection()
        self._sz.fiok = "" if i <= 0 else self.fiok.GetString(i)
        return self._sz

    def hianyzo_autovalasz(self) -> bool:
        """A művelet-lista nem enged üres automata választ létrehozni, tehát
        itt már nincs mit ellenőrizni. (A hívó ezt a nevet mindkét
        párbeszédnél hívja, ezért marad meg.)"""
        return False

    def utkozes(self) -> str:
        """Egymásnak ellentmondó műveletek – a mentés előtt kérdezünk rá."""
        return SZ.utkozes(self._sz.muveletek)


# ======================================================================
#  EGY művelet szerkesztése  (MK3, 2026-09-05)
# ======================================================================
class MuveletDialog(_Alap):
    """Egy művelet felvétele vagy módosítása.

    VAK-FIRST DÖNTÉS: a párbeszédben MINDIG csak annyi mező van, amennyi az
    éppen választott művelethez kell. Nem raktunk ki egyszerre egy mappa-,
    egy cím-, egy idő- és egy szövegmezőt azzal, hogy „a többit hagyd
    üresen” – felolvasva minden fölösleges mező egy külön nyíl-lépés és egy
    „ezt is ki kell tölteni?” bizonytalanság.

    Ezért a felső legördülőből választasz műveletet, és ALATTA pontosan az az
    egy mező jelenik meg, ami hozzá tartozik; a többi eltűnik. A művelet
    váltásakor a program KI IS MONDJA, mit kell megadni."""

    def __init__(self, parent, main, mappak=(), kulcs=None, ertek=None,
                 autovalasz_targy=""):
        super().__init__(parent, main, "Művelet", (620, -1))
        self._kulcsok = list(SZ.VALASZTHATO_MUVELETEK)
        v = wx.BoxSizer(wx.VERTICAL)

        self.tipus = wx.Choice(
            self, choices=[SZ.MUVELET_NEVEK.get(k, k) for k in self._kulcsok])
        self.tipus.SetSelection(self._kulcsok.index(kulcs)
                                if kulcs in self._kulcsok else 0)
        self._cimkezett(self, v, "&Melyik művelet:", self.tipus)
        self.tipus.Bind(wx.EVT_CHOICE, lambda e: self._tipus_valt())

        # --- MAPPA (áthelyezés / másolás)
        self.mappa_cimke = wx.StaticText(self, label=(
            "&Melyik mappába (új nevet is beírhatsz, a program létrehozza):"))
        v.Add(self.mappa_cimke, 0, wx.LEFT | wx.TOP, 8)
        self.mappa = wx.ComboBox(self, choices=list(mappak))
        self.mappa.SetName("A cél mappa neve")
        v.Add(self.mappa, 0, wx.EXPAND | wx.ALL, 8)

        # --- IDŐ (emlékeztető)
        self.ido_cimke = wx.StaticText(self, label="Mikor &szóljon:")
        v.Add(self.ido_cimke, 0, wx.LEFT | wx.TOP, 8)
        self.ido = wx.Choice(self,
                             choices=[c for _mp, c in SZ.EMLEKEZTETO_IDOK])
        self.ido.SetSelection(2)                 # „holnap ilyenkor”
        self.ido.SetName("Mennyi idő múlva emlékeztessen")
        v.Add(self.ido, 0, wx.EXPAND | wx.ALL, 8)

        # --- EGYSOROS szöveg (továbbítás címe / bemondás szövege)
        self.sor_cimke = wx.StaticText(self, label="&Érték:")
        v.Add(self.sor_cimke, 0, wx.LEFT | wx.TOP, 8)
        self.sor = wx.TextCtrl(self)
        v.Add(self.sor, 0, wx.EXPAND | wx.ALL, 8)

        # --- AUTOMATA VÁLASZ: tárgy + többsoros szöveg
        self.targy_cimke = wx.StaticText(self, label=(
            "Az automata válasz &tárgya (üresen: „Re:” és az eredeti levél "
            "tárgya):"))
        v.Add(self.targy_cimke, 0, wx.LEFT | wx.TOP, 8)
        self.targy = wx.TextCtrl(self, value=str(autovalasz_targy or ""))
        self.targy.SetName("Az automata válasz tárgya")
        v.Add(self.targy, 0, wx.EXPAND | wx.ALL, 8)
        self.level_cimke = wx.StaticText(self, label=(
            "Az automata &válasz szövege. Beírhatod ezeket, és a program "
            "kitölti: " + ", ".join(h for h, _m in AV.HELYEK) + "."))
        v.Add(self.level_cimke, 0, wx.LEFT | wx.TOP, 8)
        self.level = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(-1, 120))
        self.level.SetName("Az automata válasz szövege. Helykitöltők: "
                           + "; ".join("%s = %s" % (h, m)
                                       for h, m in AV.HELYEK))
        v.Add(self.level, 0, wx.EXPAND | wx.ALL, 8)

        # a meglévő érték visszatöltése a megfelelő mezőbe
        if kulcs and ertek is not None:
            fajta = SZ.MUVELET_ERTEK.get(kulcs, "")
            if fajta == "mappa":
                self.mappa.SetValue(str(ertek))
            elif fajta == "ido":
                for j, (mp, _c) in enumerate(SZ.EMLEKEZTETO_IDOK):
                    if mp == ertek:
                        self.ido.SetSelection(j)
                        break
            elif fajta in ("cim", "szoveg"):
                self.sor.SetValue(str(ertek))
            elif fajta == "level":
                self.level.SetValue(str(ertek))

        gs = wx.BoxSizer(wx.HORIZONTAL)
        ok = wx.Button(self, wx.ID_OK, "&Rendben")
        ok.SetDefault()
        gs.Add(ok, 0, wx.RIGHT, 8)
        gs.Add(wx.Button(self, wx.ID_CANCEL, "Még&sem"), 0)
        v.Add(gs, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        self.SetSizer(v)
        self._tipus_valt(elso=True)
        self.CentreOnParent()
        self.tipus.SetFocus()

    # ---- csak a szükséges mező látszik
    def _mezok(self, fajta: str):
        return {
            "mappa": [self.mappa_cimke, self.mappa],
            "ido": [self.ido_cimke, self.ido],
            "cim": [self.sor_cimke, self.sor],
            "szoveg": [self.sor_cimke, self.sor],
            "level": [self.targy_cimke, self.targy,
                      self.level_cimke, self.level],
        }.get(fajta, [])

    def _tipus_valt(self, elso=False):
        kulcs = self._kulcsok[max(0, self.tipus.GetSelection())]
        fajta = SZ.MUVELET_ERTEK.get(kulcs, "")
        mind = (self._mezok("mappa") + self._mezok("ido") + self._mezok("cim")
                + self._mezok("level"))
        for w in mind:
            w.Hide()
        for w in self._mezok(fajta):
            w.Show()
        if fajta == "cim":
            self.sor_cimke.SetLabel("A &cím, ahova továbbítsa:")
            self.sor.SetName("Az e-mail cím, ahova a levél továbbmegy")
        elif fajta == "szoveg":
            self.sor_cimke.SetLabel("Amit érkezéskor &mondjon ki:")
            self.sor.SetName("A mondat, ami az ilyen levél érkezésekor "
                             "elhangzik")
        self.Layout()
        self.Fit()
        if not elso:
            self._mond(SZ.MUVELET_NEVEK.get(kulcs, kulcs)
                       + (". Add meg az értékét lejjebb." if fajta
                          else ". Ehhez nem kell semmit megadni."))

    # ---- eredmény
    def eredmeny(self):
        """(kulcs, ertek, automata-válasz-tárgy). Üres kulcs = nincs mit
        felvenni (például az automata válasz szövege üresen maradt)."""
        kulcs = self._kulcsok[max(0, self.tipus.GetSelection())]
        fajta = SZ.MUVELET_ERTEK.get(kulcs, "")
        if not fajta:
            return kulcs, True, ""
        if fajta == "mappa":
            ertek = self.mappa.GetValue().strip()
        elif fajta == "ido":
            ertek = SZ.EMLEKEZTETO_IDOK[max(0, self.ido.GetSelection())][0]
        elif fajta == "level":
            ertek = self.level.GetValue().strip()
        else:
            ertek = self.sor.GetValue().strip()
        if not ertek:
            # ÜRESEN nem vesszük fel: egy érték nélküli művelet némán nem
            # csinálna semmit, és a felhasználó azt hinné, be van állítva.
            self._mond("Ehhez a művelethez meg kell adni egy értéket – "
                       "üresen nem veszem fel.")
            return "", None, ""
        return kulcs, ertek, self.targy.GetValue().strip()


# ======================================================================
#  Szabály EBBŐL a levélből – a leggyorsabb út
# ======================================================================
class SzabalyLevelbolDialog(_Alap):
    def __init__(self, parent, main, info, mappak=()):
        super().__init__(parent, main, "Szabály ebből a levélből", (640, -1))
        self._info = info
        v = wx.BoxSizer(wx.VERTICAL)

        self._tipusok = [("felado", "Minden levél ettől a feladótól: %s"
                          % SZ.cim_resz(info.get("felado", "")))]
        dom = SZ.domain_resz(info.get("felado", ""))
        if dom:
            self._tipusok.append(("domain", "Minden levél innen: @%s" % dom))
        if (info.get("lista_id") or "").strip():
            self._tipusok.append(
                ("lista", "Minden levél erről a levelezőlistáról: %s"
                 % info.get("lista_id")))
        if info.get("marketing"):
            self._tipusok.append(
                ("marketing", "Minden hírlevél és reklám (nem csak ez a feladó)"))
        self._tipusok.append(("targy", "Ilyen tárgyú levelek: %s"
                              % info.get("targy", "")))

        self.valaszto = wx.RadioBox(
            self, label="Mire vonatkozzon a szabály?",
            choices=[sz for _, sz in self._tipusok],
            majorDimension=1, style=wx.RA_SPECIFY_COLS)
        self.valaszto.SetName("Mire vonatkozzon a szabály")
        v.Add(self.valaszto, 0, wx.EXPAND | wx.ALL, 10)

        self.cel = wx.ComboBox(self, choices=list(mappak))
        self._cimkezett(
            self, v, "&Melyik mappába kerüljön (új nevet is beírhatsz, a "
                     "program létrehozza):", self.cel)

        self.olvasott = wx.CheckBox(self, label="Egyben &olvasottnak is jelöli")
        v.Add(self.olvasott, 0, wx.LEFT, 10)
        self.nincs_hang = wx.CheckBox(
            self, label="&Ne szóljon rájuk értesítő hang")
        v.Add(self.nincs_hang, 0, wx.LEFT, 10)

        # --- AUTOMATA VÁLASZ a GYORS úton is (MK2) ---
        # Ez a párbeszéd a leggyakoribb út: rááll a levélre, Ctrl+Shift+R, kész.
        # Ha az automata válasz csak a teljes szerkesztőben volna meg, a
        # funkció gyakorlatilag elérhetetlen maradna. [Dávid jelezte, 2026-09-05]
        self.autov_be = wx.CheckBox(
            self, label="A&utomata válasz küldése ezeknek a leveleknek")
        self.autov_be.SetName(
            "Automata válasz: akire ez a szabály illik, az kap egy általad "
            "megírt választ. Címenként naponta EGYSZER megy el, és soha nem "
            "megy levelezőlistára, hírlevélre, no-reply címre vagy automata "
            "üzenetre. A tárgy „Re:” és az eredeti levél tárgya lesz.")
        v.Add(self.autov_be, 0, wx.LEFT | wx.TOP, 10)

        v.Add(wx.StaticText(self, label=(
            "Az automata &válasz szövege (csak akkor kell, ha a fenti pipa be "
            "van kapcsolva). Beírhatod ezeket, és a program kitölti: "
            + ", ".join(h for h, _m in AV.HELYEK) + ".")), 0, wx.LEFT, 10)
        self.autov_szoveg = wx.TextCtrl(self, style=wx.TE_MULTILINE,
                                        size=(-1, 90))
        self.autov_szoveg.SetName(
            "Az automata válasz szövege. Helykitöltők: "
            + "; ".join("%s = %s" % (h, m) for h, m in AV.HELYEK))
        v.Add(self.autov_szoveg, 0,
              wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        gs = wx.BoxSizer(wx.HORIZONTAL)
        ok = wx.Button(self, wx.ID_OK, "&Létrehozás")
        ok.SetDefault()
        gs.Add(ok, 0, wx.RIGHT, 8)
        gs.Add(wx.Button(self, wx.ID_CANCEL, "&Mégsem"), 0)
        v.Add(gs, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        self.SetSizerAndFit(v)
        self.CentreOnParent()
        self.valaszto.SetFocus()
        wx.CallAfter(self._mond,
                     "Szabály ebből a levélből. Válaszd ki, mire vonatkozzon, "
                     "majd add meg a mappát. Lejjebb automata választ is "
                     "beállíthatsz ezekre a levelekre.")

    def eredmeny(self) -> SZ.Szabaly:
        tipus = self._tipusok[self.valaszto.GetSelection()][0]
        sz = SZ.szabaly_levelbol(self._info, tipus, self.cel.GetValue().strip())
        if self.olvasott.GetValue():
            sz.muveletek[SZ.MUV_OLVASOTT] = True
        if self.nincs_hang.GetValue():
            sz.muveletek[SZ.MUV_NINCS_HANG] = True
        if self.autov_be.GetValue():
            szoveg = self.autov_szoveg.GetValue().strip()
            if szoveg:
                sz.muveletek[SZ.MUV_AUTOVALASZ] = szoveg
        return sz

    def hianyzo_autovalasz(self) -> bool:
        """Pipa van, szöveg nincs – a hívó ilyenkor rákérdez."""
        return bool(self.autov_be.GetValue()
                    and not self.autov_szoveg.GetValue().strip())


# ======================================================================
#  A szabályok kezelése
# ======================================================================
class SzabalyokDialog(_Alap):
    def __init__(self, parent, main, szabalyok, mappak=(), fiokok=(),
                 proba=None, futtat=None):
        super().__init__(parent, main, "Szabályok", (760, 520))
        self.szabalyok = [SZ.szabaly_be(SZ.szabaly_ki(sz)) for sz in szabalyok]
        self._mappak = list(mappak)
        self._fiokok = list(fiokok)
        self._proba = proba
        self._futtat = futtat

        v = wx.BoxSizer(wx.VERTICAL)
        sug = wx.StaticText(self, label=(
            "A szabályok fentről lefelé futnak le minden új levélre. "
            "A szóköz ki- és bekapcsolja a kijelölt szabályt."))
        sug.Wrap(720)
        v.Add(sug, 0, wx.ALL, 10)

        self.lista = wx.ListBox(self, style=wx.LB_SINGLE)
        self.lista.SetName("Szabályok")
        self.lista.Bind(wx.EVT_CHAR_HOOK, self._billentyu)
        v.Add(self.lista, 1, wx.EXPAND | wx.ALL, 10)

        s1 = wx.BoxSizer(wx.HORIZONTAL)
        for cimke, kez in (("Ú&j szabály", self._uj),
                           ("&Szerkesztés", self._szerk),
                           ("&Törlés", self._torol),
                           ("&Fel", lambda e: self._mozgat(-1)),
                           ("&Le", lambda e: self._mozgat(1))):
            b = wx.Button(self, label=cimke)
            b.Bind(wx.EVT_BUTTON, kez)
            s1.Add(b, 0, wx.RIGHT, 6)
        v.Add(s1, 0, wx.LEFT | wx.BOTTOM, 10)

        s2 = wx.BoxSizer(wx.HORIZONTAL)
        b = wx.Button(self, label="&Ki/be kapcsolás  (szóköz)")
        b.Bind(wx.EVT_BUTTON, lambda e: self._kapcsol())
        s2.Add(b, 0, wx.RIGHT, 6)
        b = wx.Button(self, label="&Próba a mostani listán")
        b.Bind(wx.EVT_BUTTON, lambda e: self._proba_gomb())
        s2.Add(b, 0, wx.RIGHT, 6)
        b = wx.Button(self, label="Futtatás mos&t")
        b.Bind(wx.EVT_BUTTON, lambda e: self._futtat_gomb())
        s2.Add(b, 0, wx.RIGHT, 6)
        ok = wx.Button(self, wx.ID_OK, "&Mentés és bezárás")
        ok.SetDefault()
        s2.Add(ok, 0, wx.RIGHT, 6)
        s2.Add(wx.Button(self, wx.ID_CANCEL, "&Mégsem"), 0)
        v.Add(s2, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        self.SetSizer(v)
        self.CentreOnParent()
        self._frissit()
        self.lista.SetFocus()

    # ---- lista
    def _frissit(self, kijelol=-1):
        self.lista.Set([sz.leiras() for sz in self.szabalyok])
        if self.szabalyok:
            self.lista.SetSelection(
                min(max(0, kijelol), len(self.szabalyok) - 1))

    def _valasztott(self):
        i = self.lista.GetSelection()
        return i if 0 <= i < len(self.szabalyok) else -1

    def _billentyu(self, e):
        if e.GetKeyCode() == wx.WXK_SPACE:
            self._kapcsol()
            return
        e.Skip()

    def _kapcsol(self):
        i = self._valasztott()
        if i < 0:
            self._mond("Nincs kijelölt szabály.")
            return
        self.szabalyok[i].be = not self.szabalyok[i].be
        self._frissit(i)
        self._mond("Bekapcsolva." if self.szabalyok[i].be else "Kikapcsolva.")

    def _autovalasz_ellenoriz(self, d) -> bool:
        """Ha az automata válasz be van pipálva, de nincs szövege, rákérdezünk.

        Enélkül a szabály némán MENTŐDNE automata válasz nélkül, a felhasználó
        meg azt hinné, be van kapcsolva – és napokig keresné, miért nem megy."""
        if d.hianyzo_autovalasz():
            uzenet = ("Bepipáltad az automata választ, de nem írtál hozzá "
                      "szöveget – így nem menne el semmi. Visszamész megírni?")
            self._mond(uzenet)
            if wx.MessageBox(uzenet, "Automata válasz",
                             wx.YES_NO | wx.ICON_WARNING, self) == wx.YES:
                return False
        # ÜTKÖZŐ MŰVELETEK: eddig némán az egyik győzött, és a felhasználó nem
        # tudta, miért nem oda került a levele, ahova várta. [MK3]
        try:
            baj = d.utkozes()
        except Exception:
            baj = ""
        if baj:
            uzenet = ("Figyelem: %s. Visszamész átnézni a műveleteket?" % baj)
            self._mond(uzenet)
            if wx.MessageBox(uzenet, "Ütköző műveletek",
                             wx.YES_NO | wx.ICON_WARNING, self) == wx.YES:
                return False
        return True

    def _uj(self, e):
        d = SzabalyDialog(self, self.main, None, self._mappak, self._fiokok,
                          self._proba)
        if d.ShowModal() == wx.ID_OK and self._autovalasz_ellenoriz(d):
            sz = d.eredmeny()
            if not sz.feltetelek:
                self._mond("Feltétel nélküli szabályt nem hozok létre – az "
                           "minden levélre illene.")
            else:
                self.szabalyok.append(sz)
                self._frissit(len(self.szabalyok) - 1)
                self._mond("Szabály létrehozva: " + sz.leiras())
        d.Destroy()

    def _szerk(self, e):
        i = self._valasztott()
        if i < 0:
            self._mond("Nincs kijelölt szabály.")
            return
        d = SzabalyDialog(self, self.main, self.szabalyok[i], self._mappak,
                          self._fiokok, self._proba)
        if d.ShowModal() == wx.ID_OK and self._autovalasz_ellenoriz(d):
            self.szabalyok[i] = d.eredmeny()
            self._frissit(i)
        d.Destroy()

    def _torol(self, e):
        i = self._valasztott()
        if i < 0:
            self._mond("Nincs kijelölt szabály.")
            return
        if wx.MessageBox("Törlöd ezt a szabályt?\n\n" + self.szabalyok[i].leiras(),
                         "Szabály törlése", wx.YES_NO | wx.ICON_QUESTION,
                         self) != wx.YES:
            return
        del self.szabalyok[i]
        self._frissit(i - 1)
        self._mond("Szabály törölve.")

    def _mozgat(self, irany):
        i = self._valasztott()
        if i < 0:
            return
        uj = i + irany
        if not 0 <= uj < len(self.szabalyok):
            self._mond("Ez a szabály már a lista szélén van.")
            return
        self.szabalyok[i], self.szabalyok[uj] = (self.szabalyok[uj],
                                                 self.szabalyok[i])
        self._frissit(uj)
        self._mond("%d. hely." % (uj + 1))

    def _proba_gomb(self):
        i = self._valasztott()
        if i < 0 or self._proba is None:
            self._mond("Nincs kijelölt szabály.")
            return
        self._proba(self.szabalyok[i])

    def _futtat_gomb(self):
        if self._futtat is None:
            return
        self._futtat(list(self.szabalyok))
