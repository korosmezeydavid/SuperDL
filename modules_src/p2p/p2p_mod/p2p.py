"""Gépről gépre fájlküldés (P2P) a magic-wormhole protokollal.

Két gomb + egy könnyen bemondható szó-kód (pl. „7-alma-traktor"). A küldő
megkapja a kódot és átadja; a fogadó beírja → a fájl gépről gépre megy (NAT
mögött is, relay-tartalékkal), VÉGPONTOK KÖZTI titkosítással. A projekt
ingyenes, nyílt szervereit használja – nekünk nincs szerver-üzemeltetés.

A tényleges átvitelt a `wormhole` parancssori eszköz végzi, amit alfolyamatként
hajtunk: fejlesztéskor a telepített wormhole.exe, a kész (frozen) programban
maga a SuperDL.exe `--wh` kapcsolóval (a magic-wormhole bele van csomagolva).
"""

import os
import time
import re
import subprocess
import sys
import threading
from pathlib import Path

_CODE_RE = re.compile(r"code is:\s*(\S+)", re.IGNORECASE)
_INTO_RE = re.compile(r"into:\s*'([^']+)'", re.IGNORECASE)
_PCT_RE = re.compile(r"(\d{1,3})\s*%")           # a wormhole/tqdm haladás-%-a
_NOWIN = 0x08000000 if os.name == "nt" else 0


def _human_size(n: int) -> str:
    """Bájtméret bemondható magyar alakban (a siker-visszaigazoláshoz)."""
    n = int(n or 0)
    for unit, hatar in (("gigabájt", 1024 ** 3), ("megabájt", 1024 ** 2),
                        ("kilobájt", 1024)):
        if n >= hatar:
            return f"{n / hatar:.1f} {unit}".replace(".", ",")
    return f"{n} bájt"


def _stop_proc(proc, timeout: float = 3.0) -> None:
    """Gyerekfolyamat BIZTOS leállítása: terminate→wait→kill→wait + csövek
    bezárása (MK4: a megszakított küldés/fogadás ne hagyjon árva folyamatot)."""
    if proc is None:
        return
    try:
        alive = proc.poll() is None
    except Exception:
        alive = False
    if alive:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=timeout)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                proc.wait(timeout=timeout)
            except Exception:
                pass
    for name in ("stdout", "stderr", "stdin"):
        s = getattr(proc, name, None)
        if s is not None:
            try:
                s.close()
            except Exception:
                pass


def _iter_segments(stream):
    """A wormhole kimenetének olvasása \\n ÉS \\r határon. FONTOS: a haladást a
    tqdm KOCSIVISSZA-val (\\r) frissíti ugyanabban a sorban, ezért a sima
    soronkénti (\\n) olvasás sosem látná a százalékot. Karakterenként olvasunk
    (a haladás-kimenet kis mennyiségű), így a % élőben megjelenik."""
    buf = ""
    while True:
        ch = stream.read(1)
        if not ch:
            break
        if ch in ("\r", "\n"):
            if buf:
                yield buf
            buf = ""
        else:
            buf += ch
    if buf:
        yield buf


