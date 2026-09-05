# -*- coding: utf-8 -*-
"""KÖZÖS HIBASZÖVEG-FORDÍTÓ (letöltő-motor MK6).

**Miért kellett.** A `media.friendly_error()` évek óta megvan, és nagyon jó:
korhatár, bot-ellenőrzés, privát videó, régiózár, lejárt link – mind
lépésenkénti magyar tanáccsal. **Csak épp egyetlen hívója volt**, a yt-dlp
motor. A szegmentált letöltő és a torrent nyers kivételszöveget írt a
`progress.error`-ba, amit aztán a felolvasó bemondott a felhasználónak.

Ez ugyanaz a minta, mint a tvmusor naptár-hibájánál: **egy jó szolgáltatás
létezik, de nincs bekötve.** Az MK6 „ugorj a hibás elemre, és mondd meg, mit
tegyél" ígérete háromból egy motoron teljesült volna.

**Amit ez a modul hozzátesz** a `media.friendly_error`-hoz: a torrent- és a
szegmentált letöltő SAJÁT hibái, amiket a yt-dlp sosem termel (aria2-indítás,
magnet-hiba, tracker, Range-támogatás hiánya, ellenőrzőösszeg-eltérés).

A modul SZÁNDÉKOSAN nem tud a wx-ről és a hálózatról: szövegből szöveget
csinál, tehát wx és net nélkül tesztelhető.
"""
from __future__ import annotations

# Azok a mondatkezdetek, amiket MI magunk gyártottunk (MK2, MK3, MK4). Ezeket
# TILOS újrafordítani: már magyarul, emberi nyelven szólnak, és a mintaillesztés
# csak elronthatná őket.
_SAJAT_KEZDETEK = (
    "nincs elég hely",
    "a letöltött fájl ellenőrző összege",
    "ez a link egy weboldalra mutat",
    "a letöltött fájl mérete nem teljes",
    "hiányos letöltés",
)


def sajat_uzenet(uzenet: str) -> bool:
    """Igaz, ha ezt a mondatot MI írtuk, tehát nem kell hozzányúlni."""
    m = (uzenet or "").strip().lower()
    return any(m.startswith(k) for k in _SAJAT_KEZDETEK)


def _torrent_es_szegmens(m: str) -> str:
    """A torrent- és a szegmentált letöltő saját hibái.

    Ezeket a yt-dlp SOSEM termeli, ezért a `media.friendly_error` nem is
    ismerheti őket – és pont ezek maradtak eddig nyers angol szövegként."""
    if "aria2" in m and ("not found" in m or "nem található" in m
                         or "cannot" in m or "failed to start" in m):
        return ("A torrent-motor (aria2) nem indult el. A program általában "
                "magától letölti – indítsd újra a letöltést; ha nem segít, a "
                "Súgó, majd a Frissítések keresése telepíti újra a motort.")
    if "rpc" in m and ("refused" in m or "timed out" in m or "timeout" in m):
        return ("A torrent-motor nem válaszol. Állítsd le a letöltést, és "
                "indítsd újra. Ha ez ismétlődik, indítsd újra a programot – "
                "a torrent a sorban marad, és onnan folytatódik, ahol tart.")
    if "magnet" in m and ("invalid" in m or "malformed" in m or "parse" in m):
        return ("Ez a magnet-link hibás vagy hiányos. Másold ki újra a "
                "forrásoldalról – a teljes link a magnet kettőspont résszel "
                "kezdődik.")
    if "no peers" in m or "no seeds" in m or "0 seeders" in m:
        return ("Ehhez a torrenthez jelenleg NINCS megosztó, ezért nem tud "
                "haladni. Ez nem a te hibád és nem a programé: várni kell, "
                "amíg valaki megosztja. A sorban marad, és magától "
                "újrapróbálkozik.")
    if "tracker" in m and ("failed" in m or "error" in m or "unreachable" in m):
        return ("A torrent nyilvántartó szervere (tracker) nem válaszol. A "
                "letöltés a peer-felderítéssel így is elindulhat; hagyd a "
                "sorban, magától újrapróbálkozik.")
    if "nem támogatta a range" in m or "not 206" in m or "nem 206" in m:
        return ("Ez a szerver nem engedi a fájl darabokban letöltését, ezért "
                "a letöltés csak egy szálon megy – lassabb lehet, de működik. "
                "Ha megszakadt, indítsd újra: onnan folytatja, ahol tart.")
    return ""


