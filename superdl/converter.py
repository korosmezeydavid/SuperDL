"""Kötegelt médiakonvertáló ffmpeg-gel: egy vagy sok fájl átalakítása.

Három irány:
  * "audio"   – hang → hang (pl. M4A → MP3),
  * "video"   – videó → videó (pl. MKV → MP4),
  * "extract" – videó → hang (a hangsáv kivonása).

OKOS MÓD: ha csak a konténer változik és a meglévő kodek belefér a cél
formátumba, VESZTESÉGMENTES REMUX történik (`-c copy`, gyors), különben
újrakódolás. SOHA nem ír felül: ütközéskor sorszámmal átnevez. A minőséget
egyszerű előbeállítás adja (hang-bitráta; videónál ésszerű x264-minőség).
"""

import os
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from . import ffmpeg as ffmpeg_mod

# cél hangformátum -> (ffmpeg kodek, kiterjesztés, "natív" kodeknevek a remuxhoz)
AUDIO_TARGETS = {
    "mp3":  ("libmp3lame", ".mp3", ("mp3",)),
    "m4a":  ("aac",        ".m4a", ("aac", "alac")),
    "opus": ("libopus",    ".opus", ("opus",)),
    "flac": ("flac",       ".flac", ("flac",)),
    "wav":  ("pcm_s16le",  ".wav", ("pcm_s16le", "pcm_s24le")),
    "ogg":  ("libvorbis",  ".ogg", ("vorbis",)),
}

# cél videoformátum -> (kiterjesztés, video-kodek, audio-kodek,
#                       a konténerbe remuxolható VIDEO-kodekek halmaza,
#                       remuxolható AUDIO-kodekek halmaza)
VIDEO_TARGETS = {
    "mp4":  (".mp4", "libx264",     "aac",
             {"h264", "hevc", "mpeg4"}, {"aac", "mp3", "ac3"}),
    "mkv":  (".mkv", "libx264",     "aac",
             {"h264", "hevc", "mpeg4", "vp8", "vp9", "av1"},
             {"aac", "mp3", "ac3", "opus", "vorbis", "flac"}),
    "mov":  (".mov", "libx264",     "aac",
             {"h264", "hevc", "mpeg4"}, {"aac", "mp3"}),
    "avi":  (".avi", "mpeg4",       "libmp3lame",
             {"mpeg4", "mjpeg"}, {"mp3", "ac3"}),
    "webm": (".webm", "libvpx-vp9", "libopus",
             {"vp8", "vp9", "av1"}, {"opus", "vorbis"}),
}

AUDIO_BITRATES = ("128", "192", "256", "320")
MODES = ("audio", "video", "extract")


@dataclass
class ConvertJob:
    src: str
    status: str = "várakozik"      # várakozik / folyamatban / kész / hiba / leállítva
    out: str = ""
    error: str = ""
    progress: float = 0.0          # 0..1 az adott fájlon belül


def _ffprobe() -> str | None:
    ff = ffmpeg_mod.find_ffmpeg()
    if not ff:
        return None
    p = Path(ff).with_name("ffprobe.exe")
    return str(p) if p.is_file() else None


def probe(path: str) -> tuple[str, str, float]:
    """A forrás (video-kodek, audio-kodek, hossz_mp). Hiányzó sávnál "".
    A kodekeket külön stream-lekérdezésekkel, megbízhatóan kérjük le."""
    pb = _ffprobe()
    if not pb:
        return "", "", 0.0

    def first(args):
        try:
            r = subprocess.run([pb, "-v", "error", *args, path],
                               capture_output=True, text=True, timeout=30)
            return r.stdout.strip().splitlines()[0] if r.stdout.strip() else ""
        except (OSError, subprocess.SubprocessError, IndexError):
            return ""
    vcodec = first(["-select_streams", "v:0", "-show_entries",
                    "stream=codec_name", "-of",
                    "default=noprint_wrappers=1:nokey=1"])
    acodec = first(["-select_streams", "a:0", "-show_entries",
                    "stream=codec_name", "-of",
                    "default=noprint_wrappers=1:nokey=1"])
    d = first(["-show_entries", "format=duration", "-of",
               "default=noprint_wrappers=1:nokey=1"])
    try:
        dur = float(d)
    except ValueError:
        dur = 0.0
    return vcodec, acodec, dur


def unique_path(out_dir: str, stem: str, ext: str) -> str:
    """Ütközésmentes kimeneti útvonal: ha létezik, sorszámot fűz hozzá."""
    base = Path(out_dir) / f"{stem}{ext}"
    if not base.exists():
        return str(base)
    i = 2
    while True:
        cand = Path(out_dir) / f"{stem} ({i}){ext}"
        if not cand.exists():
            return str(cand)
        i += 1


