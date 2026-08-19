# -*- coding: utf-8 -*-
"""Super Mail – TÉRTIVEVÉNY (olvasási visszaigazolás, MDN).

Felhasználói kérés: „tértivevény-kérés lehetősége az e-mail olvasottságáról”.

AMIT ELŐRE KI KELL MONDANI: ez KÉRÉS, nem nyugta. A szabvány (RFC 3798/8098)
szerint a címzett programja megkérdezi a címzettet, hogy küldjön-e
visszajelzést – és ő nemet is mondhat; sok program pedig meg sem kérdezi.
Tehát: ha jön visszajelzés, az BIZTOS jel; ha nem jön, abból NEM következik,
hogy nem olvasták el. A felületen is pontosan ezt írjuk ki.

ADATVÉDELEM: fordítva, amikor MINKET kérnek meg, a program alapból KÉRDEZ, és
soha nem küld a hátunk mögött. Rejtett képpel („tracking pixel") pedig
egyáltalán nem mérünk – az a címzett megfigyelése a tudta nélkül.
"""

from __future__ import annotations

import json
import os
import time
from email.message import EmailMessage
from email.utils import formatdate, parseaddr

FAJL = "tertivevony.json"

# a fogadói oldal beállítása
KERDEZ, MINDIG, SOHA = "kerdez", "mindig", "soha"


def alap_mappa() -> str:
    from superdl import store
    return str(store.CONFIG_DIR)


# ====================================================================
#  Kérés küldéskor
# ====================================================================

def keres_beallit(msg, sajat_cim: str) -> None:
    """A levélbe beleteszi a visszajelzés-kérést."""
    if not sajat_cim:
        return
    if "Disposition-Notification-To" in msg:
        del msg["Disposition-Notification-To"]
    msg["Disposition-Notification-To"] = sajat_cim


def kertunk_e(msg) -> str:
    """Kértek-e TŐLÜNK visszajelzést? Visszaadja a címet, ahova menne."""
    cim = parseaddr(msg.get("Disposition-Notification-To", "") or "")[1]
    return cim or ""


# ====================================================================
#  MDN összeállítása (amit MI küldünk vissza)
# ====================================================================

def mdn_level(eredeti, sajat_cim: str, cimzett: str = "") -> EmailMessage:
    """Szabályos MDN-válasz: multipart/report + message/disposition-notification."""
    cel = cimzett or kertunk_e(eredeti)
    targy = eredeti.get("Subject", "") or "(nincs tárgy)"
    azonosito = (eredeti.get("Message-ID", "") or "").strip()

    uzenet = EmailMessage()
    uzenet["From"] = sajat_cim
    uzenet["To"] = cel
    uzenet["Subject"] = "Olvasási visszaigazolás: %s" % targy
    uzenet["Date"] = formatdate(localtime=True)
    if azonosito:
        uzenet["In-Reply-To"] = azonosito
        uzenet["References"] = azonosito
    uzenet["Auto-Submitted"] = "auto-replied"    # ne induljon körlevél-lavina

    uzenet.set_content(
        "Ez egy automatikus visszaigazolás.\n\n"
        "A(z) „%s” tárgyú levelet megjelenítette a címzett (%s).\n\n"
        "Figyelem: ez csak azt jelenti, hogy a levelet megnyitották – azt nem, "
        "hogy el is olvasták.\n\nSuper Mail\n" % (targy, sajat_cim))
    uzenet.make_mixed()
    uzenet.set_param("report-type", "disposition-notification",
                     header="Content-Type")
    # A gépi rész: ezt olvassa a küldő programja.
    ertesito = ("Reporting-UA: Super Mail\r\n"
                "Final-Recipient: rfc822;%s\r\n" % sajat_cim)
    if azonosito:
        ertesito += "Original-Message-ID: %s\r\n" % azonosito
    ertesito += "Disposition: manual-action/MDN-sent-manually; displayed\r\n"
    uzenet.add_attachment(ertesito.encode("utf-8"),
                          maintype="message",
                          subtype="disposition-notification")
    return uzenet


# ====================================================================
#  Beérkező MDN felismerése
# ====================================================================

