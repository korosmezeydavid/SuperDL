# -*- coding: utf-8 -*-
"""RETRÓ BESZÉDHANG – a 80-as/90-es évek magyar beszélő gépeinek hangzása.

MI EZ ÉS MI NEM:
A BraiLab 4 (HomeLab 4 + beszéd-ROM) jellegzetes hangját egy Philips MEA8000
FORMÁNS-beszédgenerátor chip adta. Ez a modul NEM azt a chipet emulálja, NEM
használ fel semmilyen eredeti ROM-ot vagy kódot – hanem a korszak
formánsszintézisének ISMERT AKUSZTIKAI JELLEMZŐIT alkotja újra, saját kóddal:

  1. kevés formáns → az eSpeak beépített Klatt-formánsszintézise adja az alapot;
  2. szűk sávszélesség → ~8 kHz mintavétel, 300–3400 Hz sáv;
  3. durva kvantálás → csökkentett bitmélység + minta-tartás („lépcsőzés");
  4. szabályos gerjesztés → rögzített hangmagasság és tempó (nincs élő ingadozás).

A feldolgozás numpyval történik (a Core-ban már ott van), külső program
nélkül – így gyors, és nem függ az ffmpeg meglététől.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import uuid
import wave
from dataclasses import dataclass

_NOWIN = 0x08000000 if os.name == "nt" else 0


@dataclass(frozen=True)
class RetroPreset:
    """Egy retró hangkarakter. A `nev` a felületen jelenik meg."""
    kulcs: str
    nev: str
    variant: str          # eSpeak hang-változat (pl. "klatt2")
    freq: int = 8000      # kimeneti mintavétel (a korszakra jellemző)
    also_hz: int = 300    # sáv alsó határa
    felso_hz: int = 3400  # sáv felső határa
    bitek: int = 8        # effektív bitmélység (kvantálás)
    tartas: int = 1       # minta-tartás (1 = nincs; 2-3 = durvább „lépcső")
    sebesseg: int = 150   # eSpeak tempó (szó/perc)
    hangmagassag: int = 50   # eSpeak alap-hangmagasság (0..99)
    hangkozok: int = 20   # hanglejtés-tartomány (kicsi = monoton, gépies)


# A választható karakterek. Az elsőt tekintjük alapértelmezettnek.
PRESETS: tuple[RetroPreset, ...] = (
    RetroPreset("brailab", "Retró beszélő gép (a legjellegzetesebb)",
                variant="klatt2", bitek=8, tartas=1,
                sebesseg=145, hangmagassag=45, hangkozok=15),
    RetroPreset("robot", "Kemény robot (durvább, gépiesebb)",
                variant="robosoft", bitek=6, tartas=2,
                sebesseg=140, hangmagassag=40, hangkozok=5),
    RetroPreset("terminal", "Terminál (tisztább, de korhű)",
                variant="klatt4", bitek=10, tartas=1, felso_hz=3800,
                sebesseg=155, hangmagassag=55, hangkozok=25),
    RetroPreset("urhajo", "Űrhajó fedélzeti hang (mély, lassú)",
                variant="klatt3", bitek=8, tartas=1, felso_hz=3000,
                sebesseg=130, hangmagassag=25, hangkozok=10),
    RetroPreset("tiszta", "Mai hang (összehasonlításhoz, nem retró)",
                variant="", freq=22050, also_hz=0, felso_hz=0,
                bitek=16, tartas=1, sebesseg=165, hangmagassag=50,
                hangkozok=50),
)

PRESET_MAP = {p.kulcs: p for p in PRESETS}
DEFAULT_PRESET = PRESETS[0].kulcs


def preset(kulcs: str) -> RetroPreset:
    return PRESET_MAP.get(kulcs or "", PRESETS[0])


# ---------------------------------------------------------------- DSP

def _biquad(x, b0, b1, b2, a1, a2):
    """Másodfokú szűrő futtatása (Direct Form I). Kis mennyiségű hangnál a
    numpy-s ciklus is bőven elég gyors, és nincs scipy-függőségünk."""
    import numpy as np
    y = np.empty_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i in range(x.shape[0]):
        xi = float(x[i])
        yi = b0 * xi + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        y[i] = yi
        x2, x1 = x1, xi
        y2, y1 = y1, yi
    return y


def _lowpass(x, fs: int, fc: float, q: float = 0.707):
    import math
    if fc <= 0 or fc >= fs / 2:
        return x
    w = 2 * math.pi * fc / fs
    cs, sn = math.cos(w), math.sin(w)
    al = sn / (2 * q)
    b0 = (1 - cs) / 2
    b1 = 1 - cs
    b2 = (1 - cs) / 2
    a0 = 1 + al
    a1 = -2 * cs
    a2 = 1 - al
    return _biquad(x, b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def _highpass(x, fs: int, fc: float, q: float = 0.707):
    import math
    if fc <= 0:
        return x
    w = 2 * math.pi * fc / fs
    cs, sn = math.cos(w), math.sin(w)
    al = sn / (2 * q)
    b0 = (1 + cs) / 2
    b1 = -(1 + cs)
    b2 = (1 + cs) / 2
    a0 = 1 + al
    a1 = -2 * cs
    a2 = 1 - al
    return _biquad(x, b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def _resample(x, fs_be: int, fs_ki: int):
    """Egyszerű lineáris újramintavételezés. A tükrözés (aliasing) ellen a
    hívó ELŐTTE aluláteresztő szűrőt futtat – ez adja a korhű sávkorlátot."""
    import numpy as np
    if fs_be == fs_ki or x.size == 0:
        return x
    n_ki = int(round(x.size * fs_ki / fs_be))
    if n_ki <= 1:
        return x
    poz = np.linspace(0.0, x.size - 1.0, n_ki)
    return np.interp(poz, np.arange(x.size, dtype=np.float64), x)


def _kvantal(x, bitek: int):
    """Bitmélység-csökkentés: ez adja a korszakra jellemző „szemcsés" hangot."""
    import numpy as np
    if bitek >= 16:
        return x
    lepcsok = float(2 ** (bitek - 1))
    return np.round(x * lepcsok) / lepcsok


