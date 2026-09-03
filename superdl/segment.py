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

from . import lemezhely
from . import retrypolicy

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
    # MK3: figyelmeztetés, ami NEM hiba – a letöltés fut tovább, csak szólunk
    # (ma: fogyó lemezhely). Külön mező, mert az `error` megjelenése a
    # felületen hibát jelent, és egy figyelmeztetést hibaként mutatni ugyanaz
    # a kár, mint a hálózati várakozást hibának mondani (MK2).
    figyelmeztetes: str = ""
    # MK8: hányszor kellett MENET KÖZBEN újrapróbálni (szegmens/darab szinten).
    # Eddig ez teljesen néma volt: a felhasználó annyit érzékelt, hogy „lassú".
    # Vakon a lassú és az akadozó között nincs különbség – pedig az egyik
    # normális, a másik nem.
    belso_probak: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, n: int) -> None:
        with self._lock:
            self.downloaded += n

    def nullaz(self) -> None:
        """A számláló nullázása ZÁR ALATT (MK3).

        A `downloaded = 0` közvetlen írása versenyhelyzet: a sebességmérő szál
        ugyanezt olvassa, egy `add()` pedig épp hozzáadhat. Így a nullázás
        után a számláló nagyobb lehetett a valóságnál, és a százalék meg a
        hátralévő idő is hazudott – vakon pont az a két adat, amiből a
        felhasználó tájékozódik."""
        with self._lock:
            self.downloaded = 0

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


_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def vart_ujjlenyomat(url: str, fejlecek=None) -> str:
    """A forrás által ígért SHA-256, kisbetűs hexában – vagy üres szöveg.

    Két helyről fogadjuk el, mert csak ez a kettő fordul elő a gyakorlatban:

    1. **Az URL töredéke**: `…/fajl.zip#sha256=<hex>`. Ez a tükörszervereknél
       és a letöltő-oldalakon bevett szokás, és a felhasználó is be tudja
       illeszteni kézzel, ha az oldalon látja az ujjlenyomatot.
    2. **`Digest` / `Repr-Digest` válaszfejléc** (RFC 3230 és RFC 9530):
       `sha-256=<base64>`, az újabb alak kettősponttal keretezve.

    Amit NEM fogadunk el: MD5 és SHA-1. Egy törött ellenőrzés rosszabb a
    semminél, mert biztonságérzetet ad – a felhasználó azt hiszi, ellenőriztük.
    """
    import base64
    for resz in (url or "").split("#")[1:]:
        for darab in re.split(r"[&;]", resz):
            m = re.match(r"\s*sha-?256\s*[=:]\s*([0-9a-fA-F]{64})\s*$", darab)
            if m:
                return m.group(1).lower()
    for kulcs in ("digest", "repr-digest", "content-digest"):
        ertek = ((fejlecek or {}).get(kulcs) or "").strip()
        if not ertek:
            continue
        for darab in ertek.split(","):
            m = re.match(r"\s*sha-?256\s*=\s*:?([^:,\s]+):?\s*$", darab, re.I)
            if not m:
                continue
            nyers = m.group(1)
            if _HEX64.match(nyers.lower()):
                return nyers.lower()
            try:
                b = base64.b64decode(nyers + "=" * (-len(nyers) % 4))
            except (ValueError, TypeError):
                continue
            if len(b) == 32:
                return b.hex()
    return ""


