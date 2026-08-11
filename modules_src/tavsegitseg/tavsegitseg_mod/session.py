# -*- coding: utf-8 -*-
"""Távsegítség – a MUNKAMENET (vezérlő-hurok): szerepek, a beleegyezés/pánik
kapu, és az események útja a két gép között.

Szándékosan CSERÉLHETŐ transzporttal dolgozik (bármi, aminek van `kuld(dict)`
metódusa és `set_fogado(cb)`-vel visszahív a beérkező dict-tel), így a
biztonság-kritikus logika VALÓS hálózat nélkül is végigtesztelhető. A valós
időben az események a Csevejcenter alacsony-késésű UDP P2P csatornáján mennek
majd; a szoba-kód/kézfogás a netroom-on (Ably).

SZEREPEK:
  „segitett”  – akit irányítanak: ő ENGEDÉLYEZI (beleegyezés után) az
                irányítást, és NÁLA fut a Vezerlo (injektálás). Csak akkor
                injektál, ha az irányítás aktív ÉS a Vezerlo aktív.
  „iranyito”  – aki segít: elkapott egér-/billentyű-eseményeket KÜLD, de csak
                ha az irányítás aktív (a segített engedélyezte).

Bármelyik fél BÁRMIKOR leállíthatja az irányítást (pánik) – ez azonnal csukja a
Vezerlo kapuját és jelez a másiknak."""
from .vezerles import Vezerlo


class Munkamenet:
    def __init__(self, transport, szerep, nev, vezerlo=None, on_allapot=None):
        assert szerep in ("segitett", "iranyito")
        self.transport = transport
        self.szerep = szerep
        self.nev = nev
        self.vezerlo = vezerlo if vezerlo is not None else Vezerlo()
        self.iranyit = False           # aktív-e most az irányítás
        self.tars = ""                 # a másik fél neve (kézfogásból)
        self._on_allapot = on_allapot  # cb(esemeny_kulcs, adat) – UI/felolvasás
        self._closing = False
        if hasattr(transport, "set_fogado"):
            transport.set_fogado(self.fogad)

    # ------------------------------------------------------------ jelzés
    def _jelez(self, kulcs, adat=None):
        if self._on_allapot and not self._closing:
            try:
                self._on_allapot(kulcs, adat or {})
            except Exception:
                pass

    # ------------------------------------------------- SEGÍTETT: engedély
    def iranyitas_engedelyez(self):
        """A SEGÍTETT hívja – a beleegyezés elfogadása UTÁN. Ettől kezdve az
        irányító eseményeit végrehajtjuk (amíg le nem állítjuk)."""
        if self.szerep != "segitett" or self._closing:
            return
        self.iranyit = True
        self.vezerlo.aktiv = True
        self.transport.kuld({"t": "vezerles_be", "ki": self.nev})
        self._jelez("iranyitas_be", {"ki": self.tars})

    # ------------------------------------------------- PÁNIK / leállítás
    def iranyitas_leallit(self, panik=False):
        """Bármelyik fél hívhatja. Azonnal csukja a kaput és jelez a másiknak."""
        volt = self.iranyit
        self.iranyit = False
        self.vezerlo.aktiv = False
        if not self._closing:
            try:
                self.transport.kuld({"t": "vezerles_ki", "ki": self.nev,
                                     "panik": bool(panik)})
            except Exception:
                pass
        if volt:
            self._jelez("iranyitas_ki", {"panik": panik})

    # ------------------------------------------------- IRÁNYÍTÓ: küldés
    def esemeny_kuld(self, esemeny):
        """Az IRÁNYÍTÓ egy elkapott eseményt küld – CSAK ha az irányítás aktív."""
        if self.szerep != "iranyito" or not self.iranyit or self._closing:
            return False
        self.transport.kuld({"t": "esemeny", "e": esemeny})
        return True

    def csevej_kuld(self, szoveg):
        if self._closing or not szoveg:
            return
        self.transport.kuld({"t": "csevej", "ki": self.nev, "szoveg": szoveg})

    # ------------------------------------------------- beérkező üzenetek
    def fogad(self, uzenet):
        if self._closing or not isinstance(uzenet, dict):
            return
        t = uzenet.get("t")
        if t == "kezfogas":
            self.tars = (uzenet.get("ki") or "").strip()
            self._jelez("tars", {"ki": self.tars})
        elif t == "vezerles_be":
            # a segített engedélyezte → az irányító mostantól küldhet
            self.iranyit = True
            if self.szerep == "iranyito":
                self._jelez("iranyitas_be", {"ki": self.tars})
        elif t == "vezerles_ki":
            self.iranyit = False
            self.vezerlo.aktiv = False
            self._jelez("iranyitas_ki", {"panik": bool(uzenet.get("panik"))})
        elif t == "esemeny":
            # CSAK a segített injektál, és CSAK ha az irányítás aktív (a Vezerlo
            # `aktiv` kapuja a második, független biztosíték)
            if self.szerep == "segitett" and self.iranyit:
                self.vezerlo.alkalmaz(uzenet.get("e"))
        elif t == "csevej":
            self._jelez("csevej", {"ki": uzenet.get("ki"),
                                   "szoveg": uzenet.get("szoveg", "")})

    def leallit(self):
        self._closing = True
        self.iranyit = False
        self.vezerlo.aktiv = False
