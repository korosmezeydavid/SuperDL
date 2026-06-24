"""AI hangalámondás (audio description) videóhoz.

A videó KÉPI tartalmát egy vízió-AI írja le, a leírásokat helyi/Edge hanggal
megszólaltatjuk, és a videóba illesztjük – alapból a PÁRBESZÉD-SZÜNETEKBE
(csend-detektálással), az eredeti hangot a narráció alatt halkítva (ducking).
Így a videó vakon is „nézhetővé" válik.

Folyamat: jelenetváltás-érzékeléssel képkockák → vízió-AI rövid leírás →
TTS hangklipek → csend-detektálás → elhelyezés + mux ducking-gal. A videósávot
`-c:v copy`-val érintetlenül hagyjuk (csak a hangsávot építjük újra).
"""

import os
import re
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from . import ffmpeg as ffmpeg_mod

_NOWIN = 0x08000000 if os.name == "nt" else 0


def _ff():
    ff = ffmpeg_mod.find_ffmpeg()
    if not ff:
        d = ffmpeg_mod.ensure_ffmpeg()
        ff = ffmpeg_mod.find_ffmpeg() if d else None
    return ff


def _run(cmd, cwd=None):
    """Lefuttat egy ffmpeg-parancsot, visszaadja a (returncode, stderr)-t."""
    try:
        r = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, text=True,
                           encoding="utf-8", errors="replace",
                           creationflags=_NOWIN, timeout=900)
        return r.returncode, r.stderr or ""
    except (OSError, subprocess.SubprocessError) as e:
        return 1, str(e)


def _scene_cuts(ff: str, src: str, threshold: float) -> list[float]:
    """A jelenetVÁLTÁSOK nyers időpontjai (mp) – ráadás a fix mintavételhez.
    (Ehhez végig kell dekódolni a videót, ezért csak a tényleges készítéskor
    futtatjuk, a gyors becslésnél nem.)"""
    _rc, err = _run([ff, "-i", src, "-vf",
                     f"select='gt(scene,{threshold})',showinfo",
                     "-vsync", "vfr", "-f", "null", "-"])
    return sorted(float(m) for m in re.findall(r"pts_time:([0-9.]+)", err))


def description_times(ff: str, src: str, min_gap: float, max_count: int,
                      scene_cuts: list[float] | None = None) -> list[float]:
    """A leírandó időpontok. ALAP: FIX időközönkénti mintavétel (így MINDEN
    videóra van leírás, akkor is, ha nincs benne éles vágás), kiegészítve a
    jelenetváltásokkal, ha kaptunk ilyet. `min_gap`-szűrés + `max_count`-korlát
    (a vízió-hívások száma = költség)."""
    dur = media_duration(ff, src)
    if dur <= 0:
        return []
    # a videó hosszához igazított időköz, hogy a max_count-ot ne lépjük túl
    interval = max(min_gap, 8.0, dur / max(1, max_count))
    times = []
    t = min(interval * 0.5, dur * 0.5)         # az első leírás kicsit beljebb
    while t < dur:
        times.append(round(t, 2))
        t += interval
    if scene_cuts:
        times = sorted(set(times) | {round(c, 2) for c in scene_cuts
                                     if 0.3 < c < dur})
    kept: list[float] = []
    for x in times:
        if not kept or x - kept[-1] >= min_gap:
            kept.append(x)
    if max_count > 0 and len(kept) > max_count:
        step = len(kept) / max_count
        kept = [kept[int(i * step)] for i in range(max_count)]
    return kept or [round(dur / 2, 2)]


def silence_gaps(ff: str, src: str, noise_db: int = -30,
                 min_dur: float = 0.8) -> list[tuple[float, float]]:
    """Csendes szakaszok (start, end) az eredeti hangban – ide tesszük a
    narrációt, hogy ne beszéljen bele a párbeszédbe."""
    _rc, err = _run([ff, "-i", src, "-af",
                     f"silencedetect=n={noise_db}dB:d={min_dur}",
                     "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", err)]
    gaps = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else s + 999
        gaps.append((s, e))
    return gaps


