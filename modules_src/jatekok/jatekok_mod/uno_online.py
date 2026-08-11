# -*- coding: utf-8 -*-
"""UNO – host-authoritative ONLINE motor (fejetlen, wx és hálózat nélkül).

Ez a közös „online-héj" első alkalmazása a saját kártyajátékokra. A LÉNYEG a
MAGÁNKÉZ: a host oszt és a teljes állapotot ő tartja, de mindenki CSAK a saját
kezét kapja meg (`kez(nev)`), a többiektől csak a LAPSZÁMOT látja
(`allapot_publikus`). Így egy gépen sem lehet más lapjába lesni. A motor sem
wx-ről, sem Ably-ról nem tud → gépi teszttel teljesen ellenőrizhető, pontosan
mint a Szerencsekerék `OnlineHost`-ja.

A szabályok a `jatekok/sajat.py` konzolos `jatek_uno`-jával azonosak (ugyanazok
a segédfüggvények): színben/értékben egyező vagy Színkérő rakható; húzás után a
húzott lap LERAKHATÓ, ha illik; kihagyás/irányváltó/+2/+4; egy lapnál UNO, nulla
lapnál győzelem. Nincs laphúzás-stackelés és nincs +4-kihívás (egyszerű UNO).
"""
import random

from .jatekok import sajat as SZK


