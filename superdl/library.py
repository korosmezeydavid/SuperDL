"""Könyvtár és könyvjelzők: melyik könyvet hol hagyta abba a felhasználó.

Könyvenként (a fájl elérési útja szerint) megjegyzi a felolvasási pozíciót
(karakterben), a teljes hosszt, a választott TTS-motort és hangot. Így a
felolvasás bármikor onnan folytatható, ahol abbamaradt.
"""

import time
from dataclasses import dataclass, field

from . import store


@dataclass
class Bookmark:
    path: str
    title: str = ""
    engine_key: str = "edge"
    voice_id: str = ""
    rate: int = 0
    pitch: int = 0
    pos_char: int = 0
    total_chars: int = 0
    updated: float = field(default_factory=time.time)

    def percent(self) -> int:
        if self.total_chars <= 0:
            return 0
        return max(0, min(100, round(self.pos_char / self.total_chars * 100)))

    def to_record(self) -> dict:
        return {"path": self.path, "title": self.title,
                "engine_key": self.engine_key, "voice_id": self.voice_id,
                "rate": self.rate, "pitch": self.pitch,
                "pos_char": self.pos_char, "total_chars": self.total_chars,
                "updated": self.updated}

    @classmethod
    def from_record(cls, r: dict) -> "Bookmark":
        return cls(path=r["path"], title=r.get("title", ""),
                   engine_key=r.get("engine_key", "edge"),
                   voice_id=r.get("voice_id", ""),
                   rate=int(r.get("rate", 0)), pitch=int(r.get("pitch", 0)),
                   pos_char=int(r.get("pos_char", 0)),
                   total_chars=int(r.get("total_chars", 0)),
                   updated=r.get("updated", 0.0))


class Library:
    def __init__(self):
        self.items: list[Bookmark] = [
            Bookmark.from_record(r) for r in store.load_library()]

    def save(self) -> None:
        store.save_library([b.to_record() for b in self.items])

    def get(self, path: str) -> Bookmark | None:
        return next((b for b in self.items if b.path == path), None)

    def recent(self) -> list[Bookmark]:
        return sorted(self.items, key=lambda b: b.updated, reverse=True)

    def upsert(self, path: str, *, title="", engine_key="edge", voice_id="",
               rate=0, pitch=0, pos_char=0, total_chars=0) -> Bookmark:
        b = self.get(path)
        if b is None:
            b = Bookmark(path=path)
            self.items.append(b)
        b.title = title or b.title
        b.engine_key = engine_key or b.engine_key
        b.voice_id = voice_id or b.voice_id
        b.rate, b.pitch = rate, pitch
        b.pos_char, b.total_chars = pos_char, total_chars
        b.updated = time.time()
        self.save()
        return b

    def remove(self, path: str) -> None:
        self.items = [b for b in self.items if b.path != path]
        self.save()
