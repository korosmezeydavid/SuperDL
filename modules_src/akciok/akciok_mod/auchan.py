# -*- coding: utf-8 -*-
"""Auchan – a heti (és tematikus) katalógusok iPaper-szövegrétegéből.

Ugyanaz a gyűjtő, ami az androidos SuperDL-ben fut (AuchanOffers.kt), és
ami a kutatásban (akcio_kutatas/egyeb/auchan_offers.py) készült; a kettő
egyezését az Android-oldal egyezés-tesztje őrzi (426 = 426 termék).

    Felfedezés: auchan.hu/api/v2/cache/catalog/list?availability=current&storeType=hyper|super
    Szöveg:     a katalógus `flipbookUrl` néző-oldala → "pageTexts":[…]
    Párosítás:  ár = kiszerelés × egységár, az oldal ár-címkéivel ELLENŐRIZVE

A név-sorok CSUPA NAGYBETŰSEK („CSIRKEMELLFILÉ"), utánuk a leírás a
kiszereléssel és az egységárral; a nagy árcímkék szövege máshol áll.

⚠️ SZÁNDÉKOS SZIGOR: csak az a termék marad, amelynek az ára igazolt (a
számolt ár ott van az oldalon, vagy „2 db: N Ft" kiírás). A kártyás és az
eredeti ár is csak igazolva marad – egy vak felhasználónak inkább kevesebbet
mondjunk, mint rosszat.
"""
import datetime as _dt
import json
import re

from .termek import Termek

BOLT = "Auchan"
LISTA = ("https://auchan.hu/api/v2/cache/catalog/list?availability=current"
         "&storeType=")
KARTYA = "Auchan Bizalomkártyával"

LOW = re.compile(r"[a-záéíóöőúüű]")
LET = re.compile(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]")
CODE = re.compile(r"^\d+_[A-Z]{2}$")
NOISE = ("ÚJDONSÁG", "NORMÁL ELADÁSI", "NYEREMÉNY", "MATRICA", "SMEG",
         "TÉNYLEG", "ELINDULT", "AUCHAN.HU", "WWW.")
NUMTOK = re.compile(r"[\d+.,x%/-]+")
NUM = r"\d{1,3}(?: \d{1,3})*(?:,\d+)?"
PRICE_TOK = re.compile(r"(Bizalomkártyával:\s*|Tényleg ennyi:\s*)?(" + NUM +
                       r") ?Ft(?: ?/(10 dkg|db|kg|l))?")
UNIT_RX = re.compile(r"((?:" + NUM + r")(?:/" + NUM + r")*) ?Ft/"
                     r"(kg|l|db|tekercs|lap|mosás|m|csomag|pár)\b")
PACK_RX = re.compile(r"(?<![\d/])(\d+(?:,\d+)?(?:/\d+(?:,\d+)?)*)\s?"
                     r"(?:x\s?(\d+(?:,\d+)?)\s?)?(kg|dkg|g|ml|cl|l)\b")
MULTI_RX = re.compile(r"(\d+(?:\+\d+)?) db: (" + NUM + r") ?Ft")
CUT = re.compile(r"\s\d+_[A-Z]{2}\b|\s-\d+ %|Tényleg ennyi:")
SZOKOZOK = re.compile("[   \xa0]")
DARAB_EGYSEGEK = ("tekercs", "lap", "mosás", "db", "pár")


def _num(s: str) -> float:
    return float(s.replace(" ", "").replace("\xa0", "").replace(",", "."))


def _nagybetus(tok: str) -> bool:
    w = tok.strip(",.*!:;()\"'")
    if CODE.match(w):
        return False
    return len(LET.findall(w)) >= 2 and not LOW.search(w)


def _nevek(text: str) -> list:
    """(kezdet, vég, név) a CSUPA NAGYBETŰS szó-sorozatokra."""
    toks = [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"\S+", text)]

    def szamnagy(k):
        return (k + 1 < len(toks) and NUMTOK.fullmatch(toks[k][2])
                and not CODE.match(toks[k][2]) and _nagybetus(toks[k + 1][2]))
    ki, i = [], 0
    while i < len(toks):
        if _nagybetus(toks[i][2]) or szamnagy(i):
            j = i
            while j + 1 < len(toks) and (_nagybetus(toks[j + 1][2])
                                          or szamnagy(j + 1)):
                j += 1
            ki.append((toks[i][0], toks[j][1], text[toks[i][0]:toks[j][1]]))
            i = j + 1
        else:
            i += 1
    return ki


