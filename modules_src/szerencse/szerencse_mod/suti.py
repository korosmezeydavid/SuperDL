# -*- coding: utf-8 -*-
"""Szerencsesüti – a logika, wx nélkül (tesztelhető).

Dávid ötlete (2026-09-27): napközben 15 percenként érkezik egy süti, amit
Ctrl+Alt+S-sel lehet kibontani. Benne bölcsesség, vicc, beszólás – vagy
büntetés (1, 2, 10, 24 óra sütiszünet), vagy bónusz (még egy süti).
Legfeljebb 3 süti gyűlhet össze; éjszakai csend alatt nem jön süti.
"""
import datetime as _dt
import random
import re
from dataclasses import dataclass
from pathlib import Path

PERIODUS_MP = 15 * 60
MAX_VARO = 3

# a fajták és a súlyuk (összesen 100)
SULYOK = {"bolcsesseg": 30, "vicc": 29, "beszolas": 26,
          "buntetes": 8, "bonusz": 7}
# a büntetés hossza órában és a súlya a büntetésen belül
BUNTETES_SULY = {1: 50, 2: 28, 10: 16, 24: 6}
# alapértelmezett reakcióhang fajtánként (a sor végén |hang felülírja)
ALAP_HANG = {"bolcsesseg": ["", "kuncogas"],
             "vicc": ["nagy_nevetes", "kuncogas"],
             "beszolas": ["punch", "huncut"], "buntetes": ["buntetes"],
             "bonusz": ["bonusz"]}
HANGOK = ("nyitas", "erkezes", "nagy_nevetes", "kuncogas", "huncut", "punch",
          "bonusz", "buntetes")


@dataclass
class Uzenet:
    fajta: str
    szoveg: str
    hang: str = ""
    orak: int = 0            # büntetésnél: hány óra szünet


def uzenetek_betolt(szoveg: str) -> dict:
    """Az uzenetek.txt: [fajta] fejlécek alatt soronként egy üzenet; a
    [buntetes] alatt a sor elején „1:", „2:", „10:", „24:" áll (hány óra);
    a sor végén „|hang" felülírhatja a reakcióhangot. Üres sor és #-tel
    kezdődő sor: megjegyzés."""
    ki = {k: [] for k in SULYOK}
    fajta = None
    for sor in (szoveg or "").splitlines():
        s = sor.strip()
        if not s or s.startswith("#") or s.startswith("@"):
            continue
        m = re.match(r"^\[(\w+)\]$", s)
        if m:
            fajta = m.group(1) if m.group(1) in ki else None
            continue
        if not fajta:
            continue
        hang = ""
        if "|" in s:
            s, hang = (x.strip() for x in s.rsplit("|", 1))
            if hang not in HANGOK:
                hang = ""
        orak = 0
        if fajta == "buntetes":
            m = re.match(r"^(\d+)\s*:\s*(.+)$", s)
            if not m or int(m.group(1)) not in BUNTETES_SULY:
                continue
            orak, s = int(m.group(1)), m.group(2)
        ki[fajta].append(Uzenet(fajta, s, hang, orak))
    return ki


def ido_perc(s: str):
    """„22:30" → 1350 (percben); hibás alak: None."""
    m = re.match(r"^\s*(\d{1,2})(?::(\d{2}))?\s*$", s or "")
    if not m:
        return None
    h, p = int(m.group(1)), int(m.group(2) or 0)
    if h > 23 or p > 59:
        return None
    return h * 60 + p


def csendben(most: _dt.datetime, tol: str, ig: str) -> bool:
    """Az éjszakai csend (átnyúlhat éjfélen: 22:00–08:00)."""
    a, b = ido_perc(tol), ido_perc(ig)
    if a is None or b is None or a == b:
        return False
    p = most.hour * 60 + most.minute
    return a <= p < b if a < b else (p >= a or p < b)


def orak_szoveg(orak: int) -> str:
    return {1: "egy órára", 2: "két órára", 10: "tíz órára",
            24: "egy teljes napra"}.get(orak, "%d órára" % orak)


def perc_szoveg(mp: float) -> str:
    perc = max(1, int(round(mp / 60.0)))
    if perc >= 90:
        ora, maradek = divmod(perc, 60)
        return "%d óra %d perc" % (ora, maradek) if maradek else "%d óra" % ora
    return "%d perc" % perc


