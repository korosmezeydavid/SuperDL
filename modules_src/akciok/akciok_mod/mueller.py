# -*- coding: utf-8 -*-
"""Müller – a drogéria, a parfüméria és a játék prospektus (mueller.co.hu).

⚠️ A helyes cím a `mueller.co.hu` (a `muller.hu` és a `mueller.hu` nem a
bolté – ezért utasított el korábban minden kérést).

A prospektusok oldala a bolt saját tárhelyére mutat (Amazon S3, a Müller
„dam-bucket"-je), a PDF-eknek van szövegrétege. Egy termék így jön ki:

      2.495 Ft          ← eredeti ár
      1.795 Ft          ← akciós ár
    −28 %
    FELIX               ← márka (csupa nagybetű, nem mindig van)
    Nedves macskaeledel
     12 × 85 g          ← kiszerelés
    többféle            ← változat (megjegyzésbe)

A PDF néhány betűtípusa saját kódolású: a keskeny szóköz „â", a kötőjel
„Ë", a nagykötőjel „È" alakban jön. Ezeket visszafordítjuk; ahol ennél több
a zagyva jel, azt a sort kihagyjuk (inkább rövidebb név, mint olvashatatlan).
Az egységárat NEM vesszük át: a tizedesvessző elvész belőle („154 Ft/1 ml"
valójában 1,54) – rossz számot nem mondunk be.
"""
import io
import re

from .termek import Termek, ar_szam

BOLT = "Müller"
ALAP = "https://www.mueller.co.hu"
OLDAL = ALAP + "/prospektusok/"
_PDF = re.compile(
    r"https://mueller-dam-bucket[^\"'\s<>?\\]+/prospektusok/"
    r"(drogerie|parfuemerie)/[^\"'\s<>?\\]+")
# ⚠️ A JÁTÉK-prospektus (spielware) szándékosan kimarad: ott a termék neve
# hol az ár ELŐTT, hol UTÁNA áll, így a név és az ár nem párosítható
# biztosan – rossz árat pedig nem mondunk be.
UJSAG_NEV = {"drogerie": "Drogéria", "parfuemerie": "Parfüméria",
             "spielware": "Játékok"}

_AR = re.compile(r"^\d{1,3}(?:\.\d{3})*\s*Ft$")
_SZAZALEK = re.compile(r"^[−-]\s*\d+\s*%$")
_MERET = re.compile(r"^(\d+(?:[,.]\d+)?\s*[×x]\s*)?\d+(?:[,.]\d+)?\s*"
                    r"(?:[–-]\s*\d+(?:[,.]\d+)?\s*)?"
                    r"(ml|l|g|kg|db|m|cm|mm|pár|tekercs|lap)\b", re.I)
_EGYSEGAR = re.compile(r"F[tö]\s*/\s*1", re.I)
_ZAGYVA = re.compile(r"[Ø»¡£ÅÎÏÌÐÑÒÔÕÞßæøþ¢¤¥¦§¨©ª«¬®¯°±²³µ¶·¸¹º¼½¾¿èì]")
_ERV = re.compile(r"(\d{4})\D(\d{2})\D(\d{2})\D{0,3}T[ÓO]L\s*(\d{2})\D(\d{2})",
                  re.I)
_FEJLEC = re.compile(r"^[A-ZÁÉÍÓÖŐÚÜŰ&,\- ]{4,}$")
_STOP = ("KEDVEZMÉNY", "AJÁNDÉK", "TOVÁBBI", "*")


def _tiszta(s: str) -> str:
    return (s.replace("â", " ").replace("Ë", "-").replace("È", "–")
            .replace("\xa0", " ").strip())


def ervenyes(szoveg: str) -> str:
    m = _ERV.search(szoveg.replace("£", ".").replace("Å", "-"))
    return "%s.%s–%s.%s." % (m.group(2), m.group(3), m.group(4),
                             m.group(5)) if m else ""


