"""Jelszóval védett, hitelesített Főnix-pajzs csomag."""

import hmac
import io
import os
import zipfile
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .csomag import fajlok_alatta

MAGIC = b"SUPERFILES-FONIX-1"
KEY_MAGIC = b"SUPERFILES-FONIX-2"
KEY_FILE_SIZE = 32
LIMIT = 32 * 1024 * 1024


def _kulcs(jelszo, salt, kulcsfajl=None):
    secret = jelszo.encode("utf-8")
    if kulcsfajl is not None:
        with Path(kulcsfajl).open("rb") as stream:
            key = stream.read(KEY_FILE_SIZE + 1)
        if len(key) != KEY_FILE_SIZE:
            raise ValueError("Érvénytelen Főnix-kulcsfájl.")
        secret = hmac.digest(key, b"Super Files Fonix 2 password:" + secret, "sha256")
    return Scrypt(salt=salt, length=32, n=2**17, r=8, p=1).derive(secret)


def kulcsfajl_keszit(cel):
    _uj_fajl(cel, os.urandom(KEY_FILE_SIZE))


def kulcsfajlos(forras):
    with Path(forras).open("rb") as stream:
        fej = stream.read(len(MAGIC))
    if fej not in (MAGIC, KEY_MAGIC):
        raise ValueError("Ismeretlen Főnix-pajzs csomag.")
    return fej == KEY_MAGIC


def _uj_fajl(cel, adat):
    with Path(cel).open("xb") as stream:
        try:
            stream.write(adat)
        except OSError:
            stream.close()
            Path(cel).unlink(missing_ok=True)
            raise


def keszit(forrasok, cel, jelszo, kulcsfajl=None):
    if len(jelszo) < 12:
        raise ValueError("Legalább 12 karakteres jelszót adj meg.")
    elemek = fajlok_alatta(forrasok)
    if not elemek:
        raise ValueError("Nincs becsomagolható fájl.")
    adat = io.BytesIO()
    osszes = 0
    nevek = set()
    with zipfile.ZipFile(adat, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for ut, nev in elemek:
            nev = nev.replace(chr(92), "/")
            if nev.casefold() in nevek:
                raise ValueError(f"Névütközés: {nev}")
            nevek.add(nev.casefold())
            with open(ut, "rb") as stream:
                tartalom = stream.read(LIMIT - osszes + 1)
            osszes += len(tartalom)
            if osszes > LIMIT:
                raise ValueError("Az első változat legfeljebb 32 MiB tartalmat kezel.")
            archive.writestr(nev, tartalom)
    if adat.tell() > LIMIT:
        raise ValueError("A csomag túllépte a 32 MiB korlátot.")
    salt = os.urandom(16)
    nonce = os.urandom(12)
    fej = (KEY_MAGIC if kulcsfajl is not None else MAGIC) + salt + nonce
    _uj_fajl(cel, fej + AESGCM(_kulcs(jelszo, salt, kulcsfajl)).encrypt(nonce, adat.getvalue(), fej))


def felold(forras, jelszo, kulcsfajl=None):
    fejmeret = len(MAGIC) + 28
    with Path(forras).open("rb") as stream:
        adat = stream.read(LIMIT + fejmeret + 17)
    if not adat.startswith((MAGIC, KEY_MAGIC)) or not fejmeret + 16 <= len(adat) <= LIMIT + fejmeret + 16:
        raise ValueError("Ismeretlen vagy sérült Főnix-pajzs csomag.")
    if adat.startswith(KEY_MAGIC) and kulcsfajl is None:
        raise ValueError("Ehhez a csomaghoz a jelszó és a kulcsfájl is szükséges.")
    if adat.startswith(MAGIC):
        kulcsfajl = None
    salt = adat[len(MAGIC):len(MAGIC) + 16]
    nonce = adat[len(MAGIC) + 16:fejmeret]
    try:
        tartalom = AESGCM(_kulcs(jelszo, salt, kulcsfajl)).decrypt(nonce, adat[fejmeret:], adat[:fejmeret])
    except InvalidTag as exc:
        raise ValueError("Hibás jelszó, hibás kulcsfájl vagy sérült csomag.") from exc
    return zipfile.ZipFile(io.BytesIO(tartalom))


def kiment(archive, tag, cel):
    with archive.open(tag) as stream:
        data = stream.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError("A fájl túllépte a 32 MiB korlátot.")
    _uj_fajl(cel, data)


def kiment_tobb(archive, tags, celmappa):
    """A kijelölt fájlok kimentése új nevek felülírása nélkül."""
    cel = Path(celmappa)
    if not cel.is_dir():
        raise ValueError("Válassz létező célmappát.")
    terv = {}
    for tag in tags:
        nev = tag.filename.replace(chr(92), "/").rsplit("/", 1)[-1]
        if (not nev or nev in (".", "..") or nev.endswith((" ", "."))
                or Path(nev).is_reserved()
                or any(ord(c) < 32 or c in '<>:"|?*' for c in nev)):
            raise ValueError(f"Nem használható Windows-fájlnév: {nev}")
        key = nev.casefold()
        if key in terv or os.path.lexists(cel / nev):
            raise FileExistsError(f"Névütközés: {nev}")
        terv[key] = (tag, cel / nev)
    keszek = []
    try:
        for tag, ut in terv.values():
            kiment(archive, tag, ut)
            keszek.append(ut)
    except Exception:
        for ut in keszek:
            ut.unlink(missing_ok=True)
        raise
    return len(keszek)
