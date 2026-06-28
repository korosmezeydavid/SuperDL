"""Super M – lejátszási lista (egyszerű, akadálymentes modell) az 1/A
iterációhoz: fájlok/mappa hozzáadása, aktuális elem, előre/hátra léptetés.
A keverő és a crossfade későbbi iterációkban épül erre.
"""

import os
from dataclasses import dataclass
from pathlib import Path

AUDIO_EXTS = (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".wma",
              ".opus")


@dataclass
class Track:
    path: str

    @property
    def title(self) -> str:
        return Path(self.path).stem


class Playlist:
    def __init__(self):
        self.tracks: list[Track] = []
        self.index: int = -1

    def __len__(self):
        return len(self.tracks)

    def add_file(self, path: str) -> bool:
        if not os.path.isfile(path) or any(t.path == path for t in self.tracks):
            return False
        self.tracks.append(Track(path=path))
        if self.index < 0:
            self.index = 0
        return True

    def add_files(self, paths) -> int:
        return sum(1 for p in paths if self.add_file(p))

    def add_folder(self, folder: str) -> int:
        n = 0
        for root, _dirs, names in os.walk(folder):
            for name in sorted(names):
                if name.lower().endswith(AUDIO_EXTS):
                    n += self.add_file(os.path.join(root, name))
        return n

    def remove(self, i: int):
        if 0 <= i < len(self.tracks):
            self.tracks.pop(i)
            if not self.tracks:
                self.index = -1
            elif i <= self.index:
                self.index = max(0, self.index - 1)

    def clear(self):
        self.tracks.clear()
        self.index = -1

    def current(self) -> Track | None:
        return self.tracks[self.index] if 0 <= self.index < len(self.tracks) \
            else None

    def select(self, i: int) -> Track | None:
        if 0 <= i < len(self.tracks):
            self.index = i
            return self.tracks[i]
        return None

    def next(self) -> Track | None:
        if not self.tracks:
            return None
        self.index = (self.index + 1) % len(self.tracks)
        return self.tracks[self.index]

    def prev(self) -> Track | None:
        if not self.tracks:
            return None
        self.index = (self.index - 1) % len(self.tracks)
        return self.tracks[self.index]

    def has_next(self) -> bool:
        return self.index + 1 < len(self.tracks)
