"""iPhone csengőhang (.m4r) – és sima MP3 – készítése egy zenefájl
kijelölt részletéből, ffmpeg-gel.

Egyszerű, ahogy a felhasználó kérte: a KEZDET a megállás pontja, a hossz
legfeljebb 30 mp (az iPhone 40 mp-es csengőhang-korlátja alatt biztonsággal),
NINCS fade – pontos vágás. Az .m4r valójában AAC/M4A az „ipod" muxerrel.
"""

import os
import subprocess
import tempfile
from pathlib import Path

from . import ffmpeg as ffmpeg_mod

RING_MAX = 30.0       # legnagyobb hossz másodpercben
RING_MIN = 3.0        # legkisebb értelmes hossz

# cél formátum -> (kiterjesztés, ffmpeg kodek-argumentumok)
FORMATS = {
    "m4r": (".m4r", ["-c:a", "aac", "-b:a", "192k", "-f", "ipod"]),
    "mp3": (".mp3", ["-c:a", "libmp3lame", "-b:a", "192k"]),
}


def clamp_length(length: float) -> float:
    return max(RING_MIN, min(RING_MAX, length))


def make_ringtone(src: str, out: str, start: float, length: float,
                  fmt: str = "m4r", ff_progress=None) -> str:
    """A [start, start+length] szakasz kivágása és kódolása. Üres sztringet
    ad vissza siker esetén, különben a hibaüzenetet."""
    ff = ffmpeg_mod.find_ffmpeg()
    if not ff:
        ff_dir = ffmpeg_mod.ensure_ffmpeg(ff_progress)
        ff = ffmpeg_mod.find_ffmpeg() if ff_dir else None
    if not ff:
        return "az ffmpeg nem érhető el"
    if fmt not in FORMATS:
        fmt = "m4r"
    _ext, codec = FORMATS[fmt]
    start = max(0.0, start)
    length = clamp_length(length)
    cmd = [ff, "-y", "-ss", f"{start:.3f}", "-i", src,
           "-t", f"{length:.3f}", "-vn", *codec, out]
    flags = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, creationflags=flags, timeout=180)
    except (OSError, subprocess.SubprocessError) as e:
        return f"renderelési hiba: {e}"
    if r.returncode != 0 or not os.path.isfile(out):
        return "az ffmpeg hibával állt le – ellenőrizd a zenei fájlt"
    return ""


def preview_path(fmt: str = "mp3") -> str:
    """Egy ideiglenes fájl útvonala a részlet meghallgatásához."""
    ext = FORMATS.get(fmt, FORMATS["mp3"])[0]
    return str(Path(tempfile.gettempdir()) / f"superdl_ring_preview{ext}")
