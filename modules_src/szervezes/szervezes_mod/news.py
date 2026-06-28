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

from superdl import store        # megosztott tároló a Core-ból

UA = {"User-Agent": "Mozilla/5.0 (SuperDL hírolvasó)"}

# Beépített magyar hírforrások kategóriánként (kategória, név, RSS-cím).
# Mind ellenőrzött, élő feed (2026-06).
DEFAULT_FEEDS = [
    ("Hírek", "Telex", "https://telex.hu/rss"),
    ("Hírek", "444", "https://444.hu/feed"),
    ("Hírek", "HVG", "https://hvg.hu/rss"),
    ("Hírek", "Index", "https://index.hu/24ora/rss/"),
    ("Hírek", "24.hu", "https://24.hu/feed/"),
    ("Hírek", "Origo", "https://www.origo.hu/contentpartner/rss/origoall/"
                       "origo.xml"),
    ("Hírek", "Népszava", "https://nepszava.hu/feed"),
    ("IT", "HWSW", "https://www.hwsw.hu/xml/latest_news_rss.xml"),
    ("IT", "Bitport", "https://bitport.hu/rss"),
    ("Játék", "GameStar", "https://www.gamestar.hu/site/rss/rss.xml"),
    ("Játék", "IGN Hungary", "https://hu.ign.com/feed.xml"),
    ("Játék", "Player", "https://player.hu/feed/"),
    ("Tudomány", "Qubit", "https://qubit.hu/feed"),
    ("Gazdaság", "Portfolio", "https://www.portfolio.hu/rss/all.xml"),
    ("Életmód", "NLC", "https://nlc.hu/feed/"),
    ("Akadálymentesség", "MVGYOSZ", "https://www.mvgyosz.hu/feed/"),
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
    category: str = ""

    def label(self) -> str:
        """A legördülőben megjelenő név, kategória-címkével, pl. „[IT] HWSW"."""
        name = self.title or self.url
        return f"[{self.category}] {name}" if self.category else name

    def to_record(self) -> dict:
        return {"url": self.url, "title": self.title,
                "category": self.category}

    @classmethod
    def from_record(cls, r: dict) -> "NewsFeed":
        return cls(url=r["url"], title=r.get("title", ""),
                   category=r.get("category", ""))


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
        self.feeds = [NewsFeed.from_record(r)
                      for r in store.load_news_feeds()]
        # a bővített, kategorizált beépített forrásokat EGYSZER hozzáadjuk a
        # meglévőkhöz is (frissítéskor); a felhasználó saját forrásai és
        # törlései megmaradnak (marker fájl jelzi, hogy már megtörtént)
        marker = store.CONFIG_DIR / "news_defaults_v2.done"
        if not marker.exists():
            by_url = {f.url: f for f in self.feeds}
            for cat, title, url in DEFAULT_FEEDS:
                if url in by_url:
                    f = by_url[url]
                    if not f.category:          # régi, kategória nélküli elem
                        f.category, f.title = cat, title
                else:
                    self.feeds.append(NewsFeed(url=url, title=title,
                                               category=cat))
            self.save()
            try:
                store.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                marker.write_text("ok", encoding="utf-8")
            except OSError:
                pass

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
