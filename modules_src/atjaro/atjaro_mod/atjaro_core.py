# -*- coding: utf-8 -*-
"""Átjáró – a PC és a SuperDL telefon (Android launcher) közötti kapcsolat MAGJA.

A telefonon fut egy beépített WiFi-portál (HTTP-szerver, alap port 8080, 4 jegyű
PIN-nel), amit a telefon BEMOND. Ez a modul ehhez csatlakozik a helyi WiFi-n:
zenét és könyvet tölt fel a telefonra, teszteli a kapcsolatot, és le tudja tölteni
a telefon beállítás-mentését (a későbbi kétirányú szinkronhoz: gyógyszer-
emlékeztetők, könyvjelzők/olvasási pozíció).

Csak a felhasználó SAJÁT telefonjához, a saját helyi hálózatán. Semmit nem
továbbítunk sehová – a PC közvetlenül a telefon portáljához kapcsolódik.

Csak a Core-ból jövő `requests`-re épül (nincs külső függőség).
"""
import json
import os

from superdl import store

try:
    import requests
except Exception:                       # a Core-ból jön
    requests = None


ALAP_PORT = 8080
_BEALLITAS_FILE = store.CONFIG_DIR / "atjaro.json"
# a telefonon ismert könyvek fájlnevei (a Könyvolvasó „nincs a telefonon"
# kérdéséhez) – az utolsó szinkron/adatlekérés frissíti
_TELEFON_KONYVEK_FILE = store.CONFIG_DIR / "atjaro_telefon_konyvek.json"

# A portál által ismert célmappák (a /upload „dest" mezője)
DEST_ZENE = "music"
DEST_KONYV = "documents"
DEST_LETOLTES = "download"
DEST_CSENGOHANG = "ringtones"


# ---- beállítás (a telefon IP-je jegyezhető; a PIN forgó, azt nem tároljuk) ---

def beallitas_betolt():
    return store.load_json(_BEALLITAS_FILE, {})


def beallitas_ment(ip, port=ALAP_PORT):
    store.save_json(_BEALLITAS_FILE, {"ip": (ip or "").strip(),
                                      "port": int(port or ALAP_PORT)})


def telefon_konyvek_ment(nevek):
    """A telefonon ismert könyvek FÁJLNEVEIT tárolja (kisbetűsítve), hogy a
    Könyvolvasó tudja, mi van/nincs a telefonon."""
    tiszta = sorted({os.path.basename((n or "").replace("\\", "/")).strip().lower()
                     for n in (nevek or []) if (n or "").strip()})
    store.save_json(_TELEFON_KONYVEK_FILE, tiszta)


def telefon_konyvek_betolt():
    """A telefonon ismert könyv-fájlnevek halmaza (üres, ha még nincs szinkron)."""
    return set(store.load_json(_TELEFON_KONYVEK_FILE, []))


# ---- URL-ek --------------------------------------------------------------

def portal_url(ip, port=ALAP_PORT):
    ip = (ip or "").strip()
    # ha az egészet bemásolták (http://1.2.3.4:8080), fogadjuk el
    if ip.startswith("http://") or ip.startswith("https://"):
        return ip.rstrip("/")
    return f"http://{ip}:{int(port or ALAP_PORT)}"


def _pin(pin):
    return {"pin": str(pin or "").strip()}


# ---- kapcsolat-teszt -----------------------------------------------------

def csatlakozas_teszt(ip, pin, port=ALAP_PORT, timeout=6):
    """Igaz, ha a telefon portálja elérhető ÉS a PIN jó. A `/status` oldal
    bejelentkezve az állapotot adja; rossz PIN esetén a bejelentkező oldalt
    (abban PIN-beviteli mező van) – erről ismerjük fel."""
    if requests is None:
        raise RuntimeError("A hálózati modul (requests) nem érhető el.")
    url = portal_url(ip, port) + "/status"
    r = requests.get(url, params=_pin(pin), timeout=timeout)
    szoveg = (r.text or "").lower()
    # a bejelentkező oldalon PIN-beviteli mező van; ha ilyet látunk, rossz a PIN
    bejelentkezo = ('name="pin"' in szoveg or "adja meg a pin" in szoveg
                    or "add meg a pin" in szoveg)
    return r.status_code == 200 and not bejelentkezo


