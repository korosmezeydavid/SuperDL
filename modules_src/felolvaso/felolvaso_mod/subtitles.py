"""Feliratok beolvasása és időzítése a felirat-felolvasóhoz.

Támogat: mellé tett feliratfájl (.srt/.vtt, illetve .ass/.ssa az ffmpeg-en át)
és a videóba ÁGYAZOTT szöveges feliratsáv (az ffmpeg SRT-vé bontja). A feliratok
időzített „cue"-kká állnak össze; a `CueScheduler` a lejátszási POZÍCIÓ alapján
adja ki, mit kell épp felolvasni – így a felolvasás szünet/ugrás után is szinkron.
"""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from superdl import ffmpeg as ffmpeg_mod

# közvetlenül olvasható feliratfájlok; az .ass/.ssa az ffmpeg-en át
SUB_EXTS = (".srt", ".vtt", ".ass", ".ssa", ".sub")
VIDEO_EXTS = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".ts",
              ".flv", ".wmv", ".mpg", ".mpeg", ".m2ts")
AUDIO_EXTS = (".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".wma")

# a magyar felirat felismeréséhez (fájlnév-jelölők)
_HU_HINTS = (".hu.", ".hun.", ".magyar.", "_hu.", "-hu.", ".hu_", "hungarian")


@dataclass
class Cue:
    start: float          # kezdet másodpercben
    end: float            # vég másodpercben
    text: str             # a felolvasandó szöveg (formázás nélkül)


def _ffmpeg() -> str | None:
    p = ffmpeg_mod.find_ffmpeg()
    if not p:
        d = ffmpeg_mod.ensure_ffmpeg()
        p = ffmpeg_mod.find_ffmpeg() if d else None
    if not p:
        return None
    return p if p.lower().endswith("ffmpeg.exe") else str(Path(p) / "ffmpeg.exe")


def _ffprobe() -> str | None:
    ff = _ffmpeg()
    return str(Path(ff).with_name("ffprobe.exe")) if ff else None


_NOWIN = 0x08000000    # CREATE_NO_WINDOW (Windows)

_TS = re.compile(r"(\d+):([0-5]?\d):([0-5]?\d)[,.](\d{1,3})")
_ARROW = re.compile(r"-->")
# felirat-formázás, amit a FELOLVASÁSHOZ eltávolítunk
_TAG = re.compile(r"<[^>]+>|\{\\[^}]*\}|\{[^}]*\}")


def _to_seconds(m: re.Match) -> float:
    h, mi, s, ms = m.groups()
    ms = (ms + "000")[:3]              # tized/század/ezred → ezredre
    return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000.0


def _clean_line(s: str) -> str:
    s = _TAG.sub("", s)               # HTML/ASS-formázás ki
    s = s.replace("​", "").replace("﻿", "")
    return s.strip()


def parse_srt(text: str) -> list[Cue]:
    """SRT és WEBVTT szöveg feldolgozása időzített cue-kká. A blokkokat üres sor
    választja; a sorszám és a WEBVTT-fejléc kimarad, a formázás eltávolítva."""
    cues: list[Cue] = []
    # normalizált sorvégek, blokkokra bontás
    blocks = re.split(r"\r?\n\r?\n", text.replace("\r\n", "\n"))
    for block in blocks:
        lines = [ln for ln in block.split("\n") if ln.strip() != ""]
        if not lines:
            continue
        # a --> sort megkeressük (előtte lehet sorszám vagy VTT-cue-id)
        ts_idx = next((i for i, ln in enumerate(lines) if _ARROW.search(ln)), -1)
        if ts_idx < 0:
            continue
        stamps = list(_TS.finditer(lines[ts_idx]))
        if len(stamps) < 2:
            continue
        start = _to_seconds(stamps[0])
        end = _to_seconds(stamps[1])
        body = " ".join(_clean_line(ln) for ln in lines[ts_idx + 1:])
        body = re.sub(r"\s+", " ", body).strip()
        if body and end >= start:
            cues.append(Cue(start=start, end=max(end, start + 0.5), text=body))
    cues.sort(key=lambda c: c.start)
    return cues


def decode_bytes(data: bytes) -> str:
    """Feliratfájl bájtjainak szöveggé fejtése a gyakori kódolásokkal (a magyar
    feliratok jellemzően UTF-8 vagy CP1250/ISO-8859-2)."""
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    # pontszám: a legtöbb magyar ékezetes betűt adó egybájtos kódlap nyer
    best, best_score = None, -1
    hu = "áéíóöőúüűÁÉÍÓÖŐÚÜŰ"
    for enc in ("cp1250", "iso-8859-2", "cp1252"):
        try:
            t = data.decode(enc)
        except UnicodeDecodeError:
            continue
        score = sum(t.count(ch) for ch in hu) - sum(
            1 for ch in t if 0x80 <= ord(ch) <= 0x9F)
        if score > best_score:
            best, best_score = t, score
    return best if best is not None else data.decode("utf-8", errors="replace")


def load_subtitle_file(path) -> list[Cue]:
    """Mellé tett feliratfájl → cue-lista. Az .srt/.vtt közvetlenül, az
    .ass/.ssa/.sub az ffmpeg-en át (SRT-vé alakítva)."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in (".srt", ".vtt"):
        return parse_srt(decode_bytes(p.read_bytes()))
    # .ass/.ssa/.sub → ffmpeg konvertálja SRT-re a kimenetre
    ff = _ffmpeg()
    if not ff:
        raise RuntimeError("Ehhez a feliratformátumhoz ffmpeg kell.")
    try:
        r = subprocess.run([ff, "-nostdin", "-loglevel", "quiet", "-i", str(p),
                            "-f", "srt", "-"], stdout=subprocess.PIPE,
                           creationflags=_NOWIN, timeout=60)
        return parse_srt(r.stdout.decode("utf-8", "replace"))
    except (OSError, subprocess.SubprocessError) as e:
        raise RuntimeError(f"a felirat nem olvasható: {e}")


def find_sidecar_subs(media_path) -> list[str]:
    """A média mellett talált feliratfájlok (azonos vagy hasonló törzsnév),
    a MAGYAR jelölésűeket előre sorolva."""
    p = Path(media_path)
    stem = p.stem.lower()
    found = []
    try:
        for f in p.parent.iterdir():
            if not f.is_file() or f.suffix.lower() not in SUB_EXTS:
                continue
            fn = f.name.lower()
            # ugyanaz a törzsnév, vagy a felirat neve a médiával kezdődik
            if f.stem.lower() == stem or fn.startswith(stem):
                found.append(str(f))
    except OSError:
        return []
    found.sort(key=lambda s: (0 if any(h in Path(s).name.lower()
                                       for h in _HU_HINTS) else 1,
                              Path(s).name.lower()))
    return found


def embedded_text_tracks(path) -> list[dict]:
    """A médiafájlba ágyazott SZÖVEGES feliratsávok: [{index, label}].
    (A képi – DVB/PGS – feliratokhoz OCR kellene, azokat kihagyjuk.)"""
    pb = _ffprobe()
    if not pb:
        return []
    text_codecs = {"subrip", "srt", "webvtt", "ass", "ssa", "mov_text", "text"}
    try:
        import json
        r = subprocess.run(
            [pb, "-v", "error", "-select_streams", "s", "-show_entries",
             "stream=index,codec_name:stream_tags=language,title",
             "-of", "json", str(path)], stdout=subprocess.PIPE,
            creationflags=_NOWIN, timeout=30)
        streams = json.loads(r.stdout or b"{}").get("streams", [])
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    out = []
    for i, s in enumerate(streams):
        if (s.get("codec_name", "") or "").lower() not in text_codecs:
            continue
        tags = s.get("tags", {}) or {}
        label = " ".join(x for x in (tags.get("language", ""),
                                     tags.get("title", "")) if x)
        out.append({"index": i, "label": label or f"{i + 1}. feliratsáv"})
    return out


def extract_embedded(path, sub_index: int) -> list[Cue]:
    """Egy ágyazott szöveges feliratsáv kibontása cue-listává (ffmpeg → SRT)."""
    ff = _ffmpeg()
    if not ff:
        raise RuntimeError("A felirat kibontásához ffmpeg kell.")
    try:
        r = subprocess.run(
            [ff, "-nostdin", "-loglevel", "quiet", "-i", str(path),
             "-map", f"0:s:{int(sub_index)}", "-f", "srt", "-"],
            stdout=subprocess.PIPE, creationflags=_NOWIN, timeout=120)
        return parse_srt(r.stdout.decode("utf-8", "replace"))
    except (OSError, subprocess.SubprocessError) as e:
        raise RuntimeError(f"a feliratsáv nem bontható ki: {e}")


class CueScheduler:
    """A lejátszási POZÍCIÓ alapján adja ki a felolvasandó feliratokat, sorban,
    egyszer. Szünet alatt a pozíció nem nő → nincs kiadás; ugráskor `reset_to`
    újrapozicionál (a visszaugrás újra felolvastatja az érintett feliratot)."""

    def __init__(self, cues: list[Cue]):
        self.cues = sorted(cues, key=lambda c: c.start)
        self._i = 0

    def next_due(self, position: float) -> Cue | None:
        """A KÖVETKEZŐ még ki nem adott felirat, ha a kezdete már elérkezett
        (start <= position). A régóta lejárt (a pozíció túl van a végén) feliratot
        átugorjuk, hogy ne olvassa be visszamenőleg az egész elmaradt sort."""
        while self._i < len(self.cues):
            c = self.cues[self._i]
            if c.start > position:
                return None
            self._i += 1
            if position <= c.end + 2.0:      # csak ha még nagyjából aktuális
                return c
        return None

    def reset_to(self, position: float) -> None:
        """Ugrás után: az első olyan feliratra állunk, ami a pozíciónál még nem
        ért véget (így egy épp aktív feliratot is felolvas)."""
        self._i = 0
        for i, c in enumerate(self.cues):
            if c.end > position:
                self._i = i
                break
        else:
            self._i = len(self.cues)
