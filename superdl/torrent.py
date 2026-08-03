"""Torrent le- és feltöltés a beépített aria2 motorral.

A SuperDL a háttérben elindít egy aria2c folyamatot (JSON-RPC vezérléssel),
és azon keresztül kezeli a torrenteket: magnet-linkeket és .torrent
fájlokat is. A letöltés után a megadott megosztási arányig seedel.

Csak legális tartalomhoz használd - seedeléskor te magad is terjesztő vagy!
"""

import base64
import json
import random
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import requests

from .segment import Progress


def is_torrent_url(url: str) -> bool:
    u = url.strip().lower()
    if u.startswith("magnet:"):
        return True
    if u.endswith(".torrent"):
        return True
    return Path(url).suffix.lower() == ".torrent" and Path(url).is_file()


def find_aria2c() -> str | None:
    candidates = [Path.home() / ".superdl" / "bin" / "aria2c.exe"]  # frissített
    if getattr(sys, "_MEIPASS", None):           # PyInstaller-csomagban
        candidates.append(Path(sys._MEIPASS) / "aria2c.exe")
    here = Path(__file__).resolve().parent.parent
    candidates += [here / "bin" / "aria2c.exe", here / "aria2c.exe"]
    for c in candidates:
        if c.is_file():
            return str(c)
    import shutil
    return shutil.which("aria2c")


_EXCLUDED_CACHE: "list[tuple[int, int]] | None" = None


