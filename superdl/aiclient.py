"""Egységes AI-kliens: OpenAI, Google Gemini, Anthropic (Claude), xAI (Grok).

A kulcsok a Beállítások → AI fülön adhatók meg, és a GÉPEDEN tárolódnak
(~/.superdl/ai.json) – semmi nem kerül sehová azon kívül, amit te magad
küldesz a választott szolgáltatónak. Ez a modul a megfelelő szolgáltatóhoz
irányítja a kéréseket:

  chat(prompt)            – szöveges válasz
  vision(prompt, kép)     – kép leírása / OCR
  transcribe(hangfájl)    – beszéd → szöveg (OpenAI Whisper vagy Gemini)

A hívások hálózatot igényelnek; a hiányzó kulcsot és a hibákat érthető magyar
üzenettel jelzi (AIError).
"""

import base64
import mimetypes
import os

import requests

from . import store

OPENAI_CHAT = "https://api.openai.com/v1/chat/completions"
OPENAI_TRANSCRIBE = "https://api.openai.com/v1/audio/transcriptions"
GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
              "{model}:generateContent?key={key}")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
XAI_CHAT = "https://api.x.ai/v1/chat/completions"

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
    "anthropic": "claude-sonnet-4-6",
    "xai": "grok-2-vision-latest",
}
PROVIDER_NAMES = {"openai": "OpenAI", "gemini": "Google Gemini",
                  "anthropic": "Anthropic (Claude)", "xai": "xAI (Grok)"}
KEY_FIELDS = {"openai": "openai_key", "gemini": "gemini_key",
              "anthropic": "anthropic_key", "xai": "xai_key"}
ALL_PROVIDERS = ("openai", "gemini", "anthropic", "xai")

TIMEOUT = 120
TIMEOUT_LONG = 600       # transzkripcióhoz


class AIError(Exception):
    pass


# ---- konfiguráció -----------------------------------------------------

def _cfg() -> dict:
    return store.load_ai_config()


def _key(cfg: dict, provider: str) -> str:
    if provider == "gemini":
        return _gemini_key(cfg)
    return (cfg.get(KEY_FIELDS[provider]) or "").strip()


def _gemini_key(cfg: dict) -> str:
    """A Gemini-kulcs okos feloldása. A Google-kulcs „AIza”-val kezdődik; ha
    az AI-fül mezőjében nem ilyen szerepel (pl. véletlenül OpenAI-kulcs került
    oda), a hangoskönyv (TTS) beállításában megadott Gemini-kulcsot használja –
    így egyetlen érvényes Gemini-kulcs mindenhol elég."""
    k = (cfg.get("gemini_key") or "").strip()
    if k.startswith("AIza"):
        return k
    try:
        tts = (store.load_tts_keys().get("gemini") or "").strip()
    except Exception:
        tts = ""
    if tts.startswith("AIza"):
        return tts
    return k


def _model(cfg: dict, provider: str, override: str | None = None) -> str:
    if override:
        return override
    m = (cfg.get("model") or "").strip()
    return m or DEFAULT_MODELS[provider]


def available_providers(cfg: dict | None = None) -> list[str]:
    cfg = cfg if cfg is not None else _cfg()
    return [p for p in ALL_PROVIDERS if _key(cfg, p)]


def _pick(cfg: dict, prefer: list[str] | None = None) -> str:
    avail = available_providers(cfg)
    if not avail:
        raise AIError("Nincs megadva AI API-kulcs. Add meg a "
                      "Beállítások → AI fülön.")
    for p in (prefer or []):
        if p in avail:
            return p
    default = cfg.get("provider") or "openai"
    return default if default in avail else avail[0]


# ---- nyilvános hívások ------------------------------------------------

def chat(prompt: str, system: str = "", *, provider: str | None = None,
         model: str | None = None, max_tokens: int = 2000) -> str:
    cfg = _cfg()
    p = provider or _pick(cfg)
    key, mdl = _key(cfg, p), _model(cfg, p, model)
    if p in ("openai", "xai"):
        url = OPENAI_CHAT if p == "openai" else XAI_CHAT
        return _openai_style(url, key, mdl,
                             [{"role": "user", "content": prompt}],
                             system, max_tokens)
    if p == "gemini":
        return _gemini(key, mdl, [{"text": prompt}], system, max_tokens)
    return _anthropic(key, mdl, [{"type": "text", "text": prompt}],
                      system, max_tokens)


