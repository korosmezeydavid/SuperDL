# -*- coding: utf-8 -*-
"""Csevejcenter – KÖZÖS ZENE: egy hangfájlt 16 kHz mono PCM-kockákra bont
(ffmpeg-gel), és valós idejű ütemezéssel adja ki a `on_kocka(pcm)` callbacknek.
A hálózati réteg ezeket „🎵 Zene” néven küldi szét a szobában, így mindenki
együtt hallja. Csak a Core-ban már meglévő ffmpeg kell (nincs új függőség).
"""
import subprocess
import threading
import time

from .terhang import BLOKK, FS


class Zenelejatszo:
    def __init__(self, on_kocka, on_vege=None):
        self.on_kocka = on_kocka           # (pcm16_bytes) – egy ~20 ms-os kocka
        self.on_vege = on_vege             # () – a zene véget ért / leállt
        self._stop = threading.Event()
        self._proc = None
        self._thread = None

    def elerheto(self) -> bool:
        try:
            from superdl.ffmpeg import find_ffmpeg
            return bool(find_ffmpeg())
        except Exception:
            return False

    def indit(self, ut: str):
        from superdl.ffmpeg import find_ffmpeg
        ff = find_ffmpeg()
        if not ff:
            raise RuntimeError("Az ffmpeg nem érhető el a zene lejátszásához.")
        self._proc = subprocess.Popen(
            [ff, "-nostdin", "-loglevel", "quiet", "-i", ut,
             "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "1", "-ar", str(FS), "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10 ** 6)
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        n = BLOKK * 2                       # 320 minta * 2 bájt (PCM16 mono)
        start = time.monotonic()
        i = 0
        try:
            while not self._stop.is_set():
                buf = self._proc.stdout.read(n)
                if not buf or len(buf) < n:
                    break
                try:
                    self.on_kocka(buf)
                except Exception:
                    pass
                i += 1
                cel = start + i * (BLOKK / float(FS))   # pontos, valós idejű ütemezés
                d = cel - time.monotonic()
                if d > 0:
                    time.sleep(d)
        except Exception:
            pass
        finally:
            self._kilep()

    def leallit(self):
        self._stop.set()
        self._kilep()

    def _kilep(self):
        p = self._proc
        self._proc = None
        if p is not None:
            try:
                p.kill()
            except Exception:
                pass
        if self.on_vege:
            try:
                self.on_vege()
            except Exception:
                pass
