# -*- coding: utf-8 -*-
"""Okos tisztítás és fordítás-darabolás a Super Editben."""
import pytest

BASE = "modules_src.superedit.superedit_mod"
TI = pytest.importorskip(BASE + ".tisztitas")
FO = pytest.importorskip(BASE + ".forditas")


# ---- okos tisztítás -----------------------------------------------------

def test_a_webcimet_kiszedi():
    uj, db = TI.tisztit("Olvasd itt: https://pelda.hu/fejezet/12 vége",
                        {"url"})
    assert "https://" not in uj and db == 1


def test_a_hivatkozas_latszo_szovege_megmarad():
    """A [szöveg](cím) alakban a SZÖVEG a tartalom – azt nem dobjuk el."""
    uj, _db = TI.tisztit("Lásd [a második fejezetet](https://pelda.hu/2).",
                         {"md"})
    assert "a második fejezetet" in uj and "pelda.hu" not in uj


def test_a_navigacios_sort_torli():
    szoveg = "Igazi mondat.\nKövetkező fejezet\nMásik igazi mondat."
    uj, db = TI.tisztit(szoveg, {"nav"})
    assert db == 1
    assert "Igazi mondat." in uj and "Másik igazi mondat." in uj
    assert "Következő fejezet" not in uj


def test_a_mondatban_szereplo_szo_nem_esik_aldozatul():
    """A „vissza" egy mondat közepén NEM navigáció."""
    szoveg = "Hosszan nézte, majd vissza a tetejére tette a könyvet, és " \
             "csendben elmosolyodott a dolgon."
    uj, db = TI.tisztit(szoveg, {"nav"})
    assert db == 0 and uj == szoveg


def test_a_html_cimket_torli():
    uj, db = TI.tisztit("<p>Szöveg</p>", {"html"})
    assert uj == "Szöveg" and db == 2


def test_a_tobb_ures_sort_osszevonja():
    uj, _db = TI.tisztit("A\n\n\n\n\nB", {"ures"})
    assert uj == "A\n\nB"


def test_szamlal_nem_modosit():
    szoveg = "https://pelda.hu"
    TI.szamlal(szoveg)
    assert szoveg == "https://pelda.hu"


def test_az_osszefoglalo_megmondja_ha_nincs_mit_tenni():
    assert "nem találtam" in TI.osszefoglalo(
        {k: 0 for k, _n, _f in TI.SZABALYOK}).lower()


# ---- fordítás: darabolás ------------------------------------------------

def test_a_darabok_a_meret_alatt_maradnak():
    szoveg = "\n".join("Ez egy bekezdés, elég hosszú ahhoz, hogy számítson."
                       for _ in range(400))
    for d in FO.darabol(szoveg, meret=1000):
        assert len(d) <= 1000 + 200      # bekezdéshatáron vágunk, nem pontosan


def test_a_darabolas_semmit_nem_dob_el():
    szoveg = "\n".join("sor %d" % i for i in range(500))
    assert "\n".join(FO.darabol(szoveg, meret=300)) == szoveg


def test_a_fejezetjelolo_onallo_darab_es_nem_forditando():
    szoveg = "Egy.\n[[FEJEZET: Kettő]]\nHárom."
    darabok = FO.darabol(szoveg)
    assert "[[FEJEZET: Kettő]]" in darabok
    assert not FO.forditando("[[FEJEZET: Kettő]]")
    assert FO.forditando("Egy.")


def test_az_ures_darabot_nem_kuldjuk_el():
    assert not FO.forditando("   \n  \n")


def test_a_hibas_darab_eredetiben_marad(monkeypatch):
    """⚠️ Egy hiányzó bekezdés vakon észrevehetetlen; egy le nem fordított
    viszont feltűnik és javítható."""
    def rossz(_d, _h, _hv):
        raise RuntimeError("nincs net")
    monkeypatch.setattr(FO, "ai_darab", rossz)
    ki = FO.fordit("Első bekezdés.\nMásodik bekezdés.", "hu", "en",
                   motor="ai")
    assert "Első bekezdés." in ki and "Második bekezdés." in ki


def test_a_megallitas_a_maradekot_eredetiben_hagyja(monkeypatch):
    monkeypatch.setattr(FO, "ai_darab", lambda d, h, hv: "TRANSLATED")
    ki = FO.fordit("A\nB\nC", "hu", "en", motor="ai", megall=lambda: True)
    assert ki == "A\nB\nC"
