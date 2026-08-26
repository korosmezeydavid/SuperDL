# -*- coding: utf-8 -*-
"""Az önfrissítő telepítő-indító kötegfájlja.

Hibajelentés (a fejlesztő gépén, 2026-08-24): a program „valamiért nem akarta"
elvégezni a frissítést. A napló SIKERT írt (kód 0), a telepített verzió mégis
maradt a régi.

GYÖKÉROK (élesben reprodukálva): az Inno Setup indítója kicsomagol és
újraindítja magát egy segédfolyamatként, ezért a kötegfájl AZONNAL továbbment
– majd 8 másodperc múlva VISSZAINDÍTOTTA a SuperDL-t, miközben a telepítés még
tartott. A visszainduló program egypéldány-mutexe (AppMutex) pedig megállította
a telepítőt. Külön mérésben igazolva: élő mutex mellett a telepítő 1-es kóddal
kilép, és semmit nem csinál.

JAVÍTÁS: `start /wait`, majd VÁRAKOZÁS, amíg a telepítő folyamata eltűnik, és
csak azután újraindítás. Ráadásként a napló kiírja a TÉNYLEGESEN telepített
verziót, hogy egy sikertelen frissítés ne látszódjon sikeresnek.
"""

from pathlib import Path

from superdl import selfupdate as SU


def _szkript():
    return SU._installer_script(Path("C:/tmp/SuperDL-Setup-9.9.9.exe"), 4242,
                                Path("C:/naplo.log"),
                                Path("C:/App/SuperDL.exe"))


def test_a_telepitot_megvarjuk():
    sz = _szkript()
    assert 'start "" /wait "' in sz and "SuperDL-Setup-9.9.9.exe" in sz, \
        "enélkül a kötegfájl azonnal továbbmegy, és a telepítés félbemarad"


def test_a_visszainditas_csak_a_telepito_utan_jon():
    sz = _szkript()
    varakozas = sz.index(":varj_telepitore")
    ujrainditas = sz.index("SuperDL ujrainditasa")
    assert varakozas < ujrainditas, \
        "ha előbb indítanánk vissza a programot, a mutexe megölné a telepítőt"


def test_a_valodi_verziot_naploba_irjuk():
    sz = _szkript()
    assert "telepitett verzio" in sz
    assert "DisplayVersion" in sz, "a registryből olvassuk ki, mi lett belőle"


def test_a_kilepesi_kodot_elmentjuk_a_naplozas_elott():
    """A `%ERRORLEVEL%` egy későbbi parancs után már mást mutatna."""
    sz = _szkript()
    assert 'set "KOD=%ERRORLEVEL%"' in sz
    assert sz.index('set "KOD=') < sz.index("telepito vegzett")


def test_megvarjuk_a_futo_program_kilepeset():
    """A régi, jól működő rész NEM veszhet el: előbb a SuperDL lép ki."""
    sz = _szkript()
    assert "PID 4242 kilepesere" in sz
    assert sz.index("kilepesere") < sz.index("telepito inditasa")


def test_a_koteg_veget_takaritja_maga_utan():
    assert 'del "%~f0"' in _szkript()
