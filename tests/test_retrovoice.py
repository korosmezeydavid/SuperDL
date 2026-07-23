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
    felso = RV._lowpass(_szinusz(9000), 22050, p.felso_hz)
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
        assert w.getframerate() == RV.preset("brailab").freq
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
    # a kapu a regiszter-alapú „indítható-e" ellenőrzés (a katalógusban már
    # nincs indit-mező; a felület a megírt játékok regiszteréből dönt)
    assert "if not indithato" in src[i:i + 600]


def test_az_ablak_a_kotelezo_akadalymentes_elemeket_hozza():
    src = _src("modules_src/jatekok/jatekok_mod/jatekokwin.py")
    assert "_closing" in src, "nincs záráskori callback-őr"
    assert "SetName(" in src, "nincsenek címkézve a vezérlők"
    assert "WXK_F1" in src and "HELP" in src, "nincs F1 súgó"
    assert "beszel=True" in src, "a kritikus állapotok nem hallhatók"


# ---- ÉLESSÉG: a hang ne legyen tompa, „rádióból szóló" -------------------

def _felso_sav_arany(x, fs):
    """A 2 kHz feletti energia aránya – ez méri, mennyire „szúrós" a hang."""
    sp = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / fs)
    ossz = sp.sum() or 1.0
    return float(sp[f >= 2000].sum() / ossz)


def _zaj(fs=22050, mp=0.5):
    rng = np.random.default_rng(42)
    return rng.standard_normal(int(fs * mp)) * 0.3


def test_az_elohangsuly_emeli_a_magasakat():
    x = _zaj()
    tompa = _felso_sav_arany(x, 22050)
    eles = _felso_sav_arany(RV._elohangsuly(x, 0.6), 22050)
    assert eles > tompa, "az elő-hangsúlyozás nem élesít"


def test_az_elohangsuly_nullaval_nem_valtoztat():
    x = _zaj()
    assert np.array_equal(RV._elohangsuly(x, 0.0), x)


def test_a_jelenlet_csucs_kiemel():
    x = _zaj(fs=11025)
    nyers = _felso_sav_arany(x, 11025)
    emelt = _felso_sav_arany(RV._peaking(x, 11025, 3300, 9.0), 11025)
    assert emelt > nyers, "a jelenlét-csúcs nem emel"


def test_a_jelenlet_csucs_nulla_db_nel_nem_valtoztat():
    x = _zaj(fs=11025)
    assert np.array_equal(RV._peaking(x, 11025, 3300, 0.0), x)


def test_az_elesitett_karakterek_szurosabbak_a_tompanal():
    """A LÉNYEG: a felhasználó szerint a régi túl tompa volt („Szokol rádió").
    Az élesített változatoknak mérhetően több felső energiája kell legyen."""
    x = _zaj()
    tompa, fs_t = RV.retrofy(x, 22050, RV.preset("brailab_tompa"))
    for kulcs in ("brailab", "terminal", "brailab_eles", "terminal_eles"):
        p = RV.preset(kulcs)
        y, fs = RV.retrofy(x, 22050, p)
        assert _felso_sav_arany(y, fs) > _felso_sav_arany(tompa, fs_t), \
            f"{kulcs}: nem élesebb a tompa változatnál"


def test_a_nagyon_eles_valtozat_a_legszurosabb():
    x = _zaj()
    a, fa = RV.retrofy(x, 22050, RV.preset("brailab"))
    b, fb = RV.retrofy(x, 22050, RV.preset("brailab_eles"))
    assert _felso_sav_arany(b, fb) > _felso_sav_arany(a, fa)


def test_a_kedvenc_karakterek_megvannak():
    """A fejlesztő ezt a hármat választotta ki – ne tűnjenek el."""
    for kulcs in ("brailab", "terminal", "urhajo"):
        assert kulcs in RV.PRESET_MAP, f"eltűnt a kiválasztott karakter: {kulcs}"


# ---- VOKÓDER: a GERJESZTÉS lecserélése (az igazi retró hatás) ------------