def fajl_sha256(ut: Path, blokk: int = 1024 * 1024) -> str:
    """Egy fájl SHA-256 ujjlenyomata, blokkonként olvasva (egy 4 gigabájtos
    fájl nem fér a memóriába)."""
    import hashlib
    h = hashlib.sha256()
    with open(ut, "rb") as f:
        while True:
            adat = f.read(blokk)
            if not adat:
                break
            h.update(adat)
    return h.hexdigest()


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
        self._digest_fejlec: dict = {}   # MK3: ígért ujjlenyomat, ha van
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
        # MK3: ha a szerver ad ujjlenyomatot, eltesszük a végi ellenőrzéshez
        self._digest_fejlec = {
            k: (resp.headers.get(k, "") or "")
            for k in ("digest", "repr-digest", "content-digest")}
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

    def _find_resumable_target(self, name: str, size: int,
                               mod: str = "szegmentalt") -> Path | None:
        """Megkeresi a már megkezdett letöltés célfájlját (.sdlstate + .part).

        A `mod` MK3 óta kötelezően illeszkedik: egy egyszálú állapotfájlt a
        szegmentált ág nem vehet fel (a szegmenslistája üres, amiből az
        „minden kész" következne), és fordítva sem."""
        stem = Path(name).stem
        suffix = Path(name).suffix
        candidates = [self.out_dir / name]
        if stem and suffix:
            for p in sorted(self.out_dir.glob(f"{stem}*{suffix}")):
                if p.is_file() and p not in candidates:
                    candidates.append(p)
            # MK3: a KÉSZ fájlok végigjárása nem elég. Ha a célnevet egy
            # befejezett fájl foglalja, a folytatandó fájl `név (1).kit`, ami
            # MAGA NEM LÉTEZIK – csak a `.part`-ja és az állapotfájlja. Így az
            # árva félkész letöltés soha nem került elő. Az állapotfájl a
            # megbízható nyom, tehát abból is származtatunk jelöltet.
            for sp in sorted(self.out_dir.glob(f"{stem}*{suffix}.sdlstate")):
                cel = sp.with_suffix("")          # …kit.sdlstate → …kit
                if cel not in candidates:
                    candidates.append(cel)
        for cand in candidates:
            if self._load_state(cand, size, mod) is not None:
                return cand
        return None

    def _load_state(self, target: Path, size: int,
                    mod: str = "szegmentalt") -> list[list[int]] | None:
        sp = self._state_path(target)
        part = target.with_suffix(target.suffix + ".part")
        if not (sp.exists() and part.exists()):
            return None
        try:
            state = json.loads(sp.read_text())
            # a régi, mód nélküli állapotfájlok szegmentáltak voltak
            if state.get("mode", "szegmentalt") != mod:
                return None
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
                    segments: list[list[int]],
                    mod: str = "szegmentalt") -> None:
        self._state_path(target).write_text(json.dumps(
            {"url": self.url, "size": size, "segments": segments,
             "etag": self._etag, "lastmod": self._lastmod, "mode": mod}))

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

        # a módot ELŐRE el kell dönteni, mert a folytatás állapotfájlja
        # módfüggő (MK3): a két ág állapota nem cserélhető fel
        szegmentalt = bool(ranges_ok and size > 1024 * 1024
                           and self.connections > 1)
        mod = "szegmentalt" if szegmentalt else "egyszalu"

        target = unique_path(self.out_dir, name)
        # folytatható letöltésnél a már megkezdett fájlt használjuk (akár
        # egyedi „(1)" névvel is, ha az eredeti már foglalt volt)
        resumable = self._find_resumable_target(name, size, mod)
        if resumable is not None:
            target = resumable
        part = target.with_suffix(target.suffix + ".part")

        # MK3: SZABAD HELY, még az első bájt letöltése előtt.
        # Csak azt kérjük számon, ami MÉG hiányzik: folytatásnál a meglévő
        # .part már a lemezen van, azt kétszer beszámítani hamis riasztás
        # volna. A szegmentált ág előre lefoglalja a teljes méretet
        # (`truncate`), ezért ott az egész fájl kell – kivéve, ha a foglalás
        # már megtörtént, vagyis van .part.
        if size > 0:
            meglevo = part.stat().st_size if part.exists() else 0
            kell = max(0, size - meglevo)
            fer, sz, hianyzik = lemezhely.eleg_hely(self.out_dir, kell)
            if not fer:
                p.status = "hiba"
                p.error = lemezhely.hiba_szoveg(name, kell, sz, hianyzik)
                raise RuntimeError(p.error)

        speed_thread = threading.Thread(target=self._speed_meter, daemon=True)
        speed_thread.start()

        try:
            if szegmentalt:
                self._download_segmented(target, part, size)
            else:
                p.connections = 1
                self._download_single(target, part, size)
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
            # MK3: ELLENŐRZŐ ÖSSZEG, ha a forrás ígért egyet.
            # Csak akkor számolunk, ha van mihez hasonlítani: egy 4 gigabájtos
            # fájl végigolvasása semmiért perceket venne el.
            # Eltérésnél NEM nevezzük át: a sérült fájl .part marad, mert
            # egy késznek mutatott, romlott fájl a legrosszabb kimenet – a
            # felhasználó évekig hordozhatja, mielőtt kiderül.
            vart = vart_ujjlenyomat(self.url, self._digest_fejlec)
            if vart:
                kapott = fajl_sha256(part)
                if kapott != vart:
                    raise RuntimeError(
                        "A letöltött fájl ellenőrző összege nem egyezik azzal, "
                        "amit a forrás ígért, tehát sérült vagy megváltozott. "
                        "A fájlt nem tettem a helyére; a félkész változat "
                        "megmaradt, a letöltést újra lehet indítani.")
            part.rename(target)
            self._state_path(target).unlink(missing_ok=True)
            p.status = "kész"
            return target
        except Exception as e:
            if p.status != "leállítva":
                p.status, p.error = "hiba", str(e)
            raise

    def _download_single(self, target: Path, part: Path, size: int) -> None:
        existing = part.stat().st_size if part.exists() else 0
        headers = {}
        mode = "wb"
        # MK3: a folytatás feltételéből kikerült a `self.progress.total`.
        # Ismeretlen méretnél (chunked válasz, content-length nélkül) a régi
        # feltétel hamis volt, és a meglévő .part-ot NÉMÁN felülírta: nem
        # csak elölről kezdte, hanem eldobta a már letöltött adatot is.
        # Kérni akkor is szabad: ha a szerver nem tudja teljesíteni, 200-zal
        # felel, és lent úgyis visszaesünk a nulláról írásra.
        if existing:
            headers["Range"] = f"bytes={existing}-"
            mode = "ab"
            self.progress.add(existing)
        # MK3: az egyszálú ág is hagyjon nyomot maga után. Enélkül – ha a
        # kész fájl már foglalta a célnevet – az `unique_path` új nevet ad, a
        # régi .part pedig árván marad, mert a `_find_resumable_target`
        # állapotfájl NÉLKÜL nem talál rá. A szegmenslista üres: az egyszálú
        # folytatást a .part MÉRETE hordozza, nem a lista.
        self._save_state(target, size, [], "egyszalu")
        with self.session.get(self.url, stream=True, timeout=30,
                              headers=headers) as resp:
            resp.raise_for_status()
            if mode == "ab" and resp.status_code != 206:
                mode = "wb"
                self.progress.nullaz()
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
                        # MK8: a közös BELSŐ politika (másodperces lépték).
                        # Nem a perces job-szintű: ott egy szegmens akad meg
                        # nyolcból, és percet várni rá a letöltést a
                        # töredékére lassítaná, míg a többi szál dolgozik.
                        self.progress.belso_probak += 1
                        time.sleep(retrypolicy.belso_szunet(attempt))

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
        korok = 0
        while self.progress.status == "letöltés":
            time.sleep(0.5)
            now = time.monotonic()
            cur = self.progress.downloaded
            self.progress.speed = (cur - last_bytes) / max(now - last_time, 1e-6)
            last_bytes, last_time = cur, now
            # MK3: futás közbeni hely-figyelés. Tízmásodpercenként elég – a
            # lemez nem telik meg fél másodperc alatt, a `disk_usage` viszont
            # rendszerhívás, és kár percenként ezret indítani belőle.
            # A figyelmeztetés EGYSZER szól (mint az offline jelzés az MK2-ben):
            # a másodpercenként ismételt riasztás vakon használhatatlanná
            # tenné a felolvasót.
            korok += 1
            if korok % 20 == 0 and not self.progress.figyelmeztetes:
                keves, sz = lemezhely.alacsony(self.out_dir)
                if keves:
                    self.progress.figyelmeztetes = lemezhely.alacsony_szoveg(sz)
