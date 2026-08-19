# -*- coding: utf-8 -*-
"""Super Mail – SZABÁLYOK: a levelek automatikus rendezése.

Felhasználói kérés (2026-08-19): „szabályok, külön mappákba csoportosítsa pl. a
levelezőlistás, a marketinges blabla e-maileket, szépen beállíthatóan, mindenki
a saját szabályai szerint”.

Ez a fájl SZÁNDÉKOSAN wx-mentes: csak adat és logika, hogy hálózat és ablak
nélkül, gyorsan tesztelhető legyen. A tényleges IMAP-műveleteket (áthelyezés,
másolás, jelölés) a `mailwin` végzi az itt kiszámolt terv alapján.

A TERVEZÉS KÉT SARKALATOS PONTJA
  • Semmi nem történik magától, amit a felhasználó ne kért volna: a szabály
    kiszámolja, MIT tenne (`alkalmaz`), és a végrehajtás külön lépés. Ezért
    lehet „próba” gombot és visszavonást adni hozzá.
  • Minden szabály MONDATKÉNT is megfogalmazható (`leiras`) – a szabálylistát
    vakon így lehet érteni, nem oszlopokból.
"""

from __future__ import annotations

import json
import os
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field

# ---------------------------------------------------------------- mezők

MEZO_FELADO = "felado"
MEZO_CIMZETT = "cimzett"
MEZO_TARGY = "targy"
MEZO_TORZS = "torzs"
MEZO_LISTA = "lista"              # levelezőlista (List-Id fejléc)
MEZO_MARKETING = "marketing"      # tömeges/hírlevél (List-Unsubscribe, Precedence)
MEZO_CSATOLMANY = "csatolmany"
MEZO_MERET = "meret"
MEZO_FEJLEC = "fejlec"            # tetszőleges fejléc (haladóknak)

MEZO_NEVEK = {
    MEZO_FELADO: "a feladó",
    MEZO_CIMZETT: "a címzett",
    MEZO_TARGY: "a tárgy",
    MEZO_TORZS: "a levél szövege",
    MEZO_LISTA: "levelezőlista",
    MEZO_MARKETING: "hírlevél vagy reklám",
    MEZO_CSATOLMANY: "csatolmány",
    MEZO_MERET: "a levél mérete",
    MEZO_FEJLEC: "fejléc",
}

# ---------------------------------------------------------------- viszonyok

VISZ_TARTALMAZZA = "tartalmazza"
VISZ_NEM_TARTALMAZZA = "nem_tartalmazza"
VISZ_PONTOSAN = "pontosan"
VISZ_KEZDODIK = "kezdodik"
VISZ_VEGZODIK = "vegzodik"
VISZ_IGAZ = "igaz"                # a „van csatolmány / hírlevél" típusúakhoz
VISZ_HAMIS = "hamis"
VISZ_NAGYOBB = "nagyobb"          # méret, kilobájtban

VISZONY_NEVEK = {
    VISZ_TARTALMAZZA: "tartalmazza",
    VISZ_NEM_TARTALMAZZA: "nem tartalmazza",
    VISZ_PONTOSAN: "pontosan ez",
    VISZ_KEZDODIK: "ezzel kezdődik",
    VISZ_VEGZODIK: "ezzel végződik",
    VISZ_IGAZ: "van",
    VISZ_HAMIS: "nincs",
    VISZ_NAGYOBB: "nagyobb mint",
}

# ---------------------------------------------------------------- műveletek

MUV_ATHELYEZ = "athelyez"
MUV_MASOL = "masol"
MUV_OLVASOTT = "olvasott"
MUV_TOROL = "torol"
MUV_NINCS_HANG = "nincs_hang"
MUV_FONTOS = "fontos"
MUV_MEGALL = "megall"

MUVELET_NEVEK = {
    MUV_ATHELYEZ: "áthelyezés ide",
    MUV_MASOL: "másolás ide",
    MUV_OLVASOTT: "olvasottnak jelölés",
    MUV_TOROL: "Kukába",
    MUV_NINCS_HANG: "ne szóljon értesítő hang",
    MUV_FONTOS: "megjelölés fontosként",
    MUV_MEGALL: "a további szabályok kihagyása",
}

