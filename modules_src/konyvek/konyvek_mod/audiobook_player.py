# -*- coding: utf-8 -*-
"""Hangoskönyv-lejátszó: egy hangfájl VAGY egy mappányi hangfájl (több sáv) mint
könyv, folytatható pozícióval. A Core `audioengine.Player`-ére épül (ffmpeg +
sounddevice) – mindig elérhető, nincs külön modul-függősége. A hossz a
`videocompose.media_duration` (ffprobe) alapján.

A sáv természetes sorrendben (2 a 10 előtt), a sáv vége automatikusan a
következőre lép (a hívó a `on_track_end`-en át kapja meg)."""
import os
import re
import time

from superdl import store
from superdl.audioengine import Player

try:
    from superdl.videocompose import media_duration
except Exception:                       # ha valamiért nincs, 0 hosszt adunk
    def media_duration(_p):
        return 0.0


AUDIO_KITERJESZTESEK = (".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus",
                        ".wav", ".flac", ".wma", ".mp2", ".mka")


def audio_fajl(path: str) -> bool:
    return os.path.splitext(path or "")[1].lower() in AUDIO_KITERJESZTESEK


def _termeszetes_kulcs(nev: str):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", nev)]


def rel_sav(gyoker: str, ut: str) -> str:
    """A sáv ESZKÖZFÜGGETLEN azonosítója: a könyv-gyökértől számított relatív út
    (perjelekkel). Mappánál a kötet-almappát is tartalmazza (pl. „1. kötet/03.mp3"),
    így a kötetek közti azonos fájlnevek sem ütköznek. Fájl-könyvnél a fájlnév."""
    if gyoker and os.path.isdir(gyoker):
        try:
            return os.path.relpath(ut, gyoker).replace("\\", "/")
        except ValueError:
            return os.path.basename(ut)
    return os.path.basename(ut)


def mappa_savok(mappa: str) -> list:
    """Egy hangoskönyv-mappa ÖSSZES hangfájlja – az ALMAPPÁKBAN is (pl. kötetek) –,
    a relatív út szerinti természetes sorrendben (a kötetek egymás után)."""
    talalt = []
    try:
        for gyoker, _dirs, fajlok in os.walk(mappa):
            for n in fajlok:
                if audio_fajl(n):
                    talalt.append(os.path.join(gyoker, n))
    except OSError:
        return []
    talalt.sort(key=lambda p: _termeszetes_kulcs(rel_sav(mappa, p)))
    return talalt


def ido_str(mp: float) -> str:
    """Másodperc → ó:pp:mm vagy p:mm alak."""
    mp = int(max(0, mp))
    o, m, s = mp // 3600, (mp % 3600) // 60, mp % 60
    return f"{o}:{m:02d}:{s:02d}" if o else f"{m}:{s:02d}"


