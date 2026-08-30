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
import threading
import urllib.error
import urllib.parse
import urllib.request

MYMEMORY = "https://api.mymemory.translated.net/get"
_MAX_DARAB = 480          # a szolgáltatás 500 karakteres kérést enged
_FEJ = {"User-Agent": "SuperDL-mail/1.0"}

_MOTOROK_ALAP = [
    ("mymemory", "Ingyenes fordító (kulcs nélkül, a szöveg elhagyja a gépet)"),
    ("ai", "AI-fordítás a saját kulcsoddal (jobb minőség)"),
]
_OFFLINE = ("offline", "Helyben, a gépeden (a szöveg EL SEM HAGYJA a gépet)")


def _ct2_behoz():
    """A CTranslate2 futtatókörnyezet behozása – a MÁR TELEPÍTETT programban is.

    Miért nem sima `import ctranslate2`: a kész (fagyasztott) programból
    szándékosan kimarad a `ctranslate2.converters` alcsomag, mert az a torch-ot
    húzná be (+365 MB), a fordításhoz viszont semmi köze. A csomag
    `__init__.py`-ja viszont feltétel nélkül importálja, ezért a kész
    programban az `import ctranslate2` ImportError-ral elszállt – és a helyben
    futó fordítás CSENDBEN eltűnt az F9 listájából, pedig ott volt a gépen.
    Forrásból futtatva sosem látszott a hiba. [Dávid jelezte, 2026-08-30]

    Ezt a Core-ban is javítottuk (`offlineford.ct2()`), de a javítás csak új
    programverzióval jut el a felhasználóhoz. Itt, a modulban ezért MEGISMÉTELJÜK:
    így a mostani telepített programban is visszakerül a helyben futó fordító –
    modulfrissítéssel, a program újraépítése nélkül."""
    from superdl import offlineford
    ct2 = getattr(offlineford, "ct2", None)
    if callable(ct2):                      # újabb Core: ott már meg van oldva
        return ct2()
    import sys
    import types
    try:
        import ctranslate2
        return ctranslate2
    except ImportError:
        pass
    # üres pótlék a kihagyott alcsomag helyére, majd újra
    sys.modules.setdefault("ctranslate2.converters",
                           types.ModuleType("ctranslate2.converters"))
    sys.modules.pop("ctranslate2", None)
    import ctranslate2
    return ctranslate2


def offline_elerheto() -> bool:
    """Van-e a programban offline fordítómotor? (SuperDL 4.5.0-tól.) Régebbi
    programverzióval a modul szépen visszalép az online fordításra."""
    try:
        from superdl import offlineford      # 4.5.0 előtti Core-ban nincs
        _ = offlineford.modell_mappa
    except Exception:
        return False
    try:
        _ct2_behoz()
        return True
    except Exception:
        return False


def motorok() -> list:
    """A választható fordítók – az OFFLINE elöl, mert az a legvédettebb: a
    levél szövege el sem hagyja a gépet."""
    return ([_OFFLINE] if offline_elerheto() else []) + _MOTOROK_ALAP


# visszafelé kompatibilis név (a régi kód és a tesztek ezt használják)
MOTOROK = _MOTOROK_ALAP


# ---------------------------------------------------------------------------
# ALAPÉRTELMEZETT FORDÍTÓ  [felhasználói kérés, 2026-08-29]
#
# Eddig MINDEN fordításnál feljött a kérdés, hogy melyik motorral fordítsunk.
# Akinek megvan a döntése („nekem a helyben futó kell, kész”), annak ez napi
# tíz fölösleges párbeszéd. Ezért a Beállítások → Általános lapon kiválasztható
# egy alapértelmezett fordító; ilyenkor az F9 kérdés nélkül fordít.
#
# A „kérdezzen rá” marad az ALAPÉRTELMEZÉS: aki nem nyúl a beállításhoz, annak
# semmi nem változik – és a levél szövege sosem hagyja el a gépet a háta mögött,
# mert a döntést egyszer, tudatosan ő hozza meg.
# ---------------------------------------------------------------------------

BEALLITAS_KULCS = "forditas_motor"
KERDEZ = "kerdez"


def motor_ervenyes(kulcs: str) -> str:
    """A tárolt beállítás ELLENŐRZÉSE a mostani géppel.

    Miért kell: a beállítás a felhasználó gépén marad, a program viszont
    frissülhet (vagy visszafelé is: régebbi Core-ban nincs offline motor).
    Ha a beállított motor most nem elérhető, NEM hibázunk – visszalépünk a
    kérdésre, hogy a felhasználó lássa, mi történik."""
    kulcs = (kulcs or "").strip() or KERDEZ
    if kulcs == KERDEZ:
        return KERDEZ
    if kulcs == "offline":
        return "offline" if offline_elerheto() else KERDEZ
    if kulcs in [k for k, _n in _MOTOROK_ALAP]:
        return kulcs
    return KERDEZ


def alap_motor(cfg=None) -> str:
    """A beállított alapértelmezett fordító kulcsa, vagy KERDEZ."""
    try:
        ertek = (cfg or {}).get(BEALLITAS_KULCS, "")
    except Exception:
        ertek = ""
    return motor_ervenyes(ertek)


def valaszthato_motorok() -> list:
    """A beállítás legördülő listájához – az elején a „kérdezzen rá”."""
    return [(KERDEZ, "Kérdezzen rá minden fordításnál (ez az alapértelmezés)")] \
        + motorok()


