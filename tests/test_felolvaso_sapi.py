"""felolvaso: VALÓDI (nem mockolt) hangszintézis-teszt HÁTTÉRSZÁLON.

Herman Tibor auditja jogosan kifogásolta, hogy a korábbi tesztek csak
forráskód-szöveget néztek, ezért NEM foghatták meg a valódi futási hibát: a SAPI
COM a `_narrate`/`_prefetch` HÁTTÉRSZÁLÁN CoInitialize nélkül elszáll
(„CoInitialize has not been called"), és a kivétel némán elnyelődött → néma
narráció. Ez a teszt a TÉNYLEGES szintézist futtatja egy worker szálon, pont úgy,
ahogy a modul – így ez a regresszió nem térhet vissza észrevétlenül.
"""

import os
import threading

import pytest

pytest.importorskip("wx")
narrator = pytest.importorskip(
    "modules_src.felolvaso.felolvaso_mod.narrator")


def _first_sapi_voice():
    try:
        for lbl, eng, vid in narrator.voice_options():
            if eng == "sapi":
                return vid
    except Exception:
        pass
    return None


def test_sapi_szintezis_hatterszalon():
    """A LÉNYEG: SAPI-hang szintézise egy WORKER szálon (CoInitialize a COM-hoz).
    E nélkül élesben `com_error: CoInitialize has not been called` a némaság oka."""
    vid = _first_sapi_voice()
    if not vid:
        pytest.skip("nincs telepített SAPI-hang ezen a gépen")
    res = {}

    def work():
        try:
            p = narrator.synth_to_file("sapi", vid, "Ez egy teszt mondat.",
                                       rate=7)
            res["size"] = os.path.getsize(p)
            os.remove(p)
        except Exception as e:      # noqa: BLE001 – a hibát a teszt jelenti
            res["err"] = repr(e)

    t = threading.Thread(target=work)
    t.start()
    t.join(30)
    assert "err" not in res, f"SAPI a háttérszálon elszállt: {res.get('err')}"
    assert res.get("size", 0) > 0, "a SAPI üres hangfájlt adott"


def test_sok_egymas_utani_sapi_cue():
    """Egy filmnél sok cue követi egymást ugyanazon a worker-mintán – ne
    ütközzenek a tempfájlok, és ne fogyjon el a COM."""
    vid = _first_sapi_voice()
    if not vid:
        pytest.skip("nincs telepített SAPI-hang ezen a gépen")
    paths = []
    errs = []

    def work():
        for i in range(6):
            try:
                p = narrator.synth_to_file("sapi", vid, f"Mondat {i}.", rate=7)
                paths.append(p)
            except Exception as e:      # noqa: BLE001
                errs.append(repr(e))

    t = threading.Thread(target=work)
    t.start()
    t.join(60)
    try:
        assert not errs, f"háttérszálas SAPI-hibák: {errs}"
        assert len(paths) == 6
        assert len(set(paths)) == 6, "a tempfájlnevek ütköztek (nem egyediek)"
        for p in paths:
            assert os.path.getsize(p) > 0
    finally:
        for p in paths:
            try:
                os.remove(p)
            except OSError:
                pass
