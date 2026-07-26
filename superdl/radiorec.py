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
import time
import uuid as _uuid
from collections import deque
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


# A választható felvételi formátumok: kulcs → (ffmpeg-kódoló, kiterjesztés,
# szegmens-formátum a daraboláshoz). MP3 = univerzális; Opus = jobb minőség
# kisebb méreten (mindkettő tisztán darabolható a segment muxerrel).
_FORMATUMOK = {
    "mp3":  ("libmp3lame", "mp3", "mp3"),
    "opus": ("libopus",    "ogg", "ogg"),
}


def _norm_opts(options) -> dict:
    """A beállításokból (dict) egységes felvételi opciók: kódoló, kiterjesztés,
    bitráta, mintavétel, darab-hossz. Hibás/hiányzó érték → biztonságos alap."""
    o = options or {}
    fmt = str(o.get("format", "mp3")).lower()
    encoder, ext, segfmt = _FORMATUMOK.get(fmt, _FORMATUMOK["mp3"])
    try:
        br = int(o.get("bitrate_kbps", 192))
    except (TypeError, ValueError):
        br = 192
    br = min(max(br, 32), 320)
    try:
        chunk_min = max(0, int(o.get("chunk_minutes", 0)))
    except (TypeError, ValueError):
        chunk_min = 0
    try:
        sr = int(o.get("sample_rate", 0) or 0)
    except (TypeError, ValueError):
        sr = 0
    return {"encoder": encoder, "ext": ext, "segfmt": segfmt,
            "bitrate_kbps": br, "bitrate": f"{br}k",
            "chunk_seconds": chunk_min * 60, "sample_rate": sr}


def _rec_folder(base_dir: str, when: datetime) -> Path:
    # a vezető/záró szóköz Windowson WinError 123-at okoz (' C:\\...' érvénytelen)
    base = str(base_dir or "").strip() or str(Path.home() / "Downloads")
    folder = Path(base) / "Rádiófelvételek" / when.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _out_path(base_dir: str, station_name: str, when: datetime,
              ext: str = "mp3") -> Path:
    folder = _rec_folder(base_dir, when)
    fname = f"{_safe(station_name)} {when.strftime('%Y-%m-%d %H-%M-%S')}.{ext}"
    return folder / fname


