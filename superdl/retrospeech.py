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
    elesseg: float = 0.0        # utólagos jelenlét-emelés (0..1) – szúrósabb
    hangero: float = 0.9        # a kimenet csúcs-szintje (0..1)
    szotag_hangsuly: float = 0.0  # a hangsúlyos szótag amplitúdó-emelése (0..0.6)
    debox: float = 0.0          # a „dobozos” alsó-közép (500 Hz) vágása, dB
    levego: float = 0.0         # felső „levegő” hozzáadása (magas polc), dB
    drive: float = 1.0          # tömörítés/telítés a HANGERŐHÖZ (1 = nincs)
    deklinacio: float = 0.0     # mondat-lejtés (a magyaros, ereszkedő dallam)
    motor: str = "sajat"        # "sajat" = ez a formánsmotor; "klatt" = eSpeak-Klatt
    klatt_preset: str = ""      # motor="klatt" esetén a retrovoice-preset kulcsa
    tompitas: float = 0.0       # motor="klatt": aluláteresztő vágás (Hz, 0 = nincs)
    klatt_pitch: int = 0        # motor="klatt": eSpeak hangmagasság 0..99 (0 = alap)


GEPEK: tuple[RetroGep, ...] = (
    # A NYERTES: mély beszélő gép, most élesebbre, hangosabbra hangolva, több
    # szótag-hangsúllyal (a fejlesztő választása és kérése).
    RetroGep("gep_melv", "Beszélő gép – MÉLY (a nyertes)",
             alaphang=94.0, hangsuly=0.22, tempo=1.04,
             atmenet_ms=10, sav_szuk=0.9, kvant_hz=80, bitek=8,
             elesseg=0.85, hangero=0.99, szotag_hangsuly=0.42,
             debox=7.0, levego=8.5, drive=7.5, deklinacio=0.24),
    RetroGep("gep_melv_extra", "Beszélő gép – MÉLY, még élesebb",
             alaphang=92.0, hangsuly=0.26, tempo=1.05,
             atmenet_ms=9, sav_szuk=0.8, kvant_hz=90, bitek=8,
             elesseg=1.0, hangero=0.99, szotag_hangsuly=0.46,
             debox=7.5, levego=10.0, drive=9.0, deklinacio=0.26),
    # BraiLab-STÍLUS – a klasszikus magyar beszélő gép hangulata, a Philips
    # MEA8000 formáns-chip AKUSZTIKAI jellemzői alapján ÚJRAALKOTVA (saját
    # numpy-szintézis). NEM az eredeti ROM és NEM emulátor – jogtiszta.
    # Jellemzők: tisztább/magasabb alaphang, csengő formánsok (szűk sáv),
    # durvább kvantálás – ettől lesz „chippes”, mégis érthető.
    RetroGep("brailab", "BraiLab-stílus (saját újraalkotás)",
             alaphang=108.0, hangsuly=0.20, tempo=1.02,
             atmenet_ms=8, sav_szuk=0.80, kvant_hz=100, bitek=8,
             elesseg=0.80, hangero=0.99, szotag_hangsuly=0.38,
             debox=6.0, levego=9.0, drive=5.0, deklinacio=0.22),
    # A régi, eSpeak-Klatt alapú BraiLab (retrovoice motor), kicsit tompítva –
    # a fejlesztő külön kérésére, „hátha valakinek az kell". eSpeak kell hozzá,
    # ami a SuperDL-be be van építve.
    RetroGep("brailab_klatt", "BraiLab – eSpeak-Klatt (tompított)",
             motor="klatt", klatt_preset="brailab", tompitas=2800.0,
             klatt_pitch=28, hangero=0.97),
    RetroGep("gep", "Beszélő gép (közepes)",
             alaphang=122.0, hangsuly=0.18, tempo=1.0,
             atmenet_ms=12, sav_szuk=0.9, kvant_hz=60, bitek=9,
             elesseg=0.55, hangero=0.97, szotag_hangsuly=0.32,
             debox=5.0, levego=6.0, drive=2.4, deklinacio=0.20),
    RetroGep("gep_darabos", "Beszélő gép – NAGYON darabos",
             alaphang=116.0, hangsuly=0.14, tempo=1.08,
             atmenet_ms=4, sav_szuk=0.72, kvant_hz=120, bitek=7,
             elesseg=0.6, hangero=0.97, szotag_hangsuly=0.32,
             debox=6.0, levego=7.0, drive=3.0, deklinacio=0.20),
    RetroGep("gep_magas", "Beszélő gép – magas, csipogós",
             alaphang=158.0, hangsuly=0.20, tempo=0.96,
             atmenet_ms=8, sav_szuk=0.78, kvant_hz=80, bitek=8,
             elesseg=0.6, hangero=0.97, szotag_hangsuly=0.32,
             debox=4.5, levego=6.0, drive=2.4, deklinacio=0.22),
)
GEP_MAP = {g.kulcs: g for g in GEPEK}
ALAP_GEP = GEPEK[0].kulcs


