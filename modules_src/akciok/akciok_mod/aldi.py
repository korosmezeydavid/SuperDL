# -*- coding: utf-8 -*-
"""Aldi – az Aldi saját lapozós újságja (szorolap.aldi.hu, Publitas).

A lapozó minden oldalhoz kiadja a nyomdai SZÖVEGRÉTEGET is
(`<újság>/spreads.json` → pages[].text). Ez nem kép és nem AI: ugyanaz a
szöveg, ami az újságban le van nyomtatva.

⚠️ A szöveg sorrendje a nyomdai elrendezést követi, ezért az ár („769 /kg”,
„Ft”) gyakran NEM a név mellett áll. Ami viszont mindig egyben van, az a
termék blokkja: név, kiszerelés, EGYSÉGÁR és cikkszám:

    VAJAS RÚD
    150 g/csomag
    3 660 Ft/kg
    156305

Az árat ebből SZÁMOLJUK: 0,150 kg × 3 660 Ft/kg = 549 Ft – ami pontosan a
kiírt ár (2026-09-25-én mérve a teljes újságon). A kiírt egységár a bolt
hivatalos adata, a szorzás csak visszafejti belőle a darabárat.
"""
import datetime as _dt
import json
import re

from .termek import Termek, ar_szam

BOLT = "Aldi"
ALAP = "https://szorolap.aldi.hu"

_KOD = re.compile(r"^\d{6}$")
_EGYSEGAR = re.compile(
    r"^([\d  .,]+?)(?:\s*/\s*[\d  .,]+)?\s*Ft\s*/\s*(kg|l|db|darab|m|m2|tekercs|mosás|pár)\b",
    re.I)
_MERET = re.compile(r"(\d+(?:[,.]\d+)?)\s*(?:x\s*(\d+(?:[,.]\d+)?)\s*)?(kg|g|dkg|ml|cl|l|db)\b",
                    re.I)
_SZEMET = re.compile(
    r"(^a kép illusztráció|dekoráció|kiegészítők|^szuper$|csak ennyi|"
    r"^többféle$|^\*|lásd a hátoldalon|árkedvezmény|érvényben volt|"
    r"állandó kínálatunk|mostantól még több|^ft$|^vegán$|ai által készült|"
    r"^\d{2}\.\s*\d{2}\.|csütörtök|szerdáig|készlet erejéig)",
    re.I)


def ujsag_nevek(ma: _dt.date | None = None) -> list:
    """A lehetséges újságnevek: az idei és a jövő heti élelmiszer-újság,
    meg a „középső sor” (nonfood). A Publitas-címek hét szerint épülnek."""
    ma = ma or _dt.date.today()
    ki = []
    for eltolas in (0, 1, -1):
        d = ma + _dt.timedelta(weeks=eltolas)
        ev, het, _ = d.isocalendar()
        for fajta in ("aldi_online_akcios_ujsag", "aldi_kozepso_sor"):
            ki.append(("%s_%d_kw%02d" % (fajta, ev, het), fajta, het))
    return ki


def _szam(s: str) -> float | None:
    s = (s or "").replace("\xa0", " ").replace(" ", " ").strip()
    s = s.replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def szamolt_ar(meret: str, egysegar: str) -> int | None:
    """„150 g/csomag” + „3 660 Ft/kg” → 549. Ha nem egyértelmű: None."""
    e = _EGYSEGAR.match((egysegar or "").strip())
    if not e:
        return None
    egys = _szam(e.group(1))
    alap = e.group(2).lower()
    if egys is None:
        return None
    if alap in ("db", "darab", "tekercs", "pár", "mosás", "m"):
        # „6 darab” + „58,17 Ft/db” → 349; „10 tekercs” + „102,90 Ft/tekercs”
        m = re.search(r"(\d+)\s*(?:x\s*\d+\s*\w+\s*)?(darab|db|tekercs|pár|"
                      r"mosás|m)\b", meret or "", re.I)
        darab = int(m.group(1)) if m else 1
        ar = darab * egys
        return int(round(ar)) if 0 < ar < 1_000_000 else None
    m = _MERET.search(meret or "")
    if not m:
        return None
    menny = _szam(m.group(1))
    szorzo = _szam(m.group(2)) if m.group(2) else None
    egyseg = m.group(3).lower()
    if menny is None:
        return None
    if szorzo:                       # „4 x 125 g”
        menny = menny * szorzo
    valto = {"g": 0.001, "dkg": 0.01, "kg": 1, "ml": 0.001, "cl": 0.01,
             "l": 1}.get(egyseg)
    if valto is None or (alap == "kg" and egyseg in ("ml", "cl", "l")) or \
            (alap == "l" and egyseg in ("g", "dkg", "kg")):
        return None
    ar = menny * valto * egys
    return int(round(ar)) if 0 < ar < 1_000_000 else None


