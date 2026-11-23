"""A Super Fájlok tallózója.

Enter belép a mappába vagy megnyitja a fájlt. Backspace visszalép.
A műveletek a bal Alt menüsorban és a jobb klikkes helyi menüben vannak.
A Nézet menü két ágat ad: a Tab a bal és a jobb oldal között jár.
A Ctrl+C másol, a Ctrl+X kivág, a Ctrl+V a másik oldal mappájába illeszt,
a meglévő óvatos másolóval. Magától nem ír felül.
"""

import math
import os
import struct
import threading
import time

import wx

from . import tarsitas

try:
    import winsound
except Exception:
    winsound = None


def lista_sor(nev: str, mappa: bool) -> str:
    """A név elöl van, hogy a betűugrás a mappát is megtalálja."""
    if mappa:
        return "%s, mappa" % nev
    return nev


def talalat_sor(ut: str, gyoker: str) -> str:
    nev = os.path.basename(ut.rstrip("\\/")) or ut
    szulo = os.path.dirname(ut.rstrip("\\/"))
    try:
        rel = os.path.relpath(szulo, gyoker)
    except ValueError:
        rel = szulo
    hely = "" if rel in (".", "") else ", %s" % rel
    if os.path.isdir(ut):
        return "%s, mappa%s" % (nev, hely)
    return "%s%s" % (nev, hely)


def keres(gyoker: str, szoveg: str, mod: str, cancel=None) -> list[str]:
    """mod: nev vagy tipus. A név részlet mappát és fájlt is talál.
    A típus csak a fájl végét nézi, például mkv."""
    nyers = (szoveg or "").strip().lower().lstrip(".")
    if not nyers or not gyoker:
        return []
    veg = "." + nyers
    talalat = []

    def megall() -> bool:
        return bool(cancel and cancel())

    for dirpath, dirnames, filenames in os.walk(gyoker, onerror=lambda _e: None):
        if megall():
            break
        bent = []
        for nev in dirnames:
            teljes = os.path.join(dirpath, nev)
            if _csatolas(teljes):
                continue
            bent.append(nev)
            if mod == "nev" and nyers in nev.lower():
                talalat.append(teljes)
        dirnames[:] = bent
        for nev in filenames:
            if megall():
                break
            if mod == "tipus":
                if not nev.lower().endswith(veg):
                    continue
            elif nyers not in nev.lower():
                continue
            talalat.append(os.path.join(dirpath, nev))
    talalat.sort(key=lambda ut: (os.path.basename(ut).lower(), ut.lower()))
    return talalat


def _csatolas(ut: str) -> bool:
    try:
        from .masolo import _csatolas as masolo_csatolas
        return masolo_csatolas(ut)
    except Exception:
        return False


