"""HELYBEN FUTÓ FORDÍTÓ csonka futtatókörnyezete — Farkas István, 2026-09-19.

    „A helyben való fordítással szerettem volna lefordítani egy rövid
     levelet, de hibát jelzett:
         module 'ctranslate2' has no attribute 'Translator'
     Ami még probléma, hogy a ctrl+e billentyűre sem adott ki semmi
     információt."

AZ IGAZI HIBA. Nem az, hogy a futtatókörnyezet csonka — hanem hogy a
program ezt CSAK A HASZNÁLAT PILLANATÁBAN vette észre. Az `elerheto()`
ugyanis mindössze annyit nézett, hogy az `import ctranslate2` nem dob-e
kivételt. Egy olyan modul, ami importálódik, de nincs benne `Translator`,
átment a vizsgán: a felület felajánlotta a helyben fordítást, a felhasználó
kiválasztotta, és csak ott derült ki, hogy nem megy. A program megígért
valamit, amit nem tudott.

Ráadásul a nyers angol mondat vakon nem információ: a felhasználó azt is
hihette, hogy a LEVELÉVEL van baj.
"""

import sys
import types

import pytest

from superdl import hibaszoveg as H
from superdl import offlineford as OF


@pytest.fixture
def tiszta_sysmodules():
    """A ctranslate2-vel kapcsolatos bejegyzések mentése/visszaállítása –
    a teszt nem szennyezheti a többi tesztet."""
    mentve = {k: v for k, v in sys.modules.items()
              if k == "ctranslate2" or k.startswith("ctranslate2.")}
    for k in list(mentve):
        sys.modules.pop(k, None)
    yield
    for k in [k for k in sys.modules
              if k == "ctranslate2" or k.startswith("ctranslate2.")]:
        sys.modules.pop(k, None)
    sys.modules.update(mentve)


def _nincs_telepitve():
    """A „nincs telepítve" állapot szimulálása.

    ⚠️ 4.6.18: ezek a tesztek eddig arra ÉPÍTETTEK, hogy a gépen tényleg nincs
    ctranslate2 – vagyis épp arra a hibára, ami a fordítót a buildből kiejtette
    (Farkas István, 2026-09-24). Most, hogy a build-értelmezőben újra van,
    a hiányt KIFEJEZETTEN szimuláljuk: egy import-kereső, ami a ctranslate2-t
    „nem találja". (A `sys.modules[...] = None` nem elég: a `ct2()` pótmodulos
    ága kiveszi a bejegyzést és újra próbál.)"""
    sys.meta_path.insert(0, _Tilto())
    sys.modules.pop("ctranslate2", None)


class _Tilto:
    """A `ctranslate2` importját „nincs ilyen csomag"-ra futtatja."""

    def find_spec(self, nev, path=None, target=None):
        if nev == "ctranslate2" or nev.startswith("ctranslate2."):
            if nev == "ctranslate2.converters" and nev in sys.modules:
                return None
            raise ModuleNotFoundError("No module named %r" % nev)
        return None


@pytest.fixture(autouse=True)
def _tilto_takaritas():
    yield
    sys.meta_path[:] = [f for f in sys.meta_path if not isinstance(f, _Tilto)]


def _hamis_ct2(van_translator: bool):
    m = types.ModuleType("ctranslate2")
    if van_translator:
        m.Translator = object
    return m


# ──────────── a csonka modul NEM mehet át a vizsgán ─────────────────

def test_a_translator_nelkuli_modul_import_hibat_ad(tiszta_sysmodules):
    """⚠️ EZ A LÉNYEG. Pontosan Farkas esete: az import lefut, a Translator
    viszont nincs meg."""
    sys.modules["ctranslate2"] = _hamis_ct2(False)
    with pytest.raises(ImportError) as hiba:
        OF.ct2()
    assert "Translator" in str(hiba.value)


def test_a_csonka_futtatokornyezet_nem_elerheto(tiszta_sysmodules):
    """A régi `elerheto()` IGENT mondott rá – és a felület felajánlotta."""
    sys.modules["ctranslate2"] = _hamis_ct2(False)
    assert OF.elerheto() is False


def test_a_teljes_futtatokornyezet_elerheto(tiszta_sysmodules):
    sys.modules["ctranslate2"] = _hamis_ct2(True)
    assert OF.elerheto() is True
    assert OF.ct2().Translator is object


def test_a_hianyzo_csomag_sem_elerheto(tiszta_sysmodules):
    """Ha egyáltalán nincs telepítve, az is nem-et jelent (nem összeomlást)."""
    _nincs_telepitve()
    assert OF.elerheto() is False


