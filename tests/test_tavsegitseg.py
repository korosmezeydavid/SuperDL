# -*- coding: utf-8 -*-
"""Távsegítség – az esemény-modell és a VEZÉRLÉS biztonsági kapujának tesztjei.

Valódi input-injektálás NÉLKÜL (nem mozgatjuk a kurzort, és nem-Windowson is
lefut): a Vezerlo alapból INAKTÍV, és inaktívan MINDENT figyelmen kívül hagy –
ez a legfontosabb biztonsági garancia."""
import importlib

BASE = "modules_src.tavsegitseg.tavsegitseg_mod"
V = importlib.import_module(BASE + ".vezerles")
SZ = importlib.import_module(BASE + ".szovegek")


def test_esemeny_epitok():
    assert V.e_mozog(0.5, 0.25) == {"t": "mozog", "x": 0.5, "y": 0.25}
    assert V.e_katt("jobb") == {"t": "katt", "gomb": "jobb"}
    assert V.e_katt("bal", le=True) == {"t": "katt", "gomb": "bal", "le": True}
    assert V.e_gorget(120) == {"t": "gorget", "d": 120}
    assert V.e_bill(65, le=False) == {"t": "bill", "vk": 65, "le": False}
    assert V.e_char("á") == {"t": "char", "ch": "á"}


def test_vezerlo_alapbol_inaktiv():
    vez = V.Vezerlo()
    assert vez.aktiv is False


def test_inaktiv_vezerlo_semmit_nem_csinal():
    # a legfontosabb garancia: inaktívan MINDEN eseményt eldob (nincs injektálás)
    vez = V.Vezerlo()
    vez.aktiv = False
    assert vez.alkalmaz(V.e_mozog(0.5, 0.5)) is False
    assert vez.alkalmaz(V.e_katt("bal")) is False
    assert vez.alkalmaz(V.e_bill(65)) is False
    assert vez.alkalmaz(V.e_char("a")) is False


def test_rossz_bemenet_biztonsagos():
    vez = V.Vezerlo()
    vez.aktiv = True                       # aktív, de rossz/ismeretlen bemenet
    assert vez.alkalmaz(None) is False
    assert vez.alkalmaz("nem dict") is False
    assert vez.alkalmaz({"t": "ismeretlen"}) is False


def test_biztonsagi_szovegek_megvannak():
    # a beleegyező szövegek tartalmazzák a kulcs-üzeneteket
    assert "MEGBÍZHATÓ" in SZ.BELEEGYEZO_SEGITETT
    assert "pánik" in SZ.BELEEGYEZO_SEGITETT.lower() \
        or "leállításról" in SZ.BELEEGYEZO_SEGITETT.lower() \
        or "leáll" in SZ.BELEEGYEZO_SEGITETT.lower()
    assert "vissza" in SZ.BELEEGYEZO_IRANYITO.lower()   # „ne élj vissza”
    assert "{ki}" in SZ.IRANYITAS_AKTIV                 # a felület behelyettesíti