def _minta_tartas(x, n: int):
    """Minta-tartás: minden n-edik mintát tartjuk – a MEA8000-re jellemző
    „lépcsőzött" átmenetek hatását utánozza."""
    import numpy as np
    if n <= 1 or x.size == 0:
        return x
    y = x.copy()
    for eltolas in range(1, n):
        y[eltolas::n] = x[0::n][:y[eltolas::n].size]
    return y


def retrofy(pcm_f, fs_be: int, p: RetroPreset):
    """A nyers hangból RETRÓ hang. Bemenet/kimenet: float tömb (-1..1).
    Visszaad: (feldolgozott, kimeneti_mintavétel)."""
    import numpy as np
    x = np.asarray(pcm_f, dtype=np.float64)
    if x.size == 0:
        return x, p.freq
    # 1) sávkorlát MÉG az eredeti mintavételen (ez egyben tükrözés-védelem)
    if p.felso_hz:
        x = _lowpass(x, fs_be, min(p.felso_hz, fs_be / 2 - 200))
    # 2) korhű mintavételre alakítás
    x = _resample(x, fs_be, p.freq)
    # 3) mély zörej levágása (a korabeli hangszórók sem adták vissza)
    if p.also_hz:
        x = _highpass(x, p.freq, p.also_hz)
    # 4) durva kvantálás + minta-tartás → a jellegzetes „gépi szemcse"
    x = _minta_tartas(x, p.tartas)
    x = _kvantal(x, p.bitek)
    # 5) normalizálás úgy, hogy ne vágjon
    csucs = float(np.max(np.abs(x))) if x.size else 0.0
    if csucs > 0:
        x = x / csucs * 0.89
    return x, p.freq


# ------------------------------------------------------------- eSpeak

def _espeak() -> tuple[str, str]:
    """A beépített eSpeak elérési útja és adatmappája (a Core-ból)."""
    from . import selfvoice
    return selfvoice._espeak_paths()


def available() -> bool:
    """Van-e működő beszédmotor a retró hanghoz?"""
    exe, _ = _espeak()
    return bool(exe)


def _espeak_wav(text: str, p: RetroPreset, out_wav: str) -> None:
    exe, data = _espeak()
    if not exe:
        raise RuntimeError(
            "A retró hanghoz szükséges beszédmotor (eSpeak) nem érhető el.")
    hang = "hu" + (f"+{p.variant}" if p.variant else "")
    cmd = [exe, "-v", hang, "-s", str(p.sebesseg), "-p", str(p.hangmagassag),
           "-w", out_wav]
    if data:
        from pathlib import Path as _P
        cmd += ["--path", str(_P(data).parent)]
    cmd.append(text)
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                       text=True, encoding="utf-8", errors="replace",
                       creationflags=_NOWIN, timeout=120)
    if r.returncode != 0 or not os.path.isfile(out_wav):
        raise RuntimeError("A beszéd elkészítése nem sikerült: "
                           + (r.stderr or "ismeretlen hiba").strip()[:200])


def _wav_be(path: str):
    import numpy as np
    with wave.open(path, "rb") as w:
        fs = w.getframerate()
        n = w.getnframes()
        szel = w.getsampwidth()
        cs = w.getnchannels()
        raw = w.readframes(n)
    if szel != 2:
        raise RuntimeError("Csak 16 bites WAV támogatott.")
    a = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if cs > 1:
        a = a.reshape(-1, cs).mean(axis=1)
    return a, fs


def _wav_ki(path: str, x, fs: int) -> None:
    import numpy as np
    a = np.clip(np.asarray(x, dtype=np.float64), -1.0, 1.0)
    pcm = (a * 32767.0).astype("<i2").tobytes()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(fs))
        w.writeframes(pcm)


# ------------------------------------------------------------- API

def synth(text: str, out_path: str = "", preset_kulcs: str = "") -> str:
    """A megadott szöveg RETRÓ hangon, WAV-fájlba. Visszaad: a fájl útja.

    A hívó törölje a fájlt, ha már nincs rá szüksége (vagy használja a
    `speak()`-et, ami magától takarít)."""
    if not (text or "").strip():
        raise ValueError("Nincs felolvasandó szöveg.")
    p = preset(preset_kulcs)
    out = out_path or os.path.join(
        tempfile.gettempdir(),
        f"superdl_retro_{os.getpid()}_{uuid.uuid4().hex[:8]}.wav")
    nyers = out + ".nyers.wav"
    try:
        _espeak_wav(text, p, nyers)
        x, fs = _wav_be(nyers)
        y, fs_ki = retrofy(x, fs, p)
        _wav_ki(out, y, fs_ki)
    finally:
        try:
            if os.path.exists(nyers):
                os.remove(nyers)
        except OSError:
            pass
    return out


def speak(text: str, preset_kulcs: str = "", player=None) -> None:
    """Azonnali megszólaltatás a Core lejátszójával, majd takarítás."""
    path = synth(text, "", preset_kulcs)
    try:
        if player is None:
            from .audioengine import Player
            player = Player()
        player.play(path, "")
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise
