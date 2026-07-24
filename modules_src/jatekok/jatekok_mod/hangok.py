# -*- coding: utf-8 -*-
"""Játékhang-effektek – modern + fémes stílusban, SAJÁT szintézissel (numpy).

Semmilyen külső hangfájl: minden effektet menet közben állítunk elő. A
`keszit(nev)` visszaad egy (minta-tömb −1..1, mintavétel) párt, amit a
JatekKonzol lejátszik. A Saját játékok (UNO, félkarú rabló, Mille Bornes)
használják ezeket."""
import numpy as np

FS = 22050


def _norm(x, csucs=0.4):
    m = float(np.max(np.abs(x))) if len(x) else 0.0
    return (x / m * csucs) if m > 0 else x


def _env(n, atk=0.005, rel=0.1):
    e = np.ones(n)
    a = min(n, int(FS * atk))
    r = min(n - a, int(FS * rel))
    if a > 0:
        e[:a] = np.linspace(0, 1, a)
    if r > 0:
        e[-r:] = np.linspace(1, 0, r)
    return e


def _zaj(n):
    return np.random.uniform(-1, 1, n)


def _savszuro(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / FS)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x))


def _csengok(freqk, n, lecsengesek):
    t = np.arange(n) / FS
    y = np.zeros(n)
    for fr, dc in zip(freqk, lecsengesek):
        y += np.sin(2 * np.pi * fr * t) * np.exp(-t / dc)
    return y


# ---- az egyes effektek ---------------------------------------------------

def _kartya():
    """Kártyahúzás/dobás: modern swish – szűrt zajlökés, gyors lecsengéssel."""
    n = int(FS * 0.16)
    t = np.arange(n) / FS
    x = _savszuro(_zaj(n), 2500, 7000) * np.exp(-t / 0.05)
    return _norm(x, 0.4)


def _erme():
    """Érme/pénz: fémes „csing" – inharmonikus partálok, gyors lecsengés,
    két rövid koppanással."""
    def ping(fr):
        n = int(FS * 0.20)
        t = np.arange(n) / FS
        return _csengok([fr, fr * 2.76, fr * 5.4], n,
                        [0.09, 0.05, 0.03]) * np.exp(-t / 0.06)
    a = ping(2600.0)
    b = ping(3200.0)
    res = int(FS * 0.05)
    x = np.zeros(len(a) + res)
    x[:len(a)] += a
    x[res:res + len(b)] += 0.8 * b
    return _norm(x, 0.42)


def _porgetes():
    """Slot pörgés: gyorsuló-lassuló kattogás, kb. 1,4 mp."""
    dur = 1.4
    n = int(FS * dur)
    x = np.zeros(n)
    t = 0.0
    while t < dur:
        i = int(t * FS)
        if i >= n:
            break
        L = int(FS * 0.006)
        seg = _zaj(L) * np.exp(-np.arange(L) / (FS * 0.0015))
        m = min(L, n - i)
        x[i:i + m] += seg[:m]
        frac = t / dur
        interval = 0.012 + 0.035 * abs(frac - 0.45)   # középen sűrű, szélén ritka
        t += max(0.01, interval)
    x = _savszuro(x, 400, 6000)
    return _norm(x, 0.35)


def _megall():
    """Tekercs megáll: rövid „thunk"."""
    n = int(FS * 0.12)
    t = np.arange(n) / FS
    y = (np.sin(2 * np.pi * 170 * t) * np.exp(-t / 0.03)
         + 0.5 * _savszuro(_zaj(n), 200, 1200) * np.exp(-t / 0.02))
    return _norm(y, 0.4)


def _nyeremeny():
    """Nyeremény-jingle: emelkedő arpeggio (C E G C)."""
    notes = [523.25, 659.25, 783.99, 1046.5]
    n = int(FS * 0.15)
    parts = []
    for fr in notes:
        t = np.arange(n) / FS
        y = (np.sin(2 * np.pi * fr * t) + 0.5 * np.sin(2 * np.pi * 2 * fr * t))
        parts.append(y * _env(n, 0.005, 0.11))
    return _norm(np.concatenate(parts), 0.42)


def _nagy_nyeremeny():
    """Nagy nyeremény: hosszabb, csillogó felfutás + érmecsörgés."""
    j = _nyeremeny()
    e = _erme()
    x = np.concatenate([j, e, np.roll(e, int(FS * 0.03)) * 0.7])
    return _norm(x, 0.45)


def _veszit():
    """Vesztés/nincs: ereszkedő szomorkás blip."""
    notes = [440.0, 392.0, 329.6]
    n = int(FS * 0.14)
    parts = []
    for fr in notes:
        t = np.arange(n) / FS
        parts.append(np.sin(2 * np.pi * fr * t) * _env(n, 0.005, 0.1))
    return _norm(np.concatenate(parts), 0.35)


def _blip():
    """Semleges UI-koppanás (lépés, lerakás)."""
    n = int(FS * 0.06)
    t = np.arange(n) / FS
    return _norm(np.sin(2 * np.pi * 880 * t) * np.exp(-t / 0.03), 0.33)


def _dobas():
    """Kockadobás/rázás: rövid, szűrt zörrenés."""
    n = int(FS * 0.28)
    t = np.arange(n) / FS
    x = _savszuro(_zaj(n), 300, 3000)
    x *= (0.5 + 0.5 * np.sin(2 * np.pi * 28 * t)) * np.exp(-t / 0.16)
    return _norm(x, 0.35)


_EPITOK = {
    "kartya": _kartya,
    "erme": _erme,
    "porgetes": _porgetes,
    "megall": _megall,
    "nyeremeny": _nyeremeny,
    "nagy_nyeremeny": _nagy_nyeremeny,
    "veszit": _veszit,
    "blip": _blip,
    "dobas": _dobas,
}


def nevek():
    return tuple(_EPITOK)


def keszit(nev: str):
    """A megnevezett effekt (minta-tömb −1..1, mintavétel). Ismeretlen névre
    (None, FS)."""
    f = _EPITOK.get(nev)
    if f is None:
        return None, FS
    return f().astype(float), FS
