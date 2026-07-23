# -*- coding: utf-8 -*-
"""IGAZI RETRÓ FORMÁNSSZINTETIZÁTOR – teljesen saját, eSpeak NÉLKÜL.

MIÉRT KELLETT EZ:
Az eSpeak-alapú út (retrovoice.py) bármennyire szűrjük, hallatszik rajta az
alapmotor: túl SIMÁN köti össze a hangokat. A 80-as/90-es évek gépeinél épp
az volt a jellegzetes, hogy szinte HALLOTTAD, ahogy a hangokat egymás után
„ledarálja": minden hangzó a saját formáns-értékein SZÓLT egy darabig, aztán
UGROTT a következőre.

Ez a modul ezt csinálja, három lépésben:
  1. MAGYAR BETŰ→HANG átalakítás (a magyar írás majdnem tökéletesen fonetikus,
     ezért ez megbízhatóan megoldható – a korabeli gépek ROM-ja is így ment);
  2. minden hangzóhoz SAJÁT formáns-értékek és időtartam (a mi tábláink);
  3. FORMÁNSSZINTÉZIS: rezonátor-lánc, zöngés impulzus- vagy zaj-gerjesztéssel.

Semmilyen idegen ROM-ot, chip-kódot vagy hangmintát NEM használ. A táblák
általános fonetikai értékeken alapulnak, a kód a sajátunk.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# ---------------------------------------------------------------- hangzók

MGH = "aáeéiíoóöőuúüű"          # magánhangzók


@dataclass(frozen=True)
class Hang:
    """Egy beszédhang akusztikai leírása.

    tipus: 'mgh' (magánhangzó), 'zonges'/'zongetlen' (rés), 'zar' (zárhang),
           'nazalis', 'perges', 'oldalso', 'szunet'
    """
    tipus: str
    f1: float = 500.0
    f2: float = 1500.0
    f3: float = 2500.0
    b1: float = 90.0            # sávszélességek (kisebb = csengőbb, gépiesebb)
    b2: float = 110.0
    b3: float = 170.0
    hossz: int = 90             # alap-időtartam ezredmásodpercben
    hangero: float = 1.0
    zaj: float = 0.0            # a gerjesztés zaj-aránya (0 = tiszta zönge)
    zarlat: int = 0             # néma zárlat a hang előtt (ms) – zárhangoknál


# A magyar hangzók formáns-táblája. Általános fonetikai értékek, kerekítve –
# a korabeli gépek is DURVA, kvantált táblákkal dolgoztak.
TABLA: dict[str, Hang] = {
    # --- magánhangzók (rövid / hosszú) ---
    "a":  Hang("mgh", 620, 1050, 2500, hossz=95),
    "á":  Hang("mgh", 720, 1250, 2550, hossz=165),
    "e":  Hang("mgh", 600, 1750, 2600, hossz=95),
    "é":  Hang("mgh", 420, 2100, 2700, hossz=165),
    "i":  Hang("mgh", 310, 2200, 3000, hossz=90),
    "í":  Hang("mgh", 290, 2300, 3050, hossz=160),
    "o":  Hang("mgh", 470, 820, 2500, hossz=95),
    "ó":  Hang("mgh", 430, 760, 2500, hossz=165),
    "ö":  Hang("mgh", 460, 1520, 2200, hossz=95),
    "ő":  Hang("mgh", 420, 1580, 2200, hossz=165),
    "u":  Hang("mgh", 340, 720, 2400, hossz=90),
    "ú":  Hang("mgh", 315, 680, 2400, hossz=160),
    "ü":  Hang("mgh", 310, 1750, 2200, hossz=90),
    "ű":  Hang("mgh", 300, 1800, 2200, hossz=160),
    # --- zárhangok (néma zárlat + rövid pattanás) ---
    "p":  Hang("zar", 400, 1100, 2300, hossz=22, zaj=1.0, zarlat=55, hangero=0.7),
    "b":  Hang("zar", 350, 1100, 2300, hossz=22, zaj=0.5, zarlat=45, hangero=0.7),
    "t":  Hang("zar", 400, 1800, 2700, hossz=22, zaj=1.0, zarlat=55, hangero=0.75),
    "d":  Hang("zar", 350, 1700, 2600, hossz=22, zaj=0.5, zarlat=45, hangero=0.75),
    "k":  Hang("zar", 400, 1900, 2400, hossz=26, zaj=1.0, zarlat=60, hangero=0.75),
    "g":  Hang("zar", 350, 1800, 2350, hossz=24, zaj=0.5, zarlat=48, hangero=0.75),
    "ty": Hang("zar", 350, 2100, 2900, hossz=28, zaj=1.0, zarlat=55, hangero=0.75),
    "gy": Hang("zar", 320, 2000, 2800, hossz=26, zaj=0.5, zarlat=45, hangero=0.75),
    # --- réshangok ---
    "f":  Hang("zongetlen", 900, 1900, 3200, hossz=85, zaj=1.0, hangero=0.55),
    "v":  Hang("zonges", 500, 1600, 2600, hossz=70, zaj=0.6, hangero=0.7),
    "sz": Hang("zongetlen", 1800, 3600, 5200, hossz=105, zaj=1.0, hangero=0.65,
               b1=250, b2=300, b3=400),
    "z":  Hang("zonges", 1600, 3200, 4600, hossz=80, zaj=0.7, hangero=0.7,
               b1=220, b2=280, b3=380),
    "s":  Hang("zongetlen", 1400, 2600, 3800, hossz=110, zaj=1.0, hangero=0.7,
               b1=280, b2=340, b3=420),
    "zs": Hang("zonges", 1300, 2400, 3600, hossz=80, zaj=0.7, hangero=0.7,
               b1=260, b2=320, b3=400),
    "h":  Hang("zongetlen", 600, 1500, 2500, hossz=75, zaj=1.0, hangero=0.4),
    # --- affrikáták (zárlat + rés) ---
    "c":  Hang("zar", 1800, 3400, 5000, hossz=70, zaj=1.0, zarlat=45,
               hangero=0.65, b1=250, b2=300, b3=400),
    "cs": Hang("zar", 1400, 2500, 3700, hossz=75, zaj=1.0, zarlat=45,
               hangero=0.7, b1=280, b2=340, b3=420),
    "dz": Hang("zar", 1600, 3200, 4600, hossz=60, zaj=0.7, zarlat=40, hangero=0.65),
    "dzs": Hang("zar", 1300, 2400, 3500, hossz=65, zaj=0.7, zarlat=40, hangero=0.7),
    # --- nazálisok, folyékonyak ---
    "m":  Hang("nazalis", 280, 1100, 2200, hossz=80, hangero=0.6, b1=120, b2=180),
    "n":  Hang("nazalis", 280, 1600, 2600, hossz=75, hangero=0.6, b1=120, b2=180),
    "ny": Hang("nazalis", 280, 1900, 2800, hossz=80, hangero=0.6, b1=120, b2=180),
    "l":  Hang("oldalso", 380, 1300, 2700, hossz=70, hangero=0.75),
    "j":  Hang("oldalso", 300, 2200, 2900, hossz=60, hangero=0.7),
    "ly": Hang("oldalso", 300, 2200, 2900, hossz=60, hangero=0.7),
    "r":  Hang("perges", 480, 1350, 2500, hossz=70, hangero=0.75),
    " ":  Hang("szunet", hossz=110, hangero=0.0),
    ".":  Hang("szunet", hossz=260, hangero=0.0),
    ",":  Hang("szunet", hossz=160, hangero=0.0),
    "!":  Hang("szunet", hossz=260, hangero=0.0),
    "?":  Hang("szunet", hossz=260, hangero=0.0),
}

# A többjegyű betűk – MINDIG a leghosszabbat próbáljuk először
JEGYEK = ("dzs", "cs", "dz", "gy", "ly", "ny", "sz", "ty", "zs")


def szoveg_hangokra(szoveg: str) -> list[tuple[str, float]]:
    """MAGYAR BETŰ→HANG átalakítás. Visszaad: [(hang, hossz-szorzó), …].

    A magyar írás majdnem fonetikus, ezért ez megbízható: kezeli a többjegyű
    betűket (cs, sz, gy, ny, ty, zs, ly, dz, dzs) és a KETTŐZÖTT mássalhangzót
    (hosszú hang), ami a magyarban jelentésmegkülönböztető."""
    t = (szoveg or "").lower()
    ki: list[tuple[str, float]] = []
    i = 0
    while i < len(t):
        # kettőzött többjegyű betű: ssz → sz hosszan, ggy → gy hosszan …
        talalt = None
        for j in JEGYEK:
            # „ssz” alak: az első betű megismételve
            if t.startswith(j[0] + j, i):
                talalt = (j, 1.9, len(j) + 1)
                break
            if t.startswith(j, i):
                talalt = (j, 1.0, len(j))
                break
        if talalt:
            h, szorzo, n = talalt
            ki.append((h, szorzo))
            i += n
            continue
        c = t[i]
        # kettőzött egyjegyű mássalhangzó → hosszú
        if (c not in MGH and c in TABLA and i + 1 < len(t) and t[i + 1] == c):
            ki.append((c, 1.9))
            i += 2
            continue
        if c in TABLA:
            ki.append((c, 1.0))
        elif c.isdigit():
            for sz in _szam_szoveg(c):
                ki.extend(szoveg_hangokra(sz))
        elif not c.isspace():
            pass                       # ismeretlen jelet kihagyunk
        else:
            ki.append((" ", 1.0))
        i += 1
    return ki


_SZAMJEGY = {"0": "nulla", "1": "egy", "2": "kettő", "3": "három",
             "4": "négy", "5": "öt", "6": "hat", "7": "hét", "8": "nyolc",
             "9": "kilenc"}


def _szam_szoveg(c: str):
    return [_SZAMJEGY.get(c, "")]


# ------------------------------------------------------------ szintézis

@dataclass(frozen=True)
class RetroGep:
    """Egy „beszélő gép" karaktere."""
    kulcs: str
    nev: str
    fs: int = 11025
    alaphang: float = 122.0     # a zönge alapfrekvenciája (Hz)
    hangsuly: float = 0.16      # hangsúly-emelés mértéke (0 = teljesen monoton)
    tempo: float = 1.0          # időtartam-szorzó (nagyobb = lassabb)
    atmenet_ms: int = 12        # a hangok KÖZTI átcsúszás – kicsi = darabos!
    sav_szuk: float = 1.0       # sávszélesség-szorzó (kisebb = csengőbb)
    kvant_hz: int = 0           # formáns-kvantálás lépcsője (0 = nincs)
    bitek: int = 0              # kimeneti bit-kvantálás (0 = nincs)


