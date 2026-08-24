# -*- coding: utf-8 -*-
"""TELJES MENTÉS ÉS VISSZAÁLLÍTÁS – „költözés egy mozdulattal”.

Felhasználói kérés (2026-08-20): „teljes mentés… amiből minden is visszatölthető!
e-mailek, kulcsok, minden! Nyilván ez nem hagyja el a gépet, de a backup fájl
mindent is tartalmazzon… podcast-feliratkozások, YouTube-csatornák, könyvjelzők,
AI-kulcsok, e-mail jelszavak, naptár-bejegyzések, telepített modulok… hogy ha
például új gépre költözik a felhasználó, egy mozdulat legyen visszaállítani.”

MIÉRT KELL HOZZÁ JELSZÓ – ÉS MIÉRT KÖTELEZŐ?
A program a bizalmas adatokat (e-mail jelszavak, AI-kulcsok) a Windows saját
titkosításával (DPAPI) tárolja. Az így titkosított fájl CSAK azon a gépen és
CSAK azzal a felhasználóval fejthető vissza, ahol készült – ez jó védelem, de
költözésnél pont ezért használhatatlan: a másik gépen a fájl néma kacat lenne.

Ezért a mentés készítésekor a titkos részt visszafejtjük, és a TELJES csomagot
a felhasználó jelszavával titkosítjuk újra (AES-256-GCM, scrypt kulcsképzéssel).
Visszaállításkor a jelszó nyitja a csomagot, és a titkos rész az ÚJ gép saját
DPAPI-titkosításával kerül a helyére.

Ebből következik két szabály, amitől nem térünk el:
  • jelszó NÉLKÜL nem készül mentés (a fájl e-mail jelszavakat tartalmaz);
  • ha a titkosító réteg nem érhető el, INKÁBB NEM KÉSZÜL mentés, mint hogy
    nyílt szöveggel írjuk ki a jelszavakat.

A csomag SEHOVA nem megy: a felhasználó választja meg, hova mentse.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import time
import zipfile
from pathlib import Path

MAGIC = b"SUPERDL-MENTES\x01"
KITERJESZTES = ".sdlmentes"
MIN_JELSZO = 8

# A DPAPI-val titkosított fájlok: ezeket VISSZAFEJTVE tesszük a csomagba, és
# visszaállításkor az új gép saját titkosításával írjuk vissza.
TITKOS_FAJLOK = ("ai.json", "tts_keys.json", "ics_urls.json",
                 "mail_accounts.dat")

# Amit NEM mentünk: nagy és bármikor újratölthető (a mentés maradjon kicsi).
KIHAGYOTT_MAPPAK = ("bin", "forditomodellek", "gyorsitotar", "modules",
                    "play", "read", "speak", "__pycache__")
KIHAGYOTT_KITERJESZTESEK = (".bak", ".tmp", ".log", ".pyc", ".part")
KIHAGYOTT_FAJLOK = ("tvmusor_epg.xml", "queue_test.json", "osszeomlas.log",
                    "update.log")


def _config_dir() -> Path:
    from . import store
    return Path(store.CONFIG_DIR)


def _beallitas_fajl() -> Path:
    return Path.home() / ".superdl.json"


# ====================================================================
#  Titkosítás
# ====================================================================

def titkositas_elerheto() -> bool:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa
        return True
    except Exception:
        return False


def _kulcs(jelszo: str, so: bytes) -> bytes:
    """Jelszóból kulcs – scrypt-tel, hogy a jelszó próbálgatása DRÁGA legyen.

    A `maxmem` megadása kötelező: a beállított erősség ~32 megabájt memóriát
    kér, az OpenSSL alapértelmezett korlátja viszont pont ennyi, és e nélkül
    „memory limit exceeded" hibával áll meg."""
    return hashlib.scrypt(str(jelszo or "").encode("utf-8"), salt=so,
                          n=2 ** 15, r=8, p=1, dklen=32,
                          maxmem=128 * 1024 * 1024)