def vision(prompt: str, image_bytes: bytes, mime: str = "image/png", *,
           provider: str | None = None, model: str | None = None,
           max_tokens: int = 2000) -> str:
    cfg = _cfg()
    p = provider or _pick(cfg)          # mind a négy tud képet
    key, mdl = _key(cfg, p), _model(cfg, p, model)
    b64 = base64.b64encode(image_bytes).decode()
    if p in ("openai", "xai"):
        url = OPENAI_CHAT if p == "openai" else XAI_CHAT
        content = [{"type": "text", "text": prompt},
                   {"type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"}}]
        return _openai_style(url, key, mdl,
                             [{"role": "user", "content": content}],
                             "", max_tokens)
    if p == "gemini":
        parts = [{"text": prompt},
                 {"inline_data": {"mime_type": mime, "data": b64}}]
        return _gemini(key, mdl, parts, "", max_tokens)
    content = [{"type": "text", "text": prompt},
               {"type": "image", "source": {"type": "base64",
                "media_type": mime, "data": b64}}]
    return _anthropic(key, mdl, content, "", max_tokens)


def analyze_video(prompt: str, *, youtube_url: str | None = None,
                  local_path: str | None = None, progress=None) -> str:
    """Videó KÉPI elemzése a Geminivel (a többi szolgáltató ezt nem tudja).
    YouTube-linket közvetlenül elemez; helyi fájlt feltölt a Files API-val."""
    cfg = _cfg()
    if not _key(cfg, "gemini"):
        raise AIError("A videó képi elemzéséhez Google Gemini kulcs kell "
                      "(a négy közül csak a Gemini elemzi magát a videót). "
                      "Add meg a Beállítások → AI fülön.")
    key, model = _key(cfg, "gemini"), _model(cfg, "gemini")
    if youtube_url:
        part = {"file_data": {"file_uri": youtube_url}}
    elif local_path:
        uri, mime = _gemini_upload(key, local_path, progress)
        part = {"file_data": {"mime_type": mime, "file_uri": uri}}
    else:
        raise AIError("Nincs megadva videóforrás.")
    if progress:
        progress("A videó elemzése folyamatban…")
    return _gemini(key, model, [{"text": prompt}, part], "", 4000)


def _gemini_upload(key, path, progress=None):
    """Helyi fájl feltöltése a Gemini Files API-val; visszaad: (uri, mime).
    Megvárja, amíg a videó feldolgozása készen áll (ACTIVE)."""
    import time

    mime = mimetypes.guess_type(path)[0] or "video/mp4"
    size = os.path.getsize(path)
    base = "https://generativelanguage.googleapis.com"
    if progress:
        progress("Videó feltöltése a Geminihez…")
    start = requests.post(
        f"{base}/upload/v1beta/files?key={key}",
        headers={"X-Goog-Upload-Protocol": "resumable",
                 "X-Goog-Upload-Command": "start",
                 "X-Goog-Upload-Header-Content-Length": str(size),
                 "X-Goog-Upload-Header-Content-Type": mime,
                 "Content-Type": "application/json"},
        json={"file": {"display_name": os.path.basename(path)}}, timeout=60)
    _check(start)
    up_url = start.headers.get("X-Goog-Upload-URL")
    if not up_url:
        raise AIError("A Gemini fájlfeltöltés nem indult el.")
    with open(path, "rb") as f:
        up = requests.post(up_url, data=f.read(), timeout=TIMEOUT_LONG,
                           headers={"X-Goog-Upload-Offset": "0",
                                    "X-Goog-Upload-Command": "upload, finalize"})
    _check(up)
    info = up.json().get("file", {})
    name, uri, state = info.get("name"), info.get("uri"), info.get("state")
    waited = 0
    while state and state != "ACTIVE":
        if state == "FAILED":
            raise AIError("A videó feldolgozása nem sikerült a Geminin.")
        if waited > 600:
            raise AIError("A videó feldolgozása túl sokáig tartott.")
        if progress:
            progress(f"A videó feldolgozása a Geminin… ({waited} mp)")
        time.sleep(4)
        waited += 4
        g = requests.get(f"{base}/v1beta/{name}?key={key}", timeout=30)
        _check(g)
        state = g.json().get("state")
    return uri, mime


def transcribe(audio_path: str, *, srt: bool = False,
               language: str = "hu") -> str:
    cfg = _cfg()
    p = _pick(cfg, prefer=["openai", "gemini"])
    if p not in ("openai", "gemini"):
        raise AIError("A hang átirathoz OpenAI vagy Gemini kulcs kell "
                      "(a Claude és a Grok nem dolgoz fel hangot).")
    key = _key(cfg, p)
    if p == "openai":
        return _whisper(key, audio_path, srt, language)
    return _gemini_audio(key, _model(cfg, "gemini"), audio_path, srt)


