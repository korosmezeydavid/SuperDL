# -*- coding: utf-8 -*-
"""RETRÓ beszédhang motor + a Játékok keretrendszer.

A hangmotor a korszak formánsszintézisének AKUSZTIKAI jellemzőit alkotja újra
saját kóddal – nem emulál chipet és nem használ idegen ROM-ot."""
import pathlib
import sys
import wave

import numpy as np
import pytest

from superdl import retrovoice as RV

ROOT = pathlib.Path(__file__).parent.parent


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ---- karakterek ----------------------------------------------------------

def test_van_tobb_hangkarakter():
    assert len(RV.PRESETS) >= 4
    kulcsok = [p.kulcs for p in RV.PRESETS]
    assert len(set(kulcsok)) == len(kulcsok), "ismétlődő kulcs"
    assert RV.DEFAULT_PRESET in kulcsok


def test_ismeretlen_kulcs_az_elsore_esik_vissza():
    assert RV.preset("nincs-ilyen").kulcs == RV.PRESETS[0].kulcs
    assert RV.preset("").kulcs == RV.PRESETS[0].kulcs


def test_a_retro_karakterek_korhu_mintaveteluek():
    for p in RV.PRESETS:
        if p.kulcs == "tiszta":          # ez szándékosan mai hang
            continue
        assert p.freq <= 11025, f"{p.kulcs}: nem korhű mintavétel"
        assert p.bitek <= 12, f"{p.kulcs}: túl finom kvantálás"


# ---- DSP: a retró jelleg mérhető ----------------------------------------

def _szinusz(hz, fs=22050, mp=0.25):
    t = np.arange(int(fs * mp)) / fs
    return np.sin(2 * np.pi * hz * t)


def test_a_savkorlat_levagja_a_magasat():
    """A korhű sáv fölötti hang ERŐSEN halkuljon – ez adja a tompa hangzást.
    A szűrőt a normalizálás ELŐTT mérjük (a retrofy a végén egységes
    hangerőre hoz, ami elfedné a különbséget)."""
    p = RV.preset("brailab")
    also = RV._lowpass(_szinusz(500), 22050, p.felso_hz)
    felso = RV._lowpass(_szinusz(7000), 22050, p.felso_hz)
    assert np.max(np.abs(felso)) < np.max(np.abs(also)) * 0.25, \
        "a sáv fölötti hang nem halkul le eléggé"


def test_a_melyet_is_levagja():
    p = RV.preset("brailab")
    mely = RV._highpass(_szinusz(50, fs=8000), 8000, p.also_hz)
    kozep = RV._highpass(_szinusz(1000, fs=8000), 8000, p.also_hz)
    assert np.max(np.abs(mely)) < np.max(np.abs(kozep))


def test_a_kimenet_a_kert_mintavetelen_van():
    for p in RV.PRESETS:
        y, fs = RV.retrofy(_szinusz(440), 22050, p)
        assert fs == p.freq
        assert y.size > 0


def test_a_kvantalas_lepcsoket_hoz_letre():
    """Kevesebb bit → kevesebb különböző mintaérték (ez a „szemcse")."""
    x = _szinusz(440, fs=8000, mp=0.5)
    finom = RV._kvantal(x, 16)
    durva = RV._kvantal(x, 6)
    assert len(np.unique(durva)) < len(np.unique(finom))
    # 6 bit → 2^5 lépés mindkét irányban, plusz a nulla = legfeljebb 2^6+1 érték
    assert len(np.unique(durva)) <= 2 ** 6 + 1


def test_a_minta_tartas_ismetlodo_ertekeket_ad():
    x = np.arange(12, dtype=np.float64)
    y = RV._minta_tartas(x, 3)
    assert y[0] == y[1] == y[2]
    assert y[3] == y[4] == y[5]
    assert not np.array_equal(x, y)


def test_a_minta_tartas_egynel_nem_valtoztat():
    x = np.arange(10, dtype=np.float64)
    assert np.array_equal(RV._minta_tartas(x, 1), x)


