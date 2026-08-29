# -*- coding: utf-8 -*-
"""iPhone modul – akadálymentes ablak (wxPython).

Három lapfül: Zenék, Fotók és videók, Alkalmazások fájljai. Mindegyiken ugyanaz
a két művelet: MENTÉS a gépre és TÖRLÉS a telefonról. A listák jelölőnégyzetesek
(a képernyőolvasó bemondja, mi van kipipálva), a hosszú műveletek háttérszálon
futnak, és a haladás felolvasva is elhangzik.

A törlés SOHA nem indul rákérdezés nélkül, és a zenéknél a program a művelet
előtt biztonsági mentést készít a telefon zene-adatbázisáról.
"""
import os
import threading
import time

import wx

from . import iphone_core as C
from . import afc as A


_SUGO = (
    "iPHONE – SÚGÓ\n\n"
    "Ez a modul a gépet köti össze egy USB-vel csatlakoztatott iPhone-nal, hogy "
    "a rajta lévő zenéket, fotókat, videókat és hangfelvételeket LEMENTHESD a "
    "gépre, illetve TÖRÖLHESD a telefonról. Minden a saját gépeid között marad; "
    "semmit nem továbbítunk sehová.\n\n"
    "AMI KELL HOZZÁ\n"
    "• A telefon USB-kábellel csatlakoztatva.\n"
    "• A telefonon egyszer meg kell nyomni a „Megbízom ebben a gépben” gombot.\n"
    "• A gépen a Microsoft Store-ból az „Apple Devices” alkalmazás (vagy az "
    "iTunes) – ez hozza magával azt a háttérszolgáltatást, amin keresztül "
    "Windows egyáltalán szóba tud állni egy iPhone-nal. Elég telepíteni és "
    "egyszer elindítani; utána nem kell megnyitni.\n\n"
    "LAPFÜLEK\n"
    "• Zenék: a telefonon lévő számok CÍMMEL és ELŐADÓVAL. A telefon a fájlokat "
    "értelmetlen néven tárolja, a nevet külön adatbázisban – a mentés ezt "
    "olvassa össze, és rendes néven, előadó/album mappákba írja ki.\n"
    "• Fotók és videók: a telefon kamera-mappája.\n"
    "• Alkalmazások fájljai: azoknak az alkalmazásoknak a megosztott mappája, "
    "amelyek ezt engedik (például a diktafonod felvételei). A gyári Hangjegyzetek "
    "alkalmazás zárt, abba az Apple senkit nem enged bele.\n\n"
    "KEZELÉS\n"
    "• Szóközzel pipálod ki a listaelemet, Ctrl+A jelöl ki mindent.\n"
    "• Alt+M: a kijelöltek mentése a gépre (mappát kérdez).\n"
    "• Alt+T: a kijelöltek törlése a telefonról (mindig rákérdez).\n"
    "• F5: a lista frissítése. F1: ez a súgó. Escape: bezárás.\n\n"
    "A TÖRLÉSRŐL\n"
    "A zene törlése a telefon zene-adatbázisába is beleír. Ezért a program "
    "MINDIG biztonsági mentést készít előtte, a módosítást másolaton végzi, "
    "ellenőrzi az eredményt, és ha bármi nem stimmel, MAGÁTÓL visszaállítja az "
    "eredeti állapotot. A mentések a felhasználói mappádban maradnak, hogy "
    "később is legyen mihez visszanyúlni.\n"
    "Fotó vagy videó törlésekor a fájl eltűnik, de a Fotók alkalmazás saját "
    "nyilvántartásában maradhat egy üres helye, amíg a telefon magától rendbe "
    "nem teszi.\n\n"
    "ZENE FELTÖLTÉSE A TELEFONRA\n"
    "A Zenék lap tetején. A program megkérdezi, HOVA kerüljön a zene – két út "
    "közül választhatsz:\n\n"
    "1. A GYÁRI ZENE ALKALMAZÁSBA. A szám előbb a gép Apple Music könyvtárába "
    "kerül, onnan pedig az Apple Devices viszi át a telefonra. Ez az igazi: a "
    "zene ott lesz, ahol keresed. Feltétel: legyen fent az Apple Music és az "
    "Apple Devices, a telefon csatlakozzon USB-n, és legyen FELOLDVA – ha az "
    "Apple Devices nem látja a telefont, semmi nem történik (a program ezt "
    "meg is mondja). FONTOS: ilyenkor a telefon zenéje a GÉPI könyvtárhoz "
    "igazodik, tehát ami a gépi Apple Music könyvtárban nincs benne, az "
    "lekerülhet a telefonról. A program ezt a művelet előtt megkérdezi.\n\n"
    "2. EGY LEJÁTSZÓ ALKALMAZÁSBA (például VLC). Egyszerűbb és megbízhatóbb, "
    "mert csak a mi dolgunk: a fájl az alkalmazás saját mappájába kerül, és "
    "onnan nem tűnhet el. Cserébe nem a gyári appban szól. Ha nincs ilyen "
    "alkalmazás a telefonon, tegyél fel egyet az App Store-ból (a VLC ingyenes "
    "és VoiceOverrel jól használható), indítsd el egyszer, majd itt Frissítés."
    "\n\n"
    "Amit NEM csinálunk: közvetlenül a telefon zene-adatbázisába írni. Azt a "
    "telefon saját szolgáltatása birtokolja, és a kívülről írt bejegyzést "
    "előbb-utóbb felülírja – megmértük, a szám egy idő után eltűnt. Ilyet nem "
    "építünk be, mert ami csak néha működik, az rosszabb a semminél."
)


