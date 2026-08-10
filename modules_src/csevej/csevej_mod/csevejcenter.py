# -*- coding: utf-8 -*-
"""Csevejcenter – a szoba LOGIKÁJA (jelenlét + üzenetváltás) a NetSzoba fölött.

Ez a réteg NEM tud a felületről és nem beszél a képernyőolvasóhoz: csak
esemény-CALLBACKeket hív (on_uzenet, on_belepett, on_kilepett, on_tagok),
amelyeket a wx-ablak köt be és `wx.CallAfter`-rel tesz a felületre. Így a
logika wx nélkül is tesztelhető.

Jelenlét (presence) valós idejű SZÍVVERÉSSEL: mindenki ~5 mp-enként küld egy
„sziv” jelet a nevével; akiről _TAG_LEJAR mp-en belül nem hallunk, kilépettnek
számít. Nincs központi szerver – a szoba egy Ably-csatorna.
"""
import threading
import time

from .netroom import NetSzoba, ably_kulcs, szobakod   # noqa: F401 (újraexport)

_SZIV_KOZ = 5.0        # szívverés-küldés köze (mp)
_TAG_LEJAR = 16.0      # ennyi mp néma után kilépettnek vesszük a tagot
_POLL_KOZ = 1.0        # az új üzenetek lekérésének köze (mp)


