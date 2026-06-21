"""Médiakeresés több legális forráson a yt-dlp-vel, és a lejátszható
stream-URL kioldása a beépített lejátszóhoz.

A keresés gyors, „lapos" (extract_flat) lekérés: csak a találatok
metaadatait hozza, a tényleges streamet majd lejátszáskor/letöltéskor
oldja ki. A források eredménye egyetlen, egybefűzött listába kerül.
"""

from dataclasses import dataclass

# kulcs -> (yt-dlp keresési előtag, emberi név)
SOURCES = {
    "youtube": ("ytsearch", "YouTube"),
    "soundcloud": ("scsearch", "SoundCloud"),
}
DEFAULT_SOURCES = ("youtube", "soundcloud")


# YouTube keresési szűrők (a keresési URL `sp=` paramétere, URL-kódolva)
SP_FILTERS = {
    "video": "EgIQAQ%3D%3D",
    "channel": "EgIQAg%3D%3D",
    "playlist": "EgIQAw%3D%3D",
}


@dataclass
class Result:
    title: str
    url: str
    source: str = ""
    duration: int = 0
    uploader: str = ""
    id: str = ""
    kind: str = "video"            # video / playlist / channel


def human_duration(seconds: int) -> str:
    if not seconds:
        return ""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _search_one(prefix: str, label: str, query: str, count: int) -> list[Result]:
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True,
            "skip_download": True}
    out: list[Result] = []
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(f"{prefix}{count}:{query}", download=False)
    for e in info.get("entries") or []:
        url = e.get("url") or e.get("webpage_url") or e.get("id")
        if not url:
            continue
        out.append(Result(
            title=e.get("title") or "(cím nélkül)",
            url=url, source=label,
            duration=e.get("duration") or 0,
            uploader=e.get("uploader") or e.get("channel") or "",
            id=str(e.get("id") or url)))
    return out


def _youtube_typed(query: str, count: int, kind: str) -> list[Result]:
    """YouTube keresés TÍPUS szerint (lejátszási lista / csatorna) a keresési
    URL `sp=` szűrőjével. A találatok lista-/csatorna-oldalak."""
    import yt_dlp
    from urllib.parse import quote

    url = (f"https://www.youtube.com/results?search_query={quote(query)}"
           f"&sp={SP_FILTERS[kind]}")
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True,
            "skip_download": True, "playlistend": count}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=False)
    out: list[Result] = []
    for e in info.get("entries") or []:
        if not e:
            continue
        u = e.get("url") or e.get("webpage_url")
        if not u:
            continue
        out.append(Result(
            title=e.get("title") or e.get("channel") or "(cím nélkül)",
            url=u, source="YouTube",
            duration=e.get("duration") or 0,
            uploader=e.get("uploader") or e.get("channel") or "",
            id=str(e.get("id") or u), kind=kind))
    return out


def search(query: str, count: int = 25,
           sources=DEFAULT_SOURCES, kind: str = "video") -> list[Result]:
    """Egybefűzött találatlista. `kind="video"` esetén a megadott forrásokból
    (YouTube + SoundCloud) körbeforgó sorrendben; `kind` lejátszási lista vagy
    csatorna esetén a YouTube típus-szűrt találatai (csak YouTube)."""
    if kind in ("channel", "playlist"):
        try:
            return _youtube_typed(query, count, kind)
        except Exception:
            return []
    per_source: list[list[Result]] = []
    for key in sources:
        prefix, label = SOURCES[key]
        try:
            per_source.append(_search_one(prefix, label, query, count))
        except Exception:
            per_source.append([])
    # körbeforgó összefűzés
    merged: list[Result] = []
    i = 0
    while True:
        added = False
        for lst in per_source:
            if i < len(lst):
                merged.append(lst[i])
                added = True
        if not added:
            break
        i += 1
    return merged


def resolve_stream(url: str, audio_only: bool = True,
                   cookies_browser: str | None = None,
                   cookies_file: str | None = None) -> tuple[str, str, int]:
    """A megadott oldal-URL-ből kiold egy LEJÁTSZHATÓ, közvetlen stream-URL-t.
    A Windows beépített lejátszójával jól kompatibilis formátumot részesít
    előnyben (m4a hang / mp4 videó). Visszaad: (stream_url, cím, hossz_mp)."""
    import yt_dlp
    if audio_only:
        fmt = "bestaudio[ext=m4a]/bestaudio[acodec^=mp4a]/bestaudio"
    else:
        # progresszív (egyben hang+kép) mp4 a kompatibilitásért; ha nincs,
        # essen vissza hangra
        fmt = ("best[ext=mp4][acodec!=none][vcodec!=none]/"
               "best[acodec!=none][vcodec!=none]/"
               "bestaudio[ext=m4a]/bestaudio")
    opts = {"quiet": True, "no_warnings": True, "skip_download": True,
            "format": fmt}
    if cookies_browser:
        opts["cookiesfrombrowser"] = (cookies_browser,)
    elif cookies_file:
        # a kiegészítővel mentett cookies.txt-t normalizáljuk; ha nem
        # használható, lejátszásnál egyszerűen sütik nélkül próbálkozunk
        from .cookies import prepare_cookiefile, CookieFileError
        try:
            opts["cookiefile"] = prepare_cookiefile(cookies_file)
        except CookieFileError:
            pass
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=False)
    if info.get("entries"):
        info = info["entries"][0]
    return info.get("url"), info.get("title", ""), info.get("duration") or 0
