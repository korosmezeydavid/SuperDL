# -*- coding: utf-8 -*-
"""Fejezetenkénti darabolás a hangoskönyv-készítőben.

Dávid kérése: *„van aki úgy akarja ledarabolni, hogy nem x percenként hanem
fejezetenként."* A jelölőt a Super Edit teszi bele (Ctrl+Shift+J), a
hangoskönyv-készítő pedig felismeri — a közös nyelv a `superdl/fejezet.py`.
"""
import inspect

from superdl import audiobook, fejezet


class _Konyv:
    def __init__(self, szoveg, cim="Proba"):
        self.title = cim
        self.sections = [szoveg]

    @property
    def text(self):
        return "\n\n".join(self.sections)


SZOVEG = ("Fülszöveg.\n"
          "[[FEJEZET: Egy]]\n"
          "Az első fejezet szövege.\n"
          "[[FEJEZET: Kettő]]\n"
          "A második fejezet szövege.")


def test_megszamolja_a_fejezeteket():
    assert audiobook.fejezet_szamlal(_Konyv(SZOVEG)) == 2
    assert audiobook.fejezet_szamlal(_Konyv("csak sima szöveg")) == 0


def test_a_tisztitas_NEM_olvasztja_be_a_jelolot():
    """⚠️ EZ A NÉMA HIBA. A felolvasásra tisztító a bekezdésen belüli
    sortöréseket szóközzé olvasztja. Ha a jelölőt is beolvasztaná a szomszédos
    mondatba, a fejezetenkénti darabolás CSENDBEN elromlana: a hangoskönyv
    egyben maradna, és a felhasználó csak a több óra alatt elkészült fájlon
    venné észre."""
    tiszta = audiobook.clean_for_speech(SZOVEG)
    assert fejezet.szamlal(tiszta) == 2, \
        "a tisztítás után is meg kell lennie mindkét jelölőnek"
    for sor in tiszta.split("\n"):
        if fejezet.jelolo_e(sor):
            assert sor.strip().startswith("[["), \
                "a jelölő SAJÁT sorban maradjon, ne olvadjon mondatba"


def test_a_jelolo_nem_kerul_a_felolvasando_szovegbe():
    for _cim, tartalom in fejezet.fejezetek(
            audiobook.clean_for_speech(SZOVEG)):
        assert "FEJEZET]]" not in tartalom


def test_a_build_ismeri_a_fejezetenkenti_kapcsolot():
    jel = inspect.signature(audiobook.build).parameters
    assert "fejezetenkent" in jel
    assert jel["fejezetenkent"].default is False, \
        "alapból maradjon a régi viselkedés"


def test_a_fajlnev_a_fejezet_cimet_viszi():
    assert audiobook._fejezet_cim_fajlnev("Első fejezet", 1) == "01 Első fejezet"
    assert audiobook._fejezet_cim_fajlnev("", 7) == "07"


def test_a_fajlnevbol_kimaradnak_a_tiltott_jelek():
    nev = audiobook._fejezet_cim_fajlnev('A: "hely" / rész?', 3)
    for tiltott in '\\/:*?"<>|':
        assert tiltott not in nev


def test_jelolo_nelkul_nem_esik_vissza_nemAn_percekre():
    """Ha nincs jelölő, a fejezetenkénti mód egyben hagyja – de ezt a
    felület úgy kezeli, hogy fel sem ajánlja. A `build` docstringje ezt
    kimondja, hogy a következő olvasó ne találgasson."""
    assert "NEM esünk vissza némán" in (audiobook.build.__doc__ or "")