def _ar_tokenek(region: str) -> list:
    ki = []
    for m in PRICE_TOK.finditer(region):
        elo = m.group(1) or ""
        fajta = "card" if elo.startswith("Bizalom") else ("fix" if elo else "ft")
        per, v = m.group(3), _num(m.group(2))
        if per == "10 dkg":
            v *= 10
            fajta += "/kg"
        elif per:
            fajta += "/" + per
        ki.append((v, fajta))
    return ki


def _kiszereles(reszletek: str):
    """(mennyiség kg-ban / l-ben, a kiszerelés szövege) az első változatból."""
    m = PACK_RX.search(reszletek)
    if not m:
        return None, None
    elso = _num(m.group(1).split("/")[0])
    menny = elso * _num(m.group(2)) if m.group(2) else elso
    f = {"g": 0.001, "dkg": 0.01, "kg": 1, "ml": 0.001, "cl": 0.01, "l": 1}[m.group(3)]
    return menny * f, m.group(0)


def _egyezik(v, toks, fajtak):
    best = None
    for t, k in toks:
        if k not in fajtak:
            continue
        d = abs(t - v)
        if d <= max(3, 0.02 * v) and (best is None or d < abs(best - v)):
            best = t
    return best or None


def _egysegarak(resz: str, egyseg=None):
    vals, u0 = [], egyseg
    for m in UNIT_RX.finditer(resz):
        u = m.group(2)
        if u0 is None:
            u0 = u
        if u == u0:
            vals.append(_num(m.group(1).split("/")[0]))
    return u0, vals


def _g(x: float) -> str:
    return ("%g" % x).replace(".", ",")


def oldal(text: str, oldalszam: int) -> list:
    """Egy oldal szövege → az IGAZOLT árú termékek szótárai."""
    text = SZOKOZOK.sub(" ", text or "")
    futok = _nevek(text)
    jeloltek = []
    for k, (s, e, nev) in enumerate(futok):
        kov = futok[k + 1][0] if k + 1 < len(futok) else len(text)
        farok = text[e:kov]
        det = farok
        c = CUT.search(det)
        if c:
            det = det[:c.start()]
        det = det.strip(" ,")
        felt = None
        if "ESETÉN" in nev:
            a, _, b2 = nev.partition("ESETÉN")
            felt, nev = (a + "ESETÉN").strip("* "), b2.strip()
        if nev.startswith(str(oldalszam) + " "):
            nev = nev[len(str(oldalszam)) + 1:]
        if not nev or any(z in nev for z in NOISE) or len(nev) < 4:
            continue
        if not ("Ft/" in det or PACK_RX.search(det) or " db:" in det):
            continue
        elotag = len(farok) - len(farok.lstrip(" ,"))
        jeloltek.append({"s": s, "e": e + elotag + len(det),
                         "nev": nev.replace("\xad ", "").replace("\xad", ""),
                         "det": det, "felt": felt})
    if not jeloltek:
        return []
    region, utolso = [], 0
    for p in jeloltek:
        region.append(text[utolso:p["s"]] if p["s"] >= utolso else "")
        utolso = p["e"]
    region.append(text[utolso:])
    toks = _ar_tokenek(" | ".join(region))
    ki = []
    for p in jeloltek:
        det = p["det"]
        fo, _, kartya = det.partition("Bizalomkártyával:")
        menny, csomag = _kiszereles(fo)
        u, vals = _egysegarak(fo)
        if u in DARAB_EGYSEGEK and menny is None:
            m = re.search(r"(\d+)(?:/\d+)* " + u, fo)
            if m:
                menny, csomag = float(m.group(1)), m.group(0)
        tobb = MULTI_RX.findall(det)
        ar = regi = kartya_ar = egysegar = None
        igazolt = regi_ok = False
        kartya_ok = None
        if vals:
            egysegar = "%s Ft/%s" % (_g(vals[-1]), u)
            if menny:
                uj = menny * vals[-1]
                t = _egyezik(uj, toks, ("ft", "fix", "ft/db", "card"))
                ar, igazolt = (t, True) if t else (uj, False)
                if len(vals) > 1:
                    o = menny * vals[0]
                    to = _egyezik(o, toks, ("ft", "fix"))
                    regi, regi_ok = (to or o), to is not None
            elif u == "kg":
                ar, csomag = vals[-1], "1 kg"
                igazolt = _egyezik(vals[-1], toks, ("ft/kg", "ft", "fix")) is not None
                if len(vals) > 1:
                    regi, regi_ok = vals[0], True
        cu, cvals = _egysegarak(kartya, u)
        if cvals:
            if menny:
                talal = [h for h in (_egyezik(menny * cv, toks, ("card",))
                                     for cv in cvals) if h]
                kartya_ar = talal[0] if talal else menny * cvals[0]
                kartya_ok = bool(talal)
            elif cu == "kg":
                kartya_ar = cvals[0]
        if tobb and ar is None:
            ar, igazolt = _num(tobb[0][1]), True
        if not (igazolt and ar is not None):
            continue
        ki.append({"nev": p["nev"], "csomag": csomag, "ar": ar,
                   "regi": regi if regi_ok else None,
                   "kartya": kartya_ar if kartya_ok is not False else None,
                   "egysegar": egysegar, "felt": p["felt"],
                   "tobb": "; ".join("%s db: %s Ft" % (q, pr) for q, pr in tobb)})
    return ki


