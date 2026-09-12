# -*- coding: utf-8 -*-
"""Super Mail – AUTOMATA VÁLASZ.

Felhasználói kérés (2026-09-05): „a szabályokhoz hozzá lehessen egy olyat adni:
automata válasz! az automata válasz egy általad megírt levelet küld annak, akit
ezzel a szabállyal vettél fel.”

Ez a fájl SZÁNDÉKOSAN wx- és hálózat-mentes: csak adat és logika, hogy ablak és
kapcsolat nélkül, gyorsan tesztelhető legyen. A tényleges küldést a `mailwin`
végzi – a MEGLÉVŐ kimenő soron át, hogy az automata válasz is visszavonható
legyen, ott legyen az Elküldött mappában, és ugyanúgy naplózódjon, mint bármi,
amit a felhasználó maga küld.

HÁROM DOLOG, AMI ITT NEM KÉNYELMI KÉRDÉS, HANEM ALAPKÖVETELMÉNY
---------------------------------------------------------------
1. **Retesz.** Egy automata válasz, ami minden levélre elmegy, két gép között
   végtelen levélváltásba fordul. Ezért címenként NAPONTA EGYSZER megy válasz
   (`mehet`), és a küldés naplózódik.
2. **Tiltólista.** Levelezőlistára válaszolni annyi, mint a lista minden
   tagjának írni; a `noreply@` címre küldött válasz a semmibe megy; egy
   kézbesítési hibaüzenetre válaszolni pedig egyenesen kártékony. Ezeket a
   `tiltott()` ismeri fel, és a hívó SOHA nem hagyhatja figyelmen kívül.
3. **Nyilvánosság.** Az automata válasz `Auto-Submitted: auto-replied`
   fejlécet visel – ezzel mondja meg a másik oldal programjának, hogy ez gép
   volt, ne válaszoljon rá. Ez az udvariasság védi meg mindkét felet.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime

FAJL = "autovalasz-naplo.json"

# Egy címre ennyi időn belül csak EGY automata válasz megy.
RETESZ_MP = 24 * 3600

# A napló ennél régebbi sorait eldobjuk – nincs értelme örökké őrizni.
NAPLO_MEGORZES_MP = 30 * 24 * 3600

# A „ne válaszolj nekem" címek. Nem szó-kitalálás: ezek bevett, szabványos
# alakok, amiket a küldő RENDSZEREK használnak.
_NEMVALASZOLHATO = ("noreply", "no-reply", "no_reply", "donotreply",
                    "do-not-reply", "do_not_reply", "nereply", "nincsvalasz",
                    "mailer-daemon", "mailerdaemon", "postmaster",
                    "bounce", "bounces", "notifications", "notification")


# ====================================================================
#  Behelyettesíthető helyek
# ====================================================================

# A felhasználó ezeket írhatja a szövegbe. SZÁNDÉKOSAN kevés van belőlük:
# minden további egy újabb dolog, amit meg kell jegyezni.
HELYEK = [
    ("[feladó]", "a feladó neve (ha nincs, a címe)"),
    ("[cím]", "a feladó e-mail címe"),
    ("[tárgy]", "az eredeti levél tárgya"),
    ("[dátum]", "a mai dátum"),
    ("[idő]", "a pontos idő"),
]

_HONAPOK = ("január", "február", "március", "április", "május", "június",
            "július", "augusztus", "szeptember", "október", "november",
            "december")


def cim_resz(felado: str) -> str:
    """A „Név <cim@domain.hu>" alakból a puszta cím."""
    sz = str(felado or "")
    if "<" in sz and ">" in sz:
        sz = sz[sz.index("<") + 1:sz.index(">")]
    return sz.strip()


def nev_resz(felado: str) -> str:
    """A megjelenítendő NÉV a feladó fejlécből; ha nincs, a cím."""
    sz = str(felado or "").strip()
    if "<" in sz:
        nev = sz[:sz.index("<")].strip().strip('"').strip()
        if nev:
            return nev
    return cim_resz(sz) or sz


