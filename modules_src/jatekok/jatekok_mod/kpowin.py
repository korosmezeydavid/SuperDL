# -*- coding: utf-8 -*-
"""Kő-papír-olló / Répa-nyuszi-pisztoly – a Játékok modul ablaka.

Két fül: GÉP ELLEN (szerencsés vagy ravasz gép, 1/3/5/7 körös meccs) és ONLINE
egymás ellen (Ably-szoba `kpo:` előtaggal – a telefonos SuperDL is ide jön, így
gép és telefon is játszhat egymással). A választás gombokkal VAGY az 1, 2, 3
billentyűvel. Minden felolvasva, hangokkal és beszólásokkal.

A játék magja a `kpo.py`-ban van (ott tesztelve); ez csak a felület.
"""
import os
import queue
import random
import threading

import wx

from . import kpo
from . import netroom

_HANG_MAPPA = os.path.join(os.path.dirname(__file__), "kpo_hang")
_TAPS = os.path.join(os.path.dirname(__file__), "szerencsekerek_hang", "taps.mp3")

SUGO = (
    "KŐ, PAPÍR, OLLÓ – és RÉPA, NYUSZI, PISZTOLY – SÚGÓ\n\n"
    "KÉT VÁLTOZAT\n"
    "• Kő, papír, olló: a kő kicsorbítja az ollót, az olló elvágja a papírt, a "
    "papír becsomagolja a követ.\n"
    "• Répa, nyuszi, pisztoly: a nyuszi megeszi a répát, a pisztollyal le lehet "
    "lőni a nyuszit, a répával viszont be lehet dugni a pisztoly csövét.\n\n"
    "GÉP ELLEN\n"
    "Válaszd ki a változatot, a meccs hosszát (1, 3, 5 vagy 7 kör – az nyer, aki "
    "előbb szerzi meg a többséget, a döntetlen nem számít) és a gépet: a "
    "SZERENCSÉS gép vakon választ, a RAVASZ figyeli a szokásaidat. Aztán válassz "
    "a három gombbal, vagy nyomd meg az 1, 2 vagy 3 billentyűt.\n\n"
    "ONLINE\n"
    "Írd be a neved. Ha te szervezel: „Új szoba”, és mondd be vagy küldd el a "
    "kódot a társadnak. Ha csatlakozol: írd be a kódot, majd „Csatlakozás”. "
    "Amikor a társad bent van, a szervező indítja a meccset. Telefonos "
    "SuperDL-lel is játszhattok egymás ellen! Csalni nem lehet: a választásod "
    "csak akkor derül ki a másiknak, amikor ő is választott.\n\n"
    "BILLENTYŰK: 1, 2, 3 – választás; F1 – súgó; Escape – bezárás."
)


class _Hangok:
    """Két lejátszó: effektek és a taps (egymásra szólhatnak)."""

    def __init__(self):
        self._p = [None, None]

    def szol(self, nev_vagy_ut, csatorna=0):
        try:
            ut = nev_vagy_ut
            if not os.path.isabs(ut):
                ut = os.path.join(_HANG_MAPPA, nev_vagy_ut + ".wav")
            if not os.path.isfile(ut):
                return
            from superdl.audioengine import Player
            if self._p[csatorna] is None:
                self._p[csatorna] = Player()
            self._p[csatorna].play(ut, "")
        except Exception:
            pass

    def kesobb(self, ms, nev, csatorna=0):
        wx.CallLater(ms, self.szol, nev, csatorna)

    def leallit(self):
        for p in self._p:
            try:
                if p:
                    p.stop()
            except Exception:
                pass


class _Felolvaso:
    """Napló + képernyőolvasó (vagy a program saját hangja)."""

    def _mondd(self, szoveg):
        if getattr(self, "_closing", False) or not (szoveg or "").strip():
            return
        try:
            self._naplo.AppendText(szoveg + "\n")
        except Exception:
            pass
        # ELŐSZÖR a képernyőolvasó, csak utána a saját hang (test_bemondas_sorrend)
        try:
            from superdl import screenreader
            if screenreader.speak(szoveg):
                return
        except Exception:
            pass
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            try:
                sv.speak(szoveg, force=True)
            except Exception:
                pass


def _gep_neve():
    try:
        from .jatekok import sajat as SJ
        n = SJ._ellenfelek(1)
        if n:
            return n[0]
    except Exception:
        pass
    return random.choice(["Robi", "Gépi Géza", "Csipszi"])


