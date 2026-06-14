"""Élő felolvasó motor: a könyv szövegét a programban olvastatja fel, fájlba
konvertálás NÉLKÜL.

A szöveget mondatokra/bekezdésekre bontja, a választott TTS-motorral (SAPI
vagy Edge) darabonként szintetizálja, és az audioengine streaming-lejátszóval
megszólaltatja. A KÖVETKEZŐ mondatot előre szintetizálja, amíg az aktuális
szól – így folyamatos a felolvasás. Követi a pozíciót (karakterben), ezért a
könyvjelző pontos: bármikor onnan folytatható.
"""

import shutil
import threading
import time
from bisect import bisect_right
from pathlib import Path

from . import tts
from .audiobook import chunk_text
from .audioengine import Player

def _co_init():
    """COM-inicializálás a szálon (a SAPI win32com-hoz kell)."""
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass


def _co_uninit():
    try:
        import pythoncom
        pythoncom.CoUninitialize()
    except Exception:
        pass


READ_DIR = Path.home() / ".superdl" / "read"
CHUNK_LIMIT = 140          # egy felolvasott darab max. hossza karakterben
                           # (kicsi: mondatszintű ugrás és pontos könyvjelző)


class ReadEngine:
    """Egy könyvet olvas fel élőben, megszakítható, pozíciókövető módon.
    Az `on_state(dict)` visszahívás a fő szálnak jelez (idx, total, pct,
    text, playing/done/error)."""

    def __init__(self, on_state=None):
        self.on_state = on_state
        self.player = Player()
        self._chunks: list[str] = []
        self._offsets: list[int] = []     # karakter-eltolás minden darab elején
        self._total = 0
        self._idx = 0
        self._stop = threading.Event()
        self._skipped = False
        self._thread = None
        self._pf: dict[int, str] = {}     # előre szintetizált darabok
        self._pf_lock = threading.Lock()
        # TTS-paraméterek
        self.engine_key = "edge"
        self.voice_id = ""
        self.rate = 0
        self.pitch = 0
        self.api_key = ""
        try:
            READ_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    # ---- szöveg betöltése ---------------------------------------------

    def load(self, text: str) -> None:
        self._chunks = chunk_text(text, CHUNK_LIMIT)
        self._offsets, acc = [], 0
        for c in self._chunks:
            self._offsets.append(acc)
            acc += len(c) + 1
        self._total = max(1, acc)

    @property
    def total_chars(self) -> int:
        return self._total

    def chunk_count(self) -> int:
        return len(self._chunks)

    def position_char(self) -> int:
        if 0 <= self._idx < len(self._offsets):
            return self._offsets[self._idx]
        return 0

    def _index_for_char(self, pos: int) -> int:
        if pos <= 0 or not self._offsets:
            return 0
        i = bisect_right(self._offsets, pos) - 1
        return max(0, min(i, len(self._chunks) - 1))

    # ---- vezérlés -----------------------------------------------------

    def is_active(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def is_paused(self) -> bool:
        return self.player.is_paused()

    def start(self, from_char: int = 0, *, engine_key=None, voice_id="",
              rate=0, pitch=0, api_key="") -> None:
        self.stop()
        if engine_key:
            self.engine_key = engine_key
        self.voice_id = voice_id
        self.rate, self.pitch, self.api_key = rate, pitch, api_key
        if not self._chunks:
            return
        self._idx = self._index_for_char(from_char)
        with self._pf_lock:
            self._pf.clear()
        self._stop = threading.Event()
        self._skipped = False
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def toggle_pause(self) -> bool:
        return self.player.toggle_pause()

    def pause(self) -> None:
        self.player.pause()

    def resume(self) -> None:
        self.player.resume()

    def skip(self, delta: int) -> None:
        """Ugrás előre/hátra mondatonként (delta = +1 / -1)."""
        if not self.is_active():
            return
        new = max(0, min(self._idx + delta, len(self._chunks) - 1))
        self._idx = new
        self._skipped = True
        self.player.stop()           # az aktuális darab leáll, a worker újraindul

    def stop(self) -> None:
        self._stop.set()
        self.player.stop()
        t = self._thread
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=2)
        self._thread = None

    # ---- belső --------------------------------------------------------

    def _emit(self, **kw) -> None:
        if self.on_state:
            try:
                self.on_state(kw)
            except Exception:
                pass

    def _synth(self, idx: int) -> str:
        base = str(READ_DIR / f"read_{idx % 4}")
        eng = tts.ENGINES[self.engine_key]
        return eng.synth(self._chunks[idx], self.voice_id, base,
                         self.pitch, self.rate, self.api_key)

    def _begin_prefetch(self, idx: int) -> None:
        if idx >= len(self._chunks):
            return

        def work():
            _co_init()
            try:
                path = self._synth(idx)
                with self._pf_lock:
                    self._pf[idx] = path
            except Exception:
                pass
            finally:
                _co_uninit()
        threading.Thread(target=work, daemon=True).start()

    def _take_prefetch(self, idx: int):
        with self._pf_lock:
            return self._pf.pop(idx, None)

    def _worker(self) -> None:
        _co_init()      # a SAPI (COM) háttérszálon ezt igényli
        try:
            self._run()
        finally:
            _co_uninit()

    def _run(self) -> None:
        while not self._stop.is_set():
            idx = self._idx
            if idx >= len(self._chunks):
                self._emit(done=True)
                return
            pct = round(self._offsets[idx] / self._total * 100)
            self._emit(idx=idx, total=len(self._chunks), pct=pct,
                       text=self._chunks[idx], playing=True)
            try:
                path = self._take_prefetch(idx) or self._synth(idx)
            except Exception as e:
                self._emit(error=str(e))
                return
            if self._stop.is_set():
                return
            self._begin_prefetch(idx + 1)
            self.player.play(path, "")
            # várunk, amíg a darab végigszól (a szünet is „aktív")
            while self.player.is_active():
                if self._stop.is_set():
                    return
                time.sleep(0.05)
            if self._stop.is_set():
                return
            if self._skipped:
                self._skipped = False     # a skip már beállította az _idx-et
            else:
                self._idx += 1

    def cleanup(self) -> None:
        try:
            shutil.rmtree(READ_DIR, ignore_errors=True)
        except OSError:
            pass