# ---- fájl-feltöltés (zene, könyv) ----------------------------------------

def _fajl_reszek(utak):
    reszek = []
    for ut in utak:
        try:
            with open(ut, "rb") as f:
                reszek.append(("file", (os.path.basename(ut), f.read())))
        except OSError:
            pass
    return reszek


# hangoskönyv-kiterjesztések (a fájl-küldés szűrőjéhez és a mappa begyűjtéshez)
HANG_KITERJESZTESEK = (".mp3", ".m4a", ".m4b", ".aac", ".ogg", ".oga", ".opus",
                       ".wav", ".flac", ".wma", ".mp2", ".mka")

# NORMÁL (szöveges) könyv-kiterjesztések – hogy mappával ne csak hangoskönyvet,
# hanem sima könyveket is át lehessen küldeni (a felhasználó kérése). PONTOSAN a
# telefon SuperDL-je által OLVASHATÓ formátumok (BookTextExtractor.SUPPORTED_
# EXTENSIONS), hogy amit átküldünk, azt a telefon könyv-listája fel is ismerje.
KONYV_KITERJESZTESEK = (".txt", ".md", ".rtf", ".html", ".htm", ".epub", ".fb2",
                        ".pdf", ".doc", ".docx", ".odt", ".mobi", ".azw",
                        ".azw3", ".prc")

# egy könyv-mappából KÜLDHETŐ minden (hangoskönyv-hang ÉS normál könyvfájl)
KULDHETO_MAPPA_KITERJESZTESEK = tuple(HANG_KITERJESZTESEK) + KONYV_KITERJESZTESEK


def feltolt(ip, pin, utak, dest=DEST_ZENE, port=ALAP_PORT, timeout=600, subdir=""):
    """Fájlok feltöltése a telefon adott mappájába a portál /upload route-ján.
    `subdir` megadva a fájlok a célmappán belül ebbe az almappába kerülnek (egy
    egész hangoskönyv-mappa átküldéséhez). Visszaad: (sikeres_darab, hiba|None)."""
    if requests is None:
        raise RuntimeError("A hálózati modul (requests) nem érhető el.")
    reszek = _fajl_reszek(utak)
    if not reszek:
        return 0, "Egyetlen fájlt sem sikerült beolvasni."
    adat = {"dest": dest}
    if (subdir or "").strip():
        # a teljes (akár beágyazott) relatív almappa; a telefon oldalon a
        # sanitizeSubdir gondoskodik a biztonságról (útvonal-kilépés kizárva)
        adat["subdir"] = (subdir or "").strip().strip("/\\").replace("\\", "/")
    url = portal_url(ip, port) + "/upload"
    r = requests.post(url, params=_pin(pin), data=adat,
                      files=reszek, timeout=timeout)
    if r.status_code != 200:
        return 0, f"A telefon a(z) {r.status_code} hibakóddal válaszolt."
    szoveg = (r.text or "").lower()
    if 'name="pin"' in szoveg:
        return 0, "Rossz PIN – a telefon a bejelentkezést kérte."
    return len(reszek), None


def zene_kuld(ip, pin, utak, port=ALAP_PORT):
    return feltolt(ip, pin, utak, DEST_ZENE, port)


def konyv_kuld(ip, pin, utak, port=ALAP_PORT):
    return feltolt(ip, pin, utak, DEST_KONYV, port)


def _mappa_fajljai(mappa, csak_hang=False):
    """Egy mappa fájljai (nem rekurzívan). csak_hang=True esetén csak hangfájlok."""
    ki = []
    try:
        for n in sorted(os.listdir(mappa)):
            ut = os.path.join(mappa, n)
            if not os.path.isfile(ut):
                continue
            if csak_hang and os.path.splitext(n)[1].lower() not in HANG_KITERJESZTESEK:
                continue
            ki.append(ut)
    except OSError:
        pass
    return ki