def mdn_e(msg) -> bool:
    """Ez a levél maga egy olvasási visszaigazolás?"""
    tipus = (msg.get_content_type() or "").lower()
    if tipus == "multipart/report":
        fajta = (msg.get_param("report-type", "") or "").lower()
        if fajta == "disposition-notification":
            return True
    if msg.is_multipart():
        for r in msg.walk():
            if (r.get_content_type() or "").lower() == \
                    "message/disposition-notification":
                return True
    return False


def mdn_eredeti_azonosito(msg) -> str:
    """Melyik LEVELÜNKRE vonatkozik a visszaigazolás?"""
    if not msg.is_multipart():
        return ""
    for r in msg.walk():
        if (r.get_content_type() or "").lower() != \
                "message/disposition-notification":
            continue
        toltet = r.get_payload(decode=True)
        szoveg = (toltet.decode("utf-8", "replace") if toltet
                  else str(r.get_payload()))
        for sor in szoveg.splitlines():
            if sor.lower().startswith("original-message-id:"):
                return sor.split(":", 1)[1].strip()
    # tartalék: a válasz-fejlécből
    return (msg.get("In-Reply-To", "") or "").strip()


# ====================================================================
#  Nyilvántartás
# ====================================================================

def _ut(mappa: str) -> str:
    return os.path.join(mappa or alap_mappa(), FAJL)


def betolt(mappa: str = "") -> dict:
    try:
        with open(_ut(mappa), encoding="utf-8") as f:
            return dict(json.load(f))
    except (OSError, ValueError):
        return {}


def _ment(adat: dict, mappa: str = "") -> None:
    os.makedirs(mappa or alap_mappa(), exist_ok=True)
    ut = _ut(mappa)
    ideiglenes = ut + ".uj"
    with open(ideiglenes, "w", encoding="utf-8") as f:
        json.dump(adat, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(ideiglenes, ut)


def kerest_rogzit(azonosito: str, cimzett: str, targy: str,
                  mappa: str = "") -> None:
    """Elküldtünk egy levelet visszajelzés-kéréssel."""
    if not azonosito:
        return
    adat = betolt(mappa)
    adat[azonosito] = {"cimzett": cimzett, "targy": targy,
                       "kuldve": time.time(), "megjott": 0.0}
    _ment(adat, mappa)


def megjott(azonosito: str, mikor: float = 0.0, mappa: str = "") -> bool:
    """Megérkezett a visszaigazolás. Igaz, ha tényleg a mi kérésünkre jött."""
    if not azonosito:
        return False
    adat = betolt(mappa)
    tetel = adat.get(azonosito)
    if tetel is None:
        return False
    tetel["megjott"] = mikor or time.time()
    _ment(adat, mappa)
    return True


def allapot(azonosito: str, mappa: str = "") -> str:
    """Felolvasható állapot egy elküldött levélről."""
    tetel = betolt(mappa).get(azonosito or "")
    if not tetel:
        return ""
    if tetel.get("megjott"):
        mikor = time.strftime("%Y. %m. %d. %H:%M",
                              time.localtime(tetel["megjott"]))
        return "Visszaigazolva: %s" % mikor
    return "Visszaigazolás kérve – még nem érkezett meg"


def osszesito(mappa: str = "") -> list:
    """A kért visszajelzések listája, felolvasható mondatokban."""
    ki = []
    for azon, t in sorted(betolt(mappa).items(),
                          key=lambda x: -float(x[1].get("kuldve", 0))):
        kuldve = time.strftime("%Y. %m. %d. %H:%M",
                               time.localtime(t.get("kuldve", 0)))
        if t.get("megjott"):
            allapot_sz = "MEGNYITOTTA: " + time.strftime(
                "%Y. %m. %d. %H:%M", time.localtime(t["megjott"]))
        else:
            allapot_sz = "még nincs visszajelzés"
        ki.append("%s – „%s” – elküldve: %s – %s"
                  % (t.get("cimzett", ""), t.get("targy", ""), kuldve,
                     allapot_sz))
    return ki


FIGYELMEZTETES = (
    "Fontos: a visszajelzés KÉRÉS, nem nyugta. A címzett programja megkérdezi "
    "őt, és ő nemet is mondhat; sok program meg sem kérdezi. Ha megjön, az "
    "biztos jel – ha nem jön meg, abból nem következik, hogy nem olvasta el.")