class Csevejszoba:
    """Egy élő csevegő-szoba. A `nev` a saját megjelenítendő neved, a `kod` a
    szoba kódja. A UI beállítja a callbackeket, majd `belep()`-et hív."""

    def __init__(self, kod: str, nev: str, kulcs: str = ""):
        self.nev = (nev or "").strip() or "Vendég"
        self.kod = (kod or "").strip().upper()
        self.net = NetSzoba(self.kod, self.nev, kulcs, elotag="csevej")
        self._tagok: dict = {}          # nev -> utoljára hallottuk (time.time())
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._sziv_szal = None
        self._hang_host = None          # {ip, port, ki} – az utolsó hirdetett hang-host
        # UI-callbackek (mind opcionális; a UI állítja be)
        self.on_uzenet = None           # (nev: str, szoveg: str, sajat: bool)
        self.on_belepett = None         # (nev: str)
        self.on_kilepett = None         # (nev: str)
        self.on_tagok = None            # (nevek: list[str])  – bármely változáskor
        self.on_hang_host = None        # (ip, port, ki) – valaki hang-hostot hirdetett

    # ------------------------------------------------------------------
    def elerheto(self) -> bool:
        """Van-e Ably-kulcs és szobakód (különben nem tud csatlakozni)."""
        return self.net.elerheto()

    def tagok(self) -> list:
        with self._lock:
            return sorted(self._tagok.keys(), key=str.lower)

    def belep(self):
        """Belépés a szobába: előzmény némán, majd élő figyelés + szívverés."""
        # magunkat rögtön a tagok közé vesszük (a saját szívverésünk is frissíti)
        with self._lock:
            self._tagok[self.nev] = time.time()
        # 1) ELŐZMÉNY – a korábbi CSEVEGÉST némán behozzuk (jelenlétet nem; a régi
        #    szívverések nem élő jelenlét), és megjegyezzük az utolsó hang-hostot
        try:
            for u in self.net.uj_uzenetek():
                if u.get("tipus") == "uzenet":
                    self._uzenet(u, elozmeny=True)
                elif u.get("tipus") == "hang_host":
                    self._hang_host_be(u, ertesit=False)
        except Exception:
            pass
        self._ertesit_tagok()
        # 2) ÉLŐ figyelés + belépés-jelzés + szívverés-szál
        self.net.figyel(self._fogad, koz=_POLL_KOZ)
        try:
            self.net.kuld("belep")
        except Exception:
            pass
        self._sziv_szal = threading.Thread(target=self._sziv_loop, daemon=True)
        self._sziv_szal.start()

    def kuld(self, szoveg: str) -> bool:
        """Csevegő-üzenet küldése. Azonnal meg is jeleníti (optimista), a
        visszaérkező saját visszhangot pedig eldobjuk."""
        szoveg = (szoveg or "").strip()
        if not szoveg:
            return False
        self.net.kuld("uzenet", {"szoveg": szoveg})
        if self.on_uzenet:
            self.on_uzenet(self.nev, szoveg, True)   # optimista, saját
        return True

    def kilep(self):
        """Kilépés: jelzés a többieknek + a szálak leállítása."""
        self._stop.set()
        try:
            self.net.kuld("kilep")
        except Exception:
            pass
        self.net.leallit()

    # ------------------------------------------------------------------
    def _fogad(self, u: dict):
        """Egy beérkező üzenet feldolgozása (a poll-szálon fut)."""
        tipus = u.get("tipus")
        ki = u.get("ki") or "Valaki"
        sajat = (ki == self.nev)
        if tipus == "uzenet":
            if not sajat:                 # a sajátot már optimistán megjelenítettük
                self._uzenet(u, elozmeny=False)
        elif tipus == "belep":
            if not sajat:
                self._tag_frissit(ki, uj_belepo=True)
        elif tipus == "sziv":
            if not sajat:
                self._tag_frissit(ki, uj_belepo=False)
        elif tipus == "kilep":
            if not sajat:
                self._tag_kilep(ki)
        elif tipus == "hang_host":
            self._hang_host_be(u, ertesit=True)

    def _uzenet(self, u: dict, elozmeny: bool):
        adat = u.get("adat") or {}
        szoveg = str(adat.get("szoveg", "")).strip()
        if not szoveg:
            return
        # az üzenet küldője is „jelen van” – frissítsük a jelenlétét (némán)
        ki = u.get("ki") or "Valaki"
        if ki != self.nev:
            self._tag_frissit(ki, uj_belepo=False, nemakcio=True)
        if self.on_uzenet:
            self.on_uzenet(ki, szoveg, ki == self.nev)

    def _tag_frissit(self, nev: str, uj_belepo: bool, nemakcio: bool = False):
        """Egy tag jelenlétének frissítése; új tagnál értesítés."""
        uj = False
        with self._lock:
            uj = nev not in self._tagok
            self._tagok[nev] = time.time()
        if uj and not nemakcio and self.on_belepett:
            self.on_belepett(nev)
        if uj:
            self._ertesit_tagok()

    def _tag_kilep(self, nev: str):
        volt = False
        with self._lock:
            volt = self._tagok.pop(nev, None) is not None
        if volt:
            if self.on_kilepett:
                self.on_kilepett(nev)
            self._ertesit_tagok()

    def _ertesit_tagok(self):
        if self.on_tagok:
            self.on_tagok(self.tagok())

    # ---- hang-host hirdetés (a valós idejű hanghoz) -------------------
    def _hang_host_be(self, u: dict, ertesit: bool):
        adat = u.get("adat") or {}
        ip = str(adat.get("ip", "")).strip()
        port = int(adat.get("port", 0) or 0)
        ki = u.get("ki") or ""
        if not ip or not port:
            return
        self._hang_host = {"ip": ip, "port": port, "ki": ki}
        if ertesit and self.on_hang_host:
            self.on_hang_host(ip, port, ki)

    def hang_host(self):
        """Az utolsó ismert hang-host {ip, port, ki} vagy None. A hívó a
        jelenléttel (tagok) egészítheti ki, hogy él-e még."""
        return dict(self._hang_host) if self._hang_host else None

    def hirdet_host(self, ip: str, port: int):
        """Hostként bejelentjük a szobában a hang-címünket (a többiek ehhez
        csatlakoznak). Ismételt hívással frissíthető (késői belépőknek)."""
        try:
            self.net.kuld("hang_host", {"ip": ip, "port": int(port)})
        except Exception:
            pass

    def _sziv_loop(self):
        """Periodikus szívverés + a lejárt (néma) tagok kiszűrése."""
        # azonnali első szívverés, hogy a többiek gyorsan lássanak minket
        try:
            self.net.kuld("sziv")
        except Exception:
            pass
        while not self._stop.wait(_SZIV_KOZ):
            try:
                self.net.kuld("sziv")
            except Exception:
                pass
            with self._lock:
                self._tagok[self.nev] = time.time()   # magunkat sose járassuk le
            self._lejart_tagok()

    def _lejart_tagok(self):
        most = time.time()
        lejart = []
        with self._lock:
            for nev, ido in list(self._tagok.items()):
                if nev != self.nev and (most - ido) > _TAG_LEJAR:
                    del self._tagok[nev]
                    lejart.append(nev)
        for nev in lejart:
            if self.on_kilepett:
                self.on_kilepett(nev)
        if lejart:
            self._ertesit_tagok()
