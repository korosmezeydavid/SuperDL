# -*- coding: utf-8 -*-
"""Kő-papír-olló és Répa-nyuszi-pisztoly – a játék MAGJA (wx és hálózat nélkül).

Két változat, ugyanaz a körbeütős szerkezet: az elemek sorrendjében az i-edik
üti az (i-1)-ediket. Kő-papír-olló: a papír becsomagolja a követ, az olló
elvágja a papírt, a kő kicsorbítja az ollót. Répa-nyuszi-pisztoly (Dávid
szabálya): a nyuszi megeszi a répát, a pisztollyal le lehet lőni a nyuszit, a
répával viszont be lehet dugni a pisztoly csövét.

A szövegek és a szabályok a `kpo_szovegek.json`-ban vannak – az Android-SuperDL
UGYANEZT a fájlt használja, így a két program ugyanazt mondja.

ONLINE (Ably, `kpo:` előtagú szoba): KÉT játékos, és senki nem leshet. Minden
körben mindenki előbb csak a választása LENYOMATÁT küldi (SHA-256 a kör
számából, a választásból és egy véletlen sóból), és csak akkor FEDI FEL a
választást, amikor a másik lenyomata már megjött. Ha a felfedett választás nem
egyezik a lenyomattal, a kört nem számoljuk. A protokoll a telefonos
változattal bájtra azonos – a gépes és a telefonos játékos egymás ellen is
játszhat.
"""
import hashlib
import json
import os
import random
import secrets

_SZOVEG_FAJL = os.path.join(os.path.dirname(__file__), "kpo_szovegek.json")
CSATORNA_ELOTAG = "kpo"

_adat_cache = None


def adatok(ut=None) -> dict:
    """A kpo_szovegek.json tartalma (egyszer olvassuk be)."""
    global _adat_cache
    if ut is not None:
        with open(ut, encoding="utf-8") as f:
            return json.load(f)
    if _adat_cache is None:
        with open(_SZOVEG_FAJL, encoding="utf-8") as f:
            _adat_cache = json.load(f)
    return _adat_cache


class Valtozat:
    """Egy szabálykészlet (kpo vagy rnp)."""

    def __init__(self, kulcs: str, d: dict):
        self.kulcs = kulcs
        self.nev = d["nev"]
        self.elemek = list(d["elemek"])
        self.nevek = dict(d["nevek"])
        self.visszaszamlalas = d.get("visszaszamlalas", "")
        self.szabaly = d.get("szabaly", "")
        self.utes = dict(d["utes"])
        self.hang = dict(d.get("hang", {}))
        self.dontetlen = {k: list(v) for k, v in d.get("dontetlen", {}).items()}

    def index(self, kulcs: str) -> int:
        return self.elemek.index(kulcs)

    def nev_of(self, kulcs: str) -> str:
        return self.nevek.get(kulcs, kulcs)

    def kit_ut(self, kulcs: str) -> str:
        """Melyik elemet üti ez az elem."""
        return self.elemek[(self.index(kulcs) - 1) % 3]


def valtozatok() -> dict:
    return {k: Valtozat(k, v) for k, v in adatok()["valtozatok"].items()}


def valtozat(kulcs: str) -> Valtozat:
    return Valtozat(kulcs, adatok()["valtozatok"][kulcs])


def eredmeny(a: int, b: int) -> int:
    """+1, ha az `a` indexű elem üti a `b`-t; -1, ha fordítva; 0 döntetlen."""
    if a == b:
        return 0
    return 1 if (a - b) % 3 == 1 else -1


def kor_leiras(v: Valtozat, te: str, ellen: str, rng=random):
    """Egy kör kiértékelése a TE szemszögedből.
    Visszaad: (eredmény +1/0/-1, a történés mondata, a hang neve)."""
    e = eredmeny(v.index(te), v.index(ellen))
    if e == 0:
        sorok = v.dontetlen.get(te) or ["Döntetlen!"]
        return 0, rng.choice(sorok), "kpo_dontetlen"
    gyoztes, vesztes = (te, ellen) if e > 0 else (ellen, te)
    par = f"{gyoztes}>{vesztes}"
    return e, v.utes.get(par, ""), v.hang.get(par, "")


