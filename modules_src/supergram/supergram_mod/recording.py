"""Local microphone capture for user-initiated Telegram voice notes."""

import subprocess
import threading
import wave
from pathlib import Path


class VoiceRecorder:
    def __init__(self, wav_path: Path):
        self.wav_path = Path(wav_path)
        self._stop = threading.Event()
        self._thread = None
        self.error = None
        self.duration = 0

    def start(self):
        if self._thread:
            raise RuntimeError("A felvétel már fut.")
        self.wav_path.parent.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._capture, daemon=True)
        self._thread.start()

    def _capture(self):
        try:
            import sounddevice as sd
            frames = 0
            with wave.open(str(self.wav_path), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(48000)
                with sd.RawInputStream(samplerate=48000, channels=1,
                                       dtype="int16") as stream:
                    while not self._stop.is_set() and frames < 48000 * 600:
                        chunk, _overflowed = stream.read(1024)
                        output.writeframes(chunk)
                        frames += len(chunk) // 2
            self.duration = frames / 48000
        except Exception as exc:
            self.error = str(exc)

    def stop(self, ffmpeg_path: str) -> tuple[Path, int]:
        if not self._thread:
            raise RuntimeError("Nincs folyamatban felvétel.")
        self._stop.set()
        self._thread.join(timeout=5)
        if self._thread.is_alive():
            raise RuntimeError("A mikrofon még nem állt le.")
        if self.error:
            raise RuntimeError("Mikrofonhiba: " + self.error)
        if self.duration < 0.25:
            raise RuntimeError("A felvétel túl rövid.")
        if not ffmpeg_path:
            raise RuntimeError("A hangüzenethez FFmpeg szükséges.")
        ogg_path = self.wav_path.with_suffix(".ogg")
        try:
            result = subprocess.run([ffmpeg_path, "-nostdin", "-y", "-loglevel", "error",
                "-i", str(self.wav_path), "-ac", "1", "-ar", "48000", "-c:a",
                "libopus", "-b:a", "32k", str(ogg_path)], capture_output=True,
                timeout=90, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode or not ogg_path.is_file() or ogg_path.stat().st_size == 0:
                raise RuntimeError("Az OGG/Opus átalakítás sikertelen.")
            return ogg_path, max(1, round(self.duration))
        finally:
            self.wav_path.unlink(missing_ok=True)

    def cancel(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        self.wav_path.unlink(missing_ok=True)
