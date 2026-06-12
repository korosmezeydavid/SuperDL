"""Felolvasás a Windows beszédmotorjával (SAPI).

Külön, választható kiegészítés: a képernyőolvasót használók a saját
hangjukon hallják az értesítéseket, ezt a motort viszont azok is
bekapcsolhatják, akik nem futtatnak képernyőolvasót. Ha a beszédmotor
nem érhető el, csendben kikapcsol (a program így is működik).
"""

import threading


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
