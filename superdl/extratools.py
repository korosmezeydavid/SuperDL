"""Külső konverter- és OCR-eszközök: észlelés és igény szerinti letöltés.

A nagy külső eszközöket NEM sütjük az exébe (lean marad), hanem:
  • Pandoc – gazdag dokumentum-konverzió (RTF, ODT, Markdown, FB2, DOCX, EPUB,
    HTML). Igény szerint LETÖLTHETŐ a hivatalos GitHub-kiadásból a
    ~/.superdl/bin mappába.
  • Calibre (ebook-convert) és LibreOffice (soffice) – csak ÉSZLELÉS (nagy
    telepítők, a felhasználó telepíti); ha megvannak, MOBI/PDF/DOC konverzióra
    használjuk.
  • Tesseract – offline OCR; észlelés (PATH vagy ~/.superdl/bin).
"""

import hashlib
import io
import json
import os
import shutil
import sys
import threading
import urllib.request
import uuid
import zipfile
from pathlib import Path

BIN = Path.home() / ".superdl" / "bin"
UA = {"User-Agent": "SuperDL-tools"}
_lock = threading.Lock()

# A Tesseract-csomag (motor + magyar/angol nyelvi adat) a SAJÁT SuperDL-
# kiadásból tölthető le. A SHA-256-ot a csomag elkészültekor töltjük ki; amíg
# ÜRES, NEM töltünk le ellenőrizetlen binárist (integritás-elv).
_TESSERACT_ASSET = "tesseract-portable-hu-en.zip"
_TESSERACT_SHA256 = ""


def _meipass(name: str) -> str | None:
    mp = getattr(sys, "_MEIPASS", None)
    if mp and (Path(mp) / name).is_file():
        return str(Path(mp) / name)
    return None


def find_pandoc() -> str | None:
    c = BIN / "pandoc.exe"
    if c.is_file():
        return str(c)
    return _meipass("pandoc.exe") or shutil.which("pandoc")


def find_calibre() -> str | None:
    """Calibre ebook-convert (mobi/azw3/pdf/doc) – csak ha telepítve van."""
    return shutil.which("ebook-convert")