def gep(kulcs: str) -> RetroGep:
    return GEP_MAP.get(kulcs or "", GEPEK[0])


def _rezonator(x, F, B, fs: int, lep: int):
    """Klatt-féle kétpólusú rezonátor – EGY formáns, IDŐBEN VÁLTOZÓ
    paraméterekkel.

    KRITIKUS: a szűrő ÁLLAPOTA (y1, y2) végig FOLYAMATOS. A rezonátornak
    „csengenie" kell két zöngeimpulzus között – ha az állapotot blokkonként
    lenulláznánk, a hang szétesne néma töredékekre (a gerjesztő impulzusok
    ~90 mintánként jönnek, a paraméter-blokkok viszont rövidebbek). Ezért a
    paramétereket blokkonként frissítjük, de az állapotot NEM."""
    import numpy as np
    T = 1.0 / fs
    n = x.shape[0]
    y = np.empty(n)
    y1 = y2 = 0.0
    for kezd in range(0, n, lep):
        veg = min(n, kezd + lep)
        f = max(150.0, float(F[kezd]))
        bw = max(40.0, float(B[kezd]))
        c = -math.exp(-2 * math.pi * bw * T)
        b = 2 * math.exp(-math.pi * bw * T) * math.cos(2 * math.pi * f * T)
        # A CSÚCSRA normálunk, nem nulla frekvenciára. A régi `a = 1-b-c`
        # egységnyi erősítést ad DC-n, de magas középfrekvencián a rezonancia-
        # csúcs erősítése óriási: emiatt a magas formánsú réshangok („sz", „s")
        # 40-50-szer hangosabbak lettek a magánhangzóknál – a beszédből csak
        # sziszegés maradt.
        w0 = 2 * math.pi * f * T
        nev = complex(1.0, 0.0) - b * complex(math.cos(w0), -math.sin(w0)) \
            - c * complex(math.cos(2 * w0), -math.sin(2 * w0))
        a = abs(nev)
        for i in range(kezd, veg):
            yi = a * x[i] + b * y1 + c * y2
            y[i] = yi
            y2, y1 = y1, yi
    return y


def _biquad_run(x, b0, b1, b2, a1, a2):
    """Egy általános másodfokú szűrő (a stílus-EQ-khoz)."""
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


def _peaking_eq(x, fs, fc, db, q=1.0):
    """Csúcsos EQ – emel (db>0) vagy vág (db<0) egy frekvencia körül."""
    if not db:
        return x
    A = 10 ** (db / 40.0)
    w = 2 * math.pi * fc / fs
    cs, sn = math.cos(w), math.sin(w)
    al = sn / (2 * q)
    a0 = 1 + al / A
    return _biquad_run(x, (1 + al * A) / a0, (-2 * cs) / a0, (1 - al * A) / a0,
                       (-2 * cs) / a0, (1 - al / A) / a0)


