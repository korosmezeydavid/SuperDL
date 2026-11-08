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

import math
import os
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from superdl import ffmpeg as ffmpeg_mod    # megosztott Core-modulok
from superdl import proc as procutil        # alfolyamat-életciklus (MK4)
from superdl.videocompose import _find_font, human_time, media_duration, wrap_caption

OUT_FORMATS = (("MP4 – ajánlott", "mp4"), ("MKV", "mkv"), ("AVI", "avi"))
EFFECT_GAIN = 0.35
PREVIEW_SECONDS = 15.0
NOTE_DEFAULT_DUR = 4.0          # egy magyarázó szöveg alap megjelenési ideje (mp)


def _ffprobe() -> str | None:
    ff = ffmpeg_mod.find_ffmpeg()
    if not ff:
        return None
    p = Path(ff).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
    return str(p) if p.is_file() else None


def probe(path: str) -> tuple[float, int, int]:
    """(hossz_mp, szélesség, magasság) – ffprobe-bal."""
    pb = _ffprobe()
    if not pb:
        return 0.0, 0, 0
    def q(args):
        try:
            r = subprocess.run([pb, "-v", "error", *args, path],
                               capture_output=True, text=True, timeout=30,
                               # konzolablak nélkül: az elvinné a fókuszt
                               creationflags=getattr(
                                   subprocess, "CREATE_NO_WINDOW", 0))
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
class TimelineLayer:
    kind: str
    path: str
    at: float
    duration: float