# ─────────── ne hagyjunk szemetet egy későbbi jó import elé ─────────

def test_kudarc_utan_eltakaritjuk_a_potmodult(tiszta_sysmodules):
    """⚠️ A pótmodulos trükk nem mérgezheti meg a következő importot: ha nem
    sikerült, a beadott üres `ctranslate2.converters` menjen ki."""
    assert "ctranslate2.converters" not in sys.modules
    _nincs_telepitve()
    with pytest.raises(Exception):
        OF.ct2()
    assert "ctranslate2.converters" not in sys.modules, \
        "a kudarc után nem maradhat ott az üres pótmodul"


def test_a_mar_meglevo_converters_bejegyzest_nem_bantjuk(tiszta_sysmodules):
    """Ha nem MI adtuk be, nem is vesszük ki – nem a mi dolgunk."""
    sajat = types.ModuleType("ctranslate2.converters")
    sys.modules["ctranslate2.converters"] = sajat
    _nincs_telepitve()
    try:
        with pytest.raises(Exception):
            OF.ct2()
        assert sys.modules.get("ctranslate2.converters") is sajat
    finally:
        sys.modules.pop("ctranslate2.converters", None)


# ─────────────────── „miért nem" – emberi mondat ────────────────────

def test_hianyzo_reszek_megnevezi_a_futtatokornyezetet(tiszta_sysmodules):
    sys.modules["ctranslate2"] = _hamis_ct2(False)
    reszek = OF.hianyzo_reszek()
    assert any("ctranslate2" in r for r in reszek)


def test_miert_nem_ures_ha_minden_megvan(tiszta_sysmodules, monkeypatch):
    sys.modules["ctranslate2"] = _hamis_ct2(True)
    monkeypatch.setattr(OF, "_SEGEDEK", ())
    assert OF.miert_nem() == ""


def test_miert_nem_mondata_megnyugtat_es_utat_mutat(tiszta_sysmodules):
    sys.modules["ctranslate2"] = _hamis_ct2(False)
    m = OF.miert_nem()
    assert m
    assert "nem a te géped" in m, "ne a felhasználót hibáztassuk"
    assert "online" in m, "mondjuk meg, mit tud MOST csinálni"
    assert "ctranslate2" in m, "a technikai ok is legyen benne, továbbküldhetően"


def test_a_fordit_ertheto_mondattal_all_meg(tiszta_sysmodules):
    """⚠️ Ne a `_Motor.__init__`-ből jöjjön ki a nyers angol AttributeError."""
    sys.modules["ctranslate2"] = _hamis_ct2(False)
    with pytest.raises(RuntimeError) as hiba:
        OF.fordit("Ez egy rövid levél.", "en", "hu")
    assert "helyben futó fordító" in str(hiba.value)


def test_ures_szovegre_nem_panaszkodik(tiszta_sysmodules):
    """Üres szövegre ne a futtatókörnyezetről beszéljen."""
    sys.modules["ctranslate2"] = _hamis_ct2(False)
    assert OF.fordit("   ", "en", "hu") == ""


# ─────────── a NYERS angol szöveg is kapjon magyar mondatot ─────────

@pytest.mark.parametrize("nyers", [
    "module 'ctranslate2' has no attribute 'Translator'",
    "No module named 'ctranslate2'",
    "AttributeError: module 'x' has no attribute 'Translator'",
])
def test_a_nyers_angol_hibabol_ertheto_magyar_mondat_lesz(nyers):
    m = H.emberi(nyers)
    assert m != nyers, "nem maradhat nyers angol"
    assert "fordító" in m
    # ⚠️ magyar idézőjel-csapda: a záró jel UNICODE legyen (”), különben
    # lezárja a Python-füzért – ezen a fájl első változata elhasalt
    assert H.van_javaslat(nyers) is True, \
        "ez már FELISMERT hiba – ne a „nem ismerjük fel” mondat menjen"


@pytest.mark.parametrize("nyers", [
    "No module named 'sacremoses'",
    "No module named 'sentencepiece'",
    "No module named 'subword_nmt'",
])
def test_a_segedcsomagok_hianyat_is_megnevezzuk(nyers):
    m = H.emberi(nyers)
    assert "segédcsomag" in m
    assert "online" in m


def test_a_fordito_hiba_nem_keveredik_a_letoltesekkel():
    """A letöltési hibák magyarázata ne változzon ettől."""
    assert "fordító" not in H.emberi("HTTP Error 403: Forbidden")
