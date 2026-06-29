"""Super Recorder – fülre-szerkesztő modell (It.2).

Egy `Clip` a nyers 16 bites PCM-et tartja (memóriában), markerekkel. A szerkesztés
a videóvágó SZELLEMÉBEN megy: markereket dobsz le hallás után, a műveletek a
KIJELÖLT marker és a KÖVETKEZŐ marker közti SZAKASZRA hatnak (az utolsó marker
szakasza a klip végéig tart). Minden művelet visszavonható (undo/redo).

A modell tiszta logika (nincs wx); a lejátszást/megjelenítést a supereditwin
intézi (a PCM-et temp WAV-ba írva, a Core audioengine-jével).
"""

from . import superrec


class Clip:
    def __init__(self, pcm: bytes = b"", freq: int = 44100, channels: int = 2):
        self.freq = freq
        self.channels = channels
        self.pcm = bytearray(pcm)
        self.markers: list[float] = []
        self._undo: list[tuple[bytes, list]] = []
        self._redo: list[tuple[bytes, list]] = []
        self.clipboard: bytes = b""
        self._max_undo = 30

    # ---- alapok ------------------------------------------------------

    @property
    def frame_bytes(self) -> int:
        return self.channels * 2          # 16 bit = 2 byte/minta

    @property
    def bytes_per_sec(self) -> int:
        return self.freq * self.frame_bytes

    def duration(self) -> float:
        return len(self.pcm) / self.bytes_per_sec if self.bytes_per_sec else 0.0

    def has_audio(self) -> bool:
        return len(self.pcm) > 0

    def _off(self, sec: float) -> int:
        """Másodperc → BYTE-eltolás, mintahatárra (frame) igazítva, a klipbe vágva."""
        sec = max(0.0, min(sec, self.duration()))
        b = int(sec * self.bytes_per_sec)
        b -= b % self.frame_bytes
        return max(0, min(b, len(self.pcm)))

    # ---- undo/redo ---------------------------------------------------

    def _snapshot(self):
        self._undo.append((bytes(self.pcm), list(self.markers)))
        if len(self._undo) > self._max_undo:
            self._undo.pop(0)
        self._redo.clear()

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append((bytes(self.pcm), list(self.markers)))
        pcm, mk = self._undo.pop()
        self.pcm = bytearray(pcm)
        self.markers = mk
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append((bytes(self.pcm), list(self.markers)))
        pcm, mk = self._redo.pop()
        self.pcm = bytearray(pcm)
        self.markers = mk
        return True

    # ---- markerek + szakasz ------------------------------------------

    def add_marker(self, sec: float):
        sec = max(0.0, min(sec, self.duration()))
        if all(abs(sec - m) > 1e-4 for m in self.markers):
            self.markers.append(sec)
            self.markers.sort()

    def remove_marker(self, idx: int):
        if 0 <= idx < len(self.markers):
            self.markers.pop(idx)

    def clear_markers(self):
        self.markers = []

    def section(self, idx: int) -> tuple[float, float] | None:
        """A `idx`. markerhez tartozó szakasz [kezdet, vég): a marker és a
        KÖVETKEZŐ marker közt; az utolsónál a klip végéig."""
        if not (0 <= idx < len(self.markers)):
            return None
        a = self.markers[idx]
        b = self.markers[idx + 1] if idx + 1 < len(self.markers) else self.duration()
        return (a, b) if b > a else None

    def _shift_markers(self, at: float, delta: float):
        """A markereket `at` UTÁN `delta` másodperccel tolja (beszúrás/törléskor)."""
        out = []
        for m in self.markers:
            if m <= at + 1e-9:
                out.append(m)
            else:
                nm = m + delta
                if nm > at - 1e-9:
                    out.append(max(at, nm))
        self.markers = sorted(set(round(x, 6) for x in out))

    # ---- műveletek (mind visszavonható) ------------------------------

    def delete_range(self, a: float, b: float):
        ba, bb = self._off(a), self._off(b)
        if bb <= ba:
            return
        self._snapshot()
        del self.pcm[ba:bb]
        self._shift_markers(a, -(b - a))

    def trim_to(self, a: float, b: float):
        """Csak az [a,b) szakaszt tartja meg (a többit eldobja)."""
        ba, bb = self._off(a), self._off(b)
        if bb <= ba:
            return
        self._snapshot()
        self.pcm = bytearray(self.pcm[ba:bb])
        self.markers = sorted(max(0.0, m - a) for m in self.markers
                              if a - 1e-9 <= m <= b + 1e-9)

    def mute_range(self, a: float, b: float):
        ba, bb = self._off(a), self._off(b)
        if bb <= ba:
            return
        self._snapshot()
        self.pcm[ba:bb] = b"\x00" * (bb - ba)

    def insert_silence(self, at: float, dur: float):
        if dur <= 0:
            return
        self._snapshot()
        n = int(dur * self.bytes_per_sec)
        n -= n % self.frame_bytes
        off = self._off(at)
        self.pcm[off:off] = b"\x00" * n
        self._shift_markers(at, dur)

    def copy_range(self, a: float, b: float):
        ba, bb = self._off(a), self._off(b)
        if bb > ba:
            self.clipboard = bytes(self.pcm[ba:bb])

    def paste(self, at: float):
        if not self.clipboard:
            return
        self._snapshot()
        off = self._off(at)
        self.pcm[off:off] = self.clipboard
        self._shift_markers(at, len(self.clipboard) / self.bytes_per_sec)

    # ---- effektek (It.3) + vokál (It.4) ------------------------------

    def _replace_range(self, a: float, b: float, new: bytes):
        """A [a,b) byte-tartomány cseréje új PCM-re (snapshot + marker-eltolás)."""
        ba, bb = self._off(a), self._off(b)
        self._snapshot()
        old_dur = (bb - ba) / self.bytes_per_sec
        self.pcm[ba:bb] = new
        new_dur = len(new) / self.bytes_per_sec
        if abs(new_dur - old_dur) > 1e-4:
            self._shift_markers(b, new_dur - old_dur)

    def apply_filter(self, a: float, b: float, af: str) -> bool:
        """Egy ffmpeg audio-szűrőt alkalmaz az [a,b) szakaszra. A hossz változhat
        (tempó/pitch). Sikerre True; üres szakaszra False. Visszavonható."""
        ba, bb = self._off(a), self._off(b)
        if bb <= ba:
            return False
        new = superrec.process_pcm(bytes(self.pcm[ba:bb]), self.freq,
                                   self.channels, af)
        self._replace_range(a, b, new)
        return True

    def apply_vocoder(self, a: float, b: float, intensity: float = 1.0) -> bool:
        ba, bb = self._off(a), self._off(b)
        if bb <= ba:
            return False
        from . import supervocal
        new = supervocal.vocoder(bytes(self.pcm[ba:bb]), self.freq,
                                 self.channels, intensity)
        self._replace_range(a, b, new)
        return True

    def apply_harmonizer(self, a: float, b: float, intervals=(4, 7),
                         mix: float = 0.6) -> bool:
        ba, bb = self._off(a), self._off(b)
        if bb <= ba:
            return False
        from . import supervocal
        new = supervocal.harmonize(bytes(self.pcm[ba:bb]), self.freq,
                                   self.channels, intervals, mix)
        self._replace_range(a, b, new)
        return True

    def remove_vocals(self) -> bool:
        """Ének eltávolítása az EGÉSZ klipből (sztereó közép-kioltás)."""
        if not self.has_audio():
            return False
        from . import supervocal
        new = supervocal.remove_vocals(bytes(self.pcm), self.freq, self.channels)
        self._replace_range(0.0, self.duration(), new)
        return True

    def mix_with(self, pcm_b: bytes, gain_a_db: float = 0.0,
                 gain_b_db: float = 0.0) -> bool:
        """A betöltött B-sáv (alap) keverése a teljes klipbe (a hossz a hosszabbé)."""
        if not pcm_b:
            return False
        from . import supervocal
        new = supervocal.mix_track(bytes(self.pcm), pcm_b, self.channels,
                                   gain_a_db, gain_b_db)
        self._replace_range(0.0, self.duration(), new)
        return True

    # ---- ki/be -------------------------------------------------------

    @classmethod
    def from_file(cls, path: str, freq: int = 44100, channels: int = 2,
                  progress=None) -> "Clip":
        pcm = superrec.decode_to_pcm(path, freq, channels, progress)
        return cls(pcm, freq, channels)

    def to_wav(self, path: str):
        superrec.write_wav_bytes(path, bytes(self.pcm), self.freq, self.channels)

    def save(self, path: str, *, normalize: bool = False, fade_ms: int = 0,
             trim_silence: bool = False, progress=None) -> str:
        return superrec.save_pcm(path, bytes(self.pcm), self.freq, self.channels,
                                 normalize=normalize, fade_ms=fade_ms,
                                 trim_silence=trim_silence, progress=progress)
