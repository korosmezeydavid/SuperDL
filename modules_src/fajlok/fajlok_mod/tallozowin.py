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


# A médiakonvertáló saját listája. Ha a modul be van töltve, az övét használjuk.
_MEDIA = (
    ".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus", ".wma",
    ".mp4", ".mkv", ".avi", ".webm", ".mov", ".wmv", ".flv", ".m4v",
    ".mpg", ".mpeg", ".ts", ".3gp", ".vob", ".m2v", ".mpe", ".m2ts", ".mts",
    ".ape", ".wv", ".tta", ".tak", ".mpc", ".shn", ".dsf", ".dff",
    ".aiff", ".aif", ".aifc", ".au", ".amr", ".caf", ".spx", ".ra",
    ".ac3", ".dts", ".mka", ".m4b", ".oga", ".w64",
)


def media_fajl(ut: str) -> bool:
    """Igaz, ha a fájl olyan média, amit a médiakonvertáló be tud venni."""
    if not ut or os.path.isdir(ut):
        return False
    kit = os.path.splitext(ut)[1].lower()
    try:
        import sys
        from pathlib import Path
        gyoker = Path(__file__).resolve().parents[2] / "mediatools"
        if gyoker.is_dir() and str(gyoker) not in sys.path:
            sys.path.insert(0, str(gyoker))
        from mediatools_mod.convertwin import MEDIA_EXTS
        return kit in MEDIA_EXTS
    except Exception:
        return kit in _MEDIA


