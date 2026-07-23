# -*- coding: utf-8 -*-
"""Biztonságos média-export: `.part` fájl → ellenőrzés → ATOMIKUS csere.

MIÉRT KELL: a felvevő, a fülre-szerkesztő és a csengőhang-készítő eddig az
ffmpeg `-y` kapcsolójával KÖZVETLENÜL a végleges fájlnévre írt. Ha közben
elfogyott a lemez, összeomlott a program vagy hibázott a kodek, a MEGLÉVŐ
(korábbi, jó) fájl helyén egy csonka, lejátszhatatlan fájl maradt – végleges
néven, „kész" állapotban.

MEGOLDÁS: a renderelés a cél MELLÉ, ugyanabba a mappába készül `.part`
kiterjesztéssel (így a csere ugyanazon a köteten, atomikusan mehet), utána
ffprobe-bal ELLENŐRIZZÜK (van-e hangsáv, van-e hossza), és csak sikeres
ellenőrzés után lép a helyére. Hibánál a régi fájl SÉRTETLEN marad.

[Herman Tibi AUDIO-P0-04 / EDIT-P1-17 / RING-P0-04 / REC-P1-15]
"""
from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

_NOWIN = 0x08000000 if os.name == "nt" else 0


def part_path(final_path: str) -> str:
    """A véglegessel AZONOS mappában lévő, egyedi ideiglenes név. Ugyanaz a
    kötet kell, különben az `os.replace` nem atomikus."""
    p = Path(final_path)
    return str(p.with_name(f"{p.stem}.{uuid.uuid4().hex[:8]}.part{p.suffix}"))


def ffprobe_for(ffmpeg_path: str) -> str:
    """Az ffprobe az ffmpeg MELLETT szokott lenni (a Core ugyanabba a mappába
    tölti le). Ha nincs, üres sztringet ad – akkor csak méret-ellenőrzés lesz."""
    try:
        p = Path(ffmpeg_path)
        cand = p.with_name("ffprobe" + p.suffix)
        return str(cand) if cand.is_file() else ""
    except (OSError, ValueError):
        return ""


def verify_audio(path: str, ffprobe: str = "") -> tuple[bool, str]:
    """Valóban használható-e a kimenet? (létezik, nem üres, van hangsávja és
    hossza). Visszaad: (rendben?, magyar indoklás).

    Ha nincs ffprobe, csak a létezést és a méretet tudjuk ellenőrizni – ez is
    többet ér a semminél (a csonka/nulla bájtos fájl így sem megy át)."""
    try:
        if not os.path.isfile(path):
            return False, "a fájl nem jött létre"
        if os.path.getsize(path) < 512:
            return False, "a fájl üres vagy csonka"
    except OSError as e:
        return False, f"a fájl nem olvasható ({e})"
    if not ffprobe:
        return True, ""
    try:
        r = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_type:format=duration",
             "-of", "default=nw=1", path],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", creationflags=_NOWIN, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return True, ""            # ha nem tudjuk ellenőrizni, ne blokkoljunk
    out = (r.stdout or "")
    if "codec_type=audio" not in out:
        return False, "a fájlban nincs hangsáv"
    for line in out.splitlines():
        if line.startswith("duration="):
            try:
                if float(line.split("=", 1)[1]) > 0.01:
                    return True, ""
            except ValueError:
                pass
            return False, "a hang hossza nulla"
    return True, ""


def commit(part: str, final_path: str) -> None:
    """A `.part` fájl VÉGLEGESÍTÉSE: lemezre írás (fsync) + atomikus csere.
    Sikertelenség esetén a `.part` törlődik, a régi cél érintetlen marad."""
    try:
        fd = os.open(part, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass                       # az fsync hiánya nem ok a mentés eldobására
    os.replace(part, final_path)   # atomikus ugyanazon a köteten


def cleanup(part: str) -> None:
    """A félkész `.part` eltakarítása hiba/megszakítás után."""
    try:
        if part and os.path.exists(part):
            os.remove(part)
    except OSError:
        pass
