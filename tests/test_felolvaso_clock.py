"""felolvaso: az INTEGRÁLÓ óra és a film-hang nélküli feliratolvasás őrei.

Egy felhasználó jelezte: „megtalálja a feliratot, de az »épp felolvasott
felirat« mező mindig üres". Gyökér-ok: a felolvasást KIZÁRÓLAG a film
hang-pozíciója hajtotta – ha az beragadt (indulási puffer, nem dekódolható
film-hang, stream-akadás), a narráció NÉMÁN leállt. Javítás: integráló óra
(beragadáskor fali óra lép előre) + ha a film hangja egyáltalán nem játszható,
a feliratot csend fölött akkor is felolvassuk. Ezek a tesztek ezt őrzik.
"""

import inspect
import time
import types

import pytest

pytest.importorskip("wx")
W = pytest.importorskip("modules_src.felolvaso.felolvaso_mod.felolvasowin")


def _fake_frame(**kw):
    """A _clock/_clock_reset TISZTA algoritmusa – valódi ablak/hangeszköz nélkül
    (így CI-n is fut). Csak azokat a mezőket adjuk meg, amiket a _clock használ."""
    o = types.SimpleNamespace()
    o._clk_pos = 0.0
    o._clk_apos = 0.0
    o._clk_wall = time.monotonic()
    o._clk_t0 = time.monotonic()
    o._clk_started = False
    o._subs_only = False
    o._subs_paused = False

    class _Film:
        _p = 0.0
        def position(self):
            return self._p
    o.film = _Film()
    for k, v in kw.items():
        setattr(o, k, v)
    return o


def test_ora_fali_orat_hasznal_ha_a_hang_beragad():
    """A LÉNYEG: ha a hang elindult, de aztán beragad (a pozíció nem nő), a
    fali órának ELŐRE kell léptetnie – különben a felolvasás némán leáll."""
    o = _fake_frame(_clk_started=True)
    o.film._p = 2.0
    o._clk_apos = 2.0                     # a hang most NEM halad
    o._clk_wall = time.monotonic() - 1.0  # 1 mp telt el
    pos = W.FelolvasoFrame._clock(o)
    assert pos >= 0.9, "beragadt hangnál a fali órának léptetnie kell"


def test_ora_koveti_az_egeszseges_hangot():
    """Ha a hang egészségesen halad, az órát a hang-pozíció vezérli (pontos
    szinkron)."""
    o = _fake_frame()
    o._clk_apos = 0.0
    o.film._p = 0.2
    o._clk_wall = time.monotonic() - 0.2
    pos = W.FelolvasoFrame._clock(o)
    assert pos > 0.0
    assert o._clk_started, "a hang megindulását észlelnie kell"


def test_ora_subs_only_tiszta_fali_ora():
    """Film-hang nélküli feliratolvasásnál nincs hang-pozíció → az óra tisztán a
    fali órából jön, hogy a felirat akkor is menjen."""
    o = _fake_frame(_subs_only=True)
    o.film._p = 0.0
    o._clk_wall = time.monotonic() - 1.0
    pos = W.FelolvasoFrame._clock(o)
    assert pos >= 0.9


def test_ora_indulasi_puffer_alatt_var():
    """Induláskor, amíg a hang még nem szólalt meg (és nincs 2,5 mp-es türelmi
    idő túllépve), az óra 0 marad – ne olvasson bele a pufferbe idő előtt."""
    o = _fake_frame()                    # _clk_started=False, friss _clk_t0
    o.film._p = 0.0
    o._clk_wall = time.monotonic() - 0.3
    pos = W.FelolvasoFrame._clock(o)
    assert pos == 0.0


def test_ora_soha_nem_ugrik_vissza():
    """Az óra sosem léphet vissza (a scheduler egyszer-kiadós; visszaugrás
    duplán olvastatná ugyanazt a sort)."""
    o = _fake_frame(_clk_started=True)
    seq = []
    for _ in range(5):
        o._clk_wall = time.monotonic() - 0.1
        seq.append(W.FelolvasoFrame._clock(o))
    assert seq == sorted(seq), f"az óra visszalépett: {seq}"


def test_hiba_eseten_felirat_film_hang_nelkul():
    """Ha a film hangja nem játszható le, de van betöltött felirat, ne álljunk
    le némán – kapcsoljunk film-hang nélküli feliratolvasásra."""
    src = inspect.getsource(W.FelolvasoFrame._on_film_state)
    assert "_subs_only" in src
    assert "feliratot felolvasom" in src


def test_f8_diagnosztika_letezik():
    """Az F8 mondja be az állapotot (hibakereséshez)."""
    assert hasattr(W.FelolvasoFrame, "_diag")
    assert "WXK_F8" in inspect.getsource(W.FelolvasoFrame._on_key)


