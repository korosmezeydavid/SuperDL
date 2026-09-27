# -*- coding: utf-8 -*-
"""Illatorium – Kőrösmezey Dávid saját parfümboltja (illatorium.hu).

⚠️ NEM akciós újság, hanem a bolt TELJES saját kínálata (Dávid döntése,
2026-09-27: „remek lehetőség arra, hogy megjelenítsem a saját kínálatomat").
A felület ezt ki is mondja.

A forrás a bolt SAJÁT weboldala. Az oldal egy egyoldalas alkalmazás, a
termékek a JavaScript-csomagjában vannak (`/assets/index-<hash>.js`). A
csomag neve minden frissítéskor változik, ezért mindig a HTML-ből keressük
ki – így a program magától követi, ha a kínálat frissül. A kinyerés a
`G:\\Saját meghajtó\\visszaállítás\\illatorium-kereso\\extract.mjs` Python-
változata; ugyanazt a 2389 tételt kell adnia.

Három alak van a csomagban:
  {id:"AM-PINK",name:"America Pink EDT 50 ml",category:"america",
   inspiredBy:"Playboy – Pink",scentNote:"…",price50:3000}
  Vae=[["LF1","Név","Ihlette"],…]           (Lion Francesco, fix áras)
  gg("sorgenta-x","…",[{no:"12",name:"…",brand:"…",price30:…},…])
"""
import re

from .termek import Termek

BOLT = "Illatorium"
ALAP = "https://illatorium.hu"
OLDAL = ALAP + "/illatinspiraciok"

_BUNDLE = re.compile(r'src="(/assets/index-[^"]+\.js)"')
_SKIP = {"necessary", "functional", "analytics", "marketing"}
_LIT = re.compile(r'\{id:"([^"]+)",name:"((?:[^"\\]|\\.)*)"')
_AR = re.compile(r"price(Single|\d+):([0-9.e+]+)")
_LF = [("Vae", "lf-ferfi", 5000, 50), ("Uae", "lf-noi", 5000, 50),
       ("Hae", "lf-unisex", 7000, 60)]
_SORG = re.compile(r'gg\("([a-z-]+)","([^"]*)",\[')
_SORG_TETEL = re.compile(r'\{no:"([^"]*)",name:"([^"]*)"([^{}]*)\}')

_KOLLEKCIOK = [
    (r"^fp-", "Francesco Petroni"), (r"^feromon-", "Feromon"),
    (r"^iyaly-", "Iyaly"), (r"^america$", "America / US Prestige"),
    (r"^bies$", "Bi-es / Fabio Verso"), (r"^chatler-", "Chatler"),
    (r"^cl-", "Creation Lamis"), (r"^cuba-", "Cuba"), (r"^jf-", "J.Fenzi"),
    (r"^lx-|^luxure-", "Luxure"), (r"^nb-", "New Brand"),
    (r"^ly-", "Luxury"), (r"^vv-", "VV Love"), (r"^es-", "Essens"),
    (r"^one-avenue$", "One Avenue"), (r"^niche-olcso$", "Olcsó niche ihletésű"),
    (r"^lf-", "Lion Francesco"), (r"^sorgenta-", "Sorgenta"),
    (r"^mylance$", "My Lance"), (r"^testpermet$", "Bea's testpermet"),
    (r"^(ferfi|noi|unisex)$", "Bea's"),
]


def _vege(t: str, start: int, nyit: str, zar: str) -> int:
    """A `start`-nál nyíló zárójel párjának vége (a karakterláncokon át)."""
    d, s, esc, i = 0, None, False, start
    while i < len(t):
        c = t[i]
        if s:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == s:
                s = None
        elif c in "\"'`":
            s = c
        elif c == nyit:
            d += 1
        elif c == zar:
            d -= 1
            if d == 0:
                return i + 1
        i += 1
    return i


def _js(s: str | None) -> str | None:
    if s is None:
        return None
    try:
        return s.encode("latin-1", "backslashreplace").decode("unicode_escape") \
            if "\\" in s else s
    except Exception:
        return s


