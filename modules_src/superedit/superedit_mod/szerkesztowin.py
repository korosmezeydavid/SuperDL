# -*- coding: utf-8 -*-
"""Super Edit — szövegszerkesztő, amiben a formázás HALLHATÓ.

A menü teljes: minden művelet megtalálható benne, a gyorsbillentyűjével
együtt. Aki nem tudja fejből a billentyűket, végignyilazza a menüt; aki
tudja, nem nyúl hozzá.
"""

import os

import wx

from . import aiszoveg as AI
from . import bemondas as BE
from . import forditas as FO
from . import formatum as FM
from . import tisztitas as TI

BETUMERETEK = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 40, 48]
STILUSOK = ["Normál", "Címsor 1", "Címsor 2", "Címsor 3"]

SUGO = """SUPER EDIT — SZÖVEGSZERKESZTŐ

MIRE VALÓ
Formázott szöveg írása és szerkesztése úgy, hogy a FORMÁZÁS HALLHATÓ.

KÉT ÚT MINDEN MŰVELETHEZ
  Alt ................ a felső menüsor: Fájl, Szerkesztés, Formázás,
                       Tájékozódás, AI, Beállítások. Alt+F a Fájl, és így
                       tovább; a menüben minden művelet megtalálható.
  Alkalmazások gomb .. helyi menü a szerkesztőben, a leggyakoribb
  vagy Shift+F10       műveletekkel, mindegyik mellett a gyorsbillentyűjével.

Egy látó ember a félkövért látja. Itt a program megmondja. Ez a különbség a
Jegyzettömbhöz és a legtöbb szerkesztőhöz képest.

FÁJLOK
Írható és olvasható: Word (.docx – ez az alapértelmezett), szövegfájl (.txt),
weblap (.html), Markdown (.md). Csak olvasható: PDF és EPUB – ezekbe nem
tudunk rendesen visszaírni, ezért a mentés .docx-et ajánl helyettük. PDF-be
exportálni viszont lehet.

A megnyitáskor a program megmondja, ha a dokumentumban olyasmi van (táblázat,
kép), amit nem tud megtartani.

BEILLESZTETT SZÖVEG MEGTISZTÍTÁSA
  Ctrl+Shift+T ....... okos tisztítás. Weboldalról bemásolt szövegből kiszedi
                       a webcímeket, a HTML-maradványt és a navigációs
                       sorokat („következő fejezet", „vissza a tetejére").
                       ELŐBB MEGSZÁMOLJA, hány helyen változtatna, és csak
                       utána kérdez. A Ctrl+Z egy lépésben visszavon.
  Ctrl+H ............. csere mindenhol, a találatok számával, megerősítéssel.

FEJEZETEK ÉS A HANGOSKÖNYV
  Ctrl+Shift+J ....... fejezetjelölő beszúrása (adhatsz neki címet is).
                       A hangoskönyv-készítő ezek mentén tud FEJEZETENKÉNT
                       darabolni, nem percenként. A jelölő sima szöveg, tehát
                       a .txt fájlban is megmarad.
  Szerkesztés menü ... fejezetek felsorolása, Enterrel odaugrik.

FORDÍTÁS
  Ctrl+Shift+R ....... a TELJES dokumentum fordítása. Kiválasztod a forrás- és
                       a célnyelvet, majd a fordítót:
                       • AI — jobb minőség, de a szöveg elhagyja a gépet;
                       • helyi gépi fordító — a szöveg a gépen marad.
                       A szöveg 3500 karakteres darabokban megy, bekezdés-
                       határon, és a végén összeáll. Escape megállítja.
                       ⚠️ A FORDÍTÁS ÚJ FÁJLBA KERÜL az eredeti mellé
                       (például konyv-en.docx), az eredetihez nem nyúlunk.
                       Így fordíthatsz oda-vissza anélkül, hogy bármit
                       elveszítenél.

A FORMÁZÁS BEMONDÁSA
  Ctrl+Shift+I ....... mi a formázás itt? (betűtípus, méret, stílus, igazítás)
  automatikusan ...... amikor formázott részbe lépsz vagy kilépsz belőle,
                       röviden szól: „félkövér", „normál".
                       Ez a Beállítások menüben kikapcsolható.

FORMÁZÁS
  Ctrl+B / I / U ..... félkövér, dőlt, aláhúzott
  Ctrl+L / E / R / J . balra, középre, jobbra, sorkizárt
  Ctrl+Shift+> és < .. nagyobb és kisebb betű
  Ctrl+0 / 1 / 2 / 3 . normál szöveg, illetve címsor 1, 2, 3
  Ctrl+Shift+C / V ... formázás másolása és beillesztése

TÁJÉKOZÓDÁS
  Ctrl+Shift+D ....... dokumentum-térkép: a címsorok listája, Enterrel odaugrik
  Ctrl+Shift+K ....... mennyi van? (szó, karakter, bekezdés, becsült oldal)
  Ctrl+Shift+H ....... hol vagyok? (sor, bekezdés)
  Ctrl+F / H ......... keresés, csere
  Ctrl+Shift+F ....... felolvasás a kurzortól, Escape megállítja

AI (a kijelölésre, vagy ha nincs kijelölés, az egészre)
  Ctrl+Shift+A ....... AI-funkciók listája
A javaslat MINDIG külön ablakban jelenik meg, felolvasva. Te döntesz:
elfogadod, pontosítod, újra kéred, vagy eldobod. A szövegedhez addig hozzá
sem nyúl.

FÁJLTÁRSÍTÁS
Beállítások → Fájltársítások: itt választod ki, milyen fájlokra kattintva
nyíljon a Super Edit. Kiterjesztésenként külön, bármikor visszavonható.

AMIT NEM TUD
Táblázat, kép, lábjegyzet, tartalomjegyzék, változáskövetés, hasábok.
Ez nem Word-pótlék.
"""


def _mondd(main, szoveg):
    """BEMONDÁS – a KÖTELEZŐ sorrendben: ELŐBB a képernyőolvasó, és CSAK utána
    a némítás-vizsgálat meg a beépített hang."""
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