def emberi(uzenet: str) -> str:
    """Bármelyik motor hibájából emberi, LÉPÉST IS MONDÓ magyar mondat.

    Sorrend, és mindegyik lépésnek oka van:

    1. **A saját mondatainkhoz nem nyúlunk.** Az MK2/MK3/MK4 üzenetei már
       magyarul szólnak; újrafordítva csak romlanának.
    2. **Előbb a torrent/szegmens saját hibái**, mert a `media.friendly_error`
       általános mintái (pl. a „403") ráillenének, és rosszabb tanácsot adnának.
    3. **Végül a `media.friendly_error`**, ami a közös eseteket (hálózat, hely,
       jogosultság, 403, 429) MINDEN motorra jól kezeli.

    Ha egyik minta sem illik, az EREDETI szöveget adjuk vissza. Kitalálni egy
    magyarázatot rosszabb volna a nyers hibánál: a hamis magyarázat órákat
    lop el a felhasználótól (ez volt a tvmusor tanulsága)."""
    uzenet = (uzenet or "").strip()
    if not uzenet:
        return ""
    if sajat_uzenet(uzenet):
        return uzenet
    m = uzenet.lower()
    sajat = _torrent_es_szegmens(m)
    if sajat:
        return sajat
    try:
        # MK6/6 óta a `friendly_error` ITT lakik (lentebb, ebben a fájlban),
        # nem a media.py-ban. Így megszűnt a körkörös függés is: a media
        # importálja a hibaszoveget, nem fordítva.
        return friendly_error(uzenet)
    except Exception:
        # a fordítás SOHA nem buktathatja meg a hibakezelést: rosszabb egy
        # elnyelt hiba, mint egy csúnya hibaszöveg
        return uzenet


def gond_mondat(nev: str, allapot: str, uzenet: str, utkozes: bool = False,
                probak: int = 0, elakadt: bool = False,
                elakadas_oka: str = "") -> str:
    """Az MK6 ugrás után elhangzó EGY mondat: mi a baj, és mit tegyél.

    A név elöl van, mert vakon először azt kell tudni, MELYIK elemről beszélünk
    – utána jön a baj, és csak legvégül a teendő. Fordított sorrendben a
    felhasználó a mondat felénél még nem tudja, mire vonatkozik, amit hall."""
    nev = (nev or "a letöltés").strip()
    if utkozes:
        return (f"{nev}: a cél fájl már létezik, és ez DÖNTÉSRE vár – "
                "magától nem oldódik meg. Kihagyhatod, felülírhatod, vagy "
                "ellenőrizve megoszthatod.")
    if elakadt:
        # Az elakadás az ÜTKÖZÉS után, de a hiba ELŐTT áll: nincs hibaszöveg,
        # amit felolvashatnánk (kivétel sem történt), ezért ha ide nem külön
        # ág jönne, a mondat annyi lenne, hogy „állapota: letöltés” – vagyis
        # a program pont azt állítaná, hogy minden rendben. Ez volt Laci
        # egyórás élménye, mondatba öntve.
        ok = (elakadas_oka or "Régóta nem érkezik adat.").strip()
        return (f"{nev}: elakadt, bár a letöltés fut. {ok}")
    reszek = [f"{nev}:"]
    if probak:
        reszek.append(f"{probak} sikertelen próbálkozás után.")
    szoveg = emberi(uzenet)
    if szoveg:
        reszek.append(szoveg)
    elif allapot:
        reszek.append(f"állapota: {allapot}.")
    return " ".join(reszek)


def van_javaslat(uzenet: str) -> bool:
    """Igaz, ha a szövegből lett valódi tanács, nem csak visszakaptuk a nyerset.

    A felület ebből tudja, hogy érdemes-e külön kimondani a javasolt lépést,
    vagy csak a hibát olvassa fel."""
    uzenet = (uzenet or "").strip()
    if not uzenet:
        return False
    return emberi(uzenet) != uzenet or sajat_uzenet(uzenet)


# ---------------------------------------------------------------
# ÁTKÖLTÖZTETVE a media.py-ból (MK6/6, 2026-09-03).
# A szövegek VÁLTOZATLANOK: a fordítás minősége évek munkája, és a
# refaktor célja épp az volt, hogy MINDEN motor ugyanezt kapja.
# ---------------------------------------------------------------

def _looks_offline(m: str) -> bool:
    """Hálózati/kapcsolati eredetű-e a hiba szövege (a netcheck közös mintáival,
    ha elérhető; különben a leggyakoribb mintákkal)."""
    try:
        from . import netcheck
        return netcheck.looks_like_offline(m)
    except Exception:
        return any(h in m for h in (
            "getaddrinfo failed", "timed out", "timeout", "connection reset",
            "connection refused", "network is unreachable",
            "temporary failure in name resolution", "max retries exceeded",
            "failed to establish"))
