"""Super Recorder / fülre-szerkesztő: mintavétel- és bitráta-hűség őrei.

Felhasználói jelzés (2026-07): a 48 kHz-es anyagot a szerkesztő MINDENKÉPP 44,1
kHz-ben mentette, és nem lehetett bitrátát/mintavételt állítani. Mély hiba-audit,
Mérföldkő 6. GYÖKÉR: a Clip.from_file 44100-at kényszerített; az MP3 fixen 256k
volt. FIX: from_file natív mintavétel (probe_audio), save_pcm out_freq + mp3_bitrate.
"""

import inspect
import os
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent
                       / "modules_src" / "supermedia"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _ffmpeg():
    from superdl import ffmpeg as ffmpeg_mod
    ff = ffmpeg_mod.find_ffmpeg()
    if not ff:
        ff = ffmpeg_mod.find_ffmpeg() if ffmpeg_mod.ensure_ffmpeg() else None
    return ff


def test_save_pcm_es_from_file_szignatura():
    """Az új paraméterek megléte (out_freq, mp3_bitrate; from_file natív)."""
    from supermedia_mod import superrec, supereditor
    assert "out_freq" in inspect.signature(superrec.save_pcm).parameters
    assert "mp3_bitrate" in inspect.signature(superrec.save_pcm).parameters
    assert hasattr(superrec, "probe_audio")
    # a from_file alapból 0 (natív) freq-kel indul, nem 44100-zal
    assert inspect.signature(supereditor.Clip.from_file).parameters["freq"].default == 0


def test_48khz_megorzese_es_mentesi_valasztas():
    """VALÓDI ffmpeg: 48 kHz betöltése megmarad; a mentés a választott
    mintavétellel megy (Eredeti=48000, illetve 44100 kényszerítve)."""
    ff = _ffmpeg()
    if not ff:
        pytest.skip("nincs ffmpeg")
    from supermedia_mod import supereditor as ED
    d = tempfile.mkdtemp(prefix="mk6t_")
    try:
        src = os.path.join(d, "s48.wav")
        subprocess.run([ff, "-y", "-f", "lavfi",
                        "-i", "sine=frequency=440:duration=1:sample_rate=48000",
                        "-ac", "2", src],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        clip = ED.Clip.from_file(src)
        assert clip.freq == 48000, f"a 48 kHz nem maradt meg: {clip.freq}"

        out0 = os.path.join(d, "eredeti.wav")
        clip.save(out0, out_freq=0)
        with wave.open(out0, "rb") as w:
            assert w.getframerate() == 48000

        out44 = os.path.join(d, "k44.wav")
        clip.save(out44, out_freq=44100)
        with wave.open(out44, "rb") as w:
            assert w.getframerate() == 44100
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def test_ui_mintavetel_es_bitrata_valaszto():
    """A szerkesztő felületén legyen mintavétel- és MP3-bitráta-választó, és a
    mentés adja át őket."""
    pytest.importorskip("wx")
    from supermedia_mod.supereditwin import SuperEditorFrame
    cls_src = inspect.getsource(SuperEditorFrame)
    assert "sr_ch" in cls_src and "br_ch" in cls_src       # a választók léteznek
    save_src = inspect.getsource(SuperEditorFrame._on_save)
    assert "out_freq" in save_src and "mp3_bitrate" in save_src