class SuperEditFrame(wx.Frame):

    def __init__(self, main, open_path: str = ""):
        super().__init__(main, title="Super Edit", size=(1000, 700))
        self.main = main
        self._closing = False
        self._ut = ""
        self._piszkos = False
        self._csak_olvas = False
        self._valtas_bemondas = True
        self._utolso_jegyek = []
        self._masolt_formatum = None
        self._keresett = ""
        # ⚠️ Van-e egyáltalán formázás a dokumentumban? Amíg nincs, mentéskor
        # EGYETLEN stílus-lekérdezést sem csinálunk – lásd `_bekezdesek`.
        self._formazva = False
        self._forditas_fut = False
        self._forditas_megall = False

        self._build()
        self.Bind(wx.EVT_CLOSE, self._on_close)
        if open_path:
            wx.CallAfter(self.open_file, open_path)
        else:
            self._cim_frissit()
            wx.CallAfter(self._allapot,
                         "Super Edit. Új dokumentum. A menüben minden "
                         "művelet megtalálható, a súgó az F1.")

    # ---- felépítés ----------------------------------------------------

    def _jegy(self):
        """Üres formázás-jegy. EGY helyen, hogy a vezérlő típusa egy helyen
        legyen kimondva."""
        return wx.TextAttr()

    def _jegy_alap(self):
        """NORMÁL formázás-jegy — minden tulajdonság KIMONDVA.

        ⚠️ Az ÜRES jegy nem azt jelenti, hogy „normál", hanem azt, hogy „ne
        változtass". A natív mezőn ezért az üres jeggyel való visszaállítás
        után a félkövér TOVÁBB ÉLT, és az utána gépelt szöveg is vastag lett.
        Élő próbán bukott ki, nem elméletben: a „ VASTAG utana" egyben jött
        vissza félkövérként. Ahol normálra akarunk állni, ott EZT kell hívni.
        """
        a = wx.TextAttr()
        a.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL,
                          wx.FONTWEIGHT_NORMAL, False))
        return a

    def _build(self):
        # ⚠️ NATÍV szövegmező (TE_RICH2), NEM wx.richtext.RichTextCtrl.
        # A RichTextCtrl saját rajzolású vezérlő: nincs mögötte Windows-os
        # szöveg-felület, ezért a képernyőolvasó ÜRESNEK látja — fel-le
        # nyilazva nem mond semmit. Egy szövegszerkesztőnél ez nem apró
        # kényelmetlenség, hanem használhatatlanság. A TE_RICH2 a Windows
        # saját RichEdit vezérlője (ezt használja a WordPad is): az NVDA
        # olvassa a sorokat, a betűket, és MAGÁTÓL bemondja a formázást is.
        # Cserébe lemondunk a RichTextCtrl extráiról (beágyazott kép,
        # felsorolás) — azokat a modul úgysem ígéri.
        self.szerk = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_RICH2 | wx.TE_NOHIDESEL |
            wx.TE_PROCESS_TAB | wx.HSCROLL)
        self.szerk.SetName("Szöveg")
        # ⚠️ NINCS saját wx.Accessible a szerkesztőmezőn. Egy játék bemeneti
        # mezőjénél az volt a cél, hogy a mező NEVE legyen a kérdés — ott jó.
        # Egy SZÖVEGSZERKESZTŐN viszont a saját név átveszi a vezérlő
        # akadálymentes szerepét, és a képernyőolvasó ELHALLGAT gépelés
        # közben: nem mondja a betűket és a sorokat. Egy szerkesztőnél éppen
        # ez a legfontosabb visszajelzés, tehát a nevet a SetName adja, a
        # szöveg-felület pedig marad az eredeti.
        self.szerk.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT,
                                   wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        self.szerk.Bind(wx.EVT_KEY_UP, self._on_kurzor)
        self.szerk.Bind(wx.EVT_LEFT_UP, self._on_kurzor)
        self.szerk.Bind(wx.EVT_TEXT, self._on_valtozott)
        self.szerk.Bind(wx.EVT_CONTEXT_MENU, self._helyi_menu)
        self.CreateStatusBar()
        self._menu()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self.szerk.SetFocus()

    def _menu(self):
        sav = wx.MenuBar()

        f = wx.Menu()
        self._mi(f, "Ú&j\tCtrl+N", self._uj)
        self._mi(f, "&Megnyitás…\tCtrl+O", self._megnyit)
        self._mi(f, "M&entés\tCtrl+S", self._ment)
        self._mi(f, "Mentés más&ként…\tCtrl+Shift+S", self._ment_maskent)
        f.AppendSeparator()
        self._mi(f, "Exportálás &PDF-be…", self._pdf_export)
        f.AppendSeparator()
        self._mi(f, "&Bezárás\tAlt+F4", lambda: self.Close())
        sav.Append(f, "&Fájl")

        sz = wx.Menu()
        self._mi(sz, "&Visszavonás\tCtrl+Z", lambda: self.szerk.Undo())
        self._mi(sz, "Új&ra\tCtrl+Y", lambda: self.szerk.Redo())
        sz.AppendSeparator()
        self._mi(sz, "&Kivágás\tCtrl+X", lambda: self.szerk.Cut())
        self._mi(sz, "&Másolás\tCtrl+C", lambda: self.szerk.Copy())
        self._mi(sz, "&Beillesztés\tCtrl+V", lambda: self.szerk.Paste())
        self._mi(sz, "Min&det kijelöl\tCtrl+A", lambda: self.szerk.SelectAll())
        sz.AppendSeparator()
        self._mi(sz, "K&eresés…\tCtrl+F", self._keres)
        self._mi(sz, "Következő találat\tF3", self._kovetkezo_talalat)
        self._mi(sz, "&Csere mindenhol…\tCtrl+H", self._csere)
        sz.AppendSeparator()
        self._mi(sz, "Okos &tisztítás…\tCtrl+Shift+T", self._tisztitas)
        self._mi(sz, "Fejezetjelölő beszúrása\tCtrl+Shift+J",
                 self._fejezetjelolo)
        self._mi(sz, "Fejezetek felsorolása…", self._fejezetek_listaja)
        sav.Append(sz, "&Szerkesztés")

        fo = wx.Menu()
        self._mi(fo, "&Félkövér\tCtrl+B", lambda: self._jelolo("b"))
        self._mi(fo, "&Dőlt\tCtrl+I", lambda: self._jelolo("i"))
        self._mi(fo, "&Aláhúzott\tCtrl+U", lambda: self._jelolo("u"))
        fo.AppendSeparator()
        self._mi(fo, "&Betűtípus…", self._betutipus)
        self._mi(fo, "Nagyobb betű\tCtrl+Shift+.", lambda: self._meret(+1))
        self._mi(fo, "Kisebb betű\tCtrl+Shift+,", lambda: self._meret(-1))
        fo.AppendSeparator()
        self._mi(fo, "Balra\tCtrl+L", lambda: self._igazit(wx.TEXT_ALIGNMENT_LEFT))
        self._mi(fo, "Középre\tCtrl+E",
                 lambda: self._igazit(wx.TEXT_ALIGNMENT_CENTRE))
        self._mi(fo, "Jobbra\tCtrl+R",
                 lambda: self._igazit(wx.TEXT_ALIGNMENT_RIGHT))
        self._mi(fo, "Sorkizárt\tCtrl+J",
                 lambda: self._igazit(wx.TEXT_ALIGNMENT_JUSTIFIED))
        fo.AppendSeparator()
        self._mi(fo, "Normál szöveg\tCtrl+0", lambda: self._stilus(0))
        self._mi(fo, "Címsor &1\tCtrl+1", lambda: self._stilus(1))
        self._mi(fo, "Címsor &2\tCtrl+2", lambda: self._stilus(2))
        self._mi(fo, "Címsor &3\tCtrl+3", lambda: self._stilus(3))
        fo.AppendSeparator()
        self._mi(fo, "Formázás máso&lása\tCtrl+Shift+C", self._form_masol)
        self._mi(fo, "Formázás b&eillesztése\tCtrl+Shift+V", self._form_beilleszt)
        self._mi(fo, "Formázás &törlése", self._form_torol)
        sav.Append(fo, "F&ormázás")

        t = wx.Menu()
        self._mi(t, "&Mi a formázás itt?\tCtrl+Shift+I", self._formazas_mondd)
        self._mi(t, "&Hol vagyok?\tCtrl+Shift+H", self._hol_vagyok)
        self._mi(t, "Mennyi &van?\tCtrl+Shift+K", self._mennyi)
        self._mi(t, "&Dokumentum-térkép…\tCtrl+Shift+D", self._terkep)
        t.AppendSeparator()
        self._mi(t, "&Felolvasás a kurzortól\tCtrl+Shift+F", self._felolvas)
        self._mi(t, "Felolvasás &leállítása\tEscape", self._felolvas_stop)
        sav.Append(t, "&Tájékozódás")

        a = wx.Menu()
        for kulcs, nev, _u in AI.FELADATOK:
            self._mi(a, nev, lambda k=kulcs: self._ai(k))
        a.AppendSeparator()
        self._mi(a, "AI-funkciók &listája…\tCtrl+Shift+A", self._ai_lista)
        a.AppendSeparator()
        self._mi(a, "A teljes dokumentum &fordítása…\tCtrl+Shift+R",
                 self._forditas)
        sav.Append(a, "&AI")

        b = wx.Menu()
        self.mi_valtas = b.AppendCheckItem(
            wx.ID_ANY, "Mondja be a formázás &váltását")
        self.mi_valtas.Check(True)
        self.Bind(wx.EVT_MENU, self._valtas_kapcsol, self.mi_valtas)
        self._mi(b, "&Fájltársítások…", self._tarsitas)
        b.AppendSeparator()
        self._mi(b, "&Súgó\tF1", self._sugo)
        sav.Append(b, "&Beállítások")

        self.SetMenuBar(sav)

    def _mi(self, menu, cimke, fv):
        it = menu.Append(wx.ID_ANY, cimke)
        self.Bind(wx.EVT_MENU, lambda e: fv(), it)
        return it

    # ---- helyi menü (Alkalmazások billentyű / Shift+F10) ----------------

    def _helyi_menu(self, e=None):
        """A leggyakoribb műveletek EGY helyen, végignyilazhatóan.

        A gyorsbillentyű is ott van minden sorban: aki a helyi menüt
        használja, menet közben tanulja meg a billentyűket.
        """
        m = wx.Menu()
        self._mi(m, "Mi a formázás itt?\tCtrl+Shift+I", self._formazas_mondd)
        self._mi(m, "Hol vagyok?\tCtrl+Shift+H", self._hol_vagyok)
        self._mi(m, "Mennyi van?\tCtrl+Shift+K", self._mennyi)
        self._mi(m, "Dokumentum-térkép…\tCtrl+Shift+D", self._terkep)
        m.AppendSeparator()
        self._mi(m, "Félkövér\tCtrl+B", lambda: self._jelolo("b"))
        self._mi(m, "Dőlt\tCtrl+I", lambda: self._jelolo("i"))
        self._mi(m, "Aláhúzott\tCtrl+U", lambda: self._jelolo("u"))
        self._mi(m, "Formázás törlése", self._form_torol)
        m.AppendSeparator()
        self._mi(m, "Kivágás\tCtrl+X", lambda: self.szerk.Cut())
        self._mi(m, "Másolás\tCtrl+C", lambda: self.szerk.Copy())
        self._mi(m, "Beillesztés\tCtrl+V", lambda: self.szerk.Paste())
        self._mi(m, "Mindet kijelöl\tCtrl+A", lambda: self.szerk.SelectAll())
        m.AppendSeparator()
        self._mi(m, "Keresés…\tCtrl+F", self._keres)
        self._mi(m, "Csere mindenhol…\tCtrl+H", self._csere)
        self._mi(m, "Okos tisztítás…\tCtrl+Shift+T", self._tisztitas)
        self._mi(m, "Fejezetjelölő beszúrása\tCtrl+Shift+J",
                 self._fejezetjelolo)
        self._mi(m, "Felolvasás a kurzortól\tCtrl+Shift+F", self._felolvas)
        m.AppendSeparator()
        self._mi(m, "Mentés\tCtrl+S", self._ment)
        self._mi(m, "AI-funkciók…\tCtrl+Shift+A", self._ai_lista)
        self._mi(m, "Súgó\tF1", self._sugo)
        self.PopupMenu(m)
        m.Destroy()

    # ---- állapot -------------------------------------------------------

    def _allapot(self, szoveg, mondja=True):
        if self._closing:
            return
        try:
            self.SetStatusText(szoveg)
        except Exception:
            pass
        if mondja:
            _mondd(self.main, szoveg)

    def _cim_frissit(self):
        nev = os.path.basename(self._ut) if self._ut else "Névtelen"
        jel = "*" if self._piszkos else ""
        olvas = " – csak olvasható" if self._csak_olvas else ""
        self.SetTitle(f"{jel}{nev}{olvas} – Super Edit")

    def _on_valtozott(self, e):
        if not self._piszkos:
            self._piszkos = True
            self._cim_frissit()
        e.Skip()

    # ---- a formázás bemondása ------------------------------------------

    def _betu_most(self):
        try:
            attr = self._jegy()
            if self.szerk.GetStyle(self.szerk.GetInsertionPoint(), attr):
                return attr
        except Exception:
            pass
        return None

    def _on_kurzor(self, e):
        e.Skip()
        if self._closing:
            return
        if e.GetKeyCode() == wx.WXK_ALT:
            return
        if not self._valtas_bemondas:
            return
        attr = self._betu_most()
        if attr is None:
            return
        try:
            betu = attr.GetFont()
        except Exception:
            return
        mostani = BE.jegyek(betu)
        uzenet = BE.rovid(self._utolso_jegyek, mostani)
        self._utolso_jegyek = mostani
        if uzenet:
            _mondd(self.main, uzenet)

    def _formazas_mondd(self):
        attr = self._betu_most()
        betu = None
        igaz = ""
        try:
            betu = attr.GetFont() if attr is not None else None
            igaz = BE.igazitas_neve(attr.GetAlignment()) if attr else ""
        except Exception:
            pass
        kijelolt = bool(self.szerk.GetStringSelection())
        self._allapot(BE.teljes(betu, igaz, self._stilus_neve(), kijelolt))

    def _stilus_neve(self) -> str:
        attr = self._betu_most()
        try:
            if attr is not None:
                m = attr.GetFont().GetPointSize()
                for szint, meret in ((1, 20), (2, 16), (3, 14)):
                    if m >= meret:
                        return f"Címsor {szint}"
        except Exception:
            pass
        return "Normál"

    def _valtas_kapcsol(self, e=None):
        self._valtas_bemondas = self.mi_valtas.IsChecked()
        self._allapot("A formázás váltását bemondom."
                      if self._valtas_bemondas
                      else "A formázás váltását nem mondom be.")

    # ---- formázó műveletek ---------------------------------------------

    def _jelolo(self, mit):
        """Félkövér / dőlt / aláhúzott KAPCSOLÁSA.

        ⚠️ A natív mezőn nincs `ApplyBoldToSelection` — az a RichTextCtrl
        szolgáltatása volt. Itt magunk olvassuk ki a mostani állapotot és
        fordítjuk meg, hogy a Ctrl+B tényleg KAPCSOLÓ maradjon: a kétszeri
        megnyomás vissza is vegye. Egy olyan „félkövér", amit nem lehet
        levenni, rosszabb, mint ha nem lenne.
        """
        attr = self._betu_most()
        betu = None
        try:
            betu = attr.GetFont() if attr is not None else None
        except Exception:
            betu = None
        most = {"b": betu.GetWeight() >= 600 if betu else False,
                "i": betu.GetStyle() == wx.FONTSTYLE_ITALIC if betu else False,
                "u": betu.GetUnderlined() if betu else False}[mit]
        uj = not most

        a = self._jegy()
        if mit == "b":
            a.SetFontWeight(wx.FONTWEIGHT_BOLD if uj else wx.FONTWEIGHT_NORMAL)
        elif mit == "i":
            a.SetFontStyle(wx.FONTSTYLE_ITALIC if uj else wx.FONTSTYLE_NORMAL)
        else:
            a.SetFontUnderlined(uj)

        tol, ig = self.szerk.GetSelection()
        if tol >= ig:
            self.szerk.SetDefaultStyle(a)
        else:
            self.szerk.SetStyle(tol, ig, a)
        self._formazva = True
        nev = {"b": "félkövér", "i": "dőlt", "u": "aláhúzott"}[mit]
        self._allapot(nev if uj else "nem " + nev)

    def _igazit(self, mire):
        a = self._jegy()
        a.SetAlignment(mire)
        tol, ig = self.szerk.GetSelection()
        if tol >= ig:
            # nincs kijelölés: a MOSTANI bekezdésre – az igazítás bekezdés-
            # szintű tulajdonság, tehát a sor egészére kell alkalmazni
            poz = self.szerk.GetInsertionPoint()
            tol, ig = self._bekezdes_hatarai(poz)
        self.szerk.SetStyle(tol, ig, a)
        self._formazva = True
        self._allapot(BE.igazitas_neve(mire) or "igazítva")

    def _bekezdes_hatarai(self, poz):
        """A `poz`-t tartalmazó sor (bekezdés) kezdete és vége."""
        szoveg = self.szerk.GetValue()
        eleje = szoveg.rfind("\n", 0, poz) + 1
        vege = szoveg.find("\n", poz)
        return eleje, (len(szoveg) if vege < 0 else vege)

    def _meret(self, irany):
        attr = self._betu_most()
        try:
            most = attr.GetFont().GetPointSize()
        except Exception:
            most = 12
        jeloltek = BETUMERETEK if irany > 0 else list(reversed(BETUMERETEK))
        uj = next((m for m in jeloltek
                   if (m > most if irany > 0 else m < most)), most)
        self._betu_alkalmaz(meret=uj)
        self._allapot("%d pont" % uj)

    def _betu_alkalmaz(self, meret=None, nev=None, sulyos=None):
        a = self._jegy()
        if meret:
            a.SetFontSize(int(meret))
        if nev:
            a.SetFontFaceName(nev)
        if sulyos is not None:
            a.SetFontWeight(wx.FONTWEIGHT_BOLD if sulyos
                            else wx.FONTWEIGHT_NORMAL)
        self._formazva = True
        tol, ig = self.szerk.GetSelection()
        if tol >= ig:
            # nincs kijelölés: a MOSTANTÓL gépelt szövegre érvényes
            self.szerk.SetDefaultStyle(a)
            return
        self.szerk.SetStyle(tol, ig, a)

    def _betutipus(self):
        adat = wx.FontData()
        attr = self._betu_most()
        try:
            if attr is not None:
                adat.SetInitialFont(attr.GetFont())
        except Exception:
            pass
        d = wx.FontDialog(self, adat)
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            betu = d.GetFontData().GetChosenFont()
        finally:
            d.Destroy()
        self._betu_alkalmaz(meret=betu.GetPointSize(),
                            nev=betu.GetFaceName())
        self._allapot(f"{betu.GetFaceName()}, {betu.GetPointSize()} pont.")

    def _stilus(self, szint):
        meret = {0: 12, 1: 20, 2: 16, 3: 14}[szint]
        self._betu_alkalmaz(meret=meret, sulyos=bool(szint))
        self._allapot("Normál szöveg." if not szint else f"Címsor {szint}.")

    def _form_masol(self):
        attr = self._betu_most()
        if attr is None:
            self._allapot("Nincs mit másolni.")
            return
        try:
            self._masolt_formatum = attr.GetFont()
            self._allapot("Formázás másolva: "
                          + BE.teljes(self._masolt_formatum))
        except Exception:
            self._allapot("A formázást nem sikerült lemásolni.")

    def _form_beilleszt(self):
        if self._masolt_formatum is None:
            self._allapot("Előbb másolj formázást a Ctrl+Shift+C-vel.")
            return
        b = self._masolt_formatum
        self._betu_alkalmaz(meret=b.GetPointSize(), nev=b.GetFaceName(),
                            sulyos=b.GetWeight() >= 600)
        self._allapot("Formázás beillesztve.")

    def _form_torol(self):
        self._betu_alkalmaz(meret=12, nev="Segoe UI", sulyos=False)
        self._allapot("Formázás törölve, normál szöveg.")

    # ---- tájékozódás ----------------------------------------------------

    def _hol_vagyok(self):
        p = self.szerk.GetInsertionPoint()
        sor = self.szerk.PositionToXY(p)[2] + 1 \
            if len(self.szerk.PositionToXY(p)) > 2 else 1
        sorok = max(1, self.szerk.GetNumberOfLines())
        self._allapot(BE.hely(sor, sorok))

    def _mennyi(self):
        sz = self.szerk.GetValue()
        self._allapot(BE.meret_szoveg(len(sz.split()), len(sz),
                                      len([s for s in sz.split("\n") if s.strip()])))

    def _terkep(self):
        """A címsorok listája — ötven oldalnál ez a különbség a használható és
        a használhatatlan között."""
        cimsorok = []
        sz = self.szerk.GetValue().split("\n")
        pozicio = 0
        for i, sor in enumerate(sz):
            if sor.strip():
                try:
                    a = self._jegy()
                    if self.szerk.GetStyle(pozicio, a) and \
                            a.GetFont().GetPointSize() >= 14:
                        cimsorok.append((sor.strip()[:80], pozicio))
                except Exception:
                    pass
            pozicio += len(sor) + 1
        if not cimsorok:
            self._allapot("Ebben a dokumentumban nincs címsor. Címsort a "
                          "Ctrl+1, 2 vagy 3 készít.")
            return
        d = wx.SingleChoiceDialog(self, "Ugrás címsorra:", "Dokumentum-térkép",
                                  [c for c, _ in cimsorok])
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            _cim, poz = cimsorok[d.GetSelection()]
        finally:
            d.Destroy()
        self.szerk.SetInsertionPoint(poz)
        self.szerk.ShowPosition(poz)
        self.szerk.SetFocus()
        self._allapot(_cim)

    def _felolvas(self):
        sz = self.szerk.GetRange(self.szerk.GetInsertionPoint(),
                                 self.szerk.GetLastPosition())
        if not sz.strip():
            self._allapot("Innen nincs mit felolvasni.")
            return
        _mondd(self.main, sz[:8000])

    def _felolvas_stop(self):
        try:
            from superdl import screenreader
            screenreader.speak("")
        except Exception:
            pass
        sv = getattr(self.main, "selfvoice", None)
        if sv and hasattr(sv, "stop"):
            try:
                sv.stop()
            except Exception:
                pass

    # ---- okos tisztítás --------------------------------------------------

    def _tisztitas(self):
        """A beillesztett szövegből a navigációs szemét kiszedése.

        ⚠️ ELŐBB MEGSZÁMOL, AZTÁN KÉRDEZ. Vakon egy néma tömeges csere a
        legrosszabb, ami történhet: ha nem figyeltél, már nem tudod, mi volt
        ott. Ezért a párbeszéd minden szabálynál kiírja, HÁNY helyen
        változtatna, és a Ctrl+Z egy lépésben visszavonja az egészet.
        """
        szoveg = self.szerk.GetValue()
        if not szoveg.strip():
            self._allapot("A dokumentum üres, nincs mit tisztítani.")
            return
        szamok = TI.szamlal(szoveg)
        if not any(szamok.values()):
            self._allapot(TI.osszefoglalo(szamok))
            return
        cimkek, kulcsok = [], []
        for kulcs, nev, _fv in TI.SZABALYOK:
            db = szamok.get(kulcs, 0)
            cimkek.append("%s — %d helyen" % (nev, db) if db
                          else "%s — nincs találat" % nev)
            kulcsok.append(kulcs)
        self._allapot(TI.osszefoglalo(szamok))
        d = wx.MultiChoiceDialog(
            self, "Mit szedjek ki a szövegből?\n"
                  "A Ctrl+Z egy lépésben visszavonja.",
            "Okos tisztítás", cimkek)
        d.SetSelections([i for i, k in enumerate(kulcsok)
                         if k in TI.ALAP and szamok.get(k, 0)])
        try:
            if d.ShowModal() != wx.ID_OK:
                self._allapot("A tisztítást elhagytam, a szöveg változatlan.")
                return
            valasztott = {kulcsok[i] for i in d.GetSelections()}
        finally:
            d.Destroy()
        if not valasztott:
            self._allapot("Nem választottál semmit, a szöveg változatlan.")
            return
        uj, db = TI.tisztit(szoveg, valasztott)
        if uj == szoveg:
            self._allapot("Nem változott semmi.")
            return
        poz = min(self.szerk.GetInsertionPoint(), len(uj))
        self.szerk.SetValue(uj)
        self.szerk.SetInsertionPoint(poz)
        self._piszkos = True
        self._cim_frissit()
        self._allapot("Kész: %d helyen tisztítottam, a szöveg %d karakterrel "
                      "rövidebb. Ctrl+Z visszavonja."
                      % (db, len(szoveg) - len(uj)))

    # ---- fordítás --------------------------------------------------------

    def _forditas(self):
        """A TELJES dokumentum fordítása, darabokban.

        ⚠️ A MEGLÉVŐ SZÖVEGET NEM ÍRJUK FELÜL. A fordítás ÚJ FÁJLBA megy az
        eredeti mellé, és azt nyitjuk meg. Így a két változat egyszerre
        megvan, oda-vissza fordítható, és egy rossz fordítás nem viszi el a
        munkát. Ez ugyanaz az elv, mint az AI-javaslatoknál: vakon egy néma
        csere a legrosszabb, ami történhet.
        """
        szoveg = self.szerk.GetValue()
        if not szoveg.strip():
            self._allapot("A dokumentum üres, nincs mit fordítani.")
            return
        if self._forditas_fut:
            self._allapot("Már fut egy fordítás. Az Escape megállítja.")
            return

        nevek = [nev for _k, nev in FO.NYELVEK]
        kodok = [k for k, _n in FO.NYELVEK]
        honnan = self._valassz("Milyen nyelvről fordítsak?", "Forrásnyelv",
                               nevek, 0)
        if honnan is None:
            return
        hova = self._valassz("Milyen nyelvre fordítsak?", "Célnyelv",
                             nevek, 1)
        if hova is None:
            return
        if kodok[honnan] == kodok[hova]:
            self._allapot("A két nyelv ugyanaz, nincs mit fordítani.")
            return

        helyi_ok = FO.helyi_elerheto(kodok[honnan], kodok[hova])
        motorok = ["AI-fordítás (jobb minőség, a szöveg elhagyja a gépet)"]
        motor_kulcs = ["ai"]
        if helyi_ok:
            motorok.append("Helyi gépi fordítás (a szöveg a gépen marad)")
        elif FO.helyi_motor_van():
            motorok.append("Helyi gépi fordítás – a nyelvi csomagot "
                           "letöltöm hozzá (egyszeri, pár perc)")
        else:
            motorok.append("Helyi gépi fordítás – ebben a programban nem "
                           "érhető el")
        motor_kulcs.append("helyi")
        valasztott = self._valassz("Melyik fordítóval?", "Fordítás",
                                   motorok, 0)
        if valasztott is None:
            return
        motor = motor_kulcs[valasztott]
        if motor == "helyi" and not FO.helyi_motor_van():
            self._allapot(
                "A helyi gépi fordító ebben a programban nem érhető el. "
                "Válaszd az AI-fordítást, vagy frissítsd a SuperDL-t.")
            return
        # ⚠️ NEM KÜLDJÜK EL A FELHASZNÁLÓT MÁSHOVÁ. Ha a helyi fordítót kéri
        # és a nyelvi csomag hiányzik, LETÖLTJÜK — csak előbb kimondjuk, hogy
        # ezért tovább fog tartani. Egy „töltsd le a Beállításokban" válasz
        # vakon három ablakkal odébb küld, és közben elveszik, mit is akart.
        letoltes_kell = (motor == "helyi" and not helyi_ok)
        if letoltes_kell:
            db = FO.helyi_letoltes_kell(kodok[honnan], kodok[hova])
            if db == 0:
                letoltes_kell = False
            elif db < 0:
                self._allapot(
                    "A nyelvi csomagot most nem tudom megkeresni – ehhez "
                    "internet kell. Válaszd az AI-fordítást, vagy próbáld "
                    "később.")
                return
            else:
                if wx.MessageBox(
                        "A helyi fordításhoz %d nyelvi csomagot kell egyszer "
                        "letölteni (csomagonként nagyjából 60–100 megabájt).\n\n"
                        "Letöltsem most? A fordítás emiatt az első alkalommal "
                        "hosszabb lesz; utána viszont örökre offline megy, és "
                        "a szöveg nem hagyja el a gépet." % db,
                        "Nyelvi csomag letöltése",
                        wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
                    self._allapot("Rendben, nem töltöttem le semmit.")
                    return

        darabok = [d for d in FO.darabol(szoveg) if FO.forditando(d)]
        self._forditas_fut = True
        self._forditas_megall = False
        self._allapot(
            "%sFordítás %s nyelvről %s nyelvre, %d darabban. Ez eltarthat egy "
            "ideig; az Escape megállítja. Szólok, ha kész."
            % ("Előbb letöltöm a nyelvi csomagot, ezért most hosszabb lesz. "
               if letoltes_kell else "",
               FO.nyelv_neve(kodok[honnan]), FO.nyelv_neve(kodok[hova]),
               len(darabok)))

        import threading

        def halad(kesz, osszes, _d):
            # ⚠️ 4.6.7-es szabály: felhasználónak szóló jelzés SOHA nem
            # indulhat közvetlenül háttérszálról.
            if osszes >= 4 and kesz % max(1, osszes // 4) == 0:
                wx.CallAfter(self._allapot,
                             "Fordítás: %d / %d darab kész." % (kesz, osszes))

        def letoltes_halad(i, osszes):
            wx.CallAfter(self._allapot,
                         "Nyelvi csomag letöltése: %d / %d. Ez eltarthat pár "
                         "percig." % (i, osszes))

        def munka():
            try:
                if letoltes_kell:
                    if not FO.helyi_letolt(kodok[honnan], kodok[hova],
                                           letoltes_halad):
                        wx.CallAfter(
                            self._forditas_kesz, "",
                            "a nyelvi csomag letöltése után sem érhető el a "
                            "helyi fordító", kodok[hova])
                        return
                    wx.CallAfter(self._allapot,
                                 "A nyelvi csomag megvan, kezdem a fordítást.")
                eredmeny = FO.fordit(szoveg, kodok[honnan], kodok[hova],
                                     motor=motor, halad=halad,
                                     megall=lambda: self._forditas_megall)
                hiba = ""
            except Exception as ex:
                eredmeny, hiba = "", str(ex)
            wx.CallAfter(self._forditas_kesz, eredmeny, hiba,
                         kodok[hova])

        threading.Thread(target=munka, daemon=True).start()

    def _forditas_kesz(self, eredmeny, hiba, hova_kod):
        self._forditas_fut = False
        if hiba:
            self._allapot("A fordítás nem sikerült: %s" % hiba)
            return
        if not eredmeny.strip():
            self._allapot("A fordító üres választ adott, a szöveged "
                          "változatlan.")
            return
        megallt = self._forditas_megall
        self._forditas_megall = False

        # ÚJ fájl az eredeti mellé – az eredetihez nem nyúlunk
        if self._ut:
            toke, kit = os.path.splitext(self._ut)
            uj_ut = "%s-%s%s" % (toke, hova_kod, kit or ".docx")
            szam = 2
            while os.path.exists(uj_ut):
                uj_ut = "%s-%s-%d%s" % (toke, hova_kod, szam, kit or ".docx")
                szam += 1
            try:
                FM.ment(uj_ut, [(s, "Normál", []) for s in
                                eredmeny.split("\n")])
            except Exception as ex:
                self._allapot("A fordítás elkészült, de menteni nem sikerült: "
                              "%s" % ex)
                return
            self.open_file(uj_ut)
            self._allapot(
                "%sA fordítás elkészült, és új fájlba került az eredeti "
                "mellé: %s. Az eredeti fájlhoz nem nyúltam."
                % ("Megállítottam, ezért a vége eredetiben maradt. "
                   if megallt else "", os.path.basename(uj_ut)))
            return

        # nincs még fájl: megkérdezzük, mielőtt bármit felülírunk
        if wx.MessageBox(
                "A fordítás elkészült. A dokumentum még nincs elmentve "
                "fájlba, ezért a szerkesztő tartalmát cserélném le rá. "
                "Mehet? (A Ctrl+Z visszavonja.)",
                "Fordítás kész", wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
            self._allapot("A fordítást eldobtam, a szöveged változatlan.")
            return
        self.szerk.SetValue(eredmeny)
        self._piszkos = True
        self._cim_frissit()
        self._allapot("A fordítás bekerült. Ctrl+Z visszavonja.")

    def _valassz(self, kerdes, cim, tetelek, alap=0):
        """Egy választás listából. None, ha elhagyta."""
        d = wx.SingleChoiceDialog(self, kerdes, cim, tetelek)
        try:
            d.SetSelection(min(alap, len(tetelek) - 1))
            if d.ShowModal() != wx.ID_OK:
                return None
            return d.GetSelection()
        finally:
            d.Destroy()

    # ---- fejezetjelölő ---------------------------------------------------

    def _fejezetjelolo(self):
        """Fejezethatár beszúrása, amit a hangoskönyv-készítő is felismer."""
        from superdl import fejezet
        d = wx.TextEntryDialog(
            self, "A fejezet címe (üresen hagyhatod):",
            "Fejezetjelölő beszúrása")
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            cim = d.GetValue().strip()
        finally:
            d.Destroy()
        poz = self.szerk.GetInsertionPoint()
        szoveg = self.szerk.GetValue()
        # a jelölő SAJÁT SORBAN álljon – ha a kurzor sor közepén van, előbb
        # lezárjuk a sort, különben a felismerés nem találná meg
        elotte = "" if (poz == 0 or szoveg[poz - 1] == "\n") else "\n"
        utana = "" if (poz >= len(szoveg) or szoveg[poz] == "\n") else "\n"
        self.szerk.SetInsertionPoint(poz)
        self.szerk.SetDefaultStyle(self._jegy_alap())
        self.szerk.WriteText(elotte + fejezet.jelolo(cim) + "\n" + utana)
        self._piszkos = True
        self._cim_frissit()
        db = fejezet.szamlal(self.szerk.GetValue())
        self._allapot(
            "Fejezetjelölő beszúrva%s. Összesen %d fejezetjelölő van a "
            "dokumentumban. A hangoskönyv-készítő ezek mentén tud fejezetenként "
            "darabolni, percek helyett."
            % ((": " + cim) if cim else "", db))

    def _fejezetek_listaja(self):
        from superdl import fejezet
        szoveg = self.szerk.GetValue()
        cimek = fejezet.cimek(szoveg)
        if not fejezet.van_jelolo(szoveg):
            self._allapot(
                "Ebben a dokumentumban nincs fejezetjelölő. A Ctrl+Shift+J "
                "szúr be egyet oda, ahol a kurzor áll.")
            return
        d = wx.SingleChoiceDialog(
            self, "%d fejezet. Enter: odaugrom." % len(cimek),
            "Fejezetek", cimek)
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            valasztott = d.GetSelection()
        finally:
            d.Destroy()
        # a kiválasztott fejezet jelölőjének sorára ugrunk
        poz, talalt = 0, 0
        for sor in szoveg.split("\n"):
            if fejezet.jelolo_e(sor):
                if talalt == valasztott:
                    break
                talalt += 1
            poz += len(sor) + 1
        self.szerk.SetInsertionPoint(min(poz, len(szoveg)))
        self.szerk.ShowPosition(min(poz, len(szoveg)))
        self.szerk.SetFocus()
        self._allapot(cimek[valasztott] if valasztott < len(cimek) else "")

    # ---- keresés, csere --------------------------------------------------

    def _keres(self):
        d = wx.TextEntryDialog(self, "Mit keresel?", "Keresés", self._keresett)
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            self._keresett = d.GetValue()
        finally:
            d.Destroy()
        self._kovetkezo_talalat()

    def _kovetkezo_talalat(self):
        if not self._keresett:
            self._keres()
            return
        sz = self.szerk.GetValue().lower()
        tol = self.szerk.GetInsertionPoint() + 1
        i = sz.find(self._keresett.lower(), tol)
        if i < 0:
            i = sz.find(self._keresett.lower())     # körbefordul
            if i < 0:
                self._allapot(f"Nincs találat erre: {self._keresett}.")
                return
            self._allapot("A dokumentum végére értem, elölről folytatom.")
        self.szerk.SetSelection(i, i + len(self._keresett))
        self.szerk.ShowPosition(i)
        self.szerk.SetFocus()

    def _csere(self):
        d = wx.TextEntryDialog(self, "Mit cseréljek?", "Csere", self._keresett)
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            mit = d.GetValue()
        finally:
            d.Destroy()
        if not mit:
            return
        d2 = wx.TextEntryDialog(self, f"„{mit}” helyére mi kerüljön?", "Csere")
        try:
            if d2.ShowModal() != wx.ID_OK:
                return
            mire = d2.GetValue()
        finally:
            d2.Destroy()
        sz = self.szerk.GetValue()
        db = sz.count(mit)
        if not db:
            self._allapot(f"Nincs találat erre: {mit}.")
            return
        if wx.MessageBox(f"{db} helyen cserélek. Mehet?", "Csere",
                         wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
            return
        self.szerk.SetValue(sz.replace(mit, mire))
        self._piszkos = True
        self._cim_frissit()
        self._allapot(f"{db} csere kész. A Ctrl+Z visszavonja.")

    # ---- AI ---------------------------------------------------------------

    def _ai_lista(self):
        nevek = [nev for _k, nev, _u in AI.FELADATOK]
        d = wx.SingleChoiceDialog(self, "Mit csináljon az AI?", "AI-funkciók",
                                  nevek)
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            kulcs = AI.FELADATOK[d.GetSelection()][0]
        finally:
            d.Destroy()
        self._ai(kulcs)

    def _ai(self, kulcs, pontositas=""):
        kijelolt = self.szerk.GetStringSelection()
        szoveg = kijelolt or self.szerk.GetValue()
        if not szoveg.strip():
            self._allapot("Nincs szöveg, amin dolgozhatnék.")
            return
        if AI.hosszu_e(szoveg):
            self._allapot("Ez a szöveg túl hosszú egyben. Jelölj ki egy "
                          "kisebb részt, és próbáld újra.")
            return
        nev = AI.feladat(kulcs)[1]
        self._allapot(f"{nev} folyamatban…")
        import threading

        def munka():
            try:
                valasz = AI.keres(kulcs, szoveg, pontositas)
                wx.CallAfter(self._ai_kesz, kulcs, valasz, bool(kijelolt))
            except Exception as ex:
                wx.CallAfter(self._allapot, f"Az AI nem válaszolt: {ex}")

        threading.Thread(target=munka, daemon=True).start()

    def _ai_kesz(self, kulcs, valasz, volt_kijeloles):
        """⚠️ ELŐNÉZET. A dokumentumhoz addig hozzá sem nyúlunk."""
        if self._closing:
            return
        nev = AI.feladat(kulcs)[1]
        d = wx.Dialog(self, title=f"{nev} – javaslat", size=(820, 620))
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(d, label="Az AI &javaslata (a szövegedhez még nem "
                                     "nyúltunk hozzá):"), 0, wx.ALL, 8)
        t = wx.TextCtrl(d, value=valasz,
                        style=wx.TE_MULTILINE | wx.TE_RICH2)
        t.SetName("Az AI javaslata")
        v.Add(t, 1, wx.EXPAND | wx.ALL, 8)
        sor = wx.BoxSizer(wx.HORIZONTAL)
        b_ok = wx.Button(d, wx.ID_OK, "&Elfogadom")
        b_pont = wx.Button(d, wx.ID_ANY, "&Pontosítom…")
        b_ujra = wx.Button(d, wx.ID_ANY, "Ú&jra")
        b_megse = wx.Button(d, wx.ID_CANCEL, "El&dobom")
        for b in (b_ok, b_pont, b_ujra, b_megse):
            sor.Add(b, 0, wx.RIGHT, 6)
        v.Add(sor, 0, wx.ALL | wx.ALIGN_CENTER, 8)
        d.SetSizer(v)
        dontes = {"mit": "megse"}
        b_pont.Bind(wx.EVT_BUTTON,
                    lambda e: (dontes.update(mit="pontosit"), d.EndModal(wx.ID_NO)))
        b_ujra.Bind(wx.EVT_BUTTON,
                    lambda e: (dontes.update(mit="ujra"), d.EndModal(wx.ID_NO)))
        t.SetFocus()
        _mondd(self.main, "Az AI javaslata megérkezett. " + valasz[:400])
        eredmeny = d.ShowModal()
        vegleges = t.GetValue()
        d.Destroy()

        if eredmeny == wx.ID_OK:
            self._ai_beilleszt(kulcs, vegleges, volt_kijeloles)
            return
        if dontes["mit"] == "ujra":
            self._ai(kulcs)
            return
        if dontes["mit"] == "pontosit":
            p = wx.TextEntryDialog(self, "Mit módosítsak rajta?", "Pontosítás")
            try:
                if p.ShowModal() == wx.ID_OK:
                    self._ai(kulcs, p.GetValue())
            finally:
                p.Destroy()
            return
        self._allapot("A javaslatot eldobtam, a szöveged változatlan.")

    def _ai_beilleszt(self, kulcs, szoveg, volt_kijeloles):
        if kulcs in AI.HOZZAFUZ:
            self.szerk.SetInsertionPoint(self.szerk.GetLastPosition())
            self.szerk.WriteText("\n" + szoveg)
            self._allapot("A folytatás a dokumentum végére került.")
        elif kulcs in AI.CSERELO:
            if volt_kijeloles:
                # a natív mezőn a kijelölés törlése = üresre cserélés
                tol, ig = self.szerk.GetSelection()
                self.szerk.Replace(tol, ig, "")
                self.szerk.SetInsertionPoint(tol)
                self.szerk.WriteText(szoveg)
                self._allapot("A kijelölt szöveg lecserélve. Ctrl+Z visszavonja.")
            else:
                self.szerk.SetValue(szoveg)
                self._allapot("A dokumentum lecserélve. Ctrl+Z visszavonja.")
        else:
            self.szerk.SetInsertionPoint(self.szerk.GetLastPosition())
            self.szerk.WriteText("\n\n" + szoveg)
            self._allapot("A válasz a dokumentum végére került.")
        self._piszkos = True
        self._cim_frissit()

    # ---- fájlműveletek ----------------------------------------------------

    def _kerdez_mentest(self) -> bool:
        """True, ha mehet tovább (mentett vagy eldobta)."""
        if not self._piszkos:
            return True
        v = wx.MessageBox("A dokumentum megváltozott. Mented?", "Super Edit",
                          wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION, self)
        if v == wx.CANCEL:
            return False
        if v == wx.YES:
            return self._ment()
        return True

    def _uj(self):
        if not self._kerdez_mentest():
            return
        self.szerk.SetValue("")
        self._ut = ""
        self._piszkos = False
        self._csak_olvas = False
        self._formazva = False
        self._cim_frissit()
        self._allapot("Új, üres dokumentum.")

    def _valaszto(self, mentes=False, kezdo=""):
        """A BEÉPÍTETT választó: a Windowsé idegen bővítményeket tölt be, és
        azok viszik magukkal az egész programot."""
        if not mentes:
            try:
                from superdl import fajlvalaszto
                ki = fajlvalaszto.valassz_fajlokat(
                    self, "Dokumentum megnyitása", FM.MIND, tobb=False,
                    kezdo=kezdo, mondd=lambda s: _mondd(self.main, s))
                return ki[0] if ki else ""
            except Exception:
                pass
        with wx.FileDialog(
                self, "Mentés másként" if mentes else "Megnyitás",
                wildcard=FM.SZUROK,
                style=(wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) if mentes
                else (wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)) as d:
            return d.GetPath() if d.ShowModal() == wx.ID_OK else ""

    def _megnyit(self):
        if not self._kerdez_mentest():
            return
        ut = self._valaszto()
        if ut:
            self.open_file(ut)

    def open_file(self, ut: str):
        """A FÁJLTÁRSÍTÁS is ezt hívja: rákattintasz egy .txt-re, és itt nyílik."""
        if not ut or not os.path.isfile(ut):
            self._allapot("Ez a fájl nem található.")
            return
        if not FM.tamogatott(ut):
            self._allapot("Ezt a fájltípust a Super Edit nem ismeri.")
            return
        try:
            dok = FM.megnyit(ut)
        except Exception as ex:
            self._allapot(f"A fájlt nem sikerült megnyitni: {ex}")
            return
        # ⚠️ TELJESÍTMÉNY. Régen futamonként írtuk be a szöveget
        # (`SetDefaultStyle` + `WriteText`), és minden bekezdés után egy
        # sorvéget. Egy nagyobb szövegfájlnál ez tízezernyi külön művelet — a
        # megnyitás emiatt volt elviselhetetlenül lassú. Most a TELJES szöveg
        # egyetlen lépésben megy be, és utána CSAK oda teszünk formázást,
        # ahol tényleg van. Egy sima .txt-nél ez nulla formázó-lépés.
        # A sorvég a bekezdések KÖZÉ kerül (a `join` miatt), nem az utolsó
        # után — különben minden megnyitás-mentés kör egy üres bekezdéssel
        # hizlalná a dokumentumot.
        darabok = [FM.szet(b) for b in dok.bekezdesek]
        # A megnyitott fájlban VAN-e egyáltalán formázás? Ha nincs (tipikusan
        # egy .txt), a mentés sem fog stílust kiolvasni – lásd `_bekezdesek`.
        self._formazva = any(
            stilus != "Normál" or any(f[1] or f[2] or f[3] for f in futamok)
            for _sz, stilus, futamok in darabok)
        self.szerk.SetValue("\n".join(d[0] for d in darabok))
        poz = 0
        for szoveg, stilus, futamok in darabok:
            szint = {"Címsor 1": 20, "Címsor 2": 16, "Címsor 3": 14}.get(stilus)
            p = poz
            for reszszoveg, felkover, dolt, alahuzott in futamok:
                hossz = len(reszszoveg)
                if szint or felkover or dolt or alahuzott:
                    a = self._jegy_alap()
                    a.SetFontSize(szint or 12)
                    a.SetFontWeight(wx.FONTWEIGHT_BOLD
                                    if (felkover or szint)
                                    else wx.FONTWEIGHT_NORMAL)
                    a.SetFontStyle(wx.FONTSTYLE_ITALIC if dolt
                                   else wx.FONTSTYLE_NORMAL)
                    a.SetFontUnderlined(bool(alahuzott))
                    self.szerk.SetStyle(p, p + hossz, a)
                p += hossz
            poz += len(szoveg) + 1
        self.szerk.SetInsertionPoint(0)
        self._ut = ut
        self._csak_olvas = FM.csak_olvashato(ut)
        self._piszkos = False
        self._cim_frissit()
        uzenet = f"{os.path.basename(ut)} megnyitva, " \
                 f"{len(dok.bekezdesek)} bekezdés."
        if dok.figyelmeztetes:
            uzenet += " " + dok.figyelmeztetes
        self._allapot(uzenet)
        self.szerk.SetFocus()

    def _bekezdesek(self):
        """A dokumentum bekezdései A FORMÁZÁSUKKAL együtt.

        ⚠️ Ez a mentés lelke. Ha innen csak a nyers szöveg menne vissza, a
        felhasználó formázna, mentene, és a formázás NÉMÁN elveszne — pont az
        a hiba, ami ellen az egész modul készült. Ezért bekezdésenként
        kiolvassuk a stílust, és karakterenként összevonjuk az azonos jelölésű
        FUTAMOKAT (félkövér, dőlt, aláhúzott).

        Visszaad: [(szöveg, stílus, futamok)], ahol
        futamok = [(részszöveg, félkövér, dőlt, aláhúzott)].
        """
        szoveg = self.szerk.GetValue()
        sorok = szoveg.split("\n")

        # ⚠️ A LEGFONTOSABB GYORSÍTÁS: ha a dokumentumban NINCS formázás,
        # egyetlen stílus-lekérdezést sem csinálunk. Egy stílus-lekérdezés a
        # natív mezőn nagyságrendileg 7 ezredmásodperc; tízezer bekezdésnél a
        # bekezdésenkénti néhány lekérdezés is PERCEKET jelent. Egy sima
        # szövegfájlnál viszont nincs mit kiolvasni — és pont az a leggyakoribb
        # eset, amit a felhasználó nagy fájlként megnyit.
        if not self._formazva:
            return [(s, "Normál", []) for s in sorok]

        szakaszok = self._szakaszok(0, len(szoveg))
        ki = []
        poz = 0
        for sor in sorok:
            ki.append((sor, self._stilus_szakaszbol(szakaszok, poz, len(sor)),
                       self._futamok_szakaszbol(szakaszok, poz, sor)))
            poz += len(sor) + 1
        return ki

    # A formázás kiolvasása a vezérlőből – lásd a ⚠️-t a `_szakaszok`-nál.
    _SZAKASZ_MIN = 1

    def _szakaszok(self, tol, ig):
        """A dokumentum egyforma formázású szakaszai: [(tól, ig, jegyek)].

        ⚠️ MIÉRT ÍGY. A stílust csak POZÍCIÓNKÉNT lehet lekérdezni, és egy
        lekérdezés drága. Karakterenként végigmenni percekbe kerül. Ezért
        felezünk: ha egy szakasz elején, közepén és végén UGYANAZ a formázás,
        egyformának vesszük; különben kettévágjuk. Így a lekérdezések száma a
        formázott részek számától függ, nem a szöveg hosszától.

        ⚠️ AMIT EZ NEM LÁT: egy olyan formázott sziget, ami teljes egészében
        két egyforma végpont KÖZÉ esik, és a közepet sem érinti. Ezt a
        korlátot tudatosan vállaljuk: a másik út (karakterenkénti olvasás)
        használhatatlanná tette a programot nagy fájlon. A gépelés közbeni
        formázás összefüggő szakaszokban keletkezik, tehát ez a gyakorlatban
        nem fordul elő – de le van írva, hogy ha mégis, tudjuk, hol keressük.
        """
        if ig <= tol:
            return []
        eleje = self._jegyek_poznal(tol)
        if ig - tol <= self._SZAKASZ_MIN:
            return [(tol, ig, eleje)]
        vege = self._jegyek_poznal(ig - 1)
        kozep = (tol + ig) // 2
        if eleje == vege and self._jegyek_poznal(kozep) == eleje:
            return [(tol, ig, eleje)]
        bal = self._szakaszok(tol, kozep)
        jobb = self._szakaszok(kozep, ig)
        # a határon összeérő, azonos jegyű szakaszokat összevonjuk
        if bal and jobb and bal[-1][2] == jobb[0][2]:
            bal[-1] = (bal[-1][0], jobb[0][1], bal[-1][2])
            jobb = jobb[1:]
        return bal + jobb

    @staticmethod
    def _atfedok(szakaszok, tol, ig):
        return [sz for sz in szakaszok if sz[1] > tol and sz[0] < ig]

    def _stilus_szakaszbol(self, szakaszok, poz, hossz) -> str:
        meret = 12
        for _t, _i, jegyek in self._atfedok(szakaszok, poz, poz + max(hossz, 1)):
            meret = max(meret, jegyek[3])
        for szint, hatar in ((1, 20), (2, 16), (3, 14)):
            if meret >= hatar:
                return f"Címsor {szint}"
        return "Normál"

    def _futamok_szakaszbol(self, szakaszok, poz, sor):
        if not sor:
            return []
        ki = []
        for t, i, jegyek in self._atfedok(szakaszok, poz, poz + len(sor)):
            a = max(t, poz) - poz
            b = min(i, poz + len(sor)) - poz
            resz = sor[a:b]
            if not resz:
                continue
            jel = jegyek[:3]
            if ki and ki[-1][1:] == jel:          # összeérő, azonos jelölés
                ki[-1] = (ki[-1][0] + resz,) + jel
            else:
                ki.append((resz,) + jel)
        return ki or [(sor, False, False, False)]

    def _jegyek_poznal(self, poz):
        """(félkövér, dőlt, aláhúzott, méret) a megadott pozíción."""
        try:
            a = self._jegy()
            if self.szerk.GetStyle(poz, a):
                b = a.GetFont()
                return (b.GetWeight() >= 600, b.GetStyle() == wx.FONTSTYLE_ITALIC,
                        b.GetUnderlined(), b.GetPointSize())
        except Exception:
            pass
        return (False, False, False, 12)

    def _stilus_poznal(self, poz) -> str:
        _b, _d, _a, meret = self._jegyek_poznal(poz)
        for szint, hatar in ((1, 20), (2, 16), (3, 14)):
            if meret >= hatar:
                return f"Címsor {szint}"
        return "Normál"

    def _jelek_poznal(self, poz):
        """Csak a (félkövér, dőlt, aláhúzott) hármas, méret nélkül."""
        b, d, a, _m = self._jegyek_poznal(poz)
        return (b, d, a)

    def _futamok(self, poz, sor):
        """Az azonos jelölésű részek összevonva.

        ⚠️ TELJESÍTMÉNY. Ez eredetileg KARAKTERENKÉNT kérdezte le a stílust.
        Egy százezer karakteres szövegnél az százezer lekérdezés — a mentés és
        a megnyitás emiatt volt „vicc kategóriában" lassú. Most a futam VÉGÉT
        felezéssel keressük meg: a jelölés egy bekezdésen belül összefüggő
        szakaszokban áll, tehát elég megtalálni, hol vált. Így a lekérdezések
        száma a FUTAMOK számától függ, nem a karakterekétől — egy formázatlan
        bekezdés két lekérdezés, nem ezer.
        """
        if not sor:
            return []
        n = len(sor)
        futamok = []
        kezd = 0
        jelen = self._jelek_poznal(poz)
        while kezd < n:
            if self._jelek_poznal(poz + n - 1) == jelen:
                vege = n                       # a bekezdés végéig egyforma
            else:
                # felezés: `lo`-n még `jelen` van, `hi`-n már más
                lo, hi = kezd, n - 1
                while hi - lo > 1:
                    kozep = (lo + hi) // 2
                    if self._jelek_poznal(poz + kozep) == jelen:
                        lo = kozep
                    else:
                        hi = kozep
                vege = hi
            futamok.append((sor[kezd:vege],) + jelen)
            kezd = vege
            if kezd < n:
                jelen = self._jelek_poznal(poz + kezd)
        return futamok

    _SIMA = (".txt", ".log", ".md", ".markdown")

    def _veszteseg(self, ut, bekezdesek) -> str:
        """Mondat arról, ha ez a formátum NEM viszi el a formázást.

        ⚠️ A néma veszteség a legrosszabb: a felhasználó menteni akart, és
        azt hiszi, minden megvan. Ezért ha van mit elveszíteni, KIMONDJUK.
        """
        if os.path.splitext(ut)[1].lower() not in self._SIMA:
            return ""
        for bek in bekezdesek:
            _sz, stilus, futamok = FM.szet(bek)
            if stilus != "Normál" or any(f[1] or f[2] or f[3]
                                         for f in futamok):
                return (" Figyelem: ez a fájltípus nem tárol formázást, "
                        "ezért a félkövér, dőlt, aláhúzott és a címsorok "
                        "ebből a fájlból kimaradnak. A szerkesztőben "
                        "megmaradtak – Word-dokumentumként mentve megőrződnek.")
        return ""

    def _ment(self) -> bool:
        if not self._ut or self._csak_olvas:
            return self._ment_maskent()
        bek = self._bekezdesek()
        try:
            FM.ment(self._ut, bek)
        except Exception as ex:
            self._allapot(f"A mentés nem sikerült: {ex}")
            return False
        self._piszkos = False
        self._cim_frissit()
        self._allapot(f"Mentve: {os.path.basename(self._ut)}."
                      + self._veszteseg(self._ut, bek))
        return True

    def _ment_maskent(self) -> bool:
        alap = self._ut
        if self._csak_olvas and alap:
            alap = os.path.splitext(alap)[0] + ".docx"
        ut = self._valaszto(mentes=True, kezdo=os.path.dirname(alap or ""))
        if not ut:
            return False
        if not os.path.splitext(ut)[1]:
            ut += ".docx"
        bek = self._bekezdesek()
        try:
            FM.ment(ut, bek)
        except Exception as ex:
            self._allapot(f"A mentés nem sikerült: {ex}")
            return False
        self._ut = ut
        self._csak_olvas = False
        self._piszkos = False
        self._cim_frissit()
        self._allapot(f"Mentve: {os.path.basename(ut)}."
                      + self._veszteseg(ut, bek))
        return True

    def _pdf_export(self):
        with wx.FileDialog(self, "Exportálás PDF-be",
                           wildcard="PDF (*.pdf)|*.pdf",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as d:
            if d.ShowModal() != wx.ID_OK:
                return
            ut = d.GetPath()
        if not ut.lower().endswith(".pdf"):
            ut += ".pdf"
        try:
            FM.ment(ut, self._bekezdesek())
        except Exception as ex:
            self._allapot(f"A PDF-export nem sikerült: {ex}")
            return
        self._allapot(f"PDF elkészült: {os.path.basename(ut)}. "
                      "A PDF-et visszaolvasni tudjuk, szerkeszteni nem.")

    # ---- fájltársítás ------------------------------------------------------

    def _tarsitas(self):
        from superdl import fileassoc
        if not fileassoc.available():
            self._allapot("A fájltársítás csak a telepített vagy hordozható "
                          "SuperDL-nél érhető el.")
            return
        mind = list(fileassoc.SZOVEG_EXTS) + list(fileassoc.SZOVEG_EXTS_OLVASO)
        most = fileassoc.szoveg_tarsitasok()
        cimkek = []
        for e in mind:
            olvas = " – csak olvasásra" if e in fileassoc.SZOVEG_EXTS_OLVASO \
                else ""
            cimkek.append(f"{e}{olvas}")
        d = wx.MultiChoiceDialog(
            self,
            "Melyik fájlokra kattintva nyíljon a Super Edit?\n\n"
            "Szóközzel jelölöd be és veszed ki. Csak a saját felhasználói "
            "beállításodat írjuk, bármikor visszavonható.",
            "Fájltársítások", cimkek)
        d.SetSelections([i for i, e in enumerate(mind) if e in most])
        try:
            if d.ShowModal() != wx.ID_OK:
                return
            kert = [mind[i] for i in d.GetSelections()]
        finally:
            d.Destroy()
        try:
            lett = fileassoc.szoveg_beallit(kert)
        except Exception as ex:
            self._allapot(f"A társítás nem sikerült: {ex}")
            return
        if lett:
            self._allapot("Ezek a fájlok mostantól a Super Editben nyílnak: "
                          + ", ".join(sorted(lett)) + ". A Windows a végső "
                          "döntést néha külön megerősítteti.")
        else:
            self._allapot("Minden fájltársítás kikapcsolva.")

    # ---- billentyűk ---------------------------------------------------------

    def _on_key(self, e):
        kod, ctrl, shift = e.GetKeyCode(), e.ControlDown(), e.ShiftDown()
        # ⚠️ A SIMA ALT-ot A WINDOWSRA BÍZZUK. A Windows magától a menüsorra
        # viszi a fókuszt, és a képernyőolvasó be is mondja. Egy ideig én
        # szimuláltam ide egy F10-et „hogy biztosan nyisson" — de a Windows
        # AKKOR MÁR MEGNYITOTTA, és a szimulált F10 rögtön vissza is zárta.
        # Ezért mondta be a képernyőolvasó, hogy „menü", majd ugrott vissza a
        # szövegbe. A javítás: ne csináljunk semmit. Ami magától működik,
        # ahhoz nem szabad hozzányúlni.
        if kod == wx.WXK_ALT:
            e.Skip()
            return
        if kod == wx.WXK_F1:
            self._sugo()
            return
        if kod == wx.WXK_F3:
            self._kovetkezo_talalat()
            return
        # Alkalmazások billentyű, és Shift+F10 azoknak, akiknek nincs ilyen
        # gombjuk (laptop). Az EVT_CONTEXT_MENU az egérrel jövő utat fedi.
        if kod == wx.WXK_WINDOWS_MENU or (shift and kod == wx.WXK_F10):
            self._helyi_menu()
            return
        if kod == wx.WXK_ESCAPE:
            if self._forditas_fut:
                self._forditas_megall = True
                self._allapot("Megállítom a fordítást a mostani darab után.")
                return
            self._felolvas_stop()
            return
        if ctrl and shift:
            if kod in (ord("I"), ord("i")):
                self._formazas_mondd()
                return
            if kod in (ord("H"), ord("h")):
                self._hol_vagyok()
                return
            if kod in (ord("K"), ord("k")):
                self._mennyi()
                return
            if kod in (ord("D"), ord("d")):
                self._terkep()
                return
            if kod in (ord("F"), ord("f")):
                self._felolvas()
                return
            if kod in (ord("A"), ord("a")):
                self._ai_lista()
                return
            if kod in (ord("C"), ord("c")):
                self._form_masol()
                return
            if kod in (ord("V"), ord("v")):
                self._form_beilleszt()
                return
            if kod in (ord("T"), ord("t")):
                self._tisztitas()
                return
            if kod in (ord("J"), ord("j")):
                self._fejezetjelolo()
                return
            if kod in (ord("R"), ord("r")):
                self._forditas()
                return
        if ctrl and not shift and kod in (ord("0"), ord("1"), ord("2"),
                                          ord("3")):
            self._stilus(kod - ord("0"))
            return
        e.Skip()

    # ---- súgó, zárás ---------------------------------------------------------

    def _sugo(self):
        d = wx.Dialog(self, title="Super Edit – súgó", size=(800, 640))
        v = wx.BoxSizer(wx.VERTICAL)
        t = wx.TextCtrl(d, value=SUGO,
                        style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        t.SetName("Super Edit súgó szövege")
        v.Add(t, 1, wx.EXPAND | wx.ALL, 8)
        v.Add(d.CreateStdDialogButtonSizer(wx.OK), 0,
              wx.ALIGN_CENTER | wx.ALL, 8)
        d.SetSizer(v)
        t.SetFocus()
        d.ShowModal()
        d.Destroy()

    def _on_close(self, e):
        if e.CanVeto() and not self._kerdez_mentest():
            e.Veto()
            return
        self._closing = True
        e.Skip()
