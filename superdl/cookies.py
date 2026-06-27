"""A felhasználó által exportált cookies.txt előkészítése a yt-dlp-hez.

Sok böngésző-kiegészítő olyan cookies.txt-t ment, amit a yt-dlp elutasít
(„does not look like a Netscape format cookies file"): hiányzik a kötelező
fejléc, BOM van a fájl elején, vagy a kiegészítő JSON formátumban exportál.
Ez a modul egy NORMALIZÁLT másolatot készít a fájlból (az eredetit nem
módosítja), és érthető, magyar üzenetű hibát ad, ha a tartalom tényleg nem
használható.
"""

import os
import tempfile
from pathlib import Path


def available_browsers() -> list[str]:
    """A gépen MEGTALÁLHATÓ böngészők yt-dlp-neve, ésszerű sorrendben.

    A YouTube bot-ellenőrzésénél ezekből próbálunk SÜTIT kiolvasni – a
    felhasználó SAJÁT, bejelentkezett munkamenete a SAJÁT letöltéseihez
    (jogtiszta). A Chromium-alapúak elöl (oda szokás bejelentkezni a
    YouTube-ra); ha egy nem dekódolható (App-Bound titkosítás), a hívó a
    következőre lép."""
    local = os.environ.get("LOCALAPPDATA", "")
    roaming = os.environ.get("APPDATA", "")
    candidates = [
        ("chrome",   Path(local) / "Google" / "Chrome" / "User Data"),
        ("edge",     Path(local) / "Microsoft" / "Edge" / "User Data"),
        ("brave",    Path(local) / "BraveSoftware" / "Brave-Browser" / "User Data"),
        ("vivaldi",  Path(local) / "Vivaldi" / "User Data"),
        ("chromium", Path(local) / "Chromium" / "User Data"),
        ("opera",    Path(roaming) / "Opera Software" / "Opera Stable"),
        ("firefox",  Path(roaming) / "Mozilla" / "Firefox" / "Profiles"),
    ]
    out: list[str] = []
    for name, path in candidates:
        try:
            if path.exists():
                out.append(name)
        except OSError:
            pass
    return out


NETSCAPE_HEADER = "# Netscape HTTP Cookie File"
_BOM = b"\xef\xbb\xbf"
_GET_COOKIES_HINT = ("Ajánlott kiegészítő, ami helyes formátumot ad: "
                     "„Get cookies.txt LOCALLY” (Chrome/Edge), illetve "
                     "„cookies.txt” (Firefox).")


class CookieFileError(Exception):
    """Érthető, magyar üzenetű hiba a hibás/nem támogatott cookies.txt-re."""


def _looks_like_header(line: str) -> bool:
    s = line.strip().lower()
    return s.startswith("# netscape") or s.startswith("# http cookie")


def prepare_cookiefile(path: str) -> str:
    """Beolvassa és szükség szerint normalizálja a cookies.txt-t, majd egy
    biztosan yt-dlp-kompatibilis fájl útvonalát adja vissza. Ha a tartalom
    nem menthető (JSON-export, üres, nem Netscape-formátum), CookieFileError-t
    dob, érthető magyarázattal."""
    p = Path(path)
    if not p.is_file():
        raise CookieFileError(f"A megadott süti-fájl nem található: {path}")

    raw = p.read_bytes()
    had_bom = raw.startswith(_BOM)
    if had_bom:
        raw = raw[len(_BOM):]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")

    stripped = text.lstrip()
    if stripped[:1] in ("[", "{"):
        raise CookieFileError(
            "A megadott fájl JSON formátumú, a SuperDL-nek viszont Netscape "
            "(cookies.txt) formátum kell. A kiegészítőben a „cookies.txt” / "
            "„Netscape” export-lehetőséget válaszd. " + _GET_COOKIES_HINT)

    lines = text.splitlines()
    data_lines = [ln for ln in lines
                  if ln.strip() and not ln.lstrip().startswith("#")]
    if not data_lines:
        raise CookieFileError(
            "A süti-fájl üres vagy nem tartalmaz sütiket. Jelentkezz be a "
            "böngésződben az oldalra (pl. YouTube), majd exportáld újra a "
            "sütiket. " + _GET_COOKIES_HINT)
    # a Netscape-sorok TAB-bal tagoltak (7 mező); ha sehol nincs tab, ez nem
    # az a formátum, amit a yt-dlp olvasni tud
    if not any("\t" in ln for ln in data_lines):
        raise CookieFileError(
            "A süti-fájl nem a várt Netscape (tabulátorral tagolt) formátum. "
            + _GET_COOKIES_HINT)

    has_header = any(_looks_like_header(ln) for ln in lines[:5])
    # ha már van fejléc ÉS nem volt BOM, az eredeti fájl jó – nem másolunk
    if has_header and not had_bom:
        return str(p)

    body = text if has_header else (NETSCAPE_HEADER + "\n\n" + text)
    out = Path(tempfile.gettempdir()) / "superdl_cookies.txt"
    out.write_text(body, encoding="utf-8")
    return str(out)
