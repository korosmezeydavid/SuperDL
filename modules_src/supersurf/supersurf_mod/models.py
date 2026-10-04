"""A Super Surf megjelenítéstől független adatszerződései."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import uuid4

QueryKind = Literal["wikipedia_search", "article_url", "weather", "exchange_rate", "dictionary"]
Status = Literal["success", "empty", "error", "cancelled"]


@dataclass(frozen=True)
class ResearchQuery:
    kind: QueryKind
    input: str
    language: str = "hu"
    parameters: dict[str, str] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class ContentBlock:
    kind: Literal["heading", "paragraph", "list", "quote", "link", "image_alt"]
    text: str = ""
    level: int = 0
    items: tuple[str, ...] = ()
    ordered: bool = False
    url: str | None = None


@dataclass(frozen=True)
class ReaderContent:
    title: str
    blocks: tuple[ContentBlock, ...]
    byline: str | None = None
    published_at: str | None = None
    canonical_url: str | None = None
    excerpt: str | None = None

    def plain_text(self) -> str:
        parts = [self.title]
        if self.byline:
            parts.append(self.byline)
        for block in self.blocks:
            if block.kind == "list":
                parts.append("\n".join(
                    f"{i}. {x}" if block.ordered else f"• {x}"
                    for i, x in enumerate(block.items, 1)))
            elif block.text:
                parts.append(block.text)
        if self.canonical_url:
            parts.append(f"Forrás: {self.canonical_url}")
        return "\n\n".join(parts)


@dataclass(frozen=True)
class ResearchError:
    code: str
    message_hu: str
    retryable: bool = False


@dataclass(frozen=True)
class ResearchResult:
    request_id: str
    kind: QueryKind
    status: Status
    title: str | None = None
    content: ReaderContent | None = None
    source_name: str | None = None
    source_url: str | None = None
    retrieved_at: datetime | None = None
    error: ResearchError | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResearchProgress:
    request_id: str
    phase: Literal["validating", "fetching", "extracting", "rendering"]
    message_hu: str
