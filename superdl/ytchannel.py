"""YouTube (és más yt-dlp által ismert) csatornák figyelése.

Feliratkozol egy csatorna URL-jére; a SuperDL a háttérben, a yt-dlp gyors
„flat" módjával ellenőrzi, jött-e új videó. Az ÚJ videókat NEM tölti le
automatikusan: berakja egy „Friss videók" listába, ahonnan a felhasználó
gombnyomásra online lejátszhatja (streamelheti) vagy letöltheti.

Csak nyilvánosan elérhető tartalomhoz használd, jogtisztán!
"""

import re
import threading
import time
from dataclasses import dataclass, field

from . import store


@dataclass
class Video:
    id: str
    title: str
    url: str
    channel_title: str = ""
    duration: int = 0

    def to_record(self) -> dict:
        return {"id": self.id, "title": self.title, "url": self.url,
                "channel_title": self.channel_title, "duration": self.duration}

    @classmethod
    def from_record(cls, r: dict) -> "Video":
        return cls(id=r.get("id", ""), title=r.get("title", "videó"),
                   url=r.get("url", ""),
                   channel_title=r.get("channel_title", ""),
                   duration=int(r.get("duration") or 0))


@dataclass
class Channel:
    url: str
    title: str = ""
    auto: bool = True
    seen: set = field(default_factory=set)
    last_check: float = 0.0

    def to_record(self) -> dict:
        return {"url": self.url, "title": self.title, "auto": self.auto,
                "seen": sorted(self.seen), "last_check": self.last_check}

    @classmethod
    def from_record(cls, r: dict) -> "Channel":
        return cls(url=r["url"], title=r.get("title", ""),
                   auto=r.get("auto", True), seen=set(r.get("seen", [])),
                   last_check=r.get("last_check", 0.0))


def _videos_url(url: str) -> str:
    """A csatorna gyökér-URL-jét a feltöltések („/videos") fülre alakítja,
    hogy biztosan a videókat kapjuk, ne a csatorna nyitólapját."""
    u = url.strip()
    if re.search(r"youtube\.com/(@[^/?#]+|channel/[^/?#]+|c/[^/?#]+|"
                 r"user/[^/?#]+)/?$", u):
        return u.rstrip("/") + "/videos"
    return u


def fetch_videos(url: str, limit: int = 15) -> tuple[str, list[Video]]:
    """A csatorna legutóbbi videói (cím, lista). Gyors, „flat" lekérés –
    nem oldja fel egyenként a videókat."""
    import yt_dlp

    opts = {"quiet": True, "no_warnings": True, "skip_download": True,
            "extract_flat": "in_playlist", "playlistend": limit}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(_videos_url(url), download=False)

    title = (info.get("channel") or info.get("uploader")
             or info.get("title") or url)
    entries = info.get("entries") or []
    # ha tabok/al-listák jönnek (nincs id, de van bennük entries), lépjünk be
    if entries and not entries[0].get("id") and entries[0].get("entries"):
        for e in entries:
            if e.get("entries"):
                entries = e["entries"]
                break

    videos: list[Video] = []
    for e in entries[:limit]:
        if not e:
            continue
        vid = e.get("id")
        if not vid:
            continue
        vurl = (e.get("url") or e.get("webpage_url")
                or f"https://www.youtube.com/watch?v={vid}")
        videos.append(Video(
            id=vid, title=e.get("title") or "videó", url=vurl,
            channel_title=title, duration=int(e.get("duration") or 0)))
    return title, videos


class ChannelManager:
    """A csatorna-feliratkozásokat és a friss (még nem megnyitott) videók
    listáját kezeli és tárolja. A `feeds.FeedManager` testvére."""

    def __init__(self):
        self.channels: list[Channel] = [
            Channel.from_record(r) for r in store.load_channels()]
        self.fresh: list[Video] = [
            Video.from_record(r) for r in store.load_fresh_videos()]
        self._lock = threading.Lock()

    # ---- tárolás ------------------------------------------------------

    def save(self) -> None:
        with self._lock:
            store.save_channels([c.to_record() for c in self.channels])
            store.save_fresh_videos([v.to_record() for v in self.fresh])

    def find(self, url: str) -> Channel | None:
        return next((c for c in self.channels if c.url == url), None)

    # ---- feliratkozás -------------------------------------------------

    def subscribe(self, url: str, mark_existing: bool = True) -> Channel:
        """Feliratkozás egy csatornára. mark_existing=True esetén a már
        meglévő videókat 'látottnak' jelöli, így csak az ezutániakat jelzi."""
        ch = self.find(url)
        if ch is None:
            ch = Channel(url=url)
            title, videos = fetch_videos(url)
            ch.title = title
            if mark_existing:
                ch.seen = {v.id for v in videos}
            ch.last_check = time.time()
            self.channels.append(ch)
            self.save()
        return ch

    def unsubscribe(self, url: str) -> bool:
        ch = self.find(url)
        if ch:
            self.channels.remove(ch)
            self.save()
            return True
        return False

    # ---- friss videók -------------------------------------------------

    def _add_fresh(self, video: Video) -> None:
        if not any(v.id == video.id for v in self.fresh):
            self.fresh.insert(0, video)      # legújabb elöl

    def remove_fresh(self, video: Video) -> None:
        self.fresh = [v for v in self.fresh if v.id != video.id]
        self.save()

    def clear_fresh(self) -> None:
        self.fresh = []
        self.save()

    def check_all(self) -> list[tuple[Channel, Video]]:
        """Minden automatikus csatorna új videói. A talált videókat a friss
        listához adja és 'látottnak' jelöli (nem jelzi kétszer)."""
        found: list[tuple[Channel, Video]] = []
        for ch in list(self.channels):
            if not ch.auto:
                continue
            try:
                _, videos = fetch_videos(ch.url)
            except Exception:
                continue                     # hálózati hiba: legközelebb újra
            ch.last_check = time.time()
            # a régiektől az újak felé, hogy a sorrend természetes legyen
            for v in reversed(videos):
                if v.id not in ch.seen:
                    ch.seen.add(v.id)
                    self._add_fresh(v)
                    found.append((ch, v))
        self.save()
        return found
