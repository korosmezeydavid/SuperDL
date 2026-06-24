"""Hangoskönyv-építő: a könyv szövegét a választott TTS-motorral MP3-zá
alakítja, fix hangos bevezetővel és záró jogi nyilatkozattal.

Folyamat: a szöveget a motor karakterkorlátja szerint darabolja, minden
darabot felolvastat, az eredményt egységes MP3-ra normalizálja (ffmpeg),
majd összefűzi: bevezető + tartalom + nyilatkozat. A végeredmény egyetlen
MP3, vagy a felhasználó által megadott percenként darabolva.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path

from . import tts
from .ffmpeg import ensure_ffmpeg, find_ffmpeg

# A program által beállított, FIX bevezető és záró szöveg (nem szerkeszthető).
INTRO = ("{title}. Ezt a hangoskönyvet a SuperDL program készítette, "
         "kizárólag egyéni, személyes használatra.")
OUTRO = ("A hangoskönyv vége. Ezt a felvételt a SuperDL program olvasta fel, "
         "kizárólag egyéni célú hallgatásra. A felvétel terjesztése vagy "
         "megosztása a szerző engedélye nélkül tilos.")

DEFAULT_CHUNK = 6000


def chunk_text(text: str, limit: int) -> list[str]:
    """A szöveget legfeljebb `limit` karakteres darabokra bontja, lehetőleg
    bekezdés- és mondathatáron."""
    limit = limit if limit and limit > 0 else DEFAULT_CHUNK
    chunks: list[str] = []
    cur = ""

    def flush():
        nonlocal cur
        if cur.strip():
            chunks.append(cur.strip())
        cur = ""

    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        if len(cur) + len(para) + 1 <= limit:
            cur = (cur + "\n" + para) if cur else para
        elif len(para) <= limit:
            flush()
            cur = para
        else:
            flush()
            for sent in re.split(r"(?<=[.!?])\s+", para):
                if len(cur) + len(sent) + 1 <= limit:
                    cur = (cur + " " + sent) if cur else sent
                else:
                    flush()
                    cur = sent[:limit]
    flush()
    return chunks


def _ffmpeg_exe(progress=None) -> str:
    p = find_ffmpeg()
    if not p:
        d = ensure_ffmpeg(progress)
        p = find_ffmpeg() if d else None
    if not p:
        raise RuntimeError("Az ffmpeg nem érhető el.")
    if p.lower().endswith("ffmpeg.exe"):
        return p
    return os.path.join(p, "ffmpeg.exe")


def build(book, engine_key, voice_id, out_path, *, pitch=0, rate=0,
          api_key="", split_minutes=0, progress=None) -> list[str]:
    """Elkészíti a hangoskönyvet. Visszaadja a létrejött fájl(ok) listáját.
    `progress(kész, összes, állapot)` hívható a folyamatjelzéshez."""
    eng = tts.ENGINES[engine_key]
    ff = _ffmpeg_exe()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    parts = ([INTRO.format(title=book.title)]
             + chunk_text(book.text, eng.char_limit)
             + [OUTRO])
    total = len(parts)
    work = Path(tempfile.mkdtemp(prefix="sdl_book_"))
    norm_files: list[Path] = []
    try:
        for i, text in enumerate(parts):
            if progress:
                progress(i, total, "felolvasás")
            raw = eng.synth(text, voice_id, str(work / f"p{i:04d}"),
                            pitch=pitch, rate=rate, api_key=api_key)
            norm = work / f"n{i:04d}.mp3"
            subprocess.run(
                [ff, "-y", "-i", raw, "-ar", "44100", "-ac", "2",
                 "-c:a", "libmp3lame", "-qscale:a", "4", str(norm),
                 "-loglevel", "quiet"], stdin=subprocess.DEVNULL,
                creationflags=flags, check=True)
            norm_files.append(norm)
            try:
                os.remove(raw)
            except OSError:
                pass

        if progress:
            progress(total, total, "összefűzés")
        listfile = work / "list.txt"
        listfile.write_text(
            "".join(f"file '{n.as_posix()}'\n" for n in norm_files),
            encoding="utf-8")

        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if split_minutes and split_minutes > 0:
            pattern = str(out.with_name(out.stem + "_%03d" + out.suffix))
            subprocess.run(
                [ff, "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
                 "-f", "segment", "-segment_time", str(int(split_minutes * 60)),
                 "-c", "copy", pattern, "-loglevel", "quiet"],
                stdin=subprocess.DEVNULL, creationflags=flags, check=True)
            import glob
            results = sorted(glob.glob(
                str(out.with_name(out.stem + "_*" + out.suffix))))
        else:
            subprocess.run(
                [ff, "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
                 "-c", "copy", str(out), "-loglevel", "quiet"],
                stdin=subprocess.DEVNULL, creationflags=flags, check=True)
            results = [str(out)]
        if progress:
            progress(total, total, "kész")
        return results
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)
