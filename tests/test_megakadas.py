# -*- coding: utf-8 -*-
"""A MEGAKADÁS-FIGYELŐ tesztjei.

Tóth László jelzése (2026-09-14): a program a fájlválasztóban befagyott, és
„az eseménynaplóban utána semmi nyoma nem maradt". A befagyás NEM összeomlás:
a faulthandler csak haldokló folyamatról ír. Ezek a tesztek azt rögzítik,
hogy a befagyás mostantól nyomot hagy — és hogy a nyomát NEM keverjük össze
egy valódi összeomlással.
"""
import time

import pytest

from superdl import osszeomlas


@pytest.fixture
def tiszta(tmp_path, monkeypatch):
    """Friss naplófájl, a modul globális állapota visszaállítva."""
    naplo = tmp_path / "osszeomlas.log"
    monkeypatch.setattr(osszeomlas, "NAPLO", naplo)
    monkeypatch.setattr(osszeomlas, "_OLVASVA", tmp_path / "olvasva.txt")
    f = open(naplo, "a", encoding="utf-8")
    monkeypatch.setattr(osszeomlas, "_fajl", f)
    monkeypatch.setattr(osszeomlas, "_sziv", None)
    monkeypatch.setattr(osszeomlas, "_megakadva", False)
    monkeypatch.setattr(osszeomlas, "_megakadas_db", 0)
    yield naplo
    f.close()


def test_eletjel_nelkul_nem_allitunk_semmit():
    """Ha SOHA nem volt életjel, nem tudjuk, befagyott-e. A „nem tudom" nem
    ugyanaz, mint a „nem fagyott be" — de riasztani sem szabad rá."""
    osszeomlas._sziv = None
    assert osszeomlas.megakadt() is False


def test_friss_eletjel_utan_nincs_megakadas():
    osszeomlas.sziv_dobban()
    assert osszeomlas.megakadt() is False


def test_regi_eletjel_megakadas():
    osszeomlas._sziv = time.monotonic() - (osszeomlas.MEGAKADAS_MASODPERC + 5)
    assert osszeomlas.megakadt() is True


def test_nyom_a_naploba_kerul(tiszta):
    assert osszeomlas.megakadas_nyom() is True
    osszeomlas._fajl.flush()
    szoveg = tiszta.read_text(encoding="utf-8", errors="replace")
    assert osszeomlas.MEGAKADAS_FEJLEC in szoveg
    assert osszeomlas.MEGAKADAS_VEGE in szoveg
    # a lényeg: legyen benne VEREM, különben a nyom nem ér semmit
    assert "File \"" in szoveg


def test_egy_megakadasrol_csak_egyszer_irunk(tiszta):
    assert osszeomlas.megakadas_nyom() is True
    assert osszeomlas.megakadas_nyom() is False      # ugyanaz a befagyás
    osszeomlas.sziv_dobban()                          # feloldódott
    assert osszeomlas.megakadas_nyom() is True        # új befagyás


def test_tobb_nyom_nem_ir_tele_a_naplot(tiszta):
    for _ in range(osszeomlas._MEGAKADAS_MAX + 3):
        osszeomlas.megakadas_nyom()
        osszeomlas.sziv_dobban()
    osszeomlas._fajl.flush()
    szoveg = tiszta.read_text(encoding="utf-8", errors="replace")
    assert szoveg.count(osszeomlas.MEGAKADAS_FEJLEC) == \
        osszeomlas._MEGAKADAS_MAX


# --- A KETTŐ NEM UGYANAZ ----------------------------------------------

_FAGYAS = (
    "\n=== %s: a fő szál több mint 20 másodperce nem válaszol (ma) ===\n"
    "Current thread 0x1234 (most recent call first):\n"
    "  File \"valami.py\", line 1 in x\n"
    "=== %s ===\n" % (osszeomlas.MEGAKADAS_FEJLEC, osszeomlas.MEGAKADAS_VEGE)
)
_OMLAS = ("Windows fatal exception: access violation\n"
          "Current thread 0x9999 (most recent call first):\n")


def test_a_befagyas_nem_osszeomlas(monkeypatch):
    """Ha a program befagyott, de TÚLÉLTE, nem mondhatjuk neki induláskor,
    hogy „váratlanul bezárult". Ez volt a lényeg László jelzésében: a
    pontatlan mondat után a következőt sem hiszi el."""
    monkeypatch.setattr(osszeomlas, "_uj_resz", _FAGYAS)
    assert osszeomlas.uj_megakadas() is True
    assert osszeomlas.uj_osszeomlas() is False


def test_az_osszeomlas_tovabbra_is_osszeomlas(monkeypatch):
    monkeypatch.setattr(osszeomlas, "_uj_resz", _OMLAS)
    assert osszeomlas.uj_osszeomlas() is True
    assert osszeomlas.uj_megakadas() is False


def test_ha_mindketto_tortent_az_osszeomlas_szamit(monkeypatch):
    monkeypatch.setattr(osszeomlas, "_uj_resz", _FAGYAS + _OMLAS)
    assert osszeomlas.uj_megakadas() is True
    assert osszeomlas.uj_osszeomlas() is True


def test_a_jelentes_megtalalja_a_fagyas_blokkjat(tmp_path, monkeypatch):
    """A hibajelentés `utolso_osszeomlas()`-t csatol. Ha a befagyás fejléce
    nem szerepelne a keresett fejlécek között, a nyom kimaradna a
    jelentésből — vagyis pont az veszne el, amiért az egészet csináltuk."""
    naplo = tmp_path / "o.log"
    naplo.write_text("=== SuperDL indult: ma (verzió: 4.6.12) ===\n" + _FAGYAS,
                     encoding="utf-8")
    monkeypatch.setattr(osszeomlas, "NAPLO", naplo)
    nyom = osszeomlas.utolso_osszeomlas()
    assert osszeomlas.MEGAKADAS_FEJLEC in nyom
    assert "SuperDL indult" in nyom          # melyik verzió akadt meg
