"""Szegmentált, több szálú HTTP letöltő.

A fájlt darabokra osztja, és minden darabot külön szálon, HTTP Range
kéréssel tölt le ugyanabba az előre lefoglalt fájlba. Ha a szerver nem
támogatja a Range kéréseket, automatikusan egyszálú letöltésre vált.
Megszakadt letöltés a .sdlstate oldalfájl alapján folytatható.
"""

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

CHUNK_SIZE = 1024 * 256
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SuperDL/1.0"
MAX_RETRIES = 5


def parse_limit(text: str) -> int:
    """Sebességkorlát szövegből bájt/mp-be. Elfogadott alakok: '2M', '500K',
    '500 KB', '500 KB/s', '2 MB/s', '1,5 MB/s', '1.5m'. (Reguláris kifejezéssel,
    hogy a 'B' és a '/s' utótag, a szóköz és a tizedesvessző ne okozzon hibát.)"""
    if not text:
        return 0
    t = text.strip().lower().replace(",", ".")
    m = re.match(r"^\s*([0-9]*\.?[0-9]+)\s*([kmg])?", t)
    if not m:
        return 0
    mult = {"k": 1024, "m": 1024 ** 2, "g": 1024 ** 3}.get(m.group(2), 1)
    return int(float(m.group(1)) * mult)


class RateLimiter:
    """Vödör-algoritmusú sávszélesség-korlát, szálak közt megosztva."""

    def __init__(self, bps: int = 0):
        self.bps = bps
        self._lock = threading.Lock()
        self._allowance = float(bps)
        self._last = time.monotonic()

    def acquire(self, n: int) -> None:
        if self.bps <= 0:
            return
        while True:
            with self._lock:
                now = time.monotonic()
                # a vödör teteje legalább akkora legyen, mint a kért blokk (n),
                # különben egy a limitnél nagyobb blokk SOHA nem férne bele, és a
                # letöltés örökre megállna (pl. 64 KB/s limit + 256 KB-os blokk)
                cap = max(float(self.bps), float(n))
                self._allowance = min(
                    cap, self._allowance + (now - self._last) * self.bps)
                self._last = now
                if self._allowance >= n:
                    self._allowance -= n
                    return
                wait = (n - self._allowance) / self.bps
            time.sleep(min(wait, 0.5))


@dataclass
class Progress:
    total: int = 0                  # teljes méret bájtban (0 = ismeretlen)
    downloaded: int = 0
    speed: float = 0.0              # bájt/mp
    status: str = "várakozik"       # várakozik | letöltés | seedelés | kész | hiba | leállítva
    error: str = ""
    filename: str = ""
    connections: int = 1
    up_speed: float = 0.0           # feltöltés (torrentnél)
    uploaded: int = 0
    ratio: float = 0.0              # megosztási arány
    peers: int = 0
    conflict: bool = False          # torrent: a cél fájl már létezik
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, n: int) -> None:
        with self._lock:
            self.downloaded += n

    @property
    def percent(self) -> float:
        return self.downloaded / self.total * 100 if self.total else 0.0


_RESERVED_NAMES = ({"con", "prn", "aux", "nul"}
                   | {f"com{i}" for i in range(1, 10)}
                   | {f"lpt{i}" for i in range(1, 10)})