def has_audio(ff: str, src: str) -> bool:
    """Van-e hangsávja a videónak (a néma videók muxját másképp kell kezelni)?

    BIZONYTALANSÁGNÁL a biztonságosabb „nincs hang" (False) az alapértelmezés:
    ha tévesen feltételeznénk hangot egy néma videónál, a [0:a]-ra hivatkozó mux
    az EGÉSZ feldolgozást megbuktatná; fordítva legföljebb a narráció lesz a
    hangsáv. (A muxoló ráadásul fallbackként némaként is újrapróbálja.)"""
    pb = Path(ff).with_name("ffprobe.exe")
    if not pb.is_file():
        return False            # nem tudjuk megállapítani → biztonságos default
    try:
        r = subprocess.run([str(pb), "-v", "error", "-select_streams", "a",
                            "-show_entries", "stream=index", "-of",
                            "csv=p=0", src], capture_output=True, text=True,
                           timeout=30)
        return bool(r.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False            # bizonytalan → inkább némaként kezeljük


def media_duration(ff: str, src: str) -> float:
    pb = Path(ff).with_name("ffprobe.exe")
    if not pb.is_file():
        return 0.0
    try:
        r = subprocess.run([str(pb), "-v", "error", "-show_entries",
                            "format=duration", "-of",
                            "default=noprint_wrappers=1:nokey=1", src],
                           capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip() or 0)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def _wav_duration(ff: str, path: str) -> float:
    return media_duration(ff, path)


@dataclass
class Scene:
    at: float
    place: float = 0.0          # a tényleges elhelyezési időpont (szünetbe)
    text: str = ""
    clip: str = ""
    dur: float = 0.0


def default_describe(frame_bytes: bytes, detail: str) -> str:
    """A valódi vízió-AI hívás (a felhasználó kulcsával)."""
    from . import aiclient
    n = "egy-két tömör mondatban" if detail == "detailed" else "EGYETLEN rövid mondatban"
    prompt = ("Írd le MAGYARUL, {0}, mi látható ezen a videó-képkockán – "
              "hangalámondáshoz vak nézőnek. Csak a lényeget, jelen időben, "
              "felesleges bevezető nélkül.").format(n)
    return aiclient.vision(prompt, frame_bytes, "image/jpeg").strip()


class VideoDescriber:
    def __init__(self, src: str, out: str, *, voice: str = "espeak",
                 detail: str = "short", duck: bool = True, rate: int = 0,
                 scene_threshold: float = 0.4, min_gap: float = 4.0,
                 max_scenes: int = 40, describe_fn=None,
                 tts_fn=None, on_status=None, on_progress=None):
        self.src = src
        self.out = out
        self.voice = voice              # "espeak" vagy "edge"
        self.detail = detail            # "short" / "detailed"
        self.duck = duck
        self.rate = max(-10, min(10, int(rate)))    # tempó -10..10
        self.scene_threshold = scene_threshold
        self.min_gap = min_gap
        self.max_scenes = max_scenes
        self._describe = describe_fn or (lambda b: default_describe(b, self.detail))
        self._tts = tts_fn or self._tts_default
        self.on_status = on_status
        self.on_progress = on_progress
        self.error = ""
        self.scenes: list[Scene] = []
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def _emit(self, text):
        if self.on_status:
            self.on_status(text)

    def _prog(self, f):
        if self.on_progress:
            self.on_progress(max(0.0, min(1.0, f)))

    def estimate_scenes(self) -> int:
        """A leírandó képkockák becsült száma (= a vízió-hívások száma =
        költség). GYORS: csak a videó hosszából számol (nem dekódol végig)."""
        ff = _ff()
        if not ff:
            return 0
        return len(description_times(ff, self.src, self.min_gap,
                                     self.max_scenes))

    # ---- hang ---------------------------------------------------------

    def _tts_default(self, text: str, out_wav: str) -> bool:
        if self.voice == "edge":
            try:
                import shutil
                from . import tts
                base = os.path.splitext(out_wav)[0]      # HELYES out_base!
                # a tempót (rate -10..10) átadjuk az Edge-nek is
                path = tts.ENGINES["edge"].synth(
                    text, "hu-HU-TamasNeural", base, 0, self.rate)
                if path and os.path.isfile(path):
                    if path != out_wav:
                        shutil.copyfile(path, out_wav)   # ffmpeg tartalom szerint olvas
                    return True
            except Exception:
                pass
            # ha az Edge nem megy (pl. nincs net), essünk vissza eSpeak-re
        from .selfvoice import _espeak_paths
        exe, data = _espeak_paths()
        if not exe:
            return False
        # eSpeak tempó: az alap ~175 szó/perc; rate -10..10 -> kb. 105..295
        wpm = max(90, min(330, 175 + self.rate * 12))
        cmd = [exe, "-v", "hu", "-s", str(int(wpm)), "-w", out_wav]
        if data:
            cmd += ["--path", str(Path(data).parent)]
        cmd.append(text)
        rc, _ = _run(cmd)
        return rc == 0 and os.path.isfile(out_wav)

    # ---- fő folyamat --------------------------------------------------

    def run(self) -> bool:
        self.error = ""
        self._stop.clear()
        ff = _ff()
        if not ff:
            self.error = "az ffmpeg nem érhető el"
            return False

        work = Path(tempfile.mkdtemp(prefix="superdl_ad_"))
        try:
            self._emit("Jelenetek keresése…")
            try:
                cuts = _scene_cuts(ff, self.src, self.scene_threshold)
            except Exception:
                cuts = []
            times = description_times(ff, self.src, self.min_gap,
                                      self.max_scenes, cuts)
            if not times:
                self.error = ("nem sikerült meghatározni a videó hosszát – "
                              "ellenőrizd a fájlt")
                return False
            self.scenes = [Scene(at=t) for t in times]
            gaps = silence_gaps(ff, self.src)
            total = media_duration(ff, self.src)

            # 1) képkocka kivágása + AI-leírás + TTS jelenetenként
            inputs_audio = []
            n = len(self.scenes)
            for i, sc in enumerate(self.scenes):
                if self._stop.is_set():
                    self.error = "megszakítva"
                    return False
                self._emit(f"Jelenet leírása: {i + 1}/{n}…")
                frame = work / f"f{i}.jpg"
                _run([ff, "-y", "-ss", f"{sc.at:.3f}", "-i", self.src,
                      "-frames:v", "1", "-q:v", "3", str(frame)])
                if not frame.is_file():
                    continue
                try:
                    sc.text = self._describe(frame.read_bytes())
                except Exception as e:
                    self.error = f"AI-leírási hiba: {e}"
                    return False
                if not sc.text:
                    continue
                clip = work / f"n{i}.wav"
                if not self._tts(sc.text, str(clip)):
                    continue
                sc.clip = str(clip)
                sc.dur = _wav_duration(ff, str(clip))
                sc.place = self._place_in_gap(sc.at, sc.dur, gaps, total)
                inputs_audio.append(sc)
                self._prog((i + 1) / n * 0.7)

            if not inputs_audio:
                self.error = "egyetlen leírás sem készült el"
                return False

            # 2) mux: a narráció-klipek elhelyezése + ducking
            self._emit("A hangalámondás összeállítása…")
            ok = self._mux(ff, inputs_audio, work)
            self._prog(1.0)
            return ok
        finally:
            import shutil
            shutil.rmtree(work, ignore_errors=True)

    def _place_in_gap(self, at, dur, gaps, total):
        """A narrációt a jelenethez legközelebbi, ELÉG HOSSZÚ csendbe igazítja,
        úgy hogy a narráció VÉGE is a csenden belül maradjon – ne lógjon bele a
        következő párbeszédbe. Ha nincs elég hosszú csend, a jelenetidőre teszi
        (legjobb közelítés)."""
        margin = 0.3
        need = dur + margin
        cap = max(0.0, (total or at) - dur)      # ne lógjon túl a videó végén
        for s, e in gaps:
            if (e - s) < need:
                continue                          # ez a csend túl rövid ehhez
            if s <= at <= e:
                # a jelenetnél tartó csend: kezdjük itt, de húzzuk vissza, hogy a
                # narráció vége is beleférjen a csend végéig
                return max(0.0, min(min(at, e - need), cap))
            if s >= at and s - at < 6:
                # hamarosan jövő, elég hosszú csend → annak az elejére
                return max(0.0, min(s, cap))
        return max(0.0, min(at, cap))

    def _build_mux_cmd(self, ff, scenes, orig_audio):
        """A mux-parancs összeállítása a megadott „van-e eredeti hang" feltétellel."""
        cmd = [ff, "-y", "-i", self.src]
        for sc in scenes:
            cmd += ["-i", sc.clip]
        parts = []
        for idx, sc in enumerate(scenes):
            inp = idx + 1
            ms = int(sc.place * 1000)
            parts.append(
                f"[{inp}:a]aformat=channel_layouts=stereo,"
                f"adelay={ms}:all=1[d{idx}]")
        mixin = "".join(f"[d{idx}]" for idx in range(len(scenes)))
        if len(scenes) == 1:
            parts.append("[d0]anull[narr]")
        else:
            parts.append(f"{mixin}amix=inputs={len(scenes)}:normalize=0[narr]")
        if not orig_audio:
            # néma videó: a narráció maga lesz a hangsáv
            parts.append("[narr]anull[aout]")
        elif self.duck:
            parts.insert(0, "[0:a]aformat=channel_layouts=stereo[orig]")
            parts.append("[narr]asplit=2[narrA][narrB]")
            parts.append("[orig][narrA]sidechaincompress=threshold=0.03:"
                         "ratio=8:attack=20:release=300[duck]")
            parts.append("[duck][narrB]amix=inputs=2:normalize=0[aout]")
        else:
            parts.insert(0, "[0:a]aformat=channel_layouts=stereo[orig]")
            parts.append("[orig][narr]amix=inputs=2:normalize=0[aout]")
        graph = ";".join(parts)
        cmd += ["-filter_complex", graph, "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", self.out]
        return cmd

    def _mux(self, ff, scenes, work) -> bool:
        """A videó hangsávjának újraépítése: a narráció-klipeket a helyükre
        késleltetjük, összemixeljük, és (ducking esetén) az eredeti hangot a
        narráció alatt halkítjuk. A videósávot érintetlenül hagyjuk (-c:v copy)."""
        orig_audio = has_audio(ff, self.src)
        rc, err = _run(self._build_mux_cmd(ff, scenes, orig_audio),
                       cwd=str(work))
        # FALLBACK: ha hangos muxot próbáltunk és elbukott (pl. a videónak
        # mégsincs használható hangsávja), próbáljuk újra némaként – egy
        # narráció-csak hangsáv jobb, mint a teljes kudarc
        if rc != 0 and orig_audio:
            rc, err = _run(self._build_mux_cmd(ff, scenes, False),
                           cwd=str(work))
        if rc != 0:
            self.error = (err.strip().splitlines()[-1]
                          if err.strip() else "a mux nem sikerült")
            return False
        return True