def _valasztas_gombok(panel, sizer, handler):
    gombok = []
    for i in range(3):
        g = wx.Button(panel, label=f"&{i + 1}")
        g.Bind(wx.EVT_BUTTON, lambda e, i=i: handler(i))
        sizer.Add(g, 1, wx.RIGHT, 6)
        gombok.append(g)
    return gombok


def _gomb_cimkek(gombok, valt):
    for i, g in enumerate(gombok):
        nev = valt.nev_of(valt.elemek[i])
        g.SetLabel(f"&{i + 1} {nev.capitalize()}")
        g.SetName(f"{i + 1}: {nev}")


# ====================================================================== gép ellen

class GepPanel(_Felolvaso, wx.Panel):
    KORHOSSZOK = [1, 3, 5, 7]

    def __init__(self, parent, main, hangok):
        super().__init__(parent)
        self.main = main
        self.hangok = hangok
        self._closing = False
        self._foglalt = False
        self._gepnev = _gep_neve()
        self._valtok = kpo.valtozatok()
        self._build()
        self._uj_meccs(bejelent=False)

    def _build(self):
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(self, label=(
            "Játssz a gép ellen! Válassz a három gombbal vagy az 1, 2, 3 "
            "billentyűvel. Súgó: F1.")), 0, wx.ALL, 8)

        self.valt_rb = wx.RadioBox(self, label="&Változat", choices=[
            self._valtok["kpo"].nev, self._valtok["rnp"].nev],
            majorDimension=1, style=wx.RA_SPECIFY_ROWS)
        self.valt_rb.Bind(wx.EVT_RADIOBOX, lambda e: self._uj_meccs())
        v.Add(self.valt_rb, 0, wx.LEFT | wx.RIGHT, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        sor.Add(wx.StaticText(self, label="Meccs &hossza:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.hossz = wx.Choice(self, choices=[kpo.meccs_leiras(n) for n in self.KORHOSSZOK])
        self.hossz.SetSelection(2)
        self.hossz.SetName("Meccs hossza")
        self.hossz.Bind(wx.EVT_CHOICE, lambda e: self._uj_meccs())
        sor.Add(self.hossz, 0, wx.RIGHT, 12)
        sor.Add(wx.StaticText(self, label="&Gép:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        st = kpo.adatok()["gep_stilus"]
        self.stilus = wx.Choice(self, choices=[st["ravasz"], st["szerencse"]])
        self.stilus.SetSelection(0)
        self.stilus.SetName("A gép stílusa")
        self.stilus.Bind(wx.EVT_CHOICE, lambda e: self._uj_meccs())
        sor.Add(self.stilus, 1)
        v.Add(sor, 0, wx.EXPAND | wx.ALL, 8)

        self.visszaszamlal = wx.CheckBox(self, label="Visszaszámlálás &hanggal")
        self.visszaszamlal.SetValue(True)
        v.Add(self.visszaszamlal, 0, wx.LEFT, 8)

        self.allas = wx.TextCtrl(self, style=wx.TE_READONLY)
        self.allas.SetName("Állás")
        v.Add(self.allas, 0, wx.EXPAND | wx.ALL, 8)

        gs = wx.BoxSizer(wx.HORIZONTAL)
        self.gombok = _valasztas_gombok(self, gs, self.valaszt)
        v.Add(gs, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        s2 = wx.BoxSizer(wx.HORIZONTAL)
        g = wx.Button(self, label="Új &meccs")
        g.Bind(wx.EVT_BUTTON, lambda e: self._uj_meccs())
        s2.Add(g, 0, wx.RIGHT, 6)
        g = wx.Button(self, label="&Szabály")
        g.Bind(wx.EVT_BUTTON, lambda e: self._mondd(self.valt.szabaly))
        s2.Add(g, 0)
        v.Add(s2, 0, wx.ALL, 8)

        v.Add(wx.StaticText(self, label="A játék &menete:"), 0, wx.LEFT, 8)
        self._naplo = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
                                  size=(-1, 140))
        self._naplo.SetName("A játék menete, csak olvasható")
        v.Add(self._naplo, 1, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(v)

    @property
    def valt(self):
        return self._valtok["kpo" if self.valt_rb.GetSelection() == 0 else "rnp"]

    def _uj_meccs(self, bejelent=True):
        self._foglalt = False
        kor_db = self.KORHOSSZOK[max(0, self.hossz.GetSelection())]
        self.meccs = kpo.Meccs(kor_db)
        stilus = "ravasz" if self.stilus.GetSelection() == 0 else "szerencse"
        self.gep = kpo.gep(stilus)
        _gomb_cimkek(self.gombok, self.valt)
        self._allas_frissit()
        if bejelent:
            self.hangok.szol("kpo_belepett")
            self._mondd(f"Új meccs: {self.valt.nev}, {kpo.meccs_leiras(kor_db)}, "
                        f"ellenfeled {self._gepnev}. {self.valt.szabaly} "
                        "Válassz: 1, 2 vagy 3!")

    def _allas_frissit(self):
        self.allas.SetValue(self.meccs.allas("Te", self._gepnev))

    def valaszt(self, i):
        if self._foglalt:
            return
        if self.meccs.vege:
            self._uj_meccs(bejelent=False)
        self._foglalt = True
        self.hangok.szol("kpo_valasztas")
        if self.visszaszamlal.GetValue():
            self.hangok.kesobb(120, "kpo_visszaszamlalas")
            wx.CallLater(1250, self._kiertekel, i)
        else:
            wx.CallLater(150, self._kiertekel, i)

    def _kiertekel(self, i):
        if self._closing:
            return
        v = self.valt
        gi = self.gep.valaszt()
        self.gep.megfigyel(i)
        te, ok = v.elemek[i], v.elemek[gi]
        e, mondat, hang = kpo.kor_leiras(v, te, ok)
        self.meccs.rogzit(e)
        self.hangok.szol(hang)
        reszek = [f"Te: {v.nev_of(te)}. {self._gepnev}: {v.nev_of(ok)}.", mondat]
        if e > 0:
            reszek.append("Ezt a kört te nyerted!")
        elif e < 0:
            reszek.append(f"Ezt a kört {self._gepnev} nyerte.")
        if random.random() < 0.6:
            fajta = "nyersz" if e > 0 else "vesztesz" if e < 0 else "dontetlen"
            reszek.append(kpo.beszolas(fajta, gep=self._gepnev))
        self._allas_frissit()
        if self.meccs.vege:
            nyert = self.meccs.nyertel
            reszek.append(kpo.beszolas("meccs_nyersz" if nyert else "meccs_vesztesz",
                                       gep=self._gepnev))
            reszek.append(self.meccs.allas("Te", self._gepnev)
                          + " Új meccshez válassz újra, vagy nyomd meg az Új meccs gombot.")
            self.hangok.kesobb(1100, "kpo_meccs_nyer" if nyert else "kpo_meccs_veszit")
            if nyert:
                self.hangok.kesobb(2900, _TAPS, 1)
        else:
            if self.meccs.kor_db > 1:
                reszek.append(self.meccs.allas("Te", self._gepnev))
            if e:
                self.hangok.kesobb(1100, "kpo_kor_nyer" if e > 0 else "kpo_kor_veszit")
        self._mondd(" ".join(r for r in reszek if r))
        self._foglalt = False


# ====================================================================== online

class _SorosKuldo:
    """Egyetlen háttérszál küld, SORRENDBEN (a lenyomat mindig a felfedés előtt
    érjen oda) – és a felület közben nem akad meg a hálózaton."""

    def __init__(self, szoba, hiba_cb):
        self.szoba = szoba
        self.hiba_cb = hiba_cb
        self.q = queue.Queue()
        self._t = threading.Thread(target=self._fut, daemon=True)
        self._t.start()

    def __call__(self, tipus, adat):
        self.q.put((tipus, adat))

    def _fut(self):
        while True:
            t = self.q.get()
            if t is None:
                return
            try:
                self.szoba.kuld(*t)
            except Exception as e:
                self.hiba_cb(e)

    def leallit(self):
        self.q.put(None)


class OnlinePanel(_Felolvaso, wx.Panel):
    KORHOSSZOK = GepPanel.KORHOSSZOK

    def __init__(self, parent, main, hangok):
        super().__init__(parent)
        self.main = main
        self.hangok = hangok
        self._closing = False
        self._szoba = None
        self._kuldo = None
        self.jatek = None
        self._valtok = kpo.valtozatok()
        self._build()
        wx.CallAfter(self._kulcs_ellenoriz)

    # ---------------------------------------------------------------- felület
    def _alap_nev(self):
        try:
            s = getattr(self.main, "settings", {}) or {}
            return (s.get("nev") or s.get("felhasznalo") or "").strip() or "Játékos"
        except Exception:
            return "Játékos"

    def _build(self):
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(self, label=(
            "Játssz egy barátod ellen, akár telefonról is – csak internet kell. "
            "Csalni nem lehet. Súgó: F1.")), 0, wx.ALL, 8)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        sor.Add(wx.StaticText(self, label="A &neved:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.nev_mezo = wx.TextCtrl(self, value=self._alap_nev())
        self.nev_mezo.SetName("A neved")
        sor.Add(self.nev_mezo, 1)
        v.Add(sor, 0, wx.EXPAND | wx.ALL, 8)

        self.valt_rb = wx.RadioBox(self, label="&Változat (a szervező választja)", choices=[
            self._valtok["kpo"].nev, self._valtok["rnp"].nev],
            majorDimension=1, style=wx.RA_SPECIFY_ROWS)
        self.valt_rb.Bind(wx.EVT_RADIOBOX, lambda e: _gomb_cimkek(self.gombok, self._valt_ui()))
        v.Add(self.valt_rb, 0, wx.LEFT | wx.RIGHT, 8)
        sor = wx.BoxSizer(wx.HORIZONTAL)
        sor.Add(wx.StaticText(self, label="Meccs &hossza:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.hossz = wx.Choice(self, choices=[kpo.meccs_leiras(n) for n in self.KORHOSSZOK])
        self.hossz.SetSelection(2)
        self.hossz.SetName("Meccs hossza")
        sor.Add(self.hossz, 0)
        v.Add(sor, 0, wx.ALL, 8)

        lob = wx.BoxSizer(wx.HORIZONTAL)
        self.uj_gomb = wx.Button(self, label="Ú&j szoba (én szervezem)")
        self.uj_gomb.Bind(wx.EVT_BUTTON, self._uj_szoba)
        lob.Add(self.uj_gomb, 0, wx.RIGHT, 6)
        lob.Add(wx.StaticText(self, label="&kód:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.kod_mezo = wx.TextCtrl(self, size=(90, -1))
        self.kod_mezo.SetName("Szobakód")
        lob.Add(self.kod_mezo, 0, wx.RIGHT, 4)
        g = wx.Button(self, label="Kód &másolása")
        g.Bind(wx.EVT_BUTTON, self._kod_masol)
        lob.Add(g, 0, wx.RIGHT, 6)
        self.csat_gomb = wx.Button(self, label="&Csatlakozás")
        self.csat_gomb.Bind(wx.EVT_BUTTON, self._csatlakozas)
        lob.Add(self.csat_gomb, 0, wx.RIGHT, 6)
        self.indit_gomb = wx.Button(self, label="Meccs &indítása")
        self.indit_gomb.Bind(wx.EVT_BUTTON, lambda e: self._indit())
        self.indit_gomb.Disable()
        lob.Add(self.indit_gomb, 0)
        v.Add(lob, 0, wx.ALL, 8)

        self.allas = wx.TextCtrl(self, style=wx.TE_READONLY)
        self.allas.SetName("Állás")
        v.Add(self.allas, 0, wx.EXPAND | wx.ALL, 8)

        gs = wx.BoxSizer(wx.HORIZONTAL)
        self.gombok = _valasztas_gombok(self, gs, self.valaszt)
        _gomb_cimkek(self.gombok, self._valt_ui())
        v.Add(gs, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        s2 = wx.BoxSizer(wx.HORIZONTAL)
        self.ujra_gomb = wx.Button(self, label="&Visszavágó")
        self.ujra_gomb.Bind(wx.EVT_BUTTON, lambda e: self._visszavago())
        s2.Add(self.ujra_gomb, 0, wx.RIGHT, 6)
        self.kilep_gomb = wx.Button(self, label="Kilépés a s&zobából")
        self.kilep_gomb.Bind(wx.EVT_BUTTON, lambda e: self._kilep_szobabol())
        s2.Add(self.kilep_gomb, 0)
        v.Add(s2, 0, wx.ALL, 8)

        v.Add(wx.StaticText(self, label="Cse&vegés:"), 0, wx.LEFT, 8)
        self.chat_atirat = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 50))
        self.chat_atirat.SetName("Csevegés")
        v.Add(self.chat_atirat, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        cs = wx.BoxSizer(wx.HORIZONTAL)
        self.chat_be = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.chat_be.SetName("Írj a társadnak, Enter a küldés")
        self.chat_be.Bind(wx.EVT_TEXT_ENTER, lambda e: self._chat_kuld())
        cs.Add(self.chat_be, 1, wx.RIGHT, 6)
        g = wx.Button(self, label="Kül&dés")
        g.Bind(wx.EVT_BUTTON, lambda e: self._chat_kuld())
        cs.Add(g, 0)
        v.Add(cs, 0, wx.EXPAND | wx.ALL, 8)

        self._naplo = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
                                  size=(-1, 100))
        self._naplo.SetName("A játék menete, csak olvasható")
        v.Add(self._naplo, 1, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(v)
        self._jatek_gombok(False)

    def _valt_ui(self):
        return self._valtok["kpo" if self.valt_rb.GetSelection() == 0 else "rnp"]

    def _jatek_gombok(self, be):
        for g in self.gombok:
            g.Enable(be)
        self.ujra_gomb.Enable(bool(self.jatek and self.jatek.fazis == "vege"))

    def _kulcs_ellenoriz(self):
        if not netroom.ably_kulcs():
            self._mondd("Az online játék ebben a csomagban nem elérhető, a gép "
                        "elleni játék viszont mindig megy!")

    # ---------------------------------------------------------------- szoba
    def _nev(self):
        return (self.nev_mezo.GetValue() or "Játékos").strip()[:30] or "Játékos"

    def _szoba_nyit(self, kod, host):
        szoba = netroom.NetSzoba(kod, self._nev(), elotag=kpo.CSATORNA_ELOTAG)
        if not szoba.elerheto():
            self._mondd("Nincs online kulcs vagy kód – nem tudok szobát nyitni.")
            return False
        self._szoba = szoba
        self._kuldo = _SorosKuldo(szoba, lambda e: wx.CallAfter(
            self._mondd, "Nem sikerült üzenetet küldeni – van internet?"))
        k = 0 if self.valt_rb.GetSelection() == 0 else 1
        self.jatek = kpo.OnlineJatek(self._nev(), host, self._kuldo,
                                     valtozat_kulcs=("kpo", "rnp")[k],
                                     kor_db=self.KORHOSSZOK[max(0, self.hossz.GetSelection())])
        szoba.figyel(lambda u: wx.CallAfter(self._fogad, u), koz=0.7)
        self.uj_gomb.Disable()
        self.csat_gomb.Disable()
        self.nev_mezo.Disable()
        return True

    def _uj_szoba(self, e):
        kod = netroom.szobakod()
        if not self._szoba_nyit(kod, True):
            return
        self.kod_mezo.SetValue(kod)
        self._mondd(f"Szoba nyitva! A kód: {kod}, betűnként: {' '.join(kod)}. "
                    "Küldd el a társadnak, és várd, hogy belépjen.")

    def _csatlakozas(self, e):
        kod = (self.kod_mezo.GetValue() or "").strip().upper()
        if not kod:
            self._mondd("Írd be a szobakódot, amit a társad adott.")
            return
        if not self._szoba_nyit(kod, False):
            return
        self.valt_rb.Disable()
        self.hossz.Disable()
        self.jatek.belep()
        self._mondd(f"Csatlakoztál a(z) {' '.join(kod)} szobához. Várd, hogy a "
                    "szervező elindítsa a meccset.")

    def _kod_masol(self, e):
        kod = (self.kod_mezo.GetValue() or "").strip()
        if not kod:
            self._mondd("Előbb nyiss egy szobát.")
            return
        try:
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(kod))
                wx.TheClipboard.Close()
                self._mondd(f"A {kod} kód a vágólapon.")
        except Exception:
            self._mondd(f"A kód: {kod}.")

    def _indit(self):
        if not self.jatek or not self.jatek.host:
            return
        if not self.jatek.ellen_pid:
            self._mondd("Még nincs ellenfél a szobában.")
            return
        k = 0 if self.valt_rb.GetSelection() == 0 else 1
        self.jatek.inditas(("kpo", "rnp")[k], self.KORHOSSZOK[max(0, self.hossz.GetSelection())])
        self._start_bejelent()

    def _visszavago(self):
        if not self.jatek:
            return
        if self.jatek.host:
            self._indit()
        else:
            self.jatek.visszavago()
            self._mondd("Visszavágót kértél – a szervező gépe azonnal indítja.")

    def _kilep_szobabol(self):
        if self._szoba:
            if self.jatek:
                self.jatek.kilep()
            wx.CallLater(800, self._szoba_zar)
        self._mondd("Kiléptél a szobából.")

    def _szoba_zar(self):
        try:
            if self._szoba:
                self._szoba.leallit()
            if self._kuldo:
                self._kuldo.leallit()
        except Exception:
            pass
        self._szoba = self._kuldo = self.jatek = None
        for w in (self.uj_gomb, self.csat_gomb, self.nev_mezo, self.valt_rb, self.hossz):
            w.Enable()
        self.indit_gomb.Disable()
        self.kod_mezo.SetValue("")
        self.allas.SetValue("")
        self._jatek_gombok(False)

    def _chat_kuld(self):
        t = (self.chat_be.GetValue() or "").strip()
        if not t or not self.jatek:
            return
        self.jatek.csevej(t)
        self.chat_atirat.AppendText(f"Te: {t}\n")
        self.chat_be.SetValue("")

    # ---------------------------------------------------------------- játék
    def valaszt(self, i):
        j = self.jatek
        if not j or j.fazis != "jatek":
            self._mondd("Most nem lehet választani – még nem indult a meccs.")
            return
        if j.valasztott_mar():
            self._mondd("Ebben a körben már választottál. Várjuk a társadat.")
            return
        kulcs = j.valt.elemek[i]
        self.hangok.szol("kpo_valasztas")
        evs = j.valaszt(kulcs)
        if not any(ev[0] == "kor" for ev in evs):
            self._mondd(f"Választottál: {j.valt.nev_of(kulcs)}. Várjuk {j.ellen_nev} választását.")
        for ev in evs:
            self._esemeny(ev)

    def _start_bejelent(self):
        j = self.jatek
        _gomb_cimkek(self.gombok, j.valt)
        self.valt_rb.SetSelection(0 if j.valt.kulcs == "kpo" else 1)
        self._allas_frissit()
        self._jatek_gombok(True)
        self.indit_gomb.Disable()
        self.hangok.szol("kpo_belepett")
        self._mondd(f"Indul a meccs {j.ellen_nev} ellen: {j.valt.nev}, "
                    f"{kpo.meccs_leiras(j.kor_db)}. {j.valt.szabaly} Válassz: 1, 2 vagy 3!")
        try:
            self.gombok[0].SetFocus()
        except Exception:
            pass

    def _allas_frissit(self):
        j = self.jatek
        if j:
            self.allas.SetValue(j.meccs.allas("Te", j.ellen_nev or "a társad"))

    def _fogad(self, u):
        if self._closing or not self.jatek:
            return
        for ev in self.jatek.fogad(u):
            self._esemeny(ev)

    def _esemeny(self, ev):
        j = self.jatek
        f = ev[0]
        if f == "belepett":
            self.hangok.szol("kpo_belepett")
            self.indit_gomb.Enable()
            self._mondd(f"{ev[1]} belépett a szobába! Indíthatod a meccset: Meccs indítása.")
        elif f == "start":
            self._start_bejelent()
        elif f == "tele":
            self._mondd("Ez a szoba már foglalt – ketten játszanak benne. Kérj új kódot.")
            self._szoba_zar()
        elif f == "ellen_kesz":
            self.hangok.szol("kpo_ellenfel_kesz")
            if not j.valasztott_mar():
                self._mondd(f"{ev[1]} már választott. Most te jössz!")
        elif f == "kor":
            _, e, te, ok, mondat, hang = ev
            self.hangok.szol(hang)
            reszek = [f"Te: {j.valt.nev_of(te)}. {j.ellen_nev}: {j.valt.nev_of(ok)}.", mondat]
            fajta = "online_nyersz" if e > 0 else "online_vesztesz" if e < 0 else "online_dontetlen"
            reszek.append(kpo.beszolas(fajta, ellenfel=j.ellen_nev))
            if j.meccs.kor_db > 1:
                reszek.append(j.meccs.allas("Te", j.ellen_nev))
            if e and not j.meccs.vege:
                self.hangok.kesobb(1100, "kpo_kor_nyer" if e > 0 else "kpo_kor_veszit")
            self._allas_frissit()
            self._mondd(" ".join(r for r in reszek if r))
        elif f == "meccs_vege":
            nyert = ev[1]
            self.hangok.kesobb(1100, "kpo_meccs_nyer" if nyert else "kpo_meccs_veszit")
            if nyert:
                self.hangok.kesobb(2900, _TAPS, 1)
            self._jatek_gombok(False)
            self._mondd(kpo.beszolas("online_meccs_nyersz" if nyert else "online_meccs_vesztesz",
                                     ellenfel=j.ellen_nev) + " Visszavágó: V betű.")
        elif f == "csalas":
            self._mondd(f"Hiba a körben: {ev[1]} választása nem egyezett a lenyomatával. "
                        "A kört újrajátsszuk – válassz újra!")
        elif f == "kilepett":
            self._jatek_gombok(False)
            if j and j.host:
                self.indit_gomb.Disable()
                self._mondd(f"{ev[1]} kilépett. A szoba nyitva marad, jöhet új ellenfél.")
            else:
                self._mondd(f"{ev[1]} kilépett a szobából.")
        elif f == "ujra_ker":
            self._mondd(f"{ev[1]} visszavágót kért – indul!")
        elif f == "csevej":
            self.chat_atirat.AppendText(f"{ev[1]}: {ev[2]}\n")
            self._mondd(f"{ev[1]} üzeni: {ev[2]}")

    def leallit(self):
        self._closing = True
        try:
            if self.jatek:
                self.jatek.kilep()
        except Exception:
            pass
        sz, k = self._szoba, self._kuldo
        # a „kilép" üzenetnek legyen ideje kimenni, mielőtt a küldő leáll
        def _zar():
            try:
                if sz:
                    sz.leallit()
                if k:
                    k.leallit()
            except Exception:
                pass
        threading.Timer(1.5, _zar).start()


# ====================================================================== ablak

class KpoAblak(wx.Dialog):
    def __init__(self, main, jatek=None, gep_getter=None):
        super().__init__(main, title="Játék – Kő, papír, olló", size=(760, 640),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.main = main
        self.hangok = _Hangok()
        nb = wx.Notebook(self)
        self.gep_panel = GepPanel(nb, main, self.hangok)
        nb.AddPage(self.gep_panel, "Gép ellen")
        self.online_panel = OnlinePanel(nb, main, self.hangok)
        nb.AddPage(self.online_panel, "Online – egymás ellen")
        self._nb = nb
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(nb, 1, wx.EXPAND | wx.ALL, 6)
        self.SetSizer(s)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        wx.CallAfter(self._udv)

    def _udv(self):
        self.gep_panel._mondd(
            "Kő, papír, olló – vagy répa, nyuszi, pisztoly! Két fül van: Gép ellen és "
            "Online (váltás: Ctrl+Tab). Válassz az 1, 2, 3 billentyűvel. Súgó: F1.")
        self.hangok.szol("kpo_belepett")
        try:
            self.gep_panel.gombok[0].SetFocus()
        except Exception:
            pass

    def _aktiv(self):
        return self.gep_panel if self._nb.GetSelection() == 0 else self.online_panel

    def _on_key(self, e):
        k = e.GetKeyCode()
        fokusz = wx.Window.FindFocus()
        szovegben = isinstance(fokusz, wx.TextCtrl) and not fokusz.HasFlag(wx.TE_READONLY)
        if k == wx.WXK_F1:
            dlg = wx.MessageDialog(self, SUGO, "Súgó – Kő, papír, olló", wx.OK)
            dlg.ShowModal()
            dlg.Destroy()
            return
        if k == wx.WXK_ESCAPE:
            self.Close()
            return
        if not szovegben and not e.HasAnyModifiers():
            if k in (ord("1"), ord("2"), ord("3"), wx.WXK_NUMPAD1, wx.WXK_NUMPAD2, wx.WXK_NUMPAD3):
                i = {ord("1"): 0, ord("2"): 1, ord("3"): 2,
                     wx.WXK_NUMPAD1: 0, wx.WXK_NUMPAD2: 1, wx.WXK_NUMPAD3: 2}[k]
                self._aktiv().valaszt(i)
                return
            if k == ord("V") and self._aktiv() is self.online_panel:
                self.online_panel._visszavago()
                return
        e.Skip()

    def _on_close(self, e):
        self.gep_panel._closing = True
        self.online_panel.leallit()
        self.hangok.leallit()
        self.Destroy()
