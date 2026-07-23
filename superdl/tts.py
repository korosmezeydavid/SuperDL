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
import contextlib
import json
import re
import urllib.request
from dataclasses import dataclass


@contextlib.contextmanager
def _sapi_com():
    """A SAPI-t (win32com) használó szál KÖTELEZŐEN inicializálja a COM-ot.
    E nélkül HÁTTÉRSZÁLON „CoInitialize has not been called” com_error jön, amit
    a hívók néha némán elnyelnek (élesben igazolt hiba: a hangoskönyv-készítő
    SAPI-hanggal háttérszálon elszállt). Ha a hívó szál (pl. wx főszál) már
    inicializálta a COM-ot, a CoInitialize S_FALSE-t ad, de a számláló így is
    kiegyensúlyozott a CoUninitialize-zal, ezért biztonságos mindkét esetben."""
    did = False
    try:
        import pythoncom
        pythoncom.CoInitialize()
        did = True
    except Exception:
        did = False
    try:
        yield
    finally:
        if did:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass


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
        out = []
        with _sapi_com():           # háttérszál-biztos COM-inicializálás
            v = win32com.client.Dispatch("SAPI.SpVoice")
            for t in v.GetVoices():
                desc = t.GetDescription()
                lang = ""
                try:
                    lang = t.GetAttribute("Language")
                except Exception:
                    pass
                out.append(Voice(id=desc, name=desc, lang=lang))
            t = None
            v = None                # a COM-objektumokat még inicializált COM alatt engedjük el
        return out

    def synth(self, text, voice_id, out_base, pitch=0, rate=0,
              api_key="") -> str:
        import win32com.client
        path = out_base + ".wav"
        with _sapi_com():           # háttérszál-biztos COM-inicializálás
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
            t = None
            v = None
            fs = None               # a COM-objektumokat még inicializált COM alatt engedjük el
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
        # a kulcs FEJLÉCBEN megy (nem az URL-ben) – így kivételben sem szivárog
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent")
        body = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice_id}}},
            },
        }
        data = _post_json(url, body, api_key=api_key)
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
    # A szolgáltatás korlátja BÁJTBAN értendő (nem karakterben): a magyar
    # ékezetek 2 bájtosak, ezért karakterben mérve túlléphetnénk a limitet.
    # Tartalékkal 4800, mert a kérés kerete is beleszámít. [Herman Tibi AB-P1-10]
    byte_limit = 4800
    supports_pitch = True
    supports_rate = True
    needs_key = True

    def voices(self, api_key: str = "") -> list[Voice]:
        url = "https://texttospeech.googleapis.com/v1/voices"
        data = _get_json(url, api_key=api_key)
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
        url = "https://texttospeech.googleapis.com/v1/text:synthesize"
        body = {
            "input": {"text": text},
            "voice": {"languageCode": lang, "name": voice_id},
            "audioConfig": {"audioEncoding": "MP3",
                            "speakingRate": max(0.25, min(4.0, 1 + rate * 0.1)),
                            "pitch": max(-20.0, min(20.0, float(pitch)))},
        }
        data = _post_json(url, body, api_key=api_key)
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


def redact(text: str, *secrets: str) -> str:
    """Az API-kulcsok MASZKOLÁSA minden felhasználónak megjelenő szövegben.
    A hálózati kivételek szövege tartalmazhatja a kérés URL-jét/fejlécét; e nélkül
    a titkos kulcs megjelenhetne a képernyőn, a képernyőolvasó beszédében vagy egy
    támogatási levélben. [Herman Tibi AB-P0-05 / TTS-SEC-001]"""
    out = str(text)
    for s in secrets:
        s = (s or "").strip()
        if len(s) >= 8:                       # rövid „kulcs” nem valódi titok
            out = out.replace(s, "***")
    # biztonsági háló: bármilyen key=... query-paraméter maradványa
    return re.sub(r"(?i)([?&]key=)[^&\s\"']+", r"\1***", out)


class TTSError(RuntimeError):
    """TTS-hiba MASZKOLT szöveggel (soha nem tartalmaz API-kulcsot)."""


def _api_headers(api_key: str = "") -> dict:
    """A Google API-k a kulcsot FEJLÉCBEN is elfogadják (x-goog-api-key). Így a
    kulcs NEM kerül az URL-be, tehát a kivételek/naplók URL-je sem szivárogtatja."""
    h = {"User-Agent": "SuperDL"}
    if api_key:
        h["x-goog-api-key"] = api_key
    return h


def _get_json(url, timeout=30, api_key=""):
    req = urllib.request.Request(url, headers=_api_headers(api_key))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception as e:
        raise TTSError(redact(e, api_key)) from None


def _post_json(url, body, timeout=120, api_key=""):
    data = json.dumps(body).encode("utf-8")
    headers = _api_headers(api_key)
    headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception as e:
        raise TTSError(redact(e, api_key)) from None
