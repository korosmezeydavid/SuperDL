# -*- coding: utf-8 -*-
"""Super Mail – BESZÉLGETÉSEK és IDÉZET-ÁTUGRÁS.

Két dolog, ami vakon aránytalanul sokat számít:

  • BESZÉLGETÉS: a levelek szálakba fogva – „3 levél ebben a beszélgetésben”.
    A szálat elsősorban a szabvány szerinti hivatkozásokból (Message-ID,
    In-Reply-To, References) építjük, és csak másodsorban a tárgyból.
  • IDÉZET-ÁTUGRÁS: egy válaszban gyakran hatszor benne van az egész előzmény.
    Látva ezt át lehet ugrani; hallgatva végig kell ülni. Ezért kiszedjük a
    levél ÚJ részét, és azt olvassuk fel elsőként.
"""

from __future__ import annotations

import re
import unicodedata

_ELOTAG = re.compile(
    r"^\s*((re|fw|fwd|vá|va|valasz|válasz|tovabbitas|továbbítás)\s*(\[\d+\])?\s*:\s*)+",
    re.IGNORECASE)

# Idézet-kezdő sorok: a szabványos „>” mellett a magyar és angol bevezetők.
_IDEZET_KEZDET = re.compile(
    r"^\s*(-{2,}\s*(eredeti|original|továbbított|forwarded)[^\n]*"
    r"|.{0,120}\b(írta|irta|wrote|schrieb)\s*:\s*"
    r"|(on|.{0,80}\d{4}\.).{0,120}\bwrote:\s*"
    r"|_{5,}"
    r"|from:\s.+)$",
    re.IGNORECASE)


def _norm(sz) -> str:
    sz = unicodedata.normalize("NFKD", str(sz or ""))
    return "".join(c for c in sz if not unicodedata.combining(c)).casefold()


def targy_torzse(targy: str) -> str:
    """A tárgy a Re:/Fwd: előtagok nélkül – ez a szál „neve”."""
    sz = str(targy or "").strip()
    elozo = None
    while sz != elozo:
        elozo = sz
        sz = _ELOTAG.sub("", sz).strip()
    return sz


def _azonositok(info: dict) -> set:
    ki = set()
    for kulcs in ("azonosito", "valasz_erre", "hivatkozasok"):
        for m in re.findall(r"<[^>]+>", str(info.get(kulcs, "") or "")):
            ki.add(m)
    return ki


def szalak(levelek) -> list:
    """A levelek beszélgetésekbe fogva.

    Visszaad: [[levél, …], …] – minden szál IDŐRENDBEN (a legrégebbi elöl),
    a szálak pedig a legfrissebb levelük szerint, a legújabb elöl."""
    levelek = list(levelek or [])
    csoportok = []          # [(azonosító-halmaz, tárgy-törzs, [levelek])]
    for info in levelek:
        azon = _azonositok(info)
        targy = _norm(targy_torzse(info.get("targy", "")))
        cel = None
        for csop in csoportok:
            if azon & csop[0] or (targy and targy == csop[1]):
                cel = csop
                break
        if cel is None:
            csoportok.append([set(azon), targy, [info]])
        else:
            cel[0] |= azon
            cel[2].append(info)
    # a szálakon belül megőrizzük a kapott sorrendet megfordítva (a lista
    # legfrissebb-elöl érkezik, a beszélgetést viszont időrendben olvassuk)
    ki = [list(reversed(c[2])) for c in csoportok]
    return ki


def szal_szoveg(szal) -> str:
    """A beszélgetés egy mondatban – ezt olvassa fel a képernyőolvasó."""
    if not szal:
        return ""
    targy = targy_torzse(szal[-1].get("targy", "")) or "(nincs tárgy)"
    if len(szal) == 1:
        return "%s – 1 levél" % targy
    resztvevok = []
    for info in szal:
        f = str(info.get("felado", "")).split("<")[0].strip().strip('"')
        if f and f not in resztvevok:
            resztvevok.append(f)
    return ("%s – %d levél ebben a beszélgetésben (%s)"
            % (targy, len(szal), ", ".join(resztvevok[:4])))


# ====================================================================
#  Idézet-átugrás
# ====================================================================

def uj_resz(torzs: str) -> str:
    """A levél ÚJ része: az idézett előzmény és az aláírás nélkül."""
    sorok = (torzs or "").splitlines()
    ki = []
    for sor in sorok:
        if _IDEZET_KEZDET.match(sor.strip()):
            break
        if sor.strip().startswith(">"):
            break
        if sor.strip() in ("--", "-- "):        # aláírás-elválasztó (RFC 3676)
            break
        ki.append(sor)
    # a végéről a felesleges üres sorokat levágjuk
    while ki and not ki[-1].strip():
        ki.pop()
    return "\n".join(ki).strip()


def idezet_aranya(torzs: str) -> float:
    """Mennyi az idézett rész aránya (0–1)? Ha nagy, érdemes átugrani."""
    egesz = len((torzs or "").strip())
    if not egesz:
        return 0.0
    uj = len(uj_resz(torzs))
    return max(0.0, min(1.0, 1.0 - uj / egesz))


def bevezeto(torzs: str) -> str:
    """Felolvasható jelzés az idézetről – csak ha tényleg sok van."""
    arany = idezet_aranya(torzs)
    if arany < 0.4:
        return ""
    uj = uj_resz(torzs)
    sorok = len([s for s in uj.splitlines() if s.strip()])
    if not uj:
        return ("Ez a levél szinte csak idézett előzményt tartalmaz, új "
                "szöveg alig van benne.")
    return ("A levél új része %d sor; a többi idézett előzmény. Az új résszel "
            "kezdem." % sorok)
