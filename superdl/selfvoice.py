"""Self-voice: a program SAJÁT hangú MŰVELET-BEJELENTŐ rétege.

NEM helyettesíti a képernyőolvasót, hanem KIEGÉSZÍTI: a fő műveletek
kezdetét/végét mondja be (amit a képernyőolvasó magától nem mond), helyi,
fürge SAPI-hanggal. Teljesen testreszabható (hang, tempó, hangmagasság,
hangerő), és a beállítási fülről kapcsolható.

A pitch-et SAPI-XML jelöléssel állítjuk (`<pitch absmiddle="N"/>`), a tempót
és a hangerőt a SpVoice Rate/Volume tulajdonságával.
"""

import os
import subprocess
import sys
import threading
from pathlib import Path

# beépített eSpeak-NG magyar hangok (a felhasználó kérte: több hang)
ESPEAK_VOICES = [
    ("eSpeak magyar – alap (férfi)", "espeak:hu"),
    ("eSpeak magyar – férfi 2", "espeak:hu+m2"),
    ("eSpeak magyar – férfi 3", "espeak:hu+m3"),
    ("eSpeak magyar – férfi 4", "espeak:hu+m4"),
    ("eSpeak magyar – női 1", "espeak:hu+f1"),
    ("eSpeak magyar – női 2", "espeak:hu+f2"),
    ("eSpeak magyar – női 3", "espeak:hu+f3"),
]
_NOWIN = 0x08000000 if os.name == "nt" else 0


def _espeak_paths():
    """(espeak-ng.exe útvonala, espeak-ng-data mappa) vagy (None, None).
    Frozen exében a _MEIPASS-ból, fejlesztéskor a projekt bin/ mappájából."""
    bases = []
    mp = getattr(sys, "_MEIPASS", None)
    if mp:
        bases.append(Path(mp))
    bases.append(Path(__file__).resolve().parent.parent / "bin")
    for b in bases:
        exe = b / "espeak-ng.exe"
        if exe.is_file():
            data = b / "espeak-ng-data"
            return str(exe), (str(data) if data.is_dir() else None)
    return None, None


def espeak_available() -> bool:
    return _espeak_paths()[0] is not None


# művelet-kulcs -> (kezdés, befejezés, hiba) bemondandó szövegek
EVENTS = {
    "download":  ("Letöltés megkezdődött", "Letöltés befejezve",
                  "Letöltési hiba"),
    "convert":   ("Konvertálás megkezdődött", "Konvertálás befejezve",
                  "Konvertálási hiba"),
    "ringtone":  ("Csengőhang készítése elkezdődött", "A csengőhang elkészült",
                  "Hiba a csengőhang készítésekor"),
    "video":     ("A videó renderelése elkezdődött", "A videó elkészült",
                  "Hiba a videó készítésekor"),
    "send":      ("Fájlküldés elindult", "A fájl átment a másik gépre",
                  "Hiba a küldéskor"),
    "receive":   ("Fájlfogadás elindult", "A fájl megérkezett",
                  "Hiba a fogadáskor"),
    "record":    ("Felvétel elindult", "A felvétel elkészült",
                  "Hiba a felvételkor"),
}
STATES = {"start": 0, "done": 1, "error": 2}


