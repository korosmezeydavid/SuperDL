# -*- coding: utf-8 -*-
"""Póker (ötlapos húzós) – host-authoritative ONLINE motor (fejetlen).

A közös online-héj legösszetettebb motorja: PRIVÁT kéz (mint az UNO) + TÉTKÖRÖK.
Menet: ante → 1. tétkör → csere (eldobás/húzás) → 2. tétkör → leleplezés.
Akciók a tétkörben: „dob" (bedob/fold), „megad" (passz/check vagy megadás/call),
„emel" (nyit/emel fix egységgel). A kéz-értékelő (`poker_ertek`) a helyi
Pókerrel AZONOS – ide másolva, hogy a motor wx-mentes és önállóan tesztelhető
legyen (mint a Blackjack-motornál).
"""
import random
from collections import Counter

_SZINEK = ["pikk", "kör", "káró", "treff"]
_RANGOK = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "bubi", "dáma",
           "király", "ász"]
_RE = {r: i + 2 for i, r in enumerate(_RANGOK)}     # 2..14 (ász=14)

KEZ_NEV = {8: "SZÍNSOR", 7: "PÓKER (négy egyforma)", 6: "FULL HOUSE",
           5: "SZÍN (flöss)", 4: "SOR", 3: "DRILL (három egyforma)",
           2: "KÉT PÁR", 1: "EGY PÁR", 0: "MAGAS LAP"}