# ---- szolgáltató-adapterek -------------------------------------------

def _openai_style(url, key, model, messages, system, max_tokens):
    if system:
        messages = [{"role": "system", "content": system}] + messages
    body = {"model": model, "messages": messages, "max_tokens": max_tokens}
    r = requests.post(url, headers={"Authorization": f"Bearer {key}"},
                      json=body, timeout=TIMEOUT)
    _check(r)
    return r.json()["choices"][0]["message"]["content"].strip()


def _gemini(key, model, parts, system, max_tokens):
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"maxOutputTokens": max_tokens}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    r = requests.post(GEMINI_URL.format(model=model, key=key), json=body,
                      timeout=TIMEOUT_LONG)
    _check(r)
    cands = r.json().get("candidates") or []
    if not cands:
        raise AIError("A Gemini nem adott választ (lehet, hogy a tartalmat "
                      "biztonsági okból elutasította).")
    parts_out = cands[0].get("content", {}).get("parts", [])
    text = "".join(pp.get("text", "") for pp in parts_out).strip()
    if not text:
        raise AIError("A Gemini üres választ adott.")
    return text


def _anthropic(key, model, content, system, max_tokens):
    body = {"model": model, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": content}]}
    if system:
        body["system"] = system
    r = requests.post(ANTHROPIC_URL, json=body, timeout=TIMEOUT,
                      headers={"x-api-key": key,
                               "anthropic-version": "2023-06-01"})
    _check(r)
    blocks = r.json().get("content", [])
    return "".join(b.get("text", "") for b in blocks
                   if b.get("type") == "text").strip()


def _whisper(key, path, srt, language):
    fmt = "srt" if srt else "text"
    with open(path, "rb") as f:
        files = {"file": (os.path.basename(path), f)}
        data = {"model": "whisper-1", "response_format": fmt}
        if language:
            data["language"] = language
        r = requests.post(OPENAI_TRANSCRIBE, files=files, data=data,
                          headers={"Authorization": f"Bearer {key}"},
                          timeout=TIMEOUT_LONG)
    _check(r)
    return r.text.strip()


def _gemini_audio(key, model, path, srt):
    mime = mimetypes.guess_type(path)[0] or "audio/mpeg"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    if srt:
        prompt = ("Készíts időbélyeges SRT feliratot a felvétel beszédéből: "
                  "sorszám, időbélyeg (óra:perc:mp,ezredmp formátumban), "
                  "majd a szöveg. Csak a feliratot add vissza.")
    else:
        prompt = ("Írd le pontosan, magyarul, ami a felvételen elhangzik. "
                  "Csak a szöveget add vissza, megjegyzés nélkül.")
    parts = [{"text": prompt}, {"inline_data": {"mime_type": mime, "data": b64}}]
    return _gemini(key, model, parts, "", 8000)


# ---- hibakezelés ------------------------------------------------------

def _check(r):
    if r.status_code == 200:
        return
    detail = ""
    try:
        j = r.json()
        if isinstance(j, dict):
            err = j.get("error")
            if isinstance(err, dict):
                detail = err.get("message", "")
            elif isinstance(err, str):
                detail = err
            detail = detail or j.get("message", "")
    except Exception:
        detail = (r.text or "")[:300]
    detail = (detail or "ismeretlen hiba")[:400]
    low = detail.lower()
    bad_key = ("api key not valid" in low or "api_key_invalid" in low
               or "invalid api key" in low or "incorrect api key" in low)
    if r.status_code in (401, 403) or bad_key:
        raise AIError("Érvénytelen vagy hiányzó API-kulcs. Ellenőrizd a "
                      "Beállítások → AI fülön (figyelem: az AI-fül kulcsa "
                      "KÜLÖN a hangoskönyv TTS-kulcsától). – " + detail)
    if r.status_code == 404:
        raise AIError(f"Nincs ilyen modell vagy végpont ({r.status_code}). "
                      f"Próbálj másik modellt az AI fülön. – {detail}")
    if r.status_code == 429:
        raise AIError(f"Túl sok kérés, vagy elfogyott a kereted ({r.status_code})."
                      f" – {detail}")
    raise AIError(f"AI hiba ({r.status_code}): {detail}")
