"""Internetes rádió FELVÉTELE fájlba az ffmpeg-gel.

Kétféleképpen:
  • Kézi felvétel: azonnal indul és bármikor leállítható.
  • Időzített felvétel: megadod, melyik állomást, mettől meddig, és hogy
    egyszeri / minden nap / a hét adott napjain ismétlődjön. A program a
    beállított időben magától felveszi.

A felvételek MP3-ként (192 kbps) a célmappa „Rádiófelvételek/ÉÉÉÉ-HH-NN"
DÁTUMOZOTT almappájába kerülnek, a fájlnévben az állomás nevével és az
időponttal.

FONTOS: az időzített felvételhez a SuperDL-nek FUTNIA kell (a gép legyen
bekapcsolva, a program nyitva) – ez nem Windows-szolgáltatás. Ha a program
épp a felvételi időablakon belül indul el, a hátralévő részt rögzíti.

Csak olyan adást vegyél fel, amelyhez jogod van! Az internetes rádiók élő,
szabadon foghatók – a felvétel egyéni, személyes használatra készül.
"""

import re
import subprocess
import threading
import uuid as _uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path

from . import store
from .audioengine import _ffmpeg_exe

WEEKDAY_NAMES = ["hétfő", "kedd", "szerda", "csütörtök", "péntek",
                 "szombat", "vasárnap"]
WEEKDAY_SHORT = ["H", "K", "Sze", "Cs", "P", "Szo", "V"]


def _safe(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\n\r\t]+', " ", name or "").strip()
    name = re.sub(r"\s+", " ", name)
    return (name or "rádió")[:80]


def _out_path(base_dir: str, station_name: str, when: datetime) -> Path:
    folder = Path(base_dir) / "Rádiófelvételek" / when.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    fname = f"{_safe(station_name)} {when.strftime('%Y-%m-%d %H-%M-%S')}.mp3"
    return folder / fname


