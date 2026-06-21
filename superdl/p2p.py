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
import re
import subprocess
import sys
import threading
from pathlib import Path

_CODE_RE = re.compile(r"code is:\s*(\S+)", re.IGNORECASE)
_INTO_RE = re.compile(r"into:\s*'([^']+)'", re.IGNORECASE)
_NOWIN = 0x08000000 if os.name == "nt" else 0


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

    def __init__(self, path: str, on_code=None, on_done=None):
        self.path = path
        self.on_code = on_code
        self.on_done = on_done
        self._proc = None
        self._stop = False

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def cancel(self):
        self._stop = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def _run(self):
        cmd = wormhole_command(["send", "--hide-progress", self.path])
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=_NOWIN)
        except OSError as e:
            self._emit_done(False, f"A küldés nem indult el: {e}")
            return
        code_sent = False
        for line in self._proc.stdout:
            if self._stop:
                break
            m = _CODE_RE.search(line)
            if m and not code_sent:
                code_sent = True
                if self.on_code:
                    self.on_code(m.group(1))
        rc = self._proc.wait()
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

    def __init__(self, code: str, out_dir: str, on_done=None):
        self.code = code
        self.out_dir = out_dir
        self.on_done = on_done
        self._proc = None
        self._stop = False
        self.filename = ""

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def cancel(self):
        self._stop = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def _run(self):
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
        for line in self._proc.stdout:
            if self._stop:
                break
            m = _INTO_RE.search(line)
            if m:
                self.filename = m.group(1)
        rc = self._proc.wait()
        if self._stop:
            self._emit_done(False, "A fogadást megszakították.")
        elif rc == 0:
            where = os.path.join(self.out_dir, self.filename) \
                if self.filename else self.out_dir
            self._emit_done(True, f"A fájl megérkezett: {where}")
        else:
            self._emit_done(False, "A fogadás nem sikerült – ellenőrizd a "
                                   "kódot (a küldőtől pontosan), és hogy a "
                                   "küldő épp küld-e.")

    def _emit_done(self, ok, msg):
        if self.on_done:
            self.on_done(ok, msg)
