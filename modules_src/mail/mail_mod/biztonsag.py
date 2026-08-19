# -*- coding: utf-8 -*-
"""Super Mail – BIZTONSÁG: adathalászat-figyelmeztetés, veszélyes csatolmány,
egygombos leiratkozás.

MIÉRT KELL EZ KÜLÖN VAKOKNAK? Egy látó ember fél másodperc alatt kiszúrja, hogy
a „Magyar Posta” nevű levél valójában a `posta-hu.xyz` címről jött, mert LÁTJA
egymás mellett a nevet és a címet. Vakon ez a két adat időben egymás után,
külön mondatban hangzik el – és a link célja végképp nem derül ki, amíg meg nem
nyitja. Ezért itt a program KIMONDJA, amit a szem amúgy észrevenne.

Amit NEM csinálunk: nem minősítünk levelet „spamnek”, nem küldünk semmit
sehova elemzésre, és nem tiltunk meg semmit. Figyelmeztetünk – a döntés a
felhasználóé.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import unquote

# Futtatható és makrós kiterjesztések. Ezek megnyitása közvetlenül kódot
# futtat – levélben érkezve szinte mindig kártékonyak.
VESZELYES_KITERJESZTESEK = {
    ".exe", ".scr", ".com", ".pif", ".bat", ".cmd", ".ps1", ".vbs", ".vbe",
    ".js", ".jse", ".wsf", ".wsh", ".hta", ".msi", ".msp", ".jar", ".reg",
    ".lnk", ".cpl", ".dll", ".iso", ".img", ".docm", ".xlsm", ".pptm",
    ".dotm", ".xlam", ".ade", ".adp", ".chm", ".application",
}

# Gyakran utánzott, „hivatalos" nevek. Ha ilyen néven jön a levél, de a cím
# nem a valódi domainhez tartozik, az nagyon gyanús.
ISMERT_NEVEK = {
    "magyar posta": ("posta.hu",),
    "posta": ("posta.hu",),
    "nav": ("nav.gov.hu",),
    "otp": ("otpbank.hu",),
    "otp bank": ("otpbank.hu",),
    "k&h": ("kh.hu",),
    "erste": ("erstebank.hu",),
    "mbh": ("mbhbank.hu",),
    "raiffeisen": ("raiffeisen.hu",),
    "unicredit": ("unicreditbank.hu",),
    "revolut": ("revolut.com",),
    "paypal": ("paypal.com",),
    "google": ("google.com", "googlemail.com", "gmail.com"),
    "microsoft": ("microsoft.com", "outlook.com", "live.com"),
    "apple": ("apple.com", "icloud.com"),
    "facebook": ("facebook.com", "facebookmail.com"),
    "netflix": ("netflix.com"),
    "mvm": ("mvm.hu",),
    "telekom": ("telekom.hu",),
    "vodafone": ("vodafone.hu",),
    "foxpost": ("foxpost.hu",),
    "gls": ("gls-hungary.com", "gls-group.eu"),
    "dpd": ("dpd.hu",),
}

# Karakterek, amikkel latin betűket szoktak utánozni (0 az O helyén stb.)
HASONLO = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s",
                         "7": "t", "8": "b", "|": "l"})

JELSZO_SZAVAK = ("jelszó", "jelszo", "password", "pin kód", "pin-kód",
                 "kártyaszám", "kartyaszam", "bankkártya", "bankkartya",
                 "cvc", "cvv", "azonosítás", "azonositas", "belépési adat",
                 "belepesi adat", "adategyeztet", "számlaszám", "szamlaszam")

SURGETO_SZAVAK = ("azonnal", "24 órán belül", "24 oran belul", "lejár",
                  "lejar", "felfüggesztjük", "felfuggesztjuk", "zárolva",
                  "zarolva", "utolsó figyelmeztetés", "utolso figyelmeztetes")


# ====================================================================
#  Segédek
# ====================================================================

def _norm(sz) -> str:
    sz = unicodedata.normalize("NFKD", str(sz or ""))
    return "".join(c for c in sz if not unicodedata.combining(c)).casefold()


def cim_resz(felado: str) -> str:
    sz = str(felado or "")
    if "<" in sz and ">" in sz:
        sz = sz[sz.index("<") + 1:sz.index(">")]
    return sz.strip()


def nev_resz(felado: str) -> str:
    sz = str(felado or "").strip()
    if "<" in sz:
        sz = sz[:sz.index("<")]
    return sz.strip().strip('"').strip()


def domain_resz(cim: str) -> str:
    cim = cim_resz(cim)
    return cim.split("@")[-1].strip().lower() if "@" in cim else ""


def _fodomain(dom: str) -> str:
    """A domain „lényegi" része: a levelezes.posta.hu-ból posta.hu.

    Kétszintű végződéseket (co.uk, gov.hu) is kezel, hogy a nav.gov.hu ne
    „gov.hu"-ra rövidüljön."""
    reszek = [r for r in str(dom or "").lower().split(".") if r]
    if len(reszek) <= 2:
        return ".".join(reszek)
    ketszintu = {"co.uk", "gov.hu", "org.hu", "com.au", "co.jp", "com.br"}
    if ".".join(reszek[-2:]) in ketszintu and len(reszek) >= 3:
        return ".".join(reszek[-3:])
    return ".".join(reszek[-2:])


