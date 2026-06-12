"""Podcast- és RSS-feliratkozások kezelése.

Feliratkozol egy podcast vagy RSS hírcsatorna URL-jére, a SuperDL pedig
figyeli, és az új epizódokat (médiamellékleteket) automatikusan letölti.
Minden feliratkozás megjegyzi, mely epizódokat töltötte már le, így csak
az újakat hozza - ismétlés nélkül.

Csak nyilvánosan, ingyenesen elérhető hírcsatornákhoz használd!
"""

import threading
import time
from dataclasses import dataclass, field

from . import store


@dataclass
class Episode:
    title: str
    guid: str
    url: str               # a médiamelléklet (enclosure) URL-je
    published: str = ""


@dataclass
class Subscription:
    feed_url: str
    title: str = ""
    out_dir: str = ""
    audio_only: bool = True
    auto: bool = True                      # automatikusan tölti-e az újakat
    seen: set = field(default_factory=set)  # már letöltött epizód-azonosítók
    last_check: float = 0.0

    def to_record(self) -> dict:
        return {"feed_url": self.feed_url, "title": self.title,
                "out_dir": self.out_dir, "audio_only": self.audio_only,
                "auto": self.auto, "seen": sorted(self.seen),
                "last_check": self.last_check}

    @classmethod
    def from_record(cls, r: dict) -> "Subscription":
        return cls(feed_url=r["feed_url"], title=r.get("title", ""),
                   out_dir=r.get("out_dir", ""),
                   audio_only=r.get("audio_only", True),
                   auto=r.get("auto", True),
                   seen=set(r.get("seen", [])),
                   last_check=r.get("last_check", 0.0))


def parse_feed(feed_url: str) -> tuple[str, list[Episode]]:
    """Visszaadja: (csatorna címe, epizódok listája, legújabb elöl)."""
    import feedparser

    d = feedparser.parse(feed_url)
    title = (d.feed.get("title") if d.feed else "") or feed_url
    episodes: list[Episode] = []
    for entry in d.entries:
        media_url = ""
        # 1. valódi melléklet (podcast): <enclosure>
        for enc in entry.get("enclosures", []) or []:
            href = enc.get("href") or enc.get("url") or ""
            typ = (enc.get("type") or "")
            if href and (typ.startswith(("audio", "video")) or not typ):
                media_url = href
                break
        # 2. tartalék: media:content
        if not media_url:
            for mc in entry.get("media_content", []) or []:
                if mc.get("url"):
                    media_url = mc["url"]
                    break
        # 3. tartalék: maga a bejegyzés linkje (sima RSS)
        if not media_url:
            media_url = entry.get("link", "")
        if not media_url:
            continue
        guid = entry.get("id") or entry.get("guid") or media_url
        episodes.append(Episode(
            title=entry.get("title", "epizód"), guid=guid,
            url=media_url, published=entry.get("published", "")))
    return title, episodes


class FeedManager:
    """A feliratkozásokat kezeli és tárolja."""

    def __init__(self):
        self.subs: list[Subscription] = [
            Subscription.from_record(r) for r in store.load_subscriptions()]
        self._lock = threading.Lock()

    def save(self) -> None:
        with self._lock:
            store.save_subscriptions([s.to_record() for s in self.subs])

    def find(self, feed_url: str) -> Subscription | None:
        return next((s for s in self.subs if s.feed_url == feed_url), None)

    def subscribe(self, feed_url: str, out_dir: str = "",
                  audio_only: bool = True, mark_existing: bool = True
                  ) -> Subscription:
        """Feliratkozás. mark_existing=True esetén a már meglévő epizódokat
        'látottnak' jelöli, így csak az ezután megjelenőket tölti le."""
        sub = self.find(feed_url)
        if sub is None:
            sub = Subscription(feed_url=feed_url, out_dir=out_dir,
                               audio_only=audio_only)
            title, episodes = parse_feed(feed_url)
            sub.title = title
            if mark_existing:
                sub.seen = {e.guid for e in episodes}
            self.subs.append(sub)
            self.save()
        return sub

    def unsubscribe(self, feed_url: str) -> bool:
        sub = self.find(feed_url)
        if sub:
            self.subs.remove(sub)
            self.save()
            return True
        return False

    def new_episodes(self, sub: Subscription) -> list[Episode]:
        """A még le nem töltött epizódok az adott feliratkozásban."""
        _, episodes = parse_feed(sub.feed_url)
        sub.last_check = time.time()
        return [e for e in episodes if e.guid not in sub.seen]

    def mark_seen(self, sub: Subscription, episode: Episode) -> None:
        sub.seen.add(episode.guid)
        self.save()

    def check_all(self) -> list[tuple[Subscription, Episode]]:
        """Minden automatikus feliratkozás új epizódjai (felirat, epizód)."""
        found: list[tuple[Subscription, Episode]] = []
        for sub in list(self.subs):
            if not sub.auto:
                continue
            try:
                for ep in self.new_episodes(sub):
                    found.append((sub, ep))
            except Exception:
                continue  # hálózati hiba: legközelebb újra próbáljuk
        self.save()
        return found
