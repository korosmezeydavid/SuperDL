# -*- coding: utf-8 -*-
"""Csevejcenter — „halkan lehet hallani a másikat" (Dávid jelzése, 2026-09-01).

HÁROM külön oka volt, és egyik sem az, hogy „kevés a hangerő":

1. a modulban EGYETLEN erősítés-fokozat sem volt (volume/gain/hangero: nulla
   találat) — ha a mikrofon halk volt, nem volt hol felhozni;
2. az egyenlő-teljesítményű panorámázás közepén 3 dB veszik el, és EGY
   résztvevőnél mindenki középen ül;
3. a klipp-védelem (`ki /= cs`) blokkonként az EGÉSZ keveréket lehúzta, ha
   bárki túlcsordult — vagyis egy hangosabb ember folyamatosan lenyomta a
   halkabbat, és minél többen voltak, annál halkabb lett mindenki.

A 3. a legfontosabb: enélkül a hangerő-szabályzók hatástalanok lettek volna,
mert a keverő pont annyit vesz vissza, amennyit a boost ad.
"""
import importlib

import numpy as np

TH = importlib.import_module("modules_src.csevej.csevej_mod.terhang")


def _kocka(ampl=0.1, n=None):
    n = n or TH.BLOKK
    return np.full(n, ampl, dtype=np.float32)


# ---- 3. ok: a limiter nem pumpál --------------------------------------

def test_a_hangos_ember_nem_nyomja_le_tartosan_a_halkat():
    """A RÉGI viselkedés: egyetlen túlcsorduló blokk az EGÉSZ keveréket
    lehúzta, majd a következő blokkban visszaugrott — ez pumpált."""
    k = TH.Kevero()
    k.set_ulesek({"halk": 0.0, "hangos": 0.0})

    # egy blokk, amiben a hangos túlcsordul
    k.add("halk", _kocka(0.05))
    k.add("hangos", _kocka(0.95))
    elso = k.kimenet()
    assert float(np.max(np.abs(elso))) <= 1.0 + 1e-6

    # a hangos elhallgat; a halk NEM maradhat lehúzva
    for _ in range(60):                      # ~1,2 másodperc
        k.add("halk", _kocka(0.05))
        ki = k.kimenet()
    csucs = float(np.max(np.abs(ki)))
    assert csucs > 0.05, \
        "a halk résztvevőnek vissza kell jönnie, miután a hangos elhallgatott"


def test_a_limiter_nem_enged_at_torzitast():
    k = TH.Kevero()
    k.set_ulesek({"a": 0.0, "b": 0.0, "c": 0.0})
    for nev in ("a", "b", "c"):
        k.add(nev, _kocka(0.9))
    ki = k.kimenet()
    assert float(np.max(np.abs(ki))) <= 1.0 + 1e-6


def test_a_lehuzas_azonnali_a_visszaengedes_fokozatos():
    g = TH._limiter_lepes(np.full((10, 2), 2.0, dtype=np.float32), 1.0)
    assert abs(g - 0.5) < 1e-6, "a lehúzásnak azonnalinak kell lennie"
    vissza = TH._limiter_lepes(np.zeros((10, 2), dtype=np.float32), 0.5)
    assert 0.5 < vissza < 1.0, "a visszaengedés fokozatos, nem ugrik vissza"


# ---- 2. ok: a közép 3 dB-je ------------------------------------------

def test_a_kozep_nem_halkabb_mint_a_jel():
    """Kettesben mindenki középen ül; eddig ott 0,707-tel szólt mindenki."""
    k = TH.Kevero()
    k.set_ulesek({"a": 0.0})
    k.add("a", _kocka(0.5))
    ki = k.kimenet()
    assert abs(float(np.max(np.abs(ki))) - 0.5) < 0.01, \
        "középen a jelnek egységnyinek kell maradnia"


# ---- 1. ok: a hangerő-szabályzók --------------------------------------

def test_resztvevonkenti_hangero():
    """A kérés magva: aki halkan hallatszik, ŐT hozzuk fel — nem az egészet."""
    k = TH.Kevero()
    k.set_ulesek({"halk": 0.0})
    k.set_hangero("halk", 2.0)
    k.add("halk", _kocka(0.2))
    ki = k.kimenet()
    assert float(np.max(np.abs(ki))) > 0.35


def test_a_nulla_hangero_elnemit_egy_embert():
    k = TH.Kevero()
    k.set_ulesek({"a": 0.0})
    k.set_hangero("a", 0.0)
    k.add("a", _kocka(0.5))
    assert float(np.max(np.abs(k.kimenet()))) < 1e-6


def test_a_hangero_korlatos():
    k = TH.Kevero()
    assert k.set_hangero("a", 99.0) == TH.HANGERO_MAX
    assert k.set_hangero("a", -5.0) == 0.0


def test_fo_hangero_mindenkire_hat():
    k = TH.Kevero()
    k.set_ulesek({"a": 0.0, "b": 0.0})
    k.set_fo_hangero(0.5)
    k.add("a", _kocka(0.4))
    k.add("b", _kocka(0.4))
    halk = float(np.max(np.abs(k.kimenet())))

    k2 = TH.Kevero()
    k2.set_ulesek({"a": 0.0, "b": 0.0})
    k2.add("a", _kocka(0.4))
    k2.add("b", _kocka(0.4))
    teli = float(np.max(np.abs(k2.kimenet())))
    assert halk < teli


def test_az_ismeretlen_nev_alapbol_egysegnyi():
    assert TH.Kevero().hangero("aki-meg-nem-szolalt") == 1.0


# ---- mikrofon-erősítés ------------------------------------------------

def test_a_lagy_limiter_a_kuszob_alatt_nem_nyul_a_jelhez():
    x = np.array([0.0, 0.2, -0.5, 0.69], dtype=np.float32)
    assert np.allclose(TH.lagy_limit(x), x)


def test_a_lagy_limiter_nem_vag_kemenyen():
    """Kemény vágás RECSEG — és torz hangot erősíteni rosszabb, mint halkat."""
    x = np.array([3.0, -3.0], dtype=np.float32)
    y = TH.lagy_limit(x)
    assert np.all(np.abs(y) < 1.0)
    # monoton: a nagyobb bemenet nagyobb kimenet marad (nem lapul egybe)
    a = float(TH.lagy_limit(np.array([1.2], dtype=np.float32))[0])
    b = float(TH.lagy_limit(np.array([2.0], dtype=np.float32))[0])
    assert b > a


def test_a_mikrofon_eros_korlatos():
    t = TH.TerbeliHang()
    assert t.set_mikrofon_eros(100.0) == TH.MIK_EROS_MAX
    assert t.set_mikrofon_eros(0.0) == TH.MIK_EROS_MIN


# ---- a kimondott szint-tanács (vakon nincs szintmérő) -----------------

def test_a_tanacs_megmondja_mit_tegyen():
    assert "Nem hallok semmit" in TH.szint_tanacs(0.0)
    assert "Emeld" in TH.szint_tanacs(0.05)
    assert "jó szinten" in TH.szint_tanacs(0.5)
    assert "torzíthat" in TH.szint_tanacs(0.95)


def test_a_tanacs_minden_szintre_ad_valamit():
    for cs in (0.0, 0.01, 0.05, 0.1, 0.3, 0.85, 0.9, 1.0):
        assert TH.szint_tanacs(cs).strip()