def build_command(ff: str, src: str, out: str, mode: str, fmt: str,
                  bitrate: str, vcodec: str, acodec: str) -> list[str]:
    """Az ffmpeg-parancs összeállítása az okos remux/újrakódolás döntéssel.
    `vcodec`/`acodec` a FORRÁS kodekjei (a remux-döntéshez)."""
    cmd = [ff, "-y", "-i", src]

    if mode == "extract":                 # videó → hang (csak a hangsáv)
        tcodec, _ext, native = AUDIO_TARGETS[fmt]
        cmd += ["-vn"]
        if acodec in native:              # a hang már a célkodek → remux
            cmd += ["-c:a", "copy"]
        else:
            cmd += ["-c:a", tcodec]
            if fmt not in ("flac", "wav"):
                cmd += ["-b:a", f"{bitrate}k"]
        cmd += [out]
        return cmd

    if mode == "audio":                   # hang → hang
        tcodec, _ext, native = AUDIO_TARGETS[fmt]
        cmd += ["-vn"]
        if acodec in native:
            cmd += ["-c:a", "copy"]
        else:
            cmd += ["-c:a", tcodec]
            if fmt not in ("flac", "wav"):
                cmd += ["-b:a", f"{bitrate}k"]
        cmd += [out]
        return cmd

    # videó → videó
    _ext, tvcodec, tacodec, vok, aok = VIDEO_TARGETS[fmt]
    if vcodec in vok and (acodec in aok or not acodec):
        # mindkét sáv belefér a konténerbe → VESZTESÉGMENTES REMUX
        cmd += ["-c", "copy"]
    else:
        cmd += ["-c:v", tvcodec, "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p"]
        if acodec:
            cmd += ["-c:a", tacodec, "-b:a", "192k"]
    cmd += [out]
    return cmd


class Converter:
    """Egy vagy több fájl kötegelt átalakítása, sorban, megszakíthatóan."""

    def __init__(self, files, out_dir: str, mode: str, fmt: str,
                 bitrate: str = "192", on_status=None, on_progress=None,
                 ff_progress=None):
        self.jobs = [ConvertJob(src=f) for f in files]
        self.out_dir = out_dir
        self.mode = mode
        self.fmt = fmt
        self.bitrate = bitrate
        self.on_status = on_status        # on_status(index, job)
        self.on_progress = on_progress    # on_progress(index, fraction)
        self.ff_progress = ff_progress
        self._stop = threading.Event()
        self._proc = None
        self.done = 0
        self.failed = 0

    def stop(self):
        self._stop.set()
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def run(self) -> tuple[int, int]:
        """Az összes fájl feldolgozása. Visszaad: (kész, hibás)."""
        ff = ffmpeg_mod.find_ffmpeg()
        if not ff:
            ff_dir = ffmpeg_mod.ensure_ffmpeg(self.ff_progress)
            ff = ffmpeg_mod.find_ffmpeg() if ff_dir else None
        if not ff:
            for i, job in enumerate(self.jobs):
                job.status = "hiba"
                job.error = "az ffmpeg nem érhető el"
                self._emit_status(i, job)
            return 0, len(self.jobs)

        ext = (AUDIO_TARGETS[self.fmt][1] if self.mode in ("audio", "extract")
               else VIDEO_TARGETS[self.fmt][0])
        try:
            os.makedirs(self.out_dir, exist_ok=True)
        except OSError as e:
            for i, job in enumerate(self.jobs):
                job.status = "hiba"
                job.error = f"a kimeneti mappa nem hozható létre: {e}"
                self._emit_status(i, job)
            return 0, len(self.jobs)

        for i, job in enumerate(self.jobs):
            if self._stop.is_set():
                job.status = "leállítva"
                self._emit_status(i, job)
                continue
            self._convert_one(ff, i, job, ext)

        return self.done, self.failed

    def _convert_one(self, ff: str, i: int, job: ConvertJob, ext: str):
        job.status = "folyamatban"
        self._emit_status(i, job)
        src = job.src
        if not os.path.isfile(src):
            job.status = "hiba"
            job.error = "a forrásfájl nem található"
            self.failed += 1
            self._emit_status(i, job)
            return

        vcodec, acodec, dur = probe(src)
        if self.mode == "extract" and not acodec:
            job.status = "hiba"
            job.error = "a videóban nincs hangsáv"
            self.failed += 1
            self._emit_status(i, job)
            return

        stem = Path(src).stem
        out = unique_path(self.out_dir, stem, ext)
        job.out = out
        cmd = build_command(ff, src, out, self.mode, self.fmt,
                            self.bitrate, vcodec, acodec)
        cmd = cmd[:1] + ["-progress", "pipe:1", "-nostats"] + cmd[1:]

        flags = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, creationflags=flags)
        except OSError as e:
            job.status = "hiba"
            job.error = str(e)
            self.failed += 1
            self._emit_status(i, job)
            return

        for line in self._proc.stdout:
            if self._stop.is_set():
                break
            line = line.strip()
            if line.startswith("out_time_ms=") and dur > 0:
                try:
                    ms = int(line.split("=", 1)[1])
                    job.progress = min(1.0, (ms / 1_000_000) / dur)
                    if self.on_progress:
                        self.on_progress(i, job.progress)
                except (ValueError, ZeroDivisionError):
                    pass
        rc = self._proc.wait()

        if self._stop.is_set():
            job.status = "leállítva"
            try:
                if os.path.isfile(out):
                    os.remove(out)         # félkész fájl törlése
            except OSError:
                pass
        elif rc == 0 and os.path.isfile(out):
            job.status = "kész"
            job.progress = 1.0
            self.done += 1
        else:
            job.status = "hiba"
            job.error = f"ffmpeg hibakód {rc}"
            self.failed += 1
        self._emit_status(i, job)

    def _emit_status(self, i: int, job: ConvertJob):
        if self.on_status:
            self.on_status(i, job)
