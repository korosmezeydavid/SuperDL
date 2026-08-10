# -*- coding: utf-8 -*-
"""Csevejcenter – TÉRBELI (sztereó) hang-motor.

A vak-first konferencia lelke: minden résztvevő a sztereó térben egy külön
„helyről” szól (bal–közép–jobb), így a hallgató a hang IRÁNYÁBÓL tudja, KI
beszél – ezt a Zoom/Teams nem adja. Csak a már beépített `numpy` és
`sounddevice` kell (nincs új függőség, nincs Core-újraépítés).

Rétegek:
  • `ulesek(nevek)`  – nevekhez pan-pozíciókat (-1..+1) rendel, egyenletesen.
  • `_pan(mono, p)`  – egyenlő-teljesítményű mono→sztereó panorámázás.
  • `Kevero`         – per-résztvevő jitter-puffer + kevert sztereó kimenet
                       (TISZTA, wx/eszköz nélkül tesztelhető).
  • `TerbeliHang`    – valós mikrofon-rögzítés + lejátszás (a hálózati átvitel
                       ezt táplálja majd); a kimenő mono kockákat callbackkel adja.
  • `bemutato_jel`   – egy „körbejáró” hang mintája (a térélmény bemutatásához,
                       hálózat nélkül is meghallgatható).

Beszédhez 16 kHz mono bőven elég (kis sávszél), 20 ms-os kockákkal.
"""
import collections
import threading

import numpy as np

FS = 16000              # mintavételi frekvencia (Hz) – beszédhez elég
BLOKK = 320             # 20 ms @ 16 kHz (egy hang-kocka mérete mintában)
_PUFFER_MAX = 25        # résztvevőnként max ennyi kocka a jitter-pufferben (~0,5 s)


def _pan(mono: np.ndarray, pan: float) -> np.ndarray:
    """Mono jel → sztereó, egyenlő-teljesítményű panorámázással. `pan` -1..+1
    (bal..jobb); a teljes teljesítmény állandó marad minden pozícióban."""
    ang = (float(np.clip(pan, -1.0, 1.0)) + 1.0) * 0.25 * np.pi
    bal = np.cos(ang)
    jobb = np.sin(ang)
    return np.column_stack((mono * bal, mono * jobb)).astype(np.float32)


def ulesek(nevek) -> dict:
    """Résztvevő-nevekhez pan-pozíciók (-1..+1), a névsor szerint egyenletesen
    szétosztva a sztereó térben. Egy résztvevőnél középre (0)."""
    nevek = sorted({n for n in nevek if n}, key=str.lower)
    n = len(nevek)
    if n == 0:
        return {}
    if n == 1:
        return {nevek[0]: 0.0}
    return {nev: -1.0 + 2.0 * i / (n - 1) for i, nev in enumerate(nevek)}


class Kevero:
    """Több résztvevő mono hang-kockáit panorámázva sztereóvá keveri.

    TISZTA logika: `add(nev, mono)` beteszi egy résztvevő kockáját a
    puffgerébe, `kimenet(n)` pedig legyárt `n` minta kevert sztereót (minden
    résztvevőből egy kockát kivéve, a helyére panorámázva, majd összegezve és
    a klippelést elkerülve). Eszköz és wx nélkül is tesztelhető."""

    def __init__(self):
        self._pufferek: dict = {}          # nev -> deque[np.ndarray mono]
        self._pan: dict = {}               # nev -> pan (-1..+1)
        self._lock = threading.Lock()

    def set_ulesek(self, pan_map: dict):
        with self._lock:
            self._pan = dict(pan_map or {})

    def add(self, nev: str, mono: np.ndarray):
        mono = np.asarray(mono, dtype=np.float32).reshape(-1)
        with self._lock:
            dq = self._pufferek.get(nev)
            if dq is None:
                dq = collections.deque(maxlen=_PUFFER_MAX)
                self._pufferek[nev] = dq
            dq.append(mono)

    def elenged(self, nev: str):
        with self._lock:
            self._pufferek.pop(nev, None)

    def kimenet(self, n: int = BLOKK) -> np.ndarray:
        """`n` mintányi kevert sztereó (float32, [-1,1] köré vágva)."""
        ki = np.zeros((n, 2), dtype=np.float32)
        with self._lock:
            for nev, dq in self._pufferek.items():
                if not dq:
                    continue
                mono = dq.popleft()
                if mono.shape[0] < n:
                    mono = np.pad(mono, (0, n - mono.shape[0]))
                elif mono.shape[0] > n:
                    mono = mono[:n]
                ki += _pan(mono, self._pan.get(nev, 0.0))
        # lágy klipp-védelem: ha túlcsordul, arányosan visszaskálázzuk
        cs = float(np.max(np.abs(ki))) if ki.size else 0.0
        if cs > 1.0:
            ki /= cs
        return ki