def behelyettesit(szoveg: str, info: dict, most: float = 0.0) -> str:
    """A helykitöltők kitöltése.

    Amit ELGÉPELSZ, az megmarad úgy, ahogy beírtad – nem nyeljük el némán.
    Egy eltűnő mondatrész vakon sokkal rosszabb, mint egy látható hiba."""
    d = datetime.fromtimestamp(most or time.time())
    csere = {
        "[feladó]": nev_resz(info.get("felado", "")),
        "[cím]": cim_resz(info.get("felado", "")),
        "[tárgy]": str(info.get("targy", "") or ""),
        "[dátum]": "%d. %s %d." % (d.year, _HONAPOK[d.month - 1], d.day),
        "[idő]": "%d óra %d perc" % (d.hour, d.minute),
    }
    ki = str(szoveg or "")
    for mit, mire in csere.items():
        ki = ki.replace(mit, mire)
    return ki


# ====================================================================
#  Tiltás – akinek SOHA nem megy automata válasz
# ====================================================================

def tiltott(info: dict, sajat_cim: str = "") -> str:
    """Miért NEM szabad erre a levélre automata választ küldeni?

    Üres szöveg = mehet. Különben egy felolvasható magyar mondat az okkal –
    ez kerül a naplóba is, hogy utólag meg lehessen érteni, mi történt."""
    cim = cim_resz(info.get("felado", ""))
    if not cim or "@" not in cim:
        return "nincs értelmes feladó-cím"

    # SAJÁT MAGADNAK sosem válaszolunk – az azonnali végtelen kör.
    if sajat_cim and cim.strip().lower() == str(sajat_cim).strip().lower():
        return "a levél a saját címedről jött"

    if info.get("lista_id"):
        return ("levelezőlistáról jött – a válasz a lista MINDEN tagjához "
                "menne")
    if info.get("marketing") or info.get("leiratkozas"):
        return "hírlevél vagy reklám"

    if str(info.get("precedence", "")).strip().lower() in (
            "bulk", "list", "junk", "auto_reply"):
        return "tömeges küldeményként jelölt levél"

    auto = str(info.get("auto_submitted", "")).strip().lower()
    if auto and auto != "no":
        return "maga is automata levél"

    # Kézbesítési hibaüzenet: a szabvány szerint ÜRES a visszaút.
    vissza = str(info.get("vissza_ut", "")).strip()
    if vissza in ("<>", "<MAILER-DAEMON>", "<mailer-daemon>"):
        return "kézbesítési hibaüzenet"

    helyi = cim.split("@")[0].strip().lower()
    helyi_szoveg = re.sub(r"[^a-z]", "", helyi)
    for minta in _NEMVALASZOLHATO:
        tiszta = minta.replace("-", "").replace("_", "")
        if helyi_szoveg == tiszta or helyi.startswith(minta):
            return "olyan cím, amelyik nem fogad választ (%s)" % helyi
    return ""


# ====================================================================
#  Napló és a 24 órás retesz
# ====================================================================

def alap_mappa() -> str:
    from superdl import store
    return str(store.CONFIG_DIR)


def _utvonal(mappa: str = "") -> str:
    return os.path.join(mappa or alap_mappa(), FAJL)


def naplo_betolt(mappa: str = "") -> list:
    try:
        with open(_utvonal(mappa), encoding="utf-8") as f:
            adat = json.load(f)
    except (OSError, ValueError):
        return []
    return list(adat.get("tetelek", []))


