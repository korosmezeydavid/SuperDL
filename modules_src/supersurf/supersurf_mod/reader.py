"""Cikkek főszövegének kinyerése, aktív HTML megjelenítése nélkül."""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from .models import ContentBlock, ReaderContent
from .network import FetchError

NOISE = re.compile(r"(^|[-_\s])(advert|banner|cookie|sidebar|share|social|promo|related|newsletter|reklam|hirdetes|navigation|recommendations)($|[-_\s])", re.I)


def _text(tag) -> str:
    return " ".join(tag.get_text(" ", strip=True).split())


def extract_article(html: str, url: str) -> ReaderContent:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1")
    page_title = _text(title_tag) if title_tag else ""
    if not page_title and soup.title:
        page_title = _text(soup.title)
    if not page_title:
        page_title = urlsplit(url).hostname or "Cikk"
    page_title = re.sub(r"\s+[|–-]\s+[^|–-]+$", "", page_title).strip() or "Cikk"
    author = soup.find("meta", attrs={"name": re.compile(r"^author$", re.I)})
    byline = author.get("content", "").strip() if author else None
    published = soup.find("meta", attrs={"property": "article:published_time"})
    published_at = published.get("content", "").strip() if published else None
    canonical = soup.find("link", rel=lambda x: x and "canonical" in x)
    canonical_url = url
    if canonical and canonical.get("href"):
        candidate = urljoin(url, canonical["href"])
        if urlsplit(candidate).scheme in ("http", "https"):
            canonical_url = candidate

    for tag in soup(["script", "style", "iframe", "form", "nav", "header", "footer",
                     "aside", "noscript", "svg", "template", "button"]):
        tag.decompose()
    for tag in list(soup.find_all(True)):
        if tag.attrs is None:  # egy korábban eltávolított konténer gyermeke
            continue
        if tag.name in ("html", "body", "main", "article"):
            continue
        if tag.has_attr("hidden") or tag.get("aria-hidden") == "true":
            tag.decompose()
            continue
        if NOISE.search(" ".join((str(tag.get("id", "")), " ".join(tag.get("class", []))))):
            tag.decompose()

    candidates = soup.find_all("article") or soup.find_all("main")
    semantic_root = bool(candidates)
    if not candidates:
        candidates = soup.find_all(["div", "section"])
    def score(tag: Tag) -> int:
        paragraphs = tag.find_all("p")
        return sum(max(0, len(_text(p)) - 35) for p in paragraphs) - len(tag.find_all("a")) * 5
    root = max(candidates, key=score) if candidates else (soup.body or soup)
    if not semantic_root and score(root) < 60:
        root = soup.body or soup

    blocks: list[ContentBlock] = []
    # Csak a legfelső releváns elemeket dolgozzuk fel, így nincs ismétlés.
    content_tags = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol",
                    "blockquote", "table", "figure", "dl", "pre", "img", "div")
    for node in root.find_all(content_tags):
        if node.name == "div" and not any("caption" in item.lower() for item in node.get("class", [])):
            continue
        ancestors = list(node.parents)
        if root in ancestors:
            ancestors = ancestors[:ancestors.index(root)]
        if any(parent.name in ("p", "ul", "ol", "blockquote", "table", "figure", "dl", "pre")
               or (parent.name == "div" and any("caption" in item.lower() for item in parent.get("class", [])))
               for parent in ancestors):
            continue
        value = _text(node)
        if not value and node.name != "img":
            continue
        if node.name.startswith("h"):
            if value.casefold() == page_title.casefold():
                continue
            level = min(3, max(2, int(node.name[1])))
            blocks.append(ContentBlock("heading", value, level=level))
        elif node.name in ("ul", "ol"):
            items = tuple(_text(li) for li in node.find_all("li", recursive=False) if _text(li))
            if items:
                blocks.append(ContentBlock("list", items=items, ordered=node.name == "ol"))
        elif node.name == "blockquote":
            blocks.append(ContentBlock("quote", value))
        elif node.name == "table":
            caption = node.find("caption")
            if caption and (label := _text(caption)):
                blocks.append(ContentBlock("heading", label, level=3))
            for row in node.find_all("tr"):
                if row.find_parent("table") is not node:
                    continue
                cells = [_text(cell) for cell in row.find_all(("th", "td"), recursive=False)]
                cells = [cell for cell in cells if cell]
                if cells:
                    blocks.append(ContentBlock("paragraph", ": ".join(cells)))
        elif node.name == "figure":
            caption = node.find("figcaption")
            image = node.find("img")
            label = _text(caption) if caption else (image.get("alt", "").strip() if image else "")
            if label:
                blocks.append(ContentBlock("image_alt", "Kép: " + label))
        elif node.name == "dl":
            for child in node.find_all(("dt", "dd"), recursive=False):
                if label := _text(child):
                    blocks.append(ContentBlock("paragraph", label))
        elif node.name == "pre":
            blocks.append(ContentBlock("paragraph", node.get_text("\n", strip=True)))
        elif node.name == "img":
            if label := node.get("alt", "").strip():
                blocks.append(ContentBlock("image_alt", "Kép: " + label))
        elif node.name == "div":
            blocks.append(ContentBlock("image_alt", "Kép: " + value))
        else:
            blocks.append(ContentBlock("paragraph", value))
    if not any(b.kind in ("paragraph", "list", "quote") for b in blocks):
        raise FetchError("no_content", "Nem sikerült megbízható cikkrészletet találni ezen az oldalon.")
    return ReaderContent(page_title, tuple(blocks), byline=byline,
                         published_at=published_at, canonical_url=canonical_url)
