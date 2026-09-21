"""Beszélő óra és időzítő-profilok – a MOTOR (wx nélkül, tesztelhetően).

A felület a Szervezés modulban van; itt csak logika és szálak vannak, hogy
a viselkedés egységtesztelhető legyen (minden időfüggő függvény kap `most`
paramétert).

A HÁROM SZABÁLY, AMI VAKON SZÁMÍT
─────────────────────────────────
1. A periódus az ÓRÁHOZ igazodik, nem az indításhoz. 20 percnél :00, :20,
   :40 – mert aki nem lát, a bemondásból építi fel az órát a fejében.
   Ezért csak a 60 OSZTÓI engedettek.
2. Ami elmúlt, az elmúlt: három óra alvás után NEM mondunk be kilenc
   elmaradt időpontot. Egy bemondás csak a saját idejétől számított
   `TURELEM` másodpercen belül esedékes.
   ⚠️ Az IDŐZÍTŐ ennek a KIVÉTELE: a lejárt időzítőt ébredés után IS
   bemondjuk. Az idő elmúlt, de az esemény nem évül el.
3. Az óra nem vághat bele a beszédbe: minden bemondás az `orahang.Beszelo`
   SORÁBA megy, sosem szakítja félbe az előzőt.
"""

from __future__ import annotations

import datetime as _dt
import logging
import threading
import time

_log = logging.getLogger("superdl.idoora")

TURELEM = 60.0          # ennyi mp-en belül esedékes még egy bemondás
LEPES_LASSU = 20.0      # az ütemező szál normál ébredése (mint az organizer)
LEPES_GYORS = 1.0       # időzítő utolsó két percében
UTOLSO_PERC = (60, 30, 10)      # sűrű figyelmeztetés a végén (másodperc)

PERIODUSOK = (5, 10, 15, 20, 30, 60)     # a 60 osztói – lásd az 1. szabályt

STILUSOK = (
    ("pontos", "Pontos – „húsz óra negyven perc\""),
    ("termeszetes", "Természetes – „este nyolc óra negyven\""),
    ("koznyelvi", "Köznyelvi – „háromnegyed kilenc\""),
)

ALAP = {
    "bemondas": False,
    "periodus_perc": 20,
    "jingle": True,
    "prefix_be": True,
    "prefix_szoveg": "A pontos idő",
    "stilus": "pontos",
    "csend_tol": "22:00",
    "csend_ig": "07:00",
    "ules_emlekezteto_perc": 0,
    "valtozat": "f1",
    "minden_hang": False,
}


# ─────────────────────── magyar számnevek 0–59 ───────────────────────
#
# ⚠️ MIÉRT KELL EZ EGYÁLTALÁN. Prefix nélkül a „11 20" a beszédmotorban
# könnyen „ezeregyszázhúsz" lesz. A számformázás ezért NEM a prefixen múlik:
# az időt MINDIG kimondott alakban adjuk át.

_EGYES = ("nulla", "egy", "kettő", "három", "négy", "öt", "hat", "hét",
          "nyolc", "kilenc")
_TIZ = {10: "tíz", 20: "húsz", 30: "harminc", 40: "negyven", 50: "ötven"}
_TIZEN = {10: "tizen", 20: "huszon", 30: "harminc", 40: "negyven", 50: "ötven"}