class ActiveRecording:
    """Egyetlen, épp futó (vagy frissen befejezett) felvétel."""

    def __init__(self, station_name, url, base_dir, duration_s=None,
                 scheduled=False, on_done=None):
        self.station_name = station_name
        self.url = url
        self.duration_s = duration_s
        self.scheduled = scheduled
        self.on_done = on_done
        self.start_time = datetime.now()
        self.path = _out_path(base_dir, station_name, self.start_time)
        self.status = "felvétel"        # felvétel / kész / leállítva / hiba
        self.error = ""
        self._proc = None
        self._stop = threading.Event()

    def start(self) -> bool:
        ff = _ffmpeg_exe()
        if not ff:
            self.status, self.error = "hiba", "az ffmpeg nem érhető el"
            return False
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        cmd = [ff, "-hide_banner", "-loglevel", "error",
               "-rw_timeout", "15000000",          # 15 mp I/O-időkorlát
               "-i", self.url, "-vn",
               "-c:a", "libmp3lame", "-b:a", "192k"]
        if self.duration_s and self.duration_s > 0:
            cmd += ["-t", str(int(self.duration_s))]
        cmd += ["-y", str(self.path)]
        try:
            self._proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, creationflags=flags)
        except Exception as e:
            self.status, self.error = "hiba", str(e)
            return False
        threading.Thread(target=self._watch, daemon=True).start()
        return True

    def _watch(self):
        self._proc.wait()
        if self._stop.is_set():
            self.status = "leállítva"
        elif self._has_audio():
            self.status = "kész"
        else:
            self.status = "hiba"
            self.error = "az állomás nem elérhető, vagy a felvétel megszakadt"
        if self.on_done:
            try:
                self.on_done(self)
            except Exception:
                pass

    def _has_audio(self) -> bool:
        try:
            return self.path.is_file() and self.path.stat().st_size > 8192
        except OSError:
            return False

    def stop(self):
        if not self.is_active():
            return
        self._stop.set()
        p = self._proc
        try:
            p.stdin.write(b"q")          # ffmpeg sima leállítás (lezárja a fájlt)
            p.stdin.flush()
        except Exception:
            pass

        def killer():
            try:
                p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        threading.Thread(target=killer, daemon=True).start()

    def is_active(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def elapsed_s(self) -> int:
        return int((datetime.now() - self.start_time).total_seconds())


@dataclass
class Schedule:
    id: str
    station_name: str
    url: str
    start_h: int
    start_m: int
    end_h: int
    end_m: int
    repeat: str = "once"               # once / daily / weekly
    weekdays: list = field(default_factory=list)   # 0=hétfő .. 6=vasárnap
    date: str = ""                     # once: a tervezett dátum (ÉÉÉÉ-HH-NN)
    enabled: bool = True
    last_run_date: str = ""

    def duration_s(self) -> int:
        s = self.start_h * 60 + self.start_m
        e = self.end_h * 60 + self.end_m
        if e <= s:
            e += 24 * 60
        return (e - s) * 60

    def describe(self) -> str:
        rng = (f"{self.start_h:02d}:{self.start_m:02d}–"
               f"{self.end_h:02d}:{self.end_m:02d}")
        if self.repeat == "daily":
            rep = "minden nap"
        elif self.repeat == "weekly":
            days = [WEEKDAY_NAMES[d] for d in sorted(self.weekdays)]
            rep = ", ".join(days) if days else "(nincs nap kijelölve)"
        else:
            rep = f"egyszeri – {self.date or 'következő alkalom'}"
        állapot = "" if self.enabled else " [kikapcsolva]"
        return f"{self.station_name} – {rng} – {rep}{állapot}"


class RecordManager:
    """A felvételek központja: időzítő háttérszál, aktív felvételek és a
    mentett időzítések. A GUI-tól független, így a felvétel akkor is elindul,
    ha a rádió-ablak épp zárva van (csak a program fusson)."""

    FIELDS = {"id", "station_name", "url", "start_h", "start_m", "end_h",
              "end_m", "repeat", "weekdays", "date", "enabled",
              "last_run_date"}

    def __init__(self, base_dir_getter, on_event=None):
        self._base_dir_getter = base_dir_getter      # hívható -> str
        self.on_event = on_event                     # hívható(szöveg, szint)
        self.active: list[ActiveRecording] = []
        self._lock = threading.Lock()
        self.schedules: list[Schedule] = []
        for r in store.load_radio_schedule():
            try:
                self.schedules.append(Schedule(
                    **{k: v for k, v in r.items() if k in self.FIELDS}))
            except Exception:
                pass
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    # ---- segédek ------------------------------------------------------

    @staticmethod
    def new_id() -> str:
        return _uuid.uuid4().hex[:12]

    def base_dir(self) -> str:
        try:
            d = self._base_dir_getter()
        except Exception:
            d = ""
        return d or str(Path.home() / "Downloads")

    def _emit(self, text, level="info"):
        if self.on_event:
            try:
                self.on_event(text, level)
            except Exception:
                pass

    def save(self):
        store.save_radio_schedule([asdict(s) for s in self.schedules])

    # ---- időzítések ---------------------------------------------------

    def add_schedule(self, s: Schedule):
        with self._lock:
            self.schedules.append(s)
        self.save()

    def remove_schedule(self, sid: str):
        with self._lock:
            self.schedules = [s for s in self.schedules if s.id != sid]
        self.save()

    def set_enabled(self, sid: str, on: bool):
        for s in self.schedules:
            if s.id == sid:
                s.enabled = on
                if on:
                    s.last_run_date = ""    # újra figyelembe vesszük ma is
        self.save()

    def list_schedules(self) -> list[Schedule]:
        with self._lock:
            return list(self.schedules)

    # ---- kézi felvétel ------------------------------------------------

    def start_manual(self, station_name, url, duration_s=None):
        rec = ActiveRecording(station_name, url, self.base_dir(),
                              duration_s=duration_s, scheduled=False,
                              on_done=self._on_done)
        if rec.start():
            with self._lock:
                self.active.append(rec)
            self._emit(f"Felvétel elindult: {station_name} → {rec.path.name}",
                       "start")
            return rec
        self._emit(f"A felvétel nem indult el: {rec.error}", "error")
        return None

    def snapshot_active(self) -> list[ActiveRecording]:
        with self._lock:
            return [r for r in self.active if r.is_active()]

    def stop_all_active(self):
        for r in list(self.active):
            r.stop()

    def _on_done(self, rec: ActiveRecording):
        with self._lock:
            if rec in self.active:
                self.active.remove(rec)
        if rec.status == "kész":
            self._emit(f"Felvétel kész: {rec.station_name} → {rec.path}", "done")
        elif rec.status == "leállítva":
            self._emit(f"Felvétel leállítva és mentve: {rec.station_name} "
                       f"→ {rec.path}", "done")
        else:
            self._emit(f"Felvételi hiba: {rec.station_name} – {rec.error}",
                       "error")

    # ---- időzítő háttérszál -------------------------------------------

    def _loop(self):
        while not self._stop.wait(20):
            try:
                self._tick()
            except Exception:
                pass

    def _tick(self):
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        for s in self.list_schedules():
            if not s.enabled or s.last_run_date == today:
                continue
            if s.repeat == "weekly" and now.weekday() not in (s.weekdays or []):
                continue
            if s.repeat == "once" and s.date and s.date != today:
                if s.date < today:                 # lejárt, sosem futott
                    s.enabled = False
                    self.save()
                continue
            start_dt = now.replace(hour=s.start_h, minute=s.start_m,
                                   second=0, microsecond=0)
            end_dt = now.replace(hour=s.end_h, minute=s.end_m,
                                 second=0, microsecond=0)
            if (s.end_h * 60 + s.end_m) <= (s.start_h * 60 + s.start_m):
                end_dt += timedelta(days=1)
            if start_dt <= now < end_dt:
                duration = int((end_dt - now).total_seconds())
                if duration >= 5:
                    self._fire(s, duration, today)

    def _fire(self, s: Schedule, duration: int, today: str):
        s.last_run_date = today
        if s.repeat == "once":
            s.enabled = False
        self.save()
        rec = ActiveRecording(s.station_name, s.url, self.base_dir(),
                              duration_s=duration, scheduled=True,
                              on_done=self._on_done)
        if rec.start():
            with self._lock:
                self.active.append(rec)
            self._emit(f"Időzített felvétel elindult: {s.station_name} "
                       f"(kb. {max(1, duration // 60)} perc) → {rec.path.name}",
                       "start")
        else:
            self._emit(f"Az időzített felvétel nem indult el: "
                       f"{s.station_name} – {rec.error}", "error")

    def shutdown(self):
        self._stop.set()
        self.stop_all_active()
        self.save()
