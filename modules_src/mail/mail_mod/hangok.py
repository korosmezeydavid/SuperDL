# -*- coding: utf-8 -*-
"""Rövid jelzőhangok a levelezőhöz (modul-helyi, nem kell hozzá Core-kiadás).

Felhasználói kérés (2026-08-15): a levéllista TETEJÉN a felfelé nyíl ne olvassa
fel újra és újra ugyanazt a levelet – „vagy mondja, hogy nincs feljebb, vagy
csak egy pici bling hang jelezze".

A „bling" azért jobb alapértelmezés, mint egy mondat, mert a lista szélét
másodpercenként többször is el lehet érni gyors nyilazásnál: egy rövid hang
nem szakítja félbe a munkát, egy mondat viszont igen.
"""

from __future__ import annotations

import math
import struct
import threading
import wave
from pathlib import Path

_MAPPA = Path.home() / ".superdl" / "mail_hangok"
_MINTAVETEL = 22050

# TETEJE: rövid, magas, felfelé lépő „bling" – barátságos, nem hibajelzés.
_TETEJE = [(1175, 0.045), (1568, 0.075)]
# ALJA: ugyanaz lefelé – hallás után megkülönböztethető, hogy melyik szélen vagy.
_ALJA = [(1175, 0.045), (880, 0.075)]


def _hullam(frekvencia: float, hossz: float, amplitudo: float = 0.22) -> bytes:
    n = int(_MINTAVETEL * hossz)
    fel, le = int(0.008 * _MINTAVETEL), int(0.03 * _MINTAVETEL)
    ki = bytearray()
    for i in range(n):
        burok = 1.0
        if i < fel:
            burok = i / fel
        elif i > n - le:
            burok = max(0.0, (n - i) / le)
        ki += struct.pack("<h", int(32767 * amplitudo * burok
                                    * math.sin(2 * math.pi * frekvencia
                                               * i / _MINTAVETEL)))
    return bytes(ki)


def hang_fajl(teteje: bool) -> Path:
    _MAPPA.mkdir(parents=True, exist_ok=True)
    ut = _MAPPA / ("szel_fent.wav" if teteje else "szel_lent.wav")
    if not ut.is_file() or ut.stat().st_size < 500:
        adat = b"".join(_hullam(f, h) for f, h in (_TETEJE if teteje else _ALJA))
        with wave.open(str(ut), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(_MINTAVETEL)
            w.writeframes(adat)
    return ut


def bling(teteje: bool = True) -> bool:
    """Lejátssza a szél-jelzést (háttérszálon, a felület nem akad meg).
    Hiba esetén csendben False – a hang sosem áll a munka útjába."""
    try:
        ut = hang_fajl(teteje)
        import winsound
    except Exception:
        return False

    def jatszd():
        try:
            winsound.PlaySound(str(ut), winsound.SND_FILENAME)
        except Exception:
            pass

    threading.Thread(target=jatszd, daemon=True).start()
    return True