def feltolt_egyenkent(ip, pin, utak, dest=DEST_ZENE, subdir="", port=ALAP_PORT,
                      timeout=600, on_progress=None):
    """Fájlok küldése EGYENKÉNT (külön POST-onként), hogy a haladás jelezhető
    legyen. `on_progress(kesz, osszes, fajlnev, sikeres)` minden fájl után hívódik
    (a HÁTTÉRSZÁLRÓL). Visszaad: (sikeres_darab, hiba|None)."""
    utak = [u for u in (utak or []) if os.path.isfile(u)]
    n = len(utak)
    if n == 0:
        return 0, "Nincs küldhető fájl."
    ok = 0
    elso_hiba = None
    for i, ut in enumerate(utak, 1):
        try:
            db, hiba = feltolt(ip, pin, [ut], dest=dest, port=port,
                               timeout=timeout, subdir=subdir)
        except Exception as ex:
            db, hiba = 0, str(ex)
        if db:
            ok += 1
        elif elso_hiba is None:
            elso_hiba = hiba
        if on_progress:
            try:
                on_progress(i, n, os.path.basename(ut), ok)
            except Exception:
                pass
    if ok == 0:
        return 0, f"Egyetlen fájl sem ment át. {elso_hiba or ''}".strip()
    return ok, None


def _mappa_szuro(csak_hang, konyv_is):
    """A mappából KÜLDENDŐ kiterjesztések halmaza (kisbetűvel), vagy None = minden
    fájl. `konyv_is` esetén a hangfájlok MELLETT a normál könyvfájlok is mennek."""
    if konyv_is:
        return {e.lower() for e in KULDHETO_MAPPA_KITERJESZTESEK}
    if csak_hang:
        return {e.lower() for e in HANG_KITERJESZTESEK}
    return None


def _mappa_fa(mappa_ut, csak_hang=True, konyv_is=False):
    """A mappa fájljai REKURZÍVAN: (teljes_út, relatív_almappa perjelekkel). Így a
    kötet-almappák (pl. „1. kötet") szerkezete átküldhető és megőrizhető. A
    `konyv_is=True` a hangfájlok mellett a normál könyveket is beveszi."""
    szuro = _mappa_szuro(csak_hang, konyv_is)
    parok = []
    for gyoker, _dirs, fajlok in os.walk(mappa_ut):
        for fn in fajlok:
            if szuro is not None and os.path.splitext(fn)[1].lower() not in szuro:
                continue
            reldir = os.path.relpath(gyoker, mappa_ut).replace("\\", "/")
            if reldir == ".":
                reldir = ""
            parok.append((os.path.join(gyoker, fn), reldir))
    parok.sort(key=lambda pr: (pr[1].lower(), os.path.basename(pr[0]).lower()))
    return parok


def mappa_kuld(ip, pin, mappa_ut, dest=DEST_KONYV, port=ALAP_PORT, csak_hang=True,
               konyv_is=False, on_progress=None):
    """Egy egész mappa átküldése a telefonra – REKURZÍVAN, a kötet-almappák
    szerkezetét megőrizve (a telefonon a mappa NEVÉVEL kezdődő almappába kerül,
    az almappákkal együtt). `konyv_is=True` esetén nem csak hangoskönyvet, hanem
    normál könyveket (epub, txt, pdf, docx…) is átküld. Fájlonként megy, hogy a
    haladás jelezhető legyen. Visszaad: (darab, hiba|None)."""
    mappa_ut = (mappa_ut or "").rstrip("/\\")
    nev = os.path.basename(mappa_ut)
    parok = _mappa_fa(mappa_ut, csak_hang=csak_hang, konyv_is=konyv_is)
    if not parok:
        if konyv_is:
            return 0, ("Ebben a mappában (és almappáiban) nincs küldhető könyv "
                       "vagy hangfájl.")
        return 0, ("Ebben a mappában (és almappáiban) nincs küldhető hangfájl."
                   if csak_hang else "Ez a mappa üres.")
    n = len(parok)
    ok = 0
    elso_hiba = None
    for i, (teljes, reldir) in enumerate(parok, 1):
        subdir = nev + ("/" + reldir if reldir else "")
        try:
            db, hiba = feltolt(ip, pin, [teljes], dest=dest, port=port,
                               subdir=subdir)
        except Exception as ex:
            db, hiba = 0, str(ex)
        if db:
            ok += 1
        elif elso_hiba is None:
            elso_hiba = hiba
        if on_progress:
            try:
                on_progress(i, n, os.path.basename(teljes), ok)
            except Exception:
                pass
    if ok == 0:
        return 0, f"Egyetlen fájl sem ment át. {elso_hiba or ''}".strip()
    return ok, None


