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


# ---- MILLIOMOS kvíz – saját, EREDETI drámai hangvilág ---------------------
# Nem másol semmilyen műsorzenét: minden hang itt, numpy-val készül. A cél a
# hangulat (feszültség, „végleges" súlya, győzelem, bukás), nem a reprodukció.

def _mil_saw(fr, n, det=0.0):
    ph = np.cumsum(np.full(n, fr * (1 + det) / FS))
    return 2.0 * (ph - np.floor(0.5 + ph))


def _mil_pad(freqk, n, cutoff=1500, det=0.008):
    y = np.zeros(n)
    for fr in freqk:
        y += _mil_saw(fr, n, det) + _mil_saw(fr, n, -det) + 0.6 * np.sin(
            2 * np.pi * fr * np.arange(n) / FS)
    return _savszuro(y, 40, cutoff)


def _mil_start():
    """Indító szignál: rövid, felkúszó feszültség → fényes dúr feloldás."""
    n1 = int(FS * 1.0)
    t1 = np.arange(n1) / FS
    glide = 196.0 * 2 ** (5 * (t1 / (n1 / FS)) / 12.0)
    ph = np.cumsum(glide / FS)
    fesz = _savszuro(2 * (ph - np.floor(0.5 + ph)), 60, 1100) * np.linspace(0.2, 1, n1)
    n2 = int(FS * 1.3)
    akkord = _mil_pad([261.63, 329.63, 392.0, 523.25], n2, 2400) * _env(n2, 0.02, 0.6)
    return _norm(np.concatenate([fesz, akkord]), 0.42)


def _mil_kerdes():
    """Kérdés előtti finom, kétlépcsős jelzés (feszültséget indít)."""
    n = int(FS * 0.5)
    x = _mil_pad([220.0, 277.18], n, 1200) * _env(n, 0.02, 0.35)
    return _norm(x, 0.3)


def _mil_vegleges():
    """„Végleges válasz" – mély boom + rövid, feszült függő akkord."""
    n = int(FS * 1.3)
    t = np.arange(n) / FS
    boom = (np.sin(2 * np.pi * 48 * t) * np.exp(-t / 0.5)
            + 0.5 * np.sin(2 * np.pi * 120 * t) * np.exp(-t / 0.05))
    fesz = _mil_pad([220.0, 261.63, 311.13], n, 1300) * _env(n, 0.02, 0.5) * 0.7
    swell = _savszuro(_zaj(n), 300, 2000) * (t / (n / FS)) ** 2 * 0.3
    return _norm(boom + fesz + swell, 0.5)


def _mil_helyes():
    """Helyes válasz – fényes, felfutó csengő arpeggio + dúr csengés."""
    notes = [523.25, 659.25, 783.99, 1046.5, 1318.5]
    parts = []
    for i, fr in enumerate(notes):
        n = int(FS * 0.11)
        t = np.arange(n) / FS
        y = (np.sin(2 * np.pi * fr * t) + 0.5 * np.sin(2 * np.pi * 2 * fr * t)
             + 0.25 * np.sin(2 * np.pi * 3 * fr * t)) * np.exp(-t / 0.09)
        parts.append(y)
    ring_n = int(FS * 0.9)
    ring = _csengok([523.25, 659.25, 783.99, 1046.5], ring_n,
                    [0.6, 0.5, 0.5, 0.7])
    return _norm(np.concatenate(parts + [ring]), 0.44)


def _mil_rossz():
    """Rossz válasz – tritónuszos, lefelé csúszó gyomorütés + tompa boom."""
    n = int(FS * 1.6)
    t = np.arange(n) / FS
    f1 = 150 * 2 ** (-1.2 * (t / (n / FS)))
    f2 = f1 * 2 ** (6 / 12.0)                         # tritónusz
    ph1 = np.cumsum(f1 / FS); ph2 = np.cumsum(f2 / FS)
    y = 2 * (ph1 - np.floor(0.5 + ph1)) + 2 * (ph2 - np.floor(0.5 + ph2))
    y = _savszuro(y, 40, 1200) * _env(n, 0.01, 0.9)
    wob = 1.0 - 0.4 * (0.5 - 0.5 * np.cos(2 * np.pi * 7 * t))
    boom = np.sin(2 * np.pi * 42 * t) * np.exp(-t / 0.4) * 0.6
    return _norm(y * wob + boom, 0.46)