FAJL = "szabalyok.json"


# ====================================================================
#  Szövegkezelés
# ====================================================================

def _norm(sz) -> str:
    """Kisbetűs, ÉKEZET NÉLKÜLI alak az összehasonlításhoz.

    Miért: a felhasználó „hirlevel"-t gépel be, a tárgyban meg „Hírlevél" van.
    Ha ez nem illeszkedne, a szabály némán nem működne – és a felhasználó azt
    hinné, hogy a program rossz."""
    sz = str(sz or "")
    sz = unicodedata.normalize("NFKD", sz)
    sz = "".join(c for c in sz if not unicodedata.combining(c))
    return sz.casefold().strip()


# ====================================================================
#  Adatszerkezetek
# ====================================================================

@dataclass
class Feltetel:
    mezo: str = MEZO_FELADO
    viszony: str = VISZ_TARTALMAZZA
    ertek: str = ""
    fejlec_nev: str = ""          # csak MEZO_FEJLEC esetén

    def leiras(self) -> str:
        nev = (f"a(z) {self.fejlec_nev} fejléc" if self.mezo == MEZO_FEJLEC
               else MEZO_NEVEK.get(self.mezo, self.mezo))
        v = VISZONY_NEVEK.get(self.viszony, self.viszony)
        if self.viszony in (VISZ_IGAZ, VISZ_HAMIS):
            return f"{nev}: {v}"
        if self.viszony == VISZ_NAGYOBB:
            return f"{nev} {v} {self.ertek} kilobájt"
        return f"{nev} {v}: {self.ertek}"


@dataclass
class Szabaly:
    nev: str = ""
    feltetelek: list = field(default_factory=list)
    muveletek: dict = field(default_factory=dict)
    be: bool = True
    mind: bool = True             # True: MINDEN feltétel; False: BÁRMELYIK
    fiok: str = ""                # üres = minden fiókra
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def leiras(self) -> str:
        """A szabály EGY MONDATBAN – ez jelenik meg a listában, ezt olvassa fel
        a képernyőolvasó."""
        if not self.feltetelek:
            felt = "minden levélre"
        else:
            kotoszo = " és " if self.mind else " vagy "
            felt = "ha " + kotoszo.join(f.leiras() for f in self.feltetelek)
        tettek = []
        for kulcs, ertek in self.muveletek.items():
            nev = MUVELET_NEVEK.get(kulcs, kulcs)
            tettek.append(f"{nev}: {ertek}" if isinstance(ertek, str) and ertek
                          else nev)
        tett = ", ".join(tettek) if tettek else "nem csinál semmit"
        eleje = self.nev + " – " if self.nev else ""
        vege = "" if self.be else "  (kikapcsolva)"
        return f"{eleje}{felt} → {tett}{vege}"


def _feltetel_be(d):
    if isinstance(d, Feltetel):
        return d
    return Feltetel(**{k: v for k, v in (d or {}).items()
                       if k in Feltetel.__dataclass_fields__})


def szabaly_be(d) -> Szabaly:
    """Szótárból szabály (a mentett JSON-ból visszaolvasva)."""
    if isinstance(d, Szabaly):
        return d
    d = dict(d or {})
    d["feltetelek"] = [_feltetel_be(f) for f in d.get("feltetelek", [])]
    return Szabaly(**{k: v for k, v in d.items()
                      if k in Szabaly.__dataclass_fields__})


def szabaly_ki(sz: Szabaly) -> dict:
    return asdict(sz)


# ====================================================================
#  Illeszkedés
# ====================================================================

def _mezo_ertek(info: dict, mezo: str, fejlec_nev: str = ""):
    """A levél adott mezőjének értéke. `info`: a `level_fejlec_info` szótára,
    kiegészítve (lista, marketing, meret, fejlecek, torzs)."""
    if mezo == MEZO_FELADO:
        return info.get("felado", "")
    if mezo == MEZO_CIMZETT:
        return " ".join([str(info.get("cimzett", "")),
                         str(info.get("masolat", ""))])
    if mezo == MEZO_TARGY:
        return info.get("targy", "")
    if mezo == MEZO_TORZS:
        return info.get("torzs", "")
    if mezo == MEZO_LISTA:
        return info.get("lista_id", "")
    if mezo == MEZO_MARKETING:
        return info.get("marketing", False)
    if mezo == MEZO_CSATOLMANY:
        return bool(info.get("csatolmany", False))
    if mezo == MEZO_MERET:
        return int(info.get("meret", 0) or 0)
    if mezo == MEZO_FEJLEC:
        fejlecek = info.get("fejlecek") or {}
        for k, v in fejlecek.items():
            if _norm(k) == _norm(fejlec_nev):
                return v
        return ""
    return ""


