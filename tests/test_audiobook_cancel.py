# -*- coding: utf-8 -*-
"""Hangoskönyv: megszakíthatóság, felülírás-védelem, kimenet-ellenőrzés.
Herman Tibi AB-P0-02 / AB-P0-03 / AB-P0-04."""
import os
import pathlib
import threading
import types

import pytest

from superdl import audiobook

ROOT = pathlib.Path(__file__).parent.parent


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class _FakeEng:
    """TTS-motor, ami csak fájlt „gyárt" – és számolja a hívásokat."""
    char_limit = 400

    def __init__(self):
        self.hivasok = 0

    def synth(self, text, voice, base, pitch=0, rate=0, api_key=""):
        self.hivasok += 1
        with open(base + ".wav", "wb") as f:
            f.write(b"\0" * 128)
        return base + ".wav"


@pytest.fixture
def motor():
    e = _FakeEng()
    audiobook.tts.ENGINES["_teszt"] = e
    yield e
    audiobook.tts.ENGINES.pop("_teszt", None)


def _konyv(n=20):
    return types.SimpleNamespace(title="Teszt", text="Egy. Kettő. Három. " * n)


# ---- AB-P0-02: megszakíthatóság ------------------------------------------

def test_azonnali_megszakitas_nem_indit_tts_t(motor, tmp_path):
    ev = threading.Event()
    ev.set()
    with pytest.raises(audiobook.AudiobookCancelled):
        audiobook.build(_konyv(), "_teszt", "v",
                        str(tmp_path / "ki.mp3"), cancel=ev)
    assert motor.hivasok == 0, "megszakítás után is hívta a (fizetős) TTS-t"


def test_megszakitas_nem_hagy_vegleges_fajlt(motor, tmp_path):
    out = tmp_path / "ki.mp3"
    ev = threading.Event()
    ev.set()
    with pytest.raises(audiobook.AudiobookCancelled):
        audiobook.build(_konyv(), "_teszt", "v", str(out), cancel=ev)
    assert not out.exists()


def test_megszakitas_nem_hagy_szemetet_a_celmappaban(motor, tmp_path):
    ev = threading.Event()
    ev.set()
    with pytest.raises(audiobook.AudiobookCancelled):
        audiobook.build(_konyv(), "_teszt", "v",
                        str(tmp_path / "ki.mp3"), cancel=ev)
    maradek = [p.name for p in tmp_path.iterdir()]
    assert maradek == [], f"visszamaradt: {maradek}"


def test_cancel_nelkul_valtozatlanul_mukodik(motor):
    """Regresszió-őr: a cancel opcionális, nélküle a régi viselkedés."""
    import inspect
    sig = inspect.signature(audiobook.build)
    assert sig.parameters["cancel"].default is None


def test_a_kivetel_osztaly_letezik():
    assert issubclass(audiobook.AudiobookCancelled, RuntimeError)


# ---- AB-P0-03 / AB-P0-04: nem ír közvetlenül a véglegesre ----------------

def test_nem_ir_kozvetlenul_a_vegleges_nevre():
    src = _src("superdl/audiobook.py")
    assert "os.replace(str(f), str(cel))" in src, "nincs atomikus commit"
    assert "superdl_kesz_" in src, "nincs köztes (staging) mappa"


def test_a_koztes_mappa_a_cel_mellett_van():
    """Más köteten az os.replace elbukna – a temp-ben NEM lehet."""
    src = _src("superdl/audiobook.py")
    assert "out.parent /" in src, "a köztes mappa nem a cél mellett van"


def test_van_kimenet_ellenorzes():
    src = _src("superdl/audiobook.py")
    assert "üres vagy csonka" in src, "nincs csonka-kimenet ellenőrzés"
    assert "st_size < 1024" in src


def test_a_koztes_mappa_takaritodik():
    src = _src("superdl/audiobook.py")
    assert "stage_dirs" in src
    i = src.index("finally:")
    assert "stage_dirs" in src[i:i + 400], "hibánál bent maradhat a staging"


# ---- a felület: Leállítás gomb + záráskori megerősítés -------------------

def test_van_leallitas_gomb():
    src = _src("modules_src/konyvek/konyvek_mod/bookwin.py")
    assert "stop_btn" in src and "_on_stop_make" in src
    assert "Készítés &leállítása" in src


def test_a_build_megkapja_a_cancelt():
    src = _src("modules_src/konyvek/konyvek_mod/bookwin.py")
    assert "cancel=self._cancel" in src, "a felület nem adja át a megszakítást"


def test_zaraskor_rakerdez_folyo_keszitesnel():
    src = _src("modules_src/konyvek/konyvek_mod/bookwin.py")
    i = src.index("def _on_close")
    torzs = src[i:i + 900]
    assert "self._busy" in torzs and "e.Veto()" in torzs
    assert "FOLYAMATBAN" in torzs
