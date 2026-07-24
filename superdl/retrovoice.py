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
    # ÉLESSÉG: e kettő nélkül a hang tompa, „rádióból szóló". A korabeli
    # formánsszintézis valójában szúrós, átütő karakterű volt.
    elohangsuly: float = 0.0   # elő-hangsúlyozás (0..0.9) – „harapós" felsők
    elesseg_hz: int = 0        # a jelenlét-csúcs helye (Hz)
    elesseg_db: float = 0.0    # a jelenlét-csúcs mértéke (dB)
    # VOKÓDER: a gerjesztés lecserélése saját impulzussorozatra. EZ adja a
    # valódi „chip-hangot" – enélkül az alapmotor karaktere átüt.
    vokoderes: bool = False
    savok: int = 12            # csatornák száma (kevesebb = gépiesebb)
    keret_ms: int = 24         # keret-hossz (nagyobb = darabosabb)
    alaphang: float = 118.0    # a zúgó impulzussorozat alapfrekvenciája (Hz)
    szint_kvantalas: bool = True
    szint_lepcso: int = 12     # sávszint-lépcsők (kevesebb = darabosabb)
    zaj_hatar_hz: int = 2600   # e felett ZAJ gerjeszt (sziszegők)


# A választható karakterek. Az elsőt tekintjük alapértelmezettnek.
PRESETS: tuple[RetroPreset, ...] = (
    # A HÁROM BEVÁLT karakter, ÉLESÍTVE: magasabb sávhatár, feljebb tolt
    # mélyvágás (kevesebb dobozosság), elő-hangsúlyozás és jelenlét-csúcs.
    RetroPreset("brailab", "Retró beszélő gép (a legjellegzetesebb)",
                variant="klatt2", freq=11025, also_hz=380, felso_hz=4600,
                bitek=8, tartas=1,
                sebesseg=145, hangmagassag=45, hangkozok=15,
                elohangsuly=0.38, elesseg_hz=3100, elesseg_db=5.5),
    RetroPreset("terminal", "Terminál (tiszta, éles, korhű)",
                variant="klatt4", freq=11025, also_hz=400, felso_hz=4800,
                bitek=10, tartas=1,
                sebesseg=155, hangmagassag=55, hangkozok=25,
                elohangsuly=0.42, elesseg_hz=3300, elesseg_db=6.5),
    RetroPreset("urhajo", "Űrhajó fedélzeti hang (mély, rekedtes)",
                variant="klatt3", freq=11025, also_hz=300, felso_hz=4200,
                bitek=8, tartas=1,
                sebesseg=130, hangmagassag=25, hangkozok=10,
                elohangsuly=0.28, elesseg_hz=2700, elesseg_db=4.5),
    # MÉG SZÚRÓSABB változatok – ha a fentiek sem elég élesek
    RetroPreset("brailab_eles", "Retró beszélő gép – NAGYON éles",
                variant="klatt2", freq=11025, also_hz=450, felso_hz=5000,
                bitek=8, tartas=1,
                sebesseg=145, hangmagassag=45, hangkozok=15,
                elohangsuly=0.62, elesseg_hz=3400, elesseg_db=8.5),
    RetroPreset("terminal_eles", "Terminál – NAGYON éles",
                variant="klatt4", freq=11025, also_hz=470, felso_hz=5000,
                bitek=10, tartas=1,
                sebesseg=155, hangmagassag=55, hangkozok=25,
                elohangsuly=0.66, elesseg_hz=3500, elesseg_db=9.5),
    # ===== VOKÓDERES karakterek: itt a GERJESZTÉS is a mienk =====
    # Ez már nem „megszűrt eSpeak", hanem újraszintetizált beszéd: a
    # burkológörbéket megtartjuk, a hangforrást saját impulzussorozatra
    # cseréljük. Ettől lesz igazi 80-as évekbeli beszélő gép hangja.
    RetroPreset("chip", "BESZÉLŐ CHIP (igazi retró, ajánlott)",
                variant="klatt2", freq=11025, also_hz=200, felso_hz=4600,
                bitek=8, tartas=1,
                sebesseg=145, hangmagassag=45, hangkozok=15,
                elohangsuly=0.30, elesseg_hz=3100, elesseg_db=5.0,
                vokoderes=True, savok=14, keret_ms=22, alaphang=118.0,
                szint_lepcso=14, zaj_hatar_hz=2600),
    RetroPreset("chip_darabos", "BESZÉLŐ CHIP – darabosabb, gépiesebb",
                variant="klatt2", freq=11025, also_hz=200, felso_hz=4600,
                bitek=7, tartas=1,
                sebesseg=140, hangmagassag=45, hangkozok=10,
                elohangsuly=0.34, elesseg_hz=3200, elesseg_db=6.0,
                vokoderes=True, savok=10, keret_ms=32, alaphang=112.0,
                szint_lepcso=7, zaj_hatar_hz=2800),
    RetroPreset("chip_melv", "BESZÉLŐ CHIP – mély, öblös gép",
                variant="klatt3", freq=11025, also_hz=180, felso_hz=4200,
                bitek=8, tartas=1,
                sebesseg=132, hangmagassag=30, hangkozok=10,
                elohangsuly=0.26, elesseg_hz=2700, elesseg_db=4.5,
                vokoderes=True, savok=12, keret_ms=28, alaphang=88.0,
                szint_lepcso=10, zaj_hatar_hz=2600),
    # Az eredeti, TOMPÁBB 8 kHz-es változat – összehasonlításhoz megmarad
    RetroPreset("brailab_tompa", "Retró beszélő gép – tompa (a korábbi)",
                variant="klatt2", freq=8000, also_hz=300, felso_hz=3400,
                bitek=8, tartas=1,
                sebesseg=145, hangmagassag=45, hangkozok=15),
    RetroPreset("robot", "Kemény robot (durvább, gépiesebb)",
                variant="robosoft", freq=11025, also_hz=400, felso_hz=4400,
                bitek=6, tartas=2,
                sebesseg=140, hangmagassag=40, hangkozok=5,
                elohangsuly=0.45, elesseg_hz=3000, elesseg_db=6.0),
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


def _peaking(x, fs: int, fc: float, db: float, q: float = 1.0):
    """Csúcsos (peaking) EQ – a JELENLÉT-sáv kiemelése. Ez teszi a beszédet
    „szúróssá", átütővé: a formánsszintézis eredeti karaktere is ilyen éles
    volt, nem tompa. E nélkül a hang olyan, mintha rádióból szólna."""
    import math
    if not db or fc <= 0 or fc >= fs / 2:
        return x
    A = 10 ** (db / 40.0)
    w = 2 * math.pi * fc / fs
    cs, sn = math.cos(w), math.sin(w)
    al = sn / (2 * q)
    b0 = 1 + al * A
    b1 = -2 * cs
    b2 = 1 - al * A
    a0 = 1 + al / A
    a1 = -2 * cs
    a2 = 1 - al / A
    return _biquad(x, b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def _elohangsuly(x, k: float):
    """Elő-hangsúlyozás (pre-emphasis): y[n] = x[n] − k·x[n−1].
    A magasakat emeli, a mélyeket visszafogja – ettől lesz a hang „harapós",
    és eltűnik belőle a dobozos, tompa jelleg."""
    import numpy as np
    if k <= 0 or x.size < 2:
        return x
    y = np.empty_like(x)
    y[0] = x[0]
    y[1:] = x[1:] - k * x[:-1]
    return y


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


def _impulzus_sor(n: int, fs: int, f0: float):
    """Szabályos IMPULZUSSOROZAT – ez a korabeli beszélő chipek gerjesztése.
    Nem emberi hangszalag: egy zúgó, tökéletesen periodikus jel. Ettől lesz a
    hang félreismerhetetlenül „gépi"."""
    import numpy as np
    if n <= 0 or f0 <= 0:
        return np.zeros(max(0, n))
    fazis = np.arange(n) * (f0 / fs)
    egesz = np.floor(fazis).astype(np.int64)
    x = np.zeros(n)
    valt = np.empty(n, dtype=bool)
    valt[0] = True
    valt[1:] = egesz[1:] != egesz[:-1]
    x[valt] = 1.0
    return x - x.mean()          # egyenáram-mentesítés


def _sav_hatarok(savok: int, also: float, felso: float):
    """Logaritmikusan elosztott sávhatárok (a hallás így érzékel)."""
    import numpy as np
    return np.geomspace(max(60.0, also), felso, savok + 1)


def vokoder(x, fs: int, p: RetroPreset):
    """CSATORNA-VOKÓDER: a beszéd BURKOLÓGÖRBÉIT tartjuk meg, a gerjesztést
    SAJÁT impulzussorozatra cseréljük.

    EZ a lényegi különbség: az utófeldolgozás (szűrés, kvantálás) nem tünteti
    el az alapmotor karakterét, mert a gerjesztés végig az övé marad. Itt
    viszont a hangszalag-jelet ELDOBJUK, és egy nyers, periodikus
    impulzussorozattal helyettesítjük – pontosan úgy, ahogy a 80-as évek
    beszélő chipjei csinálták. A sávonkénti szinteket DURVÁN kvantáljuk, és
    keretenként LÉPCSŐSEN tartjuk → ettől lesz „darabos"."""
    import numpy as np
    x = np.asarray(x, dtype=np.float64)
    if x.size < 64:
        return x

    # keretméret a kért keret-hosszból (2 hatványa, hogy az FFT gyors legyen)
    n_kert = max(64, int(fs * p.keret_ms / 1000.0))
    N = 1 << int(np.ceil(np.log2(n_kert)))
    hop = N // 2
    ablak = np.hanning(N + 1)[:N]

    # a gerjesztés: zöngés impulzussorozat + zöngétlen zaj (a sziszegőkhöz)
    zonges = _impulzus_sor(x.size + N, fs, p.alaphang)
    rng = np.random.default_rng(12345)
    zaj = rng.standard_normal(x.size + N)

    frekv = np.fft.rfftfreq(N, 1.0 / fs)
    hatarok = _sav_hatarok(p.savok, p.also_hz or 120, min(p.felso_hz or fs / 2,
                                                          fs / 2 - 1))
    # melyik FFT-rekesz melyik sávba tartozik
    sav_idx = [np.where((frekv >= hatarok[i]) & (frekv < hatarok[i + 1]))[0]
               for i in range(p.savok)]

    ki = np.zeros(x.size + N)
    sulyok = np.zeros(x.size + N)
    lepcsok = max(2, int(p.szint_lepcso))

    for kezd in range(0, x.size, hop):
        keret = np.zeros(N)
        db = min(N, x.size - kezd)
        keret[:db] = x[kezd:kezd + db]
        X = np.fft.rfft(keret * ablak)

        gerj = np.zeros(N)
        gerj_z = np.zeros(N)
        gerj[:N] = zonges[kezd:kezd + N]
        gerj_z[:N] = zaj[kezd:kezd + N]
        E = np.fft.rfft(gerj * ablak)
        Ez = np.fft.rfft(gerj_z * ablak)

        Y = np.zeros_like(X)
        for i, idx in enumerate(sav_idx):
            if idx.size == 0:
                continue
            # a sáv SZINTJE a beszédben
            szint = float(np.sqrt(np.mean(np.abs(X[idx]) ** 2)))
            # DURVA kvantálás → lépcsős, „darabos" átmenetek
            if p.szint_kvantalas:
                szint = round(szint * lepcsok) / lepcsok
            if szint <= 0:
                continue
            # a felső sávokat ZAJ gerjeszti (sziszegők), az alsókat impulzus
            forras = Ez if hatarok[i] >= p.zaj_hatar_hz else E
            e = float(np.sqrt(np.mean(np.abs(forras[idx]) ** 2))) or 1e-9
            Y[idx] = forras[idx] * (szint / e)

        y = np.fft.irfft(Y, n=N) * ablak
        ki[kezd:kezd + N] += y
        sulyok[kezd:kezd + N] += ablak ** 2

    sulyok[sulyok < 1e-6] = 1.0
    ki = (ki / sulyok)[:x.size]
    csucs = float(np.max(np.abs(ki))) if ki.size else 0.0
    if csucs > 0:
        ki = ki / csucs
    return ki


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
    # 2b) VOKÓDER: a gerjesztés lecserélése saját impulzussorozatra – ettől
    #     szűnik meg az alapmotor felismerhető karaktere, és lesz igazi
    #     „beszélő chip" hangzás
    if p.vokoderes:
        x = vokoder(x, p.freq, p)
    # 3) mély/dobozos rész levágása (a korabeli hangszórók sem adták vissza)
    if p.also_hz:
        x = _highpass(x, p.freq, p.also_hz)
    # 4) ÉLESSÉG: elő-hangsúlyozás + jelenlét-csúcs → a hang „szúróssá",
    #    átütővé válik, és eltűnik belőle a tompa, rádiós jelleg
    x = _elohangsuly(x, p.elohangsuly)
    if p.elesseg_db:
        x = _peaking(x, p.freq, p.elesseg_hz, p.elesseg_db, q=1.1)
    # 5) durva kvantálás + minta-tartás → a jellegzetes „gépi szemcse"
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

def synth(text: str, out_path: str = "", preset_kulcs: str = "",
          preset_obj=None) -> str:
    """A megadott szöveg RETRÓ hangon, WAV-fájlba. Visszaad: a fájl útja.

    `preset_obj` megadva közvetlenül azt a RetroPreset-et használja (a hívó
    testre szabhatja pl. a hangmagasságot/sebességet); különben a kulcs alapján
    választ. A hívó törölje a fájlt, ha már nincs rá szüksége (vagy használja a
    `speak()`-et, ami magától takarít)."""
    if not (text or "").strip():
        raise ValueError("Nincs felolvasandó szöveg.")
    p = preset_obj if preset_obj is not None else preset(preset_kulcs)
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