GEPEK: tuple[RetroGep, ...] = (
    RetroGep("gep", "Beszélő gép (saját szintetizátor)",
             alaphang=122.0, hangsuly=0.16, tempo=1.0,
             atmenet_ms=12, sav_szuk=0.85, kvant_hz=60, bitek=9),
    RetroGep("gep_darabos", "Beszélő gép – NAGYON darabos",
             alaphang=116.0, hangsuly=0.12, tempo=1.08,
             atmenet_ms=4, sav_szuk=0.7, kvant_hz=120, bitek=7),
    RetroGep("gep_melv", "Beszélő gép – mély",
             alaphang=92.0, hangsuly=0.14, tempo=1.05,
             atmenet_ms=10, sav_szuk=0.8, kvant_hz=80, bitek=8),
    RetroGep("gep_magas", "Beszélő gép – magas, csipogós",
             alaphang=158.0, hangsuly=0.18, tempo=0.96,
             atmenet_ms=8, sav_szuk=0.75, kvant_hz=80, bitek=8),
)
GEP_MAP = {g.kulcs: g for g in GEPEK}
ALAP_GEP = GEPEK[0].kulcs


def gep(kulcs: str) -> RetroGep:
    return GEP_MAP.get(kulcs or "", GEPEK[0])


def _rezonator(x, f: float, bw: float, fs: int):
    """Klatt-féle kétpólusú rezonátor – EGY formáns. A formánsszintézis
    alapköve: a gerjesztést ezeken vezetjük át egymás után."""
    import numpy as np
    T = 1.0 / fs
    c = -math.exp(-2 * math.pi * bw * T)
    b = 2 * math.exp(-math.pi * bw * T) * math.cos(2 * math.pi * f * T)
    a = 1.0 - b - c
    y = np.empty_like(x)
    y1 = y2 = 0.0
    for i in range(x.shape[0]):
        yi = a * x[i] + b * y1 + c * y2
        y[i] = yi
        y2, y1 = y1, yi
    return y


