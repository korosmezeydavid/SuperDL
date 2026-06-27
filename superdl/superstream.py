"""Super Stream – egyszerű, akadálymentes ÉLŐ multistream több platformra
(YouTube, Facebook, TikTok…) egyszerre, a beágyazott ffmpeg-gel.

Vakbarát megközelítés (Robi listás kérése nyomán): a felhasználó megad egy
ÁLLÓKÉPET (a videó), egy HANGFORRÁST (mikrofon vagy hangfájl), és egy vagy több
RTMP-CÉLT (platform + stream-kulcs). A program EGYSZER kódol (H.264 + AAC), és a
ffmpeg `tee` muxerével PÁRHUZAMOSAN küldi minden célra – ha egy cél hibázik
(`onfail=ignore`), a többi megy tovább.

SZIGORÚAN LEGÁLIS: a felhasználó a SAJÁT platform-fiókjának stream-kulcsát adja
meg; nincs bundle-ölt kulcs, nincs jogsértő tartalom-terjesztés.
"""

import os
import re
import subprocess
import threading
from dataclasses import dataclass

from . import ffmpeg as ffmpeg_mod

_NOWIN = 0x08000000 if os.name == "nt" else 0

# Ismert platform-ingest URL-ek; a felhasználó a VÉGÉRE fűzi a saját
# stream-kulcsát (a TikTok a szerver-URL-t a saját stúdiójában adja).
PRESETS = [
    ("YouTube Live", "rtmp://a.rtmp.youtube.com/live2/"),
    ("Facebook Live", "rtmps://live-api-s.facebook.com:443/rtmp/"),
    ("TikTok Live", ""),                 # a szerver-URL a TikTok-stúdióból jön
    ("Egyéni RTMP-cél", ""),
]


@dataclass
class Target:
    name: str
    url: str                              # teljes RTMP-URL a stream-kulccsal


def build_command(ffmpeg: str, image: str, audio: tuple[str, str],
                  targets: list[Target], *, width: int = 1280,
                  height: int = 720, fps: int = 30, vbitrate: int = 2500,
                  abitrate: int = 160) -> list[str]:
    """Az ffmpeg-parancs: állókép (loop) + hangforrás → H.264/AAC → `tee` az
    összes RTMP-célra. `audio` = ("dshow", eszköznév) vagy ("file", útvonal)."""
    cmd = [ffmpeg, "-nostdin",
           "-re", "-loop", "1", "-framerate", str(fps), "-i", image]
    kind, val = audio
    if kind == "dshow":
        cmd += ["-f", "dshow", "-i", f"audio={val}"]
    elif kind == "file":
        cmd += ["-stream_loop", "-1", "-re", "-i", val]
    else:
        raise ValueError(f"ismeretlen hangforrás: {kind}")
    cmd += [
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-vf", f"scale={width}:{height}",
        "-b:v", f"{vbitrate}k", "-maxrate", f"{vbitrate}k",
        "-bufsize", f"{vbitrate * 2}k", "-g", str(fps * 2),
        "-c:a", "aac", "-b:a", f"{abitrate}k", "-ar", "44100",
    ]
    tee = "|".join(f"[f=flv:onfail=ignore]{t.url}" for t in targets)
    cmd += ["-f", "tee", tee]
    return cmd


def list_audio_devices(ffmpeg: str | None = None) -> list[str]:
    """A DirectShow hang-bemeneti eszközök nevei (mikrofonok, vonalbemenet…).
    Üres lista, ha nem sikerül lekérdezni."""
    ffmpeg = ffmpeg or ffmpeg_mod.find_ffmpeg()
    if not ffmpeg:
        return []
    try:
        r = subprocess.run(
            [ffmpeg, "-hide_banner", "-list_devices", "true", "-f", "dshow",
             "-i", "dummy"], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", creationflags=_NOWIN, timeout=20)
        return parse_audio_devices(r.stdout or "")
    except (OSError, subprocess.SubprocessError):
        return []


def parse_audio_devices(text: str) -> list[str]:
    """A `-list_devices` kimenetéből a HANG-eszközök neveit szedi ki. KÉT
    ffmpeg-formátumot kezel: a régit (`"Név" (audio)`) és az újabbat (egy
    „DirectShow audio devices" szekció-fejléc, majd `"Név"` sorok)."""
    out = []
    in_audio = False
    for line in text.splitlines():
        low = line.lower()
        if "(audio)" in low:                       # régi formátum
            m = re.search(r'"([^"]+)"', line)
            if m:
                out.append(m.group(1))
            continue
        if "directshow audio devices" in low:       # újabb: szekció kezdete
            in_audio = True
            continue
        if "directshow video devices" in low:
            in_audio = False
            continue
        if in_audio and "alternative name" not in low:
            m = re.search(r'"([^"]+)"', line)
            if m:
                out.append(m.group(1))
    seen, uniq = set(), []
    for n in out:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


class Streamer:
    """Az élő adás folyamata. `on_status(text)` a futás közbeni állapothoz;
    `on_done(ok, msg)` a végén."""

    def __init__(self, image: str, audio: tuple[str, str],
                 targets: list[Target], on_status=None, on_done=None,
                 **opts):
        self.image = image
        self.audio = audio
        self.targets = list(targets)
        self.on_status = on_status
        self.on_done = on_done
        self.opts = opts
        self._proc = None
        self._stop = False

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stop = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def _run(self):
        ff = ffmpeg_mod.find_ffmpeg()
        if not ff:
            ff_dir = ffmpeg_mod.ensure_ffmpeg(None)
            ff = ffmpeg_mod.find_ffmpeg() if ff_dir else None
        if not ff:
            self._emit_done(False, "Az ffmpeg nem érhető el, és nem sikerült "
                                   "letölteni.")
            return
        if not self.targets:
            self._emit_done(False, "Nincs megadva egyetlen adáscél sem.")
            return
        cmd = build_command(ff, self.image, self.audio, self.targets, **self.opts)
        try:
            self._proc = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", creationflags=_NOWIN)
        except OSError as e:
            self._emit_done(False, f"Az adás nem indult el: {e}")
            return
        live = False
        for line in self._proc.stdout:
            if self._stop:
                break
            if not live and line.startswith("frame="):
                live = True
                if self.on_status:
                    self.on_status("Élő adásban – a kép és a hang megy a "
                                   "megadott platform(ok)ra.")
        rc = self._proc.wait()
        if self._stop:
            self._emit_done(True, "Az adást leállítottad.")
        elif rc == 0:
            self._emit_done(True, "Az adás befejeződött.")
        else:
            self._emit_done(False, "Az adás hibával állt le – ellenőrizd a "
                                   "stream-kulcsot és az internetkapcsolatot.")

    def _emit_status(self, text):
        if self.on_status:
            self.on_status(text)

    def _emit_done(self, ok, msg):
        if self.on_done:
            self.on_done(ok, msg)
