"""Letöltési sor: több feladat párhuzamos futtatása, időzítéssel,
és a sor megőrzésével program-újraindítás után is."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from itertools import count

from . import store
from .media import MediaDownloader, is_media_url
from .segment import Progress, RateLimiter, SegmentDownloader
from .torrent import TorrentDownloader, is_torrent_url

_ids = count(1)


def parse_when(text: str) -> float | None:
    """Időpont szövegből unix időbélyeggé.

    Elfogad: '+90' (perc múlva), '+2h' (óra múlva), 'HH:MM' (ma/holnap az
    adott órakor), 'ÉÉÉÉ-HH-NN ÓÓ:PP' (konkrét időpont). Üres/0 esetén None.
    """
    import datetime as _dt

    text = (text or "").strip().lower()
    if not text or text == "0":
        return None
    now = _dt.datetime.now()
    if text.startswith("+"):
        body = text[1:].strip()
        mult = 60
        if body and body[-1] in "hmd":
            mult = {"m": 60, "h": 3600, "d": 86400}[body[-1]]
            body = body[:-1]
        return (now + _dt.timedelta(seconds=float(body) * mult)).timestamp()
    for fmt in ("%Y-%m-%d %H:%M", "%Y.%m.%d %H:%M", "%m-%d %H:%M"):
        try:
            dt = _dt.datetime.strptime(text, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=now.year)
            return dt.timestamp()
        except ValueError:
            pass
    try:  # csak óra:perc -> ma, vagy ha már elmúlt, holnap
        hh, mm = (int(x) for x in text.split(":"))
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if target <= now:
            target += _dt.timedelta(days=1)
        return target.timestamp()
    except (ValueError, TypeError):
        return None


@dataclass
class Job:
    url: str
    kind: str                      # "media", "file" vagy "torrent"
    progress: Progress = field(default_factory=Progress)
    id: int = field(default_factory=lambda: next(_ids))
    downloader: object = None
    out_dir: str | None = None     # ha None, a kezelő közös mappáját használja
    audio_only: bool | None = None
    start_at: float | None = None  # ütemezett indítás (unix idő), None = azonnal
    added_at: float = field(default_factory=time.time)
    submitted: bool = False        # már elindítottuk-e
    overwrite: bool = False         # torrent: meglévő fájl felülírása
    verify: bool = False            # torrent: meglévő fájl ellenőrzése + seed

    def to_record(self) -> dict:
        return {"url": self.url, "kind": self.kind, "out_dir": self.out_dir,
                "audio_only": self.audio_only, "start_at": self.start_at,
                "status": self.progress.status,
                "filename": self.progress.filename}


class DownloadManager:
    """Egyszerre legfeljebb `parallel` letöltés fut, mindegyik
    `connections` kapcsolattal."""

    # ezekben az állapotokban érdemes a sort menteni / újraindításkor folytatni
    RESUMABLE = ("várakozik", "ütemezve", "letöltés", "leállítva", "hiba")

    def __init__(self, out_dir: str, parallel: int = 3, connections: int = 8,
                 audio_only: bool = False, limit_bps: int = 0,
                 seed_ratio: float = 1.0, persist: bool = True):
        self.out_dir = out_dir
        self.connections = connections
        self.audio_only = audio_only
        self.seed_ratio = seed_ratio
        self.persist = persist
        # közös korlát: az összes letöltés együtt sem lépi túl
        self.limiter = RateLimiter(limit_bps)
        self.pool = ThreadPoolExecutor(max_workers=parallel)
        self.jobs: list[Job] = []
        self._lock = threading.Lock()
        self._closing = threading.Event()
        # az automatikus mentés csak akkor indulhat, ha már volt hozzáadás
        # vagy lefutott a restore() - különben induláskor felülírnánk a
        # korábban mentett, még folytatható sort egy üres listával
        self._allow_autosave = False
        # háttérszál: ütemezett indítás + a sor időnkénti mentése
        self._ticker = threading.Thread(target=self._tick_loop, daemon=True)
        self._ticker.start()

    # ---- hozzáadás ----------------------------------------------------

    def add(self, url: str, kind: str | None = None,
            out_dir: str | None = None, audio_only: bool | None = None,
            start_at: float | None = None, overwrite: bool = False,
            verify: bool = False) -> Job:
        if kind is None:
            if is_torrent_url(url):
                kind = "torrent"
            else:
                kind = "media" if is_media_url(url) else "file"
        job = Job(url=url, kind=kind, out_dir=out_dir, audio_only=audio_only,
                  start_at=start_at, overwrite=overwrite, verify=verify)
        job.progress.filename = url
        if start_at and start_at > time.time():
            job.progress.status = "ütemezve"
        with self._lock:
            self.jobs.append(job)
        self._allow_autosave = True
        if job.progress.status != "ütemezve":
            self._launch(job)
        self._save()
        return job

    def _launch(self, job: Job) -> None:
        job.submitted = True
        if job.kind == "torrent":
            # a torrentet az aria2 kezeli, nem foglal helyet a sorban
            # (seedelés közben sem tartana fel más letöltést)
            threading.Thread(target=self._run_job, args=(job,),
                             daemon=False).start()
        else:
            self.pool.submit(self._run_job, job)

    def _run_job(self, job: Job) -> None:
        if job.progress.status == "leállítva":
            return
        out_dir = job.out_dir or self.out_dir
        audio = self.audio_only if job.audio_only is None else job.audio_only
        try:
            if job.kind == "torrent":
                job.downloader = TorrentDownloader(
                    job.url, out_dir, progress=job.progress,
                    seed_ratio=self.seed_ratio, limit_bps=self.limiter.bps,
                    allow_overwrite=job.overwrite, check_integrity=job.verify)
            elif job.kind == "media":
                job.downloader = MediaDownloader(
                    job.url, out_dir, connections=self.connections,
                    audio_only=audio, progress=job.progress,
                    limit_bps=self.limiter.bps)
            else:
                job.downloader = SegmentDownloader(
                    job.url, out_dir, connections=self.connections,
                    progress=job.progress, limiter=self.limiter)
            job.downloader.run()
        except Exception:
            pass  # a hiba a job.progress.error mezőben már megvan
        finally:
            self._save()

    # ---- ütemezés + mentés háttérszál ---------------------------------

    def _tick_loop(self) -> None:
        last_save = time.time()
        while not self._closing.is_set():
            now = time.time()
            for job in list(self.jobs):
                if (job.progress.status == "ütemezve" and not job.submitted
                        and job.start_at and job.start_at <= now):
                    job.progress.status = "várakozik"
                    self._launch(job)
            if self._allow_autosave and now - last_save >= 3:
                last_save = now
                self._save()
            time.sleep(1)

    def _save(self) -> None:
        if not self.persist or not self._allow_autosave:
            return
        records = [j.to_record() for j in self.jobs
                   if j.progress.status in self.RESUMABLE
                   or j.kind == "torrent"]
        try:
            store.save_queue(records)
        except Exception:
            pass

    def restore(self) -> list[Job]:
        """A korábban mentett, befejezetlen letöltések folytatása
        program-indításkor. A szegmentált fájlok a .sdlstate alapján onnan
        folytatódnak, ahol abbamaradtak."""
        restored: list[Job] = []
        records = store.load_queue()      # előbb beolvassuk az egész sort
        self._allow_autosave = True       # innentől menthet a háttérszál
        for r in records:
            url = r.get("url")
            if not url:
                continue
            # a már leállított elemeket nem indítjuk újra magától: várakozóra
            job = self.add(
                url, kind=r.get("kind"), out_dir=r.get("out_dir"),
                audio_only=r.get("audio_only"),
                start_at=r.get("start_at"))
            if r.get("filename"):
                job.progress.filename = r["filename"]
            restored.append(job)
        return restored

    # ---- vezérlés -----------------------------------------------------

    def stop(self, job: Job) -> None:
        if job.downloader is not None:
            job.downloader.stop()
        elif job.progress.status in ("várakozik", "ütemezve"):
            job.progress.status = "leállítva"
        self._save()

    def stop_all(self) -> None:
        for job in self.jobs:
            self.stop(job)

    def remove(self, job: Job) -> None:
        """Eltávolítja a sorból (leállítja, ha fut)."""
        self.stop(job)
        with self._lock:
            if job in self.jobs:
                self.jobs.remove(job)
        self._save()

    def resolve_conflict(self, job: Job, mode: str) -> Job:
        """A 'fájl már létezik' ütközés feloldása ugyanazon az elemen.
        mode: 'overwrite' = felülírás, 'verify' = ellenőrzés + megosztás."""
        job.overwrite = (mode == "overwrite")
        job.verify = (mode == "verify")
        job.downloader = None
        job.submitted = False
        p = job.progress
        p.conflict = False
        p.error = ""
        p.status = "várakozik"
        p.downloaded = p.total = 0
        self._launch(job)
        self._save()
        return job

    def wait(self) -> None:
        self.pool.shutdown(wait=True)

    def close(self) -> None:
        self._closing.set()
        self._save()

    @property
    def active(self) -> bool:
        return any(j.progress.status in
                   ("várakozik", "ütemezve", "letöltés", "seedelés")
                   for j in self.jobs)