def friendly_error(msg: str) -> str:
    """Ismert, gyakori hibák érthető, lépésenkénti magyar üzenete."""
    m = msg.lower()
    # a korhatár ELŐBB, mint a bot-ellenőrzés: a „Sign in to confirm your age”
    # a bot-mintára is illik („sign in to confirm”), de a helyes üzenet a korhatáros
    if "confirm your age" in m or "age-restricted" in m or "age restricted" in m:
        return ("Ez a videó KORHATÁROS, ezért csak bejelentkezve tölthető le. "
                "Megoldás: a Beállítások → Fiók/Sütik lapon válaszd ki azt a "
                "böngészőt, amelyikben be vagy jelentkezve az oldalra – a "
                "program a sütikkel igazolja az életkort.")
    if _is_bot_check(msg):
        return ("A YouTube megerősítést kér, hogy nem robot vagy (bot-"
                "ellenőrzés). A SuperDL automatikusan megpróbálta a böngésződ "
                "sütijeit és egy tartalék lejátszó-klienst is – ha ezt az "
                "üzenetet látod, ezek sem segítettek. FONTOS: ez a legtöbbször "
                "NEM a sütiken múlik – a YouTube magát az internetkapcsolatot "
                "(IP-címet) jelöli meg, például sok letöltés, VPN/proxy vagy "
                "megosztott cím miatt. Mit tegyél, sorrendben: "
                "1. GYORSTESZT: próbáld meg telefonos mobilnetről (hotspot) – "
                "ha úgy megy, a vonalad van megjelölve, nem a géped. "
                "2. Indítsd újra a routert (sok helyen új címet kapsz), és "
                "kapcsold ki a VPN-t/proxyt. "
                "3. Várj néhány órát, és tölts le kevesebbet egyszerre – a "
                "jelölés magától lejár. "
                "4. Ha makacs: PRIVÁT böngészőablakban jelentkezz be a "
                "YouTube-ra, egy cookies.txt-kiegészítővel mentsd ki a "
                "sütiket, ZÁRD BE a privát ablakot (így a sütik érvényben "
                "maradnak), majd a Beállítások → Fiók/Sütik lapon add meg a "
                "cookies.txt fájlt – és letöltés közben ne használd a "
                "YouTube-ot ugyanazzal a fiókkal.")
    if "could not copy" in m and "cookie" in m:
        return ("A böngésző (Chrome/Edge) épp FUT, ezért a program nem tudja "
                "kiolvasni a sütijeit. Megoldás: zárd be a böngészőt, VAGY a "
                "Sütik beállításnál válaszd a Firefoxot, VAGY használj "
                "cookies.txt fájlt.")
    if ("dpapi" in m or "failed to decrypt" in m or "could not decrypt" in m
            or "failed to load cookies" in m or "unable to load cookies" in m
            or "could not load cookies" in m):
        return ("A böngésződ sütijeit nem sikerült beolvasni (az újabb "
                "Chrome/Edge „App-Bound” titkosítása miatt egyetlen letöltő sem "
                "tudja kiolvasni). Megoldás: jelentkezz be a YouTube-ra "
                "FIREFOXBAN, és a Sütik beállításnál válaszd a Firefoxot; VAGY "
                "exportálj egy cookies.txt fájlt egy böngésző-kiegészítővel. "
                "Frissítsd a programot is, hogy a legújabb letöltőmotor "
                "(yt-dlp) legyen benne.")
    # ---- további gyakori yt-dlp hibák, emberi nyelven (Tibi-audit 4.4) ----
    if "private video" in m or "this video is private" in m:
        return ("Ez a videó PRIVÁT – csak az láthatja (és töltheti le), akivel "
                "a feltöltő megosztotta. Ha jogosult vagy rá, jelentkezz be a "
                "böngészőben, és a Beállítások → Fiók/Sütik lapon válaszd ki "
                "azt a böngészőt.")
    if ("members-only" in m or "members only" in m or "join this channel" in m
            or "premium members" in m or "music premium" in m):
        return ("Ez a tartalom TAGSÁGHOZ/ELŐFIZETÉSHEZ kötött (csatornatagság "
                "vagy Premium). Csak akkor tölthető le, ha a fiókod jogosult "
                "rá: jelentkezz be a böngészőben, és a Beállítások → Fiók/Sütik "
                "lapon válaszd ki azt a böngészőt.")
    if ("available in your country" in m or "geo restricted" in m
            or "geo-restricted" in m or "blocked it in your country" in m
            or "blocked in your country" in m):
        return ("Ez a tartalom a TE ORSZÁGODBÓL nem érhető el (régiózár). Ezen "
                "a program nem tud segíteni – a szolgáltató zárolja.")
    if ("video unavailable" in m or "this video has been removed" in m
            or "account associated with this video has been terminated" in m
            or "no longer available" in m):
        return ("A videó MÁR NEM ÉRHETŐ EL (törölték, elérhetetlenné tették, "
                "vagy megszűnt a feltöltő fiókja). Ellenőrizd a linket a "
                "böngészőben.")
    if "premieres in" in m or "live event will begin" in m or "premiere" in m:
        return ("Ez a videó MÉG NEM ELÉRHETŐ – premier vagy élő adás, ami "
                "később kezdődik. Próbáld újra az adás/premier UTÁN.")
    if "requested format is not available" in m:
        return ("A kért formátum/minőség ehhez a videóhoz nem érhető el. "
                "Próbáld más formátum- vagy minőség-beállítással (Beállítások "
                "→ Letöltés).")
    if "ffmpeg is not installed" in m or "ffmpeg not found" in m:
        return ("Az ffmpeg (a hang/videó-feldolgozó motor) nem érhető el, "
                "pedig az összefűzéshez/átkódoláshoz kell. A program általában "
                "magától letölti – indítsd újra a letöltést; ha nem segít, a "
                "Súgó → Frissítések keresése frissíti a motorokat.")
    if "http error 403" in m or "forbidden" in m:
        return ("Az oldal MEGTAGADTA a hozzáférést (403). Gyakori ok: lejárt "
                "vagy hiányzó bejelentkezés, vagy az oldal átmenetileg blokkol. "
                "Próbáld újra pár perc múlva, vagy a Beállítások → Fiók/Sütik "
                "lapon add meg a bejelentkezett böngésződet.")
    if "429" in m or "too many requests" in m:
        return ("Az oldal átmenetileg KORLÁTOZ (túl sok kérés – 429). Várj "
                "egy kicsit, és tölts le kevesebbet egyszerre.")
    if ("unable to download webpage" in m or _looks_offline(m)):
        # KÜLÖNBSÉGTÉTEL: egyáltalán nincs net, vagy csak ez a szolgáltatás nem
        # válaszol (a felhasználó ezt kérte, hogy tudja, hol a gond)
        try:
            from . import netcheck
            code, why = netcheck.offline_reason()
        except Exception:
            code, why = "", ""
        if code == "no_internet":
            return ("NINCS INTERNETKAPCSOLAT. " + why + " A program a "
                    "félbeszakadt letöltést később folytatni tudja.")
        if code == "service_down":
            return ("Az internetkapcsolat működik, de EZ AZ OLDAL most nem "
                    "érhető el. Próbáld újra pár perc múlva.")
        return ("HÁLÓZATI HIBA: az oldal nem érhető el. Ellenőrizd az "
                "internetkapcsolatot, majd próbáld újra – a program a "
                "félbeszakadt letöltést folytatni tudja.")
    if ("no space left" in m or "errno 28" in m or "disk full" in m
            or "not enough space" in m):
        return ("ELFOGYOTT A HELY a lemezen – a letöltés nem fér el. "
                "Szabadíts fel helyet, vagy válassz másik célmappát.")
    if "permission denied" in m or "errno 13" in m or "access is denied" in m:
        return ("A célmappába NEM LEHET ÍRNI (hozzáférés megtagadva). Válassz "
                "másik célmappát a Beállításokban – például a Dokumentumok "
                "vagy Letöltések mappát.")
    if "unsupported url" in m or "no suitable extractor" in m:
        return ("Ezt az oldalt/linket a letöltőmotor NEM TÁMOGATJA. Ellenőrizd "
                "a linket; ha új oldalról van szó, a Súgó → Frissítések "
                "keresése frissítheti a motort, ami már ismerheti.")
    return msg
def _is_cookie_error(msg: str) -> bool:
    """Igaz, ha a hiba a böngésző-sütik kiolvasásából/betöltéséből ered (fut a
    böngésző, zárolt VAGY App-Bound-titkosított süti-adatbázis)."""
    m = msg.lower()
    return (("could not copy" in m and "cookie" in m)
            or "dpapi" in m or "failed to decrypt" in m
            or "could not decrypt" in m
            or "failed to load cookies" in m
            or "unable to load cookies" in m
            or "could not load cookies" in m)
def _is_bot_check(msg: str) -> bool:
    """Igaz, ha a YouTube BOT-ELLENŐRZÉSE blokkol (»Sign in to confirm you're
    not a bot«) – ilyenkor a böngésző bejelentkezett sütijei segítenek."""
    m = msg.lower()
    return ("not a bot" in m or "sign in to confirm" in m
            or "confirm you’re not a bot" in m)