def _mert_alaphang(x, fs):
    """A jel alapfrekvenciája autokorrelációval, zöngés kereteken."""
    N = 2048
    ered = []
    ossz_rms = np.sqrt(np.mean(x ** 2)) or 1e-9
    for i in range(0, max(0, len(x) - N), N // 2):
        s = x[i:i + N]
        if np.sqrt(np.mean(s ** 2)) < 0.10 * ossz_rms:
            continue
        s = s - s.mean()
        ac = np.correlate(s, s, "full")[N - 1:]
        lo, hi = int(fs / 300), int(fs / 60)
        if hi >= len(ac) or lo >= hi:
            continue
        p = lo + int(np.argmax(ac[lo:hi]))
        if ac[p] > 0.3 * ac[0]:
            ered.append(fs / p)
    return (float(np.median(ered)), float(np.std(ered))) if ered else (0.0, 0.0)


def test_az_impulzussor_periodikus_es_egyenaram_mentes():
    x = RV._impulzus_sor(11025, 11025, 100.0)
    assert x.size == 11025
    assert abs(float(np.mean(x))) < 1e-9, "van egyenáram-összetevő"
    m, szoras = _mert_alaphang(x, 11025)
    assert abs(m - 100.0) < 3.0, f"nem a kért alapfrekvencián zúg: {m}"


def test_az_impulzussor_nulla_frekvencian_nem_dob():
    assert RV._impulzus_sor(100, 11025, 0.0).size == 100


def test_a_vokoder_ROGZITETT_hangmagassagot_ad():
    """EZ A LÉNYEG: a vokóder ELDOBJA az alapmotor hangszalag-jelét, és saját,
    tökéletesen periodikus impulzussorozattal helyettesíti. Enélkül a hang
    „megszűrt eSpeak" marad, nem beszélő chip."""
    p = RV.preset("chip")
    assert p.vokoderes is True
    fs = p.freq
    # zöngés-szerű próbajel VÁLTOZÓ hangmagassággal
    t = np.arange(int(fs * 1.2)) / fs
    f0 = 150 + 60 * np.sin(2 * np.pi * 0.8 * t)      # 90..210 Hz között ingadozik
    be = np.sin(2 * np.pi * np.cumsum(f0) / fs) * 0.6
    be += 0.25 * np.sin(2 * np.pi * np.cumsum(f0 * 3) / fs)
    ki = RV.vokoder(be, fs, p)
    m_be, sz_be = _mert_alaphang(be, fs)
    m_ki, sz_ki = _mert_alaphang(ki, fs)
    assert sz_be > 5.0, "a próbajel nem ingadozott (rossz a teszt)"
    assert sz_ki < 3.0, f"a kimenet MÉG mindig ingadozik (±{sz_ki:.1f})"
    assert abs(m_ki - p.alaphang) < 6.0, \
        f"nem a saját alapfrekvencián szól: {m_ki:.1f} != {p.alaphang}"


def test_a_vokoder_megtartja_a_burkologorbet():
    """A hangforrás cserélődik, de a HANGERŐ-menet (és így a beszéd
    érthetősége) megmarad."""
    p = RV.preset("chip")
    fs = p.freq
    t = np.arange(int(fs * 1.0)) / fs
    burok = np.where((t % 0.25) < 0.12, 1.0, 0.05)     # szaggatott „szótagok"
    be = np.sin(2 * np.pi * 140 * t) * burok
    ki = RV.vokoder(be, fs, p)
    n = min(len(be), len(ki)) // 512 * 512
    e_be = np.abs(be[:n]).reshape(-1, 512).mean(axis=1)
    e_ki = np.abs(ki[:n]).reshape(-1, 512).mean(axis=1)
    korr = float(np.corrcoef(e_be, e_ki)[0, 1])
    assert korr > 0.6, f"a burkológörbe elveszett (korreláció {korr:.2f})"


def test_a_vokoder_rovid_jelre_nem_dob():
    p = RV.preset("chip")
    assert RV.vokoder(np.zeros(10), p.freq, p).size == 10


def test_a_kevesebb_sav_es_lepcso_darabosabb():
    """A „darabos" karakter kevesebb csatornából és durvább szint-lépcsőből jön."""
    finom, durva = RV.preset("chip"), RV.preset("chip_darabos")
    assert durva.savok < finom.savok
    assert durva.szint_lepcso < finom.szint_lepcso
    assert durva.keret_ms > finom.keret_ms


def test_a_vokoderes_karakterek_leteznek():
    vok = [p.kulcs for p in RV.PRESETS if p.vokoderes]
    assert len(vok) >= 3, "kevés vokóderes karakter"
    assert "chip" in vok


@pytest.mark.skipif(not RV.available(), reason="nincs eSpeak ezen a gépen")
def test_a_vokoderes_szintezis_vegigfut(tmp_path):
    out = str(tmp_path / "chip.wav")
    RV.synth("Ez egy próba mondat.", out, "chip")
    with wave.open(out, "rb") as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float)
        fs = w.getframerate()
    assert a.size > 1000
    _, szoras = _mert_alaphang(a, fs)
    assert szoras < 4.0, "a kész hang hangmagassága ingadozik (nem gépi)"
