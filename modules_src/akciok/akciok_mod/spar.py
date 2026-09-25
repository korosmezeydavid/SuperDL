# -*- coding: utf-8 -*-
"""Spar és Interspar – a spar.hu saját PDF-szórólapjai.

A spar.hu/ajanlatok oldal a szórólapok PDF-jét is közvetlenül linkeli
(/content/dam/sparhuwebsite/_flyers/ÉÉÉÉ/HHNN/spar-szorolap-….pdf). A PDF
szövegrétegében a sorrend szétszórt (az ár gyakran messze van a névtől),
de a név, a kiszerelés és a zárójeles EGYSÉGÁR mindig együtt áll:

    Danonino XXL
    eper-banán
    4×95 g
    (2.365,79 Ft/1 kg)        → 0,38 kg × 2365,79 = 899 Ft (a nyomtatott ár)

Ezért – mint a Tescónál – a darabárat a kiírt egységárból számoljuk.
Ami utána jön, az is hozzá tartozik:
    „2 db-tól:” / „6 db esetén:” + (egységár)  → mennyiségi ár (megjegyzés)
    „MYSPAR ÁR*” … (egységár)                   → kártyás (MySpar) ár
Pultos áru („a kiszolgálópultban”, kiszerelés nélkül): az ár kilónként.
"""
import io
import re

from .aldi import szamolt_ar

BOLT = "Spar"
OLDAL = "https://www.spar.hu/ajanlatok"
ALAP = "https://www.spar.hu"
# a helyi (egy-egy üzletre szóló) lapokat nem vesszük, csak az országosakat
UJSAGOK = (("spar-szorolap", "Spar szórólap"),
           ("interspar-szorolap", "Interspar szórólap"))

_EGYS = re.compile(r"^\((\d[\d.]*(?:,\d+)?)\s*Ft/1\s*(kg|l|db|m|pár|mosás|tekercs)\)$",
                   re.I)
_MERET = re.compile(r"^(\d+(?:[,.]\d+)?\s*[x×]\s*)?\d+(?:[,.]\d+)?\s*"
                    r"(g|dkg|kg|ml|cl|l|db|tekercs|pár|mosás|m|lap)\b"
                    r"(\s*/\s*\w+)?\s*(;\s*ár:\s*\d[\d.]*\s*Ft)?$", re.I)
_TOBB = re.compile(r"^(\d+)\s*db\s*(-tól|esetén)\s*:?$", re.I)
# a név körüli töltelék („a kiszolgálópultban és csomagolt kiszerelésben is
# kapható”): átlépjük, nem kerül a névbe, de nem is állítja meg a keresést
_TOLTELEK = re.compile(r"(kiszolgálópult|kiszerelésben|kapható|^és\b|^darabolt)", re.I)
_STOP = re.compile(r"(\bFt\b|^csak$|%|spórolás|myspar|esetén|-tól|visszaváltási|"
                   r"díj:|normál|érvényes|kiszerelés|egységár|kedvezőbb|kártyával|"
                   r"napig|illusztráció|nyerj|"
                   r"^\d[\d.,]*$|^/|oldalon|üzleteinkben|ajánlatunk|^válaszd|"
                   r"^és$|^vagy$|^is!?$)", re.I)
_ERV = re.compile(r"Érvényes:\s*(\d{4})\.\s*(\d{2})\.\s*(\d{2})\..*?"
                  r"(\d{4})\.\s*(\d{2})\.\s*(\d{2})\.", re.S)


def _szam(s: str) -> float | None:
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _darab(meret: str, egys: float, alap: str) -> int | None:
    m = re.search(r";\s*ár:\s*(\d[\d.]*)\s*Ft", meret or "")
    if m:
        return int(m.group(1).replace(".", ""))
    meret = (meret or "").replace("×", "x")
    return szamolt_ar(meret, "%s Ft/%s" % (("%.2f" % egys).replace(".", ","), alap))


def _nevek(L: list, j: int, hatar: int) -> tuple:
    """Visszafelé a névsorok j-től (a határig); (nevek, az első előtti index)."""
    nevek, lepes = [], 0
    while j > hatar and len(nevek) < 5 and lepes < 9:
        lepes += 1
        if _TOLTELEK.search(L[j]) and not _EGYS.match(L[j]):
            j -= 1
            continue
        if not _nevsor(L[j]):
            break
        nevek.insert(0, L[j])
        j -= 1
    # a név a márkával kezdődik: az előtte kóborló kisbetűs sorokat elhagyjuk
    while len(nevek) > 1 and nevek[0][:1].islower() and \
            any(x[:1].isupper() for x in nevek[1:]):
        nevek.pop(0)
    return nevek, j


def _nevsor(s: str) -> bool:
    return bool(re.search(r"[a-záéíóöőúüű]", s, re.I)) and not _STOP.search(s) \
        and not _EGYS.match(s) and not _MERET.match(s) and len(s) < 60


def _egysegar(egys: float, alap: str) -> str:
    return "1 %s = %s Ft" % (alap, ("%.2f" % egys).rstrip("0").rstrip(".").replace(".", ","))