class AudioBookPlayer:
    def __init__(self, on_track_end=None, on_error=None):
        self.player = Player()
        self.player.on_state = self._on_state
        self.tracks = []            # teljes útvonalak (sávok)
        self.book_root = ""         # a könyv gyökere (a relatív sáv-azonosítóhoz)
        self.idx = 0
        self._dur = {}              # út -> hossz (mp) gyorsítótár
        self._on_track_end = on_track_end
        self._on_error = on_error

    # ---- állapot-visszahívás az audioengine-től ----
    def _on_state(self, text):
        t = (text or "").lower()
        if t.startswith("vége"):
            if self._on_track_end:
                self._on_track_end()
        elif t.startswith("hiba"):
            if self._on_error:
                self._on_error(text)

    # ---- betöltés ----
    def load(self, tracks, book_root=""):
        self.tracks = list(tracks or [])
        self.book_root = book_root or ""
        self.idx = 0

    def track_count(self) -> int:
        return len(self.tracks)

    def current_path(self) -> str:
        return self.tracks[self.idx] if 0 <= self.idx < len(self.tracks) else ""

    def track_id(self, path=None) -> str:
        """Az aktuális (vagy megadott) sáv relatív-út azonosítója."""
        return rel_sav(self.book_root, path or self.current_path())

    def track_index_of(self, sav_id: str):
        """A megadott sáv-azonosító (relatív út VAGY fájlnév) indexe, vagy None."""
        cel = (sav_id or "").replace("\\", "/").lower()
        for i, p in enumerate(self.tracks):        # pontos relatív-út egyezés
            if rel_sav(self.book_root, p).lower() == cel:
                return i
        celnev = os.path.basename(cel)             # visszaesés: csak fájlnév
        for i, p in enumerate(self.tracks):
            if os.path.basename(p).lower() == celnev:
                return i
        return None

    def duration(self, path=None) -> float:
        p = path or self.current_path()
        if not p:
            return 0.0
        if p not in self._dur:
            try:
                self._dur[p] = float(media_duration(p) or 0.0)
            except Exception:
                self._dur[p] = 0.0
        return self._dur[p]

    # ---- vezérlés ----
    def play_track(self, i: int, at: float = 0.0):
        if not (0 <= i < len(self.tracks)):
            return
        self.idx = i
        self.player.play(self.tracks[i],
                         title=os.path.basename(self.tracks[i]),
                         start=max(0.0, at))

    def play(self):
        """Folytatás: ha épp szünetel/aktív, folytatja; különben az aktuális
        sávot indítja."""
        if self.player.is_active():
            self.player.resume()
        else:
            self.play_track(self.idx, 0.0)

    def pause(self):
        self.player.pause()

    def toggle_pause(self) -> bool:
        if not self.player.is_active():
            self.play_track(self.idx, 0.0)
            return False
        return self.player.toggle_pause()

    def stop(self):
        self.player.stop()

    def position(self) -> float:
        return self.player.position()

    def is_paused(self) -> bool:
        return self.player.is_paused()

    def is_active(self) -> bool:
        return self.player.is_active()

    def seek(self, sec: float):
        self.player.seek(max(0.0, sec))

    def relative_seek(self, delta: float):
        self.player.relative_seek(delta)

    def set_volume(self, v: float):
        self.player.set_volume(v)

    def next_track(self) -> bool:
        if self.idx + 1 < len(self.tracks):
            self.play_track(self.idx + 1, 0.0)
            return True
        return False

    def prev_track(self) -> bool:
        if self.idx > 0:
            self.play_track(self.idx - 1, 0.0)
            return True
        return False

    def close(self):
        try:
            self.player.stop()
        except Exception:
            pass


_LIB_FILE = store.CONFIG_DIR / "audiobook_library.json"


def konyv_kulcs(path: str, is_dir: bool) -> str:
    """Eszközfüggetlen kulcs a hangoskönyvhöz: a mappa- vagy fájlnév kisbetűvel."""
    p = (path or "").rstrip("/\\")
    return os.path.basename(p).strip().lower()


class AudioLibrary:
    """A megnyitott hangoskönyvek POLCA: teljes út + folytatási pozíció, hogy
    kilépés után is meglegyenek, és egy Enterrel visszatölthetők legyenek onnan,
    ahol abbahagytad. A könyvjelzők ettől függetlenül a közös bookmark-tárban."""

    def __init__(self):
        self.items = list(store.load_json(_LIB_FILE, []) or [])

    def save(self):
        store.save_json(_LIB_FILE, self.items)

    def _find(self, kulcs):
        for it in self.items:
            if it.get("key") == kulcs:
                return it
        return None

    def upsert(self, path, title, is_dir, track="", ms=0) -> dict:
        """Felveszi/frissíti a polcon (a meglévő folytatást megtartja, ha most
        nem adunk újat)."""
        k = konyv_kulcs(path, is_dir)
        it = self._find(k)
        if it is None:
            it = {"key": k, "track": "", "ms": 0}
            self.items.append(it)
        it["path"] = path
        it["title"] = title
        it["is_dir"] = bool(is_dir)
        if track:
            it["track"] = os.path.basename((track or "").replace("\\", "/"))
        if ms:
            it["ms"] = int(ms)
        it["updated"] = time.time()
        self.save()
        return it

    def set_resume(self, kulcs, track, ms):
        it = self._find(kulcs)
        if it is not None:
            it["track"] = os.path.basename((track or "").replace("\\", "/"))
            it["ms"] = int(max(0, ms))
            it["updated"] = time.time()
            self.save()

    def get(self, kulcs) -> dict:
        return self._find(kulcs)

    def recent(self) -> list:
        return sorted(self.items, key=lambda it: it.get("updated", 0),
                      reverse=True)

    def remove(self, kulcs):
        elotte = len(self.items)
        self.items = [it for it in self.items if it.get("key") != kulcs]
        if len(self.items) != elotte:
            self.save()
