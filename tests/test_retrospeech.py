# -*- coding: utf-8 -*-
"""SAJÁT magyar formánsszintetizátor (retrospeech) – eSpeak NÉLKÜL.

A fejlesztő visszajelzése: „az eSpeak már túlságosan jól egybe mondja a
dolgokat, nincs benne az a darabosság". A megoldás: saját betű→hang
átalakítás + saját formánsszintézis, ahol minden hangzó a SAJÁT értékein
szól, és rövid átmenettel ugrik a következőre."""
import numpy as np
import pytest

from superdl import retrospeech as RS


# ---- magyar betű→hang ----------------------------------------------------

def _h(sz):
    return [x for x, _ in RS.szoveg_hangokra(sz)]


def test_egyszeru_szo():
    assert _h("kutya") == ["k", "u", "ty", "a"]


@pytest.mark.parametrize("szo,vart", [
    ("cseresznye", ["cs", "e", "r", "e", "sz", "ny", "e"]),
    ("gyerek",     ["gy", "e", "r", "e", "k"]),
    ("lyuk",       ["ly", "u", "k"]),
    ("dzsungel",   ["dzs", "u", "n", "g", "e", "l"]),
    ("zsiráf",     ["zs", "i", "r", "á", "f"]),
])
def test_tobbjegyu_betuk(szo, vart):
    assert _h(szo) == vart


@pytest.mark.parametrize("szo,vart", [
    ("asszony", ["a", "sz", "o", "ny"]),      # ssz → hosszú sz
    ("meggy",   ["m", "e", "gy"]),            # ggy → hosszú gy
    ("otthon",  ["o", "t", "h", "o", "n"]),
])
def test_kettozott_massalhangzo(szo, vart):
    assert _h(szo) == vart


def test_a_kettozott_hosszabb_idotartamot_kap():
    r = dict((h, sz) for h, sz in RS.szoveg_hangokra("assza"))
    assert r["sz"] > 1.5, "a kettőzött mássalhangzó nem lett hosszabb"


def test_a_hosszu_maganhangzo_hosszabb():
    assert RS.TABLA["á"].hossz > RS.TABLA["a"].hossz
    assert RS.TABLA["í"].hossz > RS.TABLA["i"].hossz


def test_szamjegyek_kimondasa():
    assert _h("7") == _h("hét")


def test_irasjelek_szunetet_adnak():
    h = _h("a. b")
    assert "." in h and " " in h


def test_ismeretlen_jelet_kihagy():
    assert _h("a@#b") == ["a", "b"]


def test_ures_szoveg():
    assert RS.szoveg_hangokra("") == []


# ---- a formáns-tábla teljessége -----------------------------------------

def test_minden_magyar_betunek_van_hangja():
    for c in "aábcdeéfghiíjklmnoóöőprstuúüűvz":
        assert c in RS.TABLA, f"hiányzik a táblából: {c}"
    for j in RS.JEGYEK:
        assert j in RS.TABLA, f"hiányzik a többjegyű: {j}"


def test_a_maganhangzoknak_ertelmes_formansaik_vannak():
    for c in RS.MGH:
        h = RS.TABLA[c]
        assert h.tipus == "mgh"
        assert 200 < h.f1 < 900, f"{c}: F1 tartományon kívül"
        assert h.f2 > h.f1, f"{c}: F2 nem nagyobb F1-nél"
        assert h.f3 > h.f2, f"{c}: F3 nem nagyobb F2-nél"


# ---- a szintézis akusztikája --------------------------------------------

def _van_csucs(x, fs, cel, tur=0.25):
    """Van-e a spektrum-burkolón helyi maximum a cél ±25%-án belül?"""
    sp = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / fs)
    w = max(3, int(110 / (f[1] - f[0])))   # szűk ablak: a közeli F1/F2 se
                                           # mosódjon össze (o, ó, u, ú)
    b = np.convolve(sp, np.ones(w) / w, mode="same")
    sav = (f >= cel * (1 - tur)) & (f <= cel * (1 + tur))
    if not sav.any():
        return False
    i = int(np.argmax(b * sav))
    return bool(b[i] >= b[max(0, i - 1)] and b[i] >= b[min(len(b) - 1, i + 1)])


@pytest.mark.parametrize("hang", ["á", "i", "u", "e", "o", "ü", "ó", "í"])
def test_a_formansok_ott_vannak_ahol_a_tabla_mondja(hang):
    """A LÉNYEG: a szintetizátor tényleg a megadott formánsokat állítja elő –
    ezen múlik, hogy a magánhangzók megkülönböztethetők-e."""
    g = RS.gep("gep")
    x, fs = RS.szintetizal(hang * 8, g)
    h = RS.TABLA[hang]
    assert _van_csucs(x, fs, RS._kvant(h.f1, g.kvant_hz)), f"{hang}: nincs F1"
    assert _van_csucs(x, fs, RS._kvant(h.f2, g.kvant_hz)), f"{hang}: nincs F2"


