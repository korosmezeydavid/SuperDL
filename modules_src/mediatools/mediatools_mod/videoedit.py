"""Videóvágó és -összefűző motor (ffmpeg/ffprobe).

Modell: a projekt klipek listája, amik egyetlen globális idővonalat adnak
(egymás után). A felhasználó MARKEREKKEL jelöl időpontokat (füllel vágás), és
„magyarázó szövegeket" tehet bármely időponthoz (ezek a kimeneti videóra
ráégnek). Két kimenet:
  * SZAKASZ mentése: a globális idővonal [kezdet, vég] része,
  * TELJES mentés: az egész összefűzve.

Eltérő felbontású/kódolású klipeket a concat-szűrővel, közös felbontásra
skálázva fűz össze (normalizált alap). A path-escape gondok ellen a render egy
ideiglenes munkamappában fut, a szöveg-/betűfájlok puszta néven.
"""

import os
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from superdl import ffmpeg as ffmpeg_mod    # megosztott Core-modulok
from superdl.videocompose import _find_font, human_time, wrap_caption

OUT_FORMATS = (("MP4 – ajánlott", "mp4"), ("MKV", "mkv"), ("AVI", "avi"))
NOTE_DEFAULT_DUR = 4.0          # egy magyarázó szöveg alap megjelenési ideje (mp)


def _ffprobe() -> str | None:
    ff = ffmpeg_mod.find_ffmpeg()
    if not ff:
        return None
    p = Path(ff).with_name("ffprobe.exe")
    return str(p) if p.is_file() else None


def probe(path: str) -> tuple[float, int, int]:
    """(hossz_mp, szélesség, magasság) – ffprobe-bal."""
    pb = _ffprobe()
    if not pb:
        return 0.0, 0, 0
    def q(args):
        try:
            r = subprocess.run([pb, "-v", "error", *args, path],
                               capture_output=True, text=True, timeout=30)
            return r.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    dur = q(["-show_entries", "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1"])
    wh = q(["-select_streams", "v:0", "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x"])
    try:
        d = float(dur)
    except ValueError:
        d = 0.0
    w = h = 0
    if "x" in wh:
        try:
            w, h = (int(x) for x in wh.split("x")[:2])
        except ValueError:
            w = h = 0
    return d, w, h


@dataclass
class Clip:
    path: str
    duration: float = 0.0
    width: int = 0
    height: int = 0

    def label(self) -> str:
        return f"{Path(self.path).name} ({human_time(self.duration)})"


@dataclass
class TextNote:
    at: float                  # globális időpont (mp)
    text: str
    dur: float = NOTE_DEFAULT_DUR

    def label(self) -> str:
        return f"{human_time(self.at)} – {self.text}"


@dataclass
class Marker:
    at: float

    def label(self) -> str:
        return human_time(self.at)




