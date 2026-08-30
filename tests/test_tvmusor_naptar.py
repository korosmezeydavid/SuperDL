# -*- coding: utf-8 -*-
"""TV műsor – a kedvenc-emlékeztető megtalálja-e a Core naptárkezelőjét.

LACI JELZÉSE (2026-08-30): „Megpróbáltam emlékeztetőt beállítani a Vuk című
rajzfilmhez, de azt írja a program, hogy »A naptár most nem érhető el… A
Szervezés modul naptára kell hozzá.« Nem értem, fel van telepítve a szervezés
modul."

GYÖKÉR: a modul a `core.main`-en át kereste a főablakot, a CoreContext viszont
`main_frame` (és `frame`) néven adja, `main` néven SOHA. Így a keresés MINDIG
üres kézzel tért vissza – a funkció a megjelenése óta halott volt, és a hibaüzenet
ráadásul rossz helyre (a Szervezés modulhoz) küldte a felhasználót. A naptár
KEZELŐJE a Core-ban van (`MainFrame._organizer`), a Szervezés csak az ABLAKOT adja.

Ezek a tesztek wx-ablak létrehozása NÉLKÜL futnak: a metódusokat a osztályról,
kacsa-tipusú „self"-fel hívjuk.
"""
import importlib

W = importlib.import_module("modules_src.tvmusor.tvmusor_mod.tvmusorwin")
Frame = W.TvMusorFrame


class Kezelo:
    """A Core OrganizerManagere annyiban, amennyi itt számít."""

    def __init__(self):
        self.events = []

    def add_event(self, ev):
        self.events.append(ev)


class FoAblak:
    def __init__(self, kezelo):
        self._organizer = kezelo


class CoreContextSzeru:
    """A VALÓDI szerződés: `main_frame` és `frame`, `main` NINCS."""

    def __init__(self, foablak):
        self._foablak = foablak

    @property
    def main_frame(self):
        return self._foablak

    @property
    def frame(self):
        return self.main_frame


class Onmaga:
    """Kacsa-típusú „self" a TvMusorFrame metódusaihoz."""

    def __init__(self, core, szulo=None):
        self.core = core
        self._szulo = szulo
        self._naptar_hiba = ""

    def GetParent(self):
        return self._szulo


def _keres(core, szulo=None):
    return Frame._naptar_kezelo(Onmaga(core, szulo))


# --- a regresszió maga -------------------------------------------------

def test_coretext_main_frame_neven_adja_a_foablakot():
    """EZ A LACI-HIBA: `main` nincs, `main_frame` van – mégis meg kell találni."""
    k = Kezelo()
    core = CoreContextSzeru(FoAblak(k))
    assert not hasattr(core, "main"), "a CoreContextnek tényleg nincs `main`-je"
    assert _keres(core) is k


def test_a_szulo_ablakon_at_is_megvan():
    """A `register_window` megnyitója a FŐABLAKOT adja szülőnek – ez a mentőöv,
    ha a core egyáltalán nem vezet el a főablakhoz."""
    k = Kezelo()

    class Semmi:
        pass

    assert _keres(Semmi(), szulo=FoAblak(k)) is k


def test_a_core_sajat_organizere_is_jo():
    """Ha egyszer bekerül a tervezett `core.organizer` szolgáltatás, működjön."""
    k = Kezelo()

    class CoreSzolgaltatassal:
        organizer = k

    assert _keres(CoreSzolgaltatassal()) is k


def test_property_hiba_nem_szakitja_meg_a_keresest():
    k = Kezelo()

    class Rossz:
        @property
        def main_frame(self):
            raise RuntimeError("elszállt")

    assert _keres(Rossz(), szulo=FoAblak(k)) is k


def test_ha_tenyleg_nincs_naptar_akkor_None():
    class Semmi:
        pass

    assert _keres(Semmi(), szulo=None) is None


# --- az üzenet ---------------------------------------------------------

def test_az_uzenet_nem_a_szervezes_modult_hibaztatja():
    o = Onmaga(core=None)
    o._naptar_hiba = "nincs-naptar"
    szoveg = Frame._naptar_hiba_szoveg(o)
    assert "Szervezés" not in szoveg, (
        "a naptár KEZELŐJE a Core-ban van – nem a Szervezés modul hiánya okozza")
    assert "nem a tiéd" in szoveg


def test_valodi_hiba_eseten_a_hibat_mondjuk_el():
    o = Onmaga(core=None)
    o._naptar_hiba = "lemez megtelt"
    szoveg = Frame._naptar_hiba_szoveg(o)
    assert "lemez megtelt" in szoveg
    assert "nem érhető el" not in szoveg, (
        "a valódi hiba NE hangozzék úgy, mintha hiányozna a naptár")
