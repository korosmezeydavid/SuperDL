# -*- coding: utf-8 -*-
"""Rádió időzített felvétel: éjfélen átnyúló ablak, mappahiba, scheduler-health.

Herman Tibor média-audit: RAD-P0-01 (éjfélen átnyúló ablak kimarad),
RAD-P0-02 (az időzítő némán elnyeli a hibát), RAD-P0-03 (a célmappa-hiba a
felvétel indulása előtt néma marad)."""
from datetime import datetime, timedelta

import pytest

from superdl import radiorec


def _sched(**kw):
    base = dict(id="x", station_name="S", url="http://u/stream",
                start_h=23, start_m=0, end_h=1, end_m=0)
    base.update(kw)
    return radiorec.Schedule(**base)


# ---- RAD-P0-01: éjfélen átnyúló ablak -------------------------------------

def test_ejfeli_ablak_tegnap_kezdodott_ma_folytatodik():
    now = datetime(2026, 8, 4, 0, 30)         # 00:30, a 23:00-01:00 ablakban
    win = radiorec._active_window(_sched(repeat="daily"), now)
    assert win is not None, "az éjfélen átnyúló ablakot aktívnak kell látni"
    start_dt, end_dt, key = win
    assert key == "2026-08-03"                # a TEGNAPI kezdőnap
    assert end_dt == datetime(2026, 8, 4, 1, 0)
    assert int((end_dt - now).total_seconds()) == 30 * 60   # 30 perc hátra


def test_ejfel_utan_pontosan_a_vegen_mar_nem_aktiv():
    now = datetime(2026, 8, 4, 1, 0)          # pont a végén
    assert radiorec._active_window(_sched(repeat="daily"), now) is None


def test_nappali_normal_ablak():
    now = datetime(2026, 8, 4, 10, 30)
    win = radiorec._active_window(
        _sched(start_h=10, start_m=0, end_h=11, end_m=0, repeat="daily"), now)
    assert win is not None and win[2] == "2026-08-04"


def test_weekly_a_kezdonap_hetnapjahoz_meri():
    now = datetime(2026, 8, 4, 0, 30)
    start_day = now.date() - timedelta(days=1)
    # a TEGNAPI (kezdő)nap van felvéve → az éjféli ablak fut
    s = _sched(repeat="weekly", weekdays=[start_day.weekday()])
    assert radiorec._active_window(s, now) is not None
    # ha a MAI nap van felvéve, a tegnap indult ablak NEM fut (a mai 23:00 jövő)
    s2 = _sched(repeat="weekly", weekdays=[now.weekday()])
    assert radiorec._active_window(s2, now) is None


def test_once_a_kezdonapra_illeszkedik():
    now = datetime(2026, 8, 4, 0, 30)
    assert radiorec._active_window(
        _sched(repeat="once", date="2026-08-03"), now) is not None   # tegnap
    assert radiorec._active_window(
        _sched(repeat="once", date="2026-08-04"), now) is None       # ma 23:00


# ---- RAD-P0-03: a célmappa-hiba nem marad néma -----------------------------

def test_celmappa_hiba_nem_nema(tmp_path, monkeypatch):
    monkeypatch.setattr(radiorec, "_ffmpeg_exe", lambda: "ffmpeg")
    # a base_dir egy FÁJL → alá nem hozható létre mappa → OSError
    f = tmp_path / "ez_egy_fajl"
    f.write_text("x", encoding="utf-8")
    rec = radiorec.ActiveRecording("S", "http://u/stream", str(f))
    assert rec.start() is False
    assert rec.status == "hiba"
    assert "célmappa" in rec.error


# ---- RAD-P0-02: scheduler-health + üres tick nem dob -----------------------

def test_scheduler_health_es_ures_tick(monkeypatch, tmp_path):
    monkeypatch.setattr(radiorec.store, "load_radio_schedule", lambda: [])
    m = radiorec.RecordManager(base_dir_getter=lambda: str(tmp_path))
    try:
        assert m.scheduler_health() == {"errors": 0, "last_error": ""}
        m._tick()                             # üres ütemezés – nem dob
    finally:
        m._stop.set()