def _high_shelf(x, fs, fc, db):
    """Magas polc – a `fc` fölötti sáv egészét emeli/csökkenti (levegő)."""
    if not db:
        return x
    A = 10 ** (db / 40.0)
    w = 2 * math.pi * fc / fs
    cs, sn = math.cos(w), math.sin(w)
    al = sn / 2 * math.sqrt((A + 1 / A) * (1 / 0.9 - 1) + 2)
    sq = 2 * math.sqrt(A) * al
    a0 = (A + 1) - (A - 1) * cs + sq
    b0 = A * ((A + 1) + (A - 1) * cs + sq)
    b1 = -2 * A * ((A - 1) + (A + 1) * cs)
    b2 = A * ((A + 1) + (A - 1) * cs - sq)
    a1 = 2 * ((A - 1) - (A + 1) * cs)
    a2 = (A + 1) - (A - 1) * cs - sq
    return _biquad_run(x, b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def _kvant(ertek: float, lepcso: int) -> float:
    """Formáns-kvantálás: a korabeli chipek DURVA táblákból dolgoztak."""
    if lepcso <= 0:
        return ertek
    return round(ertek / lepcso) * lepcso


def _retrovoice():
    """A retró eSpeak-Klatt motor betöltése (a SuperDL Core-ból)."""
    from superdl import retrovoice as RV
    return RV


def _klatt_szintezis(szoveg: str, g: RetroGep):
    """A „BraiLab – eSpeak-Klatt" hang: a régi retrovoice (eSpeak Klatt +
    numpy-DSP) adja az alapot, amit itt még kicsit TOMPÍTUNK (aluláteresztő),
    ahogy a fejlesztő kérte. Ehhez eSpeak kell – a SuperDL-ben be van építve.

    A hangmagasságot a `klatt_pitch` (eSpeak pitch 0..99) adja – így NEM
    magas/idegesítő. A tempót az eSpeak SEBESSÉGÉVEL állítjuk (nem
    újramintavételezéssel), ezért a tempó NEM tolja el a hangmagasságot."""
    import dataclasses
    import os
    import numpy as np
    RV = _retrovoice()
    alap = RV.preset(g.klatt_preset or "brailab")
    valt = {}
    if g.klatt_pitch:
        valt["hangmagassag"] = max(0, min(99, int(g.klatt_pitch)))
    if g.tempo and abs(g.tempo - 1.0) > 1e-3:
        valt["sebesseg"] = int(max(80, min(400, round(alap.sebesseg / g.tempo))))
    p = dataclasses.replace(alap, **valt) if valt else alap
    path = RV.synth(szoveg, "", preset_obj=p)
    try:
        x, fs = RV._wav_be(path)
    finally:
        try:
            os.remove(path)
        except Exception:
            pass
    x = np.asarray(x, dtype=float)
    if g.tompitas and g.tompitas > 0 and x.size:
        x = RV._lowpass(x, fs, float(g.tompitas))
    csucs = float(np.max(np.abs(x))) if x.size else 0.0
    if csucs > 0:
        x = x / csucs * min(0.98, g.hangero)
    return x, fs


def szintetizal(szoveg: str, g: RetroGep):
    """A szöveg megszólaltatása. Alapból a SAJÁT formánsmotorral; a
    motor="klatt" hangoknál a retró eSpeak-Klatt motorral (lásd fent).
    Visszaad: (minta-tömb float −1..1, mintavétel)."""
    import numpy as np
    if g.motor == "klatt":
        return _klatt_szintezis(szoveg, g)
    hangok = szoveg_hangokra(szoveg)
    if not hangok:
        return np.zeros(0), g.fs
    fs = g.fs

    # --- 1) idővonal: minden hangzó a SAJÁT hosszán, hangsúllyal ---
    # A magyar hangsúly a szó ELSŐ szótagján van: azt kicsit hosszabbra ÉS
    # hangosabbra vesszük. A `szotag_hangsuly` szabályozza, mennyire.
    szakaszok = []          # (Hang, minta-szám, hangsúlyos-e)
    mondat_id = []          # szakaszonként: hányadik MONDATBAN van (deklinációhoz)
    mid = 0
    elso_mgh = True
    for nev, szorzo in hangok:
        h = TABLA.get(nev)
        if h is None:
            continue
        ms = h.hossz * szorzo * g.tempo
        hangsulyos = False
        if h.zarlat:
            szakaszok.append((TABLA[" "], int(fs * h.zarlat * g.tempo / 1000),
                              False))
            mondat_id.append(mid)
        if h.tipus == "mgh":
            if elso_mgh:                     # a SZÓ első magánhangzója = hangsúlyos
                ms *= 1.14
                hangsulyos = True
                elso_mgh = False
        elif h.tipus == "szunet":
            elso_mgh = True
        szakaszok.append((h, max(1, int(fs * ms / 1000)), hangsulyos))
        mondat_id.append(mid)
        if nev in ".!?":                     # a mondat vége → új mondat kezdődik
            mid += 1

    ossz = sum(n for _, n, _ in szakaszok)
    if ossz <= 0:
        return np.zeros(0), fs

    # --- 2) paraméter-pályák: LÉPCSŐSEN, rövid átmenetekkel ---
    # EZ a lényeg: a formánsok a hangzón BELÜL állnak, és csak egy nagyon
    # rövid szakaszon csúsznak át a következőbe → hallható „darálás".
    F1 = np.zeros(ossz); F2 = np.zeros(ossz); F3 = np.zeros(ossz)
    B1 = np.zeros(ossz); B2 = np.zeros(ossz); B3 = np.zeros(ossz)
    AMP = np.zeros(ossz); ZAJ = np.zeros(ossz); ZONGE = np.zeros(ossz)

    # MONDAT-DEKLINÁCIÓ: a magyar (és a legtöbb nyelv) mondatdallama ereszkedő –
    # a hangmagasság a mondat elején magasabb, a végére leereszkedik. Enélkül a
    # gépi hang egyhangú; ettől lesz „magyarosabb". Mondatonként újraindul.
    hatarok = {}
    poz = 0
    for (_, n, _), m in zip(szakaszok, mondat_id):
        hatarok.setdefault(m, [poz, poz])
        hatarok[m][1] = poz + n
        poz += n
    DEKL = np.ones(ossz)
    if g.deklinacio:
        for kezd, veg in hatarok.values():
            if veg > kezd:
                DEKL[kezd:veg] = np.linspace(1.0 + g.deklinacio * 0.5,
                                             1.0 - g.deklinacio * 0.5, veg - kezd)

    poz = 0
    HSULY = np.ones(ossz)      # hangsúly-szorzó a hangmagassághoz
    for h, n, hangsulyos in szakaszok:
        v = slice(poz, poz + n)
        F1[v] = _kvant(h.f1, g.kvant_hz)
        F2[v] = _kvant(h.f2, g.kvant_hz)
        F3[v] = _kvant(h.f3, g.kvant_hz)
        B1[v] = h.b1 * g.sav_szuk
        B2[v] = h.b2 * g.sav_szuk
        B3[v] = h.b3 * g.sav_szuk
        amp = h.hangero
        if hangsulyos and g.szotag_hangsuly:
            amp *= 1.0 + g.szotag_hangsuly            # hangosabb szótag
            HSULY[v] = 1.0 + g.szotag_hangsuly * 0.35  # + kicsit magasabb hang
        AMP[v] = amp
        ZAJ[v] = h.zaj
        ZONGE[v] = 0.0 if h.tipus in ("zongetlen", "szunet") else 1.0
        if h.tipus == "perges":          # „r": gyors amplitúdó-pergetés
            t = np.arange(n) / fs
            # SZINUSZOS pergetés (nem négyszög): a np.sign kemény élei kattantak
            AMP[v] = amp * (0.6 + 0.4 * np.sin(2 * math.pi * 26.0 * t))
        poz += n

    # rövid átcsúsztatás a határokon (atmenet_ms) – kicsi érték = darabos
    at = max(1, int(fs * g.atmenet_ms / 1000))
    if at > 1:
        k = np.ones(at) / at
        for arr in (F1, F2, F3, B1, B2, B3, AMP):
            arr[:] = np.convolve(arr, k, mode="same")
    # A ZÖNGE/ZAJ kapuját KÜLÖN, kicsit hosszabban (~8 ms) simítjuk: a zöngés↔
    # zöngétlen és a zaj be/ki KEMÉNY lépcsője kattant minden fonéma-határon
    # („ahogy formálja a szavakat"). A formáns-lépcsőt (retró karakter) nem
    # bántjuk – csak a gerjesztés kapuját lágyítjuk, így megszűnik a kattogás.
    atz = max(at, int(fs * 0.008))
    if atz > 1:
        kz = np.ones(atz) / atz
        ZONGE[:] = np.convolve(ZONGE, kz, mode="same")
        ZAJ[:] = np.convolve(ZAJ, kz, mode="same")

    # --- 3) gerjesztés: zöngés impulzussor + zaj ---
    rng = np.random.default_rng(4242)
    t = np.arange(ossz) / fs
    # enyhe hangsúly-ingadozás (a felhasználó kérte: legyen egy kis élet)
    # a hangmagasság: enyhe alap-ingadozás + a HANGSÚLYOS szótagok kiemelése
    at = max(1, int(fs * g.atmenet_ms / 1000))
    HSULY = np.convolve(HSULY, np.ones(at) / at, mode="same")
    f0 = g.alaphang * HSULY * DEKL * (1.0 + g.hangsuly * 0.5 *
                                      np.sin(2 * math.pi * 0.7 * t))
    fazis = np.cumsum(f0) / fs
    egesz = np.floor(fazis).astype(np.int64)
    imp = np.zeros(ossz)
    valt = np.empty(ossz, dtype=bool)
    valt[0] = True
    valt[1:] = egesz[1:] != egesz[:-1]
    imp[valt] = 1.0
    # GLOTTISZ-GERJESZTÉS: az egymintás impulzus túl kevés energiát hordoz
    # (90 mintánként egy tüske → RMS ~0,1), ezért a zaj elnyomná a zöngét, és a
    # beszédből csak sziszegés maradna. A valódi hangszalag-jel szélesebb
    # impulzus: az impulzussort egy kétpólusú szűrőn vezetjük át, ami
    # glottisz-szerű alakot és rendes energiát ad neki.
    glott = _rezonator(imp, np.full(ossz, 240.0), np.full(ossz, 160.0),
                       fs, ossz)
    # MINDKÉT forrást egységnyi hangerőre hozzuk, hogy az arányuk a
    # hangzó-táblából (ZAJ) jöjjön, ne a véletlenből
    zaj = rng.standard_normal(ossz)
    e_g = float(np.sqrt(np.mean(glott ** 2))) or 1e-9
    e_z = float(np.sqrt(np.mean(zaj ** 2))) or 1e-9
    glott = glott / e_g
    # A zaj szintje MÉRÉSSEL beállítva: a sugárzási differenciálás (+6 dB/okt)
    # a magas formánsú réshangokat („sz", „s") jobban emeli, mint a mély
    # magánhangzókat, ezért a nyers arány 5-6-szoros lenne. 0,04-nél az „sz"
    # a magánhangzó ~0,4-szeresén szól – ez felel meg a valódi beszédnek.
    zaj = zaj / e_z * 0.04
    gerj = ZONGE * (1.0 - ZAJ) * glott + np.maximum(ZAJ, 1.0 - ZONGE) * zaj

    # --- 4) formáns-lánc ---
    # A pályák szakaszonként állandók, ezért szakaszonként futtatjuk a
    # rezonátorokat – így gyors marad, és a „lépcsőzés" megmarad.
    # A láncot EGYBEN futtatjuk (folyamatos szűrő-állapottal), a paramétereket
    # 5 ms-onként frissítve. Így a rezonátorok végig csengenek.
    lep = max(1, int(fs * 0.005))
    ki = _rezonator(gerj, F1, B1, fs, lep)
    ki = _rezonator(ki, F2, B2, fs, lep)
    ki = _rezonator(ki, F3, B3, fs, lep)

    # --- 4b) SUGÁRZÁSI KARAKTERISZTIKA ---
    # A valódi hangképzésben a száj nyílása differenciálóként viselkedik
    # (+6 dB/oktáv). Enélkül a rezonátor-lánc „megeszi" a felsőbb formánsokat:
    # az F2/F3 eltűnne, és a magánhangzók megkülönböztethetetlenné válnának
    # (az F2 hordozza a magánhangzó azonosságát).
    ki = np.concatenate(([ki[0]], np.diff(ki)))

    ki *= AMP
    # STÍLUS-EQ: a hangzás finomhangolása
    if g.debox:
        # a „dobozos" alsó-közép (500 Hz körüli torlódás) VÁGÁSA → nyitottabb
        ki = _peaking_eq(ki, fs, 500.0, -g.debox, q=1.1)
    if g.elesseg:
        # jelenlét-emelés → szúrósabb, „harapósabb"
        ki = _peaking_eq(ki, fs, 2800.0, 8.0 * g.elesseg, q=1.1)
    if g.levego:
        # magas polc → „levegő", eltűnik a tompa/dobozos jelleg
        ki = _high_shelf(ki, fs, 3600.0, g.levego)

    # HANGERŐ: tömörítés (soft-clip). A nyers hang crest-faktora nagy (a
    # pattanások hangosak, az átlag halk), ezért a puszta csúcs-normálás után
    # is HALKNAK hallik. A tanh-telítés felhozza az átlagot (RMS), és korhű
    # „meleg" torzítást ad – pontosan olyat, mint egy túlvezérelt kis hangszóró.
    if g.drive and g.drive > 1.0:
        csucs = float(np.max(np.abs(ki))) or 1e-9
        ki = np.tanh(ki / csucs * g.drive) * csucs

    # SORREND: előbb NORMALIZÁLUNK, csak utána kvantálunk. Fordítva a
    # kvantálás lenullázná a jelet.
    csucs = float(np.max(np.abs(ki))) if ki.size else 0.0
    if csucs > 0:
        ki = ki / csucs * min(0.98, g.hangero)
    if g.bitek:
        lepcsok = float(2 ** (g.bitek - 1))
        ki = np.round(ki * lepcsok) / lepcsok
    # KATTANÁS-MENTES INDÍTÁS/ZÁRÁS: rövid (~6 ms) fel-/leúsztatás a legelső és
    # legutolsó mintáknál, hogy a hang ne PATTANJON az elején/végén.
    nf = min(ki.size // 2, max(1, int(fs * 0.006)))
    if nf > 1:
        ramp = np.linspace(0.0, 1.0, nf)
        ki[:nf] *= ramp
        ki[-nf:] *= ramp[::-1]
    return ki, fs


def available() -> bool:
    """Elérhető-e a retró hang? A motor TELJESEN saját (numpy), így ez mindig
    igaz, ha a numpy betölthető."""
    try:
        import numpy            # noqa: F401
        return True
    except Exception:
        return False


def synth(szoveg: str, out_path: str = "", gep_kulcs: str = "",
          tempo_szorzo: float = 1.0) -> str:
    """A szöveg RETRÓ gépi hangon, WAV-fájlba. Visszaad: a fájl útja.

    `tempo_szorzo`: a beszéd időtartam-szorzója (1.0 = változatlan; >1 lassabb,
    <1 gyorsabb). A hangválasztó tempó-csúszkája adja."""
    import dataclasses
    import os
    import tempfile
    import uuid
    import wave
    import numpy as np
    if not (szoveg or "").strip():
        raise ValueError("Nincs felolvasandó szöveg.")
    g = gep(gep_kulcs)
    if tempo_szorzo and abs(tempo_szorzo - 1.0) > 1e-3:
        g = dataclasses.replace(g, tempo=g.tempo * float(tempo_szorzo))
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
