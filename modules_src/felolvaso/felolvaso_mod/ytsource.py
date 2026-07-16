"""YouTube- (és más yt-dlp-oldal-) link forrásként a felirat-felolvasóhoz.

A yt-dlp-vel feloldjuk a videó KÖZVETLEN hang-stream URL-jét (a Player azt már
le tudja játszani), és letöltjük a feliratot – a MANUÁLISAT előnyben, különben a
YouTube AUTO-feliratát, ami akár magyarra fordítva is elérhető (`automatic_
captions['hu']`). Így egy angol videó magyar (gépi) feliratát is felolvassa.
"""

import urllib.request

from . import subtitles

# a felirat-letöltéshez preferált formátumok (a parse_srt SRT-t és VTT-t kezel)
_SUB_FMT_PREF = ("srt", "vtt")
UA = {"User-Agent": "SuperDL/2.0"}


def is_url(s: str) -> bool:
    s = (s or "").strip().lower()
    return s.startswith(("http://", "https://", "www."))


def _best_audio_url(info: dict) -> str:
    fmts = info.get("formats") or []
    audio = [f for f in fmts
             if f.get("acodec") not in (None, "none")
             and f.get("vcodec") in (None, "none") and f.get("url")]
    audio.sort(key=lambda f: f.get("abr") or 0, reverse=True)
    if audio:
        return audio[0]["url"]
    # tartalék: bármely URL-lel bíró formátum, végül a fő info-url
    for f in fmts:
        if f.get("url"):
            return f["url"]
    return info.get("url", "")


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def _pick_sub_entry(track_list):
    """A preferált formátumú (srt/vtt) feliratbejegyzés kiválasztása egy nyelvi
    listából (különben az első, ha van url-je)."""
    for fmt in _SUB_FMT_PREF:
        for e in track_list or []:
            if (e.get("ext") or "").lower() == fmt and e.get("url"):
                return e
    for e in track_list or []:
        if e.get("url"):
            return e
    return None


def _load_subs(info: dict, prefer_langs):
    """(cue-lista, nyelv-címke) az első elérhető feliratból. Sorrend: a kért
    nyelvek MANUÁLIS felirata, majd ugyanazok AUTO-felirata."""
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    for src, tag in ((manual, "manuális"), (auto, "auto")):
        for lang in prefer_langs:
            entry = _pick_sub_entry(src.get(lang))
            if not entry:
                continue
            try:
                cues = subtitles.parse_srt(_fetch_text(entry["url"]))
            except Exception:
                continue
            if cues:
                return cues, f"{lang} ({tag})"
    return [], ""


def load_from_url(url: str, prefer_langs=("hu", "en"),
                  cookies_browser: str | None = None):
    """A link feloldása: (hang-stream URL, cue-lista, felirat-nyelv címke).
    `cookies_browser` megadva a bejelentkezett böngésző sütijeivel próbál (a
    korhatáros/bot-ellenőrzött videókhoz – a letöltő mintája szerint)."""
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    if cookies_browser:
        opts["cookiesfrombrowser"] = (cookies_browser,)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        try:
            from superdl.media import friendly_error
            raise RuntimeError(friendly_error(str(e)))
        except ImportError:
            raise RuntimeError(str(e))
    if info.get("entries"):                     # lista/lejátszási lista → 1. elem
        entries = [x for x in info["entries"] if x]
        info = entries[0] if entries else info
    stream = _best_audio_url(info)
    if not stream:
        raise RuntimeError("Nem találtam lejátszható hang-streamet ehhez a "
                           "videóhoz.")
    cues, lang = _load_subs(info, prefer_langs)
    title = info.get("title", "") or url
    return stream, cues, lang, title