def szam(n: int) -> str:
    """Magyar számnév 0–59, ÖNÁLLÓ alakban („kettő")."""
    n = int(n)
    if n < 0 or n > 59:
        return str(n)
    if n < 10:
        return _EGYES[n]
    t, e = (n // 10) * 10, n % 10
    if e == 0:
        return _TIZ[t]
    return _TIZEN[t] + _EGYES[e]


def szam_jelzo(n: int) -> str:
    """Magyar számnév JELZŐI alakban, főnév előtt: „két óra", nem „kettő óra".
    Csak a kettő tér el – de az minden tízesben („huszonkét perc")."""
    s = szam(n)
    if s.endswith("kettő"):
        return s[:-len("kettő")] + "két"
    return s


# ─────────────────────────── időszövegek ────────────────────────────

def _napszak(ora: int) -> str:
    if ora < 4:
        return "éjjel"
    if ora < 10:
        return "reggel"
    if ora < 12:
        return "délelőtt"
    if ora < 18:
        return "délután"
    if ora < 22:
        return "este"
    return "éjjel"


def idoszoveg(t, stilus: str = "pontos") -> str:
    """Az időpont KIMONDOTT alakja. `t` bármi, aminek van .hour/.minute-ja."""
    h, m = int(t.hour), int(t.minute)
    if stilus == "termeszetes":
        if h == 12 and m == 0:
            return "dél"
        if h == 0 and m == 0:
            return "éjfél"
        h12 = h % 12 or 12
        alap = "%s %s óra" % (_napszak(h), szam_jelzo(h12))
        return alap if m == 0 else "%s %s" % (alap, szam(m))
    if stilus == "koznyelvi":
        kov12 = (h + 1) % 24 % 12 or 12
        # ⚠️ A „negyed/fél/háromnegyed" után ÖNÁLLÓ alak jön („fél tizenkettő"),
        # az „óra" előtt viszont JELZŐI („tizenkét óra"). Ez a kettő nem
        # cserélhető fel – élő teszt bukott rajta.
        if m == 0:
            return "pontosan %s óra" % szam_jelzo(h % 12 or 12)
        if m == 15:
            return "negyed %s" % szam(kov12)
        if m == 30:
            return "fél %s" % szam(kov12)
        if m == 45:
            return "háromnegyed %s" % szam(kov12)
        if m < 30:
            return "%s óra múlt %s perccel" % (
                szam_jelzo(h % 12 or 12), szam_jelzo(m))
        return "%s perc múlva %s óra" % (szam_jelzo(60 - m),
                                         szam_jelzo(kov12))
    # "pontos" – és minden ismeretlen stílus
    if m == 0:
        return "%s óra" % szam_jelzo(h)
    return "%s óra %s perc" % (szam_jelzo(h), szam_jelzo(m))


def bemondas_szoveg(t, beall: dict) -> str:
    """A teljes bemondás szövege: [prefix] + idő. A jingle NEM itt van –
    az hang, nem szöveg (lásd `orahang.Beszelo._jingle`)."""
    ido = idoszoveg(t, beall.get("stilus", "pontos"))
    if beall.get("prefix_be", True):
        p = (beall.get("prefix_szoveg") or "").strip()
        if p:
            return "%s %s." % (p, ido)
    return ido + "."


def hatralevo_szoveg(masodperc: float) -> str:
    """„hét perc", „harminc másodperc", „egy óra tíz perc" – KIMONDVA."""
    s = max(0, int(round(masodperc)))
    if s < 60:
        return "%s másodperc" % szam_jelzo(s)
    perc, mp = divmod(s, 60)
    if perc < 60:
        alap = "%s perc" % szam_jelzo(perc)
        return alap if mp == 0 else "%s %s másodperc" % (alap, szam_jelzo(mp))
    ora, perc = divmod(perc, 60)
    alap = "%s óra" % szam_jelzo(ora)
    return alap if perc == 0 else "%s %s perc" % (alap, szam_jelzo(perc))


# ───────────────────── ütemezés (1. és 2. szabály) ──────────────────

def periodus_ok(perc: int) -> bool:
    """Csak a 60 OSZTÓI engedettek – különben a bemondások elcsúsznának a
    kerek pontokról, és pont az veszne el, amiért az egész készül."""
    try:
        perc = int(perc)
    except (TypeError, ValueError):
        return False
    return 1 <= perc <= 60 and 60 % perc == 0


def elozo_bemondas(most, periodus_perc: int):
    """Az UTOLSÓ esedékes bemondási időpont (<= most), az órához igazítva."""
    if not periodus_ok(periodus_perc):
        periodus_perc = ALAP["periodus_perc"]
    ora = most.replace(minute=0, second=0, microsecond=0)
    return ora + _dt.timedelta(
        minutes=periodus_perc * (most.minute // periodus_perc))


def kovetkezo_bemondas(most, periodus_perc: int):
    """A KÖVETKEZŐ bemondás időpontja (> most), az órához igazítva.
    20 percnél mindig :00, :20, :40 – bármikor indult a program."""
    if not periodus_ok(periodus_perc):
        periodus_perc = ALAP["periodus_perc"]
    return elozo_bemondas(most, periodus_perc) + _dt.timedelta(
        minutes=periodus_perc)


def _ora_perc(szoveg: str, alap: tuple[int, int]) -> tuple[int, int]:
    try:
        h, m = str(szoveg).split(":")
        h, m = int(h), int(m)
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    except (ValueError, AttributeError):
        pass
    return alap


def ido_ertheto(szoveg: str) -> bool:
    """Értelmezhető-e „óra:perc" alakként? A felület ezzel ellenőrzi a
    csendes sáv mezőit, MENTÉS ELŐTT – egy elgépelt sáv csendben rossz
    időben némítana."""
    return _ora_perc(szoveg, None) is not None


def csendben(most, tol: str, ig: str) -> bool:
    """Csendes sávban vagyunk-e? ⚠️ A sáv ÁTNYÚLHAT ÉJFÉLEN (22:00–07:00) –
    ez a klasszikus elrontás. Ha a két érték egyenlő, nincs csend."""
    h1, m1 = _ora_perc(tol, (22, 0))
    h2, m2 = _ora_perc(ig, (7, 0))
    a, b = h1 * 60 + m1, h2 * 60 + m2
    t = most.hour * 60 + most.minute
    if a == b:
        return False
    if a < b:
        return a <= t < b
    return t >= a or t < b          # éjfélen átnyúló sáv


class Utemezo:
    """A periodikus időbemondás ütemezője. Nem beszél: csak megmondja,
    esedékes-e most egy bemondás (és megjegyzi, mit mondott be utoljára)."""

    def __init__(self, beall: dict | None = None):
        self.beall = dict(ALAP)
        if beall:
            self.beall.update(beall)
        self._utolso = None          # az utoljára bemondott időpont

    def frissit(self, beall: dict) -> None:
        self.beall.update(beall)

    def esedekes(self, most):
        """Bemondandó időpont, vagy None. A 2. szabály itt él: ami több mint
        `TURELEM` másodperce elmúlt, az elmúlt – csendben."""
        if not self.beall.get("bemondas"):
            return None
        if csendben(most, self.beall.get("csend_tol"),
                    self.beall.get("csend_ig")):
            return None
        p = self.beall.get("periodus_perc", ALAP["periodus_perc"])
        pont = elozo_bemondas(most, p)
        if pont == self._utolso:
            return None
        self._utolso = pont
        if (most - pont).total_seconds() > TURELEM:
            return None              # átaludtuk – nem mondjuk be utólag
        return pont

    def szoveg(self, pont) -> str:
        return bemondas_szoveg(pont, self.beall)


# ──────────────────────── időzítő-profilok ──────────────────────────

IDOZITO_ALAP = {
    "nev": "időzítő",
    "hossz_perc": 20,
    "kozbenso_perc": 5,          # 0 = csak a végén szól
    "valtozat": "f2",
    "veg_jingle": True,
    "kimondja_a_nevet": True,
}


def profil_rendben(p: dict) -> tuple[bool, str]:
    """Elmenthető-e a profil? (igen/nem, hibaüzenet)."""
    nev = (p.get("nev") or "").strip()
    if not nev:
        return False, "Adj nevet az időzítőnek."
    try:
        hossz = int(p.get("hossz_perc", 0))
    except (TypeError, ValueError):
        return False, "A hossz csak egész szám perc lehet."
    if not 1 <= hossz <= 24 * 60:
        return False, "A hossz 1 perc és 24 óra között lehet."
    try:
        kozb = int(p.get("kozbenso_perc", 0))
    except (TypeError, ValueError):
        return False, "A figyelmeztetés csak egész szám perc lehet."
    if kozb < 0:
        return False, "A figyelmeztetés nem lehet negatív."
    if kozb and kozb >= hossz:
        return False, ("A köztes figyelmeztetés rövidebb legyen, mint maga "
                       "az időzítő.")
    return True, ""


def _kuszobok(hossz_perc: int, kozbenso_perc: int) -> list[int]:
    """A figyelmeztetések HÁTRALÉVŐ másodpercben, csökkenő sorrendben.
    Az utolsó perc mindig sűrűbb (60, 30, 10 mp) – az 5 percenkénti
    figyelmeztetés ott már kevés."""
    ki = set(UTOLSO_PERC)
    if kozbenso_perc:
        t = kozbenso_perc * 60
        while t < hossz_perc * 60:
            if t > UTOLSO_PERC[0]:
                ki.add(t)
            t += kozbenso_perc * 60
    return sorted(ki, reverse=True)


class FutoIdozito:
    """Egy ÉPPEN FUTÓ időzítő. A monotonic órát használja: a rendszeróra
    átállítása (nyári időszámítás, NTP) nem rövidíti és nem nyújtja meg."""

    _kovetkezo_azon = 1

    def __init__(self, profil: dict, *, most: float | None = None):
        p = dict(IDOZITO_ALAP)
        p.update(profil or {})
        self.profil = p
        self.azon = FutoIdozito._kovetkezo_azon
        FutoIdozito._kovetkezo_azon += 1
        self.indult = time.monotonic() if most is None else most
        self.hossz = int(p["hossz_perc"]) * 60
        self.vege = self.indult + self.hossz
        self._hatra = _kuszobok(int(p["hossz_perc"]),
                                int(p.get("kozbenso_perc") or 0))
        self._kesz = False

    @property
    def nev(self) -> str:
        return self.profil.get("nev") or "időzítő"

    @property
    def valtozat(self) -> str:
        return self.profil.get("valtozat") or ""

    def hatralevo(self, most: float | None = None) -> float:
        most = time.monotonic() if most is None else most
        return max(0.0, self.vege - most)

    def lejart(self, most: float | None = None) -> bool:
        most = time.monotonic() if most is None else most
        return most >= self.vege

    def _elotag(self) -> str:
        if self.profil.get("kimondja_a_nevet", True):
            return self.nev + ": "
        return ""

    def allapot_szoveg(self, most: float | None = None) -> str:
        """„ebédszünet: hét perc van hátra" – a kérdezésre adott válasz."""
        return "%s%s van hátra." % (self._elotag() or (self.nev + ": "),
                                    hatralevo_szoveg(self.hatralevo(most)))

    def esedekes(self, most: float | None = None) -> list[tuple[str, bool]]:
        """Az ekkor esedékes bemondások: [(szöveg, sürgős), …].

        ⚠️ Ha a gép közben ALUDT, a kihagyott KÖZTES figyelmeztetéseket
        csendben elengedjük (azok már nem információk), a LEJÁRATOT viszont
        mindenképp bemondjuk – az esemény nem évül el."""
        most = time.monotonic() if most is None else most
        ki: list[tuple[str, bool]] = []
        hatra = self.vege - most
        while self._hatra and hatra <= self._hatra[0]:
            kuszob = self._hatra.pop(0)
            if hatra <= 0:
                continue             # a lejáratot lent külön mondjuk be
            if kuszob - hatra <= TURELEM:      # nem aludtuk át
                ki.append(("%s%s van hátra." % (
                    self._elotag(), hatralevo_szoveg(kuszob)), False))
        if hatra <= 0 and not self._kesz:
            self._kesz = True
            ki.append(("%sletelt az idő." % self._elotag(), True))
        return ki


# ───────────────────────────── a motor ──────────────────────────────

class OraMotor:
    """A beszélő óra és az időzítők futtatója.

    ⚠️ 4.6.7-ES SZABÁLY: ebből a szálból NEM indul semmi, ami a felhasználó
    felé mutat. A bemondás az `orahang.Beszelo` SAJÁT szálán megy (ott nincs
    wx és nincs COM), a felületnek szóló értesítés pedig az `ertesito`
    visszahíváson át megy, amit a hívó `wx.CallAfter`-rel köt be.
    """

    def __init__(self, beszelo, beall: dict | None = None, *, ertesito=None):
        self.beszelo = beszelo
        self.utemezo = Utemezo(beall)
        self.ertesito = ertesito          # fn(esemeny, adat) – wx.CallAfter!
        self._futok: list[FutoIdozito] = []
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._szal = None
        self._ules_kezdet = time.monotonic()
        self._ules_utolso = 0

    # ---- életciklus -------------------------------------------------

    def indul(self) -> None:
        if self._szal is not None:
            return
        self._stop.clear()
        self._szal = threading.Thread(target=self._fut, daemon=True,
                                      name="superdl-idoora")
        self._szal.start()
        _log.info("beszélő óra elindult")

    def leall(self) -> None:
        self._stop.set()
        sz, self._szal = self._szal, None
        if sz is not None:
            sz.join(timeout=3)
        _log.info("beszélő óra leállt")

    def beallit(self, beall: dict) -> None:
        self.utemezo.frissit(beall)

    # ---- időzítők ---------------------------------------------------

    def idozito_indit(self, profil: dict) -> FutoIdozito:
        f = FutoIdozito(profil)
        with self._lock:
            self._futok.append(f)
        _log.info("időzítő indult: %s (%s perc)", f.nev,
                  f.profil.get("hossz_perc"))
        self._ertesit("idozito_valtozas", None)
        return f

    def idozito_leallit(self, azon: int) -> bool:
        with self._lock:
            elotte = len(self._futok)
            self._futok = [f for f in self._futok if f.azon != azon]
            valt = len(self._futok) != elotte
        if valt:
            self._ertesit("idozito_valtozas", None)
        return valt

    def futok(self) -> list[FutoIdozito]:
        with self._lock:
            return list(self._futok)

    def futo_osszefoglalo(self) -> str:
        """Kilépéshez: „Fut az ebédszünet időzítőd, hét perc van hátra."
        Üres, ha nem fut semmi. ⚠️ Csendben elveszíteni rosszabb a semminél."""
        fs = self.futok()
        if not fs:
            return ""
        most = time.monotonic()
        reszek = ["%s (%s)" % (f.nev, hatralevo_szoveg(f.hatralevo(most)))
                  for f in fs]
        if len(reszek) == 1:
            return "Fut egy időzítőd: %s." % reszek[0]
        # JELZŐI alak: „két időzítőd", nem „kettő időzítőd" (élő teszt fogta).
        return "Fut %s időzítőd: %s." % (szam_jelzo(len(reszek)),
                                         ", ".join(reszek))

    # ---- bemondások -------------------------------------------------

    def mennyi_az_ido(self, *, most=None, reszletes: bool = False) -> str:
        """Az azonnali „mennyi az idő?" bemondása. Ez FELHASZNÁLÓI kérés,
        tehát sürgős: a sor tele állapota se nyelje el."""
        most = most or _dt.datetime.now()
        szov = bemondas_szoveg(most, self.utemezo.beall)
        if reszletes:
            szov += " " + self._datum_szoveg(most)
        self.beszelo.mond(szov, self.utemezo.beall.get("valtozat", ""),
                          jingle=bool(self.utemezo.beall.get("jingle")),
                          surgos=True)
        return szov

    @staticmethod
    def _datum_szoveg(most) -> str:
        honap = ("január", "február", "március", "április", "május", "június",
                 "július", "augusztus", "szeptember", "október", "november",
                 "december")[most.month - 1]
        nap = ("hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat",
               "vasárnap")[most.weekday()]
        szov = "%s %s %s, %s." % (most.year, honap, szam_jelzo(most.day), nap)
        try:
            from . import namedays
            nn = namedays.for_date(most.date())
            if nn:
                szov += " Névnap: %s." % nn
        except Exception:
            pass
        return szov

    def idozitok_allapota(self) -> str:
        fs = self.futok()
        if not fs:
            return "Nem fut időzítő."
        most = time.monotonic()
        return " ".join(f.allapot_szoveg(most) for f in fs)

    # ---- belül ------------------------------------------------------

    def _ertesit(self, esemeny, adat) -> None:
        if self.ertesito is None:
            return
        try:
            self.ertesito(esemeny, adat)
        except Exception:
            _log.exception("értesítés hiba: %s", esemeny)

    def _lepes(self) -> float:
        """A következő ébredésig eltelő idő. Az időzítő utolsó két percében
        sűrűbb, hogy a 60/30/10 másodperces jelzés pontos legyen."""
        most = time.monotonic()
        for f in self.futok():
            if f.hatralevo(most) <= 2 * 60:
                return LEPES_GYORS
        return LEPES_LASSU

    def _fut(self) -> None:
        while not self._stop.is_set():
            try:
                self._egy_kor()
            except Exception:
                _log.exception("az óra-ütemező köre hibára futott")
            self._stop.wait(self._lepes())

    def _egy_kor(self) -> None:
        beall = self.utemezo.beall
        # 1) időzítők – ELŐBB, mert ezek a sürgősek
        kesz = []
        for f in self.futok():
            for szov, surgos in f.esedekes():
                self.beszelo.mond(szov, f.valtozat,
                                  jingle=bool(f.profil.get("veg_jingle"))
                                  and surgos,
                                  surgos=surgos)
            if f.lejart():
                kesz.append(f)
        if kesz:
            with self._lock:
                azonok = {f.azon for f in kesz}
                self._futok = [f for f in self._futok
                               if f.azon not in azonok]
            self._ertesit("idozito_valtozas", None)
        # 2) periodikus időbemondás
        pont = self.utemezo.esedekes(_dt.datetime.now())
        if pont is not None:
            self.beszelo.mond(self.utemezo.szoveg(pont),
                              beall.get("valtozat", ""),
                              jingle=bool(beall.get("jingle")))
        # 3) ülés-emlékeztető (alapból ki)
        self._ules(beall)

    def _ules(self, beall: dict) -> None:
        perc = int(beall.get("ules_emlekezteto_perc") or 0)
        if perc <= 0:
            self._ules_utolso = 0
            return
        eltelt = (time.monotonic() - self._ules_kezdet) / 60.0
        q = int(eltelt // perc)
        if q > self._ules_utolso:
            self._ules_utolso = q
            if not csendben(_dt.datetime.now(), beall.get("csend_tol"),
                            beall.get("csend_ig")):
                self.beszelo.mond(
                    "Már %s perce a gépnél vagy." % szam_jelzo(q * perc),
                    beall.get("valtozat", ""))

    def ules_ujraindit(self) -> None:
        self._ules_kezdet = time.monotonic()
        self._ules_utolso = 0
