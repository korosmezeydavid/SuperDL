"""Frissítéskezelő: a letöltőmotorok (yt-dlp, aria2) verzióinak
ellenőrzése és frissítése.

A frissítések a felhasználó saját mappájába kerülnek (~/.superdl/bin), így
a program magját nem írják felül, és rendszergazdai jog sem kell hozzájuk:

  ~/.superdl/bin/ytdlp/yt_dlp/   - a frissített yt-dlp (a betöltési útvonal
                                   elejére kerül, lásd a csomag __init__.py-t)
  ~/.superdl/bin/aria2c.exe      - a frissített aria2 (a torrent.py ezt
                                   részesíti előnyben a beágyazottal szemben)

Csak a hivatalos forrásokat használja: a yt-dlp-t a PyPI-ról, az aria2-t a
projekt GitHub-kiadásaiból.
"""

import io
import json
import re
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

CONFIG_BIN = Path.home() / ".superdl" / "bin"
YTDLP_DIR = CONFIG_BIN / "ytdlp"
ARIA2_BUNDLED = "1.37.0"
UA = {"User-Agent": "SuperDL-updater"}


# ---- letöltés-segédek -------------------------------------------------

def _open(url: str, timeout: int = 30):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout)


def _get_json(url: str):
    with _open(url) as r:
        return json.load(r)


def download_bytes(url: str, progress=None) -> bytes:
    with _open(url, timeout=60) as r:
        total = int(r.headers.get("Content-Length", 0) or 0)
        buf = bytearray()
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            buf += chunk
            if progress and total:
                progress(len(buf) / total)
    return bytes(buf)


# ---- verziók ----------------------------------------------------------

def _ver_tuple(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v))


def is_newer(latest: str, current: str) -> bool:
    try:
        return _ver_tuple(latest) > _ver_tuple(current)
    except Exception:
        return latest != current


def effective_ytdlp_version() -> str:
    """A ténylegesen használt yt-dlp verziója (frissített, ha van)."""
    marker = YTDLP_DIR / "INSTALLED_VERSION"
    if marker.exists():
        try:
            return marker.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    try:
        import yt_dlp
        return yt_dlp.version.__version__
    except Exception:
        return "?"


def effective_aria2_version() -> str:
    exe = CONFIG_BIN / "aria2c.exe"
    if exe.exists():
        try:
            out = subprocess.run(
                [str(exe), "--version"], capture_output=True, text=True,
                timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            m = re.search(r"aria2 version ([\d.]+)", out)
            if m:
                return m.group(1)
        except Exception:
            pass
    return ARIA2_BUNDLED


def latest_ytdlp() -> tuple[str, str | None]:
    d = _get_json("https://pypi.org/pypi/yt-dlp/json")
    ver = d["info"]["version"]
    whl = None
    for f in d["releases"].get(ver, []):
        if f["filename"].endswith("py3-none-any.whl"):
            whl = f["url"]
            break
    return ver, whl


def latest_aria2() -> tuple[str, str | None]:
    d = _get_json("https://api.github.com/repos/aria2/aria2/releases/latest")
    ver = d["tag_name"].replace("release-", "")
    asset = next((a["browser_download_url"] for a in d.get("assets", [])
                  if a["name"].endswith("win-64bit-build1.zip")), None)
    return ver, asset


# ---- ellenőrzés -------------------------------------------------------

def check_updates() -> list[dict]:
    """Mindkét motor állapota: aktuális és legfrissebb verzió.
    Hálózati hiba esetén az adott motornál 'latest' = None."""
    out = []
    cur_yt = effective_ytdlp_version()
    try:
        lat_yt, _ = latest_ytdlp()
    except Exception:
        lat_yt = None
    out.append({"key": "ytdlp", "name": "yt-dlp (médialetöltő motor)",
                "current": cur_yt, "latest": lat_yt,
                "update": bool(lat_yt and is_newer(lat_yt, cur_yt))})

    cur_ar = effective_aria2_version()
    try:
        lat_ar, _ = latest_aria2()
    except Exception:
        lat_ar = None
    out.append({"key": "aria2", "name": "aria2 (torrent motor)",
                "current": cur_ar, "latest": lat_ar,
                "update": bool(lat_ar and is_newer(lat_ar, cur_ar))})
    return out


# ---- frissítés --------------------------------------------------------

def update_ytdlp(progress=None) -> str:
    ver, whl = latest_ytdlp()
    if not whl:
        raise RuntimeError("Nem található yt-dlp csomag a PyPI-n.")
    data = download_bytes(whl, progress)
    z = zipfile.ZipFile(io.BytesIO(data))
    tmp = CONFIG_BIN / "ytdlp.new"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    for name in z.namelist():
        if name.startswith("yt_dlp/"):
            z.extract(name, tmp)
    shutil.rmtree(YTDLP_DIR, ignore_errors=True)
    shutil.move(str(tmp), str(YTDLP_DIR))
    (YTDLP_DIR / "INSTALLED_VERSION").write_text(ver, encoding="utf-8")
    return ver


def update_aria2(progress=None) -> str:
    ver, asset = latest_aria2()
    if not asset:
        raise RuntimeError("Nem található aria2 letöltés.")
    data = download_bytes(asset, progress)
    z = zipfile.ZipFile(io.BytesIO(data))
    inner = next(n for n in z.namelist() if n.endswith("aria2c.exe"))
    CONFIG_BIN.mkdir(parents=True, exist_ok=True)
    new = CONFIG_BIN / "aria2c.exe.new"
    with z.open(inner) as src, open(new, "wb") as dst:
        shutil.copyfileobj(src, dst)
    try:
        new.replace(CONFIG_BIN / "aria2c.exe")
    except PermissionError:
        raise RuntimeError("Az aria2 jelenleg fut. Zárd be a futó "
                           "torrenteket, majd próbáld újra.")
    return ver
