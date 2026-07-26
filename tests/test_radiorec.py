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
         size=100_000, stopped=False, tail=(), recorded=None):
    r = rr.ActiveRecording("Teszt", url, tmp_path, duration_s=duration)
    r.start_time = datetime.now() - timedelta(seconds=elapsed)
    r.path.parent.mkdir(parents=True, exist_ok=True)
    r.path.write_bytes(b"x" * size)
    if recorded is not None:
        # a ténylegesen rögzített hang hossza (ffprobe helyett a teszthez)
        r._recorded_seconds = lambda: recorded
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
    assert _rec(tmp_path, duration=60, recorded=60).status == "kész"


def test_idozitett_korai_veg_hiba(tmp_path):
    r = _rec(tmp_path, duration=60, recorded=10, tail=["Server returned 404"])
    assert r.status == "hiba" and "VÁRATLANUL" in r.error


def test_burst_rovid_faliora_de_teljes_hang_kesz(tmp_path):
    """A JAVÍTÁS MAGJA: az élő stream puffer-lökete miatt a fali óra RÖVID
    (pl. 3 mp), de a kért HANG megvan (60 mp) → KÉSZ, nem hamis „megszakadt"."""
    assert _rec(tmp_path, duration=60, elapsed=3, recorded=60).status == "kész"


def test_ures_fajl_hiba_okkal(tmp_path):
    r = _rec(tmp_path, size=10, elapsed=1, tail=["HTTP error 403 Forbidden"])
    assert r.status == "hiba"
    assert "nem elérhető" in r.error and "403" in r.error


def test_premature_logika(tmp_path):
    r = rr.ActiveRecording("T", "http://x", tmp_path, duration_s=None)
    assert r._premature() is True       # kézi (F9): minden nem-user vég váratlan
    r.duration_s = 100
    r._recorded_seconds = lambda: 100
    assert r._premature() is False      # a kért HANGOT rögzítette
    r._recorded_seconds = lambda: 50
    assert r._premature() is True       # feleannyi hang → megszakadt


def test_reconnect_csak_http_nal():
    """VÉDŐKAPU: a -reconnect a HTTP-protokoll kapcsolója; nem-http forrásnál az
    ffmpeg „Option reconnect not found"-dal azonnal elszállna."""
    src = inspect.getsource(rr.ActiveRecording.start)
    assert '"-reconnect", "1"' in src
    assert 'startswith(("http://", "https://"))' in src
    # a hibakimenet NEM mehet a kukába (különben néma a megállás)
    assert "stderr=subprocess.PIPE" in src


def test_out_path_vezeto_szokoz_nem_okoz_winerror(tmp_path):
    """A célmappa értékében lévő VEZETŐ/ZÁRÓ szóköz Windowson WinError 123-at
    okozott (' C:\\...' → érvénytelen útvonal, nem jött létre a Rádiófelvételek
    mappa). Az _out_path most trimmel, így a mappa létrejön."""
    p = rr._out_path(f"  {tmp_path}  ", "Hobby Rádió",
                     datetime(2026, 7, 25, 20, 0, 0))
    assert p.parent.is_dir()
    assert not str(p).startswith(" ")
    assert "Rádiófelvételek" in str(p)


def test_norm_opts_alap_egyeni_es_hibas():
    o = rr._norm_opts({})
    assert o["encoder"] == "libmp3lame" and o["bitrate"] == "192k"
    assert o["chunk_seconds"] == 0 and o["ext"] == "mp3"
    o2 = rr._norm_opts({"format": "opus", "bitrate_kbps": 96,
                        "chunk_minutes": 30, "sample_rate": 48000})
    assert o2["encoder"] == "libopus" and o2["ext"] == "ogg"
    assert o2["chunk_seconds"] == 1800 and o2["bitrate"] == "96k"
    assert o2["sample_rate"] == 48000
    o3 = rr._norm_opts({"format": "x", "bitrate_kbps": "nem", "chunk_minutes": -5})
    assert o3["encoder"] == "libmp3lame" and o3["chunk_seconds"] == 0


def test_darabolt_felvetel_szegmens_parancs(tmp_path):
    """Darabolt módban a start() a segment muxert használja, %03d-mintával."""
    r = rr.ActiveRecording("T", "http://x/s", tmp_path,
                           options={"chunk_minutes": 5, "bitrate_kbps": 128})
    assert r.chunk_seconds == 300
    assert r._pattern and "%03d" in r._pattern
    src = inspect.getsource(rr.ActiveRecording.start)
    assert '"-f", "segment"' in src and '"-segment_time"' in src