def test_a_sugarzasi_karakterisztika_megvan():
    """Enélkül a rezonátor-lánc 'megenné' az F2/F3-at, és a magánhangzók
    megkülönböztethetetlenek lennének."""
    import inspect
    src = inspect.getsource(RS.szintetizal)
    assert "np.diff(ki)" in src, "hiányzik a sugárzási karakterisztika"


def test_kulonbozo_maganhangzok_kulonbozo_hangot_adnak():
    g = RS.gep("gep")
    a, fs = RS.szintetizal("á" * 6, g)
    i, _ = RS.szintetizal("i" * 6, g)
    n = min(len(a), len(i))
    sa = np.abs(np.fft.rfft(a[:n])); si = np.abs(np.fft.rfft(i[:n]))
    korr = float(np.corrcoef(sa, si)[0, 1])
    assert korr < 0.8, f"az á és az i túl hasonló (korr {korr:.2f})"


def test_a_hangmagassag_kozel_allando_de_nem_teljesen():
    """A fejlesztő kérése: legyen egy KIS hangsúly-élet, de maradjon gépies."""
    g = RS.gep("gep")
    assert 0 < g.hangsuly < 0.4, "vagy teljesen monoton, vagy túl éneklős"


def test_a_darabos_gep_rovidebb_atmenettel_dolgozik():
    """A 'darabosság' a RÖVID átmenetekből és a durva kvantálásból jön."""
    sima, darabos = RS.gep("gep"), RS.gep("gep_darabos")
    assert darabos.atmenet_ms < sima.atmenet_ms
    assert darabos.kvant_hz > sima.kvant_hz
    assert darabos.bitek < sima.bitek


def test_a_szunet_nema():
    g = RS.gep("gep")
    x, _ = RS.szintetizal("   ", g)
    assert x.size == 0 or float(np.max(np.abs(x))) < 0.05


def test_nem_vag_be():
    g = RS.gep("gep")
    x, _ = RS.szintetizal("Árvíztűrő tükörfúrógép!", g)
    assert float(np.max(np.abs(x))) <= 1.0


def test_a_szintezis_ertelmes_hosszu(tmp_path):
    g = RS.gep("gep")
    x, fs = RS.szintetizal("Jó napot kívánok!", g)
    mp = len(x) / fs
    assert 0.8 < mp < 6.0, f"gyanús hossz: {mp:.2f} mp"


def test_wav_iras(tmp_path):
    import wave
    out = str(tmp_path / "gep.wav")
    RS.synth("Teszt.", out, "gep")
    with wave.open(out, "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        assert w.getnframes() > 500


def test_ures_szoveg_elutasitva():
    with pytest.raises(ValueError):
        RS.synth("  ", "", "gep")


def test_tobb_gep_karakter_van():
    assert len(RS.GEPEK) >= 3
    assert RS.ALAP_GEP in RS.GEP_MAP
    assert RS.gep("nincs-ilyen").kulcs == RS.GEPEK[0].kulcs


# ---- jogtisztaság --------------------------------------------------------

def test_nem_hasznal_espeaket_es_idegen_artefaktumot():
    """Ez a motor TELJESEN saját: se eSpeak-hívás, se idegen ROM.
    A KÓDOT vizsgáljuk (a magyarázó szöveg említheti az eSpeak-et annak
    indoklásához, MIÉRT nem használjuk)."""
    import ast
    import inspect
    fa = ast.parse(inspect.getsource(RS))
    # semmilyen import nem hozhat be beszédmotort vagy alfolyamatot
    for csp in ast.walk(fa):
        if isinstance(csp, (ast.Import, ast.ImportFrom)):
            nev = (getattr(csp, "module", "") or "") + " " + " ".join(
                a.name for a in csp.names)
            for tiltott in ("espeak", "subprocess", "selfvoice", "retrovoice"):
                assert tiltott not in nev.lower(),                     f"idegen/külső függőség: {nev.strip()}"
    # a kódban (nem a szövegben) ne legyen idegen artefaktum-hivatkozás
    kod = "\n".join(l for l in inspect.getsource(RS).splitlines()
                    if not l.strip().startswith("#"))
    for tiltott in (".ROM", "BR4", "HL4"):
        assert tiltott not in kod, f"idegen artefaktum: {tiltott}"
