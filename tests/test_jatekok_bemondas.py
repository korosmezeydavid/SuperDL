# -*- coding: utf-8 -*-
"""Képernyőolvasós használhatóság a játékokban (Bizik Péter Károly, NVDA).

Három panasz, három ellenőrzés:
1. A körönkénti bemondás túl hosszú volt: a teljes tábla minden körben
   elhangzott, „(1-6)" betoldással – normál felolvasási sebességnél
   követhetetlen. Most csak a SAJÁT gödrök/tálak és a két pontszám hangzik el;
   a teljes tábla az „állás" szóra.
2. A játékba lépve egy néma szövegdobozban áll a játékos: a kérdést a
   képernyőolvasó saját fókuszbemondása félbeszakítja. Most a mező NEVE maga
   a kérdés.
3. Az ablakos játékok (pl. Póker) hibája némán a konzolra esett vissza, ahol
   a játék nincs regisztrálva – így úgy tűnt, „kimaradt".
"""
import importlib
import inspect
import re

import pytest

BASE = "modules_src.jatekok.jatekok_mod"
JR = pytest.importorskip(BASE + ".jatekok")
U = importlib.import_module(BASE + ".jatekok._util")
M = importlib.import_module(BASE + ".jatekok.mancala")


# ---- 1. rövid körönkénti bemondás -------------------------------------

def test_awari_rovid_bemondas_nincs_benne_a_gep_sora():
    b = M._awari_uj(1)
    rovid = M._awari_sajat(b)
    assert "gép gödrei" not in rovid
    assert "(1-6)" not in rovid
    assert "Gödreid" in rovid


def test_awari_teljes_allas_keresre_mindent_tartalmaz():
    b = M._awari_uj(1)
    teljes = M._awari_allas(b)
    assert "gödreid" in teljes.lower() and "gép gödrei" in teljes
    assert "(1-6)" not in teljes


def test_maja_rovid_bemondas():
    g = M._maja_uj()
    rovid = M._maja_sajat(g)
    assert "gép táljai" not in rovid
    assert "(1-6)" not in rovid


def test_a_szam_a_godorhoz_van_kotve():
    """A puszta számsor összefolyt; most minden szám a sorszámával jár."""
    b = M._awari_uj(1)
    b[0] = 0
    assert "1: 0" in M._awari_sajat(b)


def _bot_allassal(kertek):
    """Első körben ÁLLÁST kér, utána rendesen játszik."""
    def bot(k, ki):
        kl = k.lower()
        if "igen/nem" in kl or "ismét" in kl or "még egyet" in kl:
            return "nem"
        if "indulás" in kl:
            return "1"
        if not kertek:
            kertek.append(True)
            return "állás"
        for _, szoveg in reversed(ki):
            m = re.search(r"Gödreid\s*[–-]\s*((?:\d+: \d+(?:, )?)+)",
                          str(szoveg))
            if m:
                for i, x in enumerate(m.group(1).split(", "), 1):
                    if int(x.split(":")[1]) > 0:
                        return str(i)
                break
        return "1"
    return bot


def test_allas_szora_tenyleg_elhangzik_a_teljes_tabla():
    """KORÁBBAN: az „állás" ág csak `continue`-olt, és a tábla azért hangzott
    el, mert a ciklus elején úgyis elhangzott. A rövidítés után ez néma
    maradt volna – az „állás"-nak MAGÁNAK kell válaszolnia."""
    ki = U.lejatsz(JR.REGISZTER["awari"], _bot_allassal([]), max_lepes=200000)
    szovegek = " ".join(str(s) for _, s in ki)
    assert "gép gödrei" in szovegek, "az „állás” nem mondta el a teljes táblát"


def test_allas_nelkul_nem_hangzik_el_a_gep_sora_koronkent():
    def bot(k, ki):
        kl = k.lower()
        if "igen/nem" in kl or "ismét" in kl:
            return "nem"
        if "indulás" in kl:
            return "1"
        for _, szoveg in reversed(ki):
            m = re.search(r"Gödreid\s*[–-]\s*((?:\d+: \d+(?:, )?)+)",
                          str(szoveg))
            if m:
                for i, x in enumerate(m.group(1).split(", "), 1):
                    if int(x.split(":")[1]) > 0:
                        return str(i)
                break
        return "1"
    ki = U.lejatsz(JR.REGISZTER["awari"], bot, max_lepes=200000)
    szovegek = " ".join(str(s) for _, s in ki)
    assert "A gép gödrei" not in szovegek


# ---- 2. a kérdés legyen a beviteli mező NEVE --------------------------

def test_a_kerdes_a_mezo_neve_lesz():
    kon = importlib.import_module(BASE + ".jatekkonzol")
    forras = inspect.getsource(kon)
    assert "_var_bemenet(True, kerdes=payload)" in forras
    assert "def _bemenet_neve" in forras
    assert "class _NevAccessible" in forras


def test_a_kerdes_megmondja_mit_var():
    """A mancala kérdései önmagukban is elmondják, mit kell beírni."""
    for f in (M.jatek_awari, M.jatek_maja):
        forras = inspect.getsource(f)
        assert "Egy szám" in forras          # megmondja, mit vár
        assert "A teljes állásért" in forras  # és a kiutat is


# ---- 3. az ablakos játékok hibája nem tűnhet el ------------------------

def test_az_ablakos_jatek_hibaja_naploba_kerul():
    kon = importlib.import_module(BASE + ".jatekkonzol")
    forras = inspect.getsource(kon.indit_jatek)
    # a BETÖLTÉS és az INDÍTÁS hibája is naplóba kerül
    assert forras.count("_log.exception") >= 2
    # és a felhasználó is megtudja – nem esik némán vissza a konzolra
    assert "nem indult el" in forras


def test_a_poker_indithato():
    kon = importlib.import_module(BASE + ".jatekkonzol")
    assert kon.indithato("poker")
    assert kon._ablak_osztaly("poker") is not None