def test_output_files_es_hely_szoveg_darabolt(tmp_path):
    r = rr.ActiveRecording("T", "http://x/s", tmp_path,
                           options={"chunk_minutes": 1})
    (r._folder / f"{r._stem} - 000.mp3").write_bytes(b"x" * 20000)
    (r._folder / f"{r._stem} - 001.mp3").write_bytes(b"x" * 20000)
    assert len(r._output_files()) == 2
    assert "2 részben" in r.hely_szoveg()
    assert r._has_audio() is True


def test_start_manual_last_error_a_valodi_okot_adja(tmp_path, monkeypatch):
    """Ha a felvétel nem indul (pl. hiányzó ffmpeg), a kezelő a VALÓDI okot a
    last_error-ba teszi – ezt a rádióablak HANGOSAN felolvassa, nem néma."""
    mgr = rr.RecordManager(lambda: str(tmp_path))
    mgr._stop.set()                                  # az időzítő-szál ne dolgozzon
    # színleljük, hogy nincs ffmpeg → a start() „hiba"-val tér vissza
    monkeypatch.setattr(rr, "_ffmpeg_exe", lambda *a, **k: None)
    r = mgr.start_manual("Teszt", "http://x/stream")
    assert r is None
    assert "ffmpeg" in mgr.last_error


# ---- időzítés-módok: egyszeri / N alkalom / kikapcsolásig ----------------

def _sched(**kw):
    base = dict(id="s1", station_name="Rádió", url="http://x/s",
                start_h=20, start_m=0, end_h=21, end_m=0)
    base.update(kw)
    return rr.Schedule(**base)


def test_schedule_describe_haromfele_mod():
    # egyszeri → „utána törlődik”
    assert "utána törlődik" in _sched(repeat="once", date="2026-08-01").describe()
    # naponta + N alkalom → „még N alkalom”
    d = _sched(repeat="daily", count=5).describe()
    assert "minden nap" in d and "még 5 alkalom" in d
    # hetente + kikapcsolásig → „kikapcsolásig”
    w = _sched(repeat="weekly", weekdays=[0], count=0).describe()
    assert "kikapcsolásig" in w


def test_schedule_count_koroundtrip_fields():
    """A count mező benne van a FIELDS-ben és túléli a mentés/betöltés kört."""
    from dataclasses import asdict
    assert "count" in rr.RecordManager.FIELDS
    d = asdict(_sched(repeat="daily", count=3))
    s2 = rr.Schedule(**{k: v for k, v in d.items()
                        if k in rr.RecordManager.FIELDS})
    assert s2.count == 3


class _FakeRec:
    """Sikeres felvételt színlelő minimál-ActiveRecording a _fire teszteléséhez."""
    def __init__(self, station_name, url, base_dir, **kw):
        from pathlib import Path
        self.station_name = station_name
        self.path = Path(base_dir) / "fake.mp3"
        self.error = ""
        self.status = "kész"

    def start(self):
        return True


def _fire_mgr(tmp_path, monkeypatch, s):
    monkeypatch.setattr(rr, "ActiveRecording", _FakeRec)
    # a VALÓDI mentett időzítéseket ne írja/olvassa felül a teszt
    monkeypatch.setattr(rr.store, "load_radio_schedule", lambda: [])
    monkeypatch.setattr(rr.store, "save_radio_schedule", lambda *a, **k: None)
    mgr = rr.RecordManager(lambda: str(tmp_path))
    mgr._stop.set()
    mgr.schedules = [s]
    mgr._fire(s, 60, "2026-08-01")
    return mgr


def test_fire_egyszeri_torli_az_idozitot(tmp_path, monkeypatch):
    s = _sched(repeat="once", date="2026-08-01")
    mgr = _fire_mgr(tmp_path, monkeypatch, s)
    assert mgr.schedules == []                       # felvette és eltűnt


def test_fire_n_alkalom_visszaszamol_majd_torol(tmp_path, monkeypatch):
    s = _sched(repeat="daily", count=2)
    mgr = _fire_mgr(tmp_path, monkeypatch, s)
    assert len(mgr.schedules) == 1 and mgr.schedules[0].count == 1
    # a következő nap: még egy tüzelés → most már törlődik
    s.last_run_date = ""
    mgr._fire(s, 60, "2026-08-02")
    assert mgr.schedules == []


def test_fire_kikapcsolasig_marad(tmp_path, monkeypatch):
    s = _sched(repeat="daily", count=0)
    mgr = _fire_mgr(tmp_path, monkeypatch, s)
    assert len(mgr.schedules) == 1 and mgr.schedules[0].count == 0