class ActiveRecording:
    """Egyetlen, épp futó (vagy frissen befejezett) felvétel."""

    def __init__(self, station_name, url, base_dir, duration_s=None,
                 scheduled=False, on_done=None, options=None):
        self.station_name = station_name
        self.url = url
        self.duration_s = duration_s
        self.scheduled = scheduled
        self.on_done = on_done
        self.opts = _norm_opts(options)
        self.ext = self.opts["ext"]
        self.chunk_seconds = self.opts["chunk_seconds"]
        self.start_time = datetime.now()
        self._folder = _rec_folder(base_dir, self.start_time)
        self._stem = (f"{_safe(station_name)} "
                      f"{self.start_time.strftime('%Y-%m-%d %H-%M-%S')}")
        # darabolt módban self.path REPREZENTATÍV (a .parent a mappa); a valódi
        # kimenet a szegmens-minta (…- 000.mp3, - 001.mp3, …)
        self.path = self._folder / f"{self._stem}.{self.ext}"
        self._pattern = (str(self._folder / f"{self._stem} - %03d.{self.ext}")
                         if self.chunk_seconds > 0 else None)
        self.status = "felvétel"        # felvétel / kész / leállítva / hiba
        self.error = ""
        self._proc = None
        self._stop = threading.Event()
        self._err_tail = deque(maxlen=15)   # az ffmpeg utolsó hibasorai

    def start(self) -> bool:
        ff = _ffmpeg_exe()
        if not ff:
            self.status, self.error = "hiba", "az ffmpeg nem érhető el"
            return False
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        cmd = [ff, "-hide_banner", "-loglevel", "error"]
        # ÚJRACSATLAKOZÁS (Laci jelezte: „a legváratlanabb pillanatokban leáll"):
        # az élő adás rendszeresen megbicsaklik (pufferelés, hálózati rezdülés, a
        # szerver újraindítja) – e nélkül az ffmpeg KILÉP, és a felvétel véget ér.
        # FIGYELEM: ezek a HTTP-PROTOKOLL kapcsolói! Nem-HTTP forrásnál az ffmpeg
        # „Option reconnect not found"-dal AZONNAL elszállna, ezért csak http(s)
        # streamnél tesszük hozzá (élesben igazolva: HTTP-nél elfogadja).
        if str(self.url).lower().startswith(("http://", "https://")):
            cmd += ["-reconnect", "1", "-reconnect_streamed", "1",
                    "-reconnect_delay_max", "30"]
        # az I/O-időkorlát enyhítve (15→45 mp): a rövid akadást már az
        # újracsatlakozás kezeli, ne az időkorlát ölje meg a felvételt
        cmd += ["-rw_timeout", "45000000",
                "-i", self.url, "-vn",
                "-c:a", self.opts["encoder"], "-b:a", self.opts["bitrate"]]
        if self.opts["sample_rate"]:
            cmd += ["-ar", str(self.opts["sample_rate"])]
        if self.duration_s and self.duration_s > 0:
            cmd += ["-t", str(int(self.duration_s))]
        if self.chunk_seconds > 0:
            # DARABOLÁS: a segment muxer N másodpercenként új fájlt nyit, akár
            # 6 órán át – így a hosszú adás is kezelhető darabokban marad
            cmd += ["-f", "segment",
                    "-segment_time", str(self.chunk_seconds),
                    "-segment_format", self.opts["segfmt"],
                    "-reset_timestamps", "1", "-y", self._pattern]
        else:
            cmd += ["-y", str(self.path)]
        try:
            # a hibakimenetet NEM dobjuk el (eddig DEVNULL-ra ment = néma
            # megállás); elmentjük az utolsó sorait, hogy hibánál a VALÓDI okot
            # meg tudjuk mutatni
            self._proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE, creationflags=flags)
        except Exception as e:
            self.status, self.error = "hiba", str(e)
            return False
        threading.Thread(target=self._drain_err, daemon=True).start()
        threading.Thread(target=self._watch, daemon=True).start()
        return True

    def _drain_err(self):
        """Az ffmpeg hibasorainak folyamatos olvasása (a csövet ki KELL üríteni,
        különben megtelhet és megakasztaná a felvételt) – az utolsó sorokat
        megtartjuk a hibaüzenethez."""
        try:
            for raw in self._proc.stderr:
                line = raw.decode("utf-8", "replace").strip()
                if line:
                    self._err_tail.append(line)
        except Exception:
            pass

    def _watch(self):
        self._proc.wait()
        time.sleep(0.2)                 # a hibasor-olvasó fejezze be
        detail = " | ".join(self._err_tail)
        if self._stop.is_set():
            self.status = "leállítva"
        elif not self._has_audio():
            self.status = "hiba"
            self.error = ("az állomás nem elérhető, vagy a felvétel azonnal "
                          "megszakadt")
            if detail:
                self.error += f" – az ffmpeg üzenete: {detail}"
        elif self._premature():
            # EDDIG EZ CSENDBEN „kész" LETT (Laci: „leáll és nem ír semmiféle
            # hibát”): a megszakadt felvételt sikeresnek hittük, mert volt benne
            # adat. Mostantól JELEZZÜK – de kimondjuk, hogy a rész megmaradt.
            self.status = "hiba"
            mins = max(1, self.elapsed_s() // 60)
            self.error = (f"a felvétel VÁRATLANUL megszakadt (kb. {mins} perc "
                          "rögzült; a fájl megmaradt és lejátszható). Gyakori "
                          "ok: az adás vagy az internet megbicsaklott")
            if detail:
                self.error += f" – az ffmpeg üzenete: {detail}"
        else:
            self.status = "kész"
        if self.on_done:
            try:
                self.on_done(self)
            except Exception:
                pass

    def _output_files(self) -> list:
        """A ténylegesen létrejött kimeneti fájl(ok): egyben módban egy, darabolt
        módban a szegmensek (időrendben)."""
        if self.chunk_seconds > 0:
            try:
                return sorted(self._folder.glob(f"{self._stem} - *.{self.ext}"))
            except OSError:
                return []
        try:
            return [self.path] if self.path.is_file() else []
        except OSError:
            return []

    def hely_szoveg(self) -> str:
        """Hova került a felvétel – a felhasználónak bemondható/megjeleníthető."""
        if self.chunk_seconds > 0:
            return f"{self._folder} mappa ({len(self._output_files())} részben)"
        return str(self.path)

    @staticmethod
    def _probe_seconds(path) -> float:
        try:
            ff = _ffmpeg_exe()
            if not ff:
                return 0.0
            probe = str(Path(ff).with_name("ffprobe.exe"))
            if not Path(probe).is_file():
                return 0.0
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            r = subprocess.run(
                [probe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nk=1:nw=1", str(path)],
                capture_output=True, text=True, timeout=20, creationflags=flags)
            return float((r.stdout or "0").strip() or 0)
        except Exception:
            return 0.0

    def _recorded_seconds(self) -> float:
        """A ténylegesen RÖGZÍTETT hang összhossza másodpercben (ffprobe-bal, az
        összes kimeneti fájlon). Ez a MEGBÍZHATÓ mérték: az élő stream az elején
        puffer-löketet küldhet, ezért a fali óra rövidebb lehet, mint a rögzített
        hang – ne a fali órából döntsük el, teljes-e a felvétel."""
        return sum(self._probe_seconds(f) for f in self._output_files())

    def _premature(self) -> bool:
        """VÁRATLANUL ért véget? Időzítettnél: a kértnél érdemben rövidebb lett.
        A RÖGZÍTETT HANG HOSSZÁT nézzük (nem a fali órát!), mert az élő stream
        puffer-löketei miatt a felvétel hamarabb elkészülhet, mint amennyi valós
        idő eltelt. Kézinél (F9): minden nem-felhasználói leállás váratlan – az
        élő adás magától nem ér véget, tehát ha az ffmpeg kilépett, valami
        közbejött."""
        if self.duration_s and self.duration_s > 0:
            rogzitett = self._recorded_seconds()
            if rogzitett > 0:
                return rogzitett < self.duration_s * 0.9
            # ha az ffprobe nem mér, a FÁJLMÉRET(EK)BŐL becslünk – a bitrátához
            # igazítva (bájt/mp ≈ kbps × 1000 / 8); ez is jobb, mint a fali óra
            try:
                sz = sum(f.stat().st_size for f in self._output_files())
            except OSError:
                sz = 0
            bps = self.opts["bitrate_kbps"] * 1000 / 8
            return sz < self.duration_s * bps * 0.9
        return True

    def _has_audio(self) -> bool:
        try:
            return any(f.stat().st_size > 8192 for f in self._output_files())
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
                try:
                    p.wait(timeout=3)
                except Exception:
                    pass
            # a csövek bezárása, hogy a stderr-olvasó szál felszabaduljon és ne
            # maradjon nyitott leíró (MK4: erőforrás-életciklus)
            for s in (getattr(p, "stdin", None), getattr(p, "stderr", None),
                      getattr(p, "stdout", None)):
                if s is not None:
                    try:
                        s.close()
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
    count: int = 0                     # hátralévő alkalmak; 0 = kikapcsolásig (végtelen)

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
        # Hányszor: egyszeri (auto-törlés) / még N alkalom / kikapcsolásig
        if self.repeat == "once":
            hany = " (utána törlődik)"
        elif self.count > 0:
            hany = (f" – még {self.count} alkalom" if self.count > 1
                    else " – még 1 alkalom (utána törlődik)")
        else:
            hany = " – kikapcsolásig"
        állapot = "" if self.enabled else " [kikapcsolva]"
        return f"{self.station_name} – {rng} – {rep}{hany}{állapot}"


class RecordManager:
    """A felvételek központja: időzítő háttérszál, aktív felvételek és a
    mentett időzítések. A GUI-tól független, így a felvétel akkor is elindul,
    ha a rádió-ablak épp zárva van (csak a program fusson)."""

    FIELDS = {"id", "station_name", "url", "start_h", "start_m", "end_h",
              "end_m", "repeat", "weekdays", "date", "enabled",
              "last_run_date", "count"}

    def __init__(self, base_dir_getter, on_event=None, options_getter=None):
        self._base_dir_getter = base_dir_getter      # hívható -> str
        self._options_getter = options_getter        # hívható -> dict (felvételi opciók)
        self.on_event = on_event                     # hívható(szöveg, szint)
        self.last_error = ""                         # az utolsó indítási hiba
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
        return (d or "").strip() or str(Path.home() / "Downloads")

    def options(self) -> dict:
        """A felhasználó felvételi beállításai (formátum, bitráta, mintavétel,
        darabolás). Hiba/hiányzó getter esetén üres → mindenütt biztonságos alap."""
        try:
            return self._options_getter() or {} if self._options_getter else {}
        except Exception:
            return {}

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
                              on_done=self._on_done, options=self.options())
        if rec.start():
            self.last_error = ""
            with self._lock:
                self.active.append(rec)
            self._emit(f"Felvétel elindult: {station_name} → {rec.path.name}",
                       "start")
            return rec
        self.last_error = rec.error                   # a VALÓDI ok (pl. ffmpeg)
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
                if s.date < today:                 # lejárt, sosem futott → ne gyűljön
                    self.remove_schedule(s.id)
                    self._emit(f"Lejárt egyszeri időzítés törölve: "
                               f"{s.station_name} ({s.date})", "info")
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
        rec = ActiveRecording(s.station_name, s.url, self.base_dir(),
                              duration_s=duration, scheduled=True,
                              on_done=self._on_done, options=self.options())
        if rec.start():
            s.last_run_date = today
            # Hányszor-kezelés: egyszeri VAGY az utolsó hátralévő alkalom → törlés.
            # Korlátos (count>0) → visszaszámlálás; 0 (kikapcsolásig) → érintetlen.
            hatra = ""
            torol = False
            if s.repeat == "once":
                torol = True
            elif s.count > 0:
                s.count -= 1
                if s.count <= 0:
                    torol = True
                else:
                    hatra = f" Még {s.count} alkalom van hátra."
            self.save()
            with self._lock:
                self.active.append(rec)
            if torol:
                self.remove_schedule(s.id)
                hatra = " Ez volt az utolsó alkalom, az időzítőt törlöm."
            self._emit(f"Időzített felvétel elindult: {s.station_name} "
                       f"(kb. {max(1, duration // 60)} perc) → "
                       f"{rec.path.name}.{hatra}", "start")
        else:
            self._emit(f"Az időzített felvétel nem indult el: "
                       f"{s.station_name} – {rec.error}", "error")

    def shutdown(self):
        self._stop.set()
        self.stop_all_active()
        self.save()