# ---- a telefon könyvei (az Átjáró ellenőrzi, megvan-e a könyv) ------------

def telefon_konyvek_le(ip, pin, port=ALAP_PORT, timeout=20):
    """GET /sync/books – a telefonon lévő könyvek nevei. Visszaad:
    {"books": [...], "audiobooks": [...]} (üres, ha a telefon még nem tudja)."""
    if requests is None:
        raise RuntimeError("A hálózati modul (requests) nem érhető el.")
    url = portal_url(ip, port) + "/sync/books"
    try:
        r = requests.get(url, params=_pin(pin), timeout=timeout)
        r.raise_for_status()
        d = r.json()
        if isinstance(d, dict):
            return {"books": list(d.get("books", []) or []),
                    "audiobooks": list(d.get("audiobooks", []) or [])}
    except Exception:
        pass
    return {"books": [], "audiobooks": []}


def pc_hangoskonyv_polc():
    """A PC hangoskönyv-polca (a Könyvek modul audiobook_library.json-ja):
    {fájlnév-kulcs: {"path":..., "title":..., "is_dir":...}}. Ebből tudjuk, hol
    van helyben a hangoskönyv, ha át kell küldeni a telefonra."""
    fajl = store.CONFIG_DIR / "audiobook_library.json"
    ki = {}
    for it in (store.load_json(fajl, []) or []):
        if isinstance(it, dict) and it.get("key"):
            ki[str(it["key"]).lower()] = it
    return ki


# ---- backup letöltése (a jövőbeni szinkronhoz) ---------------------------

def backup_letolt(ip, pin, port=ALAP_PORT, timeout=30):
    """A telefon teljes beállítás-mentése (JSON) a portál /backup/download
    route-járól. Ebből olvashatók ki később a gyógyszer-emlékeztetők és a
    könyvjelzők/olvasási pozíciók."""
    if requests is None:
        raise RuntimeError("A hálózati modul (requests) nem érhető el.")
    url = portal_url(ip, port) + "/backup/download"
    r = requests.get(url, params=_pin(pin), timeout=timeout)
    r.raise_for_status()
    return r.json()


def _pref_ertek(cella):
    """A backup típusos cellája ({"t":"s|i|l|f|b|ss","v":...}) → nyers érték."""
    if not isinstance(cella, dict):
        return cella
    return cella.get("v")


def kigyujt_gyogyszerek(backup):
    """A backup-JSON-ból kiszedi a gyógyszer-emlékeztetők listáját (ha van)."""
    fajlok = (backup or {}).get("files", {})
    superdl = fajlok.get("superdl", {})
    nyers = _pref_ertek(superdl.get("medication_reminders"))
    try:
        return json.loads(nyers) if isinstance(nyers, str) else (nyers or [])
    except (ValueError, TypeError):
        return []


def kigyujt_konyv_poziciok(backup):
    """A backup-JSON-ból kiszedi a könyv → karakter-offset pozíciókat."""
    fajlok = (backup or {}).get("files", {})
    superdl = fajlok.get("superdl", {})
    nyers = _pref_ertek(superdl.get("book_positions"))
    try:
        return json.loads(nyers) if isinstance(nyers, str) else (nyers or {})
    except (ValueError, TypeError):
        return {}


