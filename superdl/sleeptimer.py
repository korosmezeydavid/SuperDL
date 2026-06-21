"""Általános alvás-időzítő lejátszáshoz/felolvasáshoz.

  * megadott IDŐTARTAM után leáll (5 perces lépésekben jellemzően),
  * a ciklust NÉGY részre osztva minden negyednél (25/50/75/100 %) elsüt egy
    „elalvási pont" visszahívást (a hívó elmenti a pillanatnyi pozíciót),
  * a vége előtti utolsó pár tíz másodpercben LASSAN ELHALKÍT (a hívó hangerő-
    állítójával), majd leállít.

A motor független a tényleges lejátszótól: a hívó adja meg a visszahívásokat
(elalvási pont rögzítése, hangerő-állítás, leállítás). Így a könyvolvasóhoz és
bármely audioengine.Player-es lejátszóhoz is használható.
"""

import threading
import time


class SleepTimer:
    def __init__(self, duration_s: float, *, on_mark=None, on_fade=None,
                 on_finish=None, on_tick=None, fade_s: float = 25.0):
        self.duration_s = max(1.0, float(duration_s))
        self.on_mark = on_mark          # on_mark(quarter:int 1..4)
        self.on_fade = on_fade          # on_fade(level: float 1..0)
        self.on_finish = on_finish      # on_finish()
        self.on_tick = on_tick          # on_tick(remaining_s) – kb. másodpercenként
        self.fade_s = min(max(0.0, fade_s), self.duration_s)
        self._start = 0.0
        self._extra = 0.0               # meghosszabbítás
        self._stop = threading.Event()
        self._fired = set()             # mely negyedek sültek már el
        self._faded = False
        self._thread = None

    # ---- vezérlés -----------------------------------------------------

    def start(self):
        self._start = time.monotonic()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self):
        """Megszakítás leállítás nélkül – a hangerőt visszaállítja."""
        if self._stop.is_set():
            return
        self._stop.set()
        if self.on_fade:
            try:
                self.on_fade(1.0)
            except Exception:
                pass

    def extend(self, extra_s: float):
        self._extra += float(extra_s)
        self._faded = False             # ha már halkult, a hosszabbítás visszahozza
        if self.on_fade:
            try:
                self.on_fade(1.0)
            except Exception:
                pass

    def active(self) -> bool:
        return self._thread is not None and self._thread.is_alive() \
            and not self._stop.is_set()

    def total_s(self) -> float:
        return self.duration_s + self._extra

    def elapsed_s(self) -> float:
        return time.monotonic() - self._start if self._start else 0.0

    def remaining_s(self) -> float:
        return max(0.0, self.total_s() - self.elapsed_s())

    # ---- futás --------------------------------------------------------

    def _run(self):
        while not self._stop.is_set():
            total = self.total_s()
            elapsed = self.elapsed_s()
            remaining = total - elapsed

            # negyed-pontok (25/50/75 %) – a 100 %-ot a végén sütjük el
            for q in (1, 2, 3):
                if q not in self._fired and elapsed >= total * q / 4:
                    self._fired.add(q)
                    self._call_mark(q)

            # elhalkulás az utolsó fade_s másodpercben
            if self.on_fade and self.fade_s > 0 and remaining <= self.fade_s:
                level = max(0.0, min(1.0, remaining / self.fade_s))
                try:
                    self.on_fade(level)
                except Exception:
                    pass
                self._faded = True

            if self.on_tick:
                try:
                    self.on_tick(remaining)
                except Exception:
                    pass

            if remaining <= 0:
                break
            self._stop.wait(min(1.0, max(0.1, remaining)))

        if self._stop.is_set():
            return
        # vég: 4. elalvási pont, teljes csend, leállítás
        self._call_mark(4)
        if self.on_fade:
            try:
                self.on_fade(0.0)
            except Exception:
                pass
        if self.on_finish:
            try:
                self.on_finish()
            except Exception:
                pass

    def _call_mark(self, q: int):
        if self.on_mark:
            try:
                self.on_mark(q)
            except Exception:
                pass
