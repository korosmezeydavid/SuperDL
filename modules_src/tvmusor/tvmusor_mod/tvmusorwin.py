# -*- coding: utf-8 -*-
"""TV műsor – az akadálymentes ablak (felolvasott tévéújság).

Lapfülek: „Mi megy most?", „Ma este", „Csatornák" (csatorna → napirend),
„Keresés" (pl. „mikor megy a Reszkessetek betörők?") és „Beállítás" (a
műsorújság forrásának címe). Minden lista navigálható (fel/le nyíl), a
képernyőolvasó minden sort felolvas, a részletek külön mezőben olvashatók.

A műsoradat a felhasználó által választott (alapból közösségi, ingyenes) XMLTV
forrásból jön – IPTV-előfizetés NEM kell hozzá.
"""
import threading

import wx

from . import epgmotor as EM


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
        s.Add(wx.StaticText(lap, label="A csatorna &műsora (mostantól):"),
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
                   "Mi megy most, Ma este, Csatornák, Keresés."
                   % (len(self._csatornak), cimke.get(honnan, honnan)))

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

    def _csatorna_valt(self):
        i = self._csat_lista.GetSelection()
        if not (0 <= i < len(self._csatornak)):
            return
        cid, nev = self._csatornak[i]
        musorok = self._tv.naprend(cid, darab=40)
        self._nap_sorok = [(nev, m) for m in musorok]
        self._nap_lista.Set([m.felolvasva() for m in musorok])
        if musorok:
            self._nap_lista.SetSelection(0)
            futo, kov = self._tv.most_kovetkezo(cid)
            if futo:
                self._mond("%s – most: %s. Utána: %s."
                           % (nev, futo.cim,
                              kov.cim if kov else "nincs adat"))

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
        "• Csatornák – válassz csatornát, alatta a műsora mostantól.\n"
        "• Keresés – írd be egy film/műsor címét (ékezet nélkül is jó), és "
        "megmondja, MIKOR és MELYIK csatornán adják.\n"
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