class VideoEditor:
    def __init__(self):
        self.clips: list[Clip] = []
        self.notes: list[TextNote] = []
        self.markers: list[Marker] = []
        self._base = None          # normalizált alap-videó (cache, ha >1 klip)
        self._base_dir = None      # az alap-videó tartós ideiglenes mappája
        self._proc = None
        self._stop = threading.Event()
        self.error = ""

    # ---- projekt ------------------------------------------------------

    def add_clip(self, path: str) -> Clip | None:
        d, w, h = probe(path)
        if d <= 0:
            return None
        c = Clip(path=path, duration=d, width=w, height=h)
        self.clips.append(c)
        self._base = None          # új klip → az alapot újra kell építeni
        return c

    def remove_clip(self, i: int):
        if 0 <= i < len(self.clips):
            self.clips.pop(i)
            self._base = None

    def total_duration(self) -> float:
        return sum(c.duration for c in self.clips)

    def add_note(self, at: float, text: str):
        self.notes.append(TextNote(at=max(0.0, at), text=text))
        self.notes.sort(key=lambda n: n.at)

    def remove_note(self, i: int):
        if 0 <= i < len(self.notes):
            self.notes.pop(i)

    def add_marker(self, at: float):
        self.markers.append(Marker(at=max(0.0, at)))
        self.markers.sort(key=lambda m: m.at)

    def remove_marker(self, i: int):
        if 0 <= i < len(self.markers):
            self.markers.pop(i)

    def target_res(self) -> tuple[int, int]:
        for c in self.clips:
            if c.width and c.height:
                return c.width, c.height
        return 1280, 720

    # ---- vezérlés -----------------------------------------------------

    def stop(self):
        self._stop.set()
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def _ff(self):
        ff = ffmpeg_mod.find_ffmpeg()
        if not ff:
            d = ffmpeg_mod.ensure_ffmpeg()
            ff = ffmpeg_mod.find_ffmpeg() if d else None
        return ff

    def _run(self, cmd, cwd=None) -> bool:
        flags = 0x08000000 if os.name == "nt" else 0
        try:
            self._proc = subprocess.Popen(
                cmd, cwd=cwd, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE, text=True, creationflags=flags)
            _out, err = self._proc.communicate()
            if self._proc.returncode != 0:
                self.error = (err or "").strip().splitlines()[-1] \
                    if err else "ffmpeg hiba"
                return False
            return True
        except (OSError, IndexError) as e:
            self.error = str(e)
            return False

    def _ensure_base(self, ff: str) -> str | None:
        """A klipek egyetlen, normalizált (közös felbontású) videóvá fűzése.
        Egyetlen klipnél maga a klip az alap (nincs felesleges újrakódolás).
        Az alapot egy tartós ideiglenes mappába tesszük (export-cache)."""
        if len(self.clips) == 1:
            return self.clips[0].path
        if self._base and os.path.isfile(self._base):
            return self._base
        if not self._base_dir:
            self._base_dir = tempfile.mkdtemp(prefix="superdl_editbase_")
        w, h = self.target_res()
        base = Path(self._base_dir) / "base.mp4"
        cmd = [ff, "-y"]
        for c in self.clips:
            cmd += ["-i", c.path]
        parts = []
        for i in range(len(self.clips)):
            parts.append(
                f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=25[v{i}]")
        streams = "".join(f"[v{i}][{i}:a]" for i in range(len(self.clips)))
        graph = ";".join(parts) + ";" + streams + \
            f"concat=n={len(self.clips)}:v=1:a=1[cv][ca]"
        cmd += ["-filter_complex", graph, "-map", "[cv]", "-map", "[ca]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                str(base)]
        if not self._run(cmd):
            return None
        self._base = str(base)
        return self._base

    def export(self, start: float, end: float, out: str,
               progress=None) -> bool:
        """A globális idővonal [start, end] részének mentése `out`-ba, a
        tartományba eső magyarázó szövegekkel ráégetve. True = siker."""
        self._stop.clear()
        self.error = ""
        ff = self._ff()
        if not ff:
            self.error = "az ffmpeg nem érhető el"
            return False
        if not self.clips:
            self.error = "nincs betöltött videó"
            return False
        total = self.total_duration()
        start = max(0.0, start)
        end = min(end if end > 0 else total, total)
        if end - start < 0.1:
            self.error = "a kijelölt szakasz túl rövid"
            return False

        work = Path(tempfile.mkdtemp(prefix="superdl_edit_"))
        try:
            base = self._ensure_base(ff)
            if not base:
                self.error = self.error or "az összefűzés nem sikerült"
                return False

            font = _find_font()
            # a kimeneti felbontás: 1 klipnél a klip saját mérete, többnél a
            # közös cél-felbontás → ehhez igazítjuk a betűméretet és a tördelést
            if len(self.clips) == 1:
                ow = self.clips[0].width or 1280
                oh = self.clips[0].height or 720
            else:
                ow, oh = self.target_res()
            fs = max(18, int(oh / 22))            # felbontás-arányos betűméret
            margin = max(12, int(oh / 18))
            # a tartományba eső szövegek, a kezdethez igazítva (PTS 0-ról indul)
            vf = []
            idx = 0
            for n in self.notes:
                if start <= n.at < end and font:
                    rel = n.at - start
                    shutil.copyfile(font, work / "font.ttf")
                    wrapped = wrap_caption(n.text, ow, fs)   # SORTÖRDELÉS
                    (work / f"note{idx}.txt").write_text(wrapped,
                                                         encoding="utf-8")
                    vf.append(
                        f"drawtext=textfile=note{idx}.txt:fontfile=font.ttf:"
                        f"fontsize={fs}:fontcolor=white:borderw=4:"
                        f"bordercolor=black:line_spacing=8:"
                        f"x=(w-text_w)/2:y=h-text_h-{margin}:"
                        f"expansion=none:"
                        f"enable='between(t,{rel:.3f},{rel + n.dur:.3f})'")
                    idx += 1

            dur = end - start
            cmd = [ff, "-y", "-ss", f"{start:.3f}", "-i", base,
                   "-t", f"{dur:.3f}"]
            if vf:
                cmd += ["-vf", ",".join(vf)]
            cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    "-progress", "pipe:1", "-nostats", out]
            # a progress-hez külön kezeljük a stdout-ot
            return self._run_progress(cmd, str(work), dur, progress)
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def cleanup(self):
        """Az alap-videó ideiglenes mappájának törlése (ablak bezárásakor)."""
        if self._base_dir:
            shutil.rmtree(self._base_dir, ignore_errors=True)
            self._base_dir = None
            self._base = None

    def _run_progress(self, cmd, cwd, dur, progress) -> bool:
        flags = 0x08000000 if os.name == "nt" else 0
        try:
            self._proc = subprocess.Popen(
                cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, creationflags=flags)
        except OSError as e:
            self.error = str(e)
            return False
        for line in self._proc.stdout:
            if self._stop.is_set():
                break
            line = line.strip()
            if line.startswith("out_time_ms=") and dur > 0 and progress:
                try:
                    ms = int(line.split("=", 1)[1])
                    progress(min(1.0, (ms / 1_000_000) / dur))
                except (ValueError, ZeroDivisionError):
                    pass
        rc = self._proc.wait()
        if self._stop.is_set():
            self.error = "a mentést megszakították"
            return False
        if rc != 0:
            self.error = f"ffmpeg hibakód {rc}"
            return False
        if progress:
            progress(1.0)
        return True