def _excluded_port_ranges() -> "list[tuple[int, int]]":
    """A Windows által lefoglalt (kizárt) TCP-porttartományok.

    Ezekre a portokra a helyi kötés/kapcsolódás WSAEACCES (WinError 10013)
    hibát ad. A Hyper-V, a WSL, a Docker és a WinNAT rebootonként foglal le
    blokkokat épp az alacsony dinamikus tartományból, ezért futásidőben
    kérdezzük le (gyorsítótárazva). Nem Windows -> üres lista."""
    global _EXCLUDED_CACHE
    if _EXCLUDED_CACHE is not None:
        return _EXCLUDED_CACHE
    ranges: list[tuple[int, int]] = []
    if sys.platform == "win32":
        try:
            out = subprocess.run(
                ["netsh", "interface", "ipv4", "show",
                 "excludedportrange", "protocol=tcp"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW).stdout
            for line in out.splitlines():
                parts = line.split()
                if (len(parts) == 2 and parts[0].isdigit()
                        and parts[1].isdigit()):
                    a, b = int(parts[0]), int(parts[1])
                    if a <= b:
                        ranges.append((a, b))
        except Exception:
            ranges = []
    _EXCLUDED_CACHE = ranges
    return ranges


def _pick_safe_port() -> int:
    """Szabad helyi TCP-port, ami EGYIK Windows-kizárt sávba sem esik.

    Inkább a magas (20000-60000) tartományból választ, ahol ritkább az
    ütközés és a lefoglalás; ha 60 próbából sem talál, az OS-adta portra
    esik vissza (a kizárt sávokat az OS is kihagyja a bind(0)-nál)."""
    ranges = _excluded_port_ranges()
    for _ in range(60):
        cand = random.randint(20000, 60000)
        if any(a <= cand <= b for a, b in ranges):
            continue
        try:
            with socket.socket() as s:
                s.bind(("127.0.0.1", cand))
            return cand
        except OSError:
            continue
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _engine_error(detail: str = "") -> str:
    """Akadálymentes, cselekvésre váltható üzenet, ha az aria2c a
    port-letiltás (WinError 10013) miatt egyáltalán nem tud elindulni."""
    return (
        "A torrentmotor (aria2c) nem tudott elindulni, mert a Windows épp "
        "minden kipróbált helyi hálózati portot letiltott a vezérléshez "
        "(hozzáférés megtagadva, WinError 10013). Ezt szinte mindig a "
        "Hyper-V, a WSL vagy a Docker, illetve egy vírusirtó vagy tűzfal "
        "okozza, és gépújraindítás után változik. Mit tehetsz, sorrendben: "
        "1. Indítsd újra a gépet, és próbáld újra a torrentet. "
        "2. Vedd fel a SuperDL-t és az aria2c.exe-t a vírusirtó vagy a tűzfal "
        "kivételei közé. "
        "3. Ha makacs a hiba, a Windows lefoglalt porttartományai az okozók; "
        "ezeket az újraindítás oldja fel a leggyorsabban."
    )


class Aria2Client:
    """Egyetlen közös aria2c folyamat az összes torrenthez."""

    _instance: "Aria2Client | None" = None
    _ilock = threading.Lock()

    @classmethod
    def get(cls) -> "Aria2Client":
        with cls._ilock:
            if cls._instance is None or not cls._instance.alive():
                cls._instance = cls()
        return cls._instance

    def __init__(self):
        exe = find_aria2c()
        if not exe:
            raise RuntimeError(
                "Az aria2c.exe nem található - torrentekhez szükséges.")
        self.secret = secrets.token_hex(16)
        self._rpc_lock = threading.Lock()
        self._errf = None
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        # Több portot is kipróbálunk: ha a Windows egy portot letiltott
        # (WinError 10013), az aria2c nem tud rá ülni és kilép -> jön a
        # következő, biztonságos (nem kizárt) port. Így a hiba önjavul.
        last_detail = ""
        for _ in range(8):
            self.port = _pick_safe_port()
            self._errf = tempfile.TemporaryFile()
            self.proc = subprocess.Popen(
                [exe, "--enable-rpc", f"--rpc-listen-port={self.port}",
                 f"--rpc-secret={self.secret}", "--rpc-listen-all=false",
                 "--quiet", "--bt-detach-seed-only=true",
                 "--summary-interval=0"],
                creationflags=flags,
                stdout=subprocess.DEVNULL, stderr=self._errf)
            if self._wait_ready():
                return
            last_detail = self._drain_and_kill() or last_detail
        # Egyik port sem jött fel -> érthető, felolvasható hiba.
        raise RuntimeError(_engine_error(last_detail))

    def _wait_ready(self, tries: int = 40) -> bool:
        """Igaz, ha az aria2c elindult ÉS felel az RPC-n. Ha a folyamat
        közben meghal (pl. a port letiltva, WinError 10013), azonnal False -
        nem várunk feleslegesen, jöhet a következő port."""
        for _ in range(tries):
            if self.proc.poll() is not None:      # az aria2c kilépett
                return False
            try:
                self.call("aria2.getVersion")
                return True
            except requests.RequestException:
                time.sleep(0.1)
        return False

    def _drain_and_kill(self) -> str:
        """Leállítja a (feltehetően hibás) aria2c-t, és visszaadja a
        stderr-jét diagnosztikához (temp fájlból, így nincs cső-holtpont)."""
        try:
            self.proc.kill()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=3)
        except Exception:
            pass
        txt = ""
        try:
            if self._errf is not None:
                self._errf.seek(0)
                txt = self._errf.read().decode("utf-8", "replace").strip()
                self._errf.close()
                self._errf = None
        except Exception:
            pass
        return txt

    def alive(self) -> bool:
        return self.proc.poll() is None

    def call(self, method: str, *params):
        payload = {"jsonrpc": "2.0", "id": "sdl", "method": method,
                   "params": [f"token:{self.secret}", *params]}
        with self._rpc_lock:
            resp = requests.post(f"http://127.0.0.1:{self.port}/jsonrpc",
                                 data=json.dumps(payload), timeout=15)
        data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", "aria2 hiba"))
        return data["result"]

    def shutdown(self):
        # előbb sima RPC-leállítás, majd BEVÁRJUK a kilépést; ha nem hal meg
        # időben, kill+wait (MK4: ne maradjon árva aria2c-folyamat/leíró)
        try:
            self.call("aria2.shutdown")
        except Exception:
            pass
        try:
            self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
            try:
                self.proc.wait(timeout=3)
            except Exception:
                pass
        try:
            if getattr(self, "_errf", None) is not None:
                self._errf.close()
                self._errf = None
        except Exception:
            pass


def shutdown_aria2() -> None:
    """A közös aria2c folyamat leállítása (kilépéskor hívandó)."""
    with Aria2Client._ilock:
        inst = Aria2Client._instance
        Aria2Client._instance = None
    if inst is not None and inst.alive():
        inst.shutdown()


def _is_exists_conflict(msg: str) -> bool:
    """Igaz, ha a hiba a 'cél fájl már létezik, de nincs vezérlőfájl' eset."""
    m = (msg or "").lower()
    return "control file" in m and "exist" in m