# ====================================================================
#  Feladó-ellenőrzés
# ====================================================================

def felado_gyanus(info: dict) -> list:
    """Figyelmeztetések a feladóról – felolvasható mondatokban."""
    felado = info.get("felado", "")
    nev, cim = nev_resz(felado), cim_resz(felado)
    dom = domain_resz(cim)
    fo = _fodomain(dom)
    ki = []

    if not cim:
        return ki

    # 1) A megjelenített NÉV maga egy e-mail cím, de nem az igazi
    nev_cim = re.search(r"[\w.+-]+@[\w.-]+\.\w+", nev or "")
    if nev_cim and _norm(nev_cim.group(0)) != _norm(cim):
        ki.append("A feladó neve egy másik e-mail címet mutat (%s), mint "
                  "ahonnan a levél valójában jött (%s)."
                  % (nev_cim.group(0), cim))

    # 2) Ismert cég nevében, de idegen címről
    nev_n = _norm(nev)
    for ismert, domainek in ISMERT_NEVEK.items():
        if ismert and ismert in nev_n:
            domainek = (domainek,) if isinstance(domainek, str) else domainek
            if fo and not any(fo == d or fo.endswith("." + d)
                              for d in domainek):
                ki.append("A levél a(z) %s nevében érkezett, de a feladó címe "
                          "%s – ez nem a hivatalos címük."
                          % (nev.strip() or ismert, cim))
            break

    # 3) Megtévesztően hasonló domain (0 az O helyén, ékezetes/punycode)
    if dom.startswith("xn--") or ".xn--" in dom:
        ki.append("A feladó címe rejtett, nem latin betűs karaktereket "
                  "tartalmaz – ez a megtévesztés egyik gyakori módja.")
    else:
        atirt = fo.translate(HASONLO)
        if atirt != fo:
            for domainek in ISMERT_NEVEK.values():
                domainek = (domainek,) if isinstance(domainek, str) else domainek
                if atirt in domainek:
                    ki.append("A feladó címe megtévesztően hasonlít erre: %s – "
                              "de nem az. A valódi cím: %s" % (atirt, cim))
                    break

    # 4) A válaszcím máshova megy, mint ahonnan jött
    valasz = cim_resz(info.get("valaszcim", ""))
    if valasz and _fodomain(domain_resz(valasz)) and fo:
        if _fodomain(domain_resz(valasz)) != fo:
            ki.append("Ha válaszolsz, a válasz nem a feladónak megy, hanem "
                      "ide: %s" % valasz)
    return ki


def tartalom_gyanus(targy: str, torzs: str) -> list:
    """Klasszikus adathalász-jegyek a szövegben (jelszókérés + sürgetés)."""
    egyben = _norm("%s\n%s" % (targy or "", torzs or ""))
    ki = []
    talalt = [sz for sz in JELSZO_SZAVAK if _norm(sz) in egyben]
    if talalt:
        surget = [sz for sz in SURGETO_SZAVAK if _norm(sz) in egyben]
        if surget:
            ki.append("Ez a levél bizalmas adatot kér (%s), és sürget is – "
                      "az adathalász levelek pontosan így néznek ki. Igazi "
                      "bank vagy hivatal SOHA nem kér jelszót levélben."
                      % talalt[0])
    return ki


# ====================================================================
#  Linkek
# ====================================================================

_LINK = re.compile(r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                   re.IGNORECASE | re.DOTALL)
_CIMKE = re.compile(r"<[^>]+>")


