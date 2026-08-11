# -*- coding: utf-8 -*-
"""Távsegítség – a beérkező hang LEJÁTSZÁSA a segítő gépén (sounddevice).

A segítettől érkező int16/16kHz/mono PCM-et egy folyamatos kimeneti stream
játssza le, egy kis pufferből (hogy ne szaggasson). A sounddevice már a Core-
ban van (a Csevejcenter is használja) – nincs új függőség."""
import threading


class HangLejatszo:
    def __init__(self, sr=16000):
        self.sr = sr
        self.elerheto = True
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._stream = None
        self._np = None

    def indit(self):
        try:
            import numpy as np
            import sounddevice as sd
        except Exception:
            self.elerheto = False
            return False
        self._np = np

        def cb(outdata, frames, timeinfo, status):
            keres = frames * 2                       # int16 mono → 2 bájt/minta
            with self._lock:
                van = min(keres, len(self._buf))
                darab = bytes(self._buf[:van])
                del self._buf[:van]
            if van < keres:                          # alulcsordulás → csend
                darab += b"\x00" * (keres - van)
            try:
                outdata[:] = np.frombuffer(darab, dtype=np.int16).reshape(-1, 1)
            except Exception:
                outdata[:] = 0

        try:
            self._stream = sd.OutputStream(
                samplerate=self.sr, channels=1, dtype="int16", callback=cb)
            self._stream.start()
            return True
        except Exception:
            self.elerheto = False
            return False

    def jatszd(self, pcm):
        """Egy beérkezett PCM-darab a lejátszó-pufferbe. A puffert korlátozzuk,
        hogy ne halmozódjon a késleltetés (max ~1,5 mp)."""
        if not pcm:
            return
        with self._lock:
            self._buf.extend(pcm)
            maxb = self.sr * 2 * 3 // 2               # ~1,5 mp
            tul = len(self._buf) - maxb
            if tul > 0:
                del self._buf[:tul]

    def leallit(self):
        try:
            if self._stream:
                self._stream.stop()
                self._stream.close()
        except Exception:
            pass
        self._stream = None
