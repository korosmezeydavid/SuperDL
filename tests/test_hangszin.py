"""Hangszín-szabályzó (zene 1.3.0) + a Core `-af` horga (4.6.16).

⚠️ A FORMA a lényeg, nem a decibel. Stolmár Barbival egyeztetve: nyilazható
lista megnevezett hangszínekkel + EGY csúszka. Ezek a tesztek azt őrzik, hogy
a forma és a visszaút megmaradjon, és hogy a szűrőlánc olyan szöveg legyen,
amit az ffmpeg tényleg megeszik.

MÉRVE (2026-09-23, ffmpeg 8.1.1, `_meres_hangszin*.py`):
- mind a 6 profil × 3 erősség lefut, rc=0, jön PCM
- basszus 100%: +7.4 dB 70 Hz-en; magas: +6.0 dB 10 kHz-en;
  beszéd: +5.4 dB 2.5 kHz-en és −2.5 dB 70 Hz-en
- limiter NÉLKÜL egy hangos 70 Hz-es jel 47 460 mintán ütközik a falnak,
  limiterrel NULLÁN. Ezért van benne az `alimiter`.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

GYOKER = Path(__file__).resolve().parents[1]


def _modul(relut, nev):
    spec = importlib.util.spec_from_file_location(nev, GYOKER / relut)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nev] = mod
    spec.loader.exec_module(mod)
    return mod


HSZ = _modul("modules_src/zene/zene_mod/hangszin.py", "_hangszin_teszt")


# ---- a forma -------------------------------------------------------------

def test_van_eredeti_hang_es_az_az_elso():
    """⚠️ A LISTA ELSŐ ELEME a visszaút. Vakon az a legfontosabb elem, mert
    egy nyíl-felfelé mindig hazavisz."""
    assert HSZ.PROFILOK[0][0] == "eredeti"
    assert HSZ.ALAP_PROFIL == "eredeti"


def test_minden_profilnak_van_neve_es_leirasa():
    for p in HSZ.PROFILOK:
        assert p[1].strip(), "névtelen hangszín"
        assert len(p[2].strip()) > 15, f"{p[0]}: a leírás nem mond semmit"


def test_nincs_ket_egyforma_azonosito_vagy_nev():
    assert len(set(HSZ.azonositok())) == len(HSZ.PROFILOK)
    assert len(set(HSZ.nevek())) == len(HSZ.PROFILOK)


def test_nem_tul_sok_hangszin():
    """Néhány megnevezett hangszín a cél, nem egy katalógus: egy hosszú
    listát nyilazva végighallgatni büntetés."""
    assert 3 <= len(HSZ.PROFILOK) <= 8


def test_nevek_es_azonositok_egyutt_mozognak():
    assert len(HSZ.nevek()) == len(HSZ.azonositok()) == len(HSZ.PROFILOK)
    for i, a in enumerate(HSZ.azonositok()):
        assert HSZ.index(a) == i
        assert HSZ.nev(a) == HSZ.nevek()[i]


# ---- a szűrőlánc ---------------------------------------------------------

def test_az_eredeti_hang_nem_szur():
    assert HSZ.szuro("eredeti", 100) == ""
    assert HSZ.szuro("eredeti", 0) == ""


def test_a_nulla_erosseg_mindig_az_eredeti():
    """⚠️ A CSÚSZKA ALJA A VISSZAÚT. Ha nullán bármelyik profil szűrne, a
    felhasználó nem tudná kihallgatni, milyen az eredeti."""
    for a in HSZ.azonositok():
        assert HSZ.szuro(a, 0) == ""


def test_az_erosseg_aranyosan_skalaz():
    fel = HSZ.szuro("basszus", 50)
    egesz = HSZ.szuro("basszus", 100)
    assert "g=3.5" in fel and "g=7" in egesz


@pytest.mark.parametrize("a", [x for x in
                               ("beszed", "basszus", "magas", "meleg", "halk")])
def test_a_szuro_ervenyes_ffmpeg_szoveg(a):
    lanc = HSZ.szuro(a, 100)
    assert lanc
    for tag in lanc.split(","):
        assert tag.startswith(("equalizer=", "acompressor=", "alimiter=")), tag
        assert " " not in tag, "szóköz a szűrőláncban elszállítja az ffmpeget"


def test_nincs_tizedesvesszo_a_lancban():
    """⚠️ Magyar Windowson a `%f` vesszőt adna, az ffmpeg viszont csak pontot
    ért. Ez néma, csak NÁLUNK nem jelentkező hiba lenne."""
    for a in HSZ.azonositok():
        for e in (17, 33, 50, 66, 100):
            assert "," not in HSZ.szuro(a, e).replace(",equalizer", "") \
                .replace(",acompressor", "").replace(",alimiter", "")


def test_a_kiemeles_kap_limitert():
    """MÉRVE: limiter nélkül egy hangos 70 Hz-es jel 47 460 mintán ütközött
    a falnak (torzítás), limiterrel nullán."""
    assert "alimiter" in HSZ.szuro("basszus", 100)
    assert "alimiter" in HSZ.szuro("magas", 100)


def test_a_tisztan_halkito_nem_kap_limitert_feleslegesen():
    assert HSZ.szuro("eredeti", 100) == ""


def test_az_erosseg_be_van_szoritva():
    assert HSZ.szuro("basszus", 500) == HSZ.szuro("basszus", 100)
    assert HSZ.szuro("basszus", -20) == ""


def test_ismeretlen_profil_nem_dol_el():
    assert HSZ.szuro("nincs-ilyen", 100) == ""
    assert HSZ.nev("nincs-ilyen") == HSZ.PROFILOK[0][1]
    assert HSZ.index("nincs-ilyen") == 0


# ---- a kimondott mondat --------------------------------------------------

def test_az_eredeti_hangot_nem_szazalekban_mondjuk():
    assert HSZ.mondat("eredeti", 100) == "Eredeti hang, szűrés nélkül."
    assert HSZ.mondat("basszus", 0) == "Eredeti hang, szűrés nélkül."


def test_a_mondat_nevet_es_szazalekot_mond():
    m = HSZ.mondat("basszus", 40)
    assert "40 százalék" in m and "Basszus" in m


# ---- a Core horga --------------------------------------------------------

def test_a_player_atveszi_es_visszaadja_a_szurot():
    from superdl.audioengine import Player
    p = Player()
    assert p.audio_filter == ""
    assert p.set_audio_filter("equalizer=f=70:g=7") is False   # nem szól semmi
    assert p.audio_filter == "equalizer=f=70:g=7"


def test_ugyanaz_a_szuro_nem_kivan_ujrainditast():
    """⚠️ Enélkül minden nyilazás megszakítaná a zenét akkor is, ha semmi
    nem változott."""
    from superdl.audioengine import Player
    p = Player()
    p.set_audio_filter("x=1")
    assert p.set_audio_filter("x=1") is False
    assert p.set_audio_filter("  x=1  ") is False


def test_a_play_beteszi_a_szurot_a_parancsba():
    import inspect
    from superdl.audioengine import Player
    src = inspect.getsource(Player.play)
    assert 'cmd += ["-af", self._af]' in src
    assert src.index("self._af") < src.index('"-f", "s16le"')


# ---- megjegyzés és visszatöltés ------------------------------------------

@pytest.fixture
def KT(tmp_path, monkeypatch):
    m = _modul("modules_src/zene/zene_mod/konyvtar.py", "_kt_hangszin_teszt")
    monkeypatch.setattr(m, "BEALLITAS", tmp_path / "zene.json")
    return m


def test_a_konyvtar_alapbol_az_eredeti_hangot_adja(KT):
    """⚠️ Aki nem nyúl hozzá, pontosan azt hallja, amit eddig: egy
    hangszín-szabályzó bevezetése senkinek nem változtathatja meg a hangját."""
    assert KT.hangszin_betolt() == ("eredeti", 100)


def test_a_konyvtar_menti_es_visszaadja(KT):
    KT.hangszin_ment("basszus", 40)
    assert KT.hangszin_betolt() == ("basszus", 40)


def test_a_hangszin_mentese_nem_torli_a_tobbi_beallitast(KT):
    KT.hangero_ment(0.3)
    KT.hangszin_ment("meleg", 70)
    assert KT.hangero_betolt() == pytest.approx(0.3)
    assert KT.hangszin_betolt() == ("meleg", 70)


def test_a_serult_erosseg_nem_dol_el(KT):
    KT.beallit(hangszin="magas", hangszin_erosseg="zagyva")
    assert KT.hangszin_betolt() == ("magas", 100)


# ---- az ablak kötései ----------------------------------------------------

WIN = (GYOKER / "modules_src/zene/zene_mod/zenewin.py").read_text(
    encoding="utf-8")
DLG = (GYOKER / "modules_src/zene/zene_mod/hangszinwin.py").read_text(
    encoding="utf-8")


def test_a_ctrl_shift_h_a_hangszin_es_megelozi_a_ctrl_h_t():
    """⚠️ A SORREND SZÁMÍT: ha a sima Ctrl+H ága előbb jön, elnyeli a
    Ctrl+Shift+H-t, és a hangkimenet-választó nyílna meg helyette."""
    hsz = WIN.index("if ctrl and shift and kod in (ord(\"H\")")
    kim = WIN.index("if ctrl and kod in (ord(\"H\")")
    assert hsz < kim


def test_a_hangszin_a_helyi_menuben_is_ott_van():
    assert "self._hangszin_parbeszed" in WIN
    assert "Ctrl+Shift+H" in WIN


def test_a_lejatszo_letrehozasakor_bekerul_a_hangszin():
    """Enélkül az indítás utáni ELSŐ szám a mentett beállítás nélkül szólna."""
    i = WIN.index("def _motor")
    blokk = WIN[i:i + 1400]
    assert "hangszin_allit" in blokk


def test_a_parbeszed_elobeni_allitast_visszavonja():
    assert "def _megse" in DLG
    assert "_kezdo" in DLG


def test_a_csuszka_az_elengedesre_alkalmaz_nem_minden_lepesre():
    """⚠️ EVT_SCROLL_CHANGED: minden köztes értéknél újraindítani a
    lejátszást szaggatna."""
    assert "EVT_SCROLL_CHANGED" in DLG
    assert "EVT_SCROLL," not in DLG


def test_a_parbeszedben_nincs_alt_utkozes():
    import re
    betuk = [m.group(1).lower()
             for m in re.finditer(r'label="[^"]*?&(\w)', DLG)]
    assert len(betuk) == len(set(betuk)), f"ütköző Alt-betűk: {betuk}"


def test_a_lista_cimkeje_a_lista_elott_jon_letre():
    """⚠️ A képernyőolvasó a LÉTREHOZÁSI sorrend szerint párosít."""
    assert DLG.index("&Hangszín") < DLG.index("self.lista = wx.ListBox")
    assert DLG.index("&Mértéke") < DLG.index("self.csuszka = wx.Slider")


# ---- a keverőlejátszó ----------------------------------------------------

KEV = (GYOKER / "modules_src/zene/zene_mod/keverolejatszo.py").read_text(
    encoding="utf-8")


def test_a_hangszin_mindket_lejatszora_megy():
    """⚠️ Az áttűnés a MÁSIK lejátszót hozza be – ha csak az aktívat
    állítanánk, a következő szám a régi hangszínnel szólalna meg."""
    i = KEV.index("def hangszin_allit")
    blokk = KEV[i:KEV.index("def kimenet(", i)]
    assert "for p in (self._a, self._b)" in blokk


def test_a_hangszin_valtas_szunetben_szunetben_hagy():
    i = KEV.index("def hangszin_allit")
    blokk = KEV[i:KEV.index("def kimenet(", i)]
    assert "is_paused" in blokk and "pause()" in blokk


def test_attunes_kozben_nincs_ujrainditas():
    i = KEV.index("def hangszin_allit")
    blokk = KEV[i:KEV.index("def kimenet(", i)]
    assert "_attunesben" in blokk


# ---- manifest ------------------------------------------------------------

def test_a_zene_manifest_emelve_es_koti_a_core_verziot():
    d = json.loads((GYOKER / "modules_src/zene/manifest.json")
                   .read_text(encoding="utf-8"))
    # legalább 1.3.0 – a későbbi zene-körök tovább emelik
    assert tuple(int(x) for x in d["version"].split(".")) >= (1, 3, 0)
    assert d["min_core_version"] == "4.6.16"


def test_a_core_verzio_legalabb_az_amit_a_zene_ker():
    """⚠️ Nem pontos egyezés: egy későbbi Core-kiadás ne törje el ezt a
    tesztet (4.6.17-ben pontosan ez történt)."""
    import superdl
    v = tuple(int(x) for x in superdl.__version__.split("."))
    assert v >= (4, 6, 16)