# ---- gyógyszer-emlékeztetők → szervező-esemény (tiszta átalakítás) --------

def gyogyszer_aktivak(gyogyszerek):
    """Csak a bekapcsolt (enabled) emlékeztetők – a kikapcsoltakat kihagyjuk."""
    ki = []
    for g in gyogyszerek or []:
        if not isinstance(g, dict):
            continue
        if g.get("enabled", True):        # ha nincs mező, alapból aktív
            ki.append(g)
    return ki


def gyogyszer_esemeny_adat(g, mai_datum):
    """Egy telefon-gyógyszer emlékeztető → szervező-eseménnyé alakítható NYERS
    adat (dict). A `mai_datum` ISO 'ÉÉÉÉ-HH-NN' (a hívó adja, hogy a mag ne
    függjön az órától/dátumtól). A napi ciklus 'daily' ismétléssé válik."""
    try:
        ora = int(g.get("hour", 0) or 0)
    except (ValueError, TypeError):
        ora = 0
    try:
        perc = int(g.get("minute", 0) or 0)
    except (ValueError, TypeError):
        perc = 0
    ora = max(0, min(23, ora))
    perc = max(0, min(59, perc))
    naponta = str(g.get("cycleType", "DAILY")).upper() == "DAILY"
    nev = (g.get("name") or "Gyógyszer").strip() or "Gyógyszer"
    return {
        "title": nev,
        "date": mai_datum,
        "time": f"{ora:02d}:{perc:02d}",
        "repeat": "daily" if naponta else "none",
        "note": "Telefonról szinkronizált gyógyszer-emlékeztető",
    }


# ---- könyv-pozíciók egyeztetése a PC-könyvtárral (fájlnév szerint) --------

def _fajlnev(ut):
    return os.path.basename((ut or "").replace("\\", "/")).strip().lower()


# ---- naptár: telefon (Google) → PC Szervezés ICS-feliratkozással ---------

# a Google Naptár beállítás-oldala, ahol a titkos iCal-cím kimásolható
GOOGLE_NAPTAR_BEALLITAS_URL = "https://calendar.google.com/calendar/u/0/r/settings"


def normalizal_ical_url(url):
    """A beillesztett naptár-cím rendbetétele: a webcal:// séma https://-re,
    körbevágás."""
    u = (url or "").strip()
    if u.lower().startswith("webcal://"):
        u = "https://" + u[len("webcal://"):]
    return u


def ical_url_ok(url):
    """Elfogadható-e ICS/iCal feliratkozási cím? (Google/Outlook/iCloud privát
    .ics link.)"""
    u = normalizal_ical_url(url).lower()
    if not (u.startswith("https://") or u.startswith("http://")):
        return False
    return (u.endswith(".ics") or "/ical/" in u or "format=ical" in u
            or "/feed/" in u)


def naptar_nev_javaslat(url):
    """Emberi név a feliratkozáshoz. FONTOS: a titkos részt NEM tartalmazza –
    a privát iCal-cím maga a hozzáférési kulcs a naptárhoz."""
    u = normalizal_ical_url(url)
    try:
        import urllib.parse
        if "/ical/" in u:
            azon = urllib.parse.unquote(u.split("/ical/", 1)[1].split("/")[0])
            if "@" in azon:
                return f"Telefon naptár ({azon})"
    except Exception:
        pass
    return "Telefon naptár (Google)"


def konyv_egyezes(poziciok, pc_utak):
    """A telefon könyv-pozícióit (android_út → offset) összeveti a PC-könyvtár
    útjaival, FÁJLNÉV szerint (az abszolút utak eszközönként mások). Visszaad
    listát: [{nev, telefon_offset, pc_ut vagy None}] – a `pc_ut` akkor van
    kitöltve, ha ugyanaz a fájlnév megvan a PC-könyvtárban is."""
    pc_index = {}
    for ut in pc_utak or []:
        pc_index.setdefault(_fajlnev(ut), ut)
    ki = []
    for android_ut, offset in (poziciok or {}).items():
        nev = os.path.basename((android_ut or "").replace("\\", "/")) or android_ut
        try:
            off = int(offset)
        except (ValueError, TypeError):
            off = 0
        ki.append({"nev": nev, "telefon_offset": off,
                   "pc_ut": pc_index.get(_fajlnev(android_ut))})
    ki.sort(key=lambda r: r["nev"].lower())
    return ki


