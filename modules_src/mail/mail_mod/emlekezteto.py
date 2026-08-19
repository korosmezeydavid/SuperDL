# -*- coding: utf-8 -*-
"""Super Mail – EMLÉKEZTETŐK: halasztás, „nem válaszoltak”, dátum a levélben.

Három dolog, ami a mai levelezőprogramokban bevált, és vakon különösen sokat ér:

  1. HALASZTÁS („emlékeztess rá”): a levél most nem aktuális – jöjjön vissza
     kedden reggel. Vakon ez azért fontos, mert a „majd később elolvasom”
     leveleket nem lehet szemmel a lista tetején tartani.
  2. „NEM VÁLASZOLTAK”: küldéskor bejelölhető, hogy szóljon, ha X napon belül
     nincs válasz. A választ a szabvány szerinti hivatkozásokból
     (In-Reply-To / References) ismerjük fel, nem szövegből.
  3. DÁTUM A LEVÉLBEN: ha a szöveg időpontot említ („kedden 14 órakor”), a
     program felajánlja, hogy felveszi a SuperDL naptárába.

A modul wx-mentes: adat és logika, hogy tesztelhető legyen.
"""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from datetime import date, datetime, timedelta

FAJL = "emlekeztetok.json"

HALASZT = "halaszt"
VALASZ_VARAS = "valasz"


def alap_mappa() -> str:
    from superdl import store
    return str(store.CONFIG_DIR)


def _ut(mappa: str) -> str:
    return os.path.join(mappa or alap_mappa(), FAJL)


def betolt(mappa: str = "") -> list:
    try:
        with open(_ut(mappa), encoding="utf-8") as f:
            return list(json.load(f).get("tetelek", []))
    except (OSError, ValueError):
        return []


