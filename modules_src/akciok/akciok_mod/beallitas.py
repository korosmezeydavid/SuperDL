# -*- coding: utf-8 -*-
"""Az Akciós újság saját beállításai a gépen: a saját boltok és a kedvencek.

Petrus József (2026-09-28):
- „lehetne egy jelölőnégyzetes kiválasztás, hogy melyik boltokban keressen
  … ha nekem a Spar, Lidl, Aldi van a településemen" → SAJÁT BOLTJAIM.
- „egy kedvencek lista, amibe beírva, hogy Mizse ásványvíz, Félix
  macskaeledel… mindig az aktuális listákból kikeresné és jelezné, hogy
  helló, most akciós" → KEDVENCEK.
"""
import json
from pathlib import Path

from .termek import illik

FAJL = Path.home() / ".superdl" / "akciok_beallitas.json"


def betolt() -> dict:
    try:
        d = json.loads(FAJL.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            d.setdefault("boltjaim", [])
            d.setdefault("kedvencek", [])
            return d
    except (OSError, ValueError):
        pass
    return {"boltjaim": [], "kedvencek": []}


def ment(adat: dict) -> None:
    FAJL.parent.mkdir(parents=True, exist_ok=True)
    tmp = FAJL.with_suffix(".tmp")
    tmp.write_text(json.dumps(adat, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    tmp.replace(FAJL)


def kedvenc_hozzaad(adat: dict, szo: str) -> bool:
    """Igaz, ha új. Ugyanaz a kedvenc kétszer nem kerül fel."""
    szo = " ".join((szo or "").split())
    if not szo:
        return False
    if any(k.lower() == szo.lower() for k in adat["kedvencek"]):
        return False
    adat["kedvencek"].append(szo)
    return True


def kedvenc_torol(adat: dict, szo: str) -> bool:
    for i, k in enumerate(adat["kedvencek"]):
        if k.lower() == (szo or "").lower():
            del adat["kedvencek"][i]
            return True
    return False


def kedvenc_talalatok(kedvencek: list, termekek: list) -> list:
    """[(kedvenc, [Termek, …])] – minden kedvenchez az akciós termékei, ár
    szerint, a legolcsóbb elöl. A kedvenc nélkül találat is benne van
    (üres listával), hogy a párbeszédben látszódjon, mi nem akciós."""
    ki = []
    for k in kedvencek:
        talalt = [t for t in termekek if illik(t, k)]
        talalt.sort(key=lambda t: (t.legjobb_ar() is None, t.legjobb_ar() or 0))
        ki.append((k, talalt))
    return ki


def kedvenc_osszefoglalo(talalatok: list, max_bolt: int = 3) -> str:
    """„Kedvenceid közül most akciós: Mizse ásványvíz (Lidl 129 forint, Spar
    149 forint), Félix macskaeledel (Penny 899 forint)." – üres, ha semmi."""
    reszek = []
    for k, lista in talalatok:
        if not lista:
            continue
        boltok, latott = [], set()
        for t in lista:
            if t.bolt in latott:
                continue
            latott.add(t.bolt)
            ar = t.legjobb_ar()
            boltok.append("%s %d forint" % (t.bolt, ar) if ar is not None
                          else t.bolt)
            if len(boltok) >= max_bolt:
                break
        reszek.append("%s (%s)" % (k, ", ".join(boltok)))
    if not reszek:
        return ""
    return "Kedvenceid közül most akciós: %s." % ", ".join(reszek)