def _szep(s: str) -> str:
    s = re.sub(r"\s+", " ", s.replace("*", "")).strip()
    # „A.D.” és hasonló rövidítések maradnak, csak a sima szavakat alakítjuk
    return " ".join(w.capitalize() if len(w) >= 2 and w.isupper()
                    and w.replace("-", "").replace("’", "").isalpha() else w
                    for w in s.split())


def termekek(oldalak: list, ujsag: str = "", ervenyes: str = "") -> list:
    """`oldalak`: az oldalak szövegei sorrendben."""
    ki = []
    for szoveg in oldalak:
        bekezdesek = [b for b in re.split(r"\n\s*\n", szoveg or "") if b.strip()]
        elozo = ""
        for b in bekezdesek:
            sorok = [s.strip() for s in b.split("\n") if s.strip()]
            if not (len(sorok) >= 3 and _KOD.match(sorok[-1])):
                if len(sorok) == 1 and sorok[0].isupper() and len(sorok[0]) < 30 \
                        and not _SZEMET.search(sorok[0]):
                    elozo = sorok[0]        # a márka gyakran külön blokk
                continue
            egysegar_i = next((i for i, s in enumerate(sorok)
                               if _EGYSEGAR.match(s)), None)
            if egysegar_i is None:
                continue
            egysegar = sorok[egysegar_i]
            meret_i = next((i for i in range(egysegar_i - 1, -1, -1)
                            if _MERET.search(sorok[i]) or "/" in sorok[i]),
                           None)
            meret = sorok[meret_i] if meret_i is not None else ""
            vege = meret_i if meret_i is not None else egysegar_i
            nevek = [s for s in sorok[:vege] if not _SZEMET.search(s)]
            if not nevek:
                continue
            nagy = [s for s in nevek if s.isupper() or s.endswith("*")]
            kicsi = [s for s in nevek if s not in nagy]
            nev = _szep(" ".join(nagy or nevek[:1]))
            if elozo and elozo.lower() not in nev.lower():
                nev = _szep(elozo) + " " + nev
            t = Termek(bolt=BOLT, nev=nev, kod=sorok[-1],
                       kiszereles=re.sub(r"/.*$", "", meret).strip() or meret,
                       egysegar=egysegar.replace("  ", " "),
                       ervenyes=ervenyes, kategoria=ujsag,
                       megjegyzes=", ".join(kicsi))
            t.ar = szamolt_ar(meret, egysegar)
            if t.ar is None and "/db" in egysegar.replace(" ", "").lower():
                t.ar = ar_szam(egysegar)
            ki.append(t)
            elozo = ""
    return ki


def _ervenyes(oldalak: list) -> str:
    for sz in oldalak[:3]:
        m = re.search(r"(\d{2})\.(\d{2})\.\s*C\s*S\s*Ü", sz or "")
        if m:
            return "%s.%s-tól" % m.groups()
        m = re.search(r"(\d{2})\.(\d{2})\.\s*[-–]\s*(\d{2})\.(\d{2})\.", sz or "")
        if m:
            return "%s.%s-tól %s.%s-ig" % m.groups()
    return ""