def ervenyesseg(szoveg: str) -> str:
    m = _ERV.search(szoveg or "")
    return "%s.%s-tól %s.%s-ig" % (m.group(2), m.group(3), m.group(5), m.group(6)) \
        if m else ""


def termekek(szoveg: str, ujsag: str = "", ervenyes: str = "") -> list:
    from .termek import Termek
    L = [re.sub(r"\s+", " ", s).strip() for s in (szoveg or "").split("\n")]
    L = [s for s in L if s]
    ki, utolso, hatar = [], None, -1        # utolso = (Termek, meret, sorindex)
    for i, s in enumerate(L):
        e = _EGYS.match(s)
        if not e:
            continue
        egys, alap = _szam(e.group(1)), e.group(2).lower()
        if not egys:
            hatar = i
            continue
        elozo = L[i - 1] if i else ""
        meret_i = i - 1
        # „62 db/csomag | 1 csomag | (122,56 Ft/1 db)”
        if re.match(r"^1\s*(csomag|doboz)$", elozo, re.I) and i >= 2 \
                and _MERET.match(L[i - 2]):
            meret_i = i - 2
        if _MERET.match(L[meret_i]):
            meret = L[meret_i]
            nevek, j = _nevek(L, meret_i - 1, hatar)
            hatar = i
            if not nevek:
                continue
            ar = _darab(meret, egys, alap)
            if not ar:
                continue
            nev = _nev(nevek, utolso, j)
            t = Termek(bolt=BOLT, nev=nev, ar=ar,
                       kiszereles=re.sub(r";\s*ár:.*$", "", meret).replace("×", "x"),
                       egysegar=_egysegar(egys, alap), ervenyes=ervenyes,
                       kategoria=ujsag)
            ki.append(t)
            utolso = (t, meret, i, nevek)
            continue
        tobb = _TOBB.match(elozo)
        kozel = utolso is not None and i - utolso[2] <= 6
        if tobb and kozel:
            t, meret = utolso[0], utolso[1]
            db_ar = _darab(re.sub(r";\s*ár:.*$", "", meret), egys, alap) \
                if t.kiszereles != "kilónként" else int(round(egys))
            if db_ar and db_ar < t.ar:
                t.megjegyzes = ", ".join(x for x in (
                    t.megjegyzes, "%s db-tól %d Ft/db" % (tobb.group(1), db_ar)) if x)
            hatar = i
            continue
        if kozel and any("MYSPAR" in x.upper() for x in L[max(0, i - 4):i]):
            t, meret = utolso[0], utolso[1]
            k = int(round(egys)) if t.kiszereles == "kilónként" else \
                _darab(re.sub(r";\s*ár:.*$", "", meret), egys, alap)
            if k and k < t.ar:
                t.kartyas_ar, t.kartya_nev = k, "MySpar-ral"
                t.kedvezmeny = "-%d%% MySpar-ral" % round((1 - k / t.ar) * 100)
            hatar = i
            continue
        # pultos áru: név, esetleg „a kiszolgálópultban”, aztán az egységár
        nevek, j = _nevek(L, i - 1, hatar)
        hatar = i
        if nevek and alap == "kg" and len(" ".join(nevek)) > 6:
            t = Termek(bolt=BOLT, nev=_nev(nevek, utolso, j), ar=int(round(egys)),
                       kiszereles="kilónként", egysegar=_egysegar(egys, alap),
                       ervenyes=ervenyes, kategoria=ujsag)
            ki.append(t)
            utolso = (t, "", i, nevek)
    return ki


def _nev(nevek: list, utolso, eleje: int) -> str:
    nev = re.sub(r"\s+", " ", " ".join(nevek)).replace("*", "").strip(" ,;")
    # „buci | tejes 350 g …” után „csokoládés-tejes 210 g …”: a változat neve
    # kisbetűs – elé tesszük az előző termék első sorát
    if nev == nev.lower() and utolso and eleje >= utolso[2] - 1:
        nev = "%s, %s" % (utolso[3][0].strip(" ,;*"), nev)
    return nev


def ujsagok(oldal_html: str) -> list:
    """[(cím, pdf-cím)] – az országos lapok közül mindből a legújabb."""
    linkek = re.findall(r'(/content/dam/sparhuwebsite/_flyers/(\d{4})/(\d{4})/'
                        r'([\w\-]+)\.pdf)', oldal_html or "")
    ki = []
    for elotag, cim in UJSAGOK:
        jo = [(ev + nap, ALAP + ut) for ut, ev, nap, nev in set(linkek)
              if nev.lower().startswith(elotag)]
        if jo:
            ki.append((cim, max(jo)[1]))
    return ki


def letolt(get, get_bytes, jelez=lambda s: None) -> list:
    from pdfminer.high_level import extract_text
    ki, latott = [], set()
    for cim, pdf_url in ujsagok(get(OLDAL)):
        jelez("Spar: %s letöltése…" % cim)
        pdf = get_bytes(pdf_url)
        jelez("Spar: %s olvasása…" % cim)
        szoveg = extract_text(io.BytesIO(pdf))
        for t in termekek(szoveg, cim, ervenyesseg(szoveg)):
            k = (t.nev.lower(), t.ar)
            if k in latott:
                continue
            latott.add(k)
            ki.append(t)
    return ki