# ---------------------------------------------------------------------------
# NYELVI CSOMAGOK – csendben, a háttérben
# ---------------------------------------------------------------------------

_letoltes_zar = threading.Lock()
_folyamatban = set()          # (honnan, hova) – nehogy kétszer induljon


def offline_kesz(honnan: str, hova: str = "hu") -> bool:
    """Megvan-e MÁR helyben ez a nyelvpár? HÁLÓZAT NÉLKÜL eldönthető –
    ezért hívható a felületi szálról is, nem akasztja meg az ablakot."""
    if not offline_elerheto():
        return False
    try:
        from superdl import offlineford
        megvan = set(offlineford.telepitett_parok())
    except Exception:
        return False
    if (honnan, hova) in megvan:
        return True
    # a nyílt modellek angol-központúak: a pivot két csomagot jelent
    return (honnan, "en") in megvan and ("en", hova) in megvan


def letolt_csendben(nyelvek, hova: str = "hu", kesz=None) -> bool:
    """A helyben futó fordításhoz kellő nyelvi csomagok letöltése HÁTTÉRBEN.

    „Szépen csendben”: nincs párbeszédablak, nincs folyamatjelző, a program
    közben végig használható. A hibát sem dobjuk a felhasználó arcába – ha a
    letöltés nem sikerül, a fordítás akkor is működik (online motorral), csak
    később megint megpróbáljuk.

    Visszaad: elindult-e egyáltalán letöltés."""
    if not offline_elerheto():
        return False
    nyelvek = [n for n in (nyelvek or []) if n and n != hova]
    if not nyelvek:
        return False

    def munka():
        from superdl import offlineford
        letoltve, hiba = [], None
        for ny in nyelvek:
            kulcs = (ny, hova)
            with _letoltes_zar:
                if kulcs in _folyamatban:
                    continue
                _folyamatban.add(kulcs)
            try:
                for p in offlineford.hianyzo(ny, hova):
                    offlineford.letolt(p)
                    letoltve.append((p["from_code"], p["to_code"]))
            except Exception as ex:                    # hálózat, hely, jog…
                hiba = ex
            finally:
                with _letoltes_zar:
                    _folyamatban.discard(kulcs)
        if kesz:
            try:
                kesz(letoltve, hiba)
            except Exception:
                pass

    threading.Thread(target=munka, daemon=True,
                     name="superdl-fordito-letoltes").start()
    return True


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
    """Egy kérés az ingyenes fordítóhoz.

    A korlát TÖBBFÉLEKÉPPEN érkezhet: néha rendes válaszban („LIMIT”), néha
    viszont a szolgáltató egyszerűen elzavar egy 429-es HTTP-hibával. Ez utóbbi
    KIVÉTELKÉNT jön, tehát a válasz-vizsgálatig el sem jutnánk – a felhasználó
    pedig egy nyers „HTTP Error 429: Too Many Requests” üzenetet kapna, ami
    semmit nem mond meg arról, mit tegyen. (Farkas István jelezte, 2026-08-29.)
    """
    keres = urllib.request.Request(url, headers=_FEJ)
    try:
        with urllib.request.urlopen(keres, timeout=timeout) as v:
            return json.loads(v.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as ex:
        if ex.code == 429:
            raise RuntimeError(
                "Az ingyenes fordító mára nem fogad több kérést tőled "
                "(a napi keret kimerült, vagy túl sűrűn ment a fordítás). "
                "Próbáld pár óra múlva vagy holnap. Ha nem szeretnél várni: a "
                "Beállításokban válaszd a helyben futó fordítást (a szöveg el "
                "sem hagyja a gépet), vagy az AI-fordítást a saját kulcsoddal."
            ) from ex
        if ex.code in (500, 502, 503, 504):
            raise RuntimeError(
                "Az ingyenes fordító most nem elérhető (a szolgáltató oldalán "
                "van a hiba). Próbáld később, vagy válts a helyben futó "
                "fordításra.") from ex
        raise RuntimeError(
            "A fordító nem válaszolt rendben (hibakód: %d)." % ex.code) from ex
    except urllib.error.URLError as ex:
        raise RuntimeError(
            "Nincs kapcsolat a fordítóval. Ellenőrizd az internetet – vagy "
            "használd a helyben futó fordítást, amihez nem kell hálózat."
        ) from ex


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
    if motor == "offline":
        from superdl import offlineford
        kesz = offlineford.fordit(szoveg, honnan, hova, halad)
    elif motor == "ai":
        kesz = ai_fordit(szoveg, honnan, hova)
    else:
        kesz = mymemory_fordit(szoveg, honnan, hova, halad)
    return {"szoveg": kesz, "motor": motor, "honnan": honnan, "hova": hova}


def motor_neve(kulcs: str) -> str:
    if kulcs == "offline":
        return "helyben, a gépeden"
    return "AI, a saját kulcsoddal" if kulcs == "ai" else "ingyenes fordítóval"


def megjelenites(eredeti: str, forditas: dict) -> str:
    """A fordítás a levél szövege FÖLÉ kerül, jól elválasztva – az eredeti
    megmarad alatta, mert azt is látni kell (nevek, számok, linkek)."""
    fejlec = ("=== FORDÍTÁS (%s nyelvről %s nyelvre, %s) ==="
              % (nyelv_neve(forditas["honnan"]), nyelv_neve(forditas["hova"]),
                 motor_neve(forditas["motor"])))
    return "%s\n\n%s\n\n=== AZ EREDETI LEVÉL ===\n\n%s" % (
        fejlec, forditas["szoveg"], eredeti)