def poker_ertek(kez):
    """Egy 5 lapos kéz értéke: (kategória 0..8, döntetlen-lista). Nagyobb a jobb."""
    ertekek = sorted((_RE[r] for _, r in kez), reverse=True)
    szinek = [s for s, _ in kez]
    c = Counter(ertekek)
    csoportok = sorted(c.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    szamok = [g[1] for g in csoportok]
    rend = [g[0] for g in csoportok]
    floss = len(set(szinek)) == 1
    egyedi = sorted(set(ertekek), reverse=True)
    sor_teto = None
    if len(egyedi) == 5:
        if egyedi[0] - egyedi[4] == 4:
            sor_teto = egyedi[0]
        elif set(egyedi) == {14, 5, 4, 3, 2}:
            sor_teto = 5
    if sor_teto and floss:
        return (8, [sor_teto])
    if szamok == [4, 1]:
        return (7, rend)
    if szamok == [3, 2]:
        return (6, rend)
    if floss:
        return (5, ertekek)
    if sor_teto:
        return (4, [sor_teto])
    if szamok == [3, 1, 1]:
        return (3, rend)
    if szamok == [2, 2, 1]:
        return (2, rend)
    if szamok == [2, 1, 1, 1]:
        return (1, rend)
    return (0, ertekek)


def lap_nev(k):
    return "%s %s" % (k[1], k[0])


def kez_nev(kez):
    return ", ".join(lap_nev(k) for k in kez) if kez else "(nincs lap)"


class PokerHost:
    """Host-oldali ötlapos húzós póker. Fázisok: „tet1", „csere", „tet2",
    „vege". A privát kezet a panel címzetten küldi (mint az UNO-nál)."""

    def __init__(self, jatekosok, kezdo_zseton=200, ante=10, tet_egyseg=20):
        self.jatekosok = [j for j in jatekosok if j] or ["Játékos"]
        self.zseton = {n: int(kezdo_zseton) for n in self.jatekosok}
        self.ante = int(ante)
        self.tet_egyseg = int(tet_egyseg)
        self.kor = 0
        self.fazis = "keszen"
        self.osztas()

    # ------------------------------------------------------------------ osztás
    def _uj_pakli(self):
        p = [(sz, r) for sz in _SZINEK for r in _RANGOK]
        random.shuffle(p)
        return p

    def osztas(self):
        self.pakli = self._uj_pakli()
        self.kor += 1
        self.pot = 0
        self.kezek = {}
        self.statusz = {}          # jatszik / passzolt / kiul
        self.cserelt = set()
        self.gyoztes = []
        self.nyeremeny = 0
        self.leleplezes_kezek = {}
        for n in self.jatekosok:
            if self.zseton[n] >= self.ante:
                self.zseton[n] -= self.ante
                self.pot += self.ante
                self.kezek[n] = [self.pakli.pop() for _ in range(5)]
                self.statusz[n] = "jatszik"
            else:
                self.kezek[n] = []
                self.statusz[n] = "kiul"
        akt = self._aktivak()
        if len(akt) <= 1:
            # nincs kivel játszani → az egyetlen aktív viszi a potot (vagy senki)
            self.fazis = "tet1"
            self._tetkor_indit()
            if len(akt) == 1:
                self._fold_veg(akt[0])
            else:
                self.fazis = "vege"
            return
        self.fazis = "tet1"
        self._tetkor_indit()

    # --------------------------------------------------------------- lekérdezők
    def _aktivak(self):
        return [n for n in self.jatekosok if self.statusz.get(n) == "jatszik"]

    @property
    def soron(self):
        if self.fazis in ("tet1", "tet2", "csere") and self.aktiv_idx is not None:
            return self.jatekosok[self.aktiv_idx]
        return ""

    def kez(self, nev):
        return list(self.kezek.get(nev, []))

    def allapot_publikus(self, uzenet=""):
        return {
            "fazis": self.fazis, "kor": self.kor, "pot": self.pot,
            "soron": self.soron, "tet_szint": getattr(self, "tet_szint", 0),
            "korbe": dict(getattr(self, "korbe", {})),
            "zseton": dict(self.zseton), "statusz": dict(self.statusz),
            "lapszamok": {n: len(self.kezek[n]) for n in self.jatekosok},
            "jatekosok": list(self.jatekosok),
            "gyoztes": list(self.gyoztes), "nyeremeny": self.nyeremeny,
            "leleplezes": {n: [list(k) for k in self.leleplezes_kezek[n]]
                           for n in self.leleplezes_kezek},
            "leleplezes_nev": {n: KEZ_NEV[poker_ertek(self.leleplezes_kezek[n])[0]]
                               for n in self.leleplezes_kezek},
            "uzenet": uzenet,
        }

    # ------------------------------------------------------------------ belső
    def _kov_aktiv_idx(self, tol):
        n = len(self.jatekosok)
        i = tol
        for _ in range(n):
            i = (i + 1) % n
            nev = self.jatekosok[i]
            if self.statusz.get(nev) == "jatszik" and self.zseton[nev] > 0:
                return i
        return tol

    def _elso_aktiv_idx(self):
        for i, nev in enumerate(self.jatekosok):
            if self.statusz.get(nev) == "jatszik":
                return i
        return None

    def _tetkor_indit(self):
        self.tet_szint = 0
        self.korbe = {n: 0 for n in self.jatekosok}
        self.lepett = set()
        self.aktiv_idx = self._elso_aktiv_idx()

    def _tetkor_kesz(self):
        for n in self._aktivak():
            kell_lepnie = self.zseton[n] > 0
            if kell_lepnie and (n not in self.lepett
                                or self.korbe[n] != self.tet_szint):
                return False
        return True

    def _tovabb_vagy_zar(self):
        if self._tetkor_kesz():
            self._tetkor_zar()
        else:
            self.aktiv_idx = self._kov_aktiv_idx(self.aktiv_idx)

    def _tetkor_zar(self):
        if self.fazis == "tet1":
            self.fazis = "csere"
            self.cserelt = set()
            self.aktiv_idx = self._elso_aktiv_idx()
        else:                       # tet2 → leleplezés
            self._leleplezes()

    def _fold_veg(self, gyoztes):
        self.zseton[gyoztes] += self.pot
        self.nyeremeny = self.pot
        self.gyoztes = [gyoztes]
        self.fazis = "vege"
        self.aktiv_idx = None

    def _leleplezes(self):
        akt = self._aktivak()
        self.leleplezes_kezek = {n: list(self.kezek[n]) for n in akt}
        ertekek = {n: poker_ertek(self.kezek[n]) for n in akt}
        legjobb = max(ertekek.values())
        gyoztesek = [n for n in akt if ertekek[n] == legjobb]
        resz = self.pot // len(gyoztesek)
        maradek = self.pot - resz * len(gyoztesek)
        for i, n in enumerate(gyoztesek):
            self.zseton[n] += resz + (maradek if i == 0 else 0)
        self.nyeremeny = resz
        self.gyoztes = gyoztesek
        self.fazis = "vege"
        self.aktiv_idx = None

    # ------------------------------------------------------------------ akció
    def akcio(self, ki, tipus, adat=None):
        d = adat if isinstance(adat, dict) else {}

        if self.fazis in ("tet1", "tet2"):
            if self.aktiv_idx is None or ki != self.jatekosok[self.aktiv_idx]:
                return None
            if self.statusz.get(ki) != "jatszik":
                return None
            if tipus == "dob":
                self.statusz[ki] = "passzolt"
                akt = self._aktivak()
                if len(akt) == 1:
                    self._fold_veg(akt[0])
                    return self.allapot_publikus(
                        f"{ki} bedobta a lapjait. {akt[0]} viszi a potot!")
                self._tovabb_vagy_zar()
                return self.allapot_publikus(f"{ki} bedobta a lapjait.")
            if tipus == "megad":
                diff = self.tet_szint - self.korbe[ki]
                pay = min(diff, self.zseton[ki])
                self.zseton[ki] -= pay
                self.pot += pay
                self.korbe[ki] += pay
                self.lepett.add(ki)
                uz = (f"{ki} passzol." if diff == 0
                      else f"{ki} megadja ({pay}).")
                self._tovabb_vagy_zar()
                return self.allapot_publikus(uz)
            if tipus == "emel":
                diff = self.tet_szint - self.korbe[ki]
                total = diff + self.tet_egyseg
                pay = min(total, self.zseton[ki])
                self.zseton[ki] -= pay
                self.pot += pay
                self.korbe[ki] += pay
                self.tet_szint = max(self.tet_szint, self.korbe[ki])
                self.lepett = {ki}
                self._tovabb_vagy_zar()
                return self.allapot_publikus(
                    f"{ki} {'nyit' if diff == 0 else 'emel'} {self.tet_egyseg}-t "
                    f"(a körben {self.korbe[ki]}).")
            return None

        if self.fazis == "csere":
            if self.aktiv_idx is None or ki != self.jatekosok[self.aktiv_idx]:
                return None
            if self.statusz.get(ki) != "jatszik" or ki in self.cserelt:
                return None
            if tipus != "csere":
                return None
            idxek = sorted({int(i) for i in (d.get("indexek") or [])
                            if isinstance(i, int) and 0 <= int(i) < 5})
            for i in reversed(idxek):
                self.kezek[ki].pop(i)
            for _ in idxek:
                if self.pakli:
                    self.kezek[ki].append(self.pakli.pop())
            self.cserelt.add(ki)
            uz = (f"{ki} {len(idxek)} lapot cserélt."
                  if idxek else f"{ki} nem cserélt.")
            if all(n in self.cserelt for n in self._aktivak()):
                self.fazis = "tet2"
                self._tetkor_indit()
            else:
                self.aktiv_idx = self._kov_aktiv_idx(self.aktiv_idx)
            return self.allapot_publikus(uz)

        return None