def _arak(szoveg: str) -> list:
    ki, latott = [], set()
    for m in _AR.finditer(szoveg):
        ml = None if m.group(1) == "Single" else int(m.group(1))
        try:
            ar = int(float(m.group(2)))
        except ValueError:
            continue
        if ar <= 100 or (ml, ar) in latott:
            continue
        latott.add((ml, ar))
        ki.append({"ml": ml, "ar": ar})
    ki.sort(key=lambda p: (p["ml"] if p["ml"] is not None else 10 ** 9, p["ar"]))
    return ki


def nyers_tetelek(t: str) -> list:
    """A csomag szövegéből a nyers tételek (az extract.mjs három gyűjtője)."""
    ki = []
    for m in _LIT.finditer(t):
        if m.group(1) in _SKIP:
            continue
        lit = t[m.start():_vege(t, m.start(), "{", "}")]

        def g(k):
            r = re.search(k + r':"((?:[^"\\]|\\.)*)"', lit)
            return _js(r.group(1)) if r else None
        ki.append({"id": m.group(1), "name": g("name"),
                   "category": g("category"), "inspiredBy": g("inspiredBy"),
                   "notes": g("scentNote"), "volume": g("volume"),
                   "prices": _arak(lit)})
    for nev, kat, ar, ml in _LF:
        i = t.find(nev + "=[[")
        if i < 0:
            continue
        start = i + len(nev) + 1
        lit = t[start:_vege(t, start, "[", "]")]
        for mm in re.finditer(r'\["([^"]*)","([^"]*)","([^"]*)"\]', lit):
            ki.append({"id": mm.group(1), "name": "Scent of " + mm.group(2),
                       "category": kat, "inspiredBy": mm.group(3),
                       "notes": None, "volume": None,
                       "prices": [{"ml": ml, "ar": ar}]})
    for g in _SORG.finditer(t):
        start = g.end() - 1
        lit = t[start:_vege(t, start, "[", "]")]
        for om in _SORG_TETEL.finditer(lit):
            bm = re.search(r'brand:"([^"]*)"', om.group(3))
            ki.append({"id": "SORG-" + om.group(1), "name": om.group(2),
                       "category": g.group(1),
                       "inspiredBy": ("%s – %s" % (bm.group(1), om.group(2))
                                      if bm else None),
                       "notes": None, "volume": None,
                       "prices": _arak(om.group(3))})
    return ki


def kollekcio(kat: str) -> str:
    for minta, nev in _KOLLEKCIOK:
        if re.search(minta, kat or ""):
            return nev
    return "Egyéb"


def _ml_nevbol(nev: str, volume: str | None):
    m = re.search(r"(\d{1,3})\s*ml\b", "%s %s" % (volume or "", nev or ""), re.I)
    return int(m.group(1)) if m else None


def termekek(t: str) -> list:
    ki, latott = [], set()
    for r in nyers_tetelek(t):
        if not r["id"] or r["id"] in latott or not r["name"]:
            continue
        latott.add(r["id"])
        pot = _ml_nevbol(r["name"], r["volume"])
        arak = [{"ml": p["ml"] if p["ml"] is not None else pot, "ar": p["ar"]}
                for p in r["prices"]]
        if not arak:
            continue
        elso = min(arak, key=lambda p: p["ar"])
        tob = [p for p in arak if p is not elso]
        megj = []
        if r["inspiredBy"]:
            megj.append("Ihlette: %s" % r["inspiredBy"])
        if r["notes"] and r["notes"] != r["inspiredBy"]:
            megj.append("Illatjegyek: %s" % r["notes"])
        if tob:
            megj.append("Más kiszerelés: " + ", ".join(
                "%s%d forint" % ("%d ml " % p["ml"] if p["ml"] else "", p["ar"])
                for p in tob))
        kisz = "%d ml" % elso["ml"] if elso["ml"] else (r["volume"] or "")
        ki.append(Termek(bolt=BOLT, nev=r["name"], ar=elso["ar"],
                         kiszereles=kisz, kategoria=kollekcio(r["category"]),
                         megjegyzes=". ".join(megj), kod=r["id"],
                         csoport="Parfüm és illat"))
    ki.sort(key=lambda x: (x.kategoria, x.nev.lower()))
    return ki


def letolt(get, jelez=lambda s: None) -> list:
    jelez("Illatorium: a kínálat betöltése…")
    m = _BUNDLE.search(get(OLDAL))
    if not m:
        raise RuntimeError("az illatorium.hu oldalán nem találom a "
                           "termékadatokat")
    return termekek(get(ALAP + m.group(1)))
