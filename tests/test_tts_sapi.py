"""tts.SapiEngine: a HÁTTÉRSZÁLAS COM-inicializálás GYÖKÉR-őre.

Mély hiba-audit, Mérföldkő 1: a hangoskönyv-készítő (`bookwin`) a
`audiobook.build`-ot HÁTTÉRSZÁLON hívja, ami `tts.ENGINES["sapi"].synth`-et →
`Dispatch("SAPI.SpVoice")`-t hív. A SapiEngine EDDIG nem inicializálta a COM-ot,
ezért háttérszálon `com_error (CoInitialize has not been called)` → SAPI-hanggal
a hangoskönyv-készítés elszállt (élesben igazolt). GYÖKÉR-FIX: a SapiEngine maga
hív CoInitialize-t (`_sapi_com`), így MINDEN hívó (audiobook, narrator, speech,
hangalámondás) egyszerre védve. Ez a teszt a VALÓDI (nem mockolt) szintézist
futtatja worker szálon.
"""

import inspect
import os
import tempfile
import threading

import pytest

from superdl import tts


def _sapi_voice():
    try:
        vs = tts.ENGINES["sapi"].voices("")
        return vs[0].id if vs else None
    except Exception:
        return None


def test_sapi_com_helper_letezik():
    """A SapiEngine maga inicializálja a COM-ot (a synth/voices `_sapi_com`-ot
    használ), nem a hívóra bízza."""
    assert hasattr(tts, "_sapi_com")
    assert "_sapi_com" in inspect.getsource(tts.SapiEngine.synth)
    assert "_sapi_com" in inspect.getsource(tts.SapiEngine.voices)
    assert "CoInitialize" in inspect.getsource(tts._sapi_com)


def test_sapi_synth_hatterszalon():
    """A LÉNYEG: SAPI-szintézis WORKER szálon – e nélkül a hangoskönyv-készítő
    SAPI-hanggal elszáll."""
    vid = _sapi_voice()
    if not vid:
        pytest.skip("nincs telepített SAPI-hang ezen a gépen")
    d = tempfile.mkdtemp(prefix="tts_sapi_test_")
    res = {}

    def work():
        try:
            p = tts.ENGINES["sapi"].synth("Ez egy teszt mondat.", vid,
                                          os.path.join(d, "p0"))
            res["size"] = os.path.getsize(p)
        except Exception as e:      # noqa: BLE001 – a hibát a teszt jelenti
            res["err"] = repr(e)

    t = threading.Thread(target=work)
    t.start()
    t.join(30)
    import shutil
    shutil.rmtree(d, ignore_errors=True)
    assert "err" not in res, f"SAPI a háttérszálon elszállt: {res.get('err')}"
    assert res.get("size", 0) > 0


def test_sapi_voices_hatterszalon():
    """A hanglista lekérése is menjen worker szálon (a bookwin/narrator is így
    hívhatja)."""
    if not _sapi_voice():
        pytest.skip("nincs telepített SAPI-hang ezen a gépen")
    res = {}

    def work():
        try:
            res["n"] = len(tts.ENGINES["sapi"].voices(""))
        except Exception as e:      # noqa: BLE001
            res["err"] = repr(e)

    t = threading.Thread(target=work)
    t.start()
    t.join(15)
    assert "err" not in res, f"voices() háttérszálon elszállt: {res.get('err')}"
    assert res.get("n", 0) >= 1
