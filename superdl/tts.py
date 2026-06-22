"""Szöveg-felolvasó (TTS) motorok közös felülete a hangoskönyv-készítőhöz.

Négy backend:
  sapi   – helyi Windows-hangok (offline, ingyenes)
  edge   – Microsoft Edge neural hangok (online, ingyenes, KULCS NÉLKÜL)
  gemini – Google Gemini TTS (saját API-kulcs)
  cloud  – Google Cloud Text-to-Speech (saját API-kulcs)

Mindegyik motor egy hang-azonosítóra és (ahol támogatott) pitch/sebesség
értékre szintetizál egy hangfájlt. A pitch és a rate egységesen -10..10
egész; a motorok a sajátjukra képezik le. A hosszú szöveget a hívó
darabolja a `char_limit` szerint.
"""

import base64
import json
import urllib.request
from dataclasses import dataclass


@dataclass
class Voice:
    id: str
    name: str
    lang: str = ""
    gender: str = ""


# ======================================================================
#  SAPI – helyi hangok
# ======================================================================
class SapiEngine:
    key = "sapi"
    name = "Helyi hangok (SAPI, offline, ingyenes)"
    char_limit = 0            # 0 = nincs gyakorlati korlát
    supports_pitch = True
    supports_rate = True
    needs_key = False

    def voices(self, api_key: str = "") -> list[Voice]:
        import win32com.client
        v = win32com.client.Dispatch("SAPI.SpVoice")
        out = []
        for t in v.GetVoices():
            desc = t.GetDescription()
            lang = ""
            try:
                lang = t.GetAttribute("Language")
            except Exception:
                pass
            out.append(Voice(id=desc, name=desc, lang=lang))
        return out

    def synth(self, text, voice_id, out_base, pitch=0, rate=0,
              api_key="") -> str:
        import win32com.client
        path = out_base + ".wav"
        fs = win32com.client.Dispatch("SAPI.SpFileStream")
        fs.Open(path, 3)
        v = win32com.client.Dispatch("SAPI.SpVoice")
        for t in v.GetVoices():
            if t.GetDescription() == voice_id:
                v.Voice = t
                break
        v.AudioOutputStream = fs
        v.Rate = max(-10, min(10, int(rate)))
        xml = f"<pitch absmiddle='{max(-10, min(10, int(pitch)))}'/>"
        v.Speak(xml + _xml_escape(text))
        fs.Close()
        return path


# ======================================================================
#  EDGE – ingyenes neural hangok, kulcs nélkül
# ======================================================================
class EdgeEngine:
    key = "edge"
    name = "Edge neural (online, ingyenes, kulcs nélkül)"
    char_limit = 0
    supports_pitch = True
    supports_rate = True
    needs_key = False

    def voices(self, api_key: str = "") -> list[Voice]:
        import asyncio

        import edge_tts
        data = asyncio.run(edge_tts.list_voices())
        out = []
        for v in data:
            out.append(Voice(id=v["ShortName"],
                             name=f"{v['ShortName']}  ({v.get('Gender','')})",
                             lang=v.get("Locale", ""),
                             gender=v.get("Gender", "")))
        out.sort(key=lambda x: (not x.lang.startswith("hu"), x.lang, x.id))
        return out

    def synth(self, text, voice_id, out_base, pitch=0, rate=0,
              api_key="") -> str:
        import asyncio

        import edge_tts
        path = out_base + ".mp3"
        r = f"{'+' if rate >= 0 else '-'}{abs(int(rate))*10}%"
        p = f"{'+' if pitch >= 0 else '-'}{abs(int(pitch))*5}Hz"

        async def go():
            c = edge_tts.Communicate(text, voice_id, rate=r, pitch=p)
            await c.save(path)

        asyncio.run(go())
        return path


# ======================================================================
#  GEMINI TTS – saját kulcs
# ======================================================================
GEMINI_VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]


class GeminiEngine:
    key = "gemini"
    name = "Google Gemini TTS (saját API-kulcs)"
    char_limit = 4000
    supports_pitch = False
    supports_rate = False
    needs_key = True
    model = "gemini-2.5-flash-preview-tts"

    def voices(self, api_key: str = "") -> list[Voice]:
        return [Voice(id=n, name=n) for n in GEMINI_VOICES]

    def synth(self, text, voice_id, out_base, pitch=0, rate=0,
              api_key="") -> str:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={api_key}")
        body = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice_id}}},
            },
        }
        data = _post_json(url, body)
        part = data["candidates"][0]["content"]["parts"][0]
        pcm = base64.b64decode(part["inlineData"]["data"])
        path = out_base + ".wav"
        _write_wav(path, pcm, rate=24000, channels=1)
        return path


# ======================================================================
#  GOOGLE CLOUD TTS – saját kulcs
# ======================================================================
class CloudEngine:
    key = "cloud"
    name = "Google Cloud Text-to-Speech (saját API-kulcs)"
    char_limit = 5000
    supports_pitch = True
    supports_rate = True
    needs_key = True

    def voices(self, api_key: str = "") -> list[Voice]:
        url = f"https://texttospeech.googleapis.com/v1/voices?key={api_key}"
        data = _get_json(url)
        out = []
        for v in data.get("voices", []):
            lang = (v.get("languageCodes") or [""])[0]
            out.append(Voice(id=v["name"], name=f"{v['name']}  ({lang})",
                             lang=lang,
                             gender=v.get("ssmlGender", "")))
        out.sort(key=lambda x: (not x.lang.startswith("hu"), x.lang, x.id))
        return out

    def synth(self, text, voice_id, out_base, pitch=0, rate=0,
              api_key="") -> str:
        lang = "-".join(voice_id.split("-")[:2]) if "-" in voice_id else "en-US"
        url = (f"https://texttospeech.googleapis.com/v1/text:synthesize"
               f"?key={api_key}")
        body = {
            "input": {"text": text},
            "voice": {"languageCode": lang, "name": voice_id},
            "audioConfig": {"audioEncoding": "MP3",
                            "speakingRate": max(0.25, min(4.0, 1 + rate * 0.1)),
                            "pitch": max(-20.0, min(20.0, float(pitch)))},
        }
        data = _post_json(url, body)
        path = out_base + ".mp3"
        with open(path, "wb") as f:
            f.write(base64.b64decode(data["audioContent"]))
        return path


ENGINES = {e.key: e for e in (SapiEngine(), EdgeEngine(),
                              GeminiEngine(), CloudEngine())}


# ---- segédek ----------------------------------------------------------

def _xml_escape(t: str) -> str:
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _write_wav(path, pcm: bytes, rate=24000, channels=1, width=2) -> None:
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(pcm)


def _get_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "SuperDL"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _post_json(url, body, timeout=120):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "User-Agent": "SuperDL"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)
