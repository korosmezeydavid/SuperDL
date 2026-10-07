"""A MediaWiki Parse API teljes cikkének olvasható, natív blokkmodellje."""
from __future__ import annotations

from bs4 import BeautifulSoup, Tag

from .models import ContentBlock, ReaderContent
from .network import FetchError


def _text(node: Tag) -> str:
    return " ".join(node.get_text(" ", strip=True).split())


def extract_wikipedia(html: str, title: str, url: str) -> ReaderContent:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".mw-parser-output") or soup
    for node in list(root.select("script, style, noscript, .mw-editsection, .reference, .noprint, .mw-empty-elt")):
        node.decompose()
    blocks: list[ContentBlock] = []
    meaningful = ("h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "table", "figure", "dl", "div")
    for node in root.find_all(meaningful):
        if node.name == "div" and "thumbcaption" not in node.get("class", []):
            continue
        if any(isinstance(parent, Tag) and parent.name in meaningful
               and (parent.name != "div" or "thumbcaption" in parent.get("class", []))
               for parent in node.parents if parent is not root):
            continue
        if node.name.startswith("h"):
            label = _text(node)
            if label:
                blocks.append(ContentBlock("heading", label, level=min(3, int(node.name[1]))))
        elif node.name == "p":
            value = _text(node)
            if value:
                blocks.append(ContentBlock("paragraph", value))
        elif node.name in ("ul", "ol"):
            items = tuple(value for li in node.find_all("li", recursive=False)
                          if (value := _text(li)))
            if items:
                blocks.append(ContentBlock("list", items=items, ordered=node.name == "ol"))
        elif node.name == "dl":
            for child in node.find_all(("dt", "dd"), recursive=False):
                if value := _text(child):
                    blocks.append(ContentBlock("paragraph", value))
        elif node.name == "table":
            caption = node.find("caption")
            if caption and (value := _text(caption)):
                blocks.append(ContentBlock("heading", value, level=3))
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
        elif node.name == "div":
            if value := _text(node):
                blocks.append(ContentBlock("image_alt", "Kép: " + value))
    if not blocks:
        raise FetchError("no_content", "Ehhez a Wikipédia-cikkhez nincs olvasható tartalom.")
    return ReaderContent(title, tuple(blocks), canonical_url=url)
