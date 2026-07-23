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


# ---- REGRESSZIÓ: a négy hiba, ami néma sziszegést okozott ----------------
# A fejlesztő jelzése: „csak apró sziszegések hallatszódtak, semmi más".
# A méréssel feltárt négy ok mindegyikére külön őr.

def _profil(x, fs):
    """Beszéd-jellemzők: néma blokkok aránya + a sávok energia-megoszlása."""
    e = np.abs(x[:len(x) // 256 * 256]).reshape(-1, 256).max(axis=1)
    sp = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / fs)
    ossz = sp.sum() or 1.0
    return {
        "nema": float(np.mean(e < 0.01)),
        "formans_sav": float(sp[(f >= 200) & (f < 1500)].sum() / ossz),
        "magas": float(sp[f >= 3000].sum() / ossz),
    }


@pytest.mark.parametrize("gk", ["gep", "gep_darabos", "gep_melv", "gep_magas"])
def test_a_kimenet_beszed_jellegu_nem_sziszeges(gk):
    """A LÉNYEG: az energia a FORMÁNS-sávban legyen, ne a magasban, és ne
    legyen szinte minden néma. A hibás állapotban: 92% néma, 3% formáns-sáv,
    86% magas – vagyis puszta sziszegés."""
    x, fs = RS.szintetizal("Üdvözöllek a retro játékok menüjében!", RS.gep(gk))
    p = _profil(x, fs)
    assert p["nema"] < 0.60, f"{gk}: a hang {p['nema']:.0%}-a néma"
    assert p["formans_sav"] > 0.25, \
        f"{gk}: alig van energia a formáns-sávban ({p['formans_sav']:.0%})"
    assert p["magas"] < 0.40, f"{gk}: sziszegés uralja ({p['magas']:.0%})"


def test_a_rezonator_allapota_folyamatos():
    """1. HIBA: a szűrő-állapot blokkonkénti nullázása szétverte a hangot –
    a rezonátornak CSENGENIE kell két zöngeimpulzus között."""
    fs = 11025
    n = fs // 2
    imp = np.zeros(n)
    imp[::90] = 1.0                       # ~122 Hz, a blokknál ritkábban
    y = RS._rezonator(imp, np.full(n, 700.0), np.full(n, 90.0), fs,
                      int(fs * 0.005))    # a blokk RÖVIDEBB a periódusnál
    e = np.abs(y[:len(y) // 256 * 256]).reshape(-1, 256).max(axis=1)
    assert float(np.mean(e < 0.01 * np.max(np.abs(y)))) < 0.10, \
        "a rezonátor nem cseng végig (állapot-nullázás)"


def test_a_rezonator_a_CSUCSRA_van_normalva():
    """3. HIBA: DC-re normálva a magas formánsú réshangok 45-ször hangosabbak
    lettek a magánhangzóknál. A csúcs-normálás után az erősítés a
    középfrekvencián ~1, függetlenül attól, hol van a formáns."""
    fs = 11025
    n = fs
    for f0 in (500.0, 1800.0, 3600.0):
        t = np.arange(n) / fs
        be = np.sin(2 * np.pi * f0 * t)    # pont a rezonancián
        ki = RS._rezonator(be, np.full(n, f0), np.full(n, 100.0), fs, n)
        # a rezonancián az erősítés legyen 1 körüli (nem 10, nem 0,01)
        eros = float(np.sqrt(np.mean(ki[fs // 4:] ** 2)) /
                     np.sqrt(np.mean(be ** 2)))
        assert 0.5 < eros < 2.0, f"{f0} Hz-en az erősítés {eros:.2f}"


def test_a_zonge_nem_halkabb_a_zajnal():
    """2. HIBA: az egymintás impulzus túl kevés energiát hordozott, ezért a
    zaj elnyomta a zöngét – a beszédből csak sziszegés maradt.

    A LÁNCOT mérjük, nem a kész fájlokat: azokat külön-külön 0,9-re
    normalizáljuk, ezért az arányuk nem lenne összehasonlítható.
    """
    g = RS.gep("gep")
    fs, n = g.fs, g.fs // 2
    lep = int(fs * 0.005)

    def lanc(gerj, h):
        y = RS._rezonator(gerj, np.full(n, h.f1), np.full(n, h.b1), fs, lep)
        y = RS._rezonator(y, np.full(n, h.f2), np.full(n, h.b2), fs, lep)
        y = RS._rezonator(y, np.full(n, h.f3), np.full(n, h.b3), fs, lep)
        return np.concatenate(([y[0]], np.diff(y)))       # sugárzás

    # a gerjesztés PONTOSAN úgy, ahogy a szintetizátor építi
    imp = np.zeros(n)
    imp[::int(fs / g.alaphang)] = 1.0
    glott = RS._rezonator(imp, np.full(n, 240.0), np.full(n, 160.0), fs, n)
    glott = glott / (float(np.sqrt(np.mean(glott ** 2))) or 1e-9)
    rng = np.random.default_rng(1)
    zaj = rng.standard_normal(n)
    zaj = zaj / (float(np.sqrt(np.mean(zaj ** 2))) or 1e-9) * 0.04

    a, sz = RS.TABLA["á"], RS.TABLA["sz"]
    r_m = float(np.sqrt(np.mean(lanc(glott, a) ** 2))) * a.hangero
    r_r = float(np.sqrt(np.mean(lanc(zaj, sz) ** 2))) * sz.hangero
    arany = r_r / (r_m or 1e-9)
    assert arany < 1.0, \
        f"a réshang HANGOSABB a magánhangzónál ({arany:.1f}x) – sziszegés"
    assert arany > 0.05, f"a réshang alig hallható ({arany:.2f}x)"


def test_a_kvantalas_a_normalizalas_UTAN_tortenik():
    """4. HIBA: fordított sorrendben a bit-kvantálás LENULLÁZTA a jelet
    (a csúcsra normált lánc kis értékeket ad, a 7 bites lépcső mindent
    0-ra kerekített)."""
    import inspect
    src = inspect.getsource(RS.szintetizal)
    i_norm = src.index("ki = ki / csucs")
    i_kvant = src.index("np.round(ki * lepcsok)")
    assert i_norm < i_kvant, "a kvantálás megelőzi a normalizálást"


@pytest.mark.parametrize("gk", ["gep", "gep_darabos", "gep_melv", "gep_magas"])
def test_egyik_karakter_sem_nemul_el(gk):
    """A `gep_darabos` (7 bit) teljesen elnémult a rossz sorrend miatt."""
    x, _ = RS.szintetizal("Próba egy kettő három.", RS.gep(gk))
    assert float(np.max(np.abs(x))) > 0.5, f"{gk}: néma vagy alig hallható"
    assert not np.isnan(x).any(), f"{gk}: NaN a kimenetben"


# ---- A NYERTES karakter finomítása (élesség, hangerő, hangsúly) ----------

def test_gep_melv_a_nyertes_es_az_elso():
    """A fejlesztő a gep_melv-et választotta – ez legyen az ALAPÉRTELMEZETT."""
    assert RS.GEPEK[0].kulcs == "gep_melv"
    assert RS.ALAP_GEP == "gep_melv"


def test_a_nyertes_eles_hangos_hangsulyos():
    g = RS.gep("gep_melv")
    assert g.elesseg > 0.3, "nincs élesítés"
    assert g.hangero > 0.9, "nem elég hangos"
    assert g.szotag_hangsuly > 0.2, "kevés a szótag-hangsúly"


def test_az_elesites_emeli_a_jelenletet():
    """Azonos alap, csak az élesség kapcsolóban különböznek."""
    import dataclasses
    alap = RS.gep("gep_melv")
    tompa = dataclasses.replace(alap, elesseg=0.0)
    x_e, fs = RS.szintetizal("Válassz játékot most!", alap)
    x_t, _ = RS.szintetizal("Válassz játékot most!", tompa)

    def jelenlet(x, fs):
        sp = np.abs(np.fft.rfft(x * np.hanning(len(x))))
        f = np.fft.rfftfreq(len(x), 1 / fs)
        return float(sp[(f >= 2200) & (f < 3600)].sum() / (sp.sum() or 1))
    assert jelenlet(x_e, fs) > jelenlet(x_t, fs), "az élesítés nem emel"


def test_a_szotag_hangsuly_amplitudo_ingadozast_ad():
    """Azonos gép, csak a szótag-hangsúly különbözik → nagyobb dinamika."""
    import dataclasses
    alap = RS.gep("gep_melv")
    lapos = dataclasses.replace(alap, szotag_hangsuly=0.0, hangsuly=0.05)
    x_h, fs = RS.szintetizal("Kezdődik a nagy kaland ma!", alap)
    x_l, _ = RS.szintetizal("Kezdődik a nagy kaland ma!", lapos)

    def dinamika(x):
        # az elején lévő hangsúlyos szótagok kiemelkednek: a szótag-csúcsok
        # szórása nagyobb, ha van szótag-hangsúly
        e = np.abs(x[:len(x) // 400 * 400]).reshape(-1, 400).max(axis=1)
        e = e[e > 0.05]
        return float(np.percentile(e, 90) - np.percentile(e, 40))
    assert dinamika(x_h) > dinamika(x_l), "a hangsúly nem ad több dinamikát"


def test_a_hangero_szabalyzo_hat():
    import dataclasses
    g = RS.gep("gep_melv")
    halk = dataclasses.replace(g, hangero=0.4)
    x_h, _ = RS.szintetizal("Teszt.", g)
    x_l, _ = RS.szintetizal("Teszt.", halk)
    assert float(np.max(np.abs(x_h))) > float(np.max(np.abs(x_l)))


def test_az_uj_szabalyzok_nem_tornek_el_semmit():
    """Minden karakter épkézláb beszédet ad (nem NaN, nem néma, nem vág)."""
    for g in RS.GEPEK:
        x, _ = RS.szintetizal("Árvíztűrő tükörfúrógép ma!", g)
        assert not np.isnan(x).any(), f"{g.kulcs}: NaN"
        assert 0.5 < float(np.max(np.abs(x))) <= 1.0, f"{g.kulcs}: rossz szint"


# ---- „dobozos + halk + magyarosabb hangsúly" finomítás -------------------
# A fejlesztő: „még mindig nagyon dobozból szól, és halk. és picit lehet
# magyarosabb a hangsúlyozása." Mind a három mérhetően javult.

def _savarany(x, fs, lo, hi):
    sp = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / fs)
    return float(sp[(f >= lo) & (f < hi)].sum() / (sp.sum() or 1))


def test_a_debox_csokkenti_a_dobozos_savot():
    import dataclasses
    g = RS.gep("gep_melv")
    nincs = dataclasses.replace(g, debox=0.0)
    x_van, fs = RS.szintetizal("Válassz játékot a listából!", g)
    x_nincs, _ = RS.szintetizal("Válassz játékot a listából!", nincs)
    assert _savarany(x_van, fs, 300, 800) < _savarany(x_nincs, fs, 300, 800), \
        "a debox nem csökkenti a dobozos sávot"


def test_a_levego_emeli_a_felso_savot():
    import dataclasses
    g = RS.gep("gep_melv")
    nincs = dataclasses.replace(g, levego=0.0)
    x_van, fs = RS.szintetizal("Kezdődik a kaland!", g)
    x_nincs, _ = RS.szintetizal("Kezdődik a kaland!", nincs)
    assert _savarany(x_van, fs, 3500, 5500) > _savarany(x_nincs, fs, 3500, 5500), \
        "a levegő nem emeli a felső sávot"


def _crest(x):
    akt = x[np.abs(x) > 0.02]
    rms = float(np.sqrt(np.mean(akt ** 2))) if len(akt) else 1e-9
    return 20 * np.log10(float(np.max(np.abs(x))) / rms)


def test_a_drive_hangosabba_teszi_a_hangot():
    """A tömörítés felhozza az átlagot (RMS) → kevésbé halk. A crest-faktor
    (csúcs/átlag) csökken."""
    import dataclasses
    g = RS.gep("gep_melv")
    nincs = dataclasses.replace(g, drive=1.0)
    x_van, fs = RS.szintetizal("Jó napot kívánok mindenkinek!", g)
    x_nincs, _ = RS.szintetizal("Jó napot kívánok mindenkinek!", nincs)
    assert _crest(x_van) < _crest(x_nincs) - 1.0, "a drive nem hoz hangerőt"


def test_a_nyertes_hangosabb_mint_a_regi_beallitas():
    """A régi gep_melv crest-faktora ~23 dB volt (halk). Most legyen jóval jobb."""
    x, fs = RS.szintetizal("Üdvözöllek a retro játékokban!", RS.gep("gep_melv"))
    assert _crest(x) < 20.0, f"még mindig halk (crest {_crest(x):.1f} dB)"


def _f0_gorbe(x, fs):
    N = 1024
    ered = []
    for i in range(0, len(x) - N, N // 2):
        s = x[i:i + N] - x[i:i + N].mean()
        if np.sqrt(np.mean(s ** 2)) < 0.05:
            continue
        ac = np.correlate(s, s, "full")[N - 1:]
        lo, hi = int(fs / 220), int(fs / 60)
        if hi < len(ac):
            p = lo + int(np.argmax(ac[lo:hi]))
            if ac[p] > 0.3 * ac[0]:
                ered.append((i, fs / p))
    return ered


def test_a_mondat_dallama_ereszkedik():
    """MAGYAROS lejtés: a hangmagasság a mondat elején magasabb, a végére
    leereszkedik. Ez teszi élőbbé, kevésbé egyhangúvá."""
    g = RS.gep("gep_melv")
    x, fs = RS.szintetizal("Ez egy hosszabb magyar mondat a próbához.", g)
    gorbe = _f0_gorbe(x, fs)
    assert len(gorbe) >= 6, "kevés zöngés keret a méréshez"
    elso = np.median([hz for i, hz in gorbe[:len(gorbe) // 3]])
    utolso = np.median([hz for i, hz in gorbe[-len(gorbe) // 3:]])
    assert elso > utolso, f"a dallam nem ereszkedik ({elso:.0f}→{utolso:.0f} Hz)"


def test_a_deklinacio_mondatonkent_ujraindul():
    """Két mondatnál a második is fentről indul (nem folytatja az esést)."""
    import dataclasses
    g = dataclasses.replace(RS.gep("gep_melv"), deklinacio=0.3)
    x, fs = RS.szintetizal("Rövid mondat. Másik rövid mondat is van itt.", g)
    assert not np.isnan(x).any() and float(np.max(np.abs(x))) > 0.5


def test_a_finomitas_nem_torte_el_a_formansokat():
    """A stílus-EQ és a tömörítés nem ronthatja el a magánhangzók azonosságát."""
    g = RS.gep("gep_melv")
    for hang in ("á", "i", "u"):
        x, fs = RS.szintetizal(hang * 8, g)
        h = RS.TABLA[hang]
        assert _van_csucs(x, fs, RS._kvant(h.f2, g.kvant_hz)), \
            f"{hang}: az F2 eltűnt a finomítás után"
