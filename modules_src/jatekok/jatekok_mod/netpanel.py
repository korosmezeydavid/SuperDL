# -*- coding: utf-8 -*-
"""Közös ős a SuperDL saját ONLINE játék-paneljeihez (UNO, Blackjack, Póker,
Ország-Város). A lobbi / csevegés / netroom-kezelés / hang / felolvasás EGYSZER
van megírva itt; a játék-specifikus rész (kézkezelés, gombok, pontozás,
üzenet-feldolgozás) a leszármazottban marad.

A leszármazott `_build`-je hozza létre AZONOS néven a szükséges vezérlőket:
nev_mezo, kod_mezo, uj_gomb, csat_gomb, indit_gomb, _naplo, chat_be,
chat_atirat; továbbá az _sor_nev / _sor_lob (lobbi-sizerek), a _jatek_widgetek
/ _jatek_sizerek listák és a fő _v sizer. A leszármazott definiálja a
`_kezeld(u)` üzenet-feldolgozót. Opcionális `HELYI_NEV` a súgó-szöveghez;
`mod_valaszto` (ha van) csatlakozáskor letiltódik.
"""
import wx

from . import netroom


class NetPanelMixin:
    """Közös lobbi/chat/net/hang plumbing. Használat:
    `class XPanel(NetPanelMixin, wx.Panel): ...`."""

    HELYI_NEV = "helyi játék"

    # --------------------------------------------------------------- lobbi
    def _alap_nev(self):
        try:
            s = getattr(self.main, "settings", {}) or {}
            return (s.get("nev") or s.get("felhasznalo") or "").strip() or "Játékos"
        except Exception:
            return "Játékos"

    def _start_ellenoriz(self):
        if not netroom.ably_kulcs():
            self._mondd("Az online játék ebben a verzióban még nem elérhető. A "
                        "%s a másik fülön viszont mindig megy!" % self.HELYI_NEV)

    def _uj_szoba(self, e):
        self._nev = (self.nev_mezo.GetValue() or "Játékos").strip()
        kod = netroom.szobakod()
        self._szoba = netroom.NetSzoba(kod, self._nev)
        if not self._szoba.elerheto():
            self._mondd("Nincs online kulcs beállítva – nem tudok szobát nyitni.")
            return
        self._host = True
        self._jatekosok = [self._nev]
        self._szoba.figyel(self._uzenet_jott)
        self._szoba_reszek_lathato(True)
        self.kod_mezo.SetValue(kod)
        self.uj_gomb.Disable()
        self.csat_gomb.Disable()
        self.indit_gomb.Enable()
        self._mondd(f"Szoba nyitva! A kódod: {kod} (betűnként: {' '.join(kod)}). "
                    "Másold és küldd el a haverjaidnak, és ha mind bent vannak, "
                    "indítsd a játékot!")

    def _kod_masol(self, e):
        kod = (self.kod_mezo.GetValue() or "").strip()
        if not kod:
            self._mondd("Előbb nyiss egy szobát – akkor lesz kód a másoláshoz.")
            return
        try:
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(kod))
                wx.TheClipboard.Close()
                self._mondd(f"A(z) {kod} kód a vágólapon!")
        except Exception:
            self._mondd(f"A kód: {kod} – mondd be a többieknek.")

    def _csatlakozas(self, e):
        self._nev = (self.nev_mezo.GetValue() or "Játékos").strip()
        kod = (self.kod_mezo.GetValue() or "").strip().upper()
        if not kod:
            self._mondd("Írd be a szobakódot, amit a szervező mondott.")
            return
        self._szoba = netroom.NetSzoba(kod, self._nev)
        if not self._szoba.elerheto():
            self._mondd("Nincs online kulcs beállítva – nem tudok csatlakozni.")
            return
        self._host = False
        self._szoba.figyel(self._uzenet_jott)
        self._szoba_reszek_lathato(True)
        self._szoba.kuld("csatlakozott", {"nev": self._nev})
        self.uj_gomb.Disable()
        self.csat_gomb.Disable()
        mod = getattr(self, "mod_valaszto", None)
        if mod:
            try:
                mod.Disable()
            except Exception:
                pass
        self._mondd(f"Csatlakoztál a(z) {kod} szobához {self._nev} néven. "
                    "Várd, hogy a szervező elindítsa a játékot!")

    # --------------------------------------------------------------- hálózat
    def _uzenet_jott(self, u):
        if not self._closing:
            wx.CallAfter(self._kezeld, u)

    # --------------------------------------------------------------- csevegés
    def _chat_kuld(self):
        t = (self.chat_be.GetValue() or "").strip()
        if not t or not self._szoba:
            return
        self._szoba.kuld("csevej", {"szoveg": t})
        self.chat_be.SetValue("")
        self.chat_be.SetFocus()

    def _chat_fogad(self, ki, adat):
        szoveg = (adat.get("szoveg") or "").strip()
        if not szoveg:
            return
        sajat = (ki == self._nev)
        cimke = "Te" if sajat else (ki or "Valaki")
        try:
            self.chat_atirat.AppendText(f"{cimke}: {szoveg}\n")
        except Exception:
            pass
        if not sajat:
            self._mondd(f"{ki} üzenete: {szoveg}")

    # --------------------------------------------------------------- láthatóság
    def _szoba_reszek_lathato(self, latszik):
        try:
            for w in self._jatek_widgetek:
                w.Show(latszik)
            for s in self._jatek_sizerek:
                self._v.Show(s, latszik, recursive=True)
            self._v.Layout()
        except Exception:
            pass

    def _lobbi_lathato(self, latszik):
        try:
            self._v.Show(self._sor_nev, latszik, recursive=True)
            self._v.Show(self._sor_lob, latszik, recursive=True)
            self._v.Layout()
        except Exception:
            pass

    # --------------------------------------------------------------- hang / szöveg
    def _hang(self, nev):
        try:
            import os
            from superdl.audioengine import Player
            mappa = os.path.join(os.path.dirname(__file__), "szerencsekerek_hang")
            ut = None
            for ext in (".wav", ".mp3"):
                p = os.path.join(mappa, nev + ext)
                if os.path.isfile(p):
                    ut = p
                    break
            if not ut:
                return
            if self._hang_player is None:
                self._hang_player = Player()
            self._hang_player.play(ut, "")
        except Exception:
            pass

    def _mondd(self, szoveg):
        if self._closing or not (szoveg or "").strip():
            return
        try:
            self._naplo.AppendText(szoveg + "\n")
        except Exception:
            pass
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

    # --------------------------------------------------------------- leállítás
    def leallit(self):
        self._closing = True
        try:
            if self._szoba:
                self._szoba.leallit()
        except Exception:
            pass