def _nagybetus(s: str) -> bool:
    betuk = [c for c in s if c.isalpha()]
    return len(betuk) >= 2 and all(c.isupper() for c in betuk)


def termekek(szoveg: str, ujsag: str = "", erv: str = "") -> list:
    nyersek = (szoveg or "").splitlines()
    sorok = [_tiszta(s) for s in nyersek]
    ki, kat, i, n = [], ujsag, 0, len(sorok)
    while i < n:
        s = sorok[i]
        # fejezetcím (pl. „TESTÁPOLÁS", „HAJÁPOLÁS") – a bolt saját kategóriája
        # fejezetcím: csupa nagybetűs sor, UTÁNA üres sor (a márkanév után
        # rögtön a terméknév jön, nem üres sor)
        if (_FEJLEC.match(s) and "KEDVEZM" not in s and "AJÁNDÉK" not in s
                and (i + 1 >= n or not sorok[i + 1])):
            kat = s[:1] + s[1:].lower()
        if not (_AR.match(s) and i + 1 < n and _AR.match(sorok[i + 1])):
            i += 1
            continue
        regi, ar = ar_szam(s), ar_szam(sorok[i + 1])
        j = i + 2
        kedv = ""
        while j < n and not sorok[j]:
            j += 1
        if j < n and _SZAZALEK.match(sorok[j]):
            kedv = "-" + re.sub(r"\D", "", sorok[j]) + "%"
            j += 1
        nev, meret, valt = [], "", []
        while j < n and not sorok[j]:
            j += 1
        while j < n and sorok[j]:
            t = sorok[j]
            if _AR.match(t) or any(t.startswith(x) for x in _STOP):
                break
            if _EGYSEGAR.search(t):
                j += 1
                continue
            if not meret and _MERET.match(t):
                meret = re.sub(r"\s+", " ", t)
            elif meret:
                if not _ZAGYVA.search(t):
                    valt.append(t)
            elif not _ZAGYVA.search(t) and len(nev) < 5:
                nev.append(t)
            j += 1
        i = j
        if not nev or ar is None or regi is None or ar >= regi:
            continue
        if len(" ".join(nev)) < 4:
            continue
        marka = nev[0] if _nagybetus(nev[0]) and len(nev) > 1 else ""
        resz = nev[1:] if marka else nev
        cim = " ".join(resz).strip()
        cim = re.sub(r"\s+", " ", cim).rstrip(" ,.;:")
        if marka:
            cim = "%s %s" % (marka.title() if len(marka) > 4 else marka, cim)
        megj = re.sub(r"\s+", " ", " ".join(valt)).strip()
        ki.append(Termek(bolt=BOLT, nev=cim[:1].upper() + cim[1:], ar=ar,
                         regi_ar=regi, kedvezmeny=kedv, kiszereles=meret,
                         ervenyes=erv, kategoria=kat or ujsag,
                         megjegyzes=megj[:120]))
    return ki


def prospektusok(oldal_html: str) -> list:
    """[(fajta, url)] – a jelenlegi drogéria-, parfüméria- és játékújság."""
    ki, latott = [], set()
    for m in _PDF.finditer(oldal_html or ""):
        url = m.group(0).rstrip("\\")
        if "InlineBanner" in url or url in latott:
            continue
        latott.add(url)
        ki.append((m.group(1), url))
    return ki


def pdf_szoveg(b: bytes) -> str:
    from pdfminer.high_level import extract_text
    return extract_text(io.BytesIO(b))


def letolt(get, get_bytes, jelez=lambda s: None) -> list:
    ki = []
    for fajta, url in prospektusok(get(OLDAL)):
        nev = UJSAG_NEV.get(fajta, fajta)
        jelez("Müller: a %s prospektus letöltése…" % nev.lower())
        szoveg = pdf_szoveg(get_bytes(url))
        ki.extend(termekek(szoveg, nev, ervenyes(szoveg)))
    return ki