def _titkosit(adat: bytes, jelszo: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    so = os.urandom(16)
    nonce = os.urandom(12)
    aes = AESGCM(_kulcs(jelszo, so))
    return MAGIC + so + nonce + aes.encrypt(nonce, adat, MAGIC)


def _visszafejt(nyers: bytes, jelszo: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if not nyers.startswith(MAGIC):
        raise ValueError("Ez a fájl nem SuperDL-mentés.")
    so = nyers[len(MAGIC):len(MAGIC) + 16]
    nonce = nyers[len(MAGIC) + 16:len(MAGIC) + 28]
    test = nyers[len(MAGIC) + 28:]
    aes = AESGCM(_kulcs(jelszo, so))
    try:
        return aes.decrypt(nonce, test, MAGIC)
    except Exception:
        raise ValueError("Hibás jelszó, vagy sérült a mentés-fájl.")


# ====================================================================
#  Gyűjtés
# ====================================================================

def _mentendo(ut: Path, gyoker: Path) -> bool:
    rel = ut.relative_to(gyoker)
    if any(r in KIHAGYOTT_MAPPAK for r in rel.parts[:-1]):
        return False
    if rel.name in KIHAGYOTT_FAJLOK:
        return False
    if rel.suffix.lower() in KIHAGYOTT_KITERJESZTESEK:
        return False
    return True


def gyujtes(gyoker: Path = None) -> tuple:
    """(sima_fajlok, titkos_adatok, hiba_lista).

    `sima_fajlok`: {relatív_út: bájtok} – a nem bizalmas adatok.
    `titkos_adatok`: {fájlnév: szótár} – a DPAPI-ból VISSZAFEJTETT tartalom."""
    from . import store
    gyoker = Path(gyoker or _config_dir())
    sima, titkos, hibak = {}, {}, []
    if gyoker.is_dir():
        for ut in gyoker.rglob("*"):
            if not ut.is_file() or not _mentendo(ut, gyoker):
                continue
            nev = ut.relative_to(gyoker).as_posix()
            if ut.name in TITKOS_FAJLOK:
                continue                      # külön, visszafejtve kezeljük
            try:
                sima[nev] = ut.read_bytes()
            except OSError as ex:
                hibak.append("%s: %s" % (nev, ex))
    for nev in TITKOS_FAJLOK:
        ut = gyoker / nev
        if not ut.is_file():
            continue
        try:
            adat = store._load_secret_config(ut)
            if adat:
                titkos[nev] = adat
        except Exception as ex:
            hibak.append("%s (titkos): %s" % (nev, ex))
    return sima, titkos, hibak


def telepitett_modulok() -> list:
    """A telepített modulok azonosítója és verziója – hogy az új gépen a
    program vissza tudja tölteni őket a boltból."""
    ki = []
    mappa = _config_dir() / "modules"
    if not mappa.is_dir():
        return ki
    for m in sorted(mappa.iterdir()):
        manifest = m / "manifest.json"
        if not manifest.is_file():
            continue
        try:
            d = json.loads(manifest.read_text(encoding="utf-8"))
            ki.append({"id": d.get("id", m.name),
                       "nev": d.get("name", m.name),
                       "verzio": d.get("version", "")})
        except Exception:
            ki.append({"id": m.name, "nev": m.name, "verzio": ""})
    return ki


# ====================================================================
#  Mentés
# ====================================================================

def keszit(cel_ut: str, jelszo: str, gyoker: Path = None) -> dict:
    """Teljes mentés készítése. Visszaad: összegzés a felületnek."""
    if len(str(jelszo or "")) < MIN_JELSZO:
        raise ValueError(
            "A mentés e-mail jelszavakat és AI-kulcsokat is tartalmaz, ezért "
            "jelszó nélkül nem készíthető el. Legalább %d karakter kell."
            % MIN_JELSZO)
    if not titkositas_elerheto():
        raise RuntimeError(
            "A titkosító réteg nem érhető el ezen a gépen, ezért NEM készítek "
            "mentést – nyílt szövegben nem írom ki a jelszavaidat.")

    sima, titkos, hibak = gyujtes(gyoker)
    modulok = telepitett_modulok()
    beallitas = b""
    bf = _beallitas_fajl()
    if bf.is_file():
        try:
            beallitas = bf.read_bytes()
        except OSError as ex:
            hibak.append("beállítások: %s" % ex)

    meta = {
        "formatum": 1,
        "keszult": time.strftime("%Y-%m-%d %H:%M:%S"),
        "program": _verzio(),
        "fajlok": len(sima),
        "titkos_fajlok": sorted(titkos),
        "modulok": modulok,
    }

    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mentes.json", json.dumps(meta, ensure_ascii=False,
                                             indent=2))
        if beallitas:
            z.writestr("beallitasok/superdl.json", beallitas)
        for nev, adat in sima.items():
            z.writestr("adatok/" + nev, adat)
        for nev, adat in titkos.items():
            z.writestr("titkos/" + nev + ".json",
                       json.dumps(adat, ensure_ascii=False))

    nyers = _titkosit(puffer.getvalue(), jelszo)
    cel = Path(cel_ut)
    cel.parent.mkdir(parents=True, exist_ok=True)
    ideiglenes = cel.with_suffix(cel.suffix + ".uj")
    with open(ideiglenes, "wb") as f:
        f.write(nyers)
        f.flush()
        os.fsync(f.fileno())
    os.replace(ideiglenes, cel)
    return {"ut": str(cel), "meret": len(nyers), "fajlok": len(sima),
            "titkos": len(titkos), "modulok": len(modulok), "hibak": hibak,
            "meta": meta}


