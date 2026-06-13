"""Az ffmpeg átalakító biztosítása a formátum-konverzióhoz (pl. MP3).

A médialetöltésnél a hang/kép átkódolásához ffmpeg kell. Ha nincs a gépen,
a SuperDL igény esetén automatikusan letölti a felhasználó saját mappájába
(~/.superdl/bin), pont mint a többi motort. Egyszeri, kb. 104 MB.

Forrás: a gyan.dev hivatalos, statikus Windows-csomagja (release-essentials).
"""

import io
import shutil
import sys
import threading
import urllib.request
import zipfile
from pathlib import Path

FFMPEG_DIR = Path.home() / ".superdl" / "bin"
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
UA = {"User-Agent": "SuperDL-ffmpeg"}
_lock = threading.Lock()


def find_ffmpeg() -> str | None:
    """A használható ffmpeg.exe elérési útja, vagy None."""
    cand = FFMPEG_DIR / "ffmpeg.exe"
    if cand.is_file():
        return str(cand)
    if getattr(sys, "_MEIPASS", None):
        m = Path(sys._MEIPASS) / "ffmpeg.exe"
        if m.is_file():
            return str(m)
    return shutil.which("ffmpeg")


def ffmpeg_dir() -> str | None:
    """Az ffmpeg.exe-t tartalmazó mappa (yt-dlp ffmpeg_location), vagy None."""
    p = find_ffmpeg()
    return str(Path(p).parent) if p else None


def ensure_ffmpeg(progress=None) -> str | None:
    """Visszaadja az ffmpeg mappáját; ha nincs, letölti. progress(letöltve,
    összes) hívható a folyamatjelzéshez. Hiba esetén None."""
    existing = ffmpeg_dir()
    if existing:
        return existing
    with _lock:
        existing = ffmpeg_dir()           # közben más szál letölthette
        if existing:
            return existing
        try:
            data = _download(FFMPEG_URL, progress)
            z = zipfile.ZipFile(io.BytesIO(data))
            FFMPEG_DIR.mkdir(parents=True, exist_ok=True)
            got = False
            for name in z.namelist():
                low = name.lower()
                if low.endswith("/bin/ffmpeg.exe") or low.endswith("/bin/ffprobe.exe"):
                    target = FFMPEG_DIR / Path(name).name
                    with z.open(name) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    if low.endswith("ffmpeg.exe"):
                        got = True
            return str(FFMPEG_DIR) if got else None
        except Exception:
            return None


def _download(url: str, progress=None) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        total = int(r.headers.get("Content-Length", 0) or 0)
        buf = bytearray()
        while True:
            chunk = r.read(262144)
            if not chunk:
                break
            buf += chunk
            if progress:
                progress(len(buf), total)
    return bytes(buf)
