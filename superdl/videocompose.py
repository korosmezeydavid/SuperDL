"""Videó készítése állóképből (háttér) + zenéből, idővonalra helyezett
szöveg- és kép-overlay-ekkel, ffmpeg filtergraph-fal.

A felhasználói döntések (rögzítve a tervben):
  * az overlay időtartama A KÖVETKEZŐ BESZÚRÁSIG tart (vagy a videó végéig),
  * a beszúrt KÉP rúsztatva, KÖZÉPEN, kisebbítve (a háttér végig látszik),
  * a SZÖVEG nagy fehér betű FEKETE KONTÚRRAL, középen alul,
  * a kimenet alapból MP4 (H.264 + AAC, 1080p), de MKV/AVI is választható.

A Windows path-escape gondok elkerülésére a render egy ideiglenes
munkamappában fut: a szöveg- és betűfájlok PUSZTA néven szerepelnek a
filtergraph drawtext-jében (nincs kettőspont/visszaper az értékben).
"""

import os
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from . import ffmpeg as ffmpeg_mod

VIDEO_FORMATS = ("mp4", "mkv", "avi")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff")


@dataclass
class Element:
    """Egy idővonalra helyezett elem."""
    at: float                     # kezdő időpont másodpercben
    kind: str                     # "text" vagy "image"
    content: str                  # a szöveg, vagy a kép elérési útja

    def label(self) -> str:
        """Akadálymentes, felolvasható leírás a listához."""
        t = human_time(self.at)
        if self.kind == "text":
            return f"{t} – Szöveg: {self.content}"
        return f"{t} – Kép: {Path(self.content).name}"


