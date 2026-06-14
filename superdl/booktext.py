"""Könyv-szöveg kinyerése a hangoskönyv-készítőhöz.

Támogatott: TXT, DOCX, EPUB (tiszta szöveg), PDF (best-effort). A
visszaadott Book a címet és a szakaszokat (fejezeteket) tartalmazza – ez
kell az egyben vagy fejezetenkénti MP3-hoz, és a cím a hangos bevezetőhöz.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED = (".txt", ".docx", ".epub", ".pdf")


@dataclass
class Book:
    title: str
    sections: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(s for s in self.sections if s.strip())

    @property
    def chars(self) -> int:
        return sum(len(s) for s in self.sections)


def _clean(t: str) -> str:
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _from_txt(path: Path) -> Book:
    raw = path.read_text(encoding="utf-8", errors="replace")
    return Book(title=path.stem, sections=[_clean(raw)])


def _from_docx(path: Path) -> Book:
    import docx
    d = docx.Document(str(path))
    title = (d.core_properties.title or path.stem).strip() or path.stem
    sections: list[str] = []
    buf: list[str] = []
    for p in d.paragraphs:
        txt = p.text.strip()
        style = (p.style.name or "").lower() if p.style else ""
        if style.startswith("heading") and buf:
            sections.append(_clean("\n".join(buf)))
            buf = []
        if txt:
            buf.append(txt)
    if buf:
        sections.append(_clean("\n".join(buf)))
    if not sections:
        sections = [""]
    return Book(title=title, sections=sections)


def _from_epub(path: Path) -> Book:
    import ebooklib
    from bs4 import BeautifulSoup
    from ebooklib import epub
    book = epub.read_epub(str(path))
    title = path.stem
    try:
        md = book.get_metadata("DC", "title")
        if md:
            title = md[0][0]
    except Exception:
        pass
    sections: list[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        txt = _clean(soup.get_text(separator="\n"))
        if txt:
            sections.append(txt)
    if not sections:
        sections = [""]
    return Book(title=title, sections=sections)


def _from_pdf(path: Path) -> Book:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    title = path.stem
    try:
        if reader.metadata and reader.metadata.title:
            title = reader.metadata.title
    except Exception:
        pass
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            pass
    return Book(title=title, sections=[_clean("\n".join(parts))])


def extract(path: str) -> Book:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".txt":
        return _from_txt(p)
    if ext == ".docx":
        return _from_docx(p)
    if ext == ".epub":
        return _from_epub(p)
    if ext == ".pdf":
        return _from_pdf(p)
    raise ValueError(f"Nem támogatott formátum: {ext}")
