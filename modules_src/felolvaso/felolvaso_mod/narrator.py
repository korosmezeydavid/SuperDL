"""A felirat-felolvasó HANGJA: a választható motorok (SAPI helyi hangok, Edge
neurális online hangok, beépített eSpeak) EGYSÉGES felülete. Minden feliratot
egy ideiglenes hangfájlba szintetizál, amit a lejátszó a film mellé megszólaltat
(a szinkront a hívó a lejátszási pozícióból vezérli).
"""

import os
import subprocess
import tempfile
from pathlib import Path

from superdl import selfvoice, tts

_NOWIN = 0x08000000    # CREATE_NO_WINDOW


def voice_options() -> list[tuple[str, str, str]]:
    """(megjelenő név, motor-kulcs, hang-azonosító) hármasok a hang-legördülőhöz.
    A helyi SAPI-hangok, a MAGYAR Edge neurális hangok és a beépített eSpeak;
    az AI-kulcsos motorok (gemini/cloud) kimaradnak – ehhez a három alap kell."""
    out: list[tuple[str, str, str]] = []
    try:
        for v in tts.ENGINES["sapi"].voices():
            out.append((f"SAPI – {v.name}", "sapi", v.id))
    except Exception:
        pass
    try:
        for v in tts.ENGINES["edge"].voices():
            if "hu-" in (v.id or "").lower():        # magyar neurális hangok
                out.append((f"Edge neurális – {v.name}", "edge", v.id))
    except Exception:
        pass
    if selfvoice.espeak_available():
        for name, vid in selfvoice.ESPEAK_VOICES:
            out.append((name, "espeak", vid))
    if not out:                                      # végszükség: eSpeak alap
        out.append(("eSpeak magyar (beépített)", "espeak", "espeak:hu"))
    return out


def _synth_espeak(voice_id: str, text: str, rate: int, pitch: int) -> str:
    exe, data = selfvoice._espeak_paths()
    if not exe:
        raise RuntimeError("Az eSpeak nem érhető el.")
    voice = voice_id[len("espeak:"):] if voice_id.startswith("espeak:") \
        else (voice_id or "hu")
    wpm = max(80, min(320, 175 + rate * 12))
    pit = max(0, min(99, 50 + pitch * 4))
    out = os.path.join(tempfile.gettempdir(),
                       f"subnarr_{os.getpid()}_{abs(hash(text)) % 10**8}.wav")
    cmd = [exe, "-v", voice, "-s", str(wpm), "-p", str(pit), "-w", out]
    if data:
        cmd += ["--path", str(Path(data).parent)]
    cmd.append(text)
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=_NOWIN, timeout=30)
    if r.returncode != 0 or not os.path.isfile(out):
        raise RuntimeError("Az eSpeak nem tudta legyártani a hangot.")
    return out


def synth_to_file(engine_key: str, voice_id: str, text: str,
                  rate: int = 0, pitch: int = 0) -> str:
    """Egy felirat szövegének hangfájlba szintetizálása a választott motorral.
    Visszaad: a hangfájl útvonala (a hívó törli lejátszás után). eSpeaknél WAV,
    SAPI-nál WAV, Edge-nél MP3 – a lejátszó (ffmpeg) mindet kezeli."""
    text = (text or "").strip()
    if not text:
        raise RuntimeError("üres szöveg")
    if engine_key == "espeak":
        return _synth_espeak(voice_id, text, rate, pitch)
    eng = tts.ENGINES.get(engine_key)
    if not eng:
        raise RuntimeError(f"ismeretlen hangmotor: {engine_key}")
    base = os.path.join(tempfile.gettempdir(),
                        f"subnarr_{os.getpid()}_{abs(hash(text)) % 10**8}")
    return eng.synth(text, voice_id, base, pitch=pitch, rate=rate)