def human_time(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def wrap_caption(text: str, frame_w: int, fontsize: int) -> str:
    """A feliratot sorokra tördeli, hogy BEFÉRJEN a kép szélességébe (a
    drawtext magától nem tördel, ezért a hosszú szöveg kilógna a kép szélein).
    Az átlagos betűszélességet a fontméret ~0,5-szeresének vesszük, margóval."""
    import textwrap
    usable = max(40, int(frame_w * 0.90))
    per_line = max(6, int(usable / max(1, fontsize * 0.5)))
    out = []
    for para in (text or "").split("\n"):
        out.extend(textwrap.wrap(para, width=per_line) or [""])
    return "\n".join(out)


def _ffprobe() -> str | None:
    ff = ffmpeg_mod.find_ffmpeg()
    if not ff:
        return None
    p = Path(ff).with_name("ffprobe.exe")
    return str(p) if p.is_file() else None


def media_duration(path: str) -> float:
    """A megadott média (zene) hossza másodpercben, ffprobe-bal. 0, ha nem
    határozható meg."""
    pb = _ffprobe()
    if not pb:
        return 0.0
    try:
        out = subprocess.run(
            [pb, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30)
        return float(out.stdout.strip() or 0)
    except (ValueError, OSError, subprocess.SubprocessError):
        return 0.0


def _find_font() -> str | None:
    """Egy Unicode TTF a magyar ékezetekhez (ő/ű is). A Windowson mindig
    elérhető Arial-t részesítjük előnyben, több tartalékkal."""
    win = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for name in ("arial.ttf", "segoeui.ttf", "tahoma.ttf", "verdana.ttf",
                 "calibri.ttf"):
        c = win / name
        if c.is_file():
            return str(c)
    # csomagolt tartalék (ha egyszer mellécsomagoljuk)
    if getattr(__import__("sys"), "_MEIPASS", None):
        m = Path(__import__("sys")._MEIPASS) / "DejaVuSans.ttf"
        if m.is_file():
            return str(m)
    return None


def _fmt_t(t: float) -> str:
    """Időpont a between(t,...) kifejezéshez (3 tizedes elég)."""
    return f"{t:.3f}"


def build_filtergraph(
        elements: list[Element], total: float, width: int, height: int
) -> tuple[str, list[str], list[Element], str]:
    """A filtergraph összeállítása. Visszaad:
      - a teljes filter_complex sztringet,
      - a beszúrandó KÉP-bemenetek elérési útjait (a -i sorrendben),
      - a SZÖVEG-elemeket (sorrendben), hogy a hívó textfile-okat írhasson,
      - a VÉGSŐ videócímke nevét (-map ehhez).
    A háttér a 0. bemenet, a zene az 1., a képek a 2., 3., ... bemenetek."""
    parts = [
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=25[base]"
    ]
    cur = "base"
    img_paths: list[str] = []
    text_elems: list[Element] = []
    img_input = 2                 # 0=háttér, 1=zene, innen jönnek a képek

    ordered = sorted(enumerate(elements), key=lambda kv: kv[1].at)
    for n, (_, el) in enumerate(ordered):
        start = max(0.0, el.at)
        # az elem a KÖVETKEZŐ elem kezdetéig (vagy a végéig) látszik
        end = ordered[n + 1][1].at if n + 1 < len(ordered) else total
        if end <= start:
            end = total if total > start else start + 3.0
        nxt = f"v{n}"
        if el.kind == "image":
            iw, ih = int(width * 0.6), int(height * 0.6)
            parts.append(
                f"[{img_input}:v]scale={iw}:{ih}:"
                f"force_original_aspect_ratio=decrease[img{n}]")
            parts.append(
                f"[{cur}][img{n}]overlay=(W-w)/2:(H-h)/2:"
                f"enable='between(t,{_fmt_t(start)},{_fmt_t(end)})'[{nxt}]")
            img_paths.append(el.content)
            img_input += 1
        else:  # text
            idx = len(text_elems)
            fontsize = max(24, int(height / 18))      # ~60 px 1080p-nél
            margin = int(height / 18)
            parts.append(
                f"[{cur}]drawtext=textfile=text{idx}.txt:fontfile=font.ttf:"
                f"fontsize={fontsize}:fontcolor=white:borderw=4:"
                f"bordercolor=black:line_spacing=8:"
                f"x=(w-text_w)/2:y=h-text_h-{margin}:"
                f"expansion=none:"
                f"enable='between(t,{_fmt_t(start)},{_fmt_t(end)})'[{nxt}]")
            text_elems.append(el)
        cur = nxt

    # a végső videócímke nevét a hívó az utolsó [vN], vagy [base], ha nincs elem
    graph = ";".join(parts)
    final_label = cur
    # a final_label-t a graph utolsó kimenete adja; jelöljük egyértelműen
    return graph, img_paths, text_elems, final_label


class VideoComposer:
    def __init__(self, background: str, music: str, elements: list[Element],
                 out_path: str, fmt: str = "mp4",
                 resolution: tuple[int, int] = (1920, 1080),
                 progress=None, ff_progress=None):
        self.background = background
        self.music = music
        self.elements = list(elements)
        self.out_path = out_path
        self.fmt = (fmt or "mp4").lower()
        self.width, self.height = resolution
        self.progress = progress          # progress(percent: float 0..1)
        self.ff_progress = ff_progress     # ffmpeg-letöltés folyamatjelző
        self._proc = None
        self._stop = threading.Event()
        self.error = ""

    def stop(self):
        self._stop.set()
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def render(self) -> bool:
        """A videó renderelése. True, ha sikerült. A hibát az `error` mezőbe
        teszi."""
        ff = ffmpeg_mod.find_ffmpeg()
        if not ff:
            ff_dir = ffmpeg_mod.ensure_ffmpeg(self.ff_progress)
            ff = ffmpeg_mod.find_ffmpeg() if ff_dir else None
        if not ff:
            self.error = ("Az ffmpeg nem érhető el, és nem sikerült letölteni. "
                          "Ellenőrizd az internetkapcsolatot.")
            return False

        font = _find_font()
        if not font:
            self.error = ("Nem találtam betűkészletet a szöveghez "
                          "(C:\\Windows\\Fonts\\arial.ttf).")
            return False

        total = media_duration(self.music)
        if total <= 0:
            self.error = ("Nem sikerült meghatározni a zene hosszát. "
                          "Ellenőrizd a zenei fájlt.")
            return False

        graph, img_paths, text_elems, final_label = build_filtergraph(
            self.elements, total, self.width, self.height)

        work = Path(tempfile.mkdtemp(prefix="superdl_vid_"))
        try:
            shutil.copyfile(font, work / "font.ttf")
            fs = max(24, int(self.height / 18))
            for i, el in enumerate(text_elems):
                (work / f"text{i}.txt").write_text(
                    wrap_caption(el.content, self.width, fs), encoding="utf-8")

            cmd = [ff, "-y",
                   "-loop", "1", "-framerate", "25", "-i", self.background,
                   "-i", self.music]
            for p in img_paths:
                cmd += ["-loop", "1", "-i", p]
            cmd += ["-filter_complex", graph,
                    "-map", f"[{final_label}]", "-map", "1:a",
                    "-c:v", "libx264", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-progress", "pipe:1", "-nostats",
                    self.out_path]

            flags = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
            self._proc = subprocess.Popen(
                cmd, cwd=str(work), stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, creationflags=flags)

            for line in self._proc.stdout:
                if self._stop.is_set():
                    break
                line = line.strip()
                if line.startswith("out_time_ms=") and self.progress and total:
                    try:
                        ms = int(line.split("=", 1)[1])
                        self.progress(min(1.0, (ms / 1_000_000) / total))
                    except (ValueError, ZeroDivisionError):
                        pass
            rc = self._proc.wait()
            if self._stop.is_set():
                self.error = "A renderelést megszakították."
                return False
            if rc != 0:
                self.error = (f"Az ffmpeg hibával állt le (kód {rc}). "
                              "Ellenőrizd a bemeneti fájlokat.")
                return False
            if self.progress:
                self.progress(1.0)
            return True
        except OSError as e:
            self.error = f"Renderelési hiba: {e}"
            return False
        finally:
            shutil.rmtree(work, ignore_errors=True)
