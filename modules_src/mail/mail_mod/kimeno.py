# -*- coding: utf-8 -*-
"""Super Mail – KIMENŐ: küldés visszavonása, időzített és évente ismétlődő levél.

Felhasználói kérések (2026-08-19):
  • „e-mail visszahívás téves vagy meggondolt címzett esetén”
  • „az időzített e-mail-küldés nagyon tetszik… a naptárral is lehetne
     szinkronizálni, hogy például július 11. napján küldjön ide egy levelet…
     születésnapi e-mailek satöbbi”

AMIT ŐSZINTÉN TUDNI KELL: elküldött levelet VISSZAHÍVNI nem lehet. Amit a
Gmail „küldés visszavonása" néven ismer, az valójában ez: a levél néhány
másodpercig még NÁLUNK vár, és csak utána megy el. Ez a modul ezt csinálja –
és ugyanezt a várakoztatást használja az időzített küldésre is.

MIÉRT LEMEZRE MENTVE? Mert a várakozó levél nem veszhet el áramszünetkor vagy
egy összeomláskor. A levél a `kimeno/<azonosító>.eml` fájlban ül, a hozzá
tartozó adatok a `kimeno.json`-ban.

AZ ÉVENTE ISMÉTLŐDŐ LEVÉL biztonsági fékkel jár: a küldés előtti napon a
program RÁKÉRDEZ. Egy év alatt sok minden történhet – ne menjen el gépiesen
egy köszöntő oda, ahova már nem való.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import date, datetime

ISM_NINCS = "nincs"
ISM_EVENTE = "evente"

FAJL = "kimeno.json"
MAPPA_NEV = "kimeno"

# a küldés-visszavonás alap-ideje másodpercben (0 = azonnali küldés)
ALAP_VISSZAVONAS = 10
VALASZTHATO_VISSZAVONAS = (0, 5, 10, 30, 60)


def alap_mappa() -> str:
    from superdl import store
    return os.path.join(str(store.CONFIG_DIR), MAPPA_NEV)


def _adatfajl(mappa: str) -> str:
    return os.path.join(mappa, FAJL)


def _level_ut(mappa: str, azon: str) -> str:
    return os.path.join(mappa, azon + ".eml")


# ====================================================================
#  Tár
# ====================================================================

def tetelek(mappa: str = "") -> list:
    mappa = mappa or alap_mappa()
    try:
        with open(_adatfajl(mappa), encoding="utf-8") as f:
            return list(json.load(f).get("tetelek", []))
    except (OSError, ValueError):
        return []


def _ment(mappa: str, tetelek_lista) -> None:
    os.makedirs(mappa, exist_ok=True)
    ut = _adatfajl(mappa)
    ideiglenes = ut + ".uj"
    with open(ideiglenes, "w", encoding="utf-8") as f:
        json.dump({"tetelek": list(tetelek_lista)}, f, ensure_ascii=False,
                  indent=2)
        f.flush()
        os.fsync(f.fileno())          # áramszünet: a levél ne tűnjön el
    os.replace(ideiglenes, ut)


def betesz(fiok_email: str, msg, mikor: float, ismetles: str = ISM_NINCS,
           cimzett: str = "", targy: str = "", mappa: str = "") -> str:
    """Levél a kimenőbe. `mikor`: epoch másodperc (mikor menjen el)."""
    mappa = mappa or alap_mappa()
    os.makedirs(mappa, exist_ok=True)
    azon = uuid.uuid4().hex[:12]
    with open(_level_ut(mappa, azon), "wb") as f:
        f.write(msg.as_bytes())
        f.flush()
        os.fsync(f.fileno())
    sor = {"id": azon, "fiok": fiok_email, "mikor": float(mikor),
           "ismetles": ismetles if ismetles in (ISM_NINCS, ISM_EVENTE)
                       else ISM_NINCS,
           "cimzett": cimzett, "targy": targy,
           "letrehozva": time.time(), "kerdezve_ev": 0, "naptar_id": ""}
    _ment(mappa, tetelek(mappa) + [sor])
    return azon


def uzenet(azon: str, mappa: str = ""):
    """A tárolt levél visszaolvasva (email.message.EmailMessage)."""
    import email
    from email.policy import default as _alap
    mappa = mappa or alap_mappa()
    with open(_level_ut(mappa, azon), "rb") as f:
        return email.message_from_binary_file(f, policy=_alap)


def torol(azon: str, mappa: str = "") -> dict:
    """Kivesz egy tételt (és törli a levél fájlját). Visszaadja a tételt."""
    mappa = mappa or alap_mappa()
    maradek, kivett = [], {}
    for sor in tetelek(mappa):
        if sor.get("id") == azon:
            kivett = sor
        else:
            maradek.append(sor)
    _ment(mappa, maradek)
    try:
        os.remove(_level_ut(mappa, azon))
    except OSError:
        pass
    return kivett


def frissit(azon: str, **mezok) -> None:
    mappa = mezok.pop("mappa", "") or alap_mappa()
    sorok = tetelek(mappa)
    for sor in sorok:
        if sor.get("id") == azon:
            sor.update(mezok)
    _ment(mappa, sorok)


# ====================================================================
#  Időzítés
# ====================================================================

def esedekes(most: float = 0.0, mappa: str = "") -> list:
    """Amiknek MOST kell elmenniük."""
    most = most or time.time()
    return [s for s in tetelek(mappa) if float(s.get("mikor", 0)) <= most]


def varakozo(most: float = 0.0, mappa: str = "") -> list:
    """Amik még várnak (a visszavonható levelek is ilyenek)."""
    most = most or time.time()
    return [s for s in tetelek(mappa) if float(s.get("mikor", 0)) > most]


def hatra_van(sor: dict, most: float = 0.0) -> int:
    """Hány másodperc múlva megy el? (Felolvasáshoz.)"""
    most = most or time.time()
    return max(0, int(round(float(sor.get("mikor", 0)) - most)))


def kovetkezo_ev(mikor: float) -> float:
    """Ugyanaz a nap és óra a KÖVETKEZŐ évben.

    A február 29. a szökőév nélküli években február 28-ra kerül – így a levél
    nem marad el négy évig."""
    d = datetime.fromtimestamp(mikor)
    ev = d.year + 1
    nap = d.day
    if d.month == 2 and d.day == 29 and not _szokoev(ev):
        nap = 28
    return d.replace(year=ev, day=nap).timestamp()


def _szokoev(ev: int) -> bool:
    return ev % 4 == 0 and (ev % 100 != 0 or ev % 400 == 0)


def kerdezni_kell(sor: dict, most: float = 0.0) -> bool:
    """Évente ismétlődő levélnél a küldés előtti napon rákérdezünk – de egy
    évben csak EGYSZER."""
    if sor.get("ismetles") != ISM_EVENTE:
        return False
    most = most or time.time()
    hatra = float(sor.get("mikor", 0)) - most
    if not 0 < hatra <= 24 * 3600:
        return False
    return int(sor.get("kerdezve_ev", 0)) != date.fromtimestamp(most).year


def megkerdezve(azon: str, most: float = 0.0, mappa: str = "") -> None:
    most = most or time.time()
    frissit(azon, kerdezve_ev=date.fromtimestamp(most).year,
            mappa=mappa or alap_mappa())


# ====================================================================
#  Felolvasható szövegek
# ====================================================================

def ido_szoveg(mp: int) -> str:
    if mp <= 0:
        return "most"
    if mp < 60:
        return "%d másodperc múlva" % mp
    if mp < 3600:
        return "%d perc múlva" % round(mp / 60)
    if mp < 48 * 3600:
        return "%d óra múlva" % round(mp / 3600)
    return "%d nap múlva" % round(mp / 86400)


def tetel_szoveg(sor: dict, most: float = 0.0) -> str:
    """Egy kimenő tétel egy mondatban – ezt olvassa fel a képernyőolvasó."""
    mikor = datetime.fromtimestamp(float(sor.get("mikor", 0)))
    ism = " (évente ismétlődik)" if sor.get("ismetles") == ISM_EVENTE else ""
    return ("%s – „%s” – %s, azaz %s%s"
            % (sor.get("cimzett", "") or "(nincs címzett)",
               sor.get("targy", "") or "(nincs tárgy)",
               mikor.strftime("%Y. %m. %d. %H:%M"),
               ido_szoveg(hatra_van(sor, most)), ism))


# ====================================================================
#  Naptár-kapcsolat
# ====================================================================

def naptarba(sor: dict, manager=None) -> str:
    """A várakozó levelet ESEMÉNYKÉNT is felveszi a SuperDL naptárába, hogy ott
    is látszódjon és felolvasható legyen.

    Az ISMÉTLŐDÉST MI kezeljük (a naptár ma napi/heti ismétlést tud, évest nem),
    ezért mindig a KÖVETKEZŐ alkalmat vesszük fel, és küldés után újat."""
    try:
        from superdl import organizer
    except Exception:
        return ""
    try:
        m = manager or organizer.OrganizerManager()
        mikor = datetime.fromtimestamp(float(sor.get("mikor", 0)))
        e = organizer.Event(
            id=organizer.new_id(),
            title="Levél megy: %s – %s" % (sor.get("cimzett", ""),
                                           sor.get("targy", "")),
            date=mikor.strftime("%Y-%m-%d"),
            time=mikor.strftime("%H:%M"),
            note="A Super Mail időzített levele.",
            reminder_min=-1,                   # a levél magától megy: ne szóljon
            repeat=organizer.REPEAT_NONE,
            action_type=organizer.ACTION_NONE)
        m.add_event(e)
        return e.id
    except Exception:
        return ""


def naptarbol_torol(esemeny_id: str, manager=None) -> None:
    if not esemeny_id:
        return
    try:
        from superdl import organizer
        (manager or organizer.OrganizerManager()).remove_event(esemeny_id)
    except Exception:
        pass
