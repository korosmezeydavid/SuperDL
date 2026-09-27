"""Turai László (2026-09-27): a végighallgatott hangoskönyv újranyitva ne a
legutóbbi megállítás helyéről, hanem az ELEJÉRŐL induljon."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "modules_src" / "konyvek"))


def _stub():
    pytest.importorskip("wx")
    from konyvek_mod import audiobookwin as W

    class Lib:
        def __init__(self):
            self.mentve = None

        def set_resume(self, kulcs, track, ms):
            self.mentve = (kulcs, track, ms)

    class Player:
        idx = 4
        tracks = ["a", "b", "c", "d", "e"]

        def next_track(self):
            return False            # ez volt az utolsó sáv

        def track_count(self):
            return len(self.tracks)

        def track_id(self):
            return "e.mp3"

        def position(self):
            return 1234.0

    class Lista:
        kijelolt = None

        def SetSelection(self, i):
            self.kijelolt = i

    # az ablakosztály neve modulonként eltérhet: megkeressük
    osztaly = next(v for v in vars(W).values()
                   if isinstance(v, type) and hasattr(v, "_on_track_end")
                   and hasattr(v, "_save_resume"))

    class Stub:
        _on_track_end = osztaly._on_track_end
        _save_resume = osztaly._save_resume
        _play = osztaly._play

        def __init__(self):
            self._closing = False
            self._vegere_ert = False
            self._bookkey = "k"
            self._resume_at = (4, 99000)
            self.lib = Lib()
            self.player = Player()
            self.sav_lista = Lista()
            self.mondott = []

        def _mond(self, s):
            self.mondott.append(s)

        def _refresh_shelf(self):
            pass
    return Stub()


def test_a_konyv_vegen_az_elejere_all():
    s = _stub()
    s._on_track_end()
    assert s.lib.mentve == ("k", "", 0)
    assert s._resume_at is None and s.player.idx == 0
    assert s.sav_lista.kijelolt == 0
    assert "elejéről" in s.mondott[-1]
    # bezáráskor is az eleje marad (nem az utolsó sáv vége)
    s.lib.mentve = None
    s._save_resume()
    assert s.lib.mentve == ("k", "", 0)