def _mil_garantalt():
    """Garantált pont – ünnepélyes mérföldkő: három csengő + meleg dúr akkord."""
    parts = []
    for fr in (659.25, 880.0, 1174.66):
        n = int(FS * 0.18)
        t = np.arange(n) / FS
        parts.append((np.sin(2 * np.pi * fr * t)
                      + 0.5 * np.sin(2 * np.pi * 2 * fr * t)) * np.exp(-t / 0.12))
    n2 = int(FS * 1.4)
    akkord = _mil_pad([261.63, 329.63, 392.0, 523.25], n2, 2600) * _env(n2, 0.02, 0.7)
    return _norm(np.concatenate(parts + [akkord]), 0.45)


def _mil_fonyeremeny():
    """Főnyeremény – nagy ünnep: felfutó arpeggiók + csillám + tartott dúr."""
    seq = [523.25, 659.25, 783.99, 1046.5, 1318.5, 1567.98, 2093.0]
    parts = []
    for fr in seq:
        n = int(FS * 0.10)
        t = np.arange(n) / FS
        parts.append((np.sin(2 * np.pi * fr * t)
                      + 0.5 * np.sin(2 * np.pi * 2 * fr * t)) * np.exp(-t / 0.08))
    n2 = int(FS * 2.0)
    t2 = np.arange(n2) / FS
    akkord = _mil_pad([261.63, 329.63, 392.0, 523.25, 659.25], n2, 3000) \
        * _env(n2, 0.02, 1.0)
    csillam = (np.sin(2 * np.pi * 1568 * t2) + np.sin(2 * np.pi * 2093 * t2)) \
        * np.exp(-t2 / 0.8) * 0.12
    e = _erme()
    return _norm(np.concatenate([np.concatenate(parts), akkord + csillam, e]), 0.5)


def _mil_felezo():
    """Felezés – rövid felszálló whoosh + két tompa koppanás (2 opció eltűnik)."""
    n = int(FS * 0.55)
    t = np.arange(n) / FS
    whoosh = _savszuro(_zaj(n), 500, 5000) * (t / (n / FS)) ** 2
    x = whoosh * 0.5
    for pos in (0.32, 0.46):
        i = int(pos * FS)
        L = int(FS * 0.08)
        seg = np.sin(2 * np.pi * 150 * np.arange(L) / FS) * np.exp(
            -np.arange(L) / (FS * 0.03))
        x[i:i + L] += seg[:max(0, min(L, n - i))][:len(x[i:i + L])]
    return _norm(x, 0.4)


def _mil_telefon():
    """Telefonos segítség – két rövid, klasszikus csengetés (kb. 425 Hz)."""
    n = int(FS * 1.4)
    t = np.arange(n) / FS
    ring = np.sin(2 * np.pi * 425 * t)
    kapu = ((t % 0.5) < 0.25).astype(float)              # ütemes ki-be
    ablak = ((t < 0.5) | ((t > 0.7) & (t < 1.2))).astype(float)   # két csengetés
    return _norm(ring * kapu * ablak * _env(n, 0.01, 0.1), 0.35)


def _mil_kozonseg():
    """Közönség – halk tömeg-morajlás (szűrt zaj) + indító csilingelés."""
    n = int(FS * 1.1)
    t = np.arange(n) / FS
    tomeg = _savszuro(_zaj(n), 200, 1500) * (0.4 + 0.3 * np.sin(2 * np.pi * 5 * t)) \
        * _env(n, 0.05, 0.4) * 0.5
    n2 = int(FS * 0.18)
    csing = _csengok([1046.5, 1318.5], n2, [0.12, 0.1])
    x = tomeg.copy()
    x[:n2] += csing[:min(n2, n)]
    return _norm(x, 0.34)


def _mil_kiszallas():
    """Kiszállás – meleg, megnyugtató dúr zárlat (viszed a pénzed)."""
    parts = []
    for freqk, dur in (([392.0, 493.88, 587.33], 0.5),
                       ([349.23, 440.0, 523.25], 0.5),
                       ([261.63, 329.63, 392.0, 523.25], 1.2)):
        n = int(FS * dur)
        parts.append(_mil_pad(freqk, n, 2000) * _env(n, 0.03, dur * 0.5))
    return _norm(np.concatenate(parts), 0.4)


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
    # Milliomos kvíz – saját, eredeti hangvilág
    "mil_start": _mil_start,
    "mil_kerdes": _mil_kerdes,
    "mil_vegleges": _mil_vegleges,
    "mil_helyes": _mil_helyes,
    "mil_rossz": _mil_rossz,
    "mil_garantalt": _mil_garantalt,
    "mil_fonyeremeny": _mil_fonyeremeny,
    "mil_felezo": _mil_felezo,
    "mil_telefon": _mil_telefon,
    "mil_kozonseg": _mil_kozonseg,
    "mil_kiszallas": _mil_kiszallas,
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
