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
import shutil
import sys
import threading
import urllib.request
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


def _latest_pandoc_url() -> str:
    req = urllib.request.Request(
        "https://api.github.com/repos/jgm/pandoc/releases/latest", headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    for a in d.get("assets", []):
        if a["name"].endswith("windows-x86_64.zip"):
            return a["browser_download_url"]
    raise RuntimeError("Nem található Windows Pandoc letöltés.")


def ensure_pandoc(progress=None) -> str | None:
    """A pandoc.exe elérési útja; ha nincs, letölti (~40 MB). Hiba esetén None."""
    p = find_pandoc()
    if p:
        return p
    with _lock:
        p = find_pandoc()
        if p:
            return p
        try:
            data = _download(_latest_pandoc_url(), progress)
            z = zipfile.ZipFile(io.BytesIO(data))
            BIN.mkdir(parents=True, exist_ok=True)
            for name in z.namelist():
                if name.lower().endswith("pandoc.exe"):
                    with z.open(name) as s, open(BIN / "pandoc.exe", "wb") as d:
                        shutil.copyfileobj(s, d)
                    return str(BIN / "pandoc.exe")
        except Exception:
            return None
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