def _mondd(main, szoveg):
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


def _hatterben(munka, kesz, hiba):
    def fut():
        try:
            e = munka()
        except Exception as ex:
            wx.CallAfter(hiba, ex)
        else:
            wx.CallAfter(kesz, e)
    threading.Thread(target=fut, daemon=True).start()


class _Lap(wx.Panel):
    """Egy lapfül: lista + a két művelet. A leszármazottak adják a tartalmat."""

    CIMKE = "Elemek"
    URES = "Nincs megjeleníthető elem."

    def __init__(self, szulo, frame):
        super().__init__(szulo)
        self.frame = frame
        self.tetelek = []
        self._elso_toltes = True      # az első betöltés indítja a következő lapot
        v = wx.BoxSizer(wx.VERTICAL)

        cim = wx.StaticText(self, label="&" + self.CIMKE + ":")
        v.Add(cim, 0, wx.LEFT | wx.TOP, 6)
        self.lista = wx.CheckListBox(self, choices=[])
        self.lista.SetName(self.CIMKE)
        self.lista.Bind(wx.EVT_LISTBOX, self._valtozott)
        self.lista.Bind(wx.EVT_CHECKLISTBOX, self._valtozott)
        self.lista.Bind(wx.EVT_CHAR_HOOK, self._billentyu)
        v.Add(self.lista, 1, wx.EXPAND | wx.ALL, 6)

        s = wx.BoxSizer(wx.HORIZONTAL)
        self.b_ment = wx.Button(self, label="💾 A kijelöltek &mentése a gépre")
        self.b_ment.Bind(wx.EVT_BUTTON, self._ment)
        s.Add(self.b_ment, 0, wx.RIGHT, 8)
        self.b_torol = wx.Button(self, label="🗑 A kijelöltek &törlése a telefonról")
        self.b_torol.Bind(wx.EVT_BUTTON, self._torol)
        s.Add(self.b_torol, 0, wx.RIGHT, 8)
        b_mind = wx.Button(self, label="Mi&ndet kijelöl")
        b_mind.Bind(wx.EVT_BUTTON, lambda e: self._mind(True))
        s.Add(b_mind, 0, wx.RIGHT, 8)
        b_semmi = wx.Button(self, label="Kijelölés t&örlése")
        b_semmi.Bind(wx.EVT_BUTTON, lambda e: self._mind(False))
        s.Add(b_semmi, 0, wx.RIGHT, 8)
        b_friss = wx.Button(self, label="&Frissítés (F5)")
        b_friss.Bind(wx.EVT_BUTTON, lambda e: self.frissit())
        s.Add(b_friss, 0)
        v.Add(s, 0, wx.ALL, 6)

        # ---- haladás: LÁTHATÓ sáv ÉS felolvasható szöveg ----
        self.sav = wx.Gauge(self, range=100)
        self.sav.SetName("Haladás")
        v.Add(self.sav, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        self.allapot = wx.StaticText(self, label="")
        self.allapot.SetName("Állapot")
        v.Add(self.allapot, 0, wx.EXPAND | wx.ALL, 6)

        hs = wx.BoxSizer(wx.HORIZONTAL)
        self.b_hol = wx.Button(self, label="&Hol tartunk? (Ctrl+H)")
        self.b_hol.Bind(wx.EVT_BUTTON, lambda e: self.hol_tartunk())
        self.b_hol.Enable(False)
        hs.Add(self.b_hol, 0, wx.RIGHT, 8)
        self.b_stop = wx.Button(self, label="⛔ Megsza&kítás")
        self.b_stop.Bind(wx.EVT_BUTTON, lambda e: self.megszakit())
        self.b_stop.Enable(False)
        hs.Add(self.b_stop, 0)
        v.Add(hs, 0, wx.LEFT | wx.BOTTOM, 6)
        self.SetSizer(v)

        self._munka = None          # a futó művelet állapota

    # ---- közös ----
    def _mond(self, szoveg):
        self.frame._mond(szoveg)

    def _allapot(self, szoveg, mondd=True):
        self.allapot.SetLabel(szoveg)
        if mondd:
            self._mond(szoveg)

    def _billentyu(self, e):
        if e.GetKeyCode() == ord("A") and e.ControlDown():
            self._mind(True)
            return
        if e.GetKeyCode() == ord("H") and e.ControlDown():
            self.hol_tartunk()
            return
        e.Skip()

    def _valtozott(self, e):
        e.Skip()
        n = len(self.lista.GetCheckedItems())
        self.b_ment.Enable(bool(n))
        self.b_torol.Enable(bool(n))

    def _mind(self, be):
        for i in range(self.lista.GetCount()):
            self.lista.Check(i, be)
        self._valtozott(wx.CommandEvent())
        self._mond("Minden elem kijelölve." if be else "A kijelölés törölve.")

    def kijeloltek(self):
        return [self.tetelek[i] for i in self.lista.GetCheckedItems()
                if i < len(self.tetelek)]

    def _feltolt(self, tetelek, sorok):
        self.tetelek = tetelek
        self.lista.Set(sorok)
        self.b_ment.Enable(False)
        self.b_torol.Enable(False)

    # ================================================= haladás-jelzés
    def munka_indul(self, cimke, darab, osszes_bajt=0):
        """Egy hosszú művelet kezdete: sáv, gombok, mérőóra."""
        self._munka = {"cimke": cimke, "i": 0, "n": darab, "nev": "",
                       "kesz_bajt": 0, "osszes_bajt": osszes_bajt,
                       "fajl_kesz": 0, "fajl_teljes": 0,
                       "kezdet": time.monotonic(), "utolso_mondas": 0.0,
                       "stop": False}
        self.sav.SetRange(max(1, darab))
        self.sav.SetValue(0)
        self.b_hol.Enable(True)
        self.b_stop.Enable(True)
        self._mond("%s indul: %d elem." % (cimke, darab))

    def munka_vege(self, zaro_szoveg):
        self._munka = None
        self.sav.SetValue(self.sav.GetRange())
        self.b_hol.Enable(False)
        self.b_stop.Enable(False)
        self._allapot(zaro_szoveg)

    def megszakit(self):
        if self._munka:
            self._munka["stop"] = True
            self._allapot("Megszakítás… a most futó fájl végén megállok.")

    def _stop_e(self):
        return bool(self._munka and self._munka["stop"])

    def hol_tartunk(self):
        """A vak felhasználó legfontosabb gombja: BÁRMIKOR megkérdezhető, hol
        tart a művelet – nem kell várni a következő bemondásra."""
        m = self._munka
        if not m:
            self._mond(self.allapot.GetLabel() or "Most nem fut művelet.")
            return
        self._mond(self._allas_szoveg(m, reszletes=True))

    @staticmethod
    def _hatralevo(m):
        eltelt = time.monotonic() - m["kezdet"]
        kesz = m["kesz_bajt"] + m["fajl_kesz"]
        if m["osszes_bajt"] and kesz > 0 and eltelt > 2:
            hatra = (m["osszes_bajt"] - kesz) * eltelt / kesz
        elif m["i"] > 0 and eltelt > 2:
            hatra = (m["n"] - m["i"]) * eltelt / m["i"]
        else:
            return "", 0.0
        if hatra < 45:
            return "kevesebb mint egy perc van hátra", hatra
        if hatra < 5400:
            return "körülbelül %d perc van hátra" % round(hatra / 60), hatra
        return "körülbelül %d óra van hátra" % round(hatra / 3600), hatra

    def _allas_szoveg(self, m, reszletes=False):
        reszek = ["%d / %d kész" % (m["i"], m["n"])]
        if m["fajl_teljes"] > 4 << 20 and m["fajl_kesz"] < m["fajl_teljes"]:
            szazalek = round(100 * m["fajl_kesz"] / max(1, m["fajl_teljes"]))
            reszek.append("a mostani fájl %d százaléknál tart" % szazalek)
        hatra, _mp = self._hatralevo(m)
        if hatra:
            reszek.append(hatra)
        if reszletes and m["nev"]:
            reszek.append("most: " + m["nev"])
        return ", ".join(reszek) + "."

    def _halad_jelzo(self, cimke):
        """Elemenkénti haladás. A bemondás IDŐALAPÚ (nagyjából félpercenként),
        nem elemenként: 691 szám mellett a darabonkénti beszéd elviselhetetlen
        lenne, a néma várakozás viszont azt az érzetet kelti, hogy lefagyott."""
        def halad(i, n, nev, ok):
            m = self._munka
            if m is None:
                return
            m["i"], m["nev"] = i, nev
            m["kesz_bajt"] += m["fajl_teljes"]
            m["fajl_kesz"] = m["fajl_teljes"] = 0
            wx.CallAfter(self._halad_kiir)
            most = time.monotonic()
            if i == n or most - m["utolso_mondas"] >= 30:
                m["utolso_mondas"] = most
                wx.CallAfter(self._mond, self._allas_szoveg(m))
        return halad

    def _bajt_jelzo(self):
        """A FÁJLON BELÜLI haladás – egy 800 MB-os videónál ez a különbség a
        „dolgozik” és a „lefagyott” érzet között."""
        def bajt(kesz, teljes):
            m = self._munka
            if m is None:
                return
            m["fajl_kesz"], m["fajl_teljes"] = kesz, teljes
            if teljes > 4 << 20:
                wx.CallAfter(self._halad_kiir)
        return bajt

    def _halad_kiir(self):
        m = self._munka
        if m is None or self.frame._closing:
            return
        self.sav.SetValue(min(m["i"], self.sav.GetRange()))
        sor = "%s: %d / %d" % (m["cimke"], m["i"], m["n"])
        if m["fajl_teljes"] > 4 << 20:
            sor += "  (a mostani fájl: %s / %s)" % (
                C.meret_szoveg(m["fajl_kesz"]), C.meret_szoveg(m["fajl_teljes"]))
        hatra, _mp = self._hatralevo(m)
        if hatra:
            sor += "  –  " + hatra
        if m["nev"]:
            sor += "  –  " + m["nev"]
        self.allapot.SetLabel(sor)

    # ---- a leszármazott tölti meg ----
    def frissit(self):
        raise NotImplementedError

    def _ment(self, e):
        raise NotImplementedError

    def _torol(self, e):
        raise NotImplementedError


class ZeneLap(_Lap):
    CIMKE = "Zenék a telefonon"

    def __init__(self, szulo, frame):
        super().__init__(szulo, frame)
        # A feltöltés a lista FÖLÉ kerül: nem a kijelöléstől függ (fájlokat
        # választasz a gépről), ezért nem is a többi gomb közé való.
        v = self.GetSizer()
        b = wx.Button(self, label="⬆ Zene &feltöltése a telefonra…")
        b.Bind(wx.EVT_BUTTON, self._zene_feltoltes)
        v.Insert(0, b, 0, wx.ALL, 6)
        self.Layout()

    def _zene_feltoltes(self, e):
        """Zene FEL a telefonra – KÉT út közül választhatsz.

        1. A GYÁRI Zene alkalmazásba, az Apple saját programjain keresztül
           (Apple Music könyvtár → Apple Devices szinkron). Ez az igazi: a szám
           ott lesz, ahol keresed. Cserébe több minden kell hozzá, és az Apple
           felületének változásaira érzékeny.
        2. Egy LEJÁTSZÓ alkalmazás saját mappájába. Egyszerűbb és
           megbízhatóbb, de nem a gyári appban szól.

        Közvetlenül a telefon zene-adatbázisába írni NEM lehet: azt a telefon
        szolgáltatása birtokolja, és a kívülről írt bejegyzést felülírja –
        élesben megmértük, ezért nem is kínáljuk fel.
        """
        from . import applemusic as AM

        utak_appok = getattr(self.frame.app, "appok", [])
        valaszthato = []
        if AM.elerheto():
            valaszthato.append(("apple",
                                "A gyári Zene alkalmazásba (Apple Musicon át)"))
        for a in utak_appok:
            valaszthato.append(("app:" + a["bundle"],
                                "A(z) %s alkalmazásba" % a["nev"]))
        if not valaszthato:
            wx.MessageBox(
                "Nincs hova feltöltenem.\n\n"
                "Vagy telepítsd a Microsoft Store-ból az Apple Music "
                "alkalmazást (akkor a gyári Zene appba tudok küldeni), vagy "
                "tegyél fel a telefonra egy lejátszót – a VLC ingyenes és "
                "VoiceOverrel jól használható.",
                "Nincs hova feltölteni", wx.OK | wx.ICON_INFORMATION, self)
            self._mond("Nincs hova feltöltenem. A súgó megmondja, mit tegyél.")
            return

        with wx.SingleChoiceDialog(self, "Hova kerüljön a zene?",
                                   "Feltöltés a telefonra",
                                   [nev for _k, nev in valaszthato]) as d:
            if d.ShowModal() != wx.ID_OK:
                self._mond("A feltöltés megszakítva.")
                return
            mod, mod_nev = valaszthato[d.GetSelection()]

        with wx.FileDialog(
                self, "Melyik zenéket küldjem a telefonra?",
                wildcard="Hangfájlok|*.mp3;*.m4a;*.m4b;*.aac;*.wav|"
                         "Minden fájl|*.*",
                style=wx.FD_OPEN | wx.FD_MULTIPLE | wx.FD_FILE_MUST_EXIST) as d:
            if d.ShowModal() != wx.ID_OK:
                self._mond("A feltöltés megszakítva.")
                return
            utak = d.GetPaths()
        if not utak:
            return

        if mod == "apple" and not self._apple_figyelmeztetes(len(utak)):
            return

        import os as _os
        self.munka_indul("Feltöltés", len(utak),
                         sum(_os.path.getsize(u) for u in utak
                             if _os.path.isfile(u)))
        halad = self._halad_jelzo("Feltöltés")
        if mod == "apple":
            _hatterben(lambda: AM.teljes_lanc(utak, halad, self._stop_e),
                       self._apple_kesz, self.frame._hiba)
        else:
            bundle = mod.split(":", 1)[1]
            _hatterben(lambda: self.frame.telefon().app_feltolt(
                           bundle, utak, halad, self._bajt_jelzo(),
                           self._stop_e),
                       lambda r: self._feltolt_kesz(r, mod_nev),
                       self.frame._hiba)

    def _apple_figyelmeztetes(self, darab) -> bool:
        """A gyári úthoz a telefon zenéje a GÉPI könyvtárhoz igazodik – ezt a
        felhasználónak értenie kell, mielőtt igent mond."""
        valasz = wx.MessageBox(
            "%d számot küldök a telefon gyári Zene alkalmazásába.\n\n"
            "Ez az Apple saját útján megy: a szám előbb a gép Apple Music "
            "könyvtárába kerül, onnan pedig az Apple Devices viszi át a "
            "telefonra.\n\n"
            "FONTOS: ilyenkor a telefon zenéje a GÉPI könyvtárhoz igazodik. "
            "Ami a gépi Apple Music könyvtárban nincs benne, az lekerülhet a "
            "telefonról.\n\n"
            "Feltétel: a telefon USB-n csatlakozzon és legyen feloldva. "
            "Folytassam?" % darab,
            "Feltöltés a gyári Zene alkalmazásba",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self)
        if valasz != wx.YES:
            self._mond("A feltöltés megszakítva.")
            return False
        return True

    def _apple_kesz(self, r):
        if self.frame._closing:
            return
        sz = "Kész. %d szám a gép Apple Music könyvtárába került." % r["behozva"]
        if r["hibak"]:
            sz += " %d nem sikerült." % len(r["hibak"])
        if r["szinkron"] == "elindult":
            sz += (" A telefonra másolás elindult – a gyári Zene "
                   "alkalmazásban fog megjelenni.")
        elif r["szinkron"]:
            sz += " A telefonra másolás viszont nem indult el: " + r["szinkron"]
        self.munka_vege(sz)
        if r["hibak"]:
            wx.MessageBox("\n".join(r["hibak"][:6]), "Feltöltés",
                          wx.OK | wx.ICON_WARNING, self)

    def _feltolt_kesz(self, r, app_nev=""):
        if self.frame._closing:
            return
        ok, hibak = r
        sz = "Kész. %d fájl a(z) %s alkalmazásba került." % (ok, app_nev)
        if hibak:
            sz += " %d nem sikerült." % len(hibak)
        self.munka_vege(sz)
        if ok:
            self._mond("Kész. Nyisd meg a telefonon a(z) %s alkalmazást – ott "
                       "megtalálod a számokat." % app_nev)

    def frissit(self):
        self._allapot("A zenék beolvasása a telefonról…")
        _hatterben(lambda: self.frame.telefon().zenek(), self._kesz,
                   self.frame._hiba)

    def _kesz(self, z):
        if self.frame._closing:
            return
        sorok = []
        for x in z:
            reszek = [x["cim"]]
            if x["eloado"]:
                reszek.append(x["eloado"])
            if C.ido_szoveg(x["mp"]):
                reszek.append(C.ido_szoveg(x["mp"]))
            reszek.append(C.meret_szoveg(x["meret"]))
            sorok.append(" – ".join(reszek))
        self._feltolt(z, sorok)
        self._allapot("%d szám a telefonon." % len(z))
        if self._elso_toltes:
            self._elso_toltes = False
            wx.CallAfter(self.frame.kep.frissit)

    def _ment(self, e):
        t = self.kijeloltek()
        if not t:
            return
        with wx.DirDialog(self, "Hova mentsem a zenéket?",
                          style=wx.DD_DEFAULT_STYLE) as d:
            if d.ShowModal() != wx.ID_OK:
                self._mond("A mentés megszakítva.")
                return
            cel = d.GetPath()
        self.munka_indul("Mentés", len(t), sum(x["meret"] for x in t))
        halad, bajt = self._halad_jelzo("Mentés"), self._bajt_jelzo()
        _hatterben(
            lambda: self.frame.telefon().zene_ment(
                t, cel, True, halad, bajt, self._stop_e),
            lambda r: self._ment_kesz(r, cel), self.frame._hiba)

    def _ment_kesz(self, r, cel):
        if self.frame._closing:
            return
        ok, hibak = r
        sz = "Kész. %d szám lementve ide: %s." % (ok, cel)
        if hibak:
            sz += " %d nem sikerült." % len(hibak)
        self.munka_vege(sz)

    def _torol(self, e):
        t = self.kijeloltek()
        if not t:
            return
        uzenet = (
            "Biztosan törölsz %d számot a telefonról?\n\n"
            "A számok VÉGLEG eltűnnek a telefonról (a gépen lévő másolatokhoz "
            "ennek semmi köze).\n\n"
            "A program a művelet előtt biztonsági mentést készít a telefon "
            "zene-adatbázisáról, és ha bármi nem sikerül, magától visszaállítja "
            "az eredeti állapotot." % len(t))
        if wx.MessageBox(uzenet, "Törlés a telefonról",
                         wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
                         self) != wx.YES:
            self._mond("A törlés megszakítva.")
            return
        self.munka_indul("Törlés", len(t))
        halad = self._halad_jelzo("Törlés")
        _hatterben(lambda: self.frame.telefon().zene_torol(t, halad),
                   self._torol_kesz, self.frame._hiba)

    def _torol_kesz(self, r):
        if self.frame._closing:
            return
        db, mentes = r
        self.munka_vege("Kész. %d szám törölve. A biztonsági mentés itt van: %s"
                        % (db, mentes))
        self.frissit()


class KepLap(_Lap):
    CIMKE = "Fotók és videók"

    def frissit(self):
        self._allapot("A fotók és videók beolvasása…")
        _hatterben(lambda: self.frame.telefon().kepek(), self._kesz,
                   self.frame._hiba)

    def _kesz(self, k):
        if self.frame._closing:
            return
        sorok = ["%s – %s – %s" % ("videó" if x["video"] else "fotó",
                                   x["nev"], C.meret_szoveg(x["meret"]))
                 for x in k]
        self._feltolt(k, sorok)
        video = sum(1 for x in k if x["video"])
        self._allapot("%d elem: %d fotó és %d videó."
                      % (len(k), len(k) - video, video), mondd=False)
        if self._elso_toltes:
            self._elso_toltes = False
            wx.CallAfter(self.frame.app.appokat_tolt)

    def _ment(self, e):
        t = self.kijeloltek()
        if not t:
            return
        with wx.DirDialog(self, "Hova mentsem a fotókat és videókat?") as d:
            if d.ShowModal() != wx.ID_OK:
                self._mond("A mentés megszakítva.")
                return
            cel = d.GetPath()
        osszes = sum(x["meret"] for x in t)
        self.munka_indul("Mentés", len(t), osszes)
        halad, bajt = self._halad_jelzo("Mentés"), self._bajt_jelzo()
        _hatterben(lambda: self.frame.telefon().kep_ment(
                       t, cel, halad, bajt, self._stop_e),
                   lambda r: self._ment_kesz(r, cel), self.frame._hiba)

    def _ment_kesz(self, r, cel):
        if self.frame._closing:
            return
        ok, hibak = r
        sz = "Kész. %d elem lementve ide: %s." % (ok, cel)
        if hibak:
            sz += " %d nem sikerült." % len(hibak)
        self.munka_vege(sz)

    def _torol(self, e):
        t = self.kijeloltek()
        if not t:
            return
        if wx.MessageBox(
                "Biztosan törölsz %d elemet a telefonról?\n\n"
                "A fájlok VÉGLEG eltűnnek. Ha nem mentetted még le őket a "
                "gépre, előbb tedd meg.\n\n"
                "Megjegyzés: a Fotók alkalmazás saját nyilvántartásában "
                "maradhat egy üres helyük, amíg a telefon magától rendbe nem "
                "teszi." % len(t),
                "Törlés a telefonról", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
                self) != wx.YES:
            self._mond("A törlés megszakítva.")
            return
        self.munka_indul("Törlés", len(t))
        halad = self._halad_jelzo("Törlés")
        _hatterben(lambda: self.frame.telefon().kep_torol(t, halad),
                   self._torol_kesz, self.frame._hiba)

    def _torol_kesz(self, r):
        if self.frame._closing:
            return
        ok, _hibak = r
        self.munka_vege("Kész. %d elem törölve a telefonról." % ok)
        self.frissit()


class AppLap(_Lap):
    CIMKE = "Az alkalmazás fájljai"

    def __init__(self, szulo, frame):
        super().__init__(szulo, frame)
        # az alkalmazás-választó a lista FÖLÉ kerül
        v = self.GetSizer()
        sor = wx.BoxSizer(wx.HORIZONTAL)
        st = wx.StaticText(self, label="&Alkalmazás:")
        sor.Add(st, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.valaszto = wx.Choice(self, choices=[])
        self.valaszto.SetName("Alkalmazás")
        self.valaszto.Bind(wx.EVT_CHOICE, lambda e: self.frissit())
        sor.Add(self.valaszto, 1)
        v.Insert(0, sor, 0, wx.EXPAND | wx.ALL, 6)
        self.appok = []
        self.Layout()

    def appokat_tolt(self):
        self._allapot("Az alkalmazások beolvasása…", mondd=False)
        _hatterben(lambda: self.frame.telefon().alkalmazasok(),
                   self._appok_kesz, self.frame._hiba)

    def _appok_kesz(self, appok):
        if self.frame._closing:
            return
        self.appok = appok
        self.valaszto.Set([a["nev"] for a in appok])
        if appok:
            self.valaszto.SetSelection(0)
            self.frissit()
        else:
            self._allapot("Egyetlen alkalmazás sem osztja meg a fájljait.")

    def frissit(self):
        i = self.valaszto.GetSelection()
        if i < 0 or i >= len(self.appok):
            return
        bundle = self.appok[i]["bundle"]
        self._allapot("A fájlok beolvasása…", mondd=False)
        _hatterben(lambda: self.frame.telefon().app_fajlok(bundle),
                   self._kesz, self.frame._hiba)

    def _kesz(self, f):
        if self.frame._closing:
            return
        self._feltolt(f, ["%s – %s" % (x["nev"], C.meret_szoveg(x["meret"]))
                          for x in f])
        self._allapot("%d fájl." % len(f) if f
                      else "Ebben az alkalmazásban nincs megosztott fájl.")

    def _bundle(self):
        i = self.valaszto.GetSelection()
        return self.appok[i]["bundle"] if 0 <= i < len(self.appok) else ""

    def _ment(self, e):
        t = self.kijeloltek()
        if not t:
            return
        with wx.DirDialog(self, "Hova mentsem a fájlokat?") as d:
            if d.ShowModal() != wx.ID_OK:
                self._mond("A mentés megszakítva.")
                return
            cel = d.GetPath()
        self.munka_indul("Mentés", len(t), sum(x["meret"] for x in t))
        halad, bajt = self._halad_jelzo("Mentés"), self._bajt_jelzo()
        b = self._bundle()
        _hatterben(lambda: self.frame.telefon().app_ment(
                       b, t, cel, halad, bajt, self._stop_e),
                   lambda r: self._ment_kesz(r, cel), self.frame._hiba)

    def _ment_kesz(self, r, cel):
        if self.frame._closing:
            return
        ok, hibak = r
        self.munka_vege("Kész. %d fájl lementve ide: %s.%s"
                        % (ok, cel,
                           " %d nem sikerült." % len(hibak) if hibak else ""))

    def _torol(self, e):
        t = self.kijeloltek()
        if not t:
            return
        if wx.MessageBox("Biztosan törölsz %d fájlt a telefonról? VÉGLEG "
                         "eltűnnek." % len(t), "Törlés a telefonról",
                         wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
                         self) != wx.YES:
            self._mond("A törlés megszakítva.")
            return
        self.munka_indul("Törlés", len(t))
        halad = self._halad_jelzo("Törlés")
        b = self._bundle()
        _hatterben(lambda: self.frame.telefon().app_torol(b, t, halad),
                   self._torol_kesz, self.frame._hiba)

    def _torol_kesz(self, r):
        if self.frame._closing:
            return
        ok, _hibak = r
        self.munka_vege("Kész. %d fájl törölve." % ok)
        self.frissit()


class IPhoneFrame(wx.Frame):
    """Az iPhone modul főablaka."""

    def __init__(self, parent=None, main=None):
        super().__init__(parent, title="iPhone – zene, fotó, videó",
                         size=(940, 660))
        self.main = main
        self._closing = False
        self._telefon = None

        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        self.fejlec = wx.StaticText(p, label="Nincs csatlakoztatott telefon.")
        self.fejlec.SetName("A telefon adatai")
        v.Add(self.fejlec, 0, wx.ALL, 8)

        self.fulek = wx.Notebook(p)
        self.zene = ZeneLap(self.fulek, self)
        self.kep = KepLap(self.fulek, self)
        self.app = AppLap(self.fulek, self)
        self.fulek.AddPage(self.zene, "&Zenék")
        self.fulek.AddPage(self.kep, "&Fotók és videók")
        self.fulek.AddPage(self.app, "&Alkalmazások fájljai")
        v.Add(self.fulek, 1, wx.EXPAND | wx.ALL, 6)

        also = wx.BoxSizer(wx.HORIZONTAL)
        # A gomb felirata az ÁLLAPOTOT mutatja: csatlakozva már nincs mit
        # „csatlakozni”, viszont újracsatlakozásra szükség lehet (kihúzott
        # kábel után). A felhasználó jelezte, hogy a régi, örökké ugyanolyan
        # felirat félrevezető volt.
        self.b_csat = wx.Button(p, label="🔌 &Csatlakozás a telefonhoz")
        self.b_csat.Bind(wx.EVT_BUTTON, lambda e: self._csatlakozas())
        also.Add(self.b_csat, 0, wx.RIGHT, 8)
        b_sugo = wx.Button(p, label="&Súgó (F1)")
        b_sugo.Bind(wx.EVT_BUTTON, lambda e: self._sugo())
        also.Add(b_sugo, 0)
        v.Add(also, 0, wx.ALL, 8)
        p.SetSizer(v)

        self.Bind(wx.EVT_CLOSE, self._bezar)
        self.Bind(wx.EVT_CHAR_HOOK, self._billentyu)
        wx.CallAfter(self._csatlakozas)

    # ---- alap ----
    def _mond(self, szoveg):
        _mondd(self.main, szoveg)

    def _billentyu(self, e):
        k = e.GetKeyCode()
        if k == wx.WXK_ESCAPE:
            self.Close()
        elif k == wx.WXK_F1:
            self._sugo()
        elif k == wx.WXK_F5:
            lap = self.fulek.GetCurrentPage()
            if hasattr(lap, "frissit"):
                lap.frissit()
        else:
            e.Skip()

    def _sugo(self):
        d = wx.Dialog(self, title="iPhone – súgó", size=(760, 600))
        pp = wx.Panel(d)
        vv = wx.BoxSizer(wx.VERTICAL)
        t = wx.TextCtrl(pp, value=_SUGO,
                        style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        t.SetName("Súgó")
        vv.Add(t, 1, wx.EXPAND | wx.ALL, 8)
        b = wx.Button(pp, wx.ID_CLOSE, label="&Bezárás")
        b.Bind(wx.EVT_BUTTON, lambda e: d.EndModal(wx.ID_CLOSE))
        vv.Add(b, 0, wx.ALL, 8)
        pp.SetSizer(vv)
        wx.CallAfter(t.SetFocus)
        d.ShowModal()
        d.Destroy()

    def _bezar(self, e):
        self._closing = True
        if self._telefon is not None:
            try:
                self._telefon.bezar()
            except Exception:
                pass
            self._telefon = None
        e.Skip()

    def _hiba(self, ex):
        if self._closing:
            return
        naplo = self._naploz(ex)
        # a kapcsolat elszakadhat (kihúzták a kábelt) – legközelebb újranyitjuk
        self._telefon = None
        self.b_csat.SetLabel("🔌 Ú&jracsatlakozás")
        self.b_csat.Enable(True)
        for lap in (self.zene, self.kep, self.app):
            if lap._munka:
                lap.munka_vege("A művelet megszakadt egy hiba miatt.")
        szoveg = self._ertheto(ex)
        self._mond(szoveg)
        wx.MessageBox(szoveg + "\n\nA részletes hibanapló: " + naplo,
                      "iPhone", wx.OK | wx.ICON_ERROR, self)

    @staticmethod
    def _ertheto(ex) -> str:
        """A nyers hálózati hibaüzenet a felhasználónak semmit nem mond meg –
        arról viszont kell tudnia, MIT tegyen."""
        sz = str(ex)
        if "WRONG_VERSION_NUMBER" in sz or "SSL" in sz.upper():
            return ("Megszakadt a kapcsolat a telefonnal. Ez akkor fordul elő, "
                    "ha a kábel meglazult, vagy a telefon lezárta a kapcsolatot. "
                    "Nyomd meg az Újracsatlakozás gombot; ha nem megy, húzd ki "
                    "és dugd vissza a kábelt.")
        if "megszakadt" in sz or "Broken pipe" in sz or "10054" in sz:
            return ("Megszakadt a kapcsolat a telefonnal. Ellenőrizd a kábelt, "
                    "majd nyomd meg az Újracsatlakozás gombot.")
        return sz

    def _naploz(self, ex) -> str:
        """A teljes hibanyom fájlba – enélkül egy ilyen hiba okát utólag nem
        lehet megtalálni."""
        import traceback
        try:
            from superdl import store
            alap = str(store.CONFIG_DIR)
        except Exception:
            alap = os.path.join(os.path.expanduser("~"), ".superdl")
        try:
            os.makedirs(alap, exist_ok=True)
            ut = os.path.join(alap, "iphone_hiba.log")
            with open(ut, "a", encoding="utf-8") as f:
                f.write("\n" + "=" * 60 + "\n")
                f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
                f.write("".join(traceback.format_exception(
                    type(ex), ex, ex.__traceback__)))
            return ut
        except Exception:
            return "(a naplót nem sikerült megírni)"

    # ---- telefon ----
    def telefon(self) -> C.Telefon:
        """A megnyitott kapcsolat (szükség esetén újranyitja)."""
        if self._telefon is None:
            self._telefon = C.Telefon()
        return self._telefon

    def _csatlakozas(self):
        if self._closing:
            return
        self.fejlec.SetLabel("Csatlakozás…")
        self.b_csat.SetLabel("🔌 Csatlakozás &folyamatban…")
        self.b_csat.Enable(False)
        _hatterben(self._csat_munka, self._csat_kesz, self._hiba)

    def _csat_munka(self):
        t = self.telefon()
        return t.nev, t.ios, t.modell

    def _csat_kesz(self, adat):
        if self._closing:
            return
        nev, ios, _modell = adat
        self.fejlec.SetLabel("Csatlakozva: %s (iOS %s)" % (nev, ios))
        self.b_csat.SetLabel("🔌 Ú&jracsatlakozás")
        self.b_csat.Enable(True)
        self._mond("Csatlakozva: %s, iOS %s. Három lapfül van: zenék, fotók és "
                   "videók, alkalmazások fájljai. F1 a súgó." % (nev, ios))
        # A három lap EGYMÁS UTÁN tölt, nem egyszerre: egy kapcsolat van a
        # telefonnal, és a párhuzamos kérések összeakadnának rajta.
        self.zene.frissit()