def _verzio() -> str:
    try:
        from . import __version__
        return str(__version__)
    except Exception:
        return "ismeretlen"


# ====================================================================
#  Olvasás és visszaállítás
# ====================================================================

def olvas(ut: str, jelszo: str) -> tuple:
    """(meta, zip-objektum) – a csomag megnyitása visszaállítás előtt."""
    nyers = Path(ut).read_bytes()
    csomag = _visszafejt(nyers, jelszo)
    z = zipfile.ZipFile(io.BytesIO(csomag))
    try:
        meta = json.loads(z.read("mentes.json").decode("utf-8"))
    except Exception:
        raise ValueError("A mentés-fájl sérült: hiányzik a leíró.")
    return meta, z


def elonezet(ut: str, jelszo: str) -> str:
    """Felolvasható összefoglaló arról, MI van a mentésben – visszaállítás
    ELŐTT. Vakon ez különösen fontos: lássa, mit fog felülírni."""
    meta, z = olvas(ut, jelszo)
    modulok = meta.get("modulok") or []
    sorok = ["Mentés készült: %s (SuperDL %s)"
             % (meta.get("keszult", "?"), meta.get("program", "?")),
             "%d adatfájl, %d bizalmas fájl (jelszavak, kulcsok)"
             % (meta.get("fajlok", 0), len(meta.get("titkos_fajlok") or []))]
    if modulok:
        sorok.append("%d telepített modul: %s"
                     % (len(modulok),
                        ", ".join(m.get("nev", m.get("id", ""))
                                  for m in modulok[:8])
                        + (" …" if len(modulok) > 8 else "")))
    return "\n".join(sorok)


def visszaallit(ut: str, jelszo: str, gyoker: Path = None,
                biztonsagi_masolat: bool = True) -> dict:
    """A mentés visszatöltése. A meglévő adatokról ELŐBB biztonsági másolat
    készül – visszaállítani is csak úgy szabad, hogy legyen visszaút."""
    from . import store
    gyoker = Path(gyoker or _config_dir())
    meta, z = olvas(ut, jelszo)

    mentett_regi = ""
    if biztonsagi_masolat and gyoker.is_dir():
        mentett_regi = str(gyoker.parent / (".superdl_elozo_%s.zip"
                                            % time.strftime("%Y%m%d_%H%M%S")))
        try:
            with zipfile.ZipFile(mentett_regi, "w",
                                 zipfile.ZIP_DEFLATED) as ki:
                for p in gyoker.rglob("*"):
                    if p.is_file() and _mentendo(p, gyoker):
                        ki.write(p, p.relative_to(gyoker).as_posix())
        except Exception:
            mentett_regi = ""

    gyoker.mkdir(parents=True, exist_ok=True)
    visszaallt, hibak = 0, []
    for nev in z.namelist():
        try:
            if nev == "mentes.json":
                continue
            if nev.startswith("beallitasok/"):
                _beallitas_fajl().write_bytes(z.read(nev))
                visszaallt += 1
            elif nev.startswith("adatok/"):
                cel = gyoker / nev[len("adatok/"):]
                if not _biztonsagos_ut(cel, gyoker):
                    hibak.append("gyanús útvonal: %s" % nev)
                    continue
                cel.parent.mkdir(parents=True, exist_ok=True)
                cel.write_bytes(z.read(nev))
                visszaallt += 1
            elif nev.startswith("titkos/"):
                fajlnev = nev[len("titkos/"):-len(".json")]
                adat = json.loads(z.read(nev).decode("utf-8"))
                # az ÚJ gép saját titkosításával írjuk vissza
                store.save_secret_json(gyoker / fajlnev, adat)
                visszaallt += 1
        except Exception as ex:
            hibak.append("%s: %s" % (nev, ex))
    return {"visszaallt": visszaallt, "hibak": hibak, "meta": meta,
            "modulok": meta.get("modulok") or [], "elozo": mentett_regi}


def _biztonsagos_ut(cel: Path, gyoker: Path) -> bool:
    """Védelem a csomagban elrejtett „../” útvonalak ellen."""
    try:
        return gyoker.resolve() in cel.resolve().parents
    except Exception:
        return False


def alap_fajlnev() -> str:
    return "SuperDL-mentes-%s%s" % (time.strftime("%Y-%m-%d"), KITERJESZTES)


def meret_szoveg(bajt: int) -> str:
    for egyseg, hatar in (("gigabájt", 1024 ** 3), ("megabájt", 1024 ** 2),
                          ("kilobájt", 1024)):
        if bajt >= hatar:
            return "%.1f %s" % (bajt / hatar, egyseg)
    return "%d bájt" % bajt