def test_announce_hangosan_is_beszel():
    """VAK-KRITIKUS: a státuszsor/címke változását a képernyőolvasó nem olvassa
    fel magától – az _announce-nak a program SAJÁT hangján (selfvoice) is be KELL
    mondania, különben a felhasználó semmilyen jelzést (F8-at sem) nem hall."""
    src = inspect.getsource(W.FelolvasoFrame._announce)
    assert "selfvoice" in src
    assert "speak" in src and "force=True" in src


def test_f8_es_indulas_mondja_a_verziot():
    """A felhasználó HALLJA a verziót (indításkor és F8-ra), hogy tudja, tényleg
    a friss modul fut-e – ez oldja fel a »frissítettem, de ugyanaz« kétséget."""
    assert hasattr(W, "MOD_VERSION")
    assert "MOD_VERSION" in inspect.getsource(W.FelolvasoFrame._diag)


def test_proaktiv_riasztas_ha_nem_indul():
    """Ha a lejátszás elindul, de pár mp-ig egyetlen felirat sem szólal meg, a
    program magától bemondja az állapotot (F8 nélkül is)."""
    src = inspect.getsource(W.FelolvasoFrame._tick)
    assert "_warned" in src and "_fired_any" in src


def test_alapbol_magyar_hangot_valaszt():
    """Ne a lista első (gyakran ANGOL SAPI) hangját válassza, hanem magyart /
    a beépített eSpeak magyart – különben a magyar feliratot angolul olvasná."""
    o = types.SimpleNamespace(_voices=[
        ("SAPI – Microsoft Zira Desktop - English", "sapi", "Zira English"),
        ("SAPI – Microsoft Szabolcs - Hungarian", "sapi", "Szabolcs Hungarian"),
        ("eSpeak magyar", "espeak", "espeak:hu"),
    ])
    assert W.FelolvasoFrame._default_voice_index(o) == 1     # a magyar SAPI

    o2 = types.SimpleNamespace(_voices=[
        ("SAPI – Zira English", "sapi", "Zira English"),
        ("eSpeak magyar", "espeak", "espeak:hu"),
    ])
    assert W.FelolvasoFrame._default_voice_index(o2) == 1    # a beépített eSpeak


def test_synth_espeak_tartalek_hiba_eseten():
    """Ha a választott motor hibázik, a _synth AUTOMATIKUSAN eSpeak-re vált –
    inkább szóljon, mint hogy néma maradjon; a hibát visszaadja, nem nyeli el."""
    from modules_src.felolvaso.felolvaso_mod import narrator as N
    calls = []

    def fake_synth(eng, vid, text, rate=0, pitch=0):
        calls.append(eng)
        if eng == "sapi":
            raise RuntimeError("CoInitialize has not been called")
        return "C:/tmp/ok.wav"

    orig = N.synth_to_file
    N.synth_to_file = fake_synth
    try:
        o = types.SimpleNamespace()
        path, err = W.FelolvasoFrame._synth(o, "sapi", "v", "szöveg", 7)
    finally:
        N.synth_to_file = orig
    assert path == "C:/tmp/ok.wav"          # az eSpeak-tartalék adott hangot
    assert "sapi" in err.lower()            # a hibát NEM nyelte el
    assert calls == ["sapi", "espeak"]      # előbb sapi, majd eSpeak-tartalék


def test_hangeszkoz_kovetes_es_f6():
    """A film HOSSZÚ streamje az indításkori eszközön ragad; eszközváltáskor
    (pl. Bluetooth) át kell vezetni. Legyen automatikus követés a _tick-ben és
    kézi F6 is."""
    assert hasattr(W.FelolvasoFrame, "_reroute_audio")
    ksrc = inspect.getsource(W.FelolvasoFrame._on_key)
    assert "WXK_F6" in ksrc
    tsrc = inspect.getsource(W.FelolvasoFrame._tick)
    assert "_cur_out_name" in tsrc and "_reroute_audio" in tsrc


def test_reroute_a_pozicion_ujranyit():
    """Az átvezetés a jelenlegi pozíción nyitja újra a filmet (seek), és
    újrahorgonyozza az órát – nem ugrik el az idővonal."""
    src = inspect.getsource(W.FelolvasoFrame._reroute_audio)
    assert "film.seek" in src
    assert "_clock_reset" in src


def test_sapi_com_init_a_szintezis_utban():
    """A SAPI COM-inicializálás legyen a szintézis-útvonalon (háttérszál-biztos)."""
    from modules_src.felolvaso.felolvaso_mod import narrator as N
    src = inspect.getsource(N.synth_to_file)
    assert "_com_init" in src
    assert "CoInitialize" in inspect.getsource(N._com_init)


def test_ugras_es_leallitas_ujrahorgonyozza_az_orat():
    """Ugrás/leállítás után az órát újra kell horgonyozni (különben a fali óra a
    régi ponthoz képest ugrana)."""
    for meth in (W.FelolvasoFrame._seek, W.FelolvasoFrame._stop,
                 W.FelolvasoFrame._toggle):
        assert "_clock_reset" in inspect.getsource(meth), \
            "hiányzik az óra újrahorgonyzása"
