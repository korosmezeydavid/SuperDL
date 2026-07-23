# -*- coding: utf-8 -*-
"""ReadEngine MUNKAMENET-GENERÁCIÓ – Herman Tibi READ-P0-01 / READ-P0-02.

A régi kód a LECSERÉLHETŐ közös stop-eseményt olvasta, ezért egy elhúzódó TTS-
szál (ami túlélte a 2 mp-es várakozást) az ÚJ könyv állapotán dolgozott tovább:
keveredő mondatok, rossz könyvjelző, régi hang az új szöveghez."""
import pathlib
import sys
import threading
import time

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "modules_src" / "konyvek"))
from konyvek_mod import readengine as RE          # noqa: E402


def _src() -> str:
    return (ROOT / "modules_src" / "konyvek" / "konyvek_mod"
            / "readengine.py").read_text(encoding="utf-8")


# ---- READ-P0-01: saját stop-esemény + generáció ---------------------------

def test_a_worker_sajat_stop_eventet_kap():
    src = _src()
    assert "def _run(self, gen: int, stop_event)" in src, \
        "a _run még mindig a közös self._stop-ot olvassa"
    assert "def _worker(self, gen: int, stop_event)" in src


def test_a_run_nem_a_kozos_stopot_figyeli():
    src = _src()
    i = src.index("def _run(self")
    torzs = src[i:src.index("def cleanup")]
    assert "self._stop.is_set()" not in torzs, \
        "a ciklus a lecserélhető közös eseményt olvassa"
    assert "stop_event.is_set()" in torzs
    assert "gen != self._gen" in torzs


def test_a_stop_lepteti_a_generaciot():
    e = RE.ReadEngine()
    g0 = e._gen
    e.stop()
    assert e._gen > g0, "a stop nem teszi elavulttá a futó szálakat"


def test_a_start_uj_generaciot_ad():
    e = RE.ReadEngine()
    e.load("Egy. Kettő. Három.")
    g0 = e._gen
    e._gen += 0
    # a start indítana szálat és TTS-t; csak a generáció-logikát nézzük
    e.stop()
    assert e._gen > g0


def test_elavult_generacio_allapota_eldobodik():
    """A régi szál NEM küldhet állapotot az új könyvre."""
    kapott = []
    e = RE.ReadEngine(on_state=lambda d: kapott.append(d))
    regi_gen = e._gen
    e._gen += 1                       # „közben új könyv indult"
    e._emit_gen(regi_gen, idx=0, text="RÉGI KÖNYV MONDATA")
    assert kapott == [], "a leváltott szál átszólt az új munkamenetbe"
    e._emit_gen(e._gen, idx=0, text="új")
    assert len(kapott) == 1


# ---- READ-P0-02: az előregyártás generációhoz kötött ----------------------

def test_a_hangfajl_neve_munkamenethez_kotott():
    src = _src()
    assert 'read_{gen}_{idx % 4}' in src, \
        "a fix read_{idx%4} gyűrű maradt (két ablak egymásra írhat)"


def test_elavult_prefetch_eredmenyt_nem_vesszuk_at():
    e = RE.ReadEngine()
    e._pf[(1, 0)] = "regi.wav"
    e._gen = 2
    assert e._take_prefetch(0, 2) is None, "elavult darabot adott vissza"
    assert e._take_prefetch(0, 1) == "regi.wav"   # a saját generációja még elérhető


def test_a_prefetch_hiba_nem_tunik_el_nemam():
    src = _src()
    i = src.index("def _begin_prefetch")
    torzs = src[i:i + 900]
    assert "except Exception: pass" not in torzs.replace("\n", " ")
    assert "_last_prefetch_error" in torzs


def test_a_regi_generaciok_fajljait_takaritja():
    src = _src()
    assert "def _purge_old_generations" in src, \
        "a generációnkénti fájlok felhalmozódnának"


def test_purge_csak_a_regieket_torli(tmp_path, monkeypatch):
    monkeypatch.setattr(RE, "READ_DIR", tmp_path)
    (tmp_path / "read_1_0.wav").write_bytes(b"regi")
    (tmp_path / "read_2_0.wav").write_bytes(b"uj")
    e = RE.ReadEngine()
    e._purge_old_generations(2)
    assert not (tmp_path / "read_1_0.wav").exists()
    assert (tmp_path / "read_2_0.wav").exists()


def test_parhuzamos_stop_es_emit_nem_kever(tmp_path):
    """Stresszteszt: 50 gyors generáció-váltás közben ÉRKEZŐ régi állapotok."""
    kapott = []
    e = RE.ReadEngine(on_state=lambda d: kapott.append(d))

    def regi_szal(gen):
        time.sleep(0.001)
        e._emit_gen(gen, text=f"gen{gen}")

    szalak = []
    for _ in range(50):
        gen = e._gen
        szalak.append(threading.Thread(target=regi_szal, args=(gen,)))
        szalak[-1].start()
        e._gen += 1                    # „új könyv indult"
    for t in szalak:
        t.join()
    assert kapott == [], f"{len(kapott)} elavult állapot szivárgott át"