# ---- aldi.hu ajánlat-oldalak (2026-09-25-től ez az ELSŐDLEGES) --------------
#
# Az aldi.hu saját ajánlat-oldalai (/ajanlatok/ÉÉÉÉ-HH-NN) tiszta termék-
# csempéket adnak: márka, név, kiszerelés, egységár, ár. Az oldal a sima
# Python-kérésre 403-at ad (böngésző-ujjlenyomatot vár), ezért ehhez a
# `curl_cffi` kell (a Core-ban, a yt-dlp is használja). Ha nincs meg, a
# fenti Publitas-szövegréteg a tartalék.

WEB = "https://www.aldi.hu"


def web_datumok(fo_html: str, ma: _dt.date | None = None) -> list:
    """A főoldal ajánlat-napjai közül az elmúlt 10 és a következő 7 nap."""
    ma = ma or _dt.date.today()
    ki = []
    for d in sorted(set(re.findall(r'/ajanlatok/(\d{4}-\d{2}-\d{2})', fo_html))):
        try:
            nap = _dt.date.fromisoformat(d)
        except ValueError:
            continue
        if -10 <= (nap - ma).days <= 7:
            ki.append(nap)
    return ki


def _html_szoveg(s: str) -> str:
    import html as _h
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", _h.unescape(s).replace("\xa0", " ")).strip()


_NAPOK = ("hétfőtől", "keddtől", "szerdától", "csütörtöktől", "péntektől",
          "szombattól", "vasárnaptól")


def web_csempek(oldal: str, nap: _dt.date | None = None) -> list:
    ki = []
    for d in oldal.split('data-test="product-tile"')[1:]:
        link = re.search(r'href="(/termek/[^"]+)"', d)
        nev = re.search(r'data-test="product-tile__name"[^>]*>(.*?)</div>', d, re.S)
        if not (link and nev):
            continue
        marka = re.search(r'data-test="product-tile__brandname"[^>]*>(.*?)</div>',
                          d, re.S)
        meret = re.search(r'data-test="product-tile__unit-of-measurement"[^>]*>(.*?)</div>',
                          d, re.S)
        egys = re.search(r'data-test="product-tile__comparison-price"[^>]*>(.*?)</div>',
                         d, re.S)
        ar = re.search(r'data-test="product-tile__price"[^>]*>(.*?)</a>', d, re.S)
        cimke = re.search(r'data-test="product-tile__on-sale-label"[^>]*>(.*?)</div>',
                          d, re.S)
        n = _html_szoveg(nev.group(1))
        m = _html_szoveg(marka.group(1)) if marka else ""
        # a név végén gyakran a kiszerelés is ott van („…, 100 ml”)
        t = Termek(bolt=BOLT, nev=_szep(m) + " " + n if m else n,
                   kod=WEB + link.group(1),
                   kiszereles=_html_szoveg(meret.group(1)) if meret else "",
                   egysegar=_html_szoveg(egys.group(1)).strip("()") if egys else "")
        if ar:
            nyers = ar.group(1)
            # ⚠️ a betétdíj („+50 Ft”) külön elem – NEM az ár (a Fantánál
            # különben „50 forint” lett volna)
            betet = re.search(r'class="base-price__deposit"[^>]*>(.*?)</(?:span|div)>',
                              nyers, re.S)
            if betet:
                t.megjegyzes = _html_szoveg(betet.group(1))
                nyers = nyers.replace(betet.group(0), "")
            szoveg = _html_szoveg(nyers)
            arak = [ar_szam(x) for x in re.findall(r"\d[\d  ]*\s?Ft", szoveg)]
            arak = [a for a in arak if a]
            if arak:
                t.ar = min(arak)
                if len(arak) > 1 and max(arak) > t.ar:
                    t.regi_ar = max(arak)
            k = re.search(r"-\s?\d+\s?%", szoveg)
            if k:
                t.kedvezmeny = k.group(0).replace(" ", "")
        if nap:
            t.ervenyes = "%02d.%02d-tól" % (nap.month, nap.day)
            t.kategoria = "%s %s" % (nap.strftime("%m.%d."),
                                    _NAPOK[nap.weekday()])
        if cimke:
            t.megjegyzes = ", ".join(x for x in (_html_szoveg(cimke.group(1)),
                                                 t.megjegyzes) if x)
        if t.ar is not None:
            ki.append(t)
    return ki