def feltetel_illeszkedik(info: dict, f: Feltetel) -> bool:
    ertek = _mezo_ertek(info, f.mezo, f.fejlec_nev)

    # logikai mezők (csatolmány, hírlevél, levelezőlista)
    if f.viszony in (VISZ_IGAZ, VISZ_HAMIS):
        van = bool(ertek)
        return van if f.viszony == VISZ_IGAZ else not van

    if f.viszony == VISZ_NAGYOBB:
        try:
            return int(ertek) > int(float(f.ertek)) * 1024
        except (TypeError, ValueError):
            return False

    minta, szoveg = _norm(f.ertek), _norm(ertek)
    if not minta:
        return False
    if f.viszony == VISZ_TARTALMAZZA:
        return minta in szoveg
    if f.viszony == VISZ_NEM_TARTALMAZZA:
        return minta not in szoveg
    if f.viszony == VISZ_PONTOSAN:
        return minta == szoveg
    if f.viszony == VISZ_KEZDODIK:
        return szoveg.startswith(minta)
    if f.viszony == VISZ_VEGZODIK:
        return szoveg.endswith(minta)
    return False


def illeszkedik(info: dict, sz: Szabaly, fiok_email: str = "") -> bool:
    """Illik-e a levélre a szabály? Feltétel nélküli szabály SOSEM illeszkedik –
    az véletlenül az egész postaládát elmozgatná."""
    if not sz.be or not sz.feltetelek:
        return False
    if sz.fiok and _norm(sz.fiok) != _norm(fiok_email):
        return False
    talalatok = (feltetel_illeszkedik(info, f) for f in sz.feltetelek)
    return all(talalatok) if sz.mind else any(talalatok)


def alkalmaz(levelek, szabalyok, fiok_email: str = ""):
    """Kiszámolja, MIT tennénk – de nem tesz semmit.

    Visszaad: [(level_info, muveletek_dict, szabaly_nevek)] csak azokra a
    levelekre, amikre illeszkedett valami. A `megall` művelet után az adott
    levélre nem nézzük a további szabályokat."""
    terv = []
    for info in levelek or []:
        muveletek, nevek = {}, []
        for sz in szabalyok or []:
            if not illeszkedik(info, sz, fiok_email):
                continue
            nevek.append(sz.nev or sz.leiras())
            for k, v in sz.muveletek.items():
                muveletek.setdefault(k, v)
            if sz.muveletek.get(MUV_MEGALL):
                break
        if muveletek:
            terv.append((info, muveletek, nevek))
    return terv


# ====================================================================
#  Szabály EGY LEVÉLBŐL – a leggyorsabb út (Ctrl+Shift+R)
# ====================================================================

def cim_resz(felado: str) -> str:
    """A „Név <cim@domain.hu>" alakból a puszta címet adja vissza."""
    sz = str(felado or "")
    if "<" in sz and ">" in sz:
        sz = sz[sz.index("<") + 1:sz.index(">")]
    return sz.strip()


def domain_resz(felado: str) -> str:
    cim = cim_resz(felado)
    return cim.split("@")[-1].strip() if "@" in cim else ""


