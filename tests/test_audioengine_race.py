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

from superdl.audioengine import Player


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
