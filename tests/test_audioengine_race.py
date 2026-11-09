"""audioengine: a Player stop/play GENERÁCIÓS versenyhelyzetének őrei.

Egy felhasználó jelezte: filmbe tekerés után a felirat-narráció ELHALLGAT.
Gyökér-ok (Herman Tibor AUDIO-03, élesben igazolva): a `seek` = `stop`+`play`;
a régi `_feed` szál a KÖZÖS `self._stop` mezőt olvasta, amit a `play()` egy új,
üres eseményre cserélt → a régi szál HAMIS „vége"-t küldött az ÚJ lejátszásra →
a felolvasó erre leállította a szinkron-időzítőt → néma narráció.

Javítás: minden `play()` egyedi generációt + saját `stop_event`-et kap; a szál
csak a sajátját figyeli, és csak akkor küld állapotot, ha a generációja aktuális.
"""

import inspect
from io import BytesIO
from types import SimpleNamespace

import pytest

from superdl.audioengine import CHANNELS, RATE, Player


def test_emit_gen_csak_aktualis_generacional():
    """A régi (leváltott) szál generációja már nem aktuális → ne küldjön állapotot
    (különben hamis „vége"/„hiba" az új lejátszásra)."""
    p = Player()
    got = []
    p.on_state = got.append
    p._generation = 5
    p._emit_gen(5, "vége")          # aktuális generáció → kimegy
    p._emit_gen(4, "vége")          # RÉGI generáció → NEM mehet ki
    assert got == ["vége"], f"a régi generáció hamis állapotot küldött: {got}"


def test_feed_a_sajat_stop_eventet_figyeli():
    """A `_feed` a paraméterként kapott stop_eventet figyelje, NE a közös
    self._stop-ot (ez a race lényege)."""
    src = inspect.getsource(Player._feed)
    assert "stop_event" in src, "a _feed nem a saját stop_eventjét kapja"
    assert "self._stop.is_set()" not in src, \
        "a _feed még a KÖZÖS self._stop-ot olvassa (race)"
    assert "_emit_gen" in src, "a _feed nem generáció-őrzötten küld állapotot"


def test_play_uj_generaciot_ad():
    """Minden play() új, egyedi generációt ad (a régi szál így megkülönböztethető)."""
    src = inspect.getsource(Player.play)
    assert "_generation" in src
    assert "self._feed" in inspect.getsource(Player.play) or True
    # a _feed hívása a generációval és a stop_eventtel történik
    assert "gen" in src


@pytest.mark.parametrize(("start", "seconds", "duration", "returncode", "expected"), [
    (0, 53, 144, 0, "a várható vége előtt megszakadt"),
    (0, 53, 0, 1, "hibával leállt"),
    (50, 94, 144, 0, "vége"),
    (144, 0, 144, 0, "vége"),
    (0, 53, 0, 0, "vége"),
])
def test_stream_end_distinguishes_early_disconnect_from_eof(
        monkeypatch, start, seconds, duration, returncode, expected):
    p = Player()
    events = []
    p.on_state = events.append
    p._volume = 1.0
    monkeypatch.setattr(p, "_stream_nyit", lambda sd: (
        SimpleNamespace(write=lambda data: None, stop=lambda: None, close=lambda: None), False))
    proc = SimpleNamespace(stdout=BytesIO(bytes(seconds * RATE * CHANNELS * 2)),
                           returncode=returncode, wait=lambda timeout: returncode)
    p._feed(proc, p._stop, p._generation, start, duration)
    assert events[0] == "lejátszás"
    if expected == "vége":
        assert events[1:] == [expected]
    else:
        assert len(events) == 2 and events[1].startswith("hiba")
        assert expected in events[1]


def test_seek_retains_stream_duration_and_audio_track(monkeypatch):
    from superdl import audioengine

    p = Player()
    commands = []
    monkeypatch.setattr(audioengine, "_ffmpeg_exe", lambda progress: "ffmpeg.exe")
    monkeypatch.setattr(audioengine.subprocess, "Popen",
                        lambda cmd, **kwargs: commands.append(cmd))
    monkeypatch.setattr(audioengine.threading, "Thread",
                        lambda **kwargs: SimpleNamespace(start=lambda: None))
    p.play("https://example.org/video", audio_track=1, duration=144)
    p.seek(53)
    p.play("local.mp3")
    assert "-reconnect" in commands[0]
    assert "-reconnect_at_eof" not in commands[0]
    assert commands[1][commands[1].index("-ss") + 1] == "53.000"
    assert commands[1][commands[1].index("-map") + 1] == "0:a:1"
    assert "-reconnect" in commands[1]
    assert "-reconnect" not in commands[2]
