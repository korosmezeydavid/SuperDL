# -*- coding: utf-8 -*-
"""IDEGEN NYELVŰ LEVÉL FORDÍTÁSA – kulcs nélkül is.

Felhasználói kérés (2026-08-16): „ha például egy levelet lengyelül kapok meg,
azt egy gombbal tudjam gyorsan az anyanyelvemre lefordíttatni – létezik olyan
megoldás, ami nem igényel API-kulcsot?”

Igen. Két motorral dolgozunk, és a réteg SZÁNDÉKOSAN cserélhető, hogy később
(Core-kiadásban) egy HELYBEN futó, offline motor is bekapcsolható legyen
anélkül, hogy a felületet újra kellene írni:

  • „mymemory” – ingyenes, KULCS NÉLKÜLI online szolgáltatás. Napi korlátja van,
    és a szöveg elhagyja a gépet: ezt a felhasználónak KI KELL MONDANI, mert egy
    magánlevél tartalmáról van szó.
  • „ai” – a felhasználó SAJÁT AI-kulcsával; jobb minőség, a hangnemet is tartja.
    Szintén külső szolgáltató.

A modul wx- és hálózat-mentesen tesztelhető: a hálózati hívás egyetlen kis
függvényben (`_lekerdez`) van, a többi tiszta szövegkezelés.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

MYMEMORY = "https://api.mymemory.translated.net/get"
_MAX_DARAB = 480          # a szolgáltatás 500 karakteres kérést enged
_FEJ = {"User-Agent": "SuperDL-mail/1.0"}

MOTOROK = [
    ("mymemory", "Ingyenes fordító (kulcs nélkül, a szöveg elhagyja a gépet)"),
    ("ai", "AI-fordítás a saját kulcsoddal (jobb minőség)"),
]

NYELVEK = [("hu", "magyar"), ("en", "angol"), ("de", "német"), ("pl", "lengyel"),
           ("sk", "szlovák"), ("ro", "román"), ("hr", "horvát"), ("sr", "szerb"),
           ("cs", "cseh"), ("uk", "ukrán"), ("ru", "orosz"), ("fr", "francia"),
           ("es", "spanyol"), ("it", "olasz"), ("nl", "holland"),
           ("pt", "portugál"), ("tr", "török")]


def nyelv_neve(kod: str) -> str:
    for k, n in NYELVEK:
        if k == kod:
            return n
    return kod or "ismeretlen"


# Nyelvfelismerés GYAKORI SZAVAKBÓL. Szándékosan pehelysúlyú (nincs külső
# csomag): a levelek nyelvének eldöntéséhez bőven elég, és ha bizonytalan,
# a hívó rákérdez a felhasználónál – nem tippel a háta mögött.
_JELLEMZO = {
    "hu": ("hogy", "nem", "egy", "vagy", "és", "van", "lesz", "kérem", "köszönöm",
           "üdvözlettel", "levél", "ezt", "azt", "meg", "már"),
    "en": ("the", "and", "you", "for", "with", "please", "regards", "have",
           "this", "that", "your", "from", "would", "thanks"),
    "de": ("und", "der", "die", "das", "ich", "nicht", "mit", "für", "bitte",
           "sehr", "geehrte", "grüße", "ist", "sie"),
    "pl": ("nie", "się", "jest", "dla", "proszę", "dzień", "dobry", "oraz",
           "przesyłam", "pozdrawiam", "który", "tak", "wiadomość"),
    "sk": ("je", "sa", "na", "prosím", "ďakujem", "dobrý", "deň", "ktoré",
           "pozdravom", "nie"),
    "cs": ("je", "se", "na", "prosím", "děkuji", "dobrý", "den", "které",
           "pozdravem", "ne"),
    "ro": ("este", "care", "pentru", "mulțumesc", "bună", "ziua", "salutări",
           "nu", "și"),
    "hr": ("je", "se", "za", "molim", "hvala", "dobar", "dan", "pozdrav", "ne"),
    "sr": ("је", "се", "за", "молим", "хвала", "добар", "дан", "поздрав"),
    "uk": ("це", "для", "будь", "ласка", "дякую", "добрий", "день", "вітаю"),
    "ru": ("это", "для", "пожалуйста", "спасибо", "добрый", "день", "здравствуйте",
           "что", "как"),
    "fr": ("les", "pour", "vous", "merci", "bonjour", "cordialement", "que",
           "est", "avec"),
    "es": ("que", "por", "para", "gracias", "hola", "saludos", "con", "los"),
    "it": ("che", "per", "con", "grazie", "ciao", "saluti", "sono", "una"),
    "nl": ("het", "een", "voor", "dank", "hallo", "groeten", "met", "niet"),
    "pt": ("que", "para", "obrigado", "olá", "com", "não", "uma"),
    "tr": ("için", "teşekkür", "merhaba", "bir", "ile", "değil", "saygılarımla"),
}


def nyelv_felismer(szoveg: str) -> tuple:
    """(nyelvkód, magabiztos-e). Ha nem elég egyértelmű, a hívó kérdezzen rá."""
    sz = re.sub(r"[^\wáéíóöőúüűàâäçèéêëìîïñòôöùûüğışčćđžłńśźż\s]", " ",
                (szoveg or "").lower(), flags=re.UNICODE)
    szavak = sz.split()
    if len(szavak) < 3:
        return "", False
    keszlet = set(szavak)
    pontok = {}
    for kod, jellemzok in _JELLEMZO.items():
        talalat = sum(1 for j in jellemzok if j in keszlet)
        if talalat:
            pontok[kod] = talalat
    if not pontok:
        return "", False
    sorrend = sorted(pontok.items(), key=lambda x: -x[1])
    elso = sorrend[0]
    masodik = sorrend[1][1] if len(sorrend) > 1 else 0
    # magabiztos, ha van legalább 2 találat ÉS érdemben veri a következőt
    return elso[0], bool(elso[1] >= 2 and elso[1] >= masodik + 2)


def darabol(szoveg: str, meret: int = _MAX_DARAB) -> list:
    """A szöveg feldarabolása a szolgáltatás korlátja alá, MONDATHATÁRON.
    Azért mondathatáron, mert szó közepén elvágva a fordítás értelmetlen lenne."""
    szoveg = (szoveg or "").strip()
    if not szoveg:
        return []
    darabok, jelenlegi = [], ""
    for resz in re.split(r"(?<=[.!?…])\s+|\n{2,}", szoveg):
        resz = resz.strip()
        if not resz:
            continue
        while len(resz.encode("utf-8")) > meret:       # nagyon hosszú mondat
            vagas = resz.rfind(" ", 0, meret // 2)
            vagas = vagas if vagas > 40 else meret // 2
            darabok.append(resz[:vagas].strip())
            resz = resz[vagas:].strip()
        if len((jelenlegi + " " + resz).encode("utf-8")) > meret:
            if jelenlegi:
                darabok.append(jelenlegi.strip())
            jelenlegi = resz
        else:
            jelenlegi = (jelenlegi + " " + resz).strip()
    if jelenlegi:
        darabok.append(jelenlegi.strip())
    return darabok


def _lekerdez(url: str, timeout: int = 30) -> dict:
    keres = urllib.request.Request(url, headers=_FEJ)
    with urllib.request.urlopen(keres, timeout=timeout) as v:
        return json.loads(v.read().decode("utf-8", "replace"))


def mymemory_fordit(szoveg: str, honnan: str, hova: str = "hu",
                    halad=None) -> str:
    """Kulcs nélküli fordítás, darabokban. A napi korlát túllépését ÉRTHETŐ
    magyar mondattal jelezzük, nem nyers hibakóddal."""
    darabok = darabol(szoveg)
    ki = []
    for i, d in enumerate(darabok):
        url = "%s?q=%s&langpair=%s" % (
            MYMEMORY, urllib.parse.quote(d),
            urllib.parse.quote("%s|%s" % (honnan, hova)))
        valasz = _lekerdez(url)
        allapot = valasz.get("responseStatus")
        adat = (valasz.get("responseData") or {}).get("translatedText") or ""
        if str(allapot) not in ("200", "200.0") or not adat:
            reszlet = str(valasz.get("responseDetails") or allapot)
            if "LIMIT" in reszlet.upper():
                raise RuntimeError(
                    "Az ingyenes fordító mai keretét kimerítetted. Próbáld "
                    "holnap, vagy használd az AI-fordítást a saját kulcsoddal.")
            raise RuntimeError("A fordítás nem sikerült: %s" % reszlet)
        ki.append(adat)
        if halad:
            halad((i + 1) / max(1, len(darabok)))
    return "\n".join(ki).strip()


def ai_fordit(szoveg: str, honnan: str, hova: str = "hu") -> str:
    """Fordítás a felhasználó SAJÁT AI-kulcsával (jobb minőség, hangnem-tartás)."""
    from superdl import aiclient
    rendszer = ("Fordító vagy. A kapott e-mailt fordítod le %s nyelvre. "
                "KIZÁRÓLAG a fordítást add vissza, magyarázat, bevezetés és "
                "idézőjel nélkül. Tartsd meg a bekezdéseket és a hangnemet; a "
                "neveket, címeket, számokat ne változtasd meg."
                % nyelv_neve(hova))
    return (aiclient.chat(szoveg, rendszer) or "").strip()


def fordit(szoveg: str, hova: str = "hu", motor: str = "mymemory",
           honnan: str = "", halad=None) -> dict:
    """A teljes fordítás. Visszaad: {"szoveg", "motor", "honnan", "hova"}."""
    szoveg = (szoveg or "").strip()
    if not szoveg:
        raise ValueError("Nincs mit fordítani.")
    if not honnan:
        honnan, _biztos = nyelv_felismer(szoveg)
    if not honnan:
        raise ValueError("Nem sikerült felismerni a levél nyelvét.")
    if honnan == hova:
        raise ValueError("A levél már %s nyelvű." % nyelv_neve(hova))
    if motor == "ai":
        kesz = ai_fordit(szoveg, honnan, hova)
    else:
        kesz = mymemory_fordit(szoveg, honnan, hova, halad)
    return {"szoveg": kesz, "motor": motor, "honnan": honnan, "hova": hova}


def megjelenites(eredeti: str, forditas: dict) -> str:
    """A fordítás a levél szövege FÖLÉ kerül, jól elválasztva – az eredeti
    megmarad alatta, mert azt is látni kell (nevek, számok, linkek)."""
    fejlec = ("=== FORDÍTÁS (%s nyelvről %s nyelvre, %s) ==="
              % (nyelv_neve(forditas["honnan"]), nyelv_neve(forditas["hova"]),
                 "AI, a saját kulcsoddal" if forditas["motor"] == "ai"
                 else "ingyenes fordítóval"))
    return "%s\n\n%s\n\n=== AZ EREDETI LEVÉL ===\n\n%s" % (
        fejlec, forditas["szoveg"], eredeti)
