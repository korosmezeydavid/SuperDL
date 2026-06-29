"""Super Recorder – vokál-effektek és 2-sávos keverés (It.4).

numpy-alapú DSP (a numpy a Core runtime-jából jön):
  * vocoder()      – IGAZI sávos vokóder STFT cross-synthesissel, BEÉPÍTETT
                     fűrész-vivőhanggal → klasszikus robot/szinti-énekhang;
  * harmonize()    – hangmagasság-eltolt másolatok (terc/kvint/oktáv) hozzákeverve;
  * remove_vocals()– ének eltávolítása dalból (közép-csatorna kioltás, sztereó);
  * mix_track()    – 2-sávos keverés (alap + ének), hangerő-egyensúllyal.

Mind 16 bites PCM-mel dolgozik (a szerkesztő `Clip`-jével kompatibilisen).
"""

import numpy as np

from . import superrec, supereffects


def _to_mono_float(pcm: bytes, channels: int):
    a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    if channels == 2:
        a = a.reshape(-1, 2).mean(axis=1)
    return a


def _float_to_pcm(mono: np.ndarray, channels: int) -> bytes:
    mono = np.clip(mono, -1.0, 1.0)
    i16 = (mono * 32767.0).astype(np.int16)
    if channels == 2:
        i16 = np.repeat(i16[:, None], 2, axis=1).reshape(-1)
    return i16.tobytes()


def vocoder(pcm: bytes, freq: int, channels: int, intensity: float = 1.0,
            carrier_hz: float = 110.0) -> bytes:
    """Sávos vokóder: a hang (modulátor) színezi a beépített fűrész-vivőhangot.
    `intensity` 0..1 a száraz/effektezett keverés. STFT cross-synthesis: a vivő
    FÁZISÁT tartjuk, a modulátor MAGNITÚDÓJÁVAL → klasszikus vokóder-hangzás."""
    x = _to_mono_float(pcm, channels)
    n = len(x)
    if n < 1024:
        return pcm
    t = np.arange(n) / freq
    carrier = 2.0 * ((t * carrier_hz) % 1.0) - 1.0      # fűrészjel (sok felharmonikus)

    win = 1024
    hop = 256
    window = np.hanning(win).astype(np.float32)
    out = np.zeros(n, dtype=np.float32)
    norm = np.zeros(n, dtype=np.float32)
    for s in range(0, n - win, hop):
        m = x[s:s + win] * window
        c = carrier[s:s + win] * window
        M = np.fft.rfft(m)
        C = np.fft.rfft(c)
        mag = np.abs(M)
        cph = C / (np.abs(C) + 1e-9)                     # vivő fázisa
        seg = np.fft.irfft(cph * mag, win).astype(np.float32) * window
        out[s:s + win] += seg
        norm[s:s + win] += window ** 2
    out /= (norm + 1e-6)
    peak = float(np.max(np.abs(out))) or 1.0
    wet = out / peak
    intensity = max(0.0, min(1.0, intensity))
    mixed = intensity * wet + (1.0 - intensity) * x
    return _float_to_pcm(mixed, channels)


def harmonize(pcm: bytes, freq: int, channels: int,
              intervals=(4, 7), mix: float = 0.6) -> bytes:
    """Harmonizer: a megadott félhang-intervallumokra (alap: terc=+4, kvint=+7)
    hangmagasság-eltolt másolatokat készít (a tempó-tartó pitch-lánccal), és az
    eredetihez keveri. `mix` a harmónia-hangok relatív hangereje."""
    base = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    acc = base.copy()
    for semi in intervals:
        af = supereffects._pitch(semi, freq)
        shifted = superrec.process_pcm(pcm, freq, channels, af)
        s = np.frombuffer(shifted, dtype=np.int16).astype(np.float32)
        k = min(len(acc), len(s))
        acc[:k] += mix * s[:k]
    peak = float(np.max(np.abs(acc))) or 1.0
    if peak > 32767.0:
        acc *= 32767.0 / peak                            # túlvezérlés ellen
    return acc.astype(np.int16).tobytes()


def remove_vocals(pcm: bytes, freq: int, channels: int) -> bytes:
    """Ének eltávolítása dalból: a sztereó KÖZÉP (általában az ének) kioltása az
    oldal-jel (L−R) képzésével, sztereóban visszaadva. Csak sztereóra van értelme."""
    if channels != 2:
        raise RuntimeError("Az ének eltávolítása sztereó hanghoz való "
                           "(a betöltött hang monó).")
    a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32).reshape(-1, 2)
    side = (a[:, 0] - a[:, 1]) * 0.5                      # közép kioltva
    st = np.repeat(side[:, None], 2, axis=1)
    return np.clip(st, -32768, 32767).astype(np.int16).tobytes()


def mix_track(pcm_a: bytes, pcm_b: bytes, channels: int,
              gain_a_db: float = 0.0, gain_b_db: float = 0.0) -> bytes:
    """Két sáv (A=jelenlegi, B=betöltött alap) keverése; a rövidebbet nullával
    a hosszabbra egészíti ki. A hangerők dB-ben adhatók meg."""
    a = np.frombuffer(pcm_a, dtype=np.int16).astype(np.float32)
    b = np.frombuffer(pcm_b, dtype=np.int16).astype(np.float32)
    n = max(len(a), len(b))
    n -= n % channels
    a = np.pad(a, (0, max(0, n - len(a))))[:n]
    b = np.pad(b, (0, max(0, n - len(b))))[:n]
    ga = 10.0 ** (gain_a_db / 20.0)
    gb = 10.0 ** (gain_b_db / 20.0)
    mix = a * ga + b * gb
    peak = float(np.max(np.abs(mix))) or 1.0
    if peak > 32767.0:
        mix *= 32767.0 / peak
    return mix.astype(np.int16).tobytes()
