# -*- coding: utf-8 -*-
"""TV műsor – az akadálymentes ablak (felolvasott tévéújság).

Lapfülek: „Mi megy most?", „Ma este", „Csatornák" (csatorna → napirend),
„Keresés" (pl. „mikor megy a Reszkessetek betörők?") és „Beállítás" (a
műsorújság forrásának címe). Minden lista navigálható (fel/le nyíl), a
képernyőolvasó minden sort felolvas, a részletek külön mezőben olvashatók.

A műsoradat a felhasználó által választott (alapból közösségi, ingyenes) XMLTV
forrásból jön – IPTV-előfizetés NEM kell hozzá.
"""
import datetime as _dt
import threading

import wx

from . import epgmotor as EM


def _biztos_attr(obj, nev):
    """getattr, ami property-hibán sem szakad meg (None-t ad)."""
    try:
        return getattr(obj, nev, None)
    except Exception:
        return None


def _hatterben(munka, kesz, hiba=None):
    """Egy hosszú műveletet háttérszálon futtat, az eredményt a fő szálra adja."""
    def fut():
        try:
            eredmeny = munka()
        except Exception as ex:
            if hiba:
                wx.CallAfter(hiba, ex)
            return
        wx.CallAfter(kesz, eredmeny)
    threading.Thread(target=fut, daemon=True).start()