def helyi_extra(ut: str) -> list[str]:
    """A helyi menü többletpontjai aszerint, hogy fájlon vagy mappán állunk."""
    if not ut:
        return []
    if os.path.isdir(ut):
        return ["Mappa küldése és megosztás…"]
    sorok = ["Fájlküldés gépről gépre"]
    if media_fajl(ut):
        sorok.append("Médiakonvertáló")
    return sorok


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
        self._csatolt_isok = {}
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

    def _archivalas(self, _e=None):
        from . import archivalas
        if self._dolgozik:
            self._mond("Még tart az előző művelet.")
            return
        if not self._ketag or not self._masik().mappa:
            self._mond("Nyiss meg egy célmappát a másik panelen.")
            return
        if not self._kijelolt_utak():
            self._mond("Jelölj ki legalább egy fájlt.")
            return
        try:
            alap = "Felvételek archiválása"
            sablonok = archivalas.mentett_nevek()
            if sablonok:
                with wx.SingleChoiceDialog(
                        self, "Válassz mentett archiválást vagy új nevet.",
                        "Archiválási művelet", ["Új művelet…", *sablonok]) as valaszto:
                    valaszto.SetSelection(0)
                    if valaszto.ShowModal() != wx.ID_OK:
                        return
                    index = valaszto.GetSelection()
                    if index > 0:
                        alap = sablonok[index - 1]
            with wx.TextEntryDialog(self, "Menthető művelet neve, egyben a ZIP neve:",
                                    "Felvételek archiválása", alap) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                nev = archivalas.nev_ellenorzes(dlg.GetValue())
            cel, elemek = archivalas.terv(self._kijelolt_utak(), self._masik().mappa, nev)
            elonezet = f"{len(elemek)} fájl. Cél: {cel}. Nincs névütközés.\n\n"
            elonezet += "\n".join(f"{ut.name} → {tag}" for ut, tag in elemek)
            self._mond(f"{len(elemek)} fájl. Cél: {cel}. Nincs névütközés.")
            with wx.Dialog(self, title="Archiválás előnézete", size=(580, 380)) as dialog:
                layout = wx.BoxSizer(wx.VERTICAL)
                lista = wx.TextCtrl(dialog, value=elonezet,
                                    style=wx.TE_MULTILINE | wx.TE_READONLY,
                                    name="Archiválási terv")
                layout.Add(lista, 1, wx.EXPAND | wx.ALL, 8)
                ment = wx.CheckBox(dialog, label="Művelet nevének mentése")
                layout.Add(ment, 0, wx.ALL, 8)
                layout.Add(dialog.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL),
                           0, wx.EXPAND | wx.ALL, 8)
                dialog.SetSizer(layout)
                lista.SetFocus()
                if dialog.ShowModal() != wx.ID_OK:
                    return
                if ment.GetValue():
                    archivalas.nev_mentese(nev)
        except (OSError, ValueError) as exc:
            self.SetStatusText(str(exc))
            self._mond(str(exc))
            return

        self._cancel.clear()
        self._dolgozik = True

        def kesz(uzenet):
            self._dolgozik = False
            if self:
                self._tolts()
                self.SetStatusText(uzenet)
                self._mond(uzenet)

        def munka():
            try:
                ok = archivalas.futtat(cel, elemek, self._cancel.is_set)
                uzenet = f"Elkészült: {cel}" if ok else "Archiválás megszakítva."
            except (OSError, ValueError, RuntimeError) as exc:
                uzenet = f"Az archiválás nem sikerült: {exc}"
            wx.CallAfter(kesz, uzenet)

        self._mond("Archiválás folyamatban.")
        threading.Thread(target=munka, daemon=True).start()

    def _osszevet(self, _e=None):
        if not self._mappa or self._dolgozik:
            return
        from superdl import fajlvalaszto
        from .osszevet import elteresek, szinkron_tetel

        elso = self._mappa
        masik = self._masik().mappa if self._ketag else ""
        if not masik:
            masik = fajlvalaszto.valassz_mappat(self, "A másik mappa", mondd=self._mond)
        if not masik:
            return
        self._cancel.clear()
        self._dolgozik = True
        self.SetStatusText("Mappák összevetése folyamatban.")
        self._mond("Mappák összevetése folyamatban.")

        def vege(rows, hiba):
            if not self:
                return
            self._dolgozik = False
            if hiba:
                self.SetStatusText(hiba)
                self._mond(hiba)
                return
            if not rows:
                self.SetStatusText("A két mappa fájltartalma egyezik.")
                self._mond("A két mappa fájltartalma egyezik.")
                return
            cim = f"{len(rows)} eltérés. Első: {elso}. Második: {masik}."
            self._mond(cim)
            with wx.MultiChoiceDialog(
                    self, cim + " Jelöld ki az első mappából átmásolandó hiányzó fájlokat.",
                    "Mappák tartalmának összevetése",
                    [f"{allapot}: {rel}" for allapot, rel, _ in rows]) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                kijelolt = [rows[i] for i in dlg.GetSelections()]
            if not kijelolt:
                return
            if any(path is None for _, _, path in kijelolt):
                self._mond("Csak az első mappában lévő hiányzó fájlokat jelöld ki.")
                return
            if wx.MessageBox(f"{len(kijelolt)} fájl másolása ide: {masik}. Futtatod?",
                             "Szinkron jóváhagyása",
                             wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self) != wx.YES:
                return
            self._cancel.clear()
            self._dolgozik = True
            self._mond("Szinkronizálás folyamatban. Megszakítás: Escape.")

            def kesz(szoveg):
                if not self:
                    return
                self._dolgozik = False
                self.SetStatusText(szoveg)
                self._mond(szoveg)

            def masol():
                darab = 0
                try:
                    for _, rel, path in kijelolt:
                        if self._cancel.is_set():
                            raise InterruptedError("Megszakítva.")
                        szinkron_tetel(path, masik, rel, self._cancel.is_set)
                        darab += 1
                except (OSError, ValueError) as exc:
                    wx.CallAfter(kesz, f"{darab} fájl átment. {exc}")
                else:
                    wx.CallAfter(kesz, f"Szinkron kész. {darab} fájl átmásolva.")

            threading.Thread(target=masol, daemon=True).start()

        def munka():
            try:
                rows = elteresek(elso, masik, self._cancel.is_set)
            except OSError as exc:
                wx.CallAfter(vege, [], f"Az összevetés megszakadt vagy sikertelen: {exc}")
            else:
                wx.CallAfter(vege, rows, "")

        threading.Thread(target=munka, daemon=True).start()

    def _masolatkereses(self, _e=None):
        if not self._mappa or self._dolgozik:
            return
        from .osszevet import masolatok

        gyoker = self._mappa
        self._cancel.clear()
        self._dolgozik = True
        self.SetStatusText("Azonos tartalmú fájlok keresése…")
        self._mond("Azonos tartalmú fájlok keresése. Megszakítás: Escape.")

        def vege(csoportok, hiba):
            if not self:
                return
            self._dolgozik = False
            szoveg = hiba or f"{len(csoportok)} másolatcsoport."
            self.SetStatusText(szoveg)
            self._mond(szoveg)
            if not csoportok:
                return
            utak = []
            sorok = []
            for index, (meret, fajlok) in enumerate(csoportok, 1):
                for path in fajlok:
                    utak.append(path)
                    sorok.append(f"{index}. csoport, {meret_szoveg(meret)}: {path}")
            with wx.MultiChoiceDialog(
                    self, szoveg + " Jelöld ki a kezelendő fájlokat.",
                    "Azonos tartalmú fájlok", sorok) as dialog:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                kijelolt = [utak[i] for i in dialog.GetSelections()]
            if not kijelolt:
                return
            with wx.SingleChoiceDialog(
                    self, "Mit tegyen a kijelölt találatokkal?", "Másolatok kezelése",
                    ["Az első kijelölt fájl mappájának megnyitása",
                     "A kijelölt fájlok áthelyezése a másik panelre"]) as dialog:
                dialog.SetSelection(0)
                if dialog.ShowModal() != wx.ID_OK:
                    return
                athelyez = dialog.GetSelection() == 1
            if not athelyez:
                hely = kijelolt[0].parent
                if hely.is_dir():
                    self._mappa = str(hely)
                    self._tolts()
                    self._mond(f"Mappa megnyitva: {hely}")
                return

            cel = self._masik().mappa if self._ketag else ""
            if not cel or not os.path.isdir(cel):
                self._mond("Az áthelyezéshez nyiss meg egy helyi mappát a másik panelen.")
                return
            utak_szovege = [str(path) for path in kijelolt]
            terv = (f"{len(kijelolt)} fájl áthelyezése ide: {cel}.\n"
                    "Névütközéskor új nevet kapnak.\n\n" + "\n".join(utak_szovege))
            with wx.Dialog(self, title="Másolatok áthelyezésének előnézete", size=(600, 400)) as dialog:
                layout = wx.BoxSizer(wx.VERTICAL)
                lista = wx.TextCtrl(dialog, value=terv, name="Áthelyezési terv",
                                    style=wx.TE_MULTILINE | wx.TE_READONLY)
                layout.Add(lista, 1, wx.EXPAND | wx.ALL, 8)
                layout.Add(dialog.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL),
                           0, wx.EXPAND | wx.ALL, 8)
                dialog.SetSizer(layout)
                lista.SetFocus()
                if dialog.ShowModal() != wx.ID_OK:
                    return
            self._indit_atvitel(utak_szovege, cel, "athelyez", "ujnev",
                                f"Cél: {cel}. Névütközéskor új nevet kapnak.")

        def munka():
            try:
                csoportok = masolatok(gyoker, self._cancel.is_set)
            except InterruptedError:
                wx.CallAfter(vege, [], "A másolatkeresés megszakadt.")
            except OSError as exc:
                wx.CallAfter(vege, [], f"A másolatkeresés nem sikerült: {exc}")
            else:
                wx.CallAfter(vege, csoportok, "")

        threading.Thread(target=munka, daemon=True).start()

    def _fonix_kulcs(self, _e=None):
        from .fonix import kulcsfajl_keszit
        with wx.FileDialog(self, "Új Főnix-kulcsfájl mentése",
                           wildcard="Főnix-kulcs (*.fonixkey)|*.fonixkey",
                           defaultFile="vedett.fonixkey", style=wx.FD_SAVE) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            try:
                kulcsfajl_keszit(dialog.GetPath())
            except OSError as exc:
                wx.MessageBox(str(exc), "Főnix-pajzs", wx.OK | wx.ICON_ERROR, self)
                return
        self._mond("A kulcsfájl elkészült. Tarts róla külön biztonsági másolatot.")

    def _fonix(self, nyitas=False):
        if self._dolgozik:
            return
        utak = self._kijelolt_utak()
        if not utak or (nyitas and len(utak) != 1):
            self._mond("Jelöld ki a csomagot." if nyitas else "Jelölj ki fájlokat vagy mappákat.")
            return
        from . import fonix

        def jelszo(cim):
            with wx.TextEntryDialog(self, cim, "Főnix-pajzs",
                                    style=wx.OK | wx.CANCEL | wx.TE_PASSWORD) as dlg:
                return dlg.GetValue() if dlg.ShowModal() == wx.ID_OK else None

        titok = jelszo("Jelszó:" if nyitas else "Új jelszó, legalább 12 karakter:")
        if titok is None or (not nyitas and titok != jelszo("Jelszó megerősítése:")):
            return
        try:
            if nyitas:
                kell_kulcs = fonix.kulcsfajlos(utak[0])
            else:
                valasz = wx.MessageBox(
                    "A jelszó mellé külön kulcsfájlt is kérjen a feloldás?",
                    "Főnix-pajzs", wx.YES_NO | wx.NO_DEFAULT | wx.CANCEL, self)
                if valasz == wx.CANCEL:
                    return
                kell_kulcs = valasz == wx.YES
        except (OSError, ValueError) as exc:
            wx.MessageBox(str(exc), "Főnix-pajzs", wx.OK | wx.ICON_ERROR, self)
            return
        kulcsfajl = None
        if kell_kulcs:
            with wx.FileDialog(self, "Főnix-kulcsfájl kiválasztása",
                               wildcard="Főnix-kulcs (*.fonixkey)|*.fonixkey",
                               style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialog:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                kulcsfajl = dialog.GetPath()
        cel = None
        if not nyitas:
            with wx.FileDialog(self, "Főnix-pajzs mentése", wildcard="Főnix-pajzs (*.fonix)|*.fonix",
                               defaultFile="vedett.fonix", style=wx.FD_SAVE) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                cel = dlg.GetPath()
        self._dolgozik = True
        self._mond("Főnix-pajzs művelet folyamatban.")

        def vege(archive, hiba):
            if not self:
                if archive:
                    archive.close()
                return
            self._dolgozik = False
            if hiba:
                wx.MessageBox(hiba, "Főnix-pajzs", wx.OK | wx.ICON_ERROR, self)
            elif archive is None:
                self._tolts()
                self._mond(f"Főnix-pajzs elkészült: {cel}")
            else:
                with archive:
                    tags = [tag for tag in archive.infolist() if not tag.is_dir()]
                    with wx.MultiChoiceDialog(
                            self, "Jelöld ki a kimentendő fájlokat.", "Védett tartalom",
                            [tag.filename for tag in tags]) as dlg:
                        if dlg.ShowModal() != wx.ID_OK:
                            return
                        kijelolt = [tags[i] for i in dlg.GetSelections()]
                    if not kijelolt:
                        return
                    try:
                        if len(kijelolt) == 1:
                            with wx.FileDialog(self, "Védett fájl mentése",
                                               defaultFile="kimentett-fajl", style=wx.FD_SAVE) as dlg:
                                if dlg.ShowModal() != wx.ID_OK:
                                    return
                                fonix.kiment(archive, kijelolt[0], dlg.GetPath())
                                darab = 1
                        else:
                            from superdl import fajlvalaszto
                            mappa = fajlvalaszto.valassz_mappat(
                                self, "Kimentés egy közös mappába", mondd=self._mond)
                            if not mappa:
                                return
                            darab = fonix.kiment_tobb(archive, kijelolt, mappa)
                    except Exception as exc:
                        wx.MessageBox(str(exc), "Főnix-pajzs", wx.OK | wx.ICON_ERROR, self)
                        return
                    self._mond(f"{darab} fájl kimentve.")

        def munka():
            try:
                archive = fonix.felold(utak[0], titok, kulcsfajl) if nyitas else None
                if not nyitas:
                    fonix.keszit(utak, cel, titok, kulcsfajl)
            except Exception as exc:
                wx.CallAfter(vege, None, str(exc))
            else:
                wx.CallAfter(vege, archive, "")

        threading.Thread(target=munka, daemon=True).start()

    def _iso_kiment(self, _e=None):
        if self._dolgozik:
            return
        utak = self._kijelolt_utak()
        if len(utak) != 1 or not utak[0].lower().endswith(".iso"):
            self._mond("Jelölj ki egy ISO-fájlt.")
            return
        from .csomag import iso_fajl_kiment, tartalom

        try:
            tagok = [tag for tag in tartalom(utak[0]) if tag not in (".", "./") and not tag.endswith("/")]
            if not tagok:
                self._mond("Az ISO nem tartalmaz választható tételt.")
                return
            with wx.SingleChoiceDialog(self, "Melyik fájlt mented?",
                                       "ISO tartalma", tagok) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                tag = tagok[dlg.GetSelection()]
            with wx.FileDialog(self, "ISO-tétel mentése", defaultFile=os.path.basename(tag),
                               style=wx.FD_SAVE) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                iso_fajl_kiment(utak[0], tag, dlg.GetPath())
        except Exception as exc:
            wx.MessageBox(str(exc), "ISO-tétel mentése", wx.OK | wx.ICON_ERROR, self)
            return
        self._tolts()
        self.SetStatusText("A kijelölt ISO-tétel elmentve.")
        self._mond("A kijelölt ISO-tétel elmentve.")

    def _iso(self, levalaszt=False):
        if self._dolgozik:
            self._mond("Még tart az előző művelet.")
            return
        utak = self._kijelolt_utak()
        fajl = utak[0] if len(utak) == 1 and utak[0].lower().endswith(".iso") else None
        if levalaszt and fajl is None:
            meghajto = os.path.splitdrive(self._mappa)[0].upper()
            fajl = self._csatolt_isok.get(meghajto)
        if fajl is None:
            self._mond("Jelölj ki egy ISO-fájlt.")
            return
        from .lemezkep import muvelet
        ag = self._aktiv
        nev = os.path.basename(fajl)
        self._dolgozik = True
        kezdet = ("ISO leválasztása" if levalaszt else "ISO csatolása") + ": " + nev
        self.SetStatusText(kezdet)
        self._mond(kezdet)

        def vege(meghajto, hiba):
            if not self:
                return
            self._dolgozik = False
            if meghajto:
                self._csatolt_isok[os.path.splitdrive(meghajto)[0].upper()] = fajl
                ag.mappa = meghajto
                self._tolts(ag)
                status = self.GetStatusBar().GetStatusText()
                if status.startswith("A mappa nem olvasható:"):
                    hiba = f"Csatolva: {meghajto}. {status}"
                ag.lista.SetFocus()
            elif levalaszt and not hiba:
                kulcs = os.path.normcase(os.path.abspath(fajl))
                for betu, eredeti in list(self._csatolt_isok.items()):
                    if os.path.normcase(os.path.abspath(eredeti)) != kulcs:
                        continue
                    del self._csatolt_isok[betu]
                    for panel in (self._bal, self._jobb):
                        if os.path.splitdrive(panel.mappa)[0].upper() == betu:
                            panel.mappa = os.path.dirname(fajl)
                            self._tolts(panel)
                ag.lista.SetFocus()
            szoveg = hiba or (f"Csatolva: {meghajto}" if meghajto else f"Leválasztva: {nev}")
            self.SetStatusText(szoveg)
            self._mond(szoveg)

        def munka():
            try:
                meghajto = muvelet(fajl, levalaszt)
            except Exception as exc:
                wx.CallAfter(vege, "", f"Az ISO-művelet nem sikerült: {exc}")
            else:
                wx.CallAfter(vege, meghajto, "")

        threading.Thread(target=munka, daemon=True).start()

    def _tomorit(self, _e=None):
        ut = self._kivalasztott()
        if not ut:
            return
        from .csomag import FORMAK, PROFILOK, tomorit
        dlg = wx.SingleChoiceDialog(self, "Milyen formátumba?", "Tömörítés", list(FORMAK))
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        forma = dlg.GetStringSelection()
        dlg.Destroy()
        cel = ut.rstrip("\\/") + "." + forma
        with wx.SingleChoiceDialog(self, "Válassz tömörítési profilt.",
                                   "Tömörítési profil", list(PROFILOK)) as szint:
            szint.SetSelection(1)
            if szint.ShowModal() != wx.ID_OK:
                return
            profil = szint.GetStringSelection()
        try:
            tomorit([ut], cel, forma, profil)
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
        self._mi(eszkoz, "ISO &csatolása virtuális meghajtóként…", lambda e: self._iso())
        self._mi(eszkoz, "ISO &leválasztása…", lambda e: self._iso(True))
        self._mi(eszkoz, "ISO kijelölt fájljának &kimentése…", self._iso_kiment)
        self._mi(eszkoz, "Főnix-pajzs létrehozása…", lambda e: self._fonix())
        self._mi(eszkoz, "Főnix-pajzs feloldása…", lambda e: self._fonix(True))
        self._mi(eszkoz, "Főnix-kulcsfájl készítése…", self._fonix_kulcs)
        self._mi(eszkoz, "Azonos tartalmú fájlok &keresése…", self._masolatkereses)
        self._mi(eszkoz, "Felvételek &archiválása…", self._archivalas)
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
                ("Társítás…", self._tarsitas)):
            it = menu.Append(wx.ID_ANY, cimke)
            self.Bind(wx.EVT_MENU, lambda e, f=fv: f(), it)
        extra = helyi_extra(self._kivalasztott())
        if extra:
            menu.AppendSeparator()
            for cimke in extra:
                fv = {
                    "Fájlküldés gépről gépre": self._fajl_kuld,
                    "Médiakonvertáló": self._media_konvert,
                    "Mappa küldése és megosztás…": self._mappa_kuld,
                }[cimke]
                it = menu.Append(wx.ID_ANY, cimke)
                self.Bind(wx.EVT_MENU, lambda e, f=fv: f(), it)
        for cimke, fv in (
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

    def _modul_ablak(self, kulcs):
        """A kész modul ablaka. A SuperDL-ben a gazda nyitja, különben a forrás."""
        host = getattr(self.main, "_module_host", None)
        if host is not None:
            if not getattr(host, "has_window", lambda _k: False)(kulcs):
                return None
            return host.open_window(kulcs)
        tar = getattr(self, "_horgony", None)
        if tar is None:
            tar = {}
            self._horgony = tar
        meglevo = tar.get(kulcs)
        if meglevo is not None:
            try:
                meglevo.Show()
                meglevo.Raise()
                return meglevo
            except Exception:
                tar.pop(kulcs, None)
        import sys
        from pathlib import Path
        gyoker = Path(__file__).resolve().parents[2]
        szulo = self.main if isinstance(self.main, wx.Window) else self
        try:
            if kulcs == "p2p_module":
                ut = gyoker / "p2p"
                if str(ut) not in sys.path:
                    sys.path.insert(0, str(ut))
                from p2p_mod.p2pwin import P2PFrame
                ablak = P2PFrame(szulo)
            elif kulcs == "convert_module":
                ut = gyoker / "mediatools"
                if str(ut) not in sys.path:
                    sys.path.insert(0, str(ut))
                from mediatools_mod.convertwin import BatchConvertFrame
                ablak = BatchConvertFrame(szulo)
            else:
                return None
        except Exception:
            return None
        ablak.Show()
        tar[kulcs] = ablak
        return ablak

    def _fajl_kuld(self, _e=None):
        ut = self._kivalasztott()
        if not ut or os.path.isdir(ut):
            self._mond("Fájlküldéshez állj egy fájlra.")
            return
        ablak = self._modul_ablak("p2p_module")
        if ablak is None or not hasattr(ablak, "_kuldes_inditas"):
            self._mond("A Fájlküldés gépről gépre modul nincs telepítve.")
            return
        wx.CallAfter(ablak._kuldes_inditas, ut)
        self._mond("Fájlküldés gépről gépre. A fájl: %s." % os.path.basename(ut))

    def _mappa_kuld(self, _e=None):
        ut = self._kivalasztott()
        if not ut or not os.path.isdir(ut):
            self._mond("Mappa küldéséhez állj egy mappára.")
            return
        ablak = self._modul_ablak("p2p_module")
        if ablak is None or not hasattr(ablak, "mappa_indit"):
            self._mond("A Fájlküldés gépről gépre modul nincs telepítve.")
            return
        wx.CallAfter(ablak.mappa_indit, ut)
        nev = os.path.basename(ut.rstrip("\\/")) or ut
        self._mond("Mappa küldése és megosztás. A mappa: %s." % nev)

    def _media_konvert(self, _e=None):
        utak = [u for u in self._kijelolt_utak() if media_fajl(u)]
        if not utak:
            egy = self._kivalasztott()
            if media_fajl(egy):
                utak = [egy]
        if not utak:
            self._mond("Médiakonvertáláshoz állj egy médiafájlra.")
            return
        ablak = self._modul_ablak("convert_module")
        if ablak is None or not hasattr(ablak, "add_paths"):
            self._mond("A Médiakonvertáló modul nincs telepítve.")
            return
        wx.CallAfter(ablak.add_paths, utak)
        self._mond("Médiakonvertáló. %d fájl." % len(utak))

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
