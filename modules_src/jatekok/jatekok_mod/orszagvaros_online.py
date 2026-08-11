# -*- coding: utf-8 -*-
"""Ország-Város-Fiú-Lány – host-authoritative ONLINE motor (fejetlen).

A saját szó-játék többjátékos, egy gépről-több gépre változata. A valós idejű
rész (az ábécé HELYI pörgetése minden gépen + az időzítés) a UI-panelé; a
motor a hálózat-független, tesztelhető logikát tartja:

- betu_rogzit(betu): az ELSŐ beérkező „stop" betűje rögzül (a stoppoló saját
  betűje; a host first-come alapon dönt) – SOHA nem a gép/random.
- valasz_be(ki, valaszok): egy játékos kategóriánkénti szavai.
- ertekel(): pontozás. Alappont a szó jóságáért (a helyi játékkal AZONOS
  `_ertekel`: rossz betű/üres = 0, jó betű de nincs a szótárban = 1, szótári
  szó = 2), PLUSZ 2 EGYEDISÉGI bónusz, ha rajtad kívül más NEM írta ugyanazt.

A kategóriák, a szótár és az `_ertekel` a meglévő `jatekok/orszagvaros.py`-ból
jönnek (semmi duplikáció).
"""
from collections import Counter

from .jatekok import orszagvaros as OV


class OrszagVarosHost:
    """Host-oldali Ország-Város állapotgép. Fázisok:
    „varakozas" (kör előtt), „betuzes" (ábécé pörög, betűre vár),
    „iras" (mindenki ír), „eredmeny" (a kör kiértékelve)."""

    def __init__(self, jatekosok, kulcsok=None, custom=None):
        self.jatekosok = [j for j in jatekosok if j] or ["Játékos"]
        self.kulcsok = list(kulcsok or OV.ALAP_KULCSOK)
        self.custom = custom if custom is not None else OV.load_custom()
        self.keszletek = {k: OV.keszlet(k, self.custom) for k in self.kulcsok}
        self.osszpont = {n: 0 for n in self.jatekosok}
        self.kor = 0
        self.fazis = "varakozas"
        self.betu = ""
        self.valaszok = {}
        self.kor_eredmeny = {}

    # ---------------------------------------------------------------- kör
    def kor_indit(self):
        """Új kör: az ábécé pörgetése kezdődhet (a betűre várunk)."""
        self.kor += 1
        self.betu = ""
        self.valaszok = {}
        self.kor_eredmeny = {}
        self.fazis = "betuzes"

    def betu_rogzit(self, betu):
        """Az ELSŐ „stop" betűje rögzül (a többit eldobjuk). True, ha most
        rögzült; False, ha rossz fázis / már van betű / üres."""
        if self.fazis != "betuzes" or self.betu:
            return False
        b = OV.ekezet_nelkul(betu or "")[:1]
        if not b:
            return False
        self.betu = b
        self.fazis = "iras"
        return True

    def valasz_be(self, ki, valaszok):
        """Egy játékos kategóriánkénti szavai (felülírja a korábbit, ha volt)."""
        if self.fazis != "iras" or ki not in self.osszpont:
            return
        v = valaszok or {}
        self.valaszok[ki] = {k: str(v.get(k, "") or "").strip()
                             for k in self.kulcsok}

    def mindenki_beadott(self):
        return all(n in self.valaszok for n in self.jatekosok)

    def ertekel(self):
        """Kiértékelés: alappont (0/1/2) + egyediségi bónusz (+2). Feltölti az
        összpontot, fázis „eredmeny", visszaadja a kör-eredményt."""
        detail = {n: {} for n in self.jatekosok}
        korpont = {n: 0 for n in self.jatekosok}
        for k in self.kulcsok:
            elbiral = {}
            for n in self.jatekosok:
                w = (self.valaszok.get(n, {}) or {}).get(k, "")
                allap, base = OV._ertekel(w, self.betu, self.keszletek[k])
                elbiral[n] = (w, allap, base, OV.ekezet_nelkul(w))
            # egy kategórián belül a NORMALIZÁLT érvényes szavak darabszáma
            szamlalo = Counter(t[3] for t in elbiral.values()
                               if t[2] > 0 and t[3])
            for n in self.jatekosok:
                w, allap, base, norm = elbiral[n]
                pont = base
                egyedi = base > 0 and szamlalo.get(norm, 0) == 1
                if egyedi:
                    pont += 2
                korpont[n] += pont
                detail[n][k] = {"szo": w, "allapot": allap, "pont": pont,
                                "egyedi": egyedi}
        for n in self.jatekosok:
            self.osszpont[n] += korpont[n]
        self.fazis = "eredmeny"
        self.kor_eredmeny = {"betu": self.betu, "korpont": korpont,
                             "detail": detail}
        return self.kor_eredmeny

    # ---------------------------------------------------------------- állapot
    def allapot_publikus(self, uzenet=""):
        return {
            "fazis": self.fazis, "kor": self.kor, "betu": self.betu,
            "kulcsok": list(self.kulcsok),
            "kategoria_nevek": {k: OV.KATEGORIA_NEVEK.get(k, k)
                                for k in self.kulcsok},
            "jatekosok": list(self.jatekosok),
            "osszpont": dict(self.osszpont),
            "beadtak": sorted(self.valaszok.keys()),
            "eredmeny": self.kor_eredmeny, "uzenet": uzenet,
        }