class TorrentDownloader:
    def __init__(self, url: str, out_dir: str, progress: Progress | None = None,
                 seed_ratio: float = 1.0, limit_bps: int = 0,
                 allow_overwrite: bool = False, check_integrity: bool = False):
        self.url = url
        self.out_dir = str(Path(out_dir).resolve())
        self.progress = progress or Progress()
        self.seed_ratio = max(0.0, seed_ratio)
        self.limit_bps = limit_bps
        self.allow_overwrite = allow_overwrite  # meglévő fájl felülírása
        self.check_integrity = check_integrity  # meglévő fájl ellenőrzése+seed
        self._stop = threading.Event()
        self.gid: str | None = None
        self.client: Aria2Client | None = None

    def stop(self) -> None:
        self._stop.set()

    def _add(self) -> str:
        opts = {"dir": self.out_dir,
                "seed-ratio": str(self.seed_ratio),
                "bt-max-peers": "120"}
        if self.seed_ratio == 0:
            opts["seed-time"] = "0"
        if self.limit_bps:
            opts["max-download-limit"] = str(self.limit_bps)
        if self.allow_overwrite:
            opts["allow-overwrite"] = "true"
        if self.check_integrity:
            # a meglévő fájlt ellenőrzi a torrent hash-ei alapján: a jó
            # részeket megtartja, a hiányzókat letölti, majd seedel
            opts["check-integrity"] = "true"
            # a kész adatnál a .aria2 vezérlőfájl már nincs meg; e nélkül az
            # aria2 „a fájl már létezik"-et dobna a check-integrity ELŐTT. Az
            # allow-overwrite engedi továbblépni: a check-integrity előbb
            # validál, és CSAK a sérült/hiányzó darabokat tölti újra (a kész
            # torrent így kérdés nélkül seedel tovább, nem indul elölről).
            opts["allow-overwrite"] = "true"
        path = Path(self.url)
        if not self.url.lower().startswith("magnet:") and path.is_file():
            blob = base64.b64encode(path.read_bytes()).decode()
            return self.client.call("aria2.addTorrent", blob, [], opts)
        return self.client.call("aria2.addUri", [self.url], opts)

    KEYS = ["status", "totalLength", "completedLength", "uploadLength",
            "downloadSpeed", "uploadSpeed", "connections", "numSeeders",
            "errorMessage", "followedBy", "bittorrent", "files"]

    def run(self) -> None:
        p = self.progress
        try:
            self.client = Aria2Client.get()
            self.gid = self._add()
        except Exception as e:
            p.status, p.error = "hiba", str(e)
            raise
        p.status = "letöltés"

        while True:
            if self._stop.is_set():
                try:
                    self.client.call("aria2.remove", self.gid)
                except Exception:
                    pass
                p.status = "leállítva"
                return
            try:
                st = self.client.call("aria2.tellStatus", self.gid, self.KEYS)
            except Exception as e:
                p.status, p.error = "hiba", str(e)
                raise

            # magnetnél az első gid csak a metaadatot tölti; utána új gid jön
            followed = st.get("followedBy")
            if followed and st.get("status") == "complete":
                self.gid = followed[0]
                continue

            total = int(st.get("totalLength", 0))
            done = int(st.get("completedLength", 0))
            up = int(st.get("uploadLength", 0))
            p.total = total
            with p._lock:
                p.downloaded = done
            p.uploaded = up
            p.speed = float(st.get("downloadSpeed", 0))
            p.up_speed = float(st.get("uploadSpeed", 0))
            p.connections = int(st.get("connections", 0))
            p.peers = int(st.get("numSeeders", 0))
            p.ratio = up / done if done else 0.0
            bt = st.get("bittorrent") or {}
            name = (bt.get("info") or {}).get("name", "")
            if not name:
                files = st.get("files") or []
                if files:
                    name = Path(files[0].get("path", "") or
                                self.url).name or self.url
            p.filename = name or p.filename or self.url

            status = st.get("status")
            if status == "complete":
                p.status = "kész"
                return
            if status == "removed":
                p.status = "leállítva"
                return
            if status == "error":
                p.status = "hiba"
                raw = st.get("errorMessage", "ismeretlen aria2 hiba")
                if _is_exists_conflict(raw):
                    p.conflict = True
                    p.error = ("A cél fájl már létezik ebben a mappában. "
                               "Válaszd: kihagyom, felülírom, vagy "
                               "ellenőrzöm és megosztom.")
                else:
                    p.error = raw
                raise RuntimeError(p.error)
            if status == "active":
                p.status = "seedelés" if total and done >= total else "letöltés"
            time.sleep(1)