def beszolas(fajta: str, rng=random, **nevek) -> str:
    """Egy véletlen beszólás a JSON `beszolasok` listájából, a nevekkel kitöltve."""
    sorok = adatok()["beszolasok"].get(fajta) or [""]
    s = rng.choice(sorok)
    try:
        return s.format(**nevek)
    except (KeyError, IndexError):
        return s


# ============================================================ gépi ellenfél

class SzerencsesGep:
    """Teljesen véletlenül választ."""

    def __init__(self, rng=None):
        self.rng = rng or random.Random()

    def megfigyel(self, ellenfel_idx: int):
        pass

    def valaszt(self) -> int:
        return self.rng.randrange(3)


class RavaszGep:
    """Figyeli a szokásaidat: mit szoktál választani, és mit szoktál egy adott
    választás után. Ebből megjósolja a következőt, és (többnyire) azt választja,
    ami üti. Néha szándékosan véletlen – hogy ne legyen kiszámítható."""

    TALALAT_ESELY = 0.75

    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.gyak = [0, 0, 0]
        self.atmenet = [[0, 0, 0] for _ in range(3)]
        self.elozo = None

    def megfigyel(self, ellenfel_idx: int):
        self.gyak[ellenfel_idx] += 1
        if self.elozo is not None:
            self.atmenet[self.elozo][ellenfel_idx] += 1
        self.elozo = ellenfel_idx

    def josol(self):
        """A várható következő választásod indexe, vagy None, ha még nincs elég adat."""
        if self.elozo is not None and sum(self.atmenet[self.elozo]) >= 2:
            sor = self.atmenet[self.elozo]
        elif sum(self.gyak) >= 3:
            sor = self.gyak
        else:
            return None
        mx = max(sor)
        return self.rng.choice([i for i, n in enumerate(sor) if n == mx])

    def valaszt(self) -> int:
        j = self.josol()
        if j is None or self.rng.random() > self.TALALAT_ESELY:
            return self.rng.randrange(3)
        return (j + 1) % 3          # ami üti a jósoltat


def gep(stilus: str, rng=None):
    return RavaszGep(rng) if stilus == "ravasz" else SzerencsesGep(rng)


# ============================================================ meccs

class Meccs:
    """`kor_db` körös meccs: az nyer, aki előbb éri el a többséget
    (1 → 1, 3 → 2, 5 → 3, 7 → 4 nyert kör). A döntetlen kör nem számít."""

    def __init__(self, kor_db: int = 3):
        self.kor_db = max(1, int(kor_db))
        self.cel = self.kor_db // 2 + 1
        self.te = 0
        self.ellen = 0
        self.korok = 0

    def rogzit(self, e: int):
        self.korok += 1
        if e > 0:
            self.te += 1
        elif e < 0:
            self.ellen += 1

    @property
    def vege(self) -> bool:
        return self.te >= self.cel or self.ellen >= self.cel

    @property
    def nyertel(self) -> bool:
        return self.te >= self.cel

    def allas(self, te_nev="Te", ellen_nev="a gép") -> str:
        return f"Állás: {te_nev} {self.te}, {ellen_nev} {self.ellen}."


def meccs_leiras(kor_db: int) -> str:
    kor_db = int(kor_db)
    if kor_db <= 1:
        return "egy kör, egy döntés"
    return f"{kor_db} körös meccs – {kor_db // 2 + 1} nyert körig"


# ============================================================ online protokoll

def hash_tipp(kor: int, kulcs: str, so: str) -> str:
    """A választás lenyomata. A telefon pontosan így számolja (UTF-8, hex, kisbetű)."""
    return hashlib.sha256(f"{int(kor)}:{kulcs}:{so}".encode("utf-8")).hexdigest()


def uj_pid() -> str:
    return secrets.token_hex(5)


