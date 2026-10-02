# -*- coding: utf-8 -*-
"""A SuperDL-logó köszöntése: női vagy férfi hang (Dávid, 2026-10-02).

A beállításokban (Hangjelzések / Beszéd) választható; induláskor a választott
szól. A két hang a csomagba is bekerül (mindkét spec), a régi startup.wav nem.
"""
import pathlib
import wave

from superdl import sounds

GYOKER = pathlib.Path(__file__).resolve().parent.parent


def test_mindket_hang_megvan_es_rendes_wav():
    for h in ("noi", "ferfi"):
        p = sounds.logo_fajl(h)
        assert p.name == f"startup_{h}.wav" and p.is_file()
        with wave.open(str(p)) as w:
            mp = w.getnframes() / w.getframerate()
            assert w.getnchannels() == 1 and 9.5 < mp < 10.5


def test_ismeretlen_ertek_noi():
    assert sounds.logo_fajl("xyz").name == "startup_noi.wav"
    assert sounds.logo_fajl("").name == "startup_noi.wav"


def test_a_valasztott_hang_szol(monkeypatch, tmp_path):
    szolt = []

    class _Ws:
        SND_FILENAME = SND_ASYNC = SND_NODEFAULT = 0

        @staticmethod
        def PlaySound(ut, _flags):
            szolt.append(pathlib.Path(ut).name)

    monkeypatch.setattr(sounds, "winsound", _Ws)
    monkeypatch.setattr(sounds, "SOUND_DIR", tmp_path)   # nincs saját felülíró fájl
    sounds.play_startup("ferfi")
    sounds.play_startup("noi")
    sounds.play_startup()
    assert szolt == ["startup_ferfi.wav", "startup_noi.wav", "startup_noi.wav"]


def test_sajat_startup_wav_tovabbra_is_elsobbseget_kap(monkeypatch, tmp_path):
    szolt = []

    class _Ws:
        SND_FILENAME = SND_ASYNC = SND_NODEFAULT = 0

        @staticmethod
        def PlaySound(ut, _flags):
            szolt.append(pathlib.Path(ut).name)

    (tmp_path / "startup.wav").write_bytes(b"x")
    monkeypatch.setattr(sounds, "winsound", _Ws)
    monkeypatch.setattr(sounds, "SOUND_DIR", tmp_path)
    sounds.play_startup("ferfi")
    assert szolt == ["startup.wav"]


def test_mindket_specben_benne_van_a_ket_hang():
    for spec in ("SuperDL.spec", "SuperDL-onedir.spec"):
        s = (GYOKER / spec).read_text(encoding="utf-8")
        assert "startup_noi.wav" in s and "startup_ferfi.wav" in s
        assert "'superdl\\\\startup.wav'" not in s


def test_beallitas_es_indulas_bekotve():
    gui = (GYOKER / "superdl_gui.py").read_text(encoding="utf-8")
    assert '"startup_hang": "noi"' in gui
    assert 'sounds.play_startup,\n                         self.settings.get("startup_hang", "noi")' in gui
    dlg = (GYOKER / "superdl" / "settingsdialog.py").read_text(encoding="utf-8")
    assert '"startup_hang": self._logo_hangok' in dlg
