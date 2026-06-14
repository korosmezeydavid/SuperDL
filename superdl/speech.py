"""Felolvasás a Windows beszédmotorjával (SAPI).

Külön, választható kiegészítés: a képernyőolvasót használók a saját
hangjukon hallják az értesítéseket, ezt a motort viszont azok is
bekapcsolhatják, akik nem futtatnak képernyőolvasót. Ha a beszédmotor
nem érhető el, csendben kikapcsol (a program így is működik).
"""

import threading
from pathlib import Path

SPEAK_DIR = Path.home() / ".superdl" / "speak"


def _co_init():
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass


def _co_uninit():
    try:
        import pythoncom
        pythoncom.CoUninitialize()
    except Exception:
        pass


class Speaker:
    def __init__(self):
        self._voice = None
        self._ok = False
        self._lock = threading.Lock()
        try:
            import win32com.client
            self._voice = win32com.client.Dispatch("SAPI.SpVoice")
            self._prefer_hungarian()
            self._ok = True
        except Exception:
            self._ok = False

    def _prefer_hungarian(self) -> None:
        try:
            for token in self._voice.GetVoices():
                desc = token.GetDescription().lower()
                if "hungar" in desc or "magyar" in desc:
                    self._voice.Voice = token
                    return
        except Exception:
            pass

    @property
    def available(self) -> bool:
        return self._ok

    def speak(self, text: str) -> None:
        """Aszinkron felolvasás; az előző mondatot félbeszakítja."""
        if not self._ok:
            return
        # 1 = SVSFlagsAsync, 2 = SVSFPurgeBeforeSpeak
        with self._lock:
            try:
                self._voice.Speak(text, 1 | 2)
            except Exception:
                pass

    def stop(self) -> None:
        if not self._ok:
            return
        with self._lock:
            try:
                self._voice.Speak("", 1 | 2)   # üres + purge = elnémítás
            except Exception:
                pass


class VoiceSpeaker:
    """Magyarul megszólaló felolvasó az értesítésekhez (üdvözlés, Ctrl+J,
    befejezés, hírcikk). Három mód:

      auto   – Edge neurális magyar hang (online); ha nincs net, magyar
               rendszerhangra (SAPI) esik vissza – mindig magyarul szól.
      edge   – mindig Edge magyar (ha nincs net, néma marad).
      system – mindig a rendszer (SAPI) hangja, offline.

    Drop-in csere a Speaker helyett: `available`, `speak`, `stop`.
    """

    def __init__(self, mode: str = "auto",
                 edge_voice: str = "hu-HU-TamasNeural"):
        self.mode = mode if mode in ("auto", "edge", "system") else "auto"
        self.edge_voice = edge_voice
        self._sapi = Speaker()            # rendszerhang + magyar SAPI tartalék
        self._sapi_voice = self._pick_sapi_voice()
        self._player = None
        self._seq = 0
        self._lock = threading.Lock()
        try:
            SPEAK_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    @staticmethod
    def _pick_sapi_voice() -> str:
        """A legjobb magyar SAPI-hang azonosítója (leírása), vagy az első."""
        try:
            from . import tts
            vs = tts.ENGINES["sapi"].voices("")
            hu = next((v for v in vs
                       if v.lang == "40E"
                       or "hungar" in v.name.lower()
                       or "magyar" in v.name.lower()), None)
            chosen = hu or (vs[0] if vs else None)
            return chosen.id if chosen else ""
        except Exception:
            return ""

    @property
    def available(self) -> bool:
        return True       # Edge vagy SAPI mindig elérhető

    def set_mode(self, mode: str) -> None:
        if mode in ("auto", "edge", "system"):
            self.mode = mode

    def _get_player(self):
        if self._player is None:
            from .audioengine import Player
            self._player = Player()
        return self._player

    def speak(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        self.stop()
        if self.mode == "system":
            self._sapi.speak(text)
            return
        with self._lock:
            self._seq += 1
            seq = self._seq
        threading.Thread(target=self._worker, args=(text, seq),
                         daemon=True).start()

    def _worker(self, text: str, seq: int) -> None:
        from . import tts
        path = None
        # 1. Edge magyar (online)
        try:
            base = str(SPEAK_DIR / f"say_{seq % 3}")
            path = tts.ENGINES["edge"].synth(text, self.edge_voice, base)
        except Exception:
            path = None
        # 2. ha nem sikerült és auto mód: magyar SAPI fájlba (offline tartalék)
        if path is None and self.mode == "auto":
            _co_init()
            try:
                base = str(SPEAK_DIR / f"say_{seq % 3}")
                path = tts.ENGINES["sapi"].synth(text, self._sapi_voice, base)
            except Exception:
                path = None
            finally:
                _co_uninit()
        with self._lock:
            if seq != self._seq:        # közben új beszéd jött vagy leállás
                return
        if path:
            try:
                self._get_player().play(path, "")
            except Exception:
                pass

    def stop(self) -> None:
        with self._lock:
            self._seq += 1
        try:
            self._sapi.stop()
        except Exception:
            pass
        if self._player:
            try:
                self._player.stop()
            except Exception:
                pass