def test_nem_vag_be_a_kimenet():
    """A normalizálás után sem lehet túlvezérlés (kattogás)."""
    hangos = _szinusz(440) * 5.0
    y, _ = RV.retrofy(hangos, 22050, RV.preset("brailab"))
    assert np.max(np.abs(y)) <= 1.0


def test_ures_bemenet_nem_dob():
    y, fs = RV.retrofy(np.array([]), 22050, RV.preset("brailab"))
    assert y.size == 0 and fs > 0


# ---- teljes szintézis (valódi eSpeak) -----------------------------------

@pytest.mark.skipif(not RV.available(), reason="nincs eSpeak ezen a gépen")
def test_valodi_szintezis_korhu_wav_ot_ad(tmp_path):
    out = str(tmp_path / "retro.wav")
    RV.synth("Szia, ez egy próba.", out, "brailab")
    with wave.open(out, "rb") as w:
        assert w.getframerate() == 8000, "nem korhű a mintavétel"
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        assert w.getnframes() > 1000, "gyanúsan rövid a hang"


@pytest.mark.skipif(not RV.available(), reason="nincs eSpeak ezen a gépen")
def test_a_nyers_kozteset_takaritja(tmp_path):
    out = str(tmp_path / "r.wav")
    RV.synth("Próba.", out, "robot")
    maradek = [p.name for p in tmp_path.iterdir() if ".nyers." in p.name]
    assert maradek == [], f"visszamaradt köztes fájl: {maradek}"


def test_ures_szoveg_elutasitva():
    with pytest.raises(ValueError):
        RV.synth("   ", "", "brailab")


# ---- jogtisztaság --------------------------------------------------------

def test_nincs_idegen_rom_vagy_chip_kod():
    """A motor SAJÁT kód: nem tartalmaz beágyazott ROM-adatot."""
    src = _src("superdl/retrovoice.py")
    assert "NEM azt a chipet emulálja" in src
    for tiltott in (".ROM", "BR4", "HL4"):
        assert tiltott not in src, f"idegen artefaktumra hivatkozik: {tiltott}"


# ---- a Játékok keretrendszer --------------------------------------------

sys.path.insert(0, str(ROOT / "modules_src" / "jatekok"))
from jatekok_mod import katalogus as K            # noqa: E402


def test_ket_kulon_katalogus_van():
    assert len(K.RETRO) > 0 and len(K.SAJAT) > 0
    assert len(K.mind()) == len(K.RETRO) + len(K.SAJAT)


def test_minden_jateknak_van_neve_es_leirasa():
    for j in K.mind():
        assert j.kulcs and j.nev and j.leiras
        assert len(j.leiras) > 10, f"{j.kulcs}: túl rövid leírás"


def test_a_kulcsok_egyediek():
    k = [j.kulcs for j in K.mind()]
    assert len(set(k)) == len(k)


def test_keres_mukodik():
    assert K.keres(K.RETRO[0].kulcs) is not None
    assert K.keres("nincs-ilyen") is None


def test_a_felulet_megmondja_ha_a_jatek_meg_keszul():
    """NINCS HAMIS SIKER: a még nem kész játéknál ezt ki kell mondani."""
    src = _src("modules_src/jatekok/jatekok_mod/jatekokwin.py")
    assert "még készül" in src
    i = src.index("def _indit")
    assert "if not j.indit" in src[i:i + 600]


def test_az_ablak_a_kotelezo_akadalymentes_elemeket_hozza():
    src = _src("modules_src/jatekok/jatekok_mod/jatekokwin.py")
    assert "_closing" in src, "nincs záráskori callback-őr"
    assert "SetName(" in src, "nincsenek címkézve a vezérlők"
    assert "WXK_F1" in src and "HELP" in src, "nincs F1 súgó"
    assert "beszel=True" in src, "a kritikus állapotok nem hallhatók"
