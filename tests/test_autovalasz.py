# -*- coding: utf-8 -*-
"""Az AUTOMATA VÁLASZ reteszei és szövegkezelése.

Ezek a tesztek nem szépészetiek: az itt ellenőrzött reteszek nélkül a program
levelezőlistára válaszolna a felhasználó nevében, vagy két gép a végtelenségig
válaszolgatna egymásnak.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "modules_src" / "mail"))

from mail_mod import autovalasz as AV          # noqa: E402
from mail_mod import szabalyok as SZ           # noqa: E402


def _level(**kw):
    alap = {"felado": "Kovács János <janos@pelda.hu>", "targy": "Kérdés",
            "azonosito": "<abc@pelda.hu>"}
    alap.update(kw)
    return alap


# ---------------------------------------------------------------- címek

def test_cim_es_nev_szetvalasztasa():
    assert AV.cim_resz("Kovács János <janos@pelda.hu>") == "janos@pelda.hu"
    assert AV.nev_resz("Kovács János <janos@pelda.hu>") == "Kovács János"
    # név nélküli feladónál a cím a név
    assert AV.nev_resz("janos@pelda.hu") == "janos@pelda.hu"


# ---------------------------------------------------------------- tiltás

def test_levelezolistara_soha():
    assert AV.tiltott(_level(lista_id="<lista.pelda.hu>"))


def test_hirlevelre_soha():
    assert AV.tiltott(_level(marketing=True))
    assert AV.tiltott(_level(leiratkozas="<mailto:le@pelda.hu>"))


def test_noreply_cimekre_soha():
    for cim in ("noreply@pelda.hu", "no-reply@pelda.hu", "donotreply@pelda.hu",
                "mailer-daemon@pelda.hu", "postmaster@pelda.hu"):
        assert AV.tiltott(_level(felado=cim)), cim


def test_automata_levelre_soha():
    assert AV.tiltott(_level(auto_submitted="auto-replied"))
    assert AV.tiltott(_level(auto_submitted="auto-generated"))
    # az „Auto-Submitted: no” a SZABVÁNY szerint azt jelenti: ez kézzel írt
    assert not AV.tiltott(_level(auto_submitted="no"))


def test_kezbesitesi_hibauzenetre_soha():
    assert AV.tiltott(_level(vissza_ut="<>"))


def test_tomeges_kuldemenyre_soha():
    assert AV.tiltott(_level(precedence="bulk"))


def test_sajat_magadnak_soha():
    """A saját címünkre küldött válasz azonnali végtelen kör lenne."""
    assert AV.tiltott(_level(felado="en@pelda.hu"), sajat_cim="EN@pelda.hu")


def test_rendes_levelre_mehet():
    assert AV.tiltott(_level()) == ""


# ---------------------------------------------------------------- retesz

def test_cimenkent_naponta_egyszer(tmp_path):
    m = str(tmp_path)
    most = time.time()
    assert AV.mehet("janos@pelda.hu", m, most)
    AV.rogzit("janos@pelda.hu", "Re: Kérdés", "próba", m, most)
    # ugyanaznap már nem
    assert not AV.mehet("janos@pelda.hu", m, most + 3600)
    # másnap igen
    assert AV.mehet("janos@pelda.hu", m, most + 25 * 3600)
    # MÁS címre viszont azonnal mehet
    assert AV.mehet("eva@pelda.hu", m, most + 60)


def test_a_naplo_nem_hizik_a_vegtelensegig(tmp_path):
    m = str(tmp_path)
    most = time.time()
    AV.rogzit("regi@pelda.hu", "x", "", m, most - 60 * 24 * 3600)
    AV.rogzit("uj@pelda.hu", "x", "", m, most)
    cimek = {t["cim"] for t in AV.naplo_betolt(m)}
    assert "uj@pelda.hu" in cimek
    assert "regi@pelda.hu" not in cimek     # a 30 napnál régebbit eldobjuk


# ---------------------------------------------------------------- szöveg

def test_helykitoltok_kitoltese():
    ki = AV.behelyettesit("Kedves [feladó]! A(z) „[tárgy]” levelet megkaptam.",
                          _level())
    assert "Kedves Kovács János!" in ki
    assert "„Kérdés”" in ki


def test_elgepelt_helykitolto_megmarad():
    """Amit elgépelsz, az NEM tűnik el némán – az sokkal rosszabb volna."""
    ki = AV.behelyettesit("Kedves [felado]!", _level())
    assert ki == "Kedves [felado]!"


def test_targy_nem_duplazza_a_re_t():
    assert AV.valasz_targy("Kérdés") == "Re: Kérdés"
    assert AV.valasz_targy("Re: Kérdés") == "Re: Kérdés"
    assert AV.valasz_targy("Kérdés", "Saját tárgy") == "Saját tárgy"


# ---------------------------------------------------------------- előkészítés

def test_elokeszit_teljes_menet(tmp_path):
    m = str(tmp_path)
    e = AV.elokeszit(_level(), "Szia [feladó], megkaptam.", mappa=m)
    assert e["mehet"]
    assert e["cimzett"] == "janos@pelda.hu"
    assert e["targy"] == "Re: Kérdés"
    assert e["torzs"] == "Szia Kovács János, megkaptam."
    assert e["valasz_id"] == "<abc@pelda.hu>"


def test_elokeszit_ures_szovegre_nem_kuld(tmp_path):
    e = AV.elokeszit(_level(), "   ", mappa=str(tmp_path))
    assert not e["mehet"] and "nincs megírva" in e["ok"]


def test_elokeszit_tiltott_levelre_nem_kuld(tmp_path):
    e = AV.elokeszit(_level(lista_id="<l.pelda.hu>"), "Szia", mappa=str(tmp_path))
    assert not e["mehet"] and "levelezőlistáról" in e["ok"]


# ---------------------------------------------------------------- szabály

def test_a_szabaly_mondata_nem_olvassa_fel_az_egesz_levelet():
    sz = SZ.Szabaly(
        nev="Ügyfélnek", feltetelek=[SZ.Feltetel(SZ.MEZO_FELADO,
                                                 SZ.VISZ_TARTALMAZZA,
                                                 "janos@pelda.hu")],
        muveletek={SZ.MUV_AUTOVALASZ: "első sor\nmásodik sor\nharmadik sor",
                   SZ.MUV_AUTOVALASZ_TARGY: "Megkaptam"})
    mondat = sz.leiras()
    assert "automata válasz (3 soros szöveg)" in mondat
    assert "első sor" not in mondat            # a teljes szöveg NEM hangzik el
    assert "az automata válasz tárgya" not in mondat   # nem külön művelet


def test_a_szabaly_tobb_muveletet_is_visz():
    """A kérés szerinti kombináció: Kukába ÉS automata válasz."""
    sz = SZ.Szabaly(
        feltetelek=[SZ.Feltetel(SZ.MEZO_FELADO, SZ.VISZ_TARTALMAZZA, "@x.hu")],
        muveletek={SZ.MUV_TOROL: True, SZ.MUV_AUTOVALASZ: "Nem érdekel."})
    terv = SZ.alkalmaz([_level(felado="a@x.hu")], [sz])
    assert len(terv) == 1
    _info, muveletek, _nevek = terv[0]
    assert muveletek[SZ.MUV_TOROL] is True
    assert muveletek[SZ.MUV_AUTOVALASZ] == "Nem érdekel."


def test_a_mentett_szabaly_visszaolvashato(tmp_path):
    """A régi és az új szabályok ugyanabban a fájlban élnek."""
    sz = SZ.Szabaly(
        nev="Teszt", feltetelek=[SZ.Feltetel(SZ.MEZO_TARGY,
                                            SZ.VISZ_TARTALMAZZA, "számla")],
        muveletek={SZ.MUV_AUTOVALASZ: "Megkaptam.",
                   SZ.MUV_ATHELYEZ: "Számlák"})
    SZ.ment(str(tmp_path), [sz])
    vissza = SZ.betolt(str(tmp_path))
    assert vissza[0].muveletek[SZ.MUV_AUTOVALASZ] == "Megkaptam."
    assert vissza[0].muveletek[SZ.MUV_ATHELYEZ] == "Számlák"