class UnoHost:
    """Host-oldali UNO állapotgép. Akciókat kap, PUBLIKUS állapotot ad, a
    magánkezet külön (`kez`). Fázisok: „jatek", „huzas_utan", „vege"."""

    def __init__(self, jatekosok, kezdo_lapszam=7):
        self.jatekosok = [j for j in jatekosok if j] or ["Játékos"]
        self.n = len(self.jatekosok)
        self.kezdo_lapszam = int(kezdo_lapszam)
        self._oszt()

    # ------------------------------------------------------------------ osztás
    def _oszt(self):
        self.pakli = SZK._uno_pakli()
        self.dobo = []
        self.kezek = {nev: [self.pakli.pop() for _ in range(self.kezdo_lapszam)]
                      for nev in self.jatekosok}
        # kezdő felső lap: se akció, se Színkérő (ahogy a konzolban)
        while True:
            top = self.pakli.pop()
            if top[0] != "szín" and top[1] not in ("kihagy", "irany", "+2"):
                break
            self.pakli.insert(0, top)
        self.dobo.append(top)
        self.szin, self.ertek = top
        self.irany = 1
        self.aktiv_idx = 0
        self.fazis = "jatek"        # jatek / huzas_utan / vege
        self.gyoztes = None
        self._huzott = None         # a most húzott lap (huzas_utan fázisban)

    # --------------------------------------------------------------- lekérdezők
    @property
    def soron(self):
        return self.jatekosok[self.aktiv_idx]

    def kez(self, nev):
        """A NÉV játékos saját keze (csak neki küldendő)."""
        return list(self.kezek.get(nev, []))

    def allapot_publikus(self, uzenet=""):
        """Amit MINDENKI megkaphat – idegen lapok NÉLKÜL, csak lapszám."""
        return {
            "fazis": self.fazis,
            "soron": self.soron if self.fazis != "vege" else "",
            "felso": SZK._uno_top_nev(self.szin, self.ertek),
            "szin": self.szin, "ertek": self.ertek, "irany": self.irany,
            "lapszamok": {n: len(self.kezek[n]) for n in self.jatekosok},
            "jatekosok": list(self.jatekosok),
            "gyoztes": self.gyoztes, "pakli_db": len(self.pakli),
            "uzenet": uzenet,
        }

    # ------------------------------------------------------------------ belső
    def _huz(self, nev, db=1):
        for _ in range(db):
            if not self.pakli:
                if len(self.dobo) <= 1:
                    return
                felso = self.dobo[-1]
                maradek = self.dobo[:-1]
                random.shuffle(maradek)
                self.pakli, self.dobo = maradek, [felso]
            self.kezek[nev].append(self.pakli.pop())

    def _lep_kov(self, kihagy=False):
        self.aktiv_idx = (self.aktiv_idx + self.irany) % self.n
        if kihagy:
            self.aktiv_idx = (self.aktiv_idx + self.irany) % self.n

    def _lerak(self, nev, kartya, valasztott_szin=None):
        """Egy lap lerakása + a lap hatása. Visszaadja a felolvasandó üzenetet."""
        self.kezek[nev].remove(kartya)
        self.dobo.append(kartya)
        if kartya[0] == "szín":
            szin = valasztott_szin or SZK._uno_gep_szin(self.kezek[nev])
            self.szin, self.ertek = szin, kartya[1]
            uz = f"{nev} {SZK._uno_nev(kartya)}-t rakott. A kért szín: {szin}."
        else:
            self.szin, self.ertek = kartya
            uz = f"{nev} lerakott: {SZK._uno_nev(kartya)}."
        if len(self.kezek[nev]) == 1:
            uz += f" {nev}: UNO!"
        if len(self.kezek[nev]) == 0:
            self.gyoztes = nev
            self.fazis = "vege"
            return uz + f" {nev} KIFOGYOTT A LAPOKBÓL – NYERT!"
        kihagy = False
        e = kartya[1]
        if e == "kihagy":
            kihagy = True
        elif e == "irany":
            self.irany *= -1
        elif e == "+2":
            kov = self.jatekosok[(self.aktiv_idx + self.irany) % self.n]
            self._huz(kov, 2)
            kihagy = True
            uz += f" {kov} húz két lapot és kimarad."
        elif e == "+4":
            kov = self.jatekosok[(self.aktiv_idx + self.irany) % self.n]
            self._huz(kov, 4)
            kihagy = True
            uz += f" {kov} húz négy lapot és kimarad."
        self._lep_kov(kihagy)
        return uz

    # ------------------------------------------------------------------ akció
    def akcio(self, ki, tipus, adat=None):
        """A soron lévő játékos lépése. Visszaad: PUBLIKUS állapot (dict), vagy
        None, ha érvénytelen (nem ő van soron / rossz fázis / rossz akció)."""
        if self.fazis == "vege" or ki != self.soron:
            return None
        d = adat if isinstance(adat, dict) else {}

        if self.fazis == "jatek":
            if tipus == "rak":
                idx = d.get("index", adat if isinstance(adat, int) else None)
                kez = self.kezek[ki]
                if idx is None or not (0 <= idx < len(kez)):
                    return None
                kartya = kez[idx]
                if not SZK._uno_rakhato(kartya, self.szin, self.ertek):
                    return self.allapot_publikus(
                        f"{ki}: az a lap most nem rakható.")
                return self.allapot_publikus(
                    self._lerak(ki, kartya, d.get("szin")))
            if tipus == "huz":
                self._huz(ki, 1)
                uj = self.kezek[ki][-1]
                if SZK._uno_rakhato(uj, self.szin, self.ertek):
                    self.fazis = "huzas_utan"
                    self._huzott = uj
                    return self.allapot_publikus(
                        f"{ki} húzott egy lapot, amit le is rakhat, vagy passzol.")
                self._lep_kov(False)
                return self.allapot_publikus(f"{ki} húzott és passzol.")
            return None

        if self.fazis == "huzas_utan":
            if tipus == "rak":
                kartya = self._huzott
                self.fazis = "jatek"
                self._huzott = None
                if kartya is None or kartya not in self.kezek[ki]:
                    return None
                return self.allapot_publikus(
                    self._lerak(ki, kartya, d.get("szin")))
            if tipus == "passz":
                self.fazis = "jatek"
                self._huzott = None
                self._lep_kov(False)
                return self.allapot_publikus(f"{ki} nem rakja le, passzol.")
            return None

        return None
