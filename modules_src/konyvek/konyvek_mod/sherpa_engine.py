"""A Sherpa-hang bejegyzése a már kiadott SuperDL magjába is.

A forrásból futó program magában hordozza a motort. A telepített programban
a Könyvek modul hozza magával, így a frissítés után az élő olvasás és az
MP3-készítés is használja.
"""

from superdl import tts

HANGMINTA = (
    "Ma szép idő van. "
    "A vessző után, ahogy most hallod, a hangsúly megáll egy pillanatra. "
    "Figyelj ide! "
    "Így szoktam kérdezni?"
)


class SherpaEngine:
    key = "sherpa"
    name = "Sherpa a gépről (Piper és Supertonic, offline, nyílt hangok)"
    char_limit = 600
    supports_pitch = True
    supports_rate = True
    needs_key = False

    def voices(self, api_key: str = "") -> list:
        from . import sherpa_voices
        out = []
        for item in sherpa_voices.discover():
            voice = tts.Voice(id=item.voice_id, name=item.name, lang=item.lang)
            voice.source = item.source
            voice.playable = item.playable
            out.append(voice)
        return out

    def source_line(self, voice_id: str) -> str:
        from . import sherpa_voices
        return sherpa_voices.source_for(voice_id)

    def synth(self, text, voice_id, out_base, pitch=0, rate=0, api_key="") -> str:
        from . import sherpa_voices
        return sherpa_voices.synthesize(
            voice_id, text, out_base, pitch=pitch, rate=rate)


def ensure() -> None:
    if "sherpa" not in tts.ENGINES:
        tts.ENGINES["sherpa"] = SherpaEngine()