def katalogusok(json_szoveg: str) -> list:
    """A catalog/list JSON → [(id, cím, flipbookUrl, tól, ig)], legfeljebb 10."""
    ki = []
    for c in (json.loads(json_szoveg) or [])[:10]:
        if isinstance(c, dict):
            ki.append((c.get("id"), c.get("title") or "", c.get("flipbookUrl") or "",
                       (c.get("availabilityFromDate") or "")[:10],
                       (c.get("availabilityToDate") or "")[:10]))
    return ki


def oldal_szovegek(html: str) -> list:
    i = (html or "").find('"pageTexts":')
    if i < 0:
        return []
    tomb, _ = json.JSONDecoder().raw_decode(html, i + len('"pageTexts":'))
    return [a or "" for a in tomb]


def _ervenyes_ma(tol: str, ig: str, ma) -> bool:
    try:
        return _dt.date.fromisoformat(tol) <= ma <= _dt.date.fromisoformat(ig)
    except ValueError:
        return True          # nincs értelmes dátum: a lista „current"-nek mondta


def _szep(nev: str) -> str:
    return nev[:1].upper() + nev[1:].lower() if nev.isupper() else nev


def _mmdd(d: str) -> str:
    return d[5:].replace("-", ".") if len(d) >= 10 else d


def termek(p: dict, cim: str, tol: str, ig: str, kod: str) -> Termek:
    t = Termek(bolt=BOLT, nev=_szep(p["nev"]), ar=int(round(p["ar"])),
               kiszereles=p["csomag"] or "",
               egysegar=p["egysegar"] or "", kategoria=cim, kod=kod,
               ervenyes=("%s-tól %s-ig" % (_mmdd(tol), _mmdd(ig))
                         if tol and ig else ""))
    if p["regi"] and p["regi"] > p["ar"]:
        t.regi_ar = int(round(p["regi"]))
        t.kedvezmeny = "-%d%%" % round((1 - p["ar"] / p["regi"]) * 100)
    if p["kartya"] and p["kartya"] < p["ar"]:
        t.kartyas_ar, t.kartya_nev = int(round(p["kartya"])), KARTYA
    t.megjegyzes = "; ".join(x for x in (
        _szep(p["felt"]) if p["felt"] else "", p["tobb"]) if x)
    return t


def letolt(get, jelez=lambda s: None, ma=None) -> list:
    """Az összes MA érvényes Auchan-katalógus (hipermarket + szupermarket, a
    közösek egyszer) igazolt árú termékei."""
    ma = ma or _dt.date.today()
    katok, latott, lista_ok = [], set(), False
    for tipus in ("hyper", "super"):
        try:
            lista = katalogusok(get(LISTA + tipus))
        except Exception:                       # noqa: BLE001
            continue
        lista_ok = True
        for k in lista:
            if k[0] not in latott and _ervenyes_ma(k[3], k[4], ma):
                latott.add(k[0])
                katok.append(k)
    if not lista_ok:
        raise RuntimeError("az Auchan katalógus-listája nem érhető el")
    ki = []
    for azon, cim, url, tol, ig in katok:
        jelez("Auchan: %s…" % cim)
        try:
            oldalak = oldal_szovegek(get(url))
        except Exception:                       # noqa: BLE001
            continue
        for i, szoveg in enumerate(oldalak):
            for n, p in enumerate(oldal(szoveg, i + 1)):
                ki.append(termek(p, cim, tol, ig,
                                 "auchan:%s:%d:%d" % (azon, i + 1, n + 1)))
    return ki