# ---- könyvjelző-szinkron (kétirányú) -------------------------------------
# A telefon (Android) könyvjelző-alakja: {id, bookPath, bookTitle, charOffset,
# preview, createdAt}. A PC-alak (superdl.bookmarks.Bookmark rekord): {book,
# title, char, preview, created, label}. Az azonosítás FÁJLNÉV szerint megy.

def android_konyvjelzo_be(lista):
    """Android könyvjelző-tömb → PC könyvjelző-rekord dict lista (fájlnév-kulccsal)."""
    ki = []
    for b in lista or []:
        if not isinstance(b, dict):
            continue
        ut = b.get("bookPath", "")
        nev = os.path.basename((ut or "").replace("\\", "/")) or ut
        try:
            off = int(b.get("charOffset", 0) or 0)
        except (ValueError, TypeError):
            off = 0
        try:
            cre = int(b.get("createdAt", 0) or 0)
        except (ValueError, TypeError):
            cre = 0
        try:
            pms = int(b.get("posMs", 0) or 0)
        except (ValueError, TypeError):
            pms = 0
        ki.append({"book": nev, "title": str(b.get("bookTitle", "")),
                   "char": off, "preview": str(b.get("preview", "")),
                   "created": cre, "label": "",
                   "kind": str(b.get("kind", "text") or "text"),
                   "pos_ms": pms,
                   "track": os.path.basename(
                       (b.get("track", "") or "").replace("\\", "/"))})
    return ki


def pc_konyvjelzo_androidra(rekordok):
    """PC könyvjelző-rekordok → Android könyvjelző-tömb. A telefon a FÁJLNEVET
    kapja bookPath-ként; a telefon oldali összefésülés a fájlnév alapján a
    valódi telefon-úthoz igazítja."""
    ki = []
    for r in rekordok or []:
        try:
            off = int(r.get("char", 0) or 0)
        except (ValueError, TypeError):
            off = 0
        try:
            cre = int(r.get("created", 0) or 0)
        except (ValueError, TypeError):
            cre = 0
        try:
            pms = int(r.get("pos_ms", 0) or 0)
        except (ValueError, TypeError):
            pms = 0
        ki.append({"bookPath": r.get("book", ""),
                   "bookTitle": r.get("title", ""),
                   "charOffset": off, "preview": r.get("preview", ""),
                   "createdAt": cre,
                   "kind": r.get("kind", "text") or "text",
                   "posMs": pms, "track": r.get("track", "")})
    return ki


def konyvjelzok_le(ip, pin, port=ALAP_PORT, timeout=30):
    """GET /sync/bookmarks – a telefon könyvjelző-tömbje (Android-alak)."""
    if requests is None:
        raise RuntimeError("A hálózati modul (requests) nem érhető el.")
    url = portal_url(ip, port) + "/sync/bookmarks"
    r = requests.get(url, params=_pin(pin), timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list):
        return data
    return data.get("bookmarks", []) if isinstance(data, dict) else []


def konyvjelzok_fel(ip, pin, android_lista, port=ALAP_PORT, timeout=30):
    """POST /sync/bookmarks – könyvjelzők a telefonra (JSON tömb). Visszaad: a
    telefon válasz-JSON-ja (pl. {added, total}) vagy None."""
    if requests is None:
        raise RuntimeError("A hálózati modul (requests) nem érhető el.")
    url = portal_url(ip, port) + "/sync/bookmarks"
    r = requests.post(url, params=_pin(pin), json=android_lista, timeout=timeout)
    r.raise_for_status()
    try:
        return r.json()
    except ValueError:
        return None
