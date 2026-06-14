"""Akadálymentes RSS hírgyűjtő és újságolvasó.

A `feedparser`-rel olvassa a hírportálok / szövetségi oldalak RSS-feedjeit,
és a kiválasztott szalagcímhez a cikk teljes, REKLÁMMENTES, letisztított
szövegét adja vissza – csak a lényeg, képernyőolvasóra optimalizálva.

A feedek listája tartósan tárolódik (a podcast-feliratkozásoktól külön).
Csak nyilvánosan elérhető hírforrásokhoz használd!
"""

import re
import urllib.request
from dataclasses import dataclass

from . import store

UA = {"User-Agent": "Mozilla/5.0 (SuperDL hírolvasó)"}

# pár alapértelmezett magyar hírforrás, hogy ne üres listával induljon
DEFAULT_FEEDS = [
    ("hírek (Telex)", "https://telex.hu/rss"),
    ("hírek (444)", "https://444.hu/feed"),
    ("közélet (HVG)", "https://hvg.hu/rss"),
    ("MVGYOSZ (vakok szövetsége)", "https://www.mvgyosz.hu/feed/"),
]


@dataclass
class Article:
    title: str
    link: str
    summary: str = ""
    published: str = ""


@dataclass
class NewsFeed:
    url: str
    title: str = ""

    def to_record(self) -> dict:
        return {"url": self.url, "title": self.title}

    @classmethod
    def from_record(cls, r: dict) -> "NewsFeed":
        return cls(url=r["url"], title=r.get("title", ""))


def _strip_html(html: str) -> str:
    """HTML → sima, olvasható szöveg (bs4-gyel, ha van; egyébként regexszel)."""
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", text).strip()


def parse_news(feed_url: str) -> tuple[str, list[Article]]:
    """(forrás címe, szalagcímek listája, legújabb elöl)."""
    import feedparser

    d = feedparser.parse(feed_url)
    title = (d.feed.get("title") if d.feed else "") or feed_url
    articles: list[Article] = []
    for e in d.entries:
        summ = e.get("summary", "") or ""
        if not summ and e.get("content"):
            summ = e["content"][0].get("value", "")
        articles.append(Article(
            title=_strip_html(e.get("title", "cím nélkül")) or "cím nélkül",
            link=e.get("link", ""),
            summary=_strip_html(summ),
            published=e.get("published", "") or e.get("updated", "")))
    return title, articles


def fetch_article_text(url: str, fallback: str = "") -> str:
    """A cikk teljes, letisztított szövege a saját URL-jéről. Reklámot,
    menüt, szkriptet eldob; a fő szövegtörzset adja vissza. Hiba esetén a
    fallback (a feedből származó összefoglaló)."""
    if not url:
        return fallback
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
        charset = r.headers.get_content_charset() or "utf-8"
        html = raw.decode(charset, "replace")
    except Exception:
        return fallback

    try:
        from bs4 import BeautifulSoup
    except Exception:
        return _strip_html(html) or fallback

    soup = BeautifulSoup(html, "html.parser")
    # zavaró, nem tartalmi elemek eldobása
    for tag in soup(["script", "style", "nav", "header", "footer", "aside",
                     "form", "noscript", "iframe", "figure", "figcaption",
                     "button"]):
        tag.decompose()

    # a fő tartalom: <article>, vagy a legtöbb bekezdést tartalmazó blokk
    container = soup.find("article")
    if container is None:
        best, best_len = None, 0
        for cand in soup.find_all(["main", "div", "section"]):
            ps = cand.find_all("p", recursive=False)
            length = sum(len(p.get_text(strip=True)) for p in ps)
            if length > best_len:
                best, best_len = cand, length
        container = best or soup.body or soup

    paras = []
    for p in container.find_all(["p", "h1", "h2", "h3", "li"]):
        t = p.get_text(" ", strip=True)
        if t and len(t) > 1:
            paras.append(t)
    text = "\n\n".join(paras).strip()
    return text or fallback


class NewsManager:
    """A hírforrások (RSS-feedek) listáját kezeli és tárolja."""

    def __init__(self):
        records = store.load_news_feeds()
        if records:
            self.feeds = [NewsFeed.from_record(r) for r in records]
        else:
            self.feeds = [NewsFeed(url=u, title=t) for t, u in DEFAULT_FEEDS]
            self.save()

    def save(self) -> None:
        store.save_news_feeds([f.to_record() for f in self.feeds])

    def find(self, url: str) -> NewsFeed | None:
        return next((f for f in self.feeds if f.url == url), None)

    def add_feed(self, url: str) -> NewsFeed:
        f = self.find(url)
        if f is None:
            f = NewsFeed(url=url)
            try:
                f.title, _ = parse_news(url)
            except Exception:
                f.title = url
            self.feeds.append(f)
            self.save()
        return f

    def remove_feed(self, url: str) -> bool:
        f = self.find(url)
        if f:
            self.feeds.remove(f)
            self.save()
            return True
        return False