def _kvant(ertek: float, lepcso: int) -> float:
    """Formáns-kvantálás: a korabeli chipek DURVA táblákból dolgoztak."""
    if lepcso <= 0:
        return ertek
    return round(ertek / lepcso) * lepcso


def szintetizal(szoveg: str, g: RetroGep):
    """A szöveg megszólaltatása SAJÁT formánsszintézissel.
    Visszaad: (minta-tömb float −1..1, mintavétel)."""
    import numpy as np
    hangok = szoveg_hangokra(szoveg)
    if not hangok:
        return np.zeros(0), g.fs
    fs = g.fs

    # --- 1) idővonal: minden hangzó a SAJÁT hosszán, hangsúllyal ---
    szakaszok = []          # (Hang, minta-szám)
    elso_mgh = True
    for nev, szorzo in hangok:
        h = TABLA.get(nev)
        if h is None:
            continue
        ms = h.hossz * szorzo * g.tempo
        if h.zarlat:
            szakaszok.append((TABLA[" "], int(fs * h.zarlat * g.tempo / 1000)))
        # a szó ELSŐ magánhangzója kicsit hosszabb (magyar hangsúly az 1. szótagon)
        if h.tipus == "mgh":
            if elso_mgh:
                ms *= 1.12
                elso_mgh = False
        elif h.tipus == "szunet":
            elso_mgh = True
        szakaszok.append((h, max(1, int(fs * ms / 1000))))

    ossz = sum(n for _, n in szakaszok)
    if ossz <= 0:
        return np.zeros(0), fs

    # --- 2) paraméter-pályák: LÉPCSŐSEN, rövid átmenetekkel ---
    # EZ a lényeg: a formánsok a hangzón BELÜL állnak, és csak egy nagyon
    # rövid szakaszon csúsznak át a következőbe → hallható „darálás".
    F1 = np.zeros(ossz); F2 = np.zeros(ossz); F3 = np.zeros(ossz)
    B1 = np.zeros(ossz); B2 = np.zeros(ossz); B3 = np.zeros(ossz)
    AMP = np.zeros(ossz); ZAJ = np.zeros(ossz); ZONGE = np.zeros(ossz)

    poz = 0
    for h, n in szakaszok:
        v = slice(poz, poz + n)
        F1[v] = _kvant(h.f1, g.kvant_hz)
        F2[v] = _kvant(h.f2, g.kvant_hz)
        F3[v] = _kvant(h.f3, g.kvant_hz)
        B1[v] = h.b1 * g.sav_szuk
        B2[v] = h.b2 * g.sav_szuk
        B3[v] = h.b3 * g.sav_szuk
        AMP[v] = h.hangero
        ZAJ[v] = h.zaj
        ZONGE[v] = 0.0 if h.tipus in ("zongetlen", "szunet") else 1.0
        if h.tipus == "perges":          # „r": gyors amplitúdó-pergetés
            t = np.arange(n) / fs
            AMP[v] = h.hangero * (0.55 + 0.45 * np.sign(
                np.sin(2 * math.pi * 26.0 * t)))
        poz += n

    # rövid átcsúsztatás a határokon (atmenet_ms) – kicsi érték = darabos
    at = max(1, int(fs * g.atmenet_ms / 1000))
    if at > 1:
        k = np.ones(at) / at
        for arr in (F1, F2, F3, B1, B2, B3, AMP):
            arr[:] = np.convolve(arr, k, mode="same")

    # --- 3) gerjesztés: zöngés impulzussor + zaj ---
    rng = np.random.default_rng(4242)
    t = np.arange(ossz) / fs
    # enyhe hangsúly-ingadozás (a felhasználó kérte: legyen egy kis élet)
    f0 = g.alaphang * (1.0 + g.hangsuly * 0.5 *
                       np.sin(2 * math.pi * 0.7 * t))
    fazis = np.cumsum(f0) / fs
    egesz = np.floor(fazis).astype(np.int64)
    imp = np.zeros(ossz)
    valt = np.empty(ossz, dtype=bool)
    valt[0] = True
    valt[1:] = egesz[1:] != egesz[:-1]
    imp[valt] = 1.0
    zaj = rng.standard_normal(ossz) * 0.5
    gerj = ZONGE * imp * (1.0 - ZAJ) + zaj * np.maximum(ZAJ, 1.0 - ZONGE)

    # --- 4) formáns-lánc ---
    # A pályák szakaszonként állandók, ezért szakaszonként futtatjuk a
    # rezonátorokat – így gyors marad, és a „lépcsőzés" megmarad.
    ki = np.zeros(ossz)
    lep = max(1, int(fs * 0.005))        # 5 ms-os felbontás a paramétereknél
    for kezd in range(0, ossz, lep):
        veg = min(ossz, kezd + lep)
        s = gerj[kezd:veg]
        if not np.any(s):
            continue
        y = _rezonator(s, max(150.0, F1[kezd]), max(40.0, B1[kezd]), fs)
        y = _rezonator(y, max(300.0, F2[kezd]), max(50.0, B2[kezd]), fs)
        y = _rezonator(y, max(500.0, F3[kezd]), max(60.0, B3[kezd]), fs)
        ki[kezd:veg] = y

    # --- 4b) SUGÁRZÁSI KARAKTERISZTIKA ---
    # A valódi hangképzésben a száj nyílása differenciálóként viselkedik
    # (+6 dB/oktáv). Enélkül a rezonátor-lánc „megeszi" a felsőbb formánsokat:
    # az F2/F3 eltűnne, és a magánhangzók megkülönböztethetetlenné válnának
    # (az F2 hordozza a magánhangzó azonosságát).
    ki = np.concatenate(([ki[0]], np.diff(ki)))

    ki *= AMP
    if g.bitek:
        lepcsok = float(2 ** (g.bitek - 1))
        ki = np.round(ki * lepcsok) / lepcsok
    csucs = float(np.max(np.abs(ki))) if ki.size else 0.0
    if csucs > 0:
        ki = ki / csucs * 0.9
    return ki, fs


def synth(szoveg: str, out_path: str = "", gep_kulcs: str = "") -> str:
    """A szöveg RETRÓ gépi hangon, WAV-fájlba. Visszaad: a fájl útja."""
    import os
    import tempfile
    import uuid
    import wave
    import numpy as np
    if not (szoveg or "").strip():
        raise ValueError("Nincs felolvasandó szöveg.")
    g = gep(gep_kulcs)
    x, fs = szintetizal(szoveg, g)
    out = out_path or os.path.join(
        tempfile.gettempdir(),
        f"superdl_gep_{os.getpid()}_{uuid.uuid4().hex[:8]}.wav")
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(pcm)
    return out
