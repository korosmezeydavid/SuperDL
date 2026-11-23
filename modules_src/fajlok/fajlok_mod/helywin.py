"""FTP és SFTP hely. A jelszó a Windows titkos tárolójába kerül.

A Google Drive külön engedélyt kér a Google-tól, ezért itt még nem csatolható.
Az ablaka megmondja ezt, és a böngészőben a Drive-ot meg tudja nyitni.
"""

from __future__ import annotations

import os
from ftplib import FTP
from pathlib import Path

import wx

_TITOK = Path.home() / ".superdl" / "fajlok" / "helyek.secret.json"


def _ment(helyek: list) -> None:
    from superdl import store
    store.save_secret_json(_TITOK, {"helyek": helyek})


def _olvas() -> list:
    from superdl import store
    if not _TITOK.is_file():
        return []
    adat = store._load_secret_config(_TITOK)
    return list(adat.get("helyek") or [])


class HelyFrame(wx.Frame):
    def __init__(self, main):
        szulo = main if isinstance(main, wx.Window) else None
        super().__init__(szulo, title="SuperDL – Helyek", size=(640, 480))
        self.main = main
        self._helyek = _olvas()
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(p, label="Csatolt helyek. Az Enter belép a kijelöltre."),
              0, wx.ALL, 8)
        self.lista = wx.ListBox(p)
        self.lista.SetName("Csatolt helyek")
        self.lista.Bind(wx.EVT_LISTBOX_DCLICK, self._belep)
        v.Add(self.lista, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        sor = wx.BoxSizer(wx.HORIZONTAL)
        for cim, fn in (
                ("&Új FTP vagy SFTP…", self._uj),
                ("&Belépés", self._belep),
                ("&Törlés a listából", self._torol),
                ("Google &Drive…", self._drive)):
            b = wx.Button(p, label=cim)
            b.Bind(wx.EVT_BUTTON, fn)
            sor.Add(b, 0, wx.RIGHT, 6)
        v.Add(sor, 0, wx.ALL, 8)
        p.SetSizer(v)
        self.CreateStatusBar()
        self._frissit()
        self.CentreOnParent()
        self.Show()
        self.lista.SetFocus()

    def _frissit(self):
        self.lista.Set([
            "%s, %s@%s" % (h.get("fajta", "ftp").upper(), h.get("felhasznalo", ""), h.get("gep", ""))
            for h in self._helyek
        ] or ["(még nincs hely)"])
        if self._helyek:
            self.lista.SetSelection(0)

    def _uj(self, _e):
        dlg = UjHelyDialog(self)
        if dlg.ShowModal() == wx.ID_OK and dlg.hely:
            self._helyek.append(dlg.hely)
            try:
                _ment(self._helyek)
            except Exception as exc:
                self.SetStatusText(str(exc))
            else:
                self._frissit()
                self.SetStatusText("A hely elmentve.")
        dlg.Destroy()

    def _torol(self, _e):
        i = self.lista.GetSelection()
        if not (0 <= i < len(self._helyek)):
            return
        del self._helyek[i]
        _ment(self._helyek)
        self._frissit()

    def _belep(self, _e=None):
        i = self.lista.GetSelection()
        if not (0 <= i < len(self._helyek)):
            self.SetStatusText("Előbb vegyél fel egy helyet.")
            return
        TavoliFrame(self.main, self._helyek[i]).Show()

    def _drive(self, _e):
        wx.MessageBox(
            "A Google Drive csatolása a Google saját engedélyét kéri, "
            "azt ebben a lépésben még nem kérem el. Az FTP és az SFTP "
            "már ugyanebből az ablakból megy. A Drive-ot a böngészőben "
            "megnyithatod addig is.",
            "Google Drive", wx.OK | wx.ICON_INFORMATION, self)
        import webbrowser
        webbrowser.open("https://drive.google.com")


class UjHelyDialog(wx.Dialog):
    def __init__(self, szulo):
        super().__init__(szulo, title="Új hely")
        self.hely = None
        v = wx.BoxSizer(wx.VERTICAL)
        self.fajta = wx.Choice(self, choices=["FTP", "SFTP"])
        self.fajta.SetSelection(0)
        self.fajta.SetName("FTP vagy SFTP")
        self.gep = wx.TextCtrl(self)
        self.gep.SetName("A gép címe")
        self.port = wx.TextCtrl(self, value="21")
        self.port.SetName("Port")
        self.nev = wx.TextCtrl(self)
        self.nev.SetName("Felhasználó")
        self.jelszo = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        self.jelszo.SetName("Jelszó")
        for cim, mezo in (
                ("Típus", self.fajta), ("Gép", self.gep), ("Port", self.port),
                ("Felhasználó", self.nev), ("Jelszó", self.jelszo)):
            v.Add(wx.StaticText(self, label=cim), 0, wx.LEFT | wx.TOP, 8)
            v.Add(mezo, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        v.Add(self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizerAndFit(v)
        self.Bind(wx.EVT_BUTTON, self._ok, id=wx.ID_OK)

    def _ok(self, _e):
        self.hely = {
            "fajta": "sftp" if self.fajta.GetSelection() == 1 else "ftp",
            "gep": self.gep.GetValue().strip(),
            "port": int(self.port.GetValue().strip() or "0") or (22 if self.fajta.GetSelection() == 1 else 21),
            "felhasznalo": self.nev.GetValue().strip(),
            "jelszo": self.jelszo.GetValue(),
        }
        if not self.hely["gep"]:
            wx.MessageBox("A gép címe hiányzik.", "Hely", wx.OK | wx.ICON_WARNING, self)
            return
        self.EndModal(wx.ID_OK)


class TavoliFrame(wx.Frame):
    def __init__(self, main, hely: dict):
        szulo = main if isinstance(main, wx.Window) else None
        super().__init__(szulo, title="SuperDL – %s" % hely.get("gep", ""), size=(700, 480))
        self.main = main
        self.hely = hely
        self._ut = "/"
        self._nevek = []
        p = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        self.cim = wx.StaticText(p, label="/")
        v.Add(self.cim, 0, wx.ALL, 8)
        self.lista = wx.ListBox(p)
        self.lista.SetName("A távoli mappa")
        self.lista.Bind(wx.EVT_LISTBOX_DCLICK, self._nyit)
        v.Add(self.lista, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        sor = wx.BoxSizer(wx.HORIZONTAL)
        for cim, fn in (("&Letöltés ide…", self._le), ("&Feltöltés…", self._fel), ("&Vissza", self._vissza)):
            b = wx.Button(p, label=cim)
            b.Bind(wx.EVT_BUTTON, fn)
            sor.Add(b, 0, wx.RIGHT, 6)
        v.Add(sor, 0, wx.ALL, 8)
        p.SetSizer(v)
        self.CreateStatusBar()
        self.CentreOnParent()
        self.Show()
        self._tolts()

    def _kapocs(self):
        if self.hely.get("fajta") == "sftp":
            import paramiko
            szallito = paramiko.Transport((self.hely["gep"], int(self.hely["port"])))
            szallito.connect(username=self.hely.get("felhasznalo") or None,
                             password=self.hely.get("jelszo") or None)
            return paramiko.SFTPClient.from_transport(szallito), szallito
        ftp = FTP()
        ftp.connect(self.hely["gep"], int(self.hely["port"]), timeout=20)
        ftp.login(self.hely.get("felhasznalo") or "anonymous",
                  self.hely.get("jelszo") or "superdl@local")
        return ftp, None

    def _tolts(self):
        self.SetStatusText("Kapcsolódás…")
        try:
            kapocs, extra = self._kapocs()
        except Exception as exc:
            self.SetStatusText("Nem sikerült belépni: %s" % exc)
            return
        try:
            if self.hely.get("fajta") == "sftp":
                sorok = kapocs.listdir_attr(self._ut or ".")
                self._nevek = [s.filename for s in sorok]
            else:
                kapocs.cwd(self._ut)
                self._nevek = kapocs.nlst()
        except Exception as exc:
            self.SetStatusText("A lista nem jött meg: %s" % exc)
            self._nevek = []
        finally:
            try:
                kapocs.close()
            except Exception:
                pass
            if extra:
                extra.close()
        self._nevek = [n for n in self._nevek if n not in (".", "..")]
        self.cim.SetLabel(self._ut)
        self.lista.Set(self._nevek or ["(üres)"])
        if self._nevek:
            self.lista.SetSelection(0)
        self.SetStatusText("%d elem a távoli mappában." % len(self._nevek))

    def _nyit(self, _e=None):
        i = self.lista.GetSelection()
        if not (0 <= i < len(self._nevek)):
            return
        nev = self._nevek[i]
        self._ut = (self._ut.rstrip("/") + "/" + nev)
        self._tolts()

    def _vissza(self, _e=None):
        self._ut = os.path.dirname(self._ut.rstrip("/")) or "/"
        self._tolts()

    def _le(self, _e):
        i = self.lista.GetSelection()
        if not (0 <= i < len(self._nevek)):
            return
        from superdl import fajlvalaszto
        mappa = fajlvalaszto.valassz_mappat(self, "Hová töltse le", mondd=None)
        if not mappa:
            return
        nev = self._nevek[i]
        cel = os.path.join(mappa, nev)
        tavoli = self._ut.rstrip("/") + "/" + nev
        try:
            self._letolt(tavoli, cel)
        except Exception as exc:
            self.SetStatusText("A letöltés megállt: %s" % exc)
            return
        self.SetStatusText("Letöltve: %s" % cel)

    def _letolt(self, tavoli, cel):
        kapocs, extra = self._kapocs()
        try:
            with open(cel, "wb") as ki:
                if self.hely.get("fajta") == "sftp":
                    kapocs.getfo(tavoli, ki)
                else:
                    kapocs.retrbinary("RETR " + tavoli, ki.write, blocksize=1024 * 1024)
        finally:
            try:
                kapocs.close()
            except Exception:
                pass
            if extra:
                extra.close()

    def _fel(self, _e):
        from superdl import fajlvalaszto
        utak = fajlvalaszto.valassz_fajlokat(self, "Feltöltendő fájl", tobb=False)
        if not utak:
            return
        helyi = utak[0]
        nev = os.path.basename(helyi)
        tavoli = self._ut.rstrip("/") + "/" + nev
        kapocs, extra = self._kapocs()
        try:
            with open(helyi, "rb") as be:
                if self.hely.get("fajta") == "sftp":
                    kapocs.putfo(be, tavoli)
                else:
                    kapocs.storbinary("STOR " + tavoli, be, blocksize=1024 * 1024)
        except Exception as exc:
            self.SetStatusText("A feltöltés megállt: %s" % exc)
            return
        finally:
            try:
                kapocs.close()
            except Exception:
                pass
            if extra:
                extra.close()
        self.SetStatusText("Feltöltve: %s" % nev)
        self._tolts()
