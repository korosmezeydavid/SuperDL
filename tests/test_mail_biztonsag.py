# -*- coding: utf-8 -*-
"""Super Mail – BIZTONSÁG: adathalászat, veszélyes csatolmány, leiratkozás.

Vakon a feladó neve és a valódi címe külön mondatban hangzik el, a link célja
pedig sehogy – ezért ezeket a program KIMONDJA. A vak felhasználók célzottan
gyakori áldozatai az adathalászatnak.
"""

import email
import sys

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import biztonsag as B              # noqa: E402
from mail_mod import mail_core as MC             # noqa: E402


# ---------------------------------------------------- feladó

def test_ismert_ceg_neve_idegen_cimrol_gyanus():
    gy = B.felado_gyanus({"felado": "Magyar Posta <info@posta-hu.xyz>"})
    assert gy and "nem a hivatalos" in gy[0]


def test_az_igazi_cim_nem_gyanus():
    assert B.felado_gyanus({"felado": "Magyar Posta <info@posta.hu>"}) == []
    # aldomain is rendben: levelezes.posta.hu
    assert B.felado_gyanus(
        {"felado": "Magyar Posta <no-reply@levelezes.posta.hu>"}) == []


def test_a_nev_mas_cimet_mutat_mint_a_valodi():
    gy = B.felado_gyanus({"felado": "ugyfelszolgalat@otpbank.hu <a@rossz.ru>"})
    assert gy and "másik e-mail címet" in gy[0]


def test_hasonlo_domain_szamokkal():
    gy = B.felado_gyanus({"felado": "Értesítés <info@0tpbank.hu>"})
    assert any("hasonlít" in x for x in gy)


def test_punycode_cim_gyanus():
    gy = B.felado_gyanus({"felado": "Bank <info@xn--tpbank-3va.hu>"})
    assert any("nem latin" in x for x in gy)


def test_elteru_valaszcim_kimondasa():
    gy = B.felado_gyanus({"felado": "Ügyfélszolgálat <info@bolt.hu>",
                          "valaszcim": "valaki@masikhely.ru"})
    assert any("a válasz nem a feladónak megy" in x for x in gy)


def test_azonos_valaszcim_nem_gyanus():
    assert B.felado_gyanus({"felado": "Bolt <info@bolt.hu>",
                            "valaszcim": "ugyfel@bolt.hu"}) == []


def test_nav_a_gov_hu_alatt_rendben():
    """A kétszintű végződés (gov.hu) miatt a nav.gov.hu-t nem szabad
    „gov.hu”-ra rövidíteni – különben minden gov.hu cím NAV-nak látszana."""
    assert B.felado_gyanus({"felado": "NAV <info@nav.gov.hu>"}) == []
    gy = B.felado_gyanus({"felado": "NAV <info@nav-ado.hu>"})
    assert gy and "nem a hivatalos" in gy[0]


# ---------------------------------------------------- tartalom

def test_jelszokeres_es_surgetes_egyutt_gyanus():
    gy = B.tartalom_gyanus(
        "Fiókja zárolva",
        "Kérjük, 24 órán belül adja meg a jelszót, különben felfüggesztjük.")
    assert gy and "SOHA nem kér jelszót" in gy[0]


def test_onmagaban_a_jelszo_szo_nem_riaszt():
    """A jelszó szó önmagában ártatlan – például egy baráti levélben."""
    assert B.tartalom_gyanus("Szia", "Elfelejtettem a jelszót a wifihez.") == []


# ---------------------------------------------------- linkek

def test_megtevesztő_link_szovege():
    html = '<a href="http://rossz.ru/belep">https://otpbank.hu/belepes</a>'
    gy = B.link_gyanus(html)
    assert gy and "rossz.ru" in gy[0]


def test_a_valodi_link_nem_gyanus():
    html = '<a href="https://posta.hu/csomag">https://posta.hu/csomag</a>'
    assert B.link_gyanus(html) == []


def test_link_celja_felolvashato():
    assert "posta.hu" in B.link_celja("https://posta.hu/nyomkovetes?id=12")


# ---------------------------------------------------- csatolmányok

@pytest.mark.parametrize("nev", ["szamla.exe", "kep.jpg.scr", "makro.docm",
                                 "futtat.js", "telepito.msi"])
def test_veszelyes_csatolmany_felismerese(nev):
    assert B.veszelyes_csatolmanyok([nev]) == [nev]


@pytest.mark.parametrize("nev", ["szamla.pdf", "kep.jpg", "tabla.xlsx",
                                 "level.txt", "zene.mp3"])
def test_artalmatlan_csatolmany(nev):
    assert B.veszelyes_csatolmanyok([nev]) == []


def test_figyelmeztetes_szovege_kimondja_a_lenyeget():
    sz = B.csatolmany_figyelmeztetes(["szamla.pdf", "virus.exe"])
    assert "virus.exe" in sz and "programot indít" in sz
    assert B.csatolmany_figyelmeztetes(["szamla.pdf"]) == ""


# ---------------------------------------------------- leiratkozás

def test_leiratkozas_a_fejlecbol():
    nyers = ("From: Hírlevél <info@bolt.hu>\r\nSubject: Akció\r\n"
             "List-Unsubscribe: <https://bolt.hu/le>, <mailto:le@bolt.hu>\r\n"
             "List-Unsubscribe-Post: List-Unsubscribe=One-Click\r\n\r\nx\r\n")
    info = MC.level_fejlec_info(email.message_from_string(nyers))
    m = B.leiratkozas_lehetosegek(info)
    assert m["http"] == "https://bolt.hu/le"
    assert m["mailto"] == "le@bolt.hu"
    assert m["egykattintas"] is True
    assert B.van_leiratkozas(info) is True
    assert "egyetlen lépéssel" in B.leiratkozas_szoveg(info)


def test_leiratkozas_nelkuli_level():
    info = MC.level_fejlec_info(
        email.message_from_string("From: a@b.hu\r\nSubject: x\r\n\r\ny\r\n"))
    assert B.van_leiratkozas(info) is False
    assert "nem adott meg" in B.leiratkozas_szoveg(info)


def test_csak_mailtos_leiratkozas():
    nyers = ("From: L <l@x.hu>\r\nSubject: x\r\n"
             "List-Unsubscribe: <mailto:le@x.hu?subject=unsub>\r\n\r\ny\r\n")
    info = MC.level_fejlec_info(email.message_from_string(nyers))
    m = B.leiratkozas_lehetosegek(info)
    assert m["mailto"].startswith("le@x.hu")
    assert m["egykattintas"] is False