class TvMusorFrame(wx.Frame):
    def __init__(self, parent, core):
        super().__init__(parent, title="TV műsor", size=(820, 600))
        self.core = core
        self._closing = False
        self._naptar_hiba = ""        # miért nem sikerült az utolsó emlékeztető
        self._tv = EM.TvMusor()
        self._csatornak = []          # (cid, nev) az aktuális listában
        self._talalatok = []          # (nev, Musor) a keresésben
        self._naprend = []            # a kiválasztott csatorna műsorai
        self._build()
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        wx.CallAfter(self._betolt)

    # ------------------------------------------------------------ felület
    def _build(self):
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        self._allapot = wx.TextCtrl(p, style=wx.TE_READONLY)
        self._allapot.SetName("Állapot")
        v.Add(self._allapot, 0, wx.EXPAND | wx.ALL, 8)

        nb = wx.Notebook(p)
        nb.AddPage(self._most_lap(nb), "Mi megy most?")
        nb.AddPage(self._este_lap(nb), "Ma este")
        nb.AddPage(self._csatorna_lap(nb), "Csatornák")
        nb.AddPage(self._keres_lap(nb), "Keresés")
        nb.AddPage(self._kedvenc_lap(nb), "Kedvencek")
        nb.AddPage(self._beall_lap(nb), "Beállítás")
        self._nb = nb
        v.Add(nb, 1, wx.EXPAND | wx.ALL, 6)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        g_friss = wx.Button(p, label="&Frissítés (letöltés újra)")
        g_friss.Bind(wx.EVT_BUTTON, lambda e: self._betolt(eroltetett=True))
        sor.Add(g_friss, 0, wx.RIGHT, 6)
        g_zar = wx.Button(p, label="Be&zárás")
        g_zar.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        sor.Add(g_zar, 0)
        v.Add(sor, 0, wx.ALL, 8)

        p.SetSizer(v)
        self._panel = p

    def _lista_lap(self, nb, cimke, nev, reszlet_nev):
        """Közös lap-váz: címke + navigálható lista + részletek mező."""
        lap = wx.Panel(nb)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(lap, label=cimke), 0, wx.ALL, 6)
        lista = wx.ListBox(lap, style=wx.LB_SINGLE)
        lista.SetName(nev)
        s.Add(lista, 1, wx.EXPAND | wx.ALL, 6)
        reszlet = wx.TextCtrl(
            lap, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 90))
        reszlet.SetName(reszlet_nev)
        s.Add(reszlet, 0, wx.EXPAND | wx.ALL, 6)
        lap.SetSizer(s)
        return lap, lista, reszlet

    def _most_lap(self, nb):
        lap, self._most_lista, self._most_reszlet = self._lista_lap(
            nb, "&Épp most futó műsorok minden csatornán (fel/le nyíl):",
            "Most futó műsorok", "A kijelölt műsor részletei")
        self._most_lista.Bind(
            wx.EVT_LISTBOX,
            lambda e: self._reszlet_mutat(self._most_sorok, self._most_lista,
                                          self._most_reszlet))
        self._most_sorok = []
        return lap

    def _este_lap(self, nb):
        lap, self._este_lista, self._este_reszlet = self._lista_lap(
            nb, "&Ma este 20:00 és 23:00 között (főműsoridő):",
            "Ma esti műsorok", "A kijelölt műsor részletei")
        self._este_lista.Bind(
            wx.EVT_LISTBOX,
            lambda e: self._reszlet_mutat(self._este_sorok, self._este_lista,
                                          self._este_reszlet))
        self._este_sorok = []
        return lap

    def _csatorna_lap(self, nb):
        lap = wx.Panel(nb)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(lap, label="&Csatorna (fel/le nyíl, Enter = műsora):"),
              0, wx.ALL, 6)
        self._csat_lista = wx.ListBox(lap, style=wx.LB_SINGLE)
        self._csat_lista.SetName("Csatornák")
        self._csat_lista.Bind(wx.EVT_LISTBOX, lambda e: self._csatorna_valt())
        s.Add(self._csat_lista, 1, wx.EXPAND | wx.ALL, 6)

        # NAP-VÁLASZTÓ (Laci kérése): ne csak „mostantól" lehessen nézni a
        # műsort, hanem a holnapit vagy a holnaputánit is – a forrás ugyanis
        # több napra előre ad adatot.
        napsor = wx.BoxSizer(wx.HORIZONTAL)
        napsor.Add(wx.StaticText(lap, label="&Nap:"), 0,
                   wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 6)
        self._nap_valaszto = wx.Choice(lap, choices=["mostantól"])
        self._nap_valaszto.SetSelection(0)
        self._nap_valaszto.SetName(
            "Melyik nap műsora – mostantól, ma, holnap, és ameddig a forrás "
            "adatot ad")
        self._nap_valaszto.Bind(wx.EVT_CHOICE, lambda e: self._csatorna_valt())
        napsor.Add(self._nap_valaszto, 0, wx.ALIGN_CENTER_VERTICAL)
        s.Add(napsor, 0, wx.TOP, 4)

        s.Add(wx.StaticText(lap, label="A csatorna &műsora:"),
              0, wx.LEFT | wx.TOP, 6)
        self._nap_lista = wx.ListBox(lap, style=wx.LB_SINGLE)
        self._nap_lista.SetName("A csatorna műsora")
        self._nap_lista.Bind(
            wx.EVT_LISTBOX,
            lambda e: self._reszlet_mutat(self._nap_sorok, self._nap_lista,
                                          self._nap_reszlet))
        s.Add(self._nap_lista, 1, wx.EXPAND | wx.ALL, 6)
        self._nap_reszlet = wx.TextCtrl(
            lap, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 80))
        self._nap_reszlet.SetName("A kijelölt műsor részletei")
        s.Add(self._nap_reszlet, 0, wx.EXPAND | wx.ALL, 6)
        self._nap_sorok = []
        lap.SetSizer(s)
        return lap

    def _keres_lap(self, nb):
        lap = wx.Panel(nb)
        s = wx.BoxSizer(wx.VERTICAL)
        sor = wx.BoxSizer(wx.HORIZONTAL)
        sor.Add(wx.StaticText(lap, label="Mit &keresel?"),
                0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._keres_mezo = wx.TextCtrl(lap, style=wx.TE_PROCESS_ENTER)
        self._keres_mezo.SetName("Keresett műsor címe")
        self._keres_mezo.Bind(wx.EVT_TEXT_ENTER, lambda e: self._keres())
        sor.Add(self._keres_mezo, 1, wx.RIGHT, 6)
        g = wx.Button(lap, label="K&eresés")
        g.Bind(wx.EVT_BUTTON, lambda e: self._keres())
        sor.Add(g, 0)
        s.Add(sor, 0, wx.EXPAND | wx.ALL, 6)
        s.Add(wx.StaticText(lap, label="&Találatok (fel/le nyíl):"),
              0, wx.LEFT, 6)
        self._tal_lista = wx.ListBox(lap, style=wx.LB_SINGLE)
        self._tal_lista.SetName("Találatok")
        self._tal_lista.Bind(
            wx.EVT_LISTBOX,
            lambda e: self._reszlet_mutat(self._tal_sorok, self._tal_lista,
                                          self._tal_reszlet))
        s.Add(self._tal_lista, 1, wx.EXPAND | wx.ALL, 6)
        self._tal_reszlet = wx.TextCtrl(
            lap, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 90))
        self._tal_reszlet.SetName("A kijelölt találat részletei")
        s.Add(self._tal_reszlet, 0, wx.EXPAND | wx.ALL, 6)
        self._tal_sorok = []
        lap.SetSizer(s)
        return lap

    def _kedvenc_lap(self, nb):
        """KEDVENC-FIGYELŐ: írd be a kedvenc filmjeid/sorozataid címét, és a
        program szól, ha jönnek a műsorban."""
        lap = wx.Panel(nb)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(lap, label=(
            "Írd be a kedvenc filmjeid, sorozataid címét – a program minden "
            "betöltéskor megnézi, jön-e valamelyik, és SZÓL, ha igen.\n"
            "Elég a cím egy jellemző része is (ékezet nélkül is jó): pl. "
            "„reszkessetek”, „barátok közt”, „columbo”.")), 0, wx.ALL, 6)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        sor.Add(wx.StaticText(lap, label="Új &kedvenc:"),
                0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._kedvenc_mezo = wx.TextCtrl(lap, style=wx.TE_PROCESS_ENTER)
        self._kedvenc_mezo.SetName("Új kedvenc címe")
        self._kedvenc_mezo.Bind(wx.EVT_TEXT_ENTER, lambda e: self._kedvenc_add())
        sor.Add(self._kedvenc_mezo, 1, wx.RIGHT, 6)
        g_add = wx.Button(lap, label="&Hozzáadás")
        g_add.Bind(wx.EVT_BUTTON, lambda e: self._kedvenc_add())
        sor.Add(g_add, 0, wx.RIGHT, 6)
        g_del = wx.Button(lap, label="&Törlés a listából")
        g_del.Bind(wx.EVT_BUTTON, lambda e: self._kedvenc_torol())
        sor.Add(g_del, 0)
        s.Add(sor, 0, wx.EXPAND | wx.ALL, 6)

        s.Add(wx.StaticText(lap, label="A &kedvenceid:"), 0, wx.LEFT, 6)
        self._kedvenc_lista = wx.ListBox(lap, style=wx.LB_SINGLE)
        self._kedvenc_lista.SetName("A kedvenceid")
        s.Add(self._kedvenc_lista, 1, wx.EXPAND | wx.ALL, 6)

        self._kedvenc_ertesit = wx.CheckBox(
            lap, label="&Szóljon magától, ha jön valamelyik kedvencem "
                       "(a műsor betöltésekor)")
        self._kedvenc_ertesit.SetValue(self._ertesites_be())
        self._kedvenc_ertesit.Bind(
            wx.EVT_CHECKBOX, lambda e: self._ertesites_ment(
                self._kedvenc_ertesit.GetValue()))
        s.Add(self._kedvenc_ertesit, 0, wx.ALL, 6)

        sor2 = wx.BoxSizer(wx.HORIZONTAL)
        g_most = wx.Button(lap, label="&Mikor jönnek a kedvenceim? (most nézd meg)")
        g_most.Bind(wx.EVT_BUTTON, lambda e: self._kedvencek_ellenoriz(kezi=True))
        sor2.Add(g_most, 0, wx.RIGHT, 6)
        self._g_emlek = wx.Button(lap, label="&Emlékeztetőt kérek a kijelöltre")
        self._g_emlek.Bind(wx.EVT_BUTTON, lambda e: self._emlekezteto_egy())
        sor2.Add(self._g_emlek, 0, wx.RIGHT, 6)
        self._g_emlek_mind = wx.Button(lap, label="Emlékeztető M&INDRE")
        self._g_emlek_mind.Bind(wx.EVT_BUTTON, lambda e: self._emlekezteto_mind())
        sor2.Add(self._g_emlek_mind, 0)
        s.Add(sor2, 0, wx.ALL, 6)

        eml = wx.BoxSizer(wx.HORIZONTAL)
        eml.Add(wx.StaticText(lap, label="Emlékeztető &ennyi perccel előtte:"),
                0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self._emlek_perc = wx.SpinCtrl(lap, min=0, max=120,
                                       initial=self._emlek_perc_betolt())
        self._emlek_perc.SetName("Emlékeztető hány perccel a kezdés előtt")
        self._emlek_perc.Bind(wx.EVT_SPINCTRL, lambda e: self._emlek_perc_ment())
        eml.Add(self._emlek_perc, 0, wx.RIGHT, 12)
        self._emlek_auto = wx.CheckBox(
            lap, label="Emlékeztető beállítása &magától az új kedvenc-műsorokra")
        self._emlek_auto.SetValue(self._emlek_auto_betolt())
        self._emlek_auto.Bind(
            wx.EVT_CHECKBOX, lambda e: self._emlek_auto_ment(
                self._emlek_auto.GetValue()))
        eml.Add(self._emlek_auto, 0, wx.ALIGN_CENTER_VERTICAL)
        s.Add(eml, 0, wx.ALL, 6)

        s.Add(wx.StaticText(lap, label="&Ami jön a kedvencekből:"), 0, wx.LEFT, 6)
        self._kedvenc_talalat = wx.ListBox(lap, style=wx.LB_SINGLE)
        self._kedvenc_talalat.SetName("A kedvencek közelgő műsorai")
        self._kedvenc_talalat.Bind(
            wx.EVT_LISTBOX,
            lambda e: self._reszlet_mutat(self._kedvenc_sorok,
                                          self._kedvenc_talalat,
                                          self._kedvenc_reszlet))
        s.Add(self._kedvenc_talalat, 1, wx.EXPAND | wx.ALL, 6)
        self._kedvenc_reszlet = wx.TextCtrl(
            lap, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 70))
        self._kedvenc_reszlet.SetName("A kijelölt műsor részletei")
        s.Add(self._kedvenc_reszlet, 0, wx.EXPAND | wx.ALL, 6)
        self._kedvenc_sorok = []
        lap.SetSizer(s)
        wx.CallAfter(self._kedvencek_listaz)
        return lap

    # ---- kedvencek tárolása ----
    def _kedvencek_betolt(self):
        try:
            ertek = self.core.store.load("tvmusor_kedvencek", []) or []
            return [str(x) for x in ertek if str(x).strip()]
        except Exception:
            return []

    def _kedvencek_ment(self, lista):
        try:
            self.core.store.save("tvmusor_kedvencek", list(lista))
        except Exception:
            pass

    def _ertesites_be(self):
        try:
            return bool(self.core.store.load("tvmusor_kedvenc_ertesites", True))
        except Exception:
            return True

    def _ertesites_ment(self, ertek):
        try:
            self.core.store.save("tvmusor_kedvenc_ertesites", bool(ertek))
        except Exception:
            pass
        self._mond("Kedvenc-értesítés: " + ("bekapcsolva." if ertek
                                            else "kikapcsolva."))

    def _kedvencek_listaz(self):
        self._kedvenc_lista.Set(self._kedvencek_betolt())

    def _kedvenc_add(self):
        cim = (self._kedvenc_mezo.GetValue() or "").strip()
        if not cim:
            self._mond("Írd be a kedvenc film vagy sorozat címét.")
            return
        lista = self._kedvencek_betolt()
        if any(x.lower() == cim.lower() for x in lista):
            self._mond("Ez már a kedvenceid között van: %s" % cim)
            return
        lista.append(cim)
        self._kedvencek_ment(lista)
        self._kedvencek_listaz()
        self._kedvenc_mezo.SetValue("")
        self._mond("Felvéve a kedvencek közé: %s. Összesen %d kedvenced van."
                   % (cim, len(lista)))
        self._kedvencek_ellenoriz(kezi=True)

    def _kedvenc_torol(self):
        i = self._kedvenc_lista.GetSelection()
        lista = self._kedvencek_betolt()
        if not (0 <= i < len(lista)):
            self._mond("Előbb válassz ki egy kedvencet a listából.")
            return
        cim = lista.pop(i)
        self._kedvencek_ment(lista)
        self._kedvencek_listaz()
        self._mond("Törölve a kedvencek közül: %s" % cim)

    # ---- naptári emlékeztető a kedvenc műsorokra ----
    def _emlek_perc_betolt(self):
        try:
            return int(self.core.store.load("tvmusor_emlek_perc", 10) or 10)
        except Exception:
            return 10

    def _emlek_perc_ment(self):
        try:
            self.core.store.save("tvmusor_emlek_perc",
                                 int(self._emlek_perc.GetValue()))
        except Exception:
            pass

    def _emlek_auto_betolt(self):
        try:
            return bool(self.core.store.load("tvmusor_emlek_auto", False))
        except Exception:
            return False

    def _emlek_auto_ment(self, ertek):
        try:
            self.core.store.save("tvmusor_emlek_auto", bool(ertek))
        except Exception:
            pass
        self._mond("Automatikus emlékeztető a kedvencekre: "
                   + ("bekapcsolva." if ertek else "kikapcsolva."))
        if ertek:
            self._emlekezteto_mind(csendes=True)

    def _beallitott_emlekeztetok(self):
        """A már beállított kedvenc-emlékeztetők kulcsai – hogy ne tegyünk be
        ugyanarra a műsorra kétszer (a naptár ne teljen meg fölöslegesen)."""
        try:
            return set(self.core.store.load("tvmusor_emlek_kulcsok", []) or [])
        except Exception:
            return set()

    def _emlek_kulcsok_ment(self, kulcsok):
        try:
            # csak a friss (mai naptól) kulcsokat tartjuk meg
            ma = _dt.date.today().isoformat()
            szurt = [k for k in kulcsok if k.split("|", 1)[0] >= ma]
            self.core.store.save("tvmusor_emlek_kulcsok", sorted(szurt)[-500:])
        except Exception:
            pass

    def _naptar_kezelo(self):
        """A Core naptárkezelője (`OrganizerManager`), vagy None.

        FONTOS: a kezelő a CORE-ban él (`MainFrame._organizer`), és a program
        indulásakor MINDIG létrejön – azért, hogy az emlékeztetők akkor is
        elsüljenek, ha a naptár ablaka zárva van. A Szervezés modul csak az
        ABLAKOT adja hozzá, a kezelőt nem.

        Ezt eddig `self.core.main`-en át kerestük – csakhogy a CoreContext a
        főablakot `main_frame` (és `frame`) néven adja, `main` néven SOHA.
        A `getattr` alapértelmezése elnyelte, a keresés mindig üres kézzel tért
        vissza, és a felhasználó azt a hamis üzenetet kapta, hogy hiányzik a
        Szervezés modul. (Ugyanez a névelcsúszás volt a „Napi infó nem indul"
        gyökér-oka is – lásd a modkit `frame`-aliasát.) Ezért itt MINDEN ismert
        útvonalat végigpróbálunk, és a legvégén a saját szülő-ablakunkat is:
        a `register_window` megnyitója a FŐABLAKOT adja szülőnek.
        """
        jeloltek = [_biztos_attr(self.core, "organizer"),
                    _biztos_attr(self.core, "_organizer")]
        for nev in ("main_frame", "frame", "main"):
            jeloltek.append(_biztos_attr(self.core, nev))
        jeloltek.append(self.GetParent())
        try:
            app = wx.GetApp()
            jeloltek.append(app.GetTopWindow() if app else None)
        except Exception:
            pass
        for j in jeloltek:
            if j is None:
                continue
            if hasattr(j, "add_event"):          # maga a kezelő
                return j
            mgr = _biztos_attr(j, "_organizer")
            if mgr is not None and hasattr(mgr, "add_event"):
                return mgr
        return None

    def _naptar_hiba_szoveg(self):
        """Mit mondjunk, ha nem sikerült az emlékeztető.

        A régi szöveg a Szervezés modult kérte számon – rossz helyre küldte a
        felhasználót, mert a naptár KEZELŐJE a Core-ban van (a Szervezés csak
        az ablakát adja). Ha tényleg nincs kezelő, az a program hibája, nem a
        felhasználóé; ha pedig más hiba történt, mondjuk meg, mi.
        """
        hiba = getattr(self, "_naptar_hiba", "") or "nincs-naptar"
        if hiba == "nincs-naptar":
            return ("A naptárkezelő most nem érhető el, ezért nem tudok "
                    "emlékeztetőt beállítani. Ez a program hibája, nem a "
                    "tiéd – indítsd újra a SuperDL-t, és ha így is marad, "
                    "jelezd a fejlesztőnek.")
        return ("Nem sikerült beállítani az emlékeztetőt. A hiba: %s. "
                "A kedvenceid megmaradtak, próbáld újra." % hiba)

    def _emlekezteto_hozzaad(self, nev, m):
        """Egy műsorra naptári emlékeztetőt tesz (a Core közös naptárába).
        Visszaad: True, ha most tettük be; False, ha már volt; None, ha nem
        sikerült (ilyenkor a `_naptar_hiba` mondja meg, miért)."""
        self._naptar_hiba = ""
        org = self._naptar_kezelo()
        if org is None:
            self._naptar_hiba = "nincs-naptar"
            return None                      # nincs naptár – a hívó jelzi
        kulcs = "%s|%s|%s" % (m.kezd.date().isoformat(), m.idopont,
                              (m.cim or "")[:60])
        meglevo = self._beallitott_emlekeztetok()
        if kulcs in meglevo:
            return False
        try:
            from superdl import organizer as O
            perc = int(self._emlek_perc.GetValue())
            ev = O.Event(
                id=O.new_id(),
                title="TV: %s – %s" % (nev, m.cim or "műsor"),
                date=m.kezd.date().isoformat(),
                time=m.kezd.strftime("%H:%M"),
                note="SuperDL kedvenc-emlékeztető",
                reminder_min=perc,
                action_type="speak",
                action_data=("Figyelem! %s perc múlva kezdődik a kedvenced: %s, "
                             "a(z) %s csatornán." % (perc, m.cim or "műsor", nev))
                if perc else
                ("Most kezdődik a kedvenced: %s, a(z) %s csatornán."
                 % (m.cim or "műsor", nev)))
            org.add_event(ev)
        except Exception as exc:
            # NE mossuk össze a „nincs naptár"-ral: az eddigi közös None miatt
            # egy valódi hiba is úgy hangzott, mintha hiányozna a naptár.
            self._naptar_hiba = str(exc) or exc.__class__.__name__
            return None
        meglevo.add(kulcs)
        self._emlek_kulcsok_ment(meglevo)
        return True

    def _emlekezteto_egy(self):
        i = self._kedvenc_talalat.GetSelection()
        if not (0 <= i < len(self._kedvenc_sorok)):
            self._mond("Előbb válassz ki egy műsort a kedvencek listájából.")
            return
        nev, m = self._kedvenc_sorok[i]
        eredmeny = self._emlekezteto_hozzaad(nev, m)
        if eredmeny is None:
            self._mond(self._naptar_hiba_szoveg())
        elif eredmeny:
            self._mond("Emlékeztető beállítva: %s, %s csatorna, %s %s-kor – "
                       "%d perccel előtte szólok."
                       % (m.cim, nev, m.kezd.strftime("%m. %d."), m.idopont,
                          int(self._emlek_perc.GetValue())))
        else:
            self._mond("Erre a műsorra már van emlékeztetőd.")

    def _emlekezteto_mind(self, csendes=False):
        if not self._kedvenc_sorok:
            if not csendes:
                self._mond("Előbb nézzük meg, mikor jönnek a kedvenceid.")
            return
        # ne lehessen véletlenül teleszórni a naptárat (pl. ha a kedvenc egy
        # gyakori szó, mint a „híradó”) – sok tételnél rákérdezünk
        if not csendes and len(self._kedvenc_sorok) > 20:
            kerdes = ("%d műsorra tennék be emlékeztetőt – ez elég sok, és mind "
                      "bekerül a naptáradba.\n\nBiztosan mindre kéred? (Ha nem, "
                      "válaszd ki egyesével a listából, és használd az "
                      "„Emlékeztetőt kérek a kijelöltre” gombot.)"
                      % len(self._kedvenc_sorok))
            self._mond(kerdes)
            if wx.MessageBox(kerdes, "Emlékeztető mindre",
                             wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
                self._mond("Rendben, nem tettem be emlékeztetőt.")
                return
        uj = mar = 0
        nincs_naptar = False
        for nev, m in self._kedvenc_sorok:
            e = self._emlekezteto_hozzaad(nev, m)
            if e is None:
                nincs_naptar = True
                break
            uj += 1 if e else 0
            mar += 0 if e else 1
        if nincs_naptar:
            if not csendes:
                self._mond(self._naptar_hiba_szoveg())
            return
        if csendes and not uj:
            return
        self._mond("Kész: %d új emlékeztető a kedvenceidre%s. A naptár %d "
                   "perccel a kezdés előtt szól."
                   % (uj, (" (%d már megvolt)" % mar) if mar else "",
                      int(self._emlek_perc.GetValue())))

    def _kedvencek_ellenoriz(self, kezi=False):
        """Megnézi, jön-e valamelyik kedvenc – és SZÓL, ha igen."""
        kedvencek = self._kedvencek_betolt()
        if not kedvencek:
            if kezi:
                self._mond("Még nincs egy kedvenced sem. Írj be egyet fent, "
                           "és Hozzáadás.")
            return
        if not self._tv.csatorna_lista():
            if kezi:
                self._mond("Előbb be kell töltenem a műsorújságot – kis türelmet.")
            return
        tal = self._tv.kedvencek_talalat(kedvencek)
        self._kedvenc_sorok = [(nev, m) for _k, nev, m in tal]
        self._kedvenc_talalat.Set([
            "%s %s – %s – %s%s" % (m.kezd.strftime("%m. %d."), m.idopont, nev,
                                   m.cim or "(nincs cím)",
                                   (" – %d perc" % m.hossz_perc)
                                   if m.hossz_perc else "")
            for _k, nev, m in tal])
        if not tal:
            if kezi:
                self._mond("A jelenlegi műsorújságban egyik kedvenced sem "
                           "szerepel. A műsor általában néhány napra előre "
                           "tartalmaz adatot.")
            return
        self._kedvenc_talalat.SetSelection(0)
        _kedvenc, nev, m = tal[0]
        napok = {0: "ma", 1: "holnap"}.get(
            (m.kezd.date() - _dt.date.today()).days, "")
        mikor = ("%s %s-kor" % (napok, m.idopont) if napok
                 else m.kezd.strftime("%m. %d-án %H:%M-kor"))
        uzenet = ("Helló! Lesz a kedvenced: %s, a(z) %s csatornán, %s."
                  % (m.cim, nev, mikor))
        if len(tal) > 1:
            uzenet += " Összesen %d kedvenc-műsor jön – a Kedvencek fülön " \
                      "mind ott van." % len(tal)
        self._mond(uzenet)
        # ha kérted, a NAPTÁR is emlékeztessen – csak az ÚJ műsorokra
        if self._emlek_auto_betolt():
            self._emlekezteto_mind(csendes=True)

    def _beall_lap(self, nb):
        lap = wx.Panel(nb)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(lap, label=(
            "A műsorújság FORRÁSA (XMLTV-cím). Üresen hagyva az alapértelmezett, "
            "ingyenes közösségi forrást használjuk – ha az nem elérhető, "
            "automatikusan a tartalékot próbáljuk.\n"
            "A műsoradat a forrás szolgáltatójáé; a SuperDL csak megjeleníti.")),
            0, wx.ALL, 8)
        self._url_mezo = wx.TextCtrl(lap, value=self._url_betolt())
        self._url_mezo.SetName("A műsorújság forrásának címe")
        s.Add(self._url_mezo, 0, wx.EXPAND | wx.ALL, 8)
        g = wx.Button(lap, label="&Mentés és letöltés")
        g.Bind(wx.EVT_BUTTON, self._url_ment)
        s.Add(g, 0, wx.ALL, 8)
        lap.SetSizer(s)
        return lap

    # ------------------------------------------------------------ adat
    def _url_betolt(self):
        try:
            return str(self.core.store.load("tvmusor_epg_url", "") or "")
        except Exception:
            return ""

    def _url_ment(self, e):
        try:
            self.core.store.save("tvmusor_epg_url",
                                 (self._url_mezo.GetValue() or "").strip())
        except Exception:
            pass
        self._mond("A forrás elmentve – letöltöm a műsorújságot.")
        self._betolt(eroltetett=True)

    def _betolt(self, eroltetett=False):
        url = (self._url_mezo.GetValue() or "").strip() if hasattr(
            self, "_url_mezo") else self._url_betolt()
        self._allapot.SetValue("Műsorújság betöltése… kis türelmet.")
        self._mond("Műsorújság betöltése, kis türelmet.")

        def munka():
            return EM.TvMusor.betolt_okosan(url, gyorsitotar=not eroltetett)
        _hatterben(munka, self._betolt_kesz, self._betolt_hiba)

    def _betolt_kesz(self, eredmeny):
        if self._closing:
            return
        self._tv, honnan = eredmeny
        self._csatornak = self._tv.csatorna_lista()
        if not self._csatornak:
            self._allapot.SetValue("Nem sikerült műsorújságot betölteni.")
            self._mond("Sajnos most nem sikerült műsorújságot betölteni. "
                       "Próbáld később, vagy adj meg másik forrást a Beállítás "
                       "fülön.")
            return
        cimke = {"gyorsitotar": "a mentett (mai) adatból",
                 "halozat": "frissen letöltve",
                 "regi": "a KORÁBBAN mentett adatból (a forrás most nem elérhető)"}
        self._csat_lista.Set([n for _c, n in self._csatornak])
        if self._csatornak:
            self._csat_lista.SetSelection(0)
            self._csatorna_valt()
        self._most_frissit()
        self._este_frissit()
        self._allapot.SetValue("Kész: %d csatorna (%s)."
                               % (len(self._csatornak),
                                  cimke.get(honnan, honnan)))
        self._mond("Megvan a műsorújság: %d csatorna, %s. Válts a fülek közt: "
                   "Mi megy most, Ma este, Csatornák, Keresés, Kedvencek."
                   % (len(self._csatornak), cimke.get(honnan, honnan)))
        # KEDVENC-FIGYELŐ: ha be van kapcsolva, magától szól, ha jön kedvenc
        if self._ertesites_be():
            wx.CallLater(1200, lambda: self._kedvencek_ellenoriz(kezi=False))

    def _betolt_hiba(self, ex):
        if self._closing:
            return
        self._allapot.SetValue("Hiba a betöltéskor.")
        self._mond("Nem sikerült letölteni a műsorújságot: %s" % ex)

    # ------------------------------------------------------------ nézetek
    def _most_frissit(self):
        self._most_sorok = self._tv.mi_megy_most()
        self._most_lista.Set([m.felolvasva(nev)
                              for nev, m in self._most_sorok])
        if self._most_sorok:
            self._most_lista.SetSelection(0)

    def _este_frissit(self):
        self._este_sorok = self._tv.ma_este()
        self._este_lista.Set([m.felolvasva(nev)
                              for nev, m in self._este_sorok])
        if self._este_sorok:
            self._este_lista.SetSelection(0)

    def _napok_frissit(self, cid):
        """A nap-választó feltöltése ahhoz a csatornához, ami ki van jelölve.

        Csatornánként külön kérdezzük le: a források nem adnak minden
        csatornára ugyanannyi napot (van, amelyik négy napra előre, van,
        amelyik csak holnapig)."""
        import datetime as dt
        ma = dt.date.today()
        self._napok = [n for n in self._tv.elerheto_napok(cid) if n >= ma]
        cimkek = ["mostantól"] + [self._tv.nap_neve(n, ma) for n in self._napok]
        elozo = self._nap_valaszto.GetSelection()
        self._nap_valaszto.Set(cimkek)
        self._nap_valaszto.SetSelection(
            elozo if 0 <= elozo < len(cimkek) else 0)

    def _csatorna_valt(self):
        i = self._csat_lista.GetSelection()
        if not (0 <= i < len(self._csatornak)):
            return
        cid, nev = self._csatornak[i]
        self._napok_frissit(cid)
        nap_i = self._nap_valaszto.GetSelection()
        napok = getattr(self, "_napok", [])
        if nap_i <= 0 or nap_i > len(napok):
            musorok = self._tv.naprend(cid, darab=40)
            fejlec = "mostantól"
        else:
            nap = napok[nap_i - 1]
            musorok = self._tv.nap_musora(cid, nap)
            fejlec = self._tv.nap_neve(nap)
        self._nap_sorok = [(nev, m) for m in musorok]
        self._nap_lista.Set([m.felolvasva() for m in musorok])
        if not musorok:
            self._mond("%s – erre a napra nincs műsoradat ehhez a "
                       "csatornához." % nev)
            return
        self._nap_lista.SetSelection(0)
        if nap_i <= 0:
            futo, kov = self._tv.most_kovetkezo(cid)
            if futo:
                self._mond("%s – most: %s. Utána: %s."
                           % (nev, futo.cim,
                              kov.cim if kov else "nincs adat"))
        else:
            self._mond("%s – %s: %d műsor. Az első: %s."
                       % (nev, fejlec, len(musorok), musorok[0].cim))

    def _keres(self):
        kif = (self._keres_mezo.GetValue() or "").strip()
        if not kif:
            self._mond("Írd be, mit keresel – például a film címét.")
            return
        self._tal_sorok = self._tv.keres(kif)
        # a találatnál a DÁTUM is kell (nem csak az óra), de az időt ne mondjuk
        # kétszer: nap + idő + csatorna + cím + hossz
        self._tal_lista.Set([
            "%s %s – %s – %s%s" % (
                m.kezd.strftime("%m. %d."), m.idopont, nev,
                m.cim or "(nincs cím)",
                (" – %d perc" % m.hossz_perc) if m.hossz_perc else "")
            for nev, m in self._tal_sorok])
        if self._tal_sorok:
            self._tal_lista.SetSelection(0)
            nev, m = self._tal_sorok[0]
            self._mond("%d találat. A legközelebbi: %s, %s, %s."
                       % (len(self._tal_sorok), m.cim, nev,
                          m.kezd.strftime("%m. %d. %H:%M")))
        else:
            self._mond("Nincs találat erre: %s. A műsorújság általában csak "
                       "néhány napra előre tartalmaz adatot." % kif)

    def _reszlet_mutat(self, sorok, lista, mezo):
        i = lista.GetSelection()
        if not (0 <= i < len(sorok)):
            return
        nev, m = sorok[i]
        reszek = ["%s – %s" % (nev, m.cim or "(nincs cím)"),
                  "Kezdés: %s, vége: %s (%d perc)"
                  % (m.kezd.strftime("%Y. %m. %d. %H:%M"),
                     m.veg.strftime("%H:%M"), m.hossz_perc)]
        if m.leiras:
            reszek.append("")
            reszek.append(m.leiras)
        mezo.SetValue("\n".join(reszek))

    # ------------------------------------------------------------ egyéb
    def _on_key(self, e):
        if e.GetKeyCode() == wx.WXK_F1:
            self._sugo()
        elif e.GetKeyCode() == wx.WXK_F5:
            self._betolt(eroltetett=True)
        elif e.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        else:
            e.Skip()

    _SUGO = (
        "TV MŰSOR – SÚGÓ\n\n"
        "Akadálymentes tévéújság: mi megy most, mi lesz ma este, mikor adják a "
        "kedvencedet. IPTV-előfizetés NEM kell hozzá – a műsoradat egy nyilvános "
        "műsorújság-forrásból (XMLTV) jön.\n\n"
        "LAPFÜLEK (Ctrl+Tab vált köztük)\n"
        "• Mi megy most? – minden csatorna ÉPP FUTÓ műsora.\n"
        "• Ma este – a 20:00–23:00 közti főműsoridő, kezdés szerint.\n"
        "• Csatornák – válassz csatornát, alatta a műsora. A NAP mezőben "
        "beállíthatod, melyik nap érdekel: „mostantól” (a most futó és a "
        "későbbi műsorok), vagy egy konkrét nap – ma, holnap, holnapután, és "
        "ameddig a forrás adatot ad. Ilyenkor a nap TELJES műsora látszik, a "
        "reggeliekkel együtt. A választék csatornánként változhat: a források "
        "nem minden csatornára adnak ugyanannyi napot (a nagyobbaknál "
        "általában ma és még 3-4 nap, néhány kisebbnél csak holnapig). A "
        "hajnalig tartó filmek az ELŐZŐ naphoz tartoznak – ahogy a tévénéző is "
        "gondolja.\n"
        "• Keresés – írd be egy film/műsor címét (ékezet nélkül is jó), és "
        "megmondja, MIKOR és MELYIK csatornán adják.\n"
        "• KEDVENCEK – írd be a kedvenc filmjeid, sorozataid címét (akár többet "
        "is; elég egy jellemző rész, ékezet nélkül is). A program minden "
        "betöltéskor megnézi, jön-e valamelyik, és SZÓL: „Helló! Lesz a "
        "kedvenced…”. Ez a jelzés a fülön ki-be kapcsolható, és a „Mikor jönnek "
        "a kedvenceim?” gombbal bármikor lekérdezhető.\n"
        "  NAPTÁRI EMLÉKEZTETŐ: a kijelölt (vagy az összes) kedvenc-műsorra "
        "emlékeztetőt kérhetsz, és a SuperDL naptára a kezdés előtt megszólal: "
        "„Figyelem! 10 perc múlva kezdődik a kedvenced…”. Az előidő percben "
        "állítható, és bekapcsolható, hogy az ÚJ kedvenc-műsorokra magától "
        "beállítsa. Ugyanarra a műsorra nem tesz be kétszer.\n"
        "• Beállítás – a műsorújság forrásának címe (üresen: alapértelmezett; "
        "ha az nem elérhető, automatikusan tartalék forrást próbálunk).\n\n"
        "A listákon fel/le nyíllal lépkedsz, a képernyőolvasó minden sort "
        "felolvas; a kijelölt műsor részletei (leírás, pontos idő) alul, külön "
        "mezőben olvashatók.\n\n"
        "F5: friss letöltés. F1: ez a súgó. Escape: bezárás.\n\n"
        "A műsoradat a forrás szolgáltatójáé; a SuperDL csak megjeleníti, nem "
        "tárolja és nem terjeszti. A műsorváltozás jogát a csatornák fenntartják."
    )

    def _sugo(self):
        try:
            from superdl.helpdialog import show_help
            show_help(self, "Súgó – TV műsor", self._SUGO)
        except Exception:
            wx.MessageBox(self._SUGO, "Súgó – TV műsor",
                          wx.OK | wx.ICON_INFORMATION, self)

    def _mond(self, szoveg):
        if self._closing or not (szoveg or "").strip():
            return
        try:
            from superdl import screenreader
            if screenreader.speak(szoveg):
                return
        except Exception:
            pass
        v = getattr(self.core, "voice", None)
        if v:
            try:
                v.speak(szoveg, force=True)
            except Exception:
                pass

    def _on_close(self, e):
        self._closing = True
        e.Skip()