def szabaly_levelbol(info: dict, tipus: str, cel_mappa: str = "") -> Szabaly:
    """Kész szabály a KIJELÖLT levélből. `tipus`:
       'felado'  – minden ettől a feladótól
       'domain'  – minden erről a webhelyről (pl. minden @nav.gov.hu)
       'lista'   – minden erről a levelezőlistáról
       'targy'   – ilyen tárgyú levelek
       'marketing' – minden hírlevél és reklám"""
    muv = {MUV_ATHELYEZ: cel_mappa} if cel_mappa else {}
    if tipus == "felado":
        cim = cim_resz(info.get("felado", ""))
        return Szabaly(nev=f"Levelek tőle: {cim}", muveletek=muv,
                       feltetelek=[Feltetel(MEZO_FELADO, VISZ_TARTALMAZZA, cim)])
    if tipus == "domain":
        dom = domain_resz(info.get("felado", ""))
        # A kukacot IS beleírjuk: enélkül a „bolt.hu" szabály a „masbolt.hu"
        # leveleit is elrakná – idegen levelek tűnnének el a Beérkezettből.
        return Szabaly(nev=f"Levelek innen: {dom}", muveletek=muv,
                       feltetelek=[Feltetel(MEZO_FELADO, VISZ_TARTALMAZZA,
                                            "@" + dom if dom else "")])
    if tipus == "lista":
        lid = info.get("lista_id", "")
        return Szabaly(nev=f"Levelezőlista: {lid}", muveletek=muv,
                       feltetelek=[Feltetel(MEZO_LISTA, VISZ_TARTALMAZZA, lid)])
    if tipus == "targy":
        t = info.get("targy", "")
        return Szabaly(nev=f"Tárgy: {t}", muveletek=muv,
                       feltetelek=[Feltetel(MEZO_TARGY, VISZ_TARTALMAZZA, t)])
    if tipus == "marketing":
        return Szabaly(nev="Hírlevelek és reklámok", muveletek=muv,
                       feltetelek=[Feltetel(MEZO_MARKETING, VISZ_IGAZ)])
    raise ValueError("ismeretlen szabálytípus: %s" % tipus)


def javaslatok(levelek, meglevo=(), kuszob: int = 5):
    """„Ebből 43 leveled van – tegyem ezentúl a Hírlevelek mappába?"

    Megszámolja, melyik levelezőlistából / hírlevél-feladótól van sok levél, és
    azokra javasol szabályt – de csak olyanra, amire MÉG NINCS szabály."""
    listak, hirlevelek = {}, {}
    for info in levelek or []:
        lid = (info.get("lista_id") or "").strip()
        if lid:
            listak[lid] = listak.get(lid, 0) + 1
        elif info.get("marketing"):
            cim = cim_resz(info.get("felado", ""))
            if cim:
                hirlevelek[cim] = hirlevelek.get(cim, 0) + 1

    mar_van = set()
    for sz in meglevo or []:
        for f in sz.feltetelek:
            if f.ertek:
                mar_van.add(_norm(f.ertek))

    ki = []
    for lid, db in listak.items():
        if db >= kuszob and _norm(lid) not in mar_van:
            ki.append(("lista", lid, db))
    for cim, db in hirlevelek.items():
        if db >= kuszob and _norm(cim) not in mar_van:
            ki.append(("hirlevel", cim, db))
    ki.sort(key=lambda t: -t[2])
    return ki


def javaslat_szovege(tipus: str, mi: str, db: int) -> str:
    if tipus == "lista":
        return (f"A(z) {mi} levelezőlistáról {db} leveled van. "
                "Tegyem ezentúl külön mappába?")
    return (f"A(z) {mi} címről {db} hírlevél vagy reklám érkezett. "
            "Tegyem ezentúl külön mappába?")


# ====================================================================
#  Mentés / betöltés
# ====================================================================

def alap_mappa() -> str:
    """A szabályok helye: a többi Super Mail-beállítás mellett."""
    from superdl import store
    return str(store.CONFIG_DIR)


def _utvonal(mappa: str) -> str:
    return os.path.join(mappa, FAJL)


def betolt(mappa: str):
    try:
        with open(_utvonal(mappa), encoding="utf-8") as f:
            adat = json.load(f)
    except (OSError, ValueError):
        return []
    return [szabaly_be(d) for d in adat.get("szabalyok", [])]


def ment(mappa: str, szabalyok) -> None:
    os.makedirs(mappa, exist_ok=True)
    ut = _utvonal(mappa)
    ideiglenes = ut + ".uj"
    adat = {"szabalyok": [szabaly_ki(sz) for sz in szabalyok]}
    with open(ideiglenes, "w", encoding="utf-8") as f:
        json.dump(adat, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(ideiglenes, ut)
