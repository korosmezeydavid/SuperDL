# -*- coding: utf-8 -*-
"""Blackjack – host-authoritative ONLINE motor (fejetlen, wx és hálózat nélkül).

A közös online-héj második motorja. A blackjackben a játékos-lapok NYÍLTAK, így
itt nincs bonyolult magánkéz – EGYETLEN rejtett elem az OSZTÓ lefordított lapja,
amit a host nem broadcastol, amíg le nem jön az osztó köre (`oszto_rejtett`).

Több játékos EGY közös osztó ellen: mindenki kap 2 lapot (az osztó 1 nyílt + 1
rejtett), sorban HÍV LAPOT / MEGÁLL / DUPLÁZ, majd az osztó 17-ig húz, és
mindenki külön elszámol az osztóval. Fix tét, egyszerű zseton-rendszer. A
szabályok közkincsek; a lap-összeg (ász 11/1) a helyi Blackjackkel azonos.
"""
import random

_SZINEK = ["pikk", "kör", "káró", "treff"]
_RANGOK = ["ász", "2", "3", "4", "5", "6", "7", "8", "9", "10",
           "bubi", "dáma", "király"]


def _ertek(rang):
    if rang == "ász":
        return 11
    if rang in ("bubi", "dáma", "király", "10"):
        return 10
    return int(rang)


def osszeg(kez):
    """A kéz blackjack-összege; az ászok 11→1-re csökkennek, amíg kell."""
    o = sum(_ertek(r) for _, r in kez)
    aszok = sum(1 for _, r in kez if r == "ász")
    while o > 21 and aszok:
        o -= 10
        aszok -= 1
    return o


def blackjack(kez):
    return len(kez) == 2 and osszeg(kez) == 21


def lap_nev(k):
    return "%s %s" % (k[1], k[0])


def kez_nev(kez):
    return ", ".join(lap_nev(k) for k in kez) if kez else "(nincs lap)"


