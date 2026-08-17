# -*- coding: utf-8 -*-
"""OFFLINE FORDÍTÁS – a magbeli réteg őrei.

A felhasználó kérése: „adjuk ki a magot is, hadd legyen nekik meg az offline
verzió is”. Az offline fordítás azért került a MAGBA, mert fordított (bináris)
futtatókörnyezetet igényel, amit egy modul-ZIP nem tud telepíteni.

Itt a tiszta logikát őrizzük (útvonal-választás, pivot, mondatvágás, csomag-
kezelés) – modell nélkül, hálózat nélkül. A tényleges fordítást élő próbában
ellenőriztem (en→hu és pl→hu angolon át).
"""

import json

import pytest

from superdl import offlineford as OF


_INDEX = [
    {"from_code": "en", "to_code": "hu", "links": ["https://p/en_hu.argosmodel"]},
    {"from_code": "hu", "to_code": "en", "links": ["https://p/hu_en.argosmodel"]},
    {"from_code": "pl", "to_code": "en", "links": ["https://p/pl_en.argosmodel"]},
    {"from_code": "en", "to_code": "de", "links": ["https://p/en_de.argosmodel"]},
]


# ----------------------------------------------------------- útvonal

def test_kozvetlen_par_egy_lepes():
    ut = OF.utvonal("en", "hu", _INDEX)
    assert [(p["from_code"], p["to_code"]) for p in ut] == [("en", "hu")]


def test_pivot_angolon_at():
    """A nyílt modellek angol-központúak: lengyel→magyar két lépés."""
    ut = OF.utvonal("pl", "hu", _INDEX)
    assert [(p["from_code"], p["to_code"]) for p in ut] == [("pl", "en"),
                                                            ("en", "hu")]


def test_ha_nincs_ut_ures_a_valasz():
    """Nem hazudunk: ha a nyelvhez nincs modell, azt meg kell mondani."""
    assert OF.utvonal("sw", "hu", _INDEX) == []
    assert OF.utvonal("hu", "de", _INDEX) != []      # hu→en→de viszont megy


def test_hianyzo_csak_a_meg_nem_telepitetteket_adja(monkeypatch):
    monkeypatch.setattr(OF, "telepitett_parok", lambda: [("pl", "en")])
    h = OF.hianyzo("pl", "hu", _INDEX)
    assert [(p["from_code"], p["to_code"]) for p in h] == [("en", "hu")]
    monkeypatch.setattr(OF, "telepitett_parok",
                        lambda: [("pl", "en"), ("en", "hu")])
    assert OF.hianyzo("pl", "hu", _INDEX) == []


def test_a_csomag_url_tobbfele_mezobol_kiolvashato():
    assert OF._csomag_url({"links": ["a", "b"]}) == "a"
    assert OF._csomag_url({"link": "c"}) == "c"
    assert OF._csomag_url({"url": "d"}) == "d"
    assert OF._csomag_url({}) == ""


# -------------------------------------------------------- mondatvágás

def test_mondatonkent_vagunk():
    """EZ NEM SZÉPÉSZET: egyben beadva a modell az első mondat után elhagyja a
    szöveg többi részét – élesben pontosan ez történt (a levél aláírása
    eltűnt), ezért mondatonként fordítunk."""
    m = OF.mondatokra("Első mondat. Második mondat! Harmadik?")
    assert m == ["Első mondat.", "Második mondat!", "Harmadik?"]


def test_a_bekezdesek_is_hatarok():
    assert OF.mondatokra("Szia\n\nÜdv: Dávid") == ["Szia", "Üdv: Dávid"]


def test_ures_szoveg_ures_lista():
    assert OF.mondatokra("") == [] and OF.mondatokra(None) == []
    assert OF.mondatokra("   \n\n  ") == []


# ------------------------------------------------------------ csomag

def test_a_telepitett_parokat_a_metadatabol_olvassuk(tmp_path, monkeypatch):
    monkeypatch.setattr(OF, "modell_mappa", lambda: tmp_path)
    (tmp_path / "en_hu").mkdir()
    (tmp_path / "en_hu" / "metadata.json").write_text(
        json.dumps({"from_code": "en", "to_code": "hu"}), encoding="utf-8")
    (tmp_path / "romlott").mkdir()
    (tmp_path / "romlott" / "metadata.json").write_text("{nem json",
                                                        encoding="utf-8")
    assert OF.telepitett_parok() == [("en", "hu")], \
        "egy romlott csomag ne vigye el a többit"


def test_nincs_mappa_nincs_baj(tmp_path, monkeypatch):
    monkeypatch.setattr(OF, "modell_mappa", lambda: tmp_path / "nincs")
    assert OF.telepitett_parok() == []


def test_a_mar_meglevo_csomagot_nem_tolti_le_ujra(tmp_path, monkeypatch):
    monkeypatch.setattr(OF, "modell_mappa", lambda: tmp_path)
    (tmp_path / "en_hu").mkdir()
    (tmp_path / "en_hu" / "metadata.json").write_text("{}", encoding="utf-8")

    def tilos(*a, **kw):
        raise AssertionError("nem szabad letölteni, ha már megvan")

    monkeypatch.setattr("urllib.request.urlopen", tilos)
    assert OF.letolt({"from_code": "en", "to_code": "hu",
                      "links": ["https://p/x"]}) == tmp_path / "en_hu"


def test_url_nelkuli_csomagra_ertheto_hiba(tmp_path, monkeypatch):
    monkeypatch.setattr(OF, "modell_mappa", lambda: tmp_path)
    with pytest.raises(RuntimeError):
        OF.letolt({"from_code": "xx", "to_code": "hu"})


def test_a_futtatokornyezet_jelenlete_lekerdezheto():
    """A modulok ezzel döntik el, felajánlhatják-e az offline fordítást."""
    assert OF.elerheto() in (True, False)


def test_a_modell_mappa_a_felhasznalo_sajat_mappajaban_van():
    assert ".superdl" in str(OF.modell_mappa())