@dataclass
class Allapot:
    varo: int = 0                    # hány süti vár kibontásra
    kovetkezo: float = 0.0           # mikor jön a következő (epoch)
    buntetes_ig: float = 0.0         # eddig nincs süti (epoch)
    bekapcsolva: bool = True
    csend_tol: str = "22:00"
    csend_ig: str = "08:00"
    erkezes_szoval: bool = True      # az érkezést a felolvasó is mondja
    bontva: int = 0                  # statisztika: eddig kibontott sütik
    csomagok: bool = True            # ünnepi süticsomagok a netről
    latott_csomag: str = ""          # melyik csomagot jelentettük már be

    def szotar(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def szotarbol(cls, d: dict) -> "Allapot":
        a = cls()
        for k, v in (d or {}).items():
            if hasattr(a, k):
                setattr(a, k, v)
        return a


VARAKOZO = [
    "Türelem, a süti még a sütőben van. Még %s.",
    "Még nem sült ki! Nagyjából %s múlva kopogtat.",
    "Üres a doboz. A következő süti %s múlva érkezik.",
    "Hé, ne kaparászd a dobozt! %s, és jön a következő.",
    "A pék most tette be a sütőbe. %s múlva szólok.",
]


class Suti:
    """Az állapotgép. Az időt kívülről kapja (tesztelhető)."""

    def __init__(self, allapot: Allapot, uzenetek: dict, rnd=None):
        self.a = allapot
        self.u = uzenetek
        self.rnd = rnd or random.Random()
        self._utolso = []            # az utolsó pár üzenet (ne ismétlődjön)
        self.csomagok = []           # a netről jött süticsomagok (Csomag)
        self.ma = None               # teszthez: a „mai" nap felülírása

    def csend(self, most_dt: _dt.datetime) -> bool:
        return csendben(most_dt, self.a.csend_tol, self.a.csend_ig)

    def lepes(self, most: float, most_dt: _dt.datetime) -> int:
        """Óraütés (percenként hívjuk). Visszaadja, hány ÚJ süti érkezett."""
        if not self.a.bekapcsolva:
            return 0
        if self.a.kovetkezo <= 0:
            self.a.kovetkezo = most + PERIODUS_MP
            return 0
        if most < self.a.kovetkezo:
            return 0
        # lejárt: ennyi periódus telt el (a program közben zárva is lehetett)
        eltelt = int((most - self.a.kovetkezo) // PERIODUS_MP) + 1
        self.a.kovetkezo += eltelt * PERIODUS_MP
        if most < self.a.buntetes_ig or self.csend(most_dt):
            return 0
        elotte = self.a.varo
        self.a.varo = min(MAX_VARO, self.a.varo + eltelt)
        return self.a.varo - elotte

    def aktiv_csomag(self):
        # Dávid döntése: a csomagot ő kapcsolja be, a felhasználó nem
        # választhat – ha van csomag, az megy.
        return aktiv_csomag(self.csomagok, self.ma or _dt.date.today())

    def csomag_hir(self) -> str:
        """Egy új csomag bejelentése – csomagonként egyszer."""
        c = self.aktiv_csomag()
        if c is None:
            return ""
        kulcs = "%s-%d" % (c.azon, (self.ma or _dt.date.today()).year)
        if kulcs == self.a.latott_csomag:
            return ""
        self.a.latott_csomag = kulcs
        return c.udvozles or ("Megérkezett a %s!" % c.nev)

    def _huz(self, fajta: str) -> Uzenet:
        lista = self.u.get(fajta) or []
        c = self.aktiv_csomag()
        if c is not None and c.uzenetek.get(fajta):
            if c.csere or self.rnd.random() * 100 < c.arany:
                lista = c.uzenetek[fajta]
        if fajta == "buntetes" and lista:
            orak = self.rnd.choices(list(BUNTETES_SULY),
                                    weights=list(BUNTETES_SULY.values()))[0]
            lista = [x for x in lista if x.orak == orak] or lista
        jo = [x for x in lista if x.szoveg not in self._utolso] or lista
        if not jo:
            return Uzenet("bolcsesseg", "Ma a süti üres volt. Ez is egy üzenet.")
        v = self.rnd.choice(jo)
        self._utolso = (self._utolso + [v.szoveg])[-40:]
        return v

    def varakozo_szoveg(self, most: float) -> str:
        if most < self.a.buntetes_ig:
            return ("Büntetésben vagy! Még %s, amíg újra süti jár."
                    % perc_szoveg(self.a.buntetes_ig - most))
        if not self.a.bekapcsolva:
            return ("A szerencsesüti ki van kapcsolva. A beállításokban "
                    "visszakapcsolhatod.")
        hatra = (max(0.0, self.a.kovetkezo - most) if self.a.kovetkezo
                 else PERIODUS_MP)
        return self.rnd.choice(VARAKOZO) % perc_szoveg(hatra)

    def kibont(self, most: float):
        """Egy süti kibontása: Uzenet, vagy None, ha nincs süti."""
        if self.a.varo <= 0:
            return None
        self.a.varo -= 1
        self.a.bontva += 1
        sulyok = SULYOK
        c = self.aktiv_csomag()
        if c is not None and c.csere:
            # csere-csomag: csak a csomagban szereplő fajták jöhetnek
            sulyok = {k: v for k, v in SULYOK.items()
                      if c.uzenetek.get(k)} or SULYOK
        fajta = self.rnd.choices(list(sulyok), weights=list(sulyok.values()))[0]
        u = self._huz(fajta)
        if u.fajta == "buntetes":
            self.a.buntetes_ig = most + u.orak * 3600
            self.a.varo = 0
        elif u.fajta == "bonusz":
            self.a.varo = min(MAX_VARO + 1, self.a.varo + 1)
        return u

    def reakcio_hang(self, u: Uzenet) -> str:
        if u.hang:
            return u.hang
        return self.rnd.choice(ALAP_HANG.get(u.fajta, [""]))

    def teljes_szoveg(self, u: Uzenet) -> str:
        if u.fajta == "buntetes":
            return "%s Büntetés: %s nincs süti." % (u.szoveg,
                                                   orak_szoveg(u.orak))
        if u.fajta == "bonusz":
            return "%s Még egy süti vár: Ctrl+Alt+S." % u.szoveg
        return u.szoveg


def hangfajl(mappa, nev: str, rnd=None):
    """A hangok/<nev>/ mappából egy véletlen .wav, vagy None."""
    d = Path(mappa) / nev
    try:
        f = sorted(p for p in d.iterdir() if p.suffix.lower() == ".wav")
    except OSError:
        return None
    return (rnd or random).choice(f) if f else None


def wav_hossz(ut) -> float:
    """A WAV hossza másodpercben (0, ha nem olvasható)."""
    try:
        import wave
        with wave.open(str(ut), "rb") as w:
            return w.getnframes() / float(w.getframerate() or 1)
    except Exception:
        return 0.0


# --- Süticsomagok a netről (Dávid ötlete, 2026-09-27) ----------------------
# A csomagok.txt a SuperDL tárolójában van; Dávid szabadon cserélgeti
# (karácsonyi, adventi, húsvéti…). Egy fájlban több csomag lehet, mindegyik
# „@nev:" sorral kezdődik; a mai napon érvényes ELSŐ csomag a nyerő.
#   @nev: karácsonyi süticsomag
#   @tol: 12-24          (hónap-nap: minden évben; vagy 2027-03-26)
#   @ig: 12-26
#   @mod: hozzaad        (a saját sütik közé keveredik) vagy csere
#   @arany: 60           (hozzaadnál: ennyi százalék jön a csomagból)
#   @udvozles: Megjött a karácsonyi süticsomag! Boldog karácsonyt!
# Utána ugyanúgy [fajta] fejlécek és üzenetek, mint az uzenetek.txt-ben.
CSOMAG_URL = ("https://raw.githubusercontent.com/korosmezeydavid/SuperDL/"
              "main/szerencse/csomagok.txt")
CSOMAG_MAX_BAJT = 300_000


@dataclass
class Csomag:
    nev: str
    uzenetek: dict
    tol: str = ""
    ig: str = ""
    csere: bool = False
    arany: int = 60
    udvozles: str = ""
    azon: str = ""


def _datum(s: str, ev: int):
    """„12-24" (minden évben) vagy „2027-03-26" → date; hibás: None."""
    s = (s or "").strip()
    try:
        if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", s):
            y, m, d = (int(x) for x in s.split("-"))
            return _dt.date(y, m, d)
        if re.match(r"^\d{1,2}-\d{1,2}$", s):
            m, d = (int(x) for x in s.split("-"))
            return _dt.date(ev, m, d)
    except ValueError:
        return None
    return None


def csomag_ervenyes(c: Csomag, ma: _dt.date) -> bool:
    if not c.tol and not c.ig:
        return True
    tol = _datum(c.tol, ma.year) if c.tol else _dt.date.min
    ig = _datum(c.ig, ma.year) if c.ig else _dt.date.max
    if tol is None or ig is None:
        return False
    evente = len(c.tol.strip()) <= 5 and len(c.ig.strip()) <= 5 \
        and c.tol and c.ig
    if evente and tol > ig:              # átnyúlik az évfordulón (12-31 → 01-01)
        return ma >= tol or ma <= ig
    return tol <= ma <= ig


def csomagok_betolt(szoveg: str) -> list:
    """A csomagok.txt → Csomag-lista. Az első „@nev:" előtti rész csak
    leírás. Üres (üzenet nélküli) csomag nem kerül be."""
    import hashlib
    blokkok, akt = [], None
    for sor in (szoveg or "").splitlines():
        s = sor.strip()
        if s.lower().startswith("@nev:"):
            akt = [sor]
            blokkok.append(akt)
        elif akt is not None:
            akt.append(sor)
    ki = []
    for b in blokkok:
        beall = {}
        for sor in b:
            m = re.match(r"^\s*@(\w+)\s*:\s*(.*)$", sor)
            if m:
                beall[m.group(1).lower()] = m.group(2).strip()
        u = uzenetek_betolt("\n".join(b))
        if not any(u.values()):
            continue
        try:
            arany = max(0, min(100, int(beall.get("arany", "60"))))
        except ValueError:
            arany = 60
        nyers = "|".join((beall.get("nev", ""), beall.get("tol", ""),
                          beall.get("ig", ""))).encode("utf-8")
        ki.append(Csomag(
            nev=beall.get("nev", "süticsomag") or "süticsomag",
            uzenetek=u, tol=beall.get("tol", ""), ig=beall.get("ig", ""),
            csere=beall.get("mod", "").lower().startswith("csere"),
            arany=arany, udvozles=beall.get("udvozles", ""),
            azon=hashlib.sha1(nyers).hexdigest()[:12]))
    return ki


def aktiv_csomag(csomagok, ma: _dt.date):
    for c in csomagok or []:
        if csomag_ervenyes(c, ma):
            return c
    return None