def safe_filename(name: str) -> str:
    """Windows-biztos fájlnév: tiltott írásjelek és vezérlőkarakterek cseréje,
    a fenntartott eszköznevek (CON, PRN, NUL, COM1…, LPT1…) elkerülése, a
    ponttal/szóközzel végződő és az üres név kezelése, és hosszkorlát."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.strip().rstrip(". ")          # nem végződhet ponttal/szóközzel
    if not name:
        return "letoltes.bin"
    if name.split(".")[0].lower() in _RESERVED_NAMES:
        name = "_" + name
    if len(name) > 200:                        # hosszkorlát a kiterjesztéssel
        root, dot, ext = name.rpartition(".")
        name = (root[:199 - len(ext)] + dot + ext) if dot and len(ext) < 20 \
            else name[:200]
    return name


def filename_from_response(url: str, resp: requests.Response) -> str:
    cd = resp.headers.get("content-disposition", "")
    m = re.search(r"filename\*=(?:UTF-8'')?([^;]+)", cd, re.I)
    if not m:
        m = re.search(r'filename="?([^";]+)"?', cd, re.I)
    if m:
        name = unquote(m.group(1).strip().strip('"'))
    else:
        name = unquote(os.path.basename(urlparse(url).path)) or "letoltes.bin"
    return safe_filename(name)


def unique_path(directory: Path, name: str) -> Path:
    """Szabad fájlnevet keres: név.kit, név (1).kit, név (2).kit ..."""
    path = directory / name
    stem, suffix = path.stem, path.suffix
    i = 1
    while path.exists():
        path = directory / f"{stem} ({i}){suffix}"
        i += 1
    return path


class SegmentDownloader:
    def __init__(self, url: str, out_dir: str, connections: int = 8,
                 progress: Progress | None = None,
                 limiter: RateLimiter | None = None):
        self.url = url
        self.out_dir = Path(out_dir)
        self.connections = max(1, connections)
        self.progress = progress or Progress()
        self.limiter = limiter or RateLimiter(0)
        self._stop = threading.Event()
        self._etag = ""              # a szerver tartalomazonosítói a folytatáshoz
        self._lastmod = ""
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def stop(self) -> None:
        self._stop.set()

    # ---- előkészítés -------------------------------------------------

    def _probe(self) -> tuple[int, bool, str, str, str, str]:
        """Visszaadja: (méret, range-támogatás, fájlnév, tartalomtípus, ETag,
        Last-Modified)."""
        resp = self.session.get(self.url, stream=True, timeout=30,
                                headers={"Range": "bytes=0-0"})
        resp.raise_for_status()
        name = filename_from_response(self.url, resp)
        ctype = (resp.headers.get("content-type", "") or "").split(";")[0].strip()
        etag = (resp.headers.get("etag", "") or "").strip()
        lastmod = (resp.headers.get("last-modified", "") or "").strip()
        if resp.status_code == 206:
            cr = resp.headers.get("content-range", "")
            m = re.search(r"/(\d+)", cr)
            size = int(m.group(1)) if m else 0
            resp.close()
            return size, True, name, ctype, etag, lastmod
        size = int(resp.headers.get("content-length", 0) or 0)
        resp.close()
        return size, False, name, ctype, etag, lastmod

    # ---- folytatás állapota ------------------------------------------

    def _state_path(self, target: Path) -> Path:
        return target.with_suffix(target.suffix + ".sdlstate")

    def _load_state(self, target: Path, size: int) -> list[list[int]] | None:
        sp = self._state_path(target)
        part = target.with_suffix(target.suffix + ".part")
        if not (sp.exists() and part.exists()):
            return None
        try:
            state = json.loads(sp.read_text())
            if state.get("url") == self.url and state.get("size") == size:
                # ha a szerver tartalomazonosítója megváltozott (a fájl tartalma
                # más lett, bár az URL és a méret azonos), NE folytassuk a régi
                # részekkel – az összekeverné a régi és új tartalmat
                if self._etag and state.get("etag") \
                        and state["etag"] != self._etag:
                    return None
                if self._lastmod and state.get("lastmod") \
                        and state["lastmod"] != self._lastmod:
                    return None
                return state["segments"]
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def _save_state(self, target: Path, size: int,
                    segments: list[list[int]]) -> None:
        self._state_path(target).write_text(json.dumps(
            {"url": self.url, "size": size, "segments": segments,
             "etag": self._etag, "lastmod": self._lastmod}))

    # ---- letöltés -----------------------------------------------------

    def run(self) -> Path:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        p = self.progress
        p.status = "letöltés"
        try:
            size, ranges_ok, name, ctype, etag, lastmod = self._probe()
        except requests.RequestException as e:
            p.status, p.error = "hiba", f"Nem érhető el: {e}"
            raise
        self._etag, self._lastmod = etag, lastmod   # a folytatás azonosítói
        # ha weboldal jön vissza fájl helyett, ne mentsünk HTML-t kacatként:
        # ez jellemzően fájlmegosztó tárhely nyitólapja (közvetett link)
        if ctype in ("text/html", "application/xhtml+xml"):
            p.status = "hiba"
            p.error = ("Ez a link egy weboldalra mutat, nem közvetlen fájlra "
                       "(valószínűleg fájlmegosztó tárhely). A letöltést a "
                       "böngészőben kell elindítani; sok tárhely várakozást, "
                       "belépést vagy ellenőrzést kér, ezért közvetlenül nem "
                       "tölthető.")
            raise RuntimeError(p.error)
        p.filename = name
        p.total = size

        target = unique_path(self.out_dir, name)
        # folytatható letöltésnél a már megkezdett fájlt használjuk
        resumable = self.out_dir / name
        if self._load_state(resumable, size) is not None:
            target = resumable
        part = target.with_suffix(target.suffix + ".part")

        speed_thread = threading.Thread(target=self._speed_meter, daemon=True)
        speed_thread.start()

        try:
            if ranges_ok and size > 1024 * 1024 and self.connections > 1:
                self._download_segmented(target, part, size)
            else:
                p.connections = 1
                self._download_single(part)
            if self._stop.is_set():
                p.status = "leállítva"
                return target
            # végső méret-ellenőrzés: ismert teljes méretnél a kész fájl pontosan
            # akkora legyen (az egyszálú útnál ez fogja el a csonka letöltést)
            if size > 0:
                actual = part.stat().st_size if part.exists() else 0
                if actual != size:
                    raise RuntimeError(
                        f"a letöltött fájl mérete nem teljes: {actual} / {size} "
                        "bájt – a letöltés nem fejeződött be rendesen")
            part.rename(target)
            self._state_path(target).unlink(missing_ok=True)
            p.status = "kész"
            return target
        except Exception as e:
            if p.status != "leállítva":
                p.status, p.error = "hiba", str(e)
            raise

    def _download_single(self, part: Path) -> None:
        existing = part.stat().st_size if part.exists() else 0
        headers = {}
        mode = "wb"
        if existing and self.progress.total:
            headers["Range"] = f"bytes={existing}-"
            mode = "ab"
            self.progress.add(existing)
        with self.session.get(self.url, stream=True, timeout=30,
                              headers=headers) as resp:
            resp.raise_for_status()
            if mode == "ab" and resp.status_code != 206:
                mode = "wb"
                self.progress.downloaded = 0
            with open(part, mode) as f:
                for chunk in resp.iter_content(CHUNK_SIZE):
                    if self._stop.is_set():
                        return
                    self.limiter.acquire(len(chunk))
                    f.write(chunk)
                    self.progress.add(len(chunk))

    def _download_segmented(self, target: Path, part: Path, size: int) -> None:
        segments = self._load_state(target, size)
        if segments is None:
            n = min(self.connections, max(1, size // (512 * 1024)))
            seg_size = size // n
            segments = [[i * seg_size,
                         (i + 1) * seg_size - 1 if i < n - 1 else size - 1]
                        for i in range(n)]
            with open(part, "wb") as f:
                f.truncate(size)
        else:
            done = size - sum(e - s + 1 for s, e in segments if s <= e)
            self.progress.add(done)

        live = [s for s in segments if s[0] <= s[1]]
        self.progress.connections = len(live)

        errors: list[str] = []
        save_lock = threading.Lock()
        last_save = [0.0]

        def save_throttled() -> None:
            now = time.monotonic()
            with save_lock:
                if now - last_save[0] >= 1.0:
                    last_save[0] = now
                    self._save_state(target, size, segments)

        def worker(seg: list[int]) -> None:
            for attempt in range(MAX_RETRIES):
                if self._stop.is_set() or seg[0] > seg[1]:
                    return
                try:
                    headers = {"Range": f"bytes={seg[0]}-{seg[1]}"}
                    with self.session.get(self.url, stream=True, timeout=30,
                                          headers=headers) as resp:
                        resp.raise_for_status()
                        # ha a szerver NEM 206-tal felel, figyelmen kívül hagyta
                        # a Range-et és a teljes fájlt küldené minden szálban →
                        # ez összekeverné a kimenetet, ezért hibának vesszük
                        if resp.status_code != 206:
                            errors.append("a szerver nem támogatta a Range "
                                          "kérést (nem 206-os válasz)")
                            return
                        with open(part, "r+b") as f:
                            f.seek(seg[0])
                            for chunk in resp.iter_content(CHUNK_SIZE):
                                if self._stop.is_set():
                                    return
                                self.limiter.acquire(len(chunk))
                                f.write(chunk)
                                seg[0] += len(chunk)
                                self.progress.add(len(chunk))
                                save_throttled()
                    return
                except requests.RequestException as e:
                    if attempt == MAX_RETRIES - 1:
                        errors.append(str(e))
                    else:
                        time.sleep(2 ** attempt)

        threads = [threading.Thread(target=worker, args=(s,), daemon=True)
                   for s in live]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if self._stop.is_set():
            with save_lock:
                self._save_state(target, size, segments)
            return
        if errors:
            raise RuntimeError("; ".join(errors[:3]))
        # MINDEN szegmensnek teljesen le kell töltődnie (seg[0] túljutott a
        # végén). Ha egy stream kivétel nélkül, idő előtt zárult, a hiányzó rész
        # nulla maradna az előre lefoglalt fájlban – ezt itt elkapjuk, hogy SOHA
        # ne nevezzünk át sérült fájlt késznek.
        incomplete = sum(1 for s in segments if s[0] <= s[1])
        if incomplete:
            raise RuntimeError(f"hiányos letöltés: {incomplete} szegmens nem "
                               "töltődött le teljesen")

    def _speed_meter(self) -> None:
        last_bytes, last_time = self.progress.downloaded, time.monotonic()
        while self.progress.status == "letöltés":
            time.sleep(0.5)
            now = time.monotonic()
            cur = self.progress.downloaded
            self.progress.speed = (cur - last_bytes) / max(now - last_time, 1e-6)
            last_bytes, last_time = cur, now