class OnlineJatek:
    """Egy online meccs állapota KÉT játékos között, a szállítástól függetlenül.

    `kuldo(tipus, adat)` küld egy üzenetet a szobába (a felület a NetSzobát
    adja). A beérkező üzenetet `fogad(u)` dolgozza fel (u = {tipus, ki, adat}),
    és ESEMÉNYEK listáját adja vissza a felületnek (tuple-ök, első elem a fajta):
      ("belepett", nev) – host: valaki jött;     ("start", ellen_nev, valt, kor_db)
      ("tele",) – a szoba foglalt;               ("ellen_kesz", ellen_nev)
      ("kor", eredm, te_kulcs, ellen_kulcs, mondat, hang) – egy kör vége
      ("meccs_vege", nyertel)                     ("csalas", ellen_nev)
      ("kilepett", nev)                           ("csevej", nev, szoveg)
      ("ujra_ker", nev) – a vendég visszavágót kér (a host automatikusan indítja)
    """

    def __init__(self, nev: str, host: bool, kuldo, pid: str = "",
                 valtozat_kulcs: str = "kpo", kor_db: int = 3, rng=None):
        self.nev = nev or "Játékos"
        self.host = bool(host)
        self.kuldo = kuldo
        self.pid = pid or uj_pid()
        self.valt = valtozat(valtozat_kulcs)
        self.kor_db = int(kor_db)
        self.rng = rng or random.Random()
        self.ellen_pid = ""
        self.ellen_nev = ""
        self.fazis = "lobbi"            # lobbi / jatek / vege
        self.meccs = Meccs(self.kor_db)
        self._uj_kor(1)

    # ---------------------------------------------------------------- kör
    def _uj_kor(self, n: int):
        self.kor = n
        self.sajat = None               # (kulcs, so)
        self.sajat_felfedve = False
        self.ellen_hash = None
        self.ellen_felfed = None        # (kulcs, so)
        self._fuggo = getattr(self, "_fuggo", {})
        if n in self._fuggo:
            self.ellen_hash = self._fuggo.pop(n)

    def _kuld(self, tipus, adat=None):
        d = dict(adat or {})
        d["pid"] = self.pid
        self.kuldo(tipus, d)

    # ---------------------------------------------------------------- lobbi
    def belep(self):
        """A vendég bejelenti magát (a csatlakozás után azonnal)."""
        self._kuld("csatlakozott", {"nev": self.nev})

    def inditas(self, valtozat_kulcs=None, kor_db=None):
        """HOST: meccs indítása (vagy visszavágó) a jelenlegi vendéggel."""
        if not self.host or not self.ellen_pid:
            return False
        if valtozat_kulcs:
            self.valt = valtozat(valtozat_kulcs)
        if kor_db:
            self.kor_db = int(kor_db)
        self._kuld("start", {
            "valtozat": self.valt.kulcs, "kor_db": self.kor_db,
            "host": {"pid": self.pid, "nev": self.nev},
            "vendeg": {"pid": self.ellen_pid, "nev": self.ellen_nev}})
        self._start_helyben()
        return True

    def _start_helyben(self):
        self.fazis = "jatek"
        self.meccs = Meccs(self.kor_db)
        self._fuggo = {}
        self._uj_kor(1)

    def visszavago(self):
        """Visszavágó: a host indítja, a vendég kéri."""
        if self.host:
            return self.inditas()
        self._kuld("ujra_ker", {})
        return True

    def kilep(self):
        try:
            self._kuld("kilep", {})
        except Exception:
            pass

    def csevej(self, szoveg: str):
        szoveg = (szoveg or "").strip()
        if szoveg:
            self._kuld("csevej", {"szoveg": szoveg})

    # ---------------------------------------------------------------- lépés
    def valaszt(self, kulcs: str) -> list:
        """A TE választásod ebben a körben. Visszaad: események (pl. ha a másik
        már választott, és így a kör azonnal lezárul a felfedéssel)."""
        if self.fazis != "jatek" or self.sajat is not None:
            return []
        if kulcs not in self.valt.elemek:
            return []
        so = secrets.token_hex(8)
        self.sajat = (kulcs, so)
        self._kuld("tipp", {"kor": self.kor, "hash": hash_tipp(self.kor, kulcs, so)})
        return self._felfed_ha_lehet()

    def valasztott_mar(self) -> bool:
        return self.sajat is not None

    def _felfed_ha_lehet(self) -> list:
        if self.sajat and self.ellen_hash and not self.sajat_felfedve:
            self.sajat_felfedve = True
            k, so = self.sajat
            self._kuld("felfed", {"kor": self.kor, "valasztas": k, "so": so})
        return self._kor_vege_ha_lehet()

    def _kor_vege_ha_lehet(self) -> list:
        if not (self.sajat_felfedve and self.ellen_felfed):
            return []
        ek, eso = self.ellen_felfed
        if ek not in self.valt.elemek or hash_tipp(self.kor, ek, eso) != self.ellen_hash:
            n = self.kor
            self._uj_kor(n)             # a kört újrajátsszuk
            return [("csalas", self.ellen_nev)]
        te = self.sajat[0]
        e, mondat, hang = kor_leiras(self.valt, te, ek, self.rng)
        self.meccs.rogzit(e)
        ki = [("kor", e, te, ek, mondat, hang)]
        if self.meccs.vege:
            self.fazis = "vege"
            ki.append(("meccs_vege", self.meccs.nyertel))
        else:
            self._uj_kor(self.kor + 1)
        return ki

    # ---------------------------------------------------------------- fogadás
    def fogad(self, u: dict) -> list:
        tipus = u.get("tipus")
        adat = u.get("adat") or {}
        pid = adat.get("pid", "")
        nev = adat.get("nev") or u.get("ki") or "Valaki"
        if not pid or pid == self.pid:
            return []                   # a saját visszhangunk (vagy régi kliens)

        if tipus == "csatlakozott":
            if not self.host:
                return []
            if self.ellen_pid and pid != self.ellen_pid:
                self._kuld("tele", {"cimzett": pid})
                return []
            uj = not self.ellen_pid
            self.ellen_pid, self.ellen_nev = pid, nev
            return [("belepett", nev)] if uj else []

        if tipus == "tele":
            return [("tele",)] if adat.get("cimzett") == self.pid else []

        if tipus == "start":
            if self.host:
                return []
            vendeg = adat.get("vendeg") or {}
            if vendeg.get("pid") != self.pid:
                return [("tele",)] if self.fazis == "lobbi" and not self.ellen_pid else []
            h = adat.get("host") or {}
            self.ellen_pid, self.ellen_nev = h.get("pid", pid), h.get("nev", "Ellenfél")
            try:
                self.valt = valtozat(adat.get("valtozat", "kpo"))
            except KeyError:
                self.valt = valtozat("kpo")
            self.kor_db = int(adat.get("kor_db", 3) or 3)
            self._start_helyben()
            return [("start", self.ellen_nev, self.valt.kulcs, self.kor_db)]

        if tipus == "csevej":           # csevegni a meccs előtt is lehet
            szoveg = (adat.get("szoveg") or "").strip()
            ki_nev = self.ellen_nev if pid == self.ellen_pid else nev
            return [("csevej", ki_nev, szoveg)] if szoveg else []

        if pid != self.ellen_pid:
            return []                   # idegen a szobában – nem vele játszunk

        if tipus == "tipp":
            k = int(adat.get("kor", 0) or 0)
            h = str(adat.get("hash", ""))
            if self.fazis != "jatek" or not h:
                return []
            if k > self.kor:
                self._fuggo[k] = h
                return []
            if k != self.kor or self.ellen_hash:
                return []
            self.ellen_hash = h
            return [("ellen_kesz", self.ellen_nev)] + self._felfed_ha_lehet()

        if tipus == "felfed":
            k = int(adat.get("kor", 0) or 0)
            if self.fazis != "jatek" or k != self.kor or self.ellen_felfed:
                return []
            self.ellen_felfed = (str(adat.get("valasztas", "")), str(adat.get("so", "")))
            return self._kor_vege_ha_lehet()

        if tipus == "ujra_ker":
            if self.host and self.fazis in ("vege", "jatek"):
                self.inditas()
                return [("ujra_ker", self.ellen_nev),
                        ("start", self.ellen_nev, self.valt.kulcs, self.kor_db)]
            return []

        if tipus == "kilep":
            self.fazis = "lobbi"
            ki = self.ellen_nev
            if self.host:
                self.ellen_pid, self.ellen_nev = "", ""
            return [("kilepett", ki)]

        return []