def _to_int16(f: np.ndarray) -> bytes:
    """float32 [-1,1] mono → PCM16 little-endian bájtok (hálózati küldéshez)."""
    f = np.clip(np.asarray(f, dtype=np.float32).reshape(-1), -1.0, 1.0)
    return (f * 32767.0).astype("<i2").tobytes()


def _from_int16(b: bytes) -> np.ndarray:
    """PCM16 little-endian bájtok → float32 [-1,1] mono."""
    return np.frombuffer(b, dtype="<i2").astype(np.float32) / 32768.0


class TerbeliHang:
    """Valós mikrofon-rögzítés + térbeli lejátszás (a hálózati réteg táplálja).

    `indit(on_kimeno)` elindítja a felvételt (minden ~20 ms-os mono kockát a
    `on_kimeno(pcm16_bytes)` callbackkal ad ki, hogy a hálózat elküldje) és a
    lejátszást (a `Kevero` kimenetét szólaltatja meg). A távoli résztvevők
    hangját a `fogad(nev, pcm16_bytes)` adja a keverőbe. `SOUNDDEVICE` kell –
    ha nincs (vagy nincs eszköz), a `hiba` kivétel száll, a hívó kezeli."""

    def __init__(self):
        self.kevero = Kevero()
        self._be = None
        self._ki = None
        self._on_kimeno = None
        self._nemit = False

    def elerheto(self) -> bool:
        try:
            import sounddevice  # noqa: F401
            return True
        except Exception:
            return False

    def set_ulesek(self, pan_map: dict):
        self.kevero.set_ulesek(pan_map)

    def fogad(self, nev: str, pcm16: bytes):
        try:
            self.kevero.add(nev, _from_int16(pcm16))
        except Exception:
            pass

    def elenged(self, nev: str):
        self.kevero.elenged(nev)

    def nemit(self, ertek: bool):
        """Mikrofon némítása (a lejátszás megy tovább)."""
        self._nemit = bool(ertek)

    def indit(self, on_kimeno):
        import sounddevice as sd
        self._on_kimeno = on_kimeno

        def be_cb(indata, frames, t, status):        # mikrofon → hálózat
            try:
                mono = np.asarray(indata, dtype=np.float32)
                if mono.ndim > 1:
                    mono = mono.mean(axis=1)
                if self._nemit:
                    return
                if self._on_kimeno:
                    self._on_kimeno(_to_int16(mono))
            except Exception:
                pass

        def ki_cb(outdata, frames, t, status):        # keverő → fejhallgató
            try:
                outdata[:] = self.kevero.kimenet(frames)
            except Exception:
                outdata.fill(0)

        self._be = sd.InputStream(samplerate=FS, channels=1, dtype="float32",
                                  blocksize=BLOKK, callback=be_cb)
        self._ki = sd.OutputStream(samplerate=FS, channels=2, dtype="float32",
                                   blocksize=BLOKK, callback=ki_cb)
        self._be.start()
        self._ki.start()

    def leallit(self):
        for s in (self._be, self._ki):
            try:
                if s is not None:
                    s.stop(); s.close()
            except Exception:
                pass
        self._be = self._ki = None


def bemutato_jel(masodperc: float = 6.0, fs: int = FS) -> np.ndarray:
    """A térélmény bemutatója HÁLÓZAT NÉLKÜL: egy lágy hang, amely balról jobbra
    ÉS vissza „körbejár” a hallgató körül. Visszaad: sztereó float32 tömb, amit
    a hívó lejátszhat (sounddevice) vagy WAV-ba írhat. Bizonyítja, hogy a
    panorámázás valóban irányból szólal meg."""
    n = int(masodperc * fs)
    t = np.arange(n) / fs
    # kellemes, beszéd-magasságú, lüktető hang (nem éles szinusz)
    alap = 240.0
    hang = (0.6 * np.sin(2 * np.pi * alap * t)
            + 0.2 * np.sin(2 * np.pi * 2 * alap * t))
    burkolo = 0.5 * (1 - np.cos(2 * np.pi * 4 * t))     # lágy lüktetés
    mono = (hang * burkolo * 0.3).astype(np.float32)
    # a pan bal(-1)→jobb(+1)→bal, kétszer körbe
    pan = np.sin(2 * np.pi * (t / masodperc) * 2.0)
    ang = (np.clip(pan, -1, 1) + 1) * 0.25 * np.pi
    ki = np.column_stack((mono * np.cos(ang), mono * np.sin(ang)))
    return ki.astype(np.float32)
