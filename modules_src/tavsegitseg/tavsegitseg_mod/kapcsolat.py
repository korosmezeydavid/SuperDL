# -*- coding: utf-8 -*-
"""Távsegítség – a KAPCSOLAT-kezelő: a netroom (szoba-kód + kézfogás) és a P2P
(valós idejű forgalom) összekötése. A Munkamenet TRANSZPORTJAKÉNT viselkedik
(kuld/set_fogado), így a felső réteg nem tud a hálózat részleteiről.

Menet: a SEGÍTETT „Új szoba"-t nyit (kap egy kódot), az IRÁNYÍTÓ a kóddal
csatlakozik. Mindketten elküldik a netroom-on a P2P-elérési jelölteiket
(publikus STUN + helyi címek); amint megkapják a másikét, a P2P hole-punchinggal
összekapcsolódik, és onnantól a vezérlés (később a hang) a gyors P2P-n megy.
Ha a P2P nem áll össze (pl. szimmetrikus NAT), a vezérlés a netroom-on megy
tartalékként – lassabb, de a billentyűzet így is működik (a hang ilyenkor nem).
"""
import json

from . import netroom
from .p2phalozat import P2PHalozat


class Kapcsolat:
    def __init__(self, nev):
        self.nev = nev
        self._szoba = None
        self._p2p = P2PHalozat(on_adat=self._p2p_adat, on_kesz=self._jelez_kesz)
        self._host = False
        self._fogado = None            # a Munkamenet.fogad (vezérlés-üzenetek)
        self._on_hang = None           # cb(pcm: bytes) – beérkező hang
        self._on_kesz = None           # cb() amikor a P2P élővé válik
        self._sajat_cimek = []
        self._viszont_kuldve = False
        self._closing = False

    # -- a Munkamenet transzport-interfésze --
    def set_fogado(self, cb):
        self._fogado = cb

    def set_hang_fogado(self, cb):
        self._on_hang = cb

    def figyeld_kesz(self, cb):
        self._on_kesz = cb

    # -- belépés --
    def uj_szoba(self, stun_lekeres=True):
        """SEGÍTETT: szobát nyit, visszaadja a kódot (vagy None, ha nincs kulcs)."""
        kod = netroom.szobakod()
        self._szoba = netroom.NetSzoba(kod, self.nev)
        if not self._szoba.elerheto():
            return None
        self._host = True
        self._szoba.figyel(self._netroom)
        self._sajat_cimek = self._p2p.indit(stun_lekeres)
        self._kuld_jeloltek()
        return kod

    def csatlakozas(self, kod, stun_lekeres=True):
        """IRÁNYÍTÓ: csatlakozik a kóddal. True, ha a szoba elérhető."""
        self._szoba = netroom.NetSzoba((kod or "").strip().upper(), self.nev)
        if not self._szoba.elerheto():
            return False
        self._szoba.figyel(self._netroom)
        self._sajat_cimek = self._p2p.indit(stun_lekeres)
        self._kuld_jeloltek()
        return True

    def _kuld_jeloltek(self):
        if self._szoba:
            self._szoba.kuld("jeloltek",
                             {"nev": self.nev, "cimek": self._sajat_cimek})

    # -- netroom (kézfogás + tartalék) --
    def _netroom(self, u):
        if self._closing:
            return
        t = u.get("tipus")
        adat = u.get("adat") or {}
        if adat.get("nev") == self.nev:      # a saját üzenetünk visszhangja – át
            return
        if t == "jeloltek":
            self._p2p.tars_jeloltek(adat.get("cimek", []))
            # biztos, ami biztos: viszont-küldjük a sajátunkat (ha a másik lemaradt
            # a history-ról), de csak egyszer
            if not self._viszont_kuldve:
                self._viszont_kuldve = True
                self._kuld_jeloltek()
        elif t == "fallback":
            if self._fogado:
                self._fogado(adat.get("d") or {})

    # -- P2P beérkező (al-típus: 0 = vezérlés-JSON, 1 = hang-PCM) --
    def _p2p_adat(self, payload):
        if not payload:
            return
        self._jelez_kesz()
        sub, body = payload[0], payload[1:]
        if sub == 0:
            try:
                d = json.loads(body.decode("utf-8"))
            except Exception:
                return
            if self._fogado:
                self._fogado(d)
        elif sub == 1:
            if self._on_hang:
                self._on_hang(body)

    def _jelez_kesz(self):
        if self._on_kesz:
            cb, self._on_kesz = self._on_kesz, None
            try:
                cb()
            except Exception:
                pass

    # -- vezérlés-küldés (P2P al-típus 0, tartalék netroom) --
    def kuld(self, uzenet):
        if self._closing:
            return
        try:
            b = b"\x00" + json.dumps(uzenet).encode("utf-8")
        except Exception:
            return
        if not self._p2p.kuld(b):
            if self._szoba:                  # P2P még nem áll → netroom-tartalék
                self._szoba.kuld("fallback", {"nev": self.nev, "d": uzenet})

    # -- hang-küldés (CSAK P2P al-típus 1; a hang nem megy netroom-tartalékon) --
    def hang_kuld(self, pcm):
        if self._closing or not pcm:
            return
        self._p2p.kuld(b"\x01" + pcm)

    def kesz(self):
        return self._p2p.kesz()

    def leallit(self):
        self._closing = True
        try:
            self._p2p.leallit()
        except Exception:
            pass
        try:
            if self._szoba:
                self._szoba.leallit()
        except Exception:
            pass