def ment(tetelek, mappa: str = "") -> None:
    os.makedirs(mappa or alap_mappa(), exist_ok=True)
    ut = _ut(mappa)
    ideiglenes = ut + ".uj"
    with open(ideiglenes, "w", encoding="utf-8") as f:
        json.dump({"tetelek": list(tetelek)}, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(ideiglenes, ut)


# ====================================================================
#  Halasztás
# ====================================================================

# felolvasható választékok: (címke, másodperc)
HALASZTASOK = (
    ("Egy óra múlva", 3600),
    ("Ma este 6-kor", -1),                 # külön számoljuk
    ("Holnap reggel 8-kor", -2),
    ("Hétfő reggel 8-kor", -3),
    ("Egy hét múlva", 7 * 86400),
)


def halasztas_ideje(valasztas: int, most: float = 0.0) -> float:
    """A választott halasztás időpontja epoch-ban."""
    most = most or time.time()
    cimke, mp = HALASZTASOK[valasztas]
    if mp > 0:
        return most + mp
    d = datetime.fromtimestamp(most)
    if mp == -1:                                        # ma este 6
        cel = d.replace(hour=18, minute=0, second=0, microsecond=0)
        if cel.timestamp() <= most:                     # már elmúlt: holnap
            cel += timedelta(days=1)
        return cel.timestamp()
    if mp == -2:                                        # holnap reggel 8
        cel = (d + timedelta(days=1)).replace(hour=8, minute=0, second=0,
                                              microsecond=0)
        return cel.timestamp()
    # hétfő reggel 8 (ha ma hétfő, a KÖVETKEZŐ hétfő)
    napok = (7 - d.weekday()) or 7
    cel = (d + timedelta(days=napok)).replace(hour=8, minute=0, second=0,
                                              microsecond=0)
    return cel.timestamp()


def halaszt(azonosito: str, fiok: str, targy: str, felado: str,
            mikor: float, mappa: str = "") -> None:
    tetelek = [t for t in betolt(mappa)
               if not (t.get("fajta") == HALASZT
                       and t.get("azonosito") == azonosito)]
    tetelek.append({"fajta": HALASZT, "azonosito": azonosito, "fiok": fiok,
                    "targy": targy, "felado": felado, "mikor": float(mikor),
                    "letrehozva": time.time()})
    ment(tetelek, mappa)


# ====================================================================
#  „Nem válaszoltak”
# ====================================================================

def valaszt_var(azonosito: str, fiok: str, cimzett: str, targy: str,
                napok: int = 5, mappa: str = "") -> None:
    if not azonosito:
        return
    tetelek = betolt(mappa)
    tetelek.append({"fajta": VALASZ_VARAS, "azonosito": azonosito,
                    "fiok": fiok, "cimzett": cimzett, "targy": targy,
                    "mikor": time.time() + max(1, int(napok)) * 86400,
                    "letrehozva": time.time()})
    ment(tetelek, mappa)


def valasz_erkezett(levelek, mappa: str = "") -> list:
    """Melyik várt levélre jött válasz? A választ a hivatkozásokból ismerjük
    fel (In-Reply-To / References) – ez a szabvány, nem szöveg-találgatás.

    Visszaadja a lezárt (megválaszolt) tételeket."""
    tetelek = betolt(mappa)
    varok = {t["azonosito"]: t for t in tetelek
             if t.get("fajta") == VALASZ_VARAS}
    if not varok:
        return []
    lezart = []
    for info in levelek or []:
        hivatkozas = "%s %s" % (info.get("valasz_erre", ""),
                                info.get("hivatkozasok", ""))
        for azon, t in list(varok.items()):
            if azon and azon in hivatkozas:
                lezart.append(t)
                varok.pop(azon, None)
    if lezart:
        maradek = [t for t in tetelek if t not in lezart]
        ment(maradek, mappa)
    return lezart


# ====================================================================
#  Esedékesség
# ====================================================================

def esedekes(most: float = 0.0, mappa: str = "") -> list:
    most = most or time.time()
    return [t for t in betolt(mappa) if float(t.get("mikor", 0)) <= most]


def levesz(tetel: dict, mappa: str = "") -> None:
    maradek = [t for t in betolt(mappa)
               if not (t.get("fajta") == tetel.get("fajta")
                       and t.get("azonosito") == tetel.get("azonosito"))]
    ment(maradek, mappa)


def tetel_szoveg(t: dict) -> str:
    mikor = datetime.fromtimestamp(float(t.get("mikor", 0)))
    if t.get("fajta") == HALASZT:
        return ("Elhalasztott levél: %s – „%s” – %s"
                % (t.get("felado", ""), t.get("targy", ""),
                   mikor.strftime("%Y. %m. %d. %H:%M")))
    return ("Nem érkezett válasz erre: %s – „%s” (elküldve %s)"
            % (t.get("cimzett", ""), t.get("targy", ""),
               datetime.fromtimestamp(
                   float(t.get("letrehozva", 0))).strftime("%Y. %m. %d.")))


# ====================================================================
#  Dátum a levél szövegében
# ====================================================================

_HONAPOK = {"január": 1, "február": 2, "március": 3, "április": 4,
            "május": 5, "június": 6, "július": 7, "augusztus": 8,
            "szeptember": 9, "október": 10, "november": 11, "december": 12}
_NAPOK = {"hétfő": 0, "kedd": 1, "szerda": 2, "csütörtök": 3, "péntek": 4,
          "szombat": 5, "vasárnap": 6}


def _norm(sz) -> str:
    sz = unicodedata.normalize("NFKD", str(sz or ""))
    return "".join(c for c in sz if not unicodedata.combining(c)).casefold()


def _ora(szoveg: str, honnan: int) -> tuple:
    """Óra:perc a találat KÖRNYÉKÉN (utána legfeljebb 40 karakterrel).

    FIGYELEM: a szöveg itt már ÉKEZET NÉLKÜLI (a `_norm` levette), ezért a
    mintákat is úgy kell írni: „ora”, nem „óra”. A „14-kor” alakot külön
    kezeljük – magyarul ez a leggyakoribb."""
    resz = szoveg[honnan:honnan + 60]
    talalatok = []
    m = re.search(r"(\d{1,2})[:.](\d{2})", resz)
    if m and int(m.group(1)) <= 23 and int(m.group(2)) <= 59:
        talalatok.append((m.start(), int(m.group(1)), int(m.group(2))))
    m = re.search(r"(\d{1,2})\s*-?\s*(?:orakor|ora|kor|h)\b", resz)
    if m and int(m.group(1)) <= 23:
        talalatok.append((m.start(), int(m.group(1)), 0))
    if not talalatok:
        return 9, 0
    # A KÖZELEBBI találat nyer, nem az, amelyik mintát előbb próbáltuk:
    # a „kedden 10-kor, vagy 2026-09-03 14:00” mondatban a keddhez a 10 óra
    # tartozik, nem a távolabbi 14:00.
    talalatok.sort()
    return talalatok[0][1], talalatok[0][2]


def datumok(szoveg: str, ma: date = None) -> list:
    """Időpontok a szövegben: [(datetime, a talált szövegrész)].

    Szándékosan óvatos: csak egyértelmű alakokat ismerünk fel. Egy téves
    naptár-bejegyzés rosszabb, mint egy elmaradt."""
    ma = ma or date.today()
    n = _norm(szoveg)
    ki = []

    # 1) 2026-07-11 / 2026. 07. 11. / 2026.07.11
    for m in re.finditer(r"(\d{4})[.\-/ ]\s*(\d{1,2})[.\-/ ]\s*(\d{1,2})", n):
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        o, p = _ora(n, m.end())
        ki.append((datetime(d.year, d.month, d.day, o, p), m.group(0)))

    # 2) „július 11” (év nélkül: a következő ilyen nap)
    for honap_nev, honap in _HONAPOK.items():
        for m in re.finditer(r"%s\s+(\d{1,2})" % _norm(honap_nev), n):
            nap = int(m.group(1))
            try:
                d = date(ma.year, honap, nap)
            except ValueError:
                continue
            if d < ma:
                d = date(ma.year + 1, honap, nap)
            o, p = _ora(n, m.end())
            ki.append((datetime(d.year, d.month, d.day, o, p), m.group(0)))

    # 3) „kedden”, „jövő kedden” – a következő ilyen nap
    for nap_nev, index in _NAPOK.items():
        for m in re.finditer(r"\b%s\w*" % _norm(nap_nev), n):
            elore = (index - ma.weekday()) % 7 or 7
            d = ma + timedelta(days=elore)
            o, p = _ora(n, m.end())
            ki.append((datetime(d.year, d.month, d.day, o, p), m.group(0)))

    # 4) „holnap”, „holnapután”
    if "holnaputan" in n:
        d = ma + timedelta(days=2)
        o, p = _ora(n, n.index("holnaputan") + 10)
        ki.append((datetime(d.year, d.month, d.day, o, p), "holnapután"))
    elif "holnap" in n:
        d = ma + timedelta(days=1)
        o, p = _ora(n, n.index("holnap") + 6)
        ki.append((datetime(d.year, d.month, d.day, o, p), "holnap"))

    # a legkorábbi elöl, ismétlődés nélkül
    latott, egyedi = set(), []
    for mikor, szo in sorted(ki, key=lambda x: x[0]):
        kulcs = mikor.strftime("%Y%m%d%H%M")
        if kulcs not in latott:
            latott.add(kulcs)
            egyedi.append((mikor, szo))
    return egyedi


def naptarba(mikor: datetime, cim: str, megjegyzes: str = "",
             manager=None) -> str:
    """Esemény a SuperDL naptárába a levélben talált időpontból."""
    try:
        from superdl import organizer
        m = manager or organizer.OrganizerManager()
        e = organizer.Event(
            id=organizer.new_id(), title=cim[:120],
            date=mikor.strftime("%Y-%m-%d"), time=mikor.strftime("%H:%M"),
            note=megjegyzes[:400], reminder_min=30,
            repeat=organizer.REPEAT_NONE,
            action_type=organizer.ACTION_NONE)
        m.add_event(e)
        return e.id
    except Exception:
        return ""
