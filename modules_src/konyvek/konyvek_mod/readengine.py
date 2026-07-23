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

from superdl import tts                      # megosztott TTS a Core-ból
from superdl.audiobook import chunk_text      # megosztott darabolás a Core-ból
from superdl.audioengine import Player        # megosztott lejátszó a Core-ból

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
CHUNK_LIMIT = 400          # egy felolvasott darab max. hossza karakterben.
                           # 140 volt, DE a 140+ karakteres mondat több darabra
                           # tört → a darabok közti szünet a mondat KÖZEPÉN
                           # „szaggatott" felolvasást adott (Szabó László). 400-nál
                           # a mondatok túlnyomó része EGY darab → folyamatos.


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
        self._pf: dict[tuple, str] = {}   # előre szintetizált darabok
        self._gen = 0                     # MUNKAMENET-generáció [READ-P0-01]
        self._last_prefetch_error = ""    # a néma elnyelés helyett
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
        # ÚJ MUNKAMENET: generáció + SAJÁT stop-esemény. Innentől a korábbi
        # szálak eredménye eldobandó, akkor is, ha később érkeznek meg.
        self._gen += 1
        gen = self._gen
        self._purge_old_generations(gen)
        stop_event = threading.Event()
        self._stop = stop_event
        self._skipped = False
        self._thread = threading.Thread(target=self._worker,
                                        args=(gen, stop_event), daemon=True)
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
        # A generáció léptetése AZONNAL elavulttá tesz minden futó szálat,
        # akkor is, ha a join időtúllépéssel tér vissza. [READ-P0-01]
        self._gen += 1
        self._stop.set()
        self.player.stop()
        t = self._thread
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=2)
        self._thread = None

    # ---- belső --------------------------------------------------------

    def _emit_gen(self, gen: int, **kw) -> None:
        """Állapot kiadása CSAK az AKTUÁLIS munkamenetből – így egy régi,
        leváltott szál nem küld hamis állapotot az új könyvre."""
        if gen == self._gen:
            self._emit(**kw)

    def _emit(self, **kw) -> None:
        if self.on_state:
            try:
                self.on_state(kw)
            except Exception:
                pass

    def _purge_old_generations(self, gen: int) -> None:
        """A KORÁBBI munkamenetek hangdarabjainak törlése. Generációnként külön
        fájlnevet használunk (az ütközés ellen), ezért a régieket takarítani
        kell – különben a könyvrészletek felhalmozódnának a lemezen."""
        try:
            elo = f"read_{gen}_"
            for f in READ_DIR.glob("read_*"):
                if not f.name.startswith(elo):
                    try:
                        f.unlink()
                    except OSError:
                        pass          # épp szól belőle: majd a következő körben
        except OSError:
            pass

    def _synth(self, idx: int, gen: int) -> str:
        # A fájlnév a MUNKAMENETHEZ kötött: a régi fix `read_{idx%4}` gyűrűt két
        # olvasóablak (vagy egy régi előregyártó szál) egyszerre írhatta, így
        # RÉGI hang kerülhetett az új mondathoz. [Herman Tibi READ-P0-02]
        base = str(READ_DIR / f"read_{gen}_{idx % 4}")
        eng = tts.ENGINES[self.engine_key]
        return eng.synth(self._chunks[idx], self.voice_id, base,
                         self.pitch, self.rate, self.api_key)

    def _begin_prefetch(self, idx: int, gen: int) -> None:
        if idx >= len(self._chunks) or gen != self._gen:
            return

        def work():
            _co_init()
            try:
                path = self._synth(idx, gen)
                with self._pf_lock:
                    if gen == self._gen:        # elavult eredményt eldobunk
                        self._pf[(gen, idx)] = path
            except Exception as e:
                # a hiba NEM tűnhet el némán: ha az előregyártás bukik, a fő
                # szál újra megpróbálja, de a diagnózishoz tudni kell róla
                self._last_prefetch_error = f"{type(e).__name__}: {e}"
            finally:
                _co_uninit()
        threading.Thread(target=work, daemon=True).start()

    def _take_prefetch(self, idx: int, gen: int):
        with self._pf_lock:
            return self._pf.pop((gen, idx), None)

    def _worker(self, gen: int, stop_event) -> None:
        _co_init()      # a SAPI (COM) háttérszálon ezt igényli
        try:
            self._run(gen, stop_event)
        finally:
            _co_uninit()

    def _run(self, gen: int, stop_event) -> None:
        # FONTOS: KIZÁRÓLAG a saját `stop_event`-jét és `gen`-jét figyeli, nem a
        # közös self._stop-ot. A régi kód a lecserélhető közös eseményt olvasta,
        # ezért egy elhúzódó (a 2 mp-es várakozást túlélő) TTS-szál az ÚJ könyv
        # állapotán dolgozott tovább: keveredő mondatok, rossz könyvjelző.
        # [Herman Tibi READ-P0-01]
        while not stop_event.is_set() and gen == self._gen:
            idx = self._idx
            if idx >= len(self._chunks):
                self._emit_gen(gen, done=True)
                return
            pct = round(self._offsets[idx] / self._total * 100)
            self._emit_gen(gen, idx=idx, total=len(self._chunks), pct=pct,
                           text=self._chunks[idx], playing=True)
            try:
                path = self._take_prefetch(idx, gen) or self._synth(idx, gen)
            except Exception as e:
                self._emit_gen(gen, error=str(e))
                return
            if stop_event.is_set() or gen != self._gen:
                return
            self._begin_prefetch(idx + 1, gen)
            self.player.play(path, "")
            # várunk, amíg a darab végigszól (a szünet is „aktív")
            while self.player.is_active():
                if stop_event.is_set() or gen != self._gen:
                    return
                time.sleep(0.05)
            if stop_event.is_set() or gen != self._gen:
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
