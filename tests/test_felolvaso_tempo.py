"""felolvaso: a MÉRÉSSEL feltárt szinkron-problémák javításának őrei.

Mérés (valósághű film-ritmus: 45 karakteres sorok 3,1 mp-enként) alap tempón és
előre-gyártás nélkül: SAPI 0/4 sor fért bele (6,1 mp csúszás), Edge 0/4 (11,8 mp)
– egy egész filmen ez percekre nőtt volna. A javítás után: SAPI/eSpeak 4/4 nulla
csúszással, Edge 3/4 (0,5 mp). Ezek a tesztek azt őrzik, hogy ne csússzon vissza.
"""

import pytest

pytest.importorskip("wx")
W = pytest.importorskip("modules_src.felolvaso.felolvaso_mod.felolvasowin")


def test_alap_tempo_gyors():
    """Az alapértelmezett tempó NEM lehet 0: a mérés szerint úgy nem tartja a
    lépést a filmfelirattal. +7 körül kell lennie."""
    assert W.DEFAULT_RATE >= 5, "az alap tempó túl lassú – csúszni fog a felolvasás"
    assert W.DEFAULT_RATE <= 10


def test_ducking_ertelmes():
    assert 0.0 < W.DUCK < 0.5      # a film halkul, de nem néma


def test_elore_gyartas_letezik():
    """Az előre-gyártás nélkül az Edge neurális hang (soronként ~1,6 mp hálózati
    válaszidő) még gyors tempón sem bírja a film-ritmust."""
    for meth in ("_prefetch", "_prefetch_done", "_drop_ahead"):
        assert hasattr(W.FelolvasoFrame, meth), f"hiányzik: {meth}"


def test_zarasi_vedelem():
    """Zárás közben futó gyártó-szál ne nyúljon a megszűnt ablakhoz."""
    import inspect
    src = inspect.getsource(W.FelolvasoFrame)
    assert "_closing" in src
    assert "self._closing = True" in src


def test_ugras_eldobja_az_elore_gyartast():
    import inspect
    for meth in (W.FelolvasoFrame._seek, W.FelolvasoFrame._stop):
        assert "_drop_ahead" in inspect.getsource(meth), \
            "ugrás/leállítás után az előre gyártott hang elavult – el kell dobni"
