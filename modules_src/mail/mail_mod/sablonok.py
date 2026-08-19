# -*- coding: utf-8 -*-
"""Super Mail – SABLONOK és OKOS MAPPÁK.

SABLONOK: kész válaszok, kitölthető helyekkel. Aki sokat levelez ugyanazzal a
szöveggel (ügyintézés, egyesületi levelezés), annak ez naponta perceket spórol.

    Kedves {nev}!  →  a program megkérdezi, mi kerüljön a {nev} helyére.

Beépített helyettesítők (ezeket nem kérdezi meg, magától tudja):
    {datum}  {ido}  {ev}  {sajat_cim}  {cimzett}

OKOS MAPPÁK: mentett szűrők a BETÖLTÖTT levelekre („Fontos, ma”, „Számlák”,
„Amire nem válaszoltam”). Nem valódi IMAP-mappák: nézetek. Ugyanazokat a
feltételeket használják, mint a szabályok – egy fogalmat kell csak megtanulni.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field

from . import szabalyok as SZ

SABLON_FAJL = "sablonok.json"
NEZET_FAJL = "okos_mappak.json"

BEEPITETT = ("datum", "ido", "ev", "sajat_cim", "cimzett")
_HELY = re.compile(r"\{([a-zA-Z_öüóőúéáűíÖÜÓŐÚÉÁŰÍ][\w öüóőúéáűíÖÜÓŐÚÉÁŰÍ-]*)\}")


def alap_mappa() -> str:
    from superdl import store
    return str(store.CONFIG_DIR)


# ====================================================================
#  Sablonok
# ====================================================================

@dataclass
class Sablon:
    nev: str = ""
    targy: str = ""
    torzs: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


def helyettesitok(szoveg: str) -> list:
    """A sablonban szereplő KITÖLTENDŐ helyek (a beépítettek nélkül)."""
    ki = []
    for nev in _HELY.findall(szoveg or ""):
        n = nev.strip()
        if n.lower() not in BEEPITETT and n not in ki:
            ki.append(n)
    return ki


def kitolt(szoveg: str, ertekek: dict = None, sajat_cim: str = "",
           cimzett: str = "", most: float = 0.0) -> str:
    """A sablon kitöltése. Az ismeretlen helyeket ÉRINTETLENÜL hagyjuk – így
    látszik, ha valamit elfelejtettünk megadni (a néma üresség rosszabb)."""
    most = most or time.time()
    beepitett = {
        "datum": time.strftime("%Y. %m. %d.", time.localtime(most)),
        "ido": time.strftime("%H:%M", time.localtime(most)),
        "ev": time.strftime("%Y", time.localtime(most)),
        "sajat_cim": sajat_cim or "",
        "cimzett": cimzett or "",
    }
    ertekek = dict(ertekek or {})

    def csere(m):
        nev = m.group(1).strip()
        if nev.lower() in beepitett:
            return beepitett[nev.lower()]
        if nev in ertekek:
            return str(ertekek[nev])
        return m.group(0)
    return _HELY.sub(csere, szoveg or "")


def sablonok_betolt(mappa: str = "") -> list:
    ut = os.path.join(mappa or alap_mappa(), SABLON_FAJL)
    try:
        with open(ut, encoding="utf-8") as f:
            return [Sablon(**{k: v for k, v in d.items()
                              if k in Sablon.__dataclass_fields__})
                    for d in json.load(f).get("sablonok", [])]
    except (OSError, ValueError, TypeError):
        return []


def sablonok_ment(sablonok, mappa: str = "") -> None:
    mappa = mappa or alap_mappa()
    os.makedirs(mappa, exist_ok=True)
    ut = os.path.join(mappa, SABLON_FAJL)
    ideiglenes = ut + ".uj"
    with open(ideiglenes, "w", encoding="utf-8") as f:
        json.dump({"sablonok": [asdict(s) for s in sablonok]}, f,
                  ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(ideiglenes, ut)


# ====================================================================
#  Okos mappák (mentett szűrők)
# ====================================================================

@dataclass
class Nezet:
    nev: str = ""
    feltetelek: list = field(default_factory=list)
    mind: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def leiras(self) -> str:
        if not self.feltetelek:
            return "%s – minden levél" % (self.nev or "Névtelen")
        kotoszo = " és " if self.mind else " vagy "
        return "%s – %s" % (self.nev or "Névtelen",
                            kotoszo.join(f.leiras() for f in self.feltetelek))


def szur(levelek, nezet: Nezet) -> list:
    """A betöltött levelekből azok, amikre a nézet illik."""
    if not nezet or not nezet.feltetelek:
        return list(levelek or [])
    ki = []
    for info in levelek or []:
        talalatok = (SZ.feltetel_illeszkedik(info, f) for f in nezet.feltetelek)
        if (all(talalatok) if nezet.mind else any(talalatok)):
            ki.append(info)
    return ki


def alap_nezetek() -> list:
    """Kezdésnek felkínált okos mappák – a leggyakoribb igényekre."""
    return [
        Nezet(nev="Olvasatlan", feltetelek=[]),          # külön kezeljük
        Nezet(nev="Csatolmányos levelek",
              feltetelek=[SZ.Feltetel(SZ.MEZO_CSATOLMANY, SZ.VISZ_IGAZ)]),
        Nezet(nev="Hírlevelek és reklámok",
              feltetelek=[SZ.Feltetel(SZ.MEZO_MARKETING, SZ.VISZ_IGAZ)]),
        Nezet(nev="Levelezőlisták",
              feltetelek=[SZ.Feltetel(SZ.MEZO_LISTA, SZ.VISZ_IGAZ)]),
        Nezet(nev="Számlák",
              feltetelek=[SZ.Feltetel(SZ.MEZO_TARGY, SZ.VISZ_TARTALMAZZA,
                                      "számla")], mind=False),
        Nezet(nev="Nagy levelek (5 megabájt fölött)",
              feltetelek=[SZ.Feltetel(SZ.MEZO_MERET, SZ.VISZ_NAGYOBB, "5120")]),
    ]


def nezetek_betolt(mappa: str = "") -> list:
    ut = os.path.join(mappa or alap_mappa(), NEZET_FAJL)
    try:
        with open(ut, encoding="utf-8") as f:
            adat = json.load(f)
    except (OSError, ValueError):
        return alap_nezetek()
    ki = []
    for d in adat.get("nezetek", []):
        d = dict(d)
        d["feltetelek"] = [SZ._feltetel_be(x) for x in d.get("feltetelek", [])]
        ki.append(Nezet(**{k: v for k, v in d.items()
                           if k in Nezet.__dataclass_fields__}))
    return ki or alap_nezetek()


def nezetek_ment(nezetek, mappa: str = "") -> None:
    mappa = mappa or alap_mappa()
    os.makedirs(mappa, exist_ok=True)
    ut = os.path.join(mappa, NEZET_FAJL)
    ideiglenes = ut + ".uj"
    with open(ideiglenes, "w", encoding="utf-8") as f:
        json.dump({"nezetek": [asdict(n) for n in nezetek]}, f,
                  ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(ideiglenes, ut)