def _katt(melyik: str):
    """Halk, rövid kattanás. A belépés magasabb, a visszalépés mélyebb."""
    if winsound is None:
        return
    rate = 22050
    if melyik == "be":
        freq, ms, amp = 1680, 16, 2200
    else:
        freq, ms, amp = 620, 32, 2000
    n = max(1, int(rate * ms / 1000))
    mintak = []
    for i in range(n):
        csendesedik = (1 - i / n) ** 2
        mintak.append(int(amp * csendesedik * math.sin(2 * math.pi * freq * i / rate)))
    adat = struct.pack("<%dh" % n, *mintak)
    fej = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(adat), b"WAVE", b"fmt ", 16,
        1, 1, rate, rate * 2, 2, 16, b"data", len(adat))
    try:
        winsound.PlaySound(
            fej + adat, winsound.SND_MEMORY | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass


def _meghajtok() -> list[str]:
    try:
        import string
        from ctypes import windll
        maszk = windll.kernel32.GetLogicalDrives()
        return ["%s:\\" % string.ascii_uppercase[i]
                for i in range(26) if maszk & (1 << i)]
    except Exception:
        return [os.path.abspath(os.sep)]


class _Ag:
    def __init__(self, oldal, cim, lista, doboz):
        self.oldal = oldal
        self.cim = cim
        self.lista = lista
        self.doboz = doboz
        self.mappa = ""
        self.nevek = []
        self.szurt = False
        self.utak = None


class TallozoFrame(wx.Frame):
    def __init__(self, main, mappa=None, ketag=False):
        szulo = main if isinstance(main, wx.Window) else None
        super().__init__(szulo, title="SuperDL – Tallózó", size=(760, 560))
        self.main = main
        self._ketag = False
        self._vagolap = []
        self._vagolap_muv = ""
        self._vagolap_cel = None
        self._cancel = threading.Event()
        self._dolgozik = False
        self._mondott = ""
        self._mondott_szaz = -1
        self._mondott_ido = 0.0
        kezdo = os.path.abspath(mappa) if mappa else ""
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        sor = wx.BoxSizer(wx.HORIZONTAL)
        self._bal = self._uj_ag(p, "bal", "Bal oldal", "Bal oldal tartalma")
        self._jobb = self._uj_ag(p, "jobb", "Jobb oldal", "Jobb oldal tartalma")
        self._aktiv = self._bal
        self._bal.mappa = kezdo
        sor.Add(self._bal.doboz, 1, wx.EXPAND | wx.RIGHT, 4)
        sor.Add(self._jobb.doboz, 1, wx.EXPAND | wx.LEFT, 4)
        v.Add(sor, 1, wx.EXPAND)
        p.SetSizer(v)
        self.CreateStatusBar()
        self._menusor()
        self.Bind(wx.EVT_CHAR_HOOK, self._billentyu)
        self.Bind(wx.EVT_CLOSE, self._zar)
        self._tolts(self._bal)
        self._jobb.doboz.Show(False)
        if ketag:
            self._ketag_allit(True, mondja=False)
        self.CentreOnParent()
        self.Show()
        self.lista.SetFocus()
        if self._ketag:
            self._mond("Két ág. A Tab a másik oldalra lép. "
                       "A Ctrl+C másol, a Ctrl+X kivág, a Ctrl+V beilleszt.")

    def _uj_ag(self, szulo, oldal, cimke, lista_nev) -> _Ag:
        doboz = wx.Panel(szulo)
        v = wx.BoxSizer(wx.VERTICAL)
        cim = wx.StaticText(doboz, label=cimke)
        cim.SetName(cimke)
        v.Add(cim, 0, wx.ALL, 8)
        lista = wx.ListBox(doboz, style=wx.LB_EXTENDED)
        lista.SetName(lista_nev)
        lista.Bind(wx.EVT_LISTBOX_DCLICK, self._nyit)
        lista.Bind(wx.EVT_LISTBOX, self._kijeloles)
        lista.Bind(wx.EVT_CONTEXT_MENU, self._helyi)
        lista.Bind(wx.EVT_SET_FOCUS, lambda e, o=oldal: self._fokusz(o, e))
        v.Add(lista, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        doboz.SetSizer(v)
        return _Ag(oldal, cim, lista, doboz)

    def _fokusz(self, oldal, event):
        self._aktiv = self._bal if oldal == "bal" else self._jobb
        event.Skip()

    @property
    def lista(self):
        return self._aktiv.lista

    @property
    def cim(self):
        return self._aktiv.cim

    @property
    def _mappa(self):
        return self._aktiv.mappa

    @_mappa.setter
    def _mappa(self, ertek):
        self._aktiv.mappa = ertek

    @property
    def _nevek(self):
        return self._aktiv.nevek

    @_nevek.setter
    def _nevek(self, ertek):
        self._aktiv.nevek = ertek

    @property
    def _szurt(self):
        return self._aktiv.szurt

    @_szurt.setter
    def _szurt(self, ertek):
        self._aktiv.szurt = ertek

    @property
    def _utak(self):
        return self._aktiv.utak

    @_utak.setter
    def _utak(self, ertek):
        self._aktiv.utak = ertek

    def _masik(self) -> _Ag:
        return self._jobb if self._aktiv is self._bal else self._bal

    def _oldal_nev(self, ag: _Ag) -> str:
        return "bal" if ag is self._bal else "jobb"

    def _mappa_nev(self, mappa: str) -> str:
        if not mappa:
            return "Ez a gép"
        return os.path.basename(mappa.rstrip("\\/")) or mappa

    def _tolts(self, ag=None):
        regi = self._aktiv
        if ag is not None:
            self._aktiv = ag
        try:
            self._tolts_aktiv()
        finally:
            self._aktiv = regi

    def _tolts_aktiv(self):
        self._utak = None
        if not self._mappa:
            self.cim.SetLabel("Ez a gép")
            self.cim.SetName("%s oldal. Ez a gép" % (
                "Bal" if self._aktiv is self._bal else "Jobb"))
            self._nevek = _meghajtok()
            self.lista.Set(self._nevek or ["(nincs meghajtó)"])
            if self._nevek:
                self.lista.SetSelection(0)
            self.SetStatusText("%d meghajtó." % len(self._nevek))
            return
        self.cim.SetLabel(self._mappa)
        self.cim.SetName("%s oldal. %s" % (
            "Bal" if self._aktiv is self._bal else "Jobb", self._mappa))
        self.cim.Wrap(680)
        try:
            nevek = os.listdir(self._mappa)
        except OSError as exc:
            self.SetStatusText("A mappa nem olvasható: %s" % exc)
            self._nevek = []
            self.lista.Set(["(nem olvasható)"])
            return
        mappak, fajlok = [], []
        for nev in nevek:
            teljes = os.path.join(self._mappa, nev)
            (mappak if os.path.isdir(teljes) else fajlok).append(nev)
        mappak.sort(key=str.lower)
        fajlok.sort(key=str.lower)
        self._nevek = mappak + fajlok
        sorok = [lista_sor(n, True) for n in mappak] + [lista_sor(n, False) for n in fajlok]
        self.lista.Set(sorok or ["(üres mappa)"])
        if self._nevek:
            self.lista.SetSelection(0)
        self.SetStatusText("%d elem." % len(self._nevek))

    def _ut_az_indexen(self, i: int) -> str:
        if self._utak is not None:
            if i < 0 or i >= len(self._utak):
                return ""
            return self._utak[i]
        if i < 0 or i >= len(self._nevek):
            return ""
        if not self._mappa:
            return self._nevek[i]
        return os.path.join(self._mappa, self._nevek[i])

    def _fokusz_index(self) -> int:
        """A többes listán a GetSelection üres. A fókuszban lévő sor kell."""
        try:
            import ctypes
            LB_GETCURSEL = 0x0188
            i = ctypes.windll.user32.SendMessageW(
                int(self.lista.GetHandle()), LB_GETCURSEL, 0, 0)
            if 0 <= int(i) < self.lista.GetCount():
                return int(i)
        except Exception:
            pass
        kijelolt = [i for i in self.lista.GetSelections() if i >= 0]
        return kijelolt[0] if kijelolt else -1

    def _kijelolt_indexek(self) -> list[int]:
        indexek = [i for i in self.lista.GetSelections() if i >= 0]
        if indexek:
            return indexek
        i = self._fokusz_index()
        return [i] if i >= 0 else []

    def _kijelolt_utak(self) -> list[str]:
        utak = []
        for i in self._kijelolt_indexek():
            ut = self._ut_az_indexen(i)
            if ut:
                utak.append(ut)
        return utak

    def _kivalasztott(self) -> str:
        return self._ut_az_indexen(self._fokusz_index())

    def _mindet(self, _e=None):
        n = len(self._utak) if self._utak is not None else len(self._nevek)
        if n <= 0:
            self._mond("Nincs mit kijelölni.")
            return
        for i in range(n):
            self.lista.SetSelection(i)
        mondat = "Minden elem kijelölve. %d elem." % n
        self.SetStatusText(mondat)
        self._mond(mondat)

    def _kijeloles(self, event):
        event.Skip()
        if not wx.GetKeyState(wx.WXK_SHIFT):
            return
        db = len(self.lista.GetSelections())
        if db > 1:
            self._mond("%d elem kijelölve." % db)

    def _nyit(self, _e=None):
        ut = self._kivalasztott()
        if not ut:
            self.SetStatusText("Előbb jelölj ki egy elemet.")
            return
        if os.path.isdir(ut):
            self._szurt = False
            self._mappa = ut
            self._tolts()
            _katt("be")
            self._mond(os.path.basename(ut.rstrip("\\/")))
            return
        mondat = tarsitas.nyit(self.main, ut)
        self.SetStatusText(mondat)
        self._mond(mondat)

    def _vissza(self, _e=None):
        if self._szurt:
            self._szurt = False
            self._tolts()
            _katt("ki")
            self._mond(os.path.basename(self._mappa.rstrip("\\/")) or self._mappa)
            return
        if not self._mappa:
            return
        csupasz = self._mappa.rstrip("\\/")
        szulo = os.path.dirname(csupasz)
        if (not szulo or szulo == csupasz or len(csupasz) <= 3):
            self._mappa = ""
            nev = "Ez a gép"
        else:
            if len(szulo) == 2 and szulo[1] == ":":
                szulo += "\\"
            self._mappa = szulo
            nev = os.path.basename(szulo.rstrip("\\/")) or szulo
        self._tolts()
        _katt("ki")
        self._mond(nev)

    def _atvisz(self, _e=None):
        ut = self._kivalasztott()
        if not ut:
            self.SetStatusText("Előbb jelölj ki egy fájlt vagy mappát.")
            return
        host = getattr(self.main, "_module_host", None)
        ablak = host.open_window("fajlok_module") if host else None
        if ablak is None or not hasattr(ablak, "atvesz"):
            self.SetStatusText("A másoló ablak nem nyílt meg.")
            return
        ablak.atvesz([ut])

    def _latok(self, _e=None):
        if not self._mappa:
            self._mond("%d meghajtó." % len(self._nevek))
            return
        fajl = mappa = bajt = 0
        try:
            for nev in os.listdir(self._mappa):
                teljes = os.path.join(self._mappa, nev)
                if os.path.isdir(teljes):
                    mappa += 1
                else:
                    fajl += 1
                    try:
                        bajt += os.path.getsize(teljes)
                    except OSError:
                        pass
        except OSError as exc:
            self.SetStatusText(str(exc))
            return
        from .masolo import meret_szoveg
        mondat = "%d mappa, %d fájl, %s." % (mappa, fajl, meret_szoveg(bajt))
        self.SetStatusText(mondat)
        self._mond(mondat)

    def _kulso_helyek(self, _e=None):
        from .helywin import HelyFrame
        HelyFrame(self.main)
        self._mond("Külső mappák. Itt FTP-t és SFTP-t lehet menteni és megnyitni.")

    def _google_drive(self, _e=None):
        mondat = ("A Google Drive még nincs csatolva. A Google saját engedélye "
                  "kell hozzá, azt még nem kérem el. Más felhő innen nem érhető el.")
        self.SetStatusText(mondat)
        self._mond(mondat)
        if wx.MessageBox(
                mondat + " Megnyissam a Drive-ot a böngészőben? Csatolás ettől még nem lesz.",
                "Google Drive",
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_INFORMATION, self) != wx.YES:
            return
        import webbrowser
        webbrowser.open("https://drive.google.com")

    def _keres(self, _e=None):
        if not self._mappa:
            self._mond("Előbb lépj be egy mappába. A keresés ott és az almappáiban megy.")
            return
        if getattr(self, "_keres_fut", False):
            self._mond("A keresés még tart. Az Escape megállítja.")
            return
        dlg = KeresesDialog(self)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        szoveg, mod = dlg.ertek()
        dlg.Destroy()
        if not (szoveg or "").strip().lstrip("."):
            self._mond("Írd be, mit keresel.")
            return
        self._keres_cancel = threading.Event()
        self._keres_fut = True
        gyoker = self._mappa
        micsoda = "Fájltípus" if mod == "tipus" else "Név részlete"
        self._mond("%s: %s. Keresés folyik a mappában és az almappáiban." % (
            micsoda, szoveg.strip()))

        def munka():
            try:
                talalat = keres(gyoker, szoveg, mod, self._keres_cancel.is_set)
            except Exception as exc:
                wx.CallAfter(self._keres_vege, [], gyoker, str(exc))
                return
            wx.CallAfter(self._keres_vege, talalat, gyoker, "")

        threading.Thread(target=munka, daemon=True).start()

    def _keres_vege(self, talalat, gyoker, hiba):
        self._keres_fut = False
        if hiba:
            self.SetStatusText(hiba)
            self._mond(hiba)
            return
        self._utak = list(talalat)
        self._nevek = [os.path.basename(ut.rstrip("\\/")) or ut for ut in talalat]
        self._szurt = True
        sorok = [talalat_sor(ut, gyoker) for ut in talalat]
        self.lista.Set(sorok or ["(nincs találat)"])
        if talalat:
            self.lista.SetSelection(0)
        mondat = ("%d találat. A Backspace a mappához visz vissza. "
                  "A listából törölhetsz, másolhatsz és megnyithatsz."
                  % len(talalat))
        if self._keres_cancel.is_set():
            mondat = "A keresés megállt. " + mondat
        self.SetStatusText(mondat)
        self._mond(mondat)
        self.lista.SetFocus()

    def _gyujtemeny(self, _e=None):
        if not self._mappa:
            return
        dlg = wx.SingleChoiceDialog(
            self, "Melyik gyűjteményt mutassam ebben a mappában?",
            "Gyűjtemény",
            ["A mai fájlok", "Ami nagyobb egy gigabájtnál",
             "Ami tegnap óta változott", "Üres almappák"])
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        valasz = dlg.GetStringSelection()
        dlg.Destroy()
        import time
        most = time.time()
        nap = 24 * 3600
        talalat = []
        for nev in self._nevek:
            teljes = os.path.join(self._mappa, nev)
            try:
                adat = os.stat(teljes)
            except OSError:
                continue
            if valasz.startswith("A mai") and not os.path.isdir(teljes):
                if time.localtime(adat.st_mtime)[:3] == time.localtime(most)[:3]:
                    talalat.append(nev)
            elif valasz.startswith("Ami nagyobb") and not os.path.isdir(teljes):
                if adat.st_size >= 1024 ** 3:
                    talalat.append(nev)
            elif valasz.startswith("Ami tegnap") and adat.st_mtime >= most - nap:
                talalat.append(nev)
            elif valasz.startswith("Üres") and os.path.isdir(teljes):
                try:
                    if not os.listdir(teljes):
                        talalat.append(nev)
                except OSError:
                    pass
        self._utak = None
        self.lista.Set(talalat or ["(nincs találat)"])
        self._nevek = talalat
        self._szurt = True
        self.SetStatusText("%d találat. A Backspace a teljes mappát hozza." % len(talalat))
        if talalat:
            self.lista.SetSelection(0)

    def _osszevet(self, _e=None):
        if not self._mappa:
            return
        from superdl import fajlvalaszto
        masik = fajlvalaszto.valassz_mappat(self, "A másik mappa", mondd=self._mond)
        if not masik:
            return
        from .osszevet import mondat
        szoveg = mondat(self._mappa, masik)
        self.SetStatusText(szoveg)
        self._mond(szoveg)
        wx.MessageBox(szoveg, "Összevetés", wx.OK | wx.ICON_INFORMATION, self)

    def _tomorit(self, _e=None):
        ut = self._kivalasztott()
        if not ut:
            return
        from .csomag import FORMAK
        dlg = wx.SingleChoiceDialog(self, "Milyen formátumba?", "Tömörítés", list(FORMAK))
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        forma = dlg.GetStringSelection()
        dlg.Destroy()
        cel = ut.rstrip("\\/") + "." + forma
        from .csomag import tomorit
        try:
            tomorit([ut], cel, forma)
        except Exception as exc:
            self.SetStatusText(str(exc))
            self._mond(str(exc))
            return
        self._tolts()
        self.SetStatusText("Becsomagolva: %s" % os.path.basename(cel))
        self._mond("Becsomagolva.")

    def _kibont(self, _e=None):
        ut = self._kivalasztott()
        if not ut or os.path.isdir(ut):
            self.SetStatusText("Jelölj ki egy csomagot.")
            return
        cel = os.path.splitext(ut)[0]
        if cel.endswith(".tar"):
            cel = os.path.splitext(cel)[0]
        from .csomag import kibont
        try:
            db = kibont(ut, cel)
        except Exception as exc:
            self.SetStatusText(str(exc))
            self._mond(str(exc))
            return
        self._tolts()
        mondat = "Kibontva, %d elem, ide: %s" % (db, os.path.basename(cel))
        self.SetStatusText(mondat)
        self._mond(mondat)

    def _onkibonto(self, _e=None):
        ut = self._kivalasztott()
        if not ut:
            return
        alap = os.path.splitext(ut.rstrip("\\/"))[0]
        from .csomag import onkibonto
        try:
            indito, _zip, jegyzek = onkibonto([ut], alap)
        except Exception as exc:
            self.SetStatusText(str(exc))
            return
        self._tolts()
        mondat = "Önkibontó kész: %s. A tartalomjegyzék: %s." % (
            os.path.basename(indito), os.path.basename(jegyzek))
        self.SetStatusText(mondat)
        self._mond(mondat)

    def _atnevez(self, _e=None):
        if self._utak is not None:
            self._mond("A találati listában az Átnevezés menüpont egy elemet nevez át.")
            return
        if not self._mappa:
            return
        mit = wx.GetTextFromUser("Mit cseréljek a nevekben?", "Átnevezés", "", self)
        if not mit:
            return
        mire = wx.GetTextFromUser("Mire cseréljem?", "Átnevezés", "", self)
        parok = []
        for nev in self._nevek:
            if mit in nev:
                parok.append((nev, nev.replace(mit, mire)))
        if not parok:
            self.SetStatusText("Egy névben sincs benne: %s" % mit)
            return
        elonezet = "\n".join("%s → %s" % (a, b) for a, b in parok[:8])
        if wx.MessageBox(
                "Így változnának, az első nyolc:\n%s\n\nÁtírjam mind a %d nevet?"
                % (elonezet, len(parok)),
                "Átnevezés", wx.YES | wx.NO | wx.ICON_QUESTION, self) != wx.YES:
            return
        for regi, uj in parok:
            os.rename(os.path.join(self._mappa, regi), os.path.join(self._mappa, uj))
        self._tolts()
        self._mond("%d fájl átnevezve." % len(parok))

    def _menusor(self):
        sav = wx.MenuBar()
        fajl = wx.Menu()
        self._mi(fajl, "&Megnyitás", self._nyit)
        self._mi(fajl, "Megnyitás &mással…", self._massal)
        self._mi(fajl, "&Társítás…", self._tarsitas)
        fajl.AppendSeparator()
        self._mi(fajl, "Ú&j mappa…", self._uj)
        self._mi(fajl, "&Törlés", self._torol)
        self._mi(fajl, "&Tulajdonságok", self._tulajdonsag)
        fajl.AppendSeparator()
        self._mi(fajl, "Másolat &mentése…", self._atvisz)
        fajl.AppendSeparator()
        self._mi(fajl, "&Bezárás", lambda: self.Close())
        sav.Append(fajl, "&Fájl")

        szerk = wx.Menu()
        self._mi(szerk, "&Másolás és áthelyezés…", self._atvisz)
        self._mi(szerk, "&Átnevezés…", self._atnevez_egy)
        self._mi(szerk, "Nevek &cseréje…", self._atnevez)
        szerk.AppendSeparator()
        self._mi(szerk, "Minden kijelölése, Ctrl+A", self._mindet)
        self._mi(szerk, "Másolás, Ctrl+C", lambda: self._vagolapra("masol"))
        self._mi(szerk, "Kivágás, Ctrl+X", lambda: self._vagolapra("athelyez"))
        self._mi(szerk, "Beillesztés, Ctrl+V", self._beilleszt)
        sav.Append(szerk, "&Szerkesztés")

        nezet = wx.Menu()
        self._egy_ag = self._mi(nezet, "&Egy ág", lambda: self._ketag_allit(False), jelolo=True)
        self._ket_ag = self._mi(nezet, "&Két ág", lambda: self._ketag_allit(True), jelolo=True)
        self._egy_ag.Check(True)
        sav.Append(nezet, "&Nézet")

        eszkoz = wx.Menu()
        self._mi(eszkoz, "&Keresés…\tCtrl+F", self._keres)
        self._mi(eszkoz, "Mit &látok?", self._latok)
        self._mi(eszkoz, "&Gyűjtemény…", self._gyujtemeny)
        self._mi(eszkoz, "Össze&vet…", self._osszevet)
        eszkoz.AppendSeparator()
        self._mi(eszkoz, "&Tömörít…", self._tomorit)
        self._mi(eszkoz, "&Kibont…", self._kibont)
        self._mi(eszkoz, "Ön&kibontó…", self._onkibonto)
        sav.Append(eszkoz, "&Eszközök")

        kulso = wx.Menu()
        self._mi(kulso, "&FTP és SFTP helyek…", self._kulso_helyek)
        self._mi(kulso, "&Google Drive…", self._google_drive)
        sav.Append(kulso, "&Külső mappák")
        self.SetMenuBar(sav)

    def _mi(self, menu, cimke, fv, jelolo=False):
        it = menu.Append(
            wx.ID_ANY, cimke,
            kind=wx.ITEM_CHECK if jelolo else wx.ITEM_NORMAL)
        self.Bind(wx.EVT_MENU, lambda e, f=fv: f(), it)
        return it

    def _helyi(self, _e=None):
        menu = wx.Menu()
        for cimke, fv in (
                ("Megnyitás", self._nyit),
                ("Megnyitás mással…", self._massal),
                ("Társítás…", self._tarsitas),
                ("Másolás, Ctrl+C", lambda: self._vagolapra("masol")),
                ("Kivágás, Ctrl+X", lambda: self._vagolapra("athelyez")),
                ("Beillesztés, Ctrl+V", self._beilleszt),
                ("Másolás és áthelyezés…", self._atvisz),
                ("Átnevezés…", self._atnevez_egy),
                ("Törlés", self._torol)):
            it = menu.Append(wx.ID_ANY, cimke)
            self.Bind(wx.EVT_MENU, lambda e, f=fv: f(), it)
        menu.AppendSeparator()
        for cimke, fv in (
                ("Keresés…", self._keres),
                ("Mit látok?", self._latok),
                ("Gyűjtemény…", self._gyujtemeny),
                ("Összevet…", self._osszevet),
                ("Tömörít…", self._tomorit),
                ("Kibont…", self._kibont),
                ("Önkibontó…", self._onkibonto)):
            it = menu.Append(wx.ID_ANY, cimke)
            self.Bind(wx.EVT_MENU, lambda e, f=fv: f(), it)
        self.PopupMenu(menu)
        menu.Destroy()

    def _uj(self, _e=None):
        if not self._mappa:
            self.SetStatusText("Előbb lépj be egy meghajtóra.")
            return
        nev = wx.GetTextFromUser("Az új mappa neve:", "Új mappa", "Új mappa", self)
        nev = (nev or "").strip().rstrip(". ")
        if not nev or nev in (".", "..") or any(c in nev for c in '\\/:*?"<>|'):
            return
        cel = os.path.join(self._mappa, nev)
        try:
            os.mkdir(cel)
        except OSError as exc:
            self.SetStatusText(str(exc))
            self._mond(str(exc))
            return
        self._tolts()
        self.SetStatusText("Új mappa: %s" % nev)
        self._mond("Új mappa: %s" % nev)

    def _torol(self, _e=None):
        if not self._mappa:
            self.SetStatusText("Meghajtót innen nem törlök.")
            return
        utak = self._kijelolt_utak()
        if not utak:
            return
        if len(utak) == 1:
            nev = os.path.basename(utak[0].rstrip("\\/"))
            kerdes = "Töröljem: %s?" % nev
        else:
            nev = "%d elem" % len(utak)
            kerdes = "Töröljem mind a %d kijelölt elemet?" % len(utak)
        if wx.MessageBox(
                kerdes, "Törlés",
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self) != wx.YES:
            return
        import shutil
        hibak = []
        for ut in utak:
            try:
                if os.path.isdir(ut):
                    shutil.rmtree(ut)
                else:
                    os.remove(ut)
            except OSError as exc:
                hibak.append("%s: %s" % (os.path.basename(ut.rstrip("\\/")), exc))
        if self._utak is not None:
            megvan = [ut for ut in self._utak if os.path.exists(ut)]
            self._utak = megvan
            self._nevek = [os.path.basename(ut.rstrip("\\/")) or ut for ut in megvan]
            sorok = [talalat_sor(ut, self._mappa) for ut in megvan]
            self.lista.Set(sorok or ["(nincs találat)"])
            if megvan:
                self.lista.SetSelection(0)
        else:
            self._tolts()
        if hibak:
            mondat = "Törölve: %d elem. %d nem sikerült." % (
                len(utak) - len(hibak), len(hibak))
        else:
            mondat = "Törölve: %s." % nev
        self.SetStatusText(mondat)
        self._mond(mondat)

    def _atnevez_egy(self, _e=None):
        if not self._mappa:
            self.SetStatusText("Meghajtót innen nem nevezek át.")
            return
        ut = self._kivalasztott()
        if not ut:
            return
        regi = os.path.basename(ut.rstrip("\\/"))
        uj = wx.GetTextFromUser("Új név:", "Átnevezés", regi, self)
        uj = (uj or "").strip().rstrip(". ")
        if not uj or uj == regi or any(c in uj for c in '\\/:*?"<>|'):
            return
        try:
            os.rename(ut, os.path.join(os.path.dirname(ut), uj))
        except OSError as exc:
            self.SetStatusText(str(exc))
            self._mond(str(exc))
            return
        self._tolts()
        self.SetStatusText("Új név: %s" % uj)
        self._mond("Új név: %s" % uj)

    def _tulajdonsag(self, _e=None):
        ut = self._kivalasztott()
        if not ut:
            return
        import time
        nev = os.path.basename(ut.rstrip("\\/")) or ut
        try:
            adat = os.stat(ut)
        except OSError as exc:
            self.SetStatusText(str(exc))
            return
        if os.path.isdir(ut):
            fajta = "Mappa"
            meret = ""
        else:
            fajta = "Fájl"
            from .masolo import meret_szoveg
            meret = ", %s" % meret_szoveg(adat.st_size)
        ido = time.strftime("%Y. %m. %d. %H:%M", time.localtime(adat.st_mtime))
        mondat = "%s. %s%s. Módosítva: %s." % (nev, fajta, meret, ido)
        self.SetStatusText(mondat)
        self._mond(mondat)

    def _ketag_allit(self, be: bool, mondja=True):
        self._ketag = bool(be)
        self._egy_ag.Check(not self._ketag)
        self._ket_ag.Check(self._ketag)
        self._jobb.doboz.Show(self._ketag)
        if self._ketag and not self._jobb.mappa and self._bal.mappa:
            self._jobb.mappa = self._bal.mappa
        if self._ketag and not self._jobb.nevek:
            self._tolts(self._jobb)
        self.SetSize((1100, 560) if self._ketag else (760, 560))
        self.Layout()
        if not self._ketag and self._aktiv is self._jobb:
            self._aktiv = self._bal
            self._bal.lista.SetFocus()
        if not mondja:
            return
        if self._ketag:
            self._mond("Két ág. A Tab a másik oldalra lép.")
        else:
            self._mond("Egy ág.")

    def _listan_van(self) -> bool:
        fokusz = wx.Window.FindFocus()
        return fokusz in (self._bal.lista, self._jobb.lista)

    def _vagolapra(self, muvelet: str):
        if self._dolgozik:
            self._mond("Még tart az előző művelet.")
            return
        if not self._ketag:
            mondat = "Ehhez a két ág kell. A Nézet menüben kapcsolható be."
            self.SetStatusText(mondat)
            self._mond(mondat)
            return
        utak = self._kijelolt_utak()
        if not utak or not self._mappa:
            self._mond("Előbb jelölj ki egy fájlt vagy mappát.")
            return
        masik = self._masik()
        from .masolo import vagolap_mondat
        self._vagolap = utak
        self._vagolap_muv = muvelet
        self._vagolap_cel = masik
        if not masik.mappa:
            mondat = "%d elem a vágólapon. A másik ágon előbb lépj be egy mappába." % len(utak)
            if muvelet == "athelyez":
                mondat = ("Kivágás. " + mondat
                          + " A forrás csak a kész másolat után törlődik.")
        else:
            mondat = vagolap_mondat(
                muvelet, self._oldal_nev(masik), masik.mappa, len(utak))
        self.SetStatusText(mondat)
        self._mond(mondat)

    def _beilleszt(self, _e=None):
        if self._dolgozik:
            self._mond("Még tart az előző művelet.")
            return
        if not self._ketag:
            mondat = "Ehhez a két ág kell. A Nézet menüben kapcsolható be."
            self.SetStatusText(mondat)
            self._mond(mondat)
            return
        from .masolo import beillesztes_oka
        cel_ag = self._cel_ag()
        oka = beillesztes_oka(self._vagolap, cel_ag.mappa)
        if oka:
            self.SetStatusText(oka)
            self._mond(oka)
            return
        valasz = wx.SingleChoiceDialog(
            self,
            "A cél a %s oldal: %s\nHa a név már megvan, mi történjen?"
            % (self._oldal_nev(cel_ag), cel_ag.mappa),
            "Beillesztés",
            ["Kihagyja a meglévőt", "Új néven menti", "Felülírja"])
        valasz.SetSelection(0)
        if valasz.ShowModal() != wx.ID_OK:
            valasz.Destroy()
            self._mond("Mégsem. Nem indult el.")
            return
        utkozes = ("kihagy", "ujnev", "felulir")[valasz.GetSelection()]
        valasz.Destroy()
        utkozes_szoveg = {
            "kihagy": "Ütközéskor a meglévőt kihagyja.",
            "ujnev": "Ütközéskor új néven menti.",
            "felulir": "Ütközéskor felülírja.",
        }[utkozes]
        extra = ""
        if self._vagolap_muv == "athelyez":
            extra = " A forrás csak a kész, ellenőrzött másolat után törlődik."
        tervezett = utkozes_szoveg + extra
        self._indit_atvitel(
            list(self._vagolap), cel_ag.mappa, self._vagolap_muv, utkozes, tervezett)

    def _indit_atvitel(self, elemek, cel, muvelet, utkozes, tervezett=""):
        from . import masolo
        self._cancel.clear()
        self._dolgozik = True
        self._mondott = ""
        self._mondott_szaz = -1
        self._mondott_ido = 0.0
        self._atvitel_muv = muvelet
        ige = "Áthelyezés" if muvelet == "athelyez" else "Másolás"
        indulo = "Számlálás. %s folyik, aztán egyenként viszem a fájlokat." % ige
        self.SetStatusText(indulo)
        self._mond(indulo)

        def munka():
            try:
                masolo.futtat(
                    elemek, cel, muvelet, utkozes,
                    lambda j: wx.CallAfter(self._atvitel_frissit, j),
                    self._cancel.is_set,
                    jovahagy=lambda mondat: self._atvitel_jovahagy(
                        mondat + " " + tervezett))
            except Exception as exc:
                wx.CallAfter(self.SetStatusText, "Hiba: %s" % exc)
                wx.CallAfter(self._atvitel_vege)

        threading.Thread(target=munka, daemon=True).start()

    def _atvitel_jovahagy(self, mondat: str) -> bool:
        doboz = {"ok": False}
        kesz = threading.Event()

        def kerdes():
            doboz["ok"] = wx.MessageBox(
                mondat + " Indulhat?", "Terv",
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self) == wx.YES
            kesz.set()

        wx.CallAfter(kerdes)
        kesz.wait()
        return doboz["ok"]

    def _atvitel_frissit(self, jel):
        from .masolo import folyamat_szoveg
        szoveg = folyamat_szoveg(getattr(self, "_atvitel_muv", "masol"), jel)
        self.SetStatusText(szoveg)
        most = time.monotonic()
        szaz = jel.szazalek()
        if ((jel.kesz or szaz - self._mondott_szaz >= 5
                or most - self._mondott_ido >= 8)
                and szoveg and szoveg != self._mondott):
            self._mond(szoveg)
            self._mondott = szoveg
            self._mondott_ido = most
            self._mondott_szaz = szaz
        if jel.kesz:
            if self._vagolap_muv == "athelyez" and not jel.hibak and not jel.megszakitva:
                self._vagolap = []
                self._vagolap_muv = ""
            self._tolts(self._bal)
            if self._ketag:
                self._tolts(self._jobb)
            self._atvitel_vege()

    def _atvitel_vege(self):
        self._dolgozik = False

    def _cel_ag(self):
        """A cél az az ág, amelyik a másoláskor a másik oldal volt.

        Ha utána a cél ágára lépsz, a beillesztés akkor is oda megy,
        nem fordul vissza a forrás mappájába.
        """
        ag = getattr(self, "_vagolap_cel", None)
        if ag is self._bal or ag is self._jobb:
            return ag
        return self._masik()

    def _helyzet(self, _e=None):
        if self._dolgozik:
            szoveg = self.GetStatusBar().GetStatusText() or "A művelet tart."
        else:
            szoveg = "Most nem másol és nem helyez át."
        self.SetStatusText(szoveg)
        self._mond(szoveg)

    def _masikra(self):
        if not self._ketag:
            return
        self._aktiv = self._masik()
        self._aktiv.lista.SetFocus()
        mondat = "%s oldal. %s." % (
            "Bal" if self._aktiv is self._bal else "Jobb",
            self._mappa_nev(self._mappa))
        self.SetStatusText(mondat)
        self._mond(mondat)

    def _zar(self, event):
        if self._dolgozik:
            self._cancel.set()
        event.Skip()

    def _billentyu(self, event):
        if event.AltDown() and not event.ControlDown():
            event.Skip()
            return
        kod = event.GetKeyCode()
        if (self._ketag and kod == wx.WXK_TAB and not event.ControlDown()
                and self._listan_van()):
            self._masikra()
            return
        if event.ControlDown() and not event.AltDown() and self._listan_van():
            if kod in (ord("A"), ord("a")):
                self._mindet()
                return
            if kod in (ord("C"), ord("c")):
                self._vagolapra("masol")
                return
            if kod in (ord("X"), ord("x")):
                self._vagolapra("athelyez")
                return
            if kod in (ord("V"), ord("v")):
                self._beilleszt()
                return
        if not self._listan_van() and kod not in (
                wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER, wx.WXK_BACK, wx.WXK_DELETE):
            event.Skip()
            return
        if kod in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._nyit()
        elif kod == wx.WXK_BACK:
            self._vissza()
        elif kod == wx.WXK_DELETE:
            self._torol()
        elif kod == wx.WXK_F8:
            self._helyzet()
        elif kod == wx.WXK_ESCAPE and getattr(self, "_keres_fut", False):
            self._keres_cancel.set()
            self._mond("A keresést megállítom.")
        elif kod == wx.WXK_ESCAPE and self._dolgozik:
            self._cancel.set()
            self._mond("Megszakítás, a mostani fájl után megáll.")
        elif kod == wx.WXK_WINDOWS_MENU or (kod == wx.WXK_F10 and event.ShiftDown()):
            self._helyi()
        else:
            event.Skip()

    def _tarsitas(self, _e=None):
        ut = self._kivalasztott()
        if not ut or os.path.isdir(ut):
            self.SetStatusText("A társítás egy fájlra vonatkozik.")
            return
        TarsitasDialog(self, tarsitas.kit(ut)).ShowModal()

    def _massal(self, _e=None):
        ut = self._kivalasztott()
        if not ut or os.path.isdir(ut):
            self.SetStatusText("Előbb jelölj ki egy fájlt.")
            return
        dlg = wx.FileDialog(self, "Program, amivel megnyílik",
                            wildcard="Program|*.exe",
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            tarsitas.ments(tarsitas.kit(ut), "program", dlg.GetPath())
            mondat = tarsitas.nyit(self.main, ut)
            self.SetStatusText(mondat)
            self._mond(mondat)
        dlg.Destroy()

    def _mond(self, szoveg):
        if not (szoveg or "").strip():
            return
        try:
            import sys
            gyoker = os.path.abspath(os.path.join(
                os.path.dirname(__file__), "..", "..", ".."))
            if gyoker not in sys.path:
                sys.path.insert(0, gyoker)
            from superdl import screenreader
            if screenreader.speak(szoveg, interrupt=True):
                return
        except Exception:
            pass
        sv = getattr(self.main, "selfvoice", None)
        if sv:
            try:
                sv.speak(szoveg, force=True)
                return
            except Exception:
                pass
        try:
            import win32com.client
            hang = getattr(self, "_sapi", None)
            if hang is None:
                hang = win32com.client.Dispatch("SAPI.SpVoice")
                self._sapi = hang
            hang.Speak(szoveg, 1 | 2)
        except Exception:
            pass


class KeresesDialog(wx.Dialog):
    def __init__(self, szulo):
        super().__init__(szulo, title="Keresés")
        v = wx.BoxSizer(wx.VERTICAL)
        self.mod = wx.RadioBox(
            self, label="Mire keresek",
            choices=["Név részlete", "Fájltípus"],
            majorDimension=1, style=wx.RA_SPECIFY_COLS)
        self.mod.SetName("Mire keresek")
        v.Add(self.mod, 0, wx.EXPAND | wx.ALL, 8)
        v.Add(wx.StaticText(
            self, label="A névnél egy részlet elég. A típusnál a végződés, például mkv."),
            0, wx.LEFT | wx.RIGHT, 8)
        self.szoveg = wx.TextCtrl(self)
        self.szoveg.SetName("Keresett szöveg")
        v.Add(self.szoveg, 0, wx.EXPAND | wx.ALL, 8)
        v.Add(self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL),
              0, wx.EXPAND | wx.ALL, 8)
        self.SetSizerAndFit(v)
        self.szoveg.SetFocus()

    def ertek(self):
        mod = "tipus" if self.mod.GetSelection() == 1 else "nev"
        return self.szoveg.GetValue(), mod


class TarsitasDialog(wx.Dialog):
    def __init__(self, szulo, kiterjesztes: str):
        super().__init__(szulo, title="Társítás: %s" % kiterjesztes)
        self.kit = kiterjesztes
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(self, label="A %s fájlokat ez nyissa:" % kiterjesztes),
              0, wx.ALL, 8)
        self.valaszt = wx.Choice(self, choices=[nev for _k, nev in tarsitas.CELOK])
        self.valaszt.SetName("Mivel nyíljon")
        most = tarsitas.beallitas(kiterjesztes).get("cel")
        idx = next((i for i, (k, _n) in enumerate(tarsitas.CELOK) if k == most), 0)
        self.valaszt.SetSelection(idx)
        v.Add(self.valaszt, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        self.program = wx.TextCtrl(self)
        self.program.SetName("A külső program elérési útja")
        self.program.SetValue(tarsitas.beallitas(kiterjesztes).get("program") or "")
        v.Add(self.program, 0, wx.EXPAND | wx.ALL, 8)
        gomb = wx.Button(self, label="Program &tallózása…")
        gomb.Bind(wx.EVT_BUTTON, self._program)
        v.Add(gomb, 0, wx.LEFT | wx.BOTTOM, 8)
        v.Add(self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizerAndFit(v)
        self.Bind(wx.EVT_BUTTON, self._ok, id=wx.ID_OK)

    def _program(self, _e):
        dlg = wx.FileDialog(self, "Program", wildcard="Program|*.exe",
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.program.SetValue(dlg.GetPath())
            self.valaszt.SetSelection(len(tarsitas.CELOK) - 1)
        dlg.Destroy()

    def _ok(self, _e):
        cel = tarsitas.CELOK[self.valaszt.GetSelection()][0]
        tarsitas.ments(self.kit, cel, self.program.GetValue().strip())
        self.EndModal(wx.ID_OK)


class TarsitasListaFrame(wx.Frame):
    """A szokásos társítások áttekintése, kiterjesztésenként."""

    def __init__(self, main):
        super().__init__(main, title="SuperDL – Társítások", size=(640, 480))
        self.main = main
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(
            p, label="Válassz egy sort, és az Enterrel átállíthatod, mivel nyíljon."),
            0, wx.ALL, 8)
        sorok = []
        self._kit = []
        for kit in sorted(set(tarsitas.ALAP) | set(tarsitas._egyeni())):
            self._kit.append(kit)
            sorok.append("%s: %s" % (kit, tarsitas.felirat(kit)))
        self.lista = wx.ListBox(p, choices=sorok or ["(még nincs társítás)"])
        self.lista.SetName("Társítások")
        self.lista.Bind(wx.EVT_LISTBOX_DCLICK, self._szerkeszt)
        v.Add(self.lista, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        b = wx.Button(p, label="&Módosítás")
        b.Bind(wx.EVT_BUTTON, self._szerkeszt)
        v.Add(b, 0, wx.ALL, 8)
        p.SetSizer(v)
        self.CentreOnParent()
        self.Show()
        if sorok:
            self.lista.SetSelection(0)
        self.lista.SetFocus()

    def _szerkeszt(self, _e=None):
        i = self.lista.GetSelection()
        if i < 0 or i >= len(self._kit):
            return
        if TarsitasDialog(self, self._kit[i]).ShowModal() == wx.ID_OK:
            self.lista.SetString(i, "%s: %s" % (self._kit[i], tarsitas.felirat(self._kit[i])))
