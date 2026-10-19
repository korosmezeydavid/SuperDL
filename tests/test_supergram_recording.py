"""A hangüzenet felvétel utáni kódolása olvasható OGG/Opus fájlt ad."""

import threading
import wave

import pytest

from modules_src.supergram.supergram_mod.recording import VoiceRecorder
from superdl.ffmpeg import find_ffmpeg


def test_encoded_voice_note_is_ogg_opus_and_source_is_removed(tmp_path):
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        pytest.skip("Nincs helyben FFmpeg")
    wav = tmp_path / "proba.wav"
    with wave.open(str(wav), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(48000)
        output.writeframes(b"\x00\x00" * 48000)
    recorder = VoiceRecorder(wav)
    recorder._thread = threading.Thread(target=lambda: None)
    recorder._thread.start()
    recorder.duration = 1
    ogg, duration = recorder.stop(ffmpeg)
    assert duration == 1
    assert ogg.read_bytes().startswith(b"OggS")
    assert b"OpusHead" in ogg.read_bytes()[:200]
    assert not wav.exists()
