# -*- coding: utf-8 -*-
"""Nevesített könyvjelzők – eszközök közt szinkronizálható tár.

A könyvjelző ESZKÖZFÜGGETLEN kulccsal (fájlnév) azonosít egy könyvet, mert az
abszolút útvonal a PC-n és a telefonon más. A `preview` (a hely szövegkezdete)
teszi lehetővé, hogy egy másik eszközön PONTOSAN megtaláljuk a helyet akkor is,
ha a karakter-offset eltér (más kivonatolás miatt). A `created` epoch MILLI-
szekundum – ugyanaz a mértékegység, mint az Android oldalon –, ez a dedup-kulcs.
"""
import os
import time
from dataclasses import dataclass

from superdl import store

_FILE = store.CONFIG_DIR / "book_bookmarks.json"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _kulcs(nev: str) -> str:
    """Eszközfüggetlen könyv-kulcs: a fájlnév kisbetűsítve."""
    return os.path.basename((nev or "").replace("\\", "/")).strip().lower()


@dataclass
class Bookmark:
    book: str            # fájlnév/mappanév (kulcs), pl. "regeny.epub" vagy "sorozat"
    title: str = ""
    char: int = 0        # SZÖVEG: karakter-offset (eszközfüggő, tájékoztató)
    preview: str = ""    # a hely szövegkezdete – ez alapján más eszközön is megtalálható
    created: int = 0     # epoch MILLISZEKUNDUM (Androiddal egyezően) – dedup-kulcs
    label: str = ""      # opcionális saját címke
    kind: str = "text"   # "text" vagy "audio"
    pos_ms: int = 0      # HANG: pozíció a sávon belül, ezredmásodpercben
    track: str = ""      # HANG: a konkrét sáv FÁJLNEVE a mappán belül ("" = egy fájl)

    @classmethod
    def from_record(cls, r: dict) -> "Bookmark":
        return cls(
            book=str(r.get("book", "")),
            title=str(r.get("title", "")),
            char=int(r.get("char", 0) or 0),
            preview=str(r.get("preview", "")),
            created=int(r.get("created", 0) or 0),
            label=str(r.get("label", "")),
            kind=str(r.get("kind", "text") or "text"),
            pos_ms=int(r.get("pos_ms", 0) or 0),
            track=str(r.get("track", "")),
        )

    def to_record(self) -> dict:
        return {"book": self.book, "title": self.title, "char": self.char,
                "preview": self.preview, "created": self.created,
                "label": self.label, "kind": self.kind, "pos_ms": self.pos_ms,
                "track": self.track}

    def kulcs(self) -> str:
        return _kulcs(self.book)

    def dkey(self):
        """Dedup-kulcs eszközök közt: (fájlnév, létrehozás-ms)."""
        return (_kulcs(self.book), int(self.created))


class BookmarkStore:
    """A nevesített könyvjelzők tára (book_bookmarks.json)."""

    def __init__(self):
        self.items = [Bookmark.from_record(r)
                      for r in store.load_json(_FILE, [])]

    def save(self) -> None:
        store.save_json(_FILE, [b.to_record() for b in self.items])

    def all(self) -> list:
        return list(self.items)

    def for_book(self, nev: str) -> list:
        """Egy adott könyv (fájlnév szerinti) könyvjelzői, legújabb elöl."""
        k = _kulcs(nev)
        ki = [b for b in self.items if b.kulcs() == k]
        ki.sort(key=lambda b: b.created, reverse=True)
        return ki

    def add(self, book: str, title="", char=0, preview="", label="",
            created=None, kind="text", pos_ms=0, track="") -> Bookmark:
        b = Bookmark(book=os.path.basename((book or "").replace("\\", "/")),
                     title=title, char=int(char or 0), preview=preview,
                     created=int(created or _now_ms()), label=label,
                     kind=kind or "text", pos_ms=int(pos_ms or 0),
                     track=os.path.basename((track or "").replace("\\", "/")))
        if not any(x.dkey() == b.dkey() for x in self.items):
            self.items.append(b)
            self.save()
        return b

    def remove(self, book: str, created: int) -> None:
        k = _kulcs(book)
        c = int(created)
        elotte = len(self.items)
        self.items = [b for b in self.items
                      if not (b.kulcs() == k and int(b.created) == c)]
        if len(self.items) != elotte:
            self.save()

    def merge(self, incoming) -> int:
        """Beolvasztja a bejövő könyvjelzőket (dedup: fájlnév+created). Visszaad:
        hány ÚJ került be."""
        van = {b.dkey() for b in self.items}
        uj = 0
        for b in incoming:
            if not isinstance(b, Bookmark):
                b = Bookmark.from_record(b)
            if b.dkey() not in van:
                self.items.append(b)
                van.add(b.dkey())
                uj += 1
        if uj:
            self.save()
        return uj
