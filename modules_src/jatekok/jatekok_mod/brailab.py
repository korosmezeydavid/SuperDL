# -*- coding: utf-8 -*-
"""BraiLab PC beszédszintetizátor a retró játékokhoz.

A hangot **Ujfalusi Zoltán** bocsátotta a rendelkezésünkre – hálás köszönettel.

MIÉRT KÜLÖN FOLYAMAT? A BraiLab `TTS.dll` 32 bites, a SuperDL 64 bites: egy 64
bites folyamat nem tud 32 bites DLL-t betölteni. Ezért a DLL egy pehelysúlyú,
32 bites kísérő-folyamatban (`brailab/brailab_host.exe`) él, és a standard
bemenetén kapja a parancsokat. Ha a host bármiért nem indul, ez a réteg
egyszerűen „nem elérhető”-t jelez, és a játék a megszokott hangon szólal meg –
NÉMA SOSEM lesz.

A motor tartományai szűkek (élőben megmérve):
    magasság  −1 / 0 / +1        (hibakód: −22)
    tempó      0 … 5, alap 4     (hibakód: −21) – a 0 a leglassabb!
    hangerő   −1 / 0 / +1        (hibakód: −23)

A motor nem jelzi, mikor fejezte be a beszédet (nincs ilyen hívása), ezért a
hossz BECSÜLT: tempónként megmért másodperc/karakter érték alapján. Ezt a
játék-konzol arra használja, hogy a mondatok ne csússzanak egymásra.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time

MAPPA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brailab")
HOST = os.path.join(MAPPA, "brailab_host.exe")
FAJLOK = ("brailab_host.exe", "TTS.dll", "BINADATA.BIN", "BINAHANK.BIN")

# FIGYELEM: a Core retró gépei közt MÁR VAN „brailab" kulcs (a saját
# újraalkotásunk), ezért az IGAZI motor kulcsa „brailab_pc".
KULCS = "brailab_pc"
NEV = "BraiLab PC – az IGAZI hang (Ujfalusi Zoltán jóvoltából)"

# tempó -> (alap másodperc, másodperc/karakter). A fejlesztői gépen mérve
# (rendszerhang-visszahallgatás, tempónként két különböző hosszú mondat): egy
# 47 karakteres mondat 4,0–6,6 másodperc volt. SZÁNDÉKOSAN FELÜLRE kerekítünk:
# ha a becslés túl RÖVID, a következő mondat belebeszél az előzőbe (ez vakon
# használhatatlan), ha túl HOSSZÚ, csak egy pillanat csend lesz.
HOSSZ_TABLA = {
    0: (0.45, 0.145),
    1: (0.45, 0.135),
    2: (0.45, 0.130),
    3: (0.45, 0.125),
    4: (0.45, 0.120),
    5: (0.40, 0.105),
}

MAGASSAGOK = (-1, 0, 1)
TEMPOK = (0, 1, 2, 3, 4, 5)
HANGEROK = (-1, 0, 1)

# A TTS_StartSay legfeljebb 511 karaktert fogad el egyszerre; hosszabb
# szövegre „-10” hibakódot ad, és NÉMA marad (élőben megmérve, 2026-10-01:
# a Kő-papír-olló, a Szerencsekerék és az Ország-Város leírása emiatt nem
# szólalt meg F8-ra). A hosszabb szöveget ezért mondathatáron darabolva,
# egymás után mondatjuk el. Kis tartalékkal maradunk a határ alatt.
MAX_KARAKTER = 480


def darabol(szoveg: str, legfeljebb: int = MAX_KARAKTER) -> list:
    """A szöveg feldarabolása legfeljebb `legfeljebb` karakteres részekre:
    elsősorban mondathatáron, ha az sem elég, vesszőnél / szóköznél, végső
    esetben keményen. Üres szövegre üres lista."""
    szoveg = " ".join((szoveg or "").split())
    if not szoveg:
        return []
    darabok = []
    while len(szoveg) > legfeljebb:
        ablak = szoveg[:legfeljebb + 1]
        vag = -1
        for jelek in ((". ", "! ", "? ", "… "), ("; ", ": ", ", ", " – "), (" ",)):
            for j in jelek:
                i = ablak.rfind(j)
                if i > 0:
                    vag = max(vag, i + len(j.rstrip()))
            if vag > 0:
                break
        if vag <= 0:
            vag = legfeljebb
        darabok.append(szoveg[:vag].strip())
        szoveg = szoveg[vag:].strip()
    if szoveg:
        darabok.append(szoveg)
    return [d for d in darabok if d]


def elerheto() -> bool:
    """Megvan-e a teljes BraiLab-készlet a modul mellett?"""
    return all(os.path.isfile(os.path.join(MAPPA, f)) for f in FAJLOK)


def becsult_hossz(szoveg: str, tempo: int = 4) -> float:
    """A kimondás BECSÜLT hossza másodpercben (a motor nem jelez véget)."""
    alap, per_kar = HOSSZ_TABLA.get(int(tempo), HOSSZ_TABLA[4])
    return alap + per_kar * len((szoveg or "").strip())


def hatarol(ertek, lehet, alap):
    """A motor tartományába szorítja az értéket (a szűk fokozatok miatt)."""
    try:
        ertek = int(ertek)
    except (TypeError, ValueError):
        return alap
    if ertek in lehet:
        return ertek
    return min(lehet, key=lambda x: abs(x - ertek))


class BrailabMotor:
    """A 32 bites host életciklusa és a parancsok küldése.

    Szálbiztos: a játék-konzol háttérszála mondat, a felület közben állíthat
    fokozatot. A hostot csak az ELSŐ megszólaláskor indítjuk el."""

    def __init__(self):
        self._p = None
        self._zar = threading.Lock()
        self.magassag = 0
        self.tempo = 4
        self.hangero = 0
        self.hiba = ""
        self._generacio = 0          # minden új mondás / leállítás növeli

    # ---- életciklus ---------------------------------------------------
    def _fut(self) -> bool:
        return self._p is not None and self._p.poll() is None

    def indit(self) -> bool:
        """Elindítja a hostot (ha még nem fut). Visszaad: sikerült-e."""
        with self._zar:
            return self._indit_zarban()

    def _indit_zarban(self) -> bool:
        if self._fut():
            return True
        self._p = None
        if not elerheto():
            self.hiba = "Nincs meg a BraiLab-készlet."
            return False
        try:
            self._p = subprocess.Popen(
                [HOST], cwd=MAPPA,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            valasz = (self._p.stdout.readline() or "").strip()
        except Exception as e:                       # pragma: no cover – gépfüggő
            self.hiba = str(e)
            self._p = None
            return False
        if valasz != "READY":
            self.hiba = valasz or "A BraiLab host nem indult el."
            self._zarj()
            return False
        self.hiba = ""
        # a mentett fokozatokat mindig visszaállítjuk az új hoston
        self._parancs("PITCH %d" % self.magassag)
        self._parancs("TEMPO %d" % self.tempo)
        self._parancs("VOLUME %d" % self.hangero)
        return True

    def _zarj(self):
        p, self._p = self._p, None
        if p is None:
            return
        try:
            if p.poll() is None:
                p.stdin.write("QUIT\n")
                p.stdin.flush()
                p.wait(2)
        except Exception:
            pass
        try:
            if p.poll() is None:
                p.kill()
        except Exception:
            pass

    def leallit(self):
        """Elnémítás + a host lezárása (a játék bezárásakor)."""
        with self._zar:
            self._generacio += 1
            if self._fut():
                self._parancs("STOP")
            self._zarj()

    # ---- parancsok ----------------------------------------------------
    def _parancs(self, sor: str) -> str:
        """Egy sor a hostnak, a válasza vissza. A záron BELÜL kell hívni."""
        if not self._fut():
            return ""
        try:
            self._p.stdin.write(sor + "\n")
            self._p.stdin.flush()
            return (self._p.stdout.readline() or "").strip()
        except Exception:
            self._p = None                # a következő hívás újraindítja
            return ""

    def mond(self, szoveg: str, intonacio: bool = True) -> float:
        """Kimondja a szöveget. `intonacio=False` esetén mondatdallam NÉLKÜL
        (monotonabb, még retróbb). Visszaad: a BECSÜLT hossz másodpercben
        (0.0, ha nem sikerült megszólalni)."""
        # a sor-alapú protokoll miatt az újsorokat szóközre váltjuk; a motor
        # 511 karakternél hosszabbat nem fogad el, ezért darabolunk
        darabok = darabol(szoveg)
        if not darabok:
            return 0.0
        elotag = "SPEAK " if intonacio else "SPEAKFLAT "
        with self._zar:
            self._generacio += 1            # a korábbi, még hátralévő darabok elmaradnak
            gen = self._generacio
            if not self._indit_zarban():
                return 0.0
            parancs = elotag + darabok[0]
            valasz = self._parancs(parancs)
            if valasz != "OK":
                # egyszeri újraindítás: a host közben elszállhatott
                self._zarj()
                if not self._indit_zarban():
                    return 0.0
                valasz = self._parancs(parancs)
                if valasz != "OK":
                    self.hiba = "a motor nem fogadta el a szöveget (%s)" % (
                        valasz or "nincs válasz")
                    return 0.0
            tempo = self.tempo
        hosszak = [becsult_hossz(d, tempo) for d in darabok]
        if len(darabok) > 1:
            threading.Thread(target=self._folytat,
                             args=(gen, elotag, darabok[1:], hosszak[:-1]),
                             daemon=True, name="brailab-folytatas").start()
        return sum(hosszak)

    def _folytat(self, gen, elotag, darabok, varakozasok):
        """A hosszú szöveg további darabjai: mindegyik az előző BECSÜLT végén
        indul. Ha közben új mondat jött vagy leállították, abbahagyja."""
        for darab, var in zip(darabok, varakozasok):
            veg = time.monotonic() + var
            while time.monotonic() < veg:
                if self._generacio != gen:
                    return
                time.sleep(0.05)
            with self._zar:
                if self._generacio != gen:
                    return
                if self._parancs(elotag + darab) != "OK":
                    return

    def stop(self):
        """Az éppen folyó beszéd azonnali megszakítása."""
        with self._zar:
            self._generacio += 1            # a hátralévő darabok se szóljanak
            if self._fut():
                self._parancs("STOP")

    def beallit(self, magassag=None, tempo=None, hangero=None) -> bool:
        """Fokozatok állítása. A tartományon kívüli értéket beszorítjuk (a
        motor különben csak hibakódot adna, és maradna a régi fokozat)."""
        if magassag is not None:
            self.magassag = hatarol(magassag, MAGASSAGOK, 0)
        if tempo is not None:
            self.tempo = hatarol(tempo, TEMPOK, 4)
        if hangero is not None:
            self.hangero = hatarol(hangero, HANGEROK, 0)
        with self._zar:
            if not self._fut():
                return True            # induláskor amúgy is beállítjuk
            jo = True
            for sor in ("PITCH %d" % self.magassag,
                        "TEMPO %d" % self.tempo,
                        "VOLUME %d" % self.hangero):
                if self._parancs(sor) != "OK":
                    jo = False
            return jo

    def fokozatok(self):
        """A motorból VISSZAKÉRDEZETT fokozatok (magasság, tempó, hangerő);
        ha a host nem fut, a mentett értékek."""
        with self._zar:
            if self._fut():
                v = self._parancs("GET")
                if v.startswith("VALUES"):
                    try:
                        p, t, h = (int(x) for x in v.split()[1:4])
                        return p, t, h
                    except (ValueError, IndexError):
                        pass
        return self.magassag, self.tempo, self.hangero


_MOTOR = None
_MOTOR_ZAR = threading.Lock()


def motor() -> BrailabMotor:
    """A folyamat egyetlen BraiLab-motorja (egy host elég mindenre)."""
    global _MOTOR
    with _MOTOR_ZAR:
        if _MOTOR is None:
            _MOTOR = BrailabMotor()
        return _MOTOR