def _has_audio(path: str) -> bool:
    probe_path = _ffprobe()
    if not probe_path:
        raise OSError("Az ffprobe nem érhető el.")
    result = subprocess.run(
        [probe_path, "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=index", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True, timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return bool(result.stdout.strip())


def _audio_chain(duration):
    return (f"aresample=48000,aformat=channel_layouts=stereo,"
            f"apad,atrim=duration={duration:.6f},asetpts=PTS-STARTPTS")


def _caption_filters(captions, work, width, height):
    font = _find_font()
    if not captions or not font:
        return []
    shutil.copyfile(font, work / "font.ttf")
    size = max(18, int(height / 22))
    margin = max(12, int(height / 18))
    filters = []
    for i, (note, at) in enumerate(captions):
        (work / f"note{i}.txt").write_text(wrap_caption(note.text, width, size), encoding="utf-8")
        filters.append(
            f"drawtext=textfile=note{i}.txt:fontfile=font.ttf:fontsize={size}:"
            f"fontcolor=white:borderw=4:bordercolor=black:line_spacing=8:"
            f"x=(w-text_w)/2:y=h-text_h-{margin}:expansion=none:"
            f"enable='between(t,{at:.3f},{at + note.dur:.3f})'")
    return filters


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
        self.layers: list[TimelineLayer] = []
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


    def add_layer(self, kind, path, at, duration=None):
        path = str(Path(path).resolve())
        if not math.isfinite(at) or not 0 <= at < self.total_duration():
            raise ValueError("Válassz a videón belüli kezdőpontot.")
        if kind == "image":
            _, width, height = probe(path)
            if not width or not height:
                raise ValueError("A képet nem sikerült beolvasni.")
        elif kind == "audio":
            duration = media_duration(path)
            if not _has_audio(path):
                raise ValueError("A fájlban nincs lejátszható hang.")
        else:
            raise ValueError("Ismeretlen beszúrástípus.")
        if duration is None or not math.isfinite(duration) or duration <= 0:
            raise ValueError("Adj meg pozitív, érvényes időtartamot.")
        layer = TimelineLayer(kind, path, at, duration)
        self.layers.append(layer)
        self.layers.sort(key=lambda item: item.at)
        return layer

    def _layer_inputs(self, cmd, base, ranges, *, video=True):
        """Apply the layers on the project timeline before trimming any ranges."""
        total = self.total_duration()
        graph = []
        video_stream = "0:v:0"
        if video:
            graph.append("[0:v:0]setpts=PTS-STARTPTS[vbase]")
            video_stream = "vbase"
        audio_stream = ""
        if _has_audio(base):
            graph.append(f"[0:a:0]{_audio_chain(total)}[abase]")
            audio_stream = "abase"

        width, height = self.target_res()
        effects = []
        source = 0
        for layer in self.layers:
            if not video and layer.kind == "image":
                continue
            end = min(total, layer.at + layer.duration)
            if not any(layer.at < right and end > left for left, right in ranges):
                continue
            cmd.extend(["-i", layer.path])
            source += 1
            if layer.kind == "image":
                graph.append(
                    f"[{source}:v:0]trim=end_frame=1,setpts=PTS-STARTPTS,"
                    f"scale={max(1, int(width * .4))}:{max(1, int(height * .4))}:"
                    f"force_original_aspect_ratio=decrease,setsar=1[image{source}]")
                graph.append(
                    f"[{video_stream}][image{source}]overlay="
                    f"x=main_w-overlay_w-main_w*0.04:y=main_h*0.04:"
                    f"enable='gte(t,{layer.at:.6f})*lt(t,{end:.6f})'[layer{source}]")
                video_stream = f"layer{source}"
            else:
                graph.append(
                    f"[{source}:a:0]aresample=48000,aformat=channel_layouts=stereo,"
                    f"atrim=duration={end - layer.at:.6f},asetpts=PTS-STARTPTS,"
                    f"volume={EFFECT_GAIN},adelay={round(layer.at * 48000)}S:all=1[effect{source}]")
                effects.append(f"[effect{source}]")
        if effects:
            if not audio_stream:
                graph.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={total:.6f}[abase]")
            graph.append(f"[abase]{''.join(effects)}amix=inputs={len(effects) + 1}:"
                         "duration=first:normalize=0,alimiter=limit=0.95:level=0:latency=1[mixed]")
            audio_stream = "mixed"
        return graph, video_stream, audio_stream

    def _render_layers(self, ff, ranges, out, work, progress):
        base = self._ensure_base(ff)
        if not base:
            return False
        cmd = [ff, "-hide_banner", "-loglevel", "error", "-y",
               "-filter_complex_threads", "1", "-i", base]
        graph, video, audio = self._layer_inputs(cmd, base, ranges)
        if len(ranges) > 1:
            graph.append(f"[{video}]split={len(ranges)}" + "".join(f"[vs{i}]" for i in range(len(ranges))))
            if audio:
                graph.append(f"[{audio}]asplit={len(ranges)}" + "".join(f"[as{i}]" for i in range(len(ranges))))
        segments = []
        for i, (left, right) in enumerate(ranges):
            vsource = f"vs{i}" if len(ranges) > 1 else video
            graph.append(f"[{vsource}]trim=start={left:.6f}:end={right:.6f},setpts=PTS-STARTPTS[v{i}]")
            segments.append(f"[v{i}]")
            if audio:
                asource = f"as{i}" if len(ranges) > 1 else audio
                graph.append(f"[{asource}]atrim=start={left:.6f}:end={right:.6f},asetpts=PTS-STARTPTS[a{i}]")
                segments.append(f"[a{i}]")
        if len(ranges) > 1:
            graph.append(f"{''.join(segments)}concat=n={len(ranges)}:v=1:a={int(bool(audio))}"
                         + ("[video][audio]" if audio else "[video]"))
            video, audio = "video", "audio" if audio else ""
        else:
            video, audio = "v0", "a0" if audio else ""

        width, height = self.target_res()
        offset = 0.0
        captions = []
        for left, right in ranges:
            captions.extend((note, offset + note.at - left)
                            for note in self.notes if left <= note.at < right)
            offset += right - left
        filters = _caption_filters(captions, work, width, height)
        if filters:
            graph.append(f"[{video}]{','.join(filters)}[captioned]")
            video = "captioned"

        graph.append(f"[{video}]pad=ceil(iw/2)*2:ceil(ih/2)*2[output_video]")
        cmd += ["-filter_complex", ";".join(graph), "-map", "[output_video]"]
        if audio:
            cmd += ["-map", f"[{audio}]"]
        cmd += ["-t", f"{offset:.6f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                "-progress", "pipe:1", "-nostats"]
        destination = Path(out).resolve()
        inputs = [Path(clip.path).resolve() for clip in self.clips]
        inputs.extend(Path(layer.path) for layer in self.layers)
        if destination in inputs:
            self.error = "A mentéshez válassz a forrásfájloktól eltérő nevet."
            return False
        with tempfile.TemporaryDirectory(prefix="superdl_output_", dir=destination.parent) as staging:
            temporary = Path(staging) / destination.name
            if not self._run_progress(cmd + [str(temporary)], str(work), offset, progress):
                return False
            os.replace(temporary, destination)
        return True

    def preview_audio(self, start, out):
        """Render a short excerpt using the same mix as the saved video."""
        self._stop.clear()
        self.error = ""
        try:
            end = min(self.total_duration(), start + PREVIEW_SECONDS)
            if end - start < 0.1:
                self.error = "Az előnézethez válassz korábbi időpontot."
                return False
            ff = self._ff()
            base = self._ensure_base(ff) if ff else None
            if not base:
                self.error = self.error or "A videó hangja nem érhető el."
                return False
            cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", base]
            graph, _, audio = self._layer_inputs(cmd, base, [(start, end)], video=False)
            if not audio:
                self.error = "Ezen a szakaszon nincs lejátszható hang."
                return False
            graph.append(f"[{audio}]atrim=start={start:.6f}:end={end:.6f},asetpts=PTS-STARTPTS[preview]")
            return self._run(cmd + ["-filter_complex", ";".join(graph), "-map", "[preview]", out])
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            self.error = str(error)
            return False

    # ---- vezérlés -----------------------------------------------------

    def stop(self):
        self._stop.set()
        procutil.stop_proc(self._proc)     # terminate→wait→kill→wait + csövek

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
            if self._stop.is_set():
                procutil.stop_proc(self._proc)
                return False
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
        cmd = [ff, "-y", "-filter_complex_threads", "1"]
        for c in self.clips:
            cmd += ["-i", c.path]
        parts = []
        for i in range(len(self.clips)):
            parts.append(
                f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=25[v{i}]")
        for i, clip in enumerate(self.clips):
            source = f"[{i}:a:0]" if _has_audio(clip.path) else "anullsrc=r=48000:cl=stereo,"
            parts.append(f"{source}{_audio_chain(clip.duration)}[a{i}]")
        streams = "".join(f"[v{i}][a{i}]" for i in range(len(self.clips)))
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
            if self.layers:
                return self._render_layers(ff, [(start, end)], out, work, progress)
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
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            self.error = str(error)
            return False
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def export_cut(self, cut_start: float, cut_end: float, out: str,
                   progress=None) -> bool:
        """A globális idővonalból KIVÁGJA a [cut_start, cut_end] szakaszt, és a
        megmaradt elejét [0, cut_start) és végét [cut_end, vége) ÖSSZEFŰZVE menti
        `out`-ba – a videó ennyivel rövidebb lesz. A megmaradó magyarázó szövegek
        a kivágás hosszával előrébb csúsznak; a kivágott részbe esők kimaradnak.
        Egyetlen ffmpeg-menetben, a trim+concat szűrővel. True = siker."""
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
        cut_start = max(0.0, cut_start)
        cut_end = min(cut_end if cut_end > 0 else total, total)
        if cut_end - cut_start < 0.1:
            self.error = "a kivágandó szakasz túl rövid"
            return False
        head = cut_start > 0.05                    # marad-e eleje
        tail = cut_end < total - 0.05              # marad-e vége
        if not head and not tail:
            self.error = "a kivágás az egész videót érintené"
            return False

        gap = cut_end - cut_start
        out_dur = total - gap
        work = Path(tempfile.mkdtemp(prefix="superdl_cut_"))
        try:
            if self.layers:
                ranges = ([(0.0, cut_start)] if head else []) + ([(cut_end, total)] if tail else [])
                return self._render_layers(ff, ranges, out, work, progress)
            base = self._ensure_base(ff)
            if not base:
                self.error = self.error or "az összefűzés nem sikerült"
                return False

            vparts, aparts = [], []
            n = 0
            if head:
                vparts.append(f"[0:v]trim=start=0:end={cut_start:.3f},"
                              f"setpts=PTS-STARTPTS[v{n}]")
                aparts.append(f"[0:a]atrim=start=0:end={cut_start:.3f},"
                              f"asetpts=PTS-STARTPTS[a{n}]")
                n += 1
            if tail:
                vparts.append(f"[0:v]trim=start={cut_end:.3f},"
                              f"setpts=PTS-STARTPTS[v{n}]")
                aparts.append(f"[0:a]atrim=start={cut_end:.3f},"
                              f"asetpts=PTS-STARTPTS[a{n}]")
                n += 1
            graph = ";".join(vparts + aparts)
            if n == 1:
                graph += ";[v0]null[vc];[a0]anull[a]"
            else:
                vl = "".join(f"[v{i}]" for i in range(n))
                al = "".join(f"[a{i}]" for i in range(n))
                graph += (f";{vl}concat=n={n}:v=1:a=0[vc]"
                          f";{al}concat=n={n}:v=0:a=1[a]")

            # a megmaradó szövegek ráégetése a [vc]-re, csúsztatott időzítéssel
            font = _find_font()
            if len(self.clips) == 1:
                ow = self.clips[0].width or 1280
                oh = self.clips[0].height or 720
            else:
                ow, oh = self.target_res()
            fs = max(18, int(oh / 22))
            margin = max(12, int(oh / 18))
            draws = []
            idx = 0
            for note in self.notes:
                t = note.at
                if cut_start <= t < cut_end or not font:
                    continue                       # kivágott részbe esik / nincs font
                rel = t if t < cut_start else t - gap
                shutil.copyfile(font, work / "font.ttf")
                (work / f"note{idx}.txt").write_text(
                    wrap_caption(note.text, ow, fs), encoding="utf-8")
                draws.append(
                    f"drawtext=textfile=note{idx}.txt:fontfile=font.ttf:"
                    f"fontsize={fs}:fontcolor=white:borderw=4:bordercolor=black:"
                    f"line_spacing=8:x=(w-text_w)/2:y=h-text_h-{margin}:"
                    f"expansion=none:"
                    f"enable='between(t,{rel:.3f},{rel + note.dur:.3f})'")
                idx += 1
            if draws:
                graph += f";[vc]{','.join(draws)}[v]"
                vmap = "[v]"
            else:
                vmap = "[vc]"

            cmd = [ff, "-y", "-i", base, "-filter_complex", graph,
                   "-map", vmap, "-map", "[a]",
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                   "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                   "-progress", "pipe:1", "-nostats", out]
            return self._run_progress(cmd, str(work), out_dur, progress)
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            self.error = str(error)
            return False
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
        if self._stop.is_set():
            procutil.stop_proc(self._proc)
            self.error = "a mentést megszakították"
            return False
        last_error = ""
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
            elif line and "=" not in line:
                last_error = line
        rc = self._proc.wait()
        procutil.close_pipes(self._proc)      # a stdout bezárása (MK4)
        if self._stop.is_set():
            self.error = "a mentést megszakították"
            return False
        if rc != 0:
            self.error = last_error or f"ffmpeg hibakód {rc}"
            return False
        if progress:
            progress(1.0)
        return True
