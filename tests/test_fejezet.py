# -*- coding: utf-8 -*-
"""Fejezetjelölő: közös nyelv a szerkesztő és a hangoskönyv-készítő között.

A jelölő SIMA SZÖVEG, mert túl kell élnie a .txt-t is: a legtöbb
hangoskönyv-alapanyag szövegfájl, ahol nincs címsor-formázás.
"""
from superdl import fejezet as F


def test_a_jelolo_cim_nelkul():
    assert F.jelolo() == "[[FEJEZET]]"
    assert F.jelolo_e("[[FEJEZET]]")
    assert F.jelolo_cime("[[FEJEZET]]") == ""


def test_a_jelolo_cimmel():
    sor = F.jelolo("Első fejezet")
    assert F.jelolo_e(sor)
    assert F.jelolo_cime(sor) == "Első fejezet"


def test_elnezo_a_felismeres():
    for sor in ("[[fejezet]]", "  [[ FEJEZET ]]  ", "[[Fejezet: Cím]]"):
        assert F.jelolo_e(sor), sor


def test_a_regi_egyenlosegjeles_alak_is_megy():
    assert F.jelolo_e("=== FEJEZET ===")
    assert F.jelolo_cime("=== Második ===") == "Második"


def test_sima_szoveg_nem_jelolo():
    for sor in ("Ez egy fejezet a könyvben.", "", "[[valami más]]",
                "a [[FEJEZET]] szó a mondat közepén"):
        assert not F.jelolo_e(sor), sor


def test_fejezetekre_bontas():
    szoveg = ("Fülszöveg.\n"
              "[[FEJEZET: Egy]]\n"
              "Első sor.\nMásodik sor.\n"
              "[[FEJEZET: Kettő]]\n"
              "Harmadik sor.")
    fej = F.fejezetek(szoveg)
    assert [c for c, _t in fej] == ["", "Egy", "Kettő"]
    assert fej[1][1] == "Első sor.\nMásodik sor."
    assert fej[2][1] == "Harmadik sor."


def test_a_jelolo_sor_nem_kerul_a_tartalomba():
    """Ez technikai jel, nem felolvasandó szöveg."""
    for _cim, tartalom in F.fejezetek("[[FEJEZET: A]]\nszöveg"):
        assert "[[FEJEZET" not in tartalom


def test_cim_nelkuli_fejezet_sorszamot_kap():
    assert F.cimek("[[FEJEZET]]\nA\n[[FEJEZET]]\nB") == ["1. fejezet",
                                                         "2. fejezet"]


def test_jelolo_nelkul_nincs_darabolas():
    assert not F.van_jelolo("csak sima szöveg\nkét sorban")
    assert F.szamlal("csak sima szöveg") == 0
