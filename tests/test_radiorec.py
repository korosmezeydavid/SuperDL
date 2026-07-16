"""radiorec: a felvétel váratlan megszakadásának kezelése (Laci jelezte: „F9-re
indított felvétel a legváratlanabb pillanatokban leáll, és nem ír semmiféle
hibát"). A javítás: ffmpeg-újracsatlakozás (CSAK http-nél!), a hibakimenet
elmentése, és a korai vég HIBAKÉNT jelzése (eddig csendben „kész" lett)."""

import inspect
import types
from datetime import datetime, timedelta

import pytest

rr = pytest.importorskip("superdl.radiorec")


def _rec(tmp_path, url="http://x/stream", duration=None, elapsed=0,
         size=100_000, stopped=False, tail=()):
    r = rr.ActiveRecording("Teszt", url, tmp_path, duration_s=duration)
    r.start_time = datetime.now() - timedelta(seconds=elapsed)
    r.path.parent.mkdir(parents=True, exist_ok=True)
    r.path.write_bytes(b"x" * size)
    if stopped:
        r._stop.set()
    for t in tail:
        r._err_tail.append(t)
    r._proc = types.SimpleNamespace(wait=lambda: 0, poll=lambda: 0, stderr=None)
    r._watch()
    return r


def test_user_stop_nem_hiba(tmp_path):
    assert _rec(tmp_path, elapsed=300, stopped=True).status == "leállítva"


def test_kezi_felvetel_varatlan_vege_HIBA(tmp_path):
    """A REGRESSZIÓ magja: eddig ez csendben „kész" lett."""
    r = _rec(tmp_path, elapsed=300, tail=["Connection reset by peer"])
    assert r.status == "hiba"
    assert "VÁRATLANUL megszakadt" in r.error
    assert "megmaradt" in r.error                 # a fájl használható – mondjuk ki
    assert "Connection reset by peer" in r.error  # a VALÓDI ffmpeg-üzenet


def test_idozitett_teljes_hossz_kesz(tmp_path):
    assert _rec(tmp_path, duration=60, elapsed=60).status == "kész"


def test_idozitett_korai_veg_hiba(tmp_path):
    r = _rec(tmp_path, duration=60, elapsed=10, tail=["Server returned 404"])
    assert r.status == "hiba" and "VÁRATLANUL" in r.error


def test_ures_fajl_hiba_okkal(tmp_path):
    r = _rec(tmp_path, size=10, elapsed=1, tail=["HTTP error 403 Forbidden"])
    assert r.status == "hiba"
    assert "nem elérhető" in r.error and "403" in r.error


def test_premature_logika():
    r = rr.ActiveRecording.__new__(rr.ActiveRecording)
    r.duration_s = None                 # kézi (F9): minden nem-user vég váratlan
    assert r._premature() is True
    r.duration_s = 100
    r.start_time = datetime.now() - timedelta(seconds=100)
    assert r._premature() is False      # kitöltötte a kért időt
    r.start_time = datetime.now() - timedelta(seconds=50)
    assert r._premature() is True       # feleannyi → megszakadt


def test_reconnect_csak_http_nal():
    """VÉDŐKAPU: a -reconnect a HTTP-protokoll kapcsolója; nem-http forrásnál az
    ffmpeg „Option reconnect not found"-dal azonnal elszállna."""
    src = inspect.getsource(rr.ActiveRecording.start)
    assert '"-reconnect", "1"' in src
    assert 'startswith(("http://", "https://"))' in src
    # a hibakimenet NEM mehet a kukába (különben néma a megállás)
    assert "stderr=subprocess.PIPE" in src
