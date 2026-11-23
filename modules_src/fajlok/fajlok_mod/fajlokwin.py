"""Super Fájlok ablaka: mit, hová, másolás vagy áthelyezés.

A felület szándékosan rövid. A munka a háttérben megy, a státuszsor mondja,
éppen melyik fájlnál tart.
"""

import os
import threading
import time

import wx

from . import masolo

_MUVELET = (("masol", "Másolás"), ("athelyez", "Áthelyezés"))
_UTKOZES = (
    ("felulir", "Felülírja"),
    ("kihagy", "Kihagyja"),
    ("ujnev", "Új néven menti"),
)


class FajlokFrame(wx.Frame):
    def __init__(self, main):
        super().__init__(main, title="SuperDL – Super Fájlok", size=(760, 560))
        self.main = main
        self._elemek = []
        self._cancel = threading.Event()
        self._dolgozik = False
        self._szal = None
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        sor = wx.BoxSizer(wx.HORIZONTAL)
        sor.Add(wx.StaticText(p, label="&Művelet:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.muvelet = wx.Choice(p, choices=[c for _k, c in _MUVELET])
        self.muvelet.SetSelection(0)
        self.muvelet.SetName("Művelet")
        sor.Add(self.muvelet, 0, wx.RIGHT, 16)
        sor.Add(wx.StaticText(p, label="Ha már &van ilyen fájl:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.utkozes = wx.Choice(p, choices=[c for _k, c in _UTKOZES])
        self.utkozes.SetSelection(0)
        self.utkozes.SetName("Ha már van ilyen fájl")
        sor.Add(self.utkozes, 0)
        v.Add(sor, 0, wx.ALL, 8)

        v.Add(wx.StaticText(p, label="&Mit vigyünk át:"), 0, wx.LEFT | wx.RIGHT, 8)
        self.lista = wx.ListBox(p)
        self.lista.SetName("Másolandó fájlok és mappák")
        v.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)

        gombok = wx.BoxSizer(wx.HORIZONTAL)
        for cim, fn in (
                ("&Fájlok…", self._fajlok),
                ("Mapp&a…", self._mappa),
                ("&Kivesz", self._kivesz)):
            b = wx.Button(p, label=cim)
            b.Bind(wx.EVT_BUTTON, fn)
            gombok.Add(b, 0, wx.RIGHT, 6)
        v.Add(gombok, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        cel = wx.BoxSizer(wx.HORIZONTAL)
        cel.Add(wx.StaticText(p, label="&Hová:"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.cel = wx.TextCtrl(p, style=wx.TE_READONLY)
        self.cel.SetName("Célmappa")
        cel.Add(self.cel, 1, wx.RIGHT, 6)
        b_cel = wx.Button(p, label="Cél&mappa…")
        b_cel.Bind(wx.EVT_BUTTON, self._cel)
        cel.Add(b_cel, 0)
        v.Add(cel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        fut = wx.BoxSizer(wx.HORIZONTAL)
        self.indit = wx.Button(p, label="&Indítás")
        self.indit.Bind(wx.EVT_BUTTON, self._indit)
        self.megall = wx.Button(p, label="&Megszakítás")
        self.megall.Bind(wx.EVT_BUTTON, self._megall)
        self.megall.Enable(False)
        self.helyzet_gomb = wx.Button(p, label="Mi a &helyzet?")
        self.helyzet_gomb.SetName("Mi a helyzet")
        self.helyzet_gomb.Bind(wx.EVT_BUTTON, self._helyzet)
        fut.Add(self.indit, 0, wx.RIGHT, 6)
        fut.Add(self.megall, 0, wx.RIGHT, 6)
        fut.Add(self.helyzet_gomb, 0, wx.RIGHT, 6)
        self.hiba_gomb = wx.Button(p, label="Hibás &fájl")
        self.hiba_gomb.SetName("Ugrás a hibás fájl mappájára")
        self.hiba_gomb.Bind(wx.EVT_BUTTON, self._hiba)
        self.hiba_gomb.Enable(False)
        fut.Add(self.hiba_gomb, 0)
        self.ejszaka = wx.CheckBox(p, label="Éjszakai menet, csak a végén szól")
        self.ejszaka.SetName("Éjszakai menet")
        v.Add(self.ejszaka, 0, wx.LEFT | wx.BOTTOM, 8)
        self._hibak = []
        self._allapot = "Adj meg fájlt vagy mappát, és egy célmappát."
        self._mondott = ""
        self._mondott_ido = 0.0
        self._mondott_szaz = -1
        azon = wx.NewIdRef()
        self.Bind(wx.EVT_MENU, self._helyzet, id=azon)
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_NORMAL, wx.WXK_F8, azon)]))
        v.Add(fut, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.meret = wx.Gauge(p, range=100)
        self.meret.SetName("Haladás")
        v.Add(self.meret, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.naplo = wx.TextCtrl(p, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.naplo.SetName("Napló")
        v.Add(self.naplo, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        p.SetSizer(v)
        self.CreateStatusBar()
        self.SetStatusText("Adj meg fájlt vagy mappát, és egy célmappát.")
        self.Bind(wx.EVT_CLOSE, self._zar)
        self.CentreOnParent()
        self.Show()
        self.lista.SetFocus()

    def _fajlok(self, _e):
        from superdl import fajlvalaszto
        utak = fajlvalaszto.valassz_fajlokat(
            self, "Fájlok, amiket átviszünk", tobb=True, mondd=self._mond)
        self._hozza(utak)

    def _mappa(self, _e):
        from superdl import fajlvalaszto
        ut = fajlvalaszto.valassz_mappat(
            self, "Mappa, amit átviszünk", mondd=self._mond)
        if ut:
            self._hozza([ut])

    def _cel(self, _e):
        from superdl import fajlvalaszto
        ut = fajlvalaszto.valassz_mappat(self, "Célmappa", mondd=self._mond)
        if ut:
            self.cel.SetValue(ut)
            self.SetStatusText(ut)

    def _hozza(self, utak):
        for ut in utak or []:
            if ut and ut not in self._elemek:
                self._elemek.append(ut)
                self.lista.Append(ut)
        if self._elemek:
            self.lista.SetSelection(len(self._elemek) - 1)
            self.SetStatusText("%d elem a listában." % len(self._elemek))

    def _kivesz(self, _e):
        i = self.lista.GetSelection()
        if i < 0:
            self.SetStatusText("Előbb jelöld ki, melyik elemet veszed ki.")
            return
        del self._elemek[i]
        self.lista.Delete(i)
        if self._elemek:
            self.lista.SetSelection(min(i, len(self._elemek) - 1))
        self.SetStatusText("%d elem a listában." % len(self._elemek))

    def _indit(self, _e):
        if self._dolgozik:
            return
        if not self._elemek:
            self.SetStatusText("Nincs mit átvinni. Adj hozzá fájlt vagy mappát.")
            return
        cel = self.cel.GetValue().strip()
        if not cel:
            self.SetStatusText("Válassz célmappát.")
            return
        muvelet = _MUVELET[self.muvelet.GetSelection()][0]
        utkozes = _UTKOZES[self.utkozes.GetSelection()][0]
        regi = masolo.menet_olvas()
        folytat = False
        keszek = None
        if masolo.menet_ugyanaz(regi, self._elemek, cel, muvelet) and regi.get("keszek"):
            valasz = wx.MessageBox(
                "Van egy félbemaradt menet: %d fájl már átment. "
                "Folytassam onnan? A Nem gomb elölről kezdi."
                % len(regi["keszek"]),
                "Folytatás", wx.YES | wx.NO | wx.ICON_QUESTION, self)
            if valasz == wx.YES:
                folytat = True
                keszek = regi["keszek"]
            else:
                masolo.menet_torol()
        self._cancel.clear()
        self._dolgozik = True
        self.indit.Enable(False)
        self.megall.Enable(True)
        self.meret.SetValue(0)
        self._mondott_szaz = -1
        self.SetStatusText("Számlálás…")
        self._mond("Számlálás, aztán egyenként viszem a fájlokat.")
        elemek = list(self._elemek)

        def mentes(kesz_utak):
            masolo.menet_ir(elemek, cel, muvelet, utkozes, kesz_utak)

        def munka():
            try:
                masolo.futtat(elemek, cel, muvelet, utkozes,
                              lambda j: wx.CallAfter(self._frissit, j),
                              self._cancel.is_set, keszek=keszek, mentes=mentes,
                              folytat=folytat, jovahagy=self._jovahagy)
            except Exception as exc:
                wx.CallAfter(self.SetStatusText, "Hiba: %s" % exc)
                wx.CallAfter(self._vege)

        self._szal = threading.Thread(target=munka, daemon=True)
        self._szal.start()

    def _megall(self, _e):
        self._cancel.set()
        self.SetStatusText("Megszakítás, a mostani fájl után megáll.")

    def atvesz(self, utak, cel=""):
        """A tallózó ide adja a kijelölt elemet."""
        self._hozza(utak)
        if cel:
            self.cel.SetValue(cel)
        self.Raise()
        self._mond("%d elem a másolóban." % len(self._elemek))

    def _jovahagy(self, mondat: str) -> bool:
        if self.ejszaka.GetValue():
            return True
        doboz = {"ok": False}
        kesz = threading.Event()

        def kerdes():
            doboz["ok"] = wx.MessageBox(
                mondat + " Indulhat?", "Terv",
                wx.YES | wx.NO | wx.ICON_QUESTION, self) == wx.YES
            kesz.set()

        wx.CallAfter(kerdes)
        kesz.wait()
        return doboz["ok"]

    def _hiba(self, _e=None):
        if not self._hibak:
            self.SetStatusText("Nincs hibás fájl.")
            return
        elso = self._hibak[0].split(":", 1)[0].strip()
        mappa = elso if os.path.isdir(elso) else os.path.dirname(elso)
        from .tallozowin import TallozoFrame
        TallozoFrame(self.main, mappa)
        self._mond("A hibás fájl mappája megnyílt.")

    def _helyzet(self, _e=None):
        self._mond(self._allapot)

    def _frissit(self, jel: masolo.Jelentes):
        szaz = jel.szazalek()
        self.meret.SetValue(max(0, min(100, szaz)))
        szoveg = jel.uzenet or jel.helyzet()
        self._allapot = szoveg
        self._hibak = list(jel.hibak)
        self.hiba_gomb.Enable(bool(self._hibak))
        self.SetStatusText(szoveg)
        hibak = "\n".join(jel.hibak)
        naplo = szoveg if not hibak else szoveg + "\n\nHibák:\n" + hibak
        self.naplo.SetValue(naplo)
        most = time.monotonic()
        ejszaka = self.ejszaka.GetValue()
        if ((jel.kesz or (not ejszaka and (szaz - self._mondott_szaz >= 5
                or most - self._mondott_ido >= 12)))
                and szoveg != self._mondott):
            self._mond(szoveg)
            self._mondott = szoveg
            self._mondott_ido = most
            self._mondott_szaz = szaz
        if jel.kesz:
            if not jel.megszakitva:
                masolo.menet_torol()
            self._vege()

    def _vege(self):
        self._dolgozik = False
        self.indit.Enable(True)
        self.megall.Enable(False)

    def _zar(self, event):
        if self._dolgozik:
            self._cancel.set()
        event.Skip()

    def _mond(self, szoveg):
        if not (szoveg or "").strip():
            return
        try:
            from superdl import screenreader
            if screenreader.speak(szoveg):
                return
        except Exception:
            pass
        sv = getattr(self.main, "selfvoice", None)
        if sv and not getattr(sv, "muted", False):
            try:
                sv.speak(szoveg, force=True)
            except Exception:
                pass
