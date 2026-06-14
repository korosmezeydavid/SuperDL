"""Hang/videó → szöveg átirat előkészítése.

Az ffmpeg kivonja és tömöríti a beszédet (16 kHz, mono, 24 kbps MP3 – ez
beszédhez bőven elég, és kicsi). Rövid anyagot egy kéréssel írat le (ekkor
időbélyeges .srt felirat is kérhető); hosszú anyagot 30 perces darabokra vág,
és darabonként átírat, majd összefűzi (ekkor sima szöveg készül).

A tényleges leírást az `aiclient.transcribe` végzi (OpenAI Whisper, vagy ha
nincs OpenAI-kulcs, Gemini).
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

from . import aiclient
from .audioengine import _ffmpeg_exe

WORK_DIR = Path.home() / ".superdl" / "transcribe"
VIDEO_DIR = Path.home() / ".superdl" / "aivideo"
_YT_RE = re.compile(r"(youtube\.com/|youtu\.be/)", re.I)
SINGLE_LIMIT = 13_000_000      # efölött darabolunk (Gemini inline miatt óvatos)
SEGMENT_SECONDS = 1800         # 30 perces darabok


def _run(cmd):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(cmd, creationflags=flags, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=True)


def _prepare_dir() -> Path:
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR, ignore_errors=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    return WORK_DIR


def extract_audio(src: str, ff: str) -> str:
    out = str(WORK_DIR / "audio.mp3")
    _run([ff, "-nostdin", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
          "-b:a", "24k", "-loglevel", "error", out])
    return out


def split_audio(audio: str, ff: str) -> list[str]:
    pat = str(WORK_DIR / "part_%03d.mp3")
    _run([ff, "-nostdin", "-y", "-i", audio, "-f", "segment",
          "-segment_time", str(SEGMENT_SECONDS), "-c", "copy",
          "-loglevel", "error", pat])
    parts = sorted(str(p) for p in WORK_DIR.glob("part_*.mp3"))
    return parts or [audio]


def is_youtube(url: str) -> bool:
    return bool(_YT_RE.search(url or ""))


def download_video_temp(src_url: str, progress=None) -> str:
    """Nem-YouTube videó letöltése egy ideiglenes fájlba (Gemini-elemzéshez).
    Közepes felbontásra korlátoz, hogy gyors legyen a feltöltés."""
    import yt_dlp

    if VIDEO_DIR.exists():
        shutil.rmtree(VIDEO_DIR, ignore_errors=True)
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    if progress:
        progress("Videó letöltése az elemzéshez…")
    opts = {"quiet": True, "no_warnings": True, "noprogress": True,
            "outtmpl": str(VIDEO_DIR / "video.%(ext)s"),
            "format": "best[height<=480][ext=mp4]/best[ext=mp4]/best"}
    ff = _ffmpeg_exe()
    if ff:
        opts["ffmpeg_location"] = os.path.dirname(ff)
    with yt_dlp.YoutubeDL(opts) as y:
        y.extract_info(src_url, download=True)
    files = list(VIDEO_DIR.glob("video.*"))
    if not files:
        raise RuntimeError("a videó letöltése nem sikerült")
    return str(files[0])


def transcribe_media(src: str, *, srt: bool = False, progress=None) -> str:
    """Egy hang/videófájl átirata. `progress(üzenet)` a fő szálnak jelez."""
    def say(m):
        if progress:
            progress(m)

    ff = _ffmpeg_exe()
    if not ff:
        raise RuntimeError("Az ffmpeg nem érhető el (az átirathoz kell).")
    _prepare_dir()

    say("Hang kinyerése és tömörítése a fájlból…")
    audio = extract_audio(src, ff)
    size = os.path.getsize(audio)

    if size <= SINGLE_LIMIT:
        say("Felirat készítése…" if srt else "Átirat készítése…")
        return aiclient.transcribe(audio, srt=srt)

    # hosszú anyag: darabolva, sima szöveggel
    if srt:
        say("Hosszú anyag – sima szöveges átirat készül (a felirat csak "
            "rövidebb, kb. egyórás fájlhoz).")
    parts = split_audio(audio, ff)
    out = []
    for i, part in enumerate(parts, 1):
        say(f"Átirat: {i}. / {len(parts)} rész feldolgozása…")
        out.append(aiclient.transcribe(part, srt=False).strip())
    return "\n\n".join(t for t in out if t)
