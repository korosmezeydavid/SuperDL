"""iPhone csengőhang (.m4r) – és sima MP3 – készítése egy zenefájl
kijelölt részletéből, ffmpeg-gel.

Egyszerű, ahogy a felhasználó kérte: a KEZDET a megállás pontja, a hossz
legfeljebb 30 mp (az iPhone 40 mp-es csengőhang-korlátja alatt biztonsággal),
NINCS fade – pontos vágás. Az .m4r valójában AAC/M4A az „ipod" muxerrel.
"""

import os
import subprocess
import tempfile
import uuid
from pathlib import Path

from superdl import ffmpeg as ffmpeg_mod    # megosztott ffmpeg a Core-ból
from superdl import mediaexport             # atomikus export (.part→ellenőrzés)

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
    # ATOMIKUS EXPORT: a cél MELLÉ renderelünk, ellenőrizzük, és csak utána
    # cseréljük. Enélkül egy megszakadt renderelés a MEGLÉVŐ csengőhangot
    # csonka fájlra cserélte volna. [Herman Tibi RING-P0-04]
    part = mediaexport.part_path(out)
    cmd = [ff, "-y", "-ss", f"{start:.3f}", "-i", src,
           "-t", f"{length:.3f}", "-vn", *codec, part]
    flags = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, creationflags=flags, timeout=180)
    except (OSError, subprocess.SubprocessError) as e:
        mediaexport.cleanup(part)
        return f"renderelési hiba: {e}"
    if r.returncode != 0:
        mediaexport.cleanup(part)
        return "az ffmpeg hibával állt le – ellenőrizd a zenei fájlt"
    ok, indok = mediaexport.verify_audio(part, mediaexport.ffprobe_for(ff))
    if not ok:
        mediaexport.cleanup(part)
        return (f"a kész csengőhang nem használható: {indok} "
                "(a korábbi fájl érintetlen maradt)")
    try:
        mediaexport.commit(part, out)
    except OSError as e:
        mediaexport.cleanup(part)
        return f"a fájl nem menthető a helyére: {e}"
    return ""


def preview_path(fmt: str = "mp3") -> str:
    """Egy EGYEDI ideiglenes fájl útvonala a részlet meghallgatásához.

    Korábban fix `superdl_ring_preview` név volt: két ablak vagy két gyors
    előnézet EGYMÁS fájlját írta felül, miközben a lejátszó olvasta (rossz
    részlet szólt, fájlzárolási hiba). [Herman Tibi RING-P0-01]"""
    ext = FORMATS.get(fmt, FORMATS["mp3"])[0]
    return str(Path(tempfile.gettempdir())
               / f"superdl_ring_preview_{os.getpid()}_{uuid.uuid4().hex[:8]}{ext}")