def _curl_get(url: str) -> str:
    from curl_cffi import requests as cr        # a Core-ból
    r = cr.get(url, impersonate="chrome", timeout=40)
    r.raise_for_status()
    return r.text


def web_letolt(jelez=lambda s: None, get=None, ma=None) -> list:
    get = get or _curl_get
    fo = get(WEB + "/hu/ajanlatok.html")
    ki, latott = [], set()
    for nap in web_datumok(fo, ma):
        jelez("Aldi: %s…" % nap.strftime("%m.%d."))
        for t in web_csempek(get(WEB + "/ajanlatok/" + nap.isoformat()), nap):
            if t.kod not in latott:
                latott.add(t.kod)
                ki.append(t)
    return ki


def letolt(get_bytes, jelez=lambda s: None, ma=None) -> list:
    """Előbb az aldi.hu ajánlat-oldalai; ha azok nem mennek (nincs
    curl_cffi, vagy a bolt oldala épp nem válaszol), a lapozós újság
    szövegrétege."""
    try:
        web = web_letolt(jelez, ma=ma)
    except Exception:                           # noqa: BLE001
        web = []
    try:
        ujsag = publitas_letolt(get_bytes, jelez, ma)
    except Exception:                           # noqa: BLE001
        ujsag = []
    return osszefesul(web, ujsag)


def _szavak(nev: str) -> set:
    from .termek import ekezet_nelkul
    return {w for w in re.findall(r"\w+", ekezet_nelkul(nev)) if len(w) > 2}


def _ugyanaz(a: set, b: set) -> bool:
    """Két név ugyanazt a terméket jelöli-e: legalább két közös szó, és ez
    a rövidebb név szavainak legalább fele („Vajas rúd • sajtos vagy” =
    „Snack Fun Vajas rúd, 150 g”)."""
    kozos = len(a & b)
    if not a or not b:
        return False
    if min(len(a), len(b)) == 1:
        return kozos == 1
    return kozos >= 2 and kozos * 2 >= min(len(a), len(b))


def osszefesul(web: list, ujsag: list) -> list:
    """A weboldal csempéi az elsődlegesek; az újságból csak az kerül mellé,
    ami a weben NINCS (az újság élelmiszereinek egy része csak ott szerepel).
    Egyezés: lásd `_ugyanaz`."""
    ki = list(web)
    webszavak = [_szavak(t.nev) for t in web]
    for t in ujsag:
        sz = _szavak(t.nev)
        if not sz:
            continue
        if any(_ugyanaz(sz, w) for w in webszavak):
            continue
        ki.append(t)
    return ki


def publitas_letolt(get_bytes, jelez=lambda s: None, ma=None) -> list:
    ki, latott, fajtak = [], set(), set()
    for nev, fajta, het in ujsag_nevek(ma):
        if fajta in fajtak:
            continue                # fajtánként a legfrissebb egy elég
        try:
            adat = get_bytes("%s/%s/spreads.json" % (ALAP, nev))
        except Exception:
            continue
        fajtak.add(fajta)
        cim = ("Akciós újság, %d. hét" if "akcios" in fajta
               else "Középső sor (nem élelmiszer), %d. hét") % het
        jelez("Aldi: %s…" % cim)
        oldalak = [pg.get("text") or ""
                   for sp in json.loads(adat.decode("utf-8"))
                   for pg in sp.get("pages", [])]
        erv = _ervenyes(oldalak)
        for t in termekek(oldalak, cim, erv):
            if t.kod in latott:
                continue
            latott.add(t.kod)
            ki.append(t)
    return ki