class BlackjackHost:
    """Host-oldali blackjack több játékossal EGY osztó ellen. Fázisok:
    „jatek" (a játékosok sorban cselekszenek), „vege" (a kör elszámolva)."""

    def __init__(self, jatekosok, kezdo_zseton=100, tet=10):
        self.jatekosok = [j for j in jatekosok if j] or ["Játékos"]
        self.alap_tet = int(tet)
        self.zseton = {n: int(kezdo_zseton) for n in self.jatekosok}
        self.kor = 0
        self.fazis = "keszen"
        self.uj_leosztas()

    # ------------------------------------------------------------------ osztás
    def _uj_pakli(self):
        p = [(sz, r) for sz in _SZINEK for r in _RANGOK]
        random.shuffle(p)
        return p

    def uj_leosztas(self):
        """Új kör: tétlevonás, osztás, természetes blackjackek. A host hívja."""
        self.pakli = self._uj_pakli()
        self.kor += 1
        self.tet = {}
        self.kezek = {}
        self.statusz = {}          # jatszik / all / bust / blackjack / kihagy
        self.eredmeny = {}
        for n in self.jatekosok:
            if self.zseton[n] >= self.alap_tet:
                self.zseton[n] -= self.alap_tet
                self.tet[n] = self.alap_tet
                self.kezek[n] = [self.pakli.pop(), self.pakli.pop()]
                self.statusz[n] = "jatszik"
            else:
                self.tet[n] = 0
                self.kezek[n] = []
                self.statusz[n] = "kihagy"
        self.oszto = [self.pakli.pop(), self.pakli.pop()]   # [nyílt, rejtett]
        self.oszto_rejtett = True
        for n in self.jatekosok:
            if self.statusz[n] == "jatszik" and blackjack(self.kezek[n]):
                self.statusz[n] = "blackjack"
        self.fazis = "jatek"
        self.aktiv_idx = None
        for i, n in enumerate(self.jatekosok):
            if self.statusz[n] == "jatszik":
                self.aktiv_idx = i
                break
        if self.aktiv_idx is None:          # mindenki bj vagy kihagy
            self._oszto_es_zaras()

    # --------------------------------------------------------------- lekérdezők
    @property
    def soron(self):
        if self.fazis == "jatek" and self.aktiv_idx is not None:
            return self.jatekosok[self.aktiv_idx]
        return ""

    def allapot_publikus(self, uzenet=""):
        if self.oszto_rejtett:
            oszto_lapok = [self.oszto[0], ("rejtett", "rejtett")]
            oszto_osszeg = None
        else:
            oszto_lapok = list(self.oszto)
            oszto_osszeg = osszeg(self.oszto)
        return {
            "fazis": self.fazis, "kor": self.kor, "soron": self.soron,
            "oszto_lapok": [list(k) for k in oszto_lapok],
            "oszto_osszeg": oszto_osszeg,
            "kezek": {n: [list(k) for k in self.kezek[n]] for n in self.jatekosok},
            "osszegek": {n: (osszeg(self.kezek[n]) if self.kezek[n] else 0)
                         for n in self.jatekosok},
            "statusz": dict(self.statusz), "zseton": dict(self.zseton),
            "tet": dict(self.tet), "eredmeny": dict(self.eredmeny),
            "jatekosok": list(self.jatekosok), "uzenet": uzenet,
        }

    # ------------------------------------------------------------------ belső
    def _kov_aktiv(self):
        for i in range(self.aktiv_idx + 1, len(self.jatekosok)):
            if self.statusz[self.jatekosok[i]] == "jatszik":
                return i
        return None

    def _lep_kov(self):
        nxt = self._kov_aktiv()
        if nxt is None:
            self._oszto_es_zaras()
        else:
            self.aktiv_idx = nxt

    def _oszto_es_zaras(self):
        self.oszto_rejtett = False
        verseny = any(self.statusz[n] in ("all", "blackjack")
                      for n in self.jatekosok)
        if verseny:
            while osszeg(self.oszto) < 17:
                self.oszto.append(self.pakli.pop())
        self._elszamol()
        self.fazis = "vege"
        self.aktiv_idx = None

    def _elszamol(self):
        oo = osszeg(self.oszto)
        oszto_bj = blackjack(self.oszto)
        oszto_bust = oo > 21
        for n in self.jatekosok:
            st = self.statusz[n]
            if st == "kihagy":
                self.eredmeny[n] = "kihagyta (nincs elég zseton)"
                continue
            if st == "bust":
                self.eredmeny[n] = "vesztett – befuccsolt"
                continue
            if st == "blackjack":
                if oszto_bj:
                    self.zseton[n] += self.tet[n]
                    self.eredmeny[n] = "döntetlen – mindkettő blackjack"
                else:
                    self.zseton[n] += int(self.tet[n] * 2.5)
                    self.eredmeny[n] = "BLACKJACK! 3:2 nyeremény"
                continue
            jo = osszeg(self.kezek[n])            # st == "all"
            if oszto_bust or jo > oo:
                self.zseton[n] += self.tet[n] * 2
                self.eredmeny[n] = "nyert"
            elif jo == oo:
                self.zseton[n] += self.tet[n]
                self.eredmeny[n] = "döntetlen"
            else:
                self.eredmeny[n] = "vesztett"

    # ------------------------------------------------------------------ akció
    def akcio(self, ki, tipus, adat=None):
        if self.fazis != "jatek" or self.aktiv_idx is None:
            return None
        aktiv = self.jatekosok[self.aktiv_idx]
        if ki != aktiv or self.statusz[ki] != "jatszik":
            return None

        if tipus == "hit":
            self.kezek[ki].append(self.pakli.pop())
            o = osszeg(self.kezek[ki])
            uz = f"{ki} lapot kért: {lap_nev(self.kezek[ki][-1])}, összeg {o}."
            if o > 21:
                self.statusz[ki] = "bust"
                uz += f" {ki} túllépte a 21-et – befuccsolt!"
                self._lep_kov()
            return self.allapot_publikus(uz)

        if tipus == "stand":
            self.statusz[ki] = "all"
            uz = f"{ki} megáll {osszeg(self.kezek[ki])}-nél."
            self._lep_kov()
            return self.allapot_publikus(uz)

        if tipus == "dupla":
            if len(self.kezek[ki]) != 2 or self.zseton[ki] < self.tet[ki]:
                return self.allapot_publikus(
                    f"{ki}: duplázni csak az első két lappal és elég zsetonnal "
                    "lehet.")
            self.zseton[ki] -= self.tet[ki]
            self.tet[ki] *= 2
            self.kezek[ki].append(self.pakli.pop())
            o = osszeg(self.kezek[ki])
            uz = (f"{ki} DUPLÁZOTT, kapott: {lap_nev(self.kezek[ki][-1])}, "
                  f"összeg {o}.")
            if o > 21:
                self.statusz[ki] = "bust"
                uz += f" {ki} befuccsolt!"
            else:
                self.statusz[ki] = "all"
            self._lep_kov()
            return self.allapot_publikus(uz)

        return None