class SelfVoice:
    def __init__(self):
        self.enabled = False
        self.muted = False          # TELJES némítás: a force=True-t is felülírja
        self.voice_desc = ""        # a kívánt hang leírásának részlete
        self.rate = 0               # -10..10 (tempó)
        self.pitch = 0              # -10..10 (hangmagasság)
        self.volume = 100           # 0..100
        self._voice = None
        self._lock = threading.Lock()
        self._espeak_proc = None
        self._init_voice()

    def _init_voice(self):
        try:
            import win32com.client
            self._voice = win32com.client.Dispatch("SAPI.SpVoice")
        except Exception:
            self._voice = None

    @property
    def available(self) -> bool:
        return self._voice is not None or espeak_available()

    @property
    def _use_espeak(self) -> bool:
        return self.voice_desc.startswith("espeak:") and espeak_available()

    def list_voices(self) -> list[str]:
        """A telepített SAPI-hangok leírásai (a beállítási legördülőhöz)."""
        out = []
        if not self._voice:
            return out
        try:
            for token in self._voice.GetVoices():
                out.append(token.GetDescription())
        except Exception:
            pass
        return out

    def configure(self, *, enabled=None, muted=None, voice_desc=None, rate=None,
                  pitch=None, volume=None):
        if enabled is not None:
            self.enabled = bool(enabled)
        if muted is not None:
            self.muted = bool(muted)
        if voice_desc is not None:
            self.voice_desc = voice_desc
        if rate is not None:
            self.rate = max(-10, min(10, int(rate)))
        if pitch is not None:
            self.pitch = max(-10, min(10, int(pitch)))
        if volume is not None:
            self.volume = max(0, min(100, int(volume)))

    def _apply_voice(self):
        if not self._voice:
            return
        try:
            self._voice.Rate = self.rate
            self._voice.Volume = self.volume
            if self.voice_desc:
                for token in self._voice.GetVoices():
                    if self.voice_desc.lower() in token.GetDescription().lower():
                        self._voice.Voice = token
                        break
        except Exception:
            pass

    def speak(self, text: str, *, force: bool = False):
        """Aszinkron bemondás. `force=False` esetén csak ha be van kapcsolva.
        eSpeak-hang esetén a beépített eSpeak-NG-vel, különben a rendszer
        SAPI-hangjával szól."""
        if self.muted:                       # TELJES némítás: a force-ot is felülírja
            return
        if not self.enabled and not force:
            return
        if self._use_espeak:
            self._speak_espeak(text)
            return
        if not self._voice:
            return
        body = text
        if self.pitch:
            # SAPI-XML: a hangmagasság -10..10 -> absmiddle
            body = f'<pitch absmiddle="{self.pitch}"/>{text}'

        def work():
            with self._lock:
                try:
                    self._apply_voice()
                    self._voice.Speak(body, 1)        # 1 = async
                except Exception:
                    pass

        threading.Thread(target=work, daemon=True).start()

    def _speak_espeak(self, text: str):
        exe, data = _espeak_paths()
        if not exe:
            return
        voice = self.voice_desc[len("espeak:"):] or "hu"
        # tempó: -10..10 -> kb. 90..260 szó/perc; hangmagasság: -10..10 -> 10..90
        wpm = max(80, min(320, 175 + self.rate * 12))
        pitch = max(0, min(99, 50 + self.pitch * 4))
        amp = max(0, min(200, int(self.volume * 2)))    # 0..100 -> 0..200
        cmd = [exe, "-v", voice, "-s", str(wpm), "-p", str(pitch),
               "-a", str(amp)]
        if data:
            cmd += ["--path", str(Path(data).parent)]
        cmd.append(text)

        def work():
            with self._lock:
                # az előző bemondást leállítjuk (ne torlódjon a hang)
                if self._espeak_proc and self._espeak_proc.poll() is None:
                    try:
                        self._espeak_proc.terminate()
                    except OSError:
                        pass
                try:
                    self._espeak_proc = subprocess.Popen(
                        cmd, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, creationflags=_NOWIN)
                except OSError:
                    pass

        threading.Thread(target=work, daemon=True).start()

    def announce(self, key: str, state: str):
        """Egy művelet-esemény bemondása (key: download/convert/…; state:
        start/done/error)."""
        if self.muted or not self.enabled:
            return
        texts = EVENTS.get(key)
        if not texts:
            return
        idx = STATES.get(state, 0)
        self.speak(texts[idx] + ".")

    def stop(self):
        with self._lock:
            if self._voice:
                try:
                    self._voice.Speak("", 1 | 2)      # purge
                except Exception:
                    pass
            if self._espeak_proc and self._espeak_proc.poll() is None:
                try:
                    self._espeak_proc.terminate()
                except OSError:
                    pass
