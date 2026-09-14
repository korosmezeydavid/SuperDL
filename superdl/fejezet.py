# -*- coding: utf-8 -*-
"""Fejezetjelölő: KÖZÖS nyelv a szerkesztő és a hangoskönyv-készítő között.

A hangoskönyv eddig percek szerint darabolt. Van, aki FEJEZETENKÉNT akarja —
de ahhoz meg kell tudni mondani, hol kezdődik egy fejezet. A Super Editben a
felhasználó beszúr egy jelölőt, a hangoskönyv-készítő pedig felismeri.

⚠️ MIÉRT SIMA SZÖVEG A JELÖLŐ. Mert túl kell élnie a .txt-t is. Egy
címsor-formázás Word-ben megvan, szövegfájlban nincs — a jelölőnek viszont
mindkettőben működnie kell, különben pont ott veszne el, ahol a legtöbb
hangoskönyv-alapanyag van.

A jelölő egy SAJÁT SORBAN álló:

    [[FEJEZET]]                 – cím nélkül
    [[FEJEZET: Első fejezet]]   – címmel

A felismerés elnéző: kis- és nagybetű mindegy, a szóközök mindegy, és a
régebbi `=== FEJEZET ===` alak is megy.
"""

import re

JELOLO = "[[FEJEZET]]"

#: `[[FEJEZET]]` vagy `[[FEJEZET: cím]]`, saját sorban
_MINTA = re.compile(r"^\s*\[\[\s*fejezet\s*(?::\s*(?P<cim>[^\]]*?))?\s*\]\]\s*$",
                    re.I)
#: régebbi, kézzel írt alak: `=== FEJEZET ===` vagy `=== Első fejezet ===`
_REGI = re.compile(r"^\s*={2,}\s*(?P<cim>.*?)\s*={2,}\s*$")


def jelolo(cim: str = "") -> str:
    """A beszúrandó jelölő-sor."""
    cim = (cim or "").strip()
    return "[[FEJEZET: %s]]" % cim if cim else JELOLO


def jelolo_e(sor: str) -> bool:
    return bool(_MINTA.match(sor or "") or _REGI.match(sor or ""))


def jelolo_cime(sor: str) -> str:
    """A jelölő-sor címe, vagy üres sztring. Nem jelölőnél is üres."""
    m = _MINTA.match(sor or "")
    if m:
        return (m.group("cim") or "").strip()
    m = _REGI.match(sor or "")
    if m:
        cim = (m.group("cim") or "").strip()
        return "" if cim.lower() == "fejezet" else cim
    return ""


def van_jelolo(szoveg: str) -> bool:
    return any(jelolo_e(s) for s in (szoveg or "").split("\n"))


def szamlal(szoveg: str) -> int:
    return sum(1 for s in (szoveg or "").split("\n") if jelolo_e(s))


def fejezetek(szoveg: str) -> list:
    """A szöveg fejezetekre bontva: [(cím, tartalom)].

    A jelölő ELŐTTI szöveg is fejezet lesz (ha van benne tartalom) — ez
    tipikusan a fülszöveg vagy a bevezető. A jelölő-sor MAGA nem kerül bele
    a tartalomba: az technikai jel, nem felolvasandó szöveg.
    """
    ki = []
    cim, darab = "", []

    def zar():
        szoveg_resz = "\n".join(darab).strip("\n")
        if szoveg_resz.strip() or cim:
            ki.append((cim, szoveg_resz))

    for sor in (szoveg or "").split("\n"):
        if jelolo_e(sor):
            zar()
            cim, darab = jelolo_cime(sor), []
        else:
            darab.append(sor)
    zar()
    if not ki:
        return []
    # ha az első fejezetnek nincs címe és nincs is tartalma, kihagyjuk
    return [(c, t) for c, t in ki if t.strip() or c]


def cimek(szoveg: str) -> list:
    """Csak a fejezetcímek, sorszámozva – a felsoroláshoz és a bemondáshoz."""
    ki = []
    for i, (cim, _t) in enumerate(fejezetek(szoveg), 1):
        ki.append(cim or "%d. fejezet" % i)
    return ki
