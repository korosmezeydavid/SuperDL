# -*- coding: utf-8 -*-
"""Super Mail – beszélgetés-szálak és idézet-átugrás."""

import sys

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import beszelgetes as BE            # noqa: E402


def _l(targy, azon="", valasz="", hiv="", felado="Mari <mari@x.hu>"):
    return {"targy": targy, "azonosito": azon, "valasz_erre": valasz,
            "hivatkozasok": hiv, "felado": felado}


# ---------------------------------------------------- tárgy

@pytest.mark.parametrize("targy,vart", [
    ("Re: Szerződés", "Szerződés"),
    ("RE: Fwd: Szerződés", "Szerződés"),
    ("Vá: Szerződés", "Szerződés"),
    ("Re[2]: Szerződés", "Szerződés"),
    ("Szerződés", "Szerződés"),
])
def test_targy_elotagok_levagasa(targy, vart):
    assert BE.targy_torzse(targy) == vart


# ---------------------------------------------------- szálak

def test_hivatkozas_alapjan_egy_szal():
    """A szálat elsősorban a szabvány szerinti hivatkozásokból építjük."""
    levelek = [_l("Re: Kérdés", "<c@x>", "<b@x>", "<a@x> <b@x>"),
               _l("Re: Kérdés", "<b@x>", "<a@x>", "<a@x>"),
               _l("Kérdés", "<a@x>")]
    szalak = BE.szalak(levelek)
    assert len(szalak) == 1
    assert len(szalak[0]) == 3
    assert szalak[0][0]["azonosito"] == "<a@x>", "időrendben, a legrégebbi elöl"


def test_kulon_beszelgetesek_kulon_szalban():
    levelek = [_l("Kérdés", "<a@x>"), _l("Számla", "<b@x>")]
    assert len(BE.szalak(levelek)) == 2


def test_azonos_targy_hivatkozas_nelkul_is_osszefog():
    """Sok szerver/kliens nem küld References-t – ilyenkor a tárgy segít."""
    levelek = [_l("Re: Ebéd", "<b@x>"), _l("Ebéd", "<a@x>")]
    assert len(BE.szalak(levelek)) == 1


def test_szal_szovege_felolvashato():
    szal = [_l("Ebéd", "<a@x>", felado="Mari <m@x.hu>"),
            _l("Re: Ebéd", "<b@x>", "<a@x>", felado="Béla <b@x.hu>")]
    sz = BE.szal_szoveg(szal)
    assert "Ebéd" in sz and "2 levél" in sz and "Mari" in sz and "Béla" in sz
    assert BE.szal_szoveg([_l("Egy", "<a@x>")]).endswith("1 levél")


# ---------------------------------------------------- idézet

def test_idezett_elozmeny_levagasa():
    torzs = ("Szia Mari!\n\nRendben, megyek.\n\n"
             "2026. 08. 19. 10:00 keltezéssel Mari írta:\n"
             "> Szia, jössz holnap?\n> Üdv, Mari\n")
    assert BE.uj_resz(torzs) == "Szia Mari!\n\nRendben, megyek."


def test_angol_bevezeto_es_eredeti_uzenet_jelolo():
    a = "Ok, thanks.\n\nOn Wed, Aug 19, 2026 at 10:00 AM Mari wrote:\n> hello"
    assert BE.uj_resz(a) == "Ok, thanks."
    b = "Rendben.\n\n----- Eredeti üzenet -----\nFrom: Mari\n> szia"
    assert BE.uj_resz(b) == "Rendben."


def test_alairas_levagasa():
    torzs = "Köszönöm!\n\n--\nKőrösmezey Dávid\nSuperDL"
    assert BE.uj_resz(torzs) == "Köszönöm!"


def test_idezet_nelkuli_level_valtozatlan():
    torzs = "Szia!\n\nMinden rendben, köszönöm.\n\nÜdv: Mari"
    assert BE.uj_resz(torzs) == torzs.strip()
    assert BE.idezet_aranya(torzs) < 0.1
    assert BE.bevezeto(torzs) == "", "ne fecsegjen, ha nincs mit átugrani"


def test_sok_idezetnel_szol_a_program():
    torzs = ("Rendben.\n\nMari írta:\n" + "> régi szöveg\n" * 40)
    assert BE.idezet_aranya(torzs) > 0.8
    sz = BE.bevezeto(torzs)
    assert "új része" in sz and "1 sor" in sz


def test_csak_idezetbol_allo_level():
    torzs = "Mari írta:\n" + "> minden\n" * 10
    assert BE.uj_resz(torzs) == ""
    assert "alig van" in BE.bevezeto(torzs)


def test_ures_torzs_nem_szall_el():
    assert BE.uj_resz("") == ""
    assert BE.idezet_aranya("") == 0.0
    assert BE.bevezeto("") == ""