def wormhole_command(args: list[str]) -> list[str]:
    """A wormhole indítóparancsa a környezethez igazítva."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--wh"] + args
    cand = Path(sys.executable).parent / "Scripts" / "wormhole.exe"
    if cand.is_file():
        return [str(cand)] + args
    import shutil
    wh = shutil.which("wormhole")
    if wh:
        return [wh] + args
    return [sys.executable, "-m", "wormhole"] + args


class SendSession:
    """Egy fájl küldése. A `on_code(code)` akkor hívódik, amikor megvan a
    bemondható kód; `on_done(ok, message)` a végén."""

    def __init__(self, path: str, on_code=None, on_done=None, on_progress=None):
        self.path = path
        self.on_code = on_code
        self.on_done = on_done
        self.on_progress = on_progress    # on_progress(percent:int) átvitel közben
        self._proc = None
        self._stop = False

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def cancel(self):
        self._stop = True
        _stop_proc(self._proc)     # terminate→wait→kill→wait + csövek

    def _run(self):
        # a haladás-elrejtést KIKAPCSOLTUK → a wormhole kiadja a haladás-%-ot
        # (a tqdm a kimeneten), amit a felület élőben mutat/bemond
        cmd = wormhole_command(["send", self.path])
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=_NOWIN)
        except OSError as e:
            self._emit_done(False, f"A küldés nem indult el: {e}")
            return
        code_sent = False
        last_pct = -1
        for seg in _iter_segments(self._proc.stdout):
            if self._stop:
                break
            m = _CODE_RE.search(seg)
            if m and not code_sent:
                code_sent = True
                if self.on_code:
                    self.on_code(m.group(1))
            pm = _PCT_RE.search(seg)
            if pm and self.on_progress:
                pct = max(0, min(100, int(pm.group(1))))
                if pct != last_pct:
                    last_pct = pct
                    self.on_progress(pct)
        rc = self._proc.wait()
        _stop_proc(self._proc)      # a csövek bezárása a lefutás végén (MK4)
        if self._stop:
            self._emit_done(False, "A küldést megszakították.")
        elif rc == 0:
            self._emit_done(True, "A fájl sikeresen átment a másik gépre.")
        else:
            self._emit_done(False, "A küldés nem fejeződött be (a másik gép "
                                   "nem csatlakozott, vagy megszakadt).")

    def _emit_done(self, ok, msg):
        if self.on_done:
            self.on_done(ok, msg)


class ReceiveSession:
    """Fájl fogadása a megadott kóddal a megadott mappába."""

    def __init__(self, code: str, out_dir: str, on_done=None, on_progress=None):
        self.code = code
        self.out_dir = out_dir
        self.on_done = on_done
        self.on_progress = on_progress
        self._proc = None
        self._stop = False
        self.filename = ""
        self._started_at = 0.0        # a fogadott fájl azonosításához

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def cancel(self):
        self._stop = True
        _stop_proc(self._proc)     # terminate→wait→kill→wait + csövek

    def _run(self):
        self._started_at = time.time()
        try:
            os.makedirs(self.out_dir, exist_ok=True)
        except OSError as e:
            self._emit_done(False, f"A célmappa nem hozható létre: {e}")
            return
        cmd = wormhole_command(["receive", "--accept-file", self.code.strip()])
        try:
            self._proc = subprocess.Popen(
                cmd, cwd=self.out_dir, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", creationflags=_NOWIN)
        except OSError as e:
            self._emit_done(False, f"A fogadás nem indult el: {e}")
            return
        last_pct = -1
        for seg in _iter_segments(self._proc.stdout):
            if self._stop:
                break
            m = _INTO_RE.search(seg)
            if m:
                self.filename = m.group(1)
            pm = _PCT_RE.search(seg)
            if pm and self.on_progress:
                pct = max(0, min(100, int(pm.group(1))))
                if pct != last_pct:
                    last_pct = pct
                    self.on_progress(pct)
        rc = self._proc.wait()
        _stop_proc(self._proc)      # a csövek bezárása a lefutás végén (MK4)
        if self._stop:
            self._emit_done(False, "A fogadást megszakították.")
        elif rc == 0:
            # NEM elég a nullás kilépési kód! Vírusirtó-karantén, lemezhiba,
            # megváltozott CLI-kimenet vagy részleges írás után is 0 jöhetne,
            # és HAMIS „megérkezett" hangzana el. Ellenőrizzük a TÉNYLEGES
            # fájlt: létezik-e és nem nulla méretű. [Herman Tibi P2P-P0-03]
            ok, where, size = self._verify_received()
            if ok:
                self._emit_done(True, f"A fájl megérkezett: {where} "
                                      f"({_human_size(size)}).")
            else:
                self._emit_done(
                    False, "A küldés lezárult, de a fogadott fájlt NEM találom "
                           f"a célmappában ({self.out_dir}). Ellenőrizd a "
                           "vírusirtót és a szabad helyet, majd próbáld újra.")
        else:
            self._emit_done(False, "A fogadás nem sikerült – ellenőrizd a "
                                   "kódot (a küldőtől pontosan), és hogy a "
                                   "küldő épp küld-e.")

    def _verify_received(self) -> tuple[bool, str, int]:
        """A fogadott fájl TÉNYLEGES ellenőrzése: létezik-e és nem üres-e.
        Ha a kimenetből ismerjük a nevet, azt nézzük; különben a célmappa
        legfrissebb, a fogadás kezdete UTÁN módosított fájlját."""
        try:
            if self.filename:
                p = os.path.join(self.out_dir, self.filename)
                if os.path.isfile(p) and os.path.getsize(p) > 0:
                    return True, p, os.path.getsize(p)
                return False, p, 0
            newest, newest_t = "", 0.0
            for n in os.listdir(self.out_dir):
                p = os.path.join(self.out_dir, n)
                try:
                    if not os.path.isfile(p) or os.path.getsize(p) <= 0:
                        continue
                    t = os.path.getmtime(p)
                except OSError:
                    continue
                if t >= self._started_at - 1 and t > newest_t:
                    newest, newest_t = p, t
            if newest:
                return True, newest, os.path.getsize(newest)
        except OSError:
            pass
        return False, self.out_dir, 0

    def _emit_done(self, ok, msg):
        if self.on_done:
            self.on_done(ok, msg)