def find_libreoffice() -> str | None:
    """LibreOffice/OpenOffice soffice (doc/pdf) – csak ha telepítve van."""
    p = shutil.which("soffice")
    if p:
        return p
    for c in (r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if Path(c).is_file():
            return c
    return None


def find_tesseract() -> str | None:
    """Tesseract OCR – ~/.superdl/bin/tesseract/ alól vagy a PATH-ról."""
    c = BIN / "tesseract" / "tesseract.exe"
    if c.is_file():
        return str(c)
    for c2 in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
               r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
        if Path(c2).is_file():
            return c2
    return shutil.which("tesseract")


def _download(url: str, progress=None) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r:
        total = int(r.headers.get("Content-Length", 0) or 0)
        buf = bytearray()
        while True:
            ch = r.read(262144)
            if not ch:
                break
            buf += ch
            if progress:
                progress(len(buf), total)
    return bytes(buf)


# RÖGZÍTETT Pandoc-verzió: a korábbi „latest" miatt a telepítés NEM volt
# reprodukálható (gépenként/időben más bináris jöhetett). [DOCCONVERT-SUPPLY-001]
_PANDOC_VERSION = "3.1.11"
# A hivatalos csomag SHA-256-ja. Ha KI VAN TÖLTVE, kötelezően ellenőrizzük, és
# eltérés esetén NEM telepítünk (a Tesseractnál bevált elv). Üresen hagyva a
# telepítés megtörténik, de HITELESÍTETLENKÉNT jelezzük a felhasználónak.
_PANDOC_SHA256 = ""

# Az utolsó eszköz-telepítési hiba/figyelmeztetés – a néma `return None` helyett
# a felület meg tudja mondani, MI a baj. [Herman Tibi OCR-P1-12]
last_tool_error = ""
last_tool_warning = ""


def _pandoc_url(version: str = _PANDOC_VERSION) -> str:
    """A RÖGZÍTETT verzió hivatalos Windows-csomagja (nem «latest»)."""
    return (f"https://github.com/jgm/pandoc/releases/download/{version}/"
            f"pandoc-{version}-windows-x86_64.zip")


def ensure_pandoc(progress=None) -> str | None:
    """A pandoc.exe elérési útja; ha nincs, letölti a RÖGZÍTETT verziót (~40 MB),
    SHA-256-tal ellenőrizve (ha ismert), és ATOMIKUSAN telepíti.

    Hiba esetén None, de az okot a `last_tool_error` megmondja (korábban minden
    kivétel némán elnyelődött, így a hiba nem volt diagnosztizálható)."""
    global last_tool_error, last_tool_warning
    p = find_pandoc()
    if p:
        return p
    with _lock:
        p = find_pandoc()
        if p:
            return p
        last_tool_error = last_tool_warning = ""
        url = _pandoc_url()
        try:
            data = _download(url, progress)
        except Exception as e:
            last_tool_error = (f"A Pandoc letöltése nem sikerült ({type(e).__name__}). "
                               "Ellenőrizd az internetkapcsolatot.")
            return None
        # INTEGRITÁS: ha ismerjük a hivatalos ujjlenyomatot, kötelező az egyezés
        digest = hashlib.sha256(data).hexdigest()
        if _PANDOC_SHA256:
            if digest.lower() != _PANDOC_SHA256.lower():
                last_tool_error = (
                    "A letöltött Pandoc-csomag ELLENŐRZÉSE MEGBUKOTT "
                    "(a fájl nem egyezik a hivatalos ujjlenyomattal), ezért NEM "
                    "telepítettem. Próbáld később, vagy telepítsd kézzel.")
                return None
        else:
            last_tool_warning = (
                "A Pandoc csomagjához nincs beépített ujjlenyomat, ezért a "
                "hitelességét nem tudtam ellenőrizni.")
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
            forras = next((n for n in z.namelist()
                           if n.lower().endswith("pandoc.exe")), "")
            if not forras:
                last_tool_error = "A letöltött csomagban nincs pandoc.exe."
                return None
            BIN.mkdir(parents=True, exist_ok=True)
            cel = BIN / "pandoc.exe"
            # ATOMIKUS telepítés: előbb ideiglenes fájlba, majd csere – így egy
            # megszakadt letöltés nem hagy sérült exét a helyén.
            tmp = BIN / f"pandoc.{uuid.uuid4().hex[:8]}.part.exe"
            try:
                with z.open(forras) as s, open(tmp, "wb") as d:
                    shutil.copyfileobj(s, d)
                os.replace(tmp, cel)
            finally:
                try:
                    if tmp.exists():
                        tmp.unlink()
                except OSError:
                    pass
            return str(cel)
        except zipfile.BadZipFile:
            last_tool_error = "A letöltött Pandoc-csomag sérült (hibás ZIP)."
        except PermissionError:
            last_tool_error = ("A Pandoc telepítéséhez nincs jogosultság a "
                               f"{BIN} mappához.")
        except OSError as e:
            last_tool_error = f"A Pandoc telepítése nem sikerült: {e}"
        return None


def _superdl_repo() -> str:
    try:
        from . import selfupdate
        return selfupdate.get_repo()
    except Exception:
        return "korosmezeydavid/SuperDL"


def _tesseract_asset_url() -> str | None:
    """A Tesseract-csomag letöltési URL-je a SAJÁT SuperDL-kiadásokból (az
    asset nevére keresve). None, ha még nincs feltöltve."""
    repo = _superdl_repo()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases?per_page=30", headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            releases = json.load(r)
    except Exception:
        return None
    for rel in releases:
        for a in rel.get("assets", []):
            if a.get("name") == _TESSERACT_ASSET:
                return a.get("browser_download_url")
    return None


def _extract_zip_to(data: bytes, dest: Path) -> None:
    """A ZIP kicsomagolása a `dest` mappába, egyetlen közös felső mappát
    lehántva (ha minden bejegyzés azonos mappa alatt van). Útvonal-bejárás
    (zip-slip) ellen védve."""
    z = zipfile.ZipFile(io.BytesIO(data))
    names = [n for n in z.namelist() if not n.endswith("/")]
    tops = {n.split("/", 1)[0] for n in names if "/" in n}
    strip = next(iter(tops)) + "/" if (len(tops) == 1
                                       and all("/" in n for n in names)) else ""
    dest.mkdir(parents=True, exist_ok=True)
    base = dest.resolve()
    for n in names:
        rel = n[len(strip):] if strip and n.startswith(strip) else n
        if not rel:
            continue
        target = (dest / rel).resolve()
        if not target.is_relative_to(base):   # zip-slip (pontos befoglalás)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with z.open(n) as s, open(target, "wb") as d:
            shutil.copyfileobj(s, d)


def ensure_tesseract(progress=None) -> str | None:
    """A tesseract.exe elérési útja; ha nincs, LETÖLTI a saját SuperDL-kiadás
    Tesseract-csomagjából (motor + magyar/angol nyelvi adat) a
    ~/.superdl/bin/tesseract mappába, SHA-256-tal ellenőrizve. Hiba, hiányzó
    csomag, vagy (még) ki nem töltött hivatalos SHA-256 esetén None."""
    p = find_tesseract()
    if p:
        return p
    if not _TESSERACT_SHA256:
        return None            # nincs hitelesített csomag → nem töltünk le
    with _lock:
        p = find_tesseract()
        if p:
            return p
        url = _tesseract_asset_url()
        if not url:
            return None
        try:
            data = _download(url, progress)
            if hashlib.sha256(data).hexdigest().lower() != _TESSERACT_SHA256.lower():
                return None    # sérült/manipulált csomag → nem telepítjük
            _extract_zip_to(data, BIN / "tesseract")
        except Exception:
            return None
        return find_tesseract()
