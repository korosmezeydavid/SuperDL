"""p2p (fájlküldés): a záráskori megerősítés és a haladás-% őrei.

Felhasználói jelzés (2026-07): (1) az ablak bezárása menet közben megerősítés
NÉLKÜL megszakította a küldést; (2) jó lenne menet közben lekérdezni a %-ot.
Mély hiba-audit, Mérföldkő 2 (2b + 2c).
"""

import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent
                       / "modules_src" / "p2p"))
p2p = pytest.importorskip("p2p_mod.p2p")


class _FakeStream:
    """Karakterenként adja vissza a szöveget (mint egy subprocess-pipe)."""

    def __init__(self, s):
        self._s = s
        self._i = 0

    def read(self, n):
        if self._i >= len(self._s):
            return ""
        ch = self._s[self._i]
        self._i += 1
        return ch


def test_kod_es_szazalek_kiolvasas_cr_frissitesbol():
    """A wormhole a haladást KOCSIVISSZÁVAL (\\r) frissíti; a kódot és a %-ot is
    ki kell tudni olvasni belőle (a sima soronkénti olvasás nem látná)."""
    out = ("Wormhole code is: 7-alma-traktor\n"
           "Sending: 0%|  | 0/13\rSending: 45%| | 6/13\r"
           "Sending: 100%|xx| 13/13\ncomplete\n")
    segs = list(p2p._iter_segments(_FakeStream(out)))
    codes = [p2p._CODE_RE.search(s).group(1) for s in segs
             if p2p._CODE_RE.search(s)]
    pcts = [int(p2p._PCT_RE.search(s).group(1)) for s in segs
            if p2p._PCT_RE.search(s)]
    assert codes == ["7-alma-traktor"]
    assert pcts == [0, 45, 100]


def test_nincs_hide_progress():
    """A --hide-progress-t EL kell venni, különben a wormhole nem ad %-ot."""
    src = inspect.getsource(p2p.SendSession._run)
    assert "--hide-progress" not in src
    assert "on_progress" in src


def test_sessions_on_progress_parameter():
    """Mindkét munkamenet fogadjon on_progress callbacket."""
    assert "on_progress" in inspect.signature(p2p.SendSession.__init__).parameters
    assert "on_progress" in \
        inspect.signature(p2p.ReceiveSession.__init__).parameters


def test_ablak_zaraskor_megerosites_es_closing_or():
    """Az ablak záráskor kérdezzen rá folyó átvitelnél (Veto), és a
    háttér-callbackek _closing alatt lépjenek ki (ne nyúljanak megszűnt ablakhoz)."""
    pytest.importorskip("wx")
    from p2p_mod import p2pwin
    close_src = inspect.getsource(p2pwin.P2PFrame._on_close)
    assert "MessageBox" in close_src and "Veto" in close_src
    assert "_closing" in close_src
    # a haladás-callback véd a záráskor
    prog_src = inspect.getsource(p2pwin.P2PFrame._send_progress)
    assert "_closing" in prog_src
    # F8 = haladás bemondása
    assert hasattr(p2pwin.P2PFrame, "_announce_progress")
    assert "WXK_F8" in inspect.getsource(p2pwin.P2PFrame._on_help_key)
