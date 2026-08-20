# -*- coding: utf-8 -*-
"""Wi-Fi jelerősség dBm-ben + a mesh-bejárás naplója.

Felhasználói kérés (2026-08-20): „olyan eszközt keresnék, ami kiírná, hogy
milyen jelerősségű az épp használt wifi-kapcsolat, a dBm értéket megadva…
mesh hálót építek éppen ki, jó lenne látnom laptopon is, hogy hol milyen erős
még a kapcsolat.”
"""

import pytest

from superdl import nettest as NT


# ---------------------------------------------------- dBm

@pytest.mark.parametrize("szazalek,vart", [
    (100, -50), (0, -100), (50, -75), (88, -56)])
def test_becsles_a_jelminosegbol(szazalek, vart):
    """A Microsoft leírása szerint 0% = −100 dBm, 100% = −50 dBm, lineárisan.
    Ez csak TARTALÉK: ha a rendszer megadja a valódi RSSI-t, azt használjuk."""
    assert NT.dbm_becsles(szazalek) == vart


def test_hibas_bemenet_nem_szall_el():
    assert NT.dbm_becsles(None) == 0
    assert NT.dbm_becsles("sok") == 0
    assert NT.dbm_becsles(500) == -50          # a tartományba szorítva


@pytest.mark.parametrize("dbm,fokozat", [
    (-40, "kiváló"), (-55, "kiváló"), (-60, "jó"), (-70, "elfogadható"),
    (-78, "gyenge"), (-90, "használhatatlan")])
def test_minosites_fokozatai(dbm, fokozat):
    assert NT.jel_minosites(dbm)[0] == fokozat


def test_a_minosites_magyaraz_is():
    fokozat, magyarazat = NT.jel_minosites(-78)
    assert fokozat == "gyenge"
    assert "mesh" in magyarazat.lower(), \
        "a gyenge jelnél mondjuk meg, mit lehet tenni"


def test_felolvashato_mondat():
    sz = NT.jel_szoveg(-49, 89, True)
    assert "-49 dBm" in sz and "kiváló" in sz and "89 százalék" in sz
    becsult = NT.jel_szoveg(-56, 88, False)
    assert "számolva" in becsult, "a becslést KIMONDJUK, hogy ne higgyék mérésnek"
    assert "nem sikerült" in NT.jel_szoveg(0)


# ---------------------------------------------------- hang

def test_erosebb_jel_magasabb_hang():
    assert NT.jel_frekvencia(-40) > NT.jel_frekvencia(-60) > NT.jel_frekvencia(-80)


def test_a_hang_a_hallhato_savban_marad():
    for dbm in (-10, -35, -60, -85, -120):
        f = NT.jel_frekvencia(dbm)
        assert NT.JEL_HANG_ALSO_HZ <= f <= NT.JEL_HANG_FELSO_HZ


def test_hibas_ertek_eseten_is_ad_hangot():
    assert NT.jel_frekvencia(None) == NT.JEL_HANG_ALSO_HZ


# ---------------------------------------------------- bejárás-napló

def test_csak_erdemi_valtozast_mondunk_ki():
    """A jel másodpercenként ingadozik 1-2 dBm-et; ha mindet bemondanánk, a
    program folyamatosan beszélne."""
    n = NT.JelNaplo(valtozas_kuszob=3)
    assert n.hozzaad(-50) is True          # az első mindig
    assert n.hozzaad(-51) is False
    assert n.hozzaad(-52) is False
    assert n.hozzaad(-53) is True          # 3 dBm eltérés az utoljára mondottól
    assert len(n.meresek) == 4, "MINDEN mérés bekerül a naplóba, csak nem mondjuk"


def test_statisztika():
    n = NT.JelNaplo()
    for d in (-50, -60, -70):
        n.hozzaad(d)
    assert n.legjobb() == -50
    assert n.leggyengebb() == -70
    assert n.atlag() == -60


def test_ures_naplo_nem_szall_el():
    n = NT.JelNaplo()
    assert n.legjobb() == 0 and n.leggyengebb() == 0 and n.atlag() == 0
    assert "Nem történt mérés" in n.osszefoglalo()
    assert n.pont("konyha") == ("", 0, 0)


def test_pont_megjelolese_a_mostani_erteket_rogziti():
    n = NT.JelNaplo()
    n.hozzaad(-49, 90)
    n.pont("nappali")
    n.hozzaad(-78, 40)
    n.pont("konyha")
    assert n.pontok[0] == ("nappali", -49, 90)
    assert n.pontok[1] == ("konyha", -78, 40)
    assert "nappali: -49 dBm – kiváló" == n.pont_szoveg(n.pontok[0])


def test_nevtelen_pont_is_mukodik():
    n = NT.JelNaplo()
    n.hozzaad(-60)
    assert n.pont("   ")[0] == "névtelen pont"


def test_az_osszefoglalo_megmondja_hova_kell_meg_egyseg():
    n = NT.JelNaplo()
    n.hozzaad(-49); n.pont("nappali")
    n.hozzaad(-80); n.pont("padlás")
    sz = n.osszefoglalo()
    assert "padlás" in sz and "mesh-egységet" in sz
    assert "nappali" not in sz.split("mesh-egységet")[1]


def test_ha_mindenhol_jo_a_jel_azt_is_kimondja():
    n = NT.JelNaplo()
    n.hozzaad(-50); n.pont("nappali")
    n.hozzaad(-60); n.pont("konyha")
    assert "legalább" in n.osszefoglalo()


def test_menthető_jegyzőkönyv():
    n = NT.JelNaplo()
    n.hozzaad(-49, 90); n.pont("nappali")
    sz = n.mentheto_szoveg("Otthon-5G")
    assert "Otthon-5G" in sz and "nappali" in sz and "-49" in sz


# ---------------------------------------------------- jelentés

def test_a_jelentes_kiirja_a_dbm_erteket():
    """Laci kérése: „a dBm értéket megadva”. A százalék marad mellette, mert a
    hétköznapi felhasználónak az mond többet."""
    h = NT.Halozat(kapcsolat="vezeték nélküli (Wi-Fi)",
                         wifi_halozat="Otthon-5G", wifi_jel=72,
                         wifi_dbm=-49, wifi_dbm_mert=True, wifi_sav="5 GHz",
                         wifi_csatorna=48)
    sz = NT.jelentes(NT.Eredmeny(halozat=h))
    assert "-49 dBm" in sz
    assert "kiváló" in sz
    assert "jelminőség: 72 százalék" in sz


def test_a_szamolt_erteket_megjeloli_a_jelentes():
    h = NT.Halozat(kapcsolat="vezeték nélküli (Wi-Fi)",
                         wifi_halozat="Otthon", wifi_jel=50,
                         wifi_dbm=-75, wifi_dbm_mert=False)
    sz = NT.jelentes(NT.Eredmeny(halozat=h))
    assert "(számolva)" in sz, "ne higgye senki mérésnek a becslést"


def test_dbm_nelkul_a_regi_szazalekos_sor_marad():
    h = NT.Halozat(kapcsolat="vezeték nélküli (Wi-Fi)",
                         wifi_halozat="Otthon", wifi_jel=45, wifi_dbm=0)
    sz = NT.jelentes(NT.Eredmeny(halozat=h))
    assert "45 százalék" in sz and "gyenge" in sz
