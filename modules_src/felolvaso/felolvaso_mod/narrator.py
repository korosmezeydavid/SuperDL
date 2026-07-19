"""A felirat-felolvasó HANGJA: a választható motorok (SAPI helyi hangok, Edge
neurális online hangok, beépített eSpeak) EGYSÉGES felülete. Minden feliratot
egy ideiglenes hangfájlba szintetizál, amit a lejátszó a film mellé megszólaltat
(a szinkront a hívó a lejátszási pozícióból vezérli).
"""

import itertools
import os
import subprocess
import tempfile
import threading
from pathlib import Path

from superdl import selfvoice, tts

_NOWIN = 0x08000000    # CREATE_NO_WINDOW

# globálisan növekvő számláló az EGYEDI tempfájlnevekhez (a hash(text) önmagában
# ütközhet azonos szövegű soroknál / párhuzamos gyártásnál)
_seq = itertools.count()


def _com_init() -> bool:
    """A SAPI (COM) HÁTTÉRSZÁLON is használható legyen. A Microsoft COM szabálya:
    minden COM-ot használó szálnak külön CoInitialize-t kell hívnia – e nélkül a
    `win32com.client.Dispatch("SAPI.SpVoice")` a worker szálon
    „CoInitialize has not been called" hibával elszáll (élesben igazolva). A
    felirat-szintézis háttérszálon fut, ezért ITT kell inicializálni."""
    try:
        import pythoncom
        pythoncom.CoInitialize()
        return True
    except Exception:
        return False


def _com_uninit(did: bool) -> None:
    if not did:
        return
    try:
        import pythoncom
        pythoncom.CoUninitialize()
    except Exception:
        pass


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
    # FONTOS: nem elérhető motort SOHA nem kínálunk fel „működő" opcióként. Ha itt
    # üres a lista, a hívó (felolvasowin) tiltja a lejátszást és HANGOSAN jelzi,
    # hogy nincs használható hangmotor – nem lesz néma, magyarázat nélküli hiba.
    return out


def _synth_espeak(voice_id: str, text: str, rate: int, pitch: int) -> str:
    exe, data = selfvoice._espeak_paths()
    if not exe:
        raise RuntimeError("Az eSpeak nem érhető el.")
    voice = voice_id[len("espeak:"):] if voice_id.startswith("espeak:") \
        else (voice_id or "hu")
    wpm = max(80, min(320, 175 + rate * 12))
    pit = max(0, min(99, 50 + pitch * 4))
    out = os.path.join(
        tempfile.gettempdir(),
        f"subnarr_{os.getpid()}_{threading.get_ident()}_{next(_seq)}.wav")
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
    # egyedi ideiglenes fájlnév (PID + a HÍVÓ szál azonosítója + számláló), hogy a
    # párhuzamos előregyártás és az azonos szövegű sorok NE ütközzenek ugyanazon a
    # néven (Windows fájlzár / féllegyártott WAV forrása lehet)
    base = os.path.join(
        tempfile.gettempdir(),
        f"subnarr_{os.getpid()}_{threading.get_ident()}_{next(_seq)}")
    if engine_key == "sapi":
        did = _com_init()                 # SAPI COM a HÁTTÉRSZÁLON is
        try:
            return eng.synth(text, voice_id, base, pitch=pitch, rate=rate)
        finally:
            _com_uninit(did)
    return eng.synth(text, voice_id, base, pitch=pitch, rate=rate)