def naplo_ment(tetelek, mappa: str = "") -> None:
    mappa = mappa or alap_mappa()
    os.makedirs(mappa, exist_ok=True)
    ut = _utvonal(mappa)
    ideiglenes = ut + ".uj"
    with open(ideiglenes, "w", encoding="utf-8") as f:
        json.dump({"tetelek": list(tetelek)}, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(ideiglenes, ut)


def _rendez(tetelek, most: float) -> list:
    """A nagyon régi sorok eldobása – a napló ne hízzon a végtelenségig."""
    hatar = most - NAPLO_MEGORZES_MP
    return [t for t in tetelek if float(t.get("mikor", 0)) >= hatar]


def mehet(cim: str, mappa: str = "", most: float = 0.0,
          retesz: float = RETESZ_MP) -> bool:
    """Küldhető-e MOST automata válasz erre a címre?

    Címenként naponta egy: ha ugyanaz a feladó napon belül tízszer ír, egy
    választ kap. Ez az ipari szokás, és ez akadályozza meg, hogy két automata
    program egymást válaszolgassa végtelenségig."""
    most = most or time.time()
    cim = (cim or "").strip().lower()
    if not cim:
        return False
    for t in naplo_betolt(mappa):
        if str(t.get("cim", "")).strip().lower() != cim:
            continue
        if most - float(t.get("mikor", 0)) < retesz:
            return False
    return True


def rogzit(cim: str, targy: str = "", szabaly: str = "", mappa: str = "",
           most: float = 0.0) -> None:
    """A most elküldött automata válasz bejegyzése a naplóba."""
    most = most or time.time()
    tetelek = _rendez(naplo_betolt(mappa), most)
    tetelek.append({"cim": (cim or "").strip(),
                    "targy": str(targy or ""),
                    "szabaly": str(szabaly or ""),
                    "mikor": float(most)})
    naplo_ment(tetelek, mappa)


def utolso_szoveg(cim: str, mappa: str = "", most: float = 0.0) -> str:
    """„Ennek a címnek ma már ment válasz” – felolvasható alakban."""
    most = most or time.time()
    cim = (cim or "").strip().lower()
    legutobb = 0.0
    for t in naplo_betolt(mappa):
        if str(t.get("cim", "")).strip().lower() == cim:
            legutobb = max(legutobb, float(t.get("mikor", 0)))
    if not legutobb:
        return ""
    ora = int((most - legutobb) // 3600)
    if ora < 1:
        return "ennek a címnek az elmúlt órában már ment automata válasz"
    return ("ennek a címnek %d órája ment automata válasz" % ora)


# ====================================================================
#  A válasz tárgya és szövege
# ====================================================================

def valasz_targy(eredeti_targy: str, sajat_targy: str = "") -> str:
    """A válasz tárgya. Üres saját tárgynál a szokásos „Re: eredeti”.

    A „Re:” nem duplázódik: ha az eredeti már válasz volt, nem lesz belőle
    „Re: Re: Re:”, ami felolvasva kifejezetten fárasztó."""
    sajat = str(sajat_targy or "").strip()
    if sajat:
        return sajat
    t = str(eredeti_targy or "").strip() or "(nincs tárgy)"
    if t[:3].lower() == "re:":
        return t
    return "Re: " + t


def elokeszit(info: dict, szoveg: str, sajat_targy: str = "",
              sajat_cim: str = "", mappa: str = "", most: float = 0.0) -> dict:
    """Minden, ami a küldéshez kell – vagy az ok, amiért nem megy.

    Visszaad egy szótárat:
      {"mehet": True/False, "ok": "...", "cimzett": "...", "targy": "...",
       "torzs": "...", "valasz_id": "..."}

    A hívó (mailwin) ebből épít levelet és teszi a kimenőbe. Azért van külön
    ez a lépés, hogy a szabály PRÓBA gombja pontosan ugyanezt tudja
    megmutatni – küldés nélkül."""
    most = most or time.time()
    szoveg = str(szoveg or "").strip()
    cim = cim_resz(info.get("felado", ""))
    alap = {"mehet": False, "ok": "", "cimzett": cim,
            "targy": valasz_targy(info.get("targy", ""), sajat_targy),
            "torzs": "", "valasz_id": (info.get("azonosito") or "").strip()}

    if not szoveg:
        alap["ok"] = "ehhez a szabályhoz nincs megírva az automata válasz szövege"
        return alap
    tilt = tiltott(info, sajat_cim)
    if tilt:
        alap["ok"] = tilt
        return alap
    if not mehet(cim, mappa, most):
        alap["ok"] = utolso_szoveg(cim, mappa, most) or \
            "ennek a címnek a közelmúltban már ment automata válasz"
        return alap

    alap["torzs"] = behelyettesit(szoveg, info, most)
    alap["mehet"] = True
    return alap


def proba_szoveg(eredmeny: dict) -> str:
    """A PRÓBA gomb felolvasható mondata – mi menne el, kinek?"""
    if eredmeny.get("mehet"):
        return ("Automata válasz menne %s címre, „%s” tárggyal. A szöveg: %s"
                % (eredmeny.get("cimzett", ""), eredmeny.get("targy", ""),
                   eredmeny.get("torzs", "")))
    return ("Erre a levélre NEM menne automata válasz: %s."
            % (eredmeny.get("ok") or "ismeretlen ok"))