def link_gyanus(html: str) -> list:
    """Olyan hivatkozások, ahol a LÁTHATÓ szöveg mást ígér, mint a cél."""
    ki = []
    for cel, szoveg in _LINK.findall(html or ""):
        latszik = unquote(_CIMKE.sub("", szoveg or "")).strip()
        if not latszik:
            continue
        # a látható szöveg maga is webcím?
        m = re.search(r"(?:https?://)?([\w.-]+\.\w{2,})", latszik)
        if not m:
            continue
        latszo_dom = _fodomain(m.group(1))
        cel_dom = _fodomain(re.sub(r"^https?://", "", cel).split("/")[0])
        if latszo_dom and cel_dom and latszo_dom != cel_dom:
            ki.append("Az egyik hivatkozás %s néven szerepel, de valójában "
                      "ide visz: %s" % (latszo_dom, cel_dom))
    return ki


def link_celja(url: str) -> str:
    """Egy hivatkozás céljának FELOLVASHATÓ leírása (megnyitás előtt)."""
    tiszta = re.sub(r"^https?://", "", str(url or "")).split("/")[0]
    return "Ez a hivatkozás ide visz: %s" % (tiszta or url)


# ====================================================================
#  Csatolmányok
# ====================================================================

def veszelyes_csatolmanyok(nevek) -> list:
    """A futtatható/makrós csatolmányok nevei."""
    ki = []
    for nev in nevek or []:
        n = str(nev or "").strip().lower()
        for kit in VESZELYES_KITERJESZTESEK:
            if n.endswith(kit):
                ki.append(nev)
                break
        else:
            # dupla kiterjesztés: „szamla.pdf.exe" – ezt fentebb elkapjuk, de a
            # „szamla.pdf .exe" alakot (szóközzel) is nézzük
            if re.search(r"\.(pdf|doc|xls|jpg|png)\s*\.\w{2,4}$", n):
                ki.append(nev)
    return ki


def csatolmany_figyelmeztetes(nevek) -> str:
    veszelyes = veszelyes_csatolmanyok(nevek)
    if not veszelyes:
        return ""
    return ("FIGYELEM: ez a csatolmány megnyitáskor programot indít a gépeden: "
            "%s. Levélben érkező ilyen fájl szinte mindig kártékony. Csak "
            "akkor nyisd meg, ha biztosan tudod, mi az és kitől jött."
            % ", ".join(veszelyes))


# ====================================================================
#  Leiratkozás (List-Unsubscribe, RFC 2369 / 8058)
# ====================================================================

def leiratkozas_lehetosegek(info: dict) -> dict:
    """A leiratkozás módjai a fejlécből: {'http': url, 'mailto': cím,
    'egykattintas': bool}.

    Vakon a leiratkozó link megkeresése a levél szövegében kínszenvedés – a
    szabvány szerinti fejléc viszont pontos és gépi."""
    nyers = str(info.get("leiratkozas", "") or "")
    ki = {"http": "", "mailto": "", "egykattintas": False}
    for resz in re.findall(r"<([^>]+)>", nyers) or ([nyers] if nyers else []):
        r = resz.strip()
        if r.lower().startswith("http") and not ki["http"]:
            ki["http"] = r
        elif r.lower().startswith("mailto:") and not ki["mailto"]:
            ki["mailto"] = r[7:]
    # RFC 8058: egykattintásos leiratkozás (a szolgáltató külön jelzi)
    post = str(info.get("leiratkozas_post", "") or "").lower()
    ki["egykattintas"] = bool(ki["http"] and "one-click" in post)
    return ki


def van_leiratkozas(info: dict) -> bool:
    m = leiratkozas_lehetosegek(info)
    return bool(m["http"] or m["mailto"])


def leiratkozas_szoveg(info: dict) -> str:
    m = leiratkozas_lehetosegek(info)
    if m["egykattintas"]:
        return ("Erről a hírlevélről egyetlen lépéssel le tudlak iratkoztatni "
                "– a szolgáltató ezt szabványosan felkínálja.")
    if m["mailto"]:
        return ("A leiratkozáshoz egy levelet kell küldeni ide: %s. "
                "Megírjam és elküldjem helyetted?" % m["mailto"])
    if m["http"]:
        return ("A leiratkozás ezen az oldalon lehetséges: %s. Megnyissam?"
                % m["http"])
    return "Ehhez a levélhez a feladó nem adott meg leiratkozási lehetőséget."
