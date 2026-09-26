# -*- coding: utf-8 -*-
"""Akciós újság 0.5.0 – Petrus József ötletei (2026-09-26).

1. Minden bolt nézetben a bolt neve az ár után („a legolcsóbbtól a
   legdrágábbig, persze feltüntetve az áruház nevét").
2. A bevásárlólista kiküldése (vágólap, fájl, Super Edit).
3. Közös termékcsoport minden bolthoz."""
import datetime as dt
import sys

import pytest

sys.path.insert(0, "modules_src/akciok")

from akciok_mod import bevasarlo as B, csoport as C  # noqa: E402
from akciok_mod.termek import Termek  # noqa: E402


def test_bolt_neve_az_ar_utan_csak_minden_bolt_nezetben():
    t = Termek("Lidl", "Joghurt natúr", ar=199, kiszereles="150 g")
    assert t.sor() == "Joghurt natúr, 199 forint, 150 g"
    assert t.sor(True) == "Joghurt natúr, 199 forint, Lidl, 150 g"


def _lista():
    adat = {}
    B.hozzaad(adat, "Rántott petrella (Penny)", 899)
    B.hozzaad(adat, "Gyulai kolbász (Auchan)", 4581)
    t, _ = B.hozzaad(adat, "Tej (Lidl)", 299)
    B.megvan_valt(adat, t["id"])
    return adat


def test_kikuldheto_szoveg():
    sz = B.szoveges(_lista(), dt.date(2026, 9, 26))
    sorok = sz.splitlines()
    assert sorok[0] == "Bevásárlólista – %s (2026. szeptember 26.)" % B.ALAP_LISTA
    assert "Rántott petrella (Penny) – 899 Ft" in sorok
    assert "Gyulai kolbász (Auchan) – 4 581 Ft" in sorok
    # a „megvan” tétel nem a listán, hanem külön a végén, és nincs az összegben
    assert "Összesen kb. 5 480 Ft" in sorok
    assert sorok[-1] == "Már megvan: Tej (Lidl)"


def test_mentes_szovegfajlba_es_wordbe(tmp_path):
    sz = B.szoveges(_lista(), dt.date(2026, 9, 26))
    txt = tmp_path / "lista.txt"
    B.ment_fajlba(sz, str(txt))
    assert txt.read_text(encoding="utf-8-sig").replace("\r\n", "\n") == sz
    docx = pytest.importorskip("docx")
    w = tmp_path / "lista.docx"
    B.ment_fajlba(sz, str(w))
    ps = [p.text for p in docx.Document(str(w)).paragraphs]
    assert ps[0].startswith("Bevásárlólista") and "Rántott petrella (Penny) – 899 Ft" in ps


@pytest.mark.parametrize("nev,kat,bolt,vart", [
    ("Milbona tejföl 20%", "", "Lidl", "Tejtermék és tojás"),
    ("Tejszelet multipack", "", "Tesco", "Édesség és snack"),
    ("Túró Rudi natúr", "", "Penny", "Édesség és snack"),
    ("Regnum lecsókolbász", "", "Spar", "Hús, hal, felvágott"),
    ("S-BUDGET disznósajt", "", "Spar", "Hús, hal, felvágott"),
    ("Italiamo Terra di bari extra szűz olívaolaj", "", "Lidl", "Alapvető élelmiszer"),
    ("Borsodi dobozos világos sör multipack", "", "Tesco", "Ital"),
    ("Kígyóuborka", "", "Penny", "Zöldség és gyümölcs"),
    ("Ecetes uborka", "", "Penny", "Alapvető élelmiszer"),
    ("Kornspitz kifli", "", "Auchan", "Pékáru"),
    ("Pampers Active Baby pants", "", "Tesco", "Baba"),
    ("Whiskas alutasakos macskaeledel", "", "Auchan", "Állateledel"),
    ("Jar sensitive mosogatószer", "", "Penny", "Háztartás és tisztítószer"),
    ("Nivea tusfürdő", "", "Aldi", "Drogéria és szépségápolás"),
    ("Apenta málna ízű üdítőital +50 ft betétdíj", "", "Penny", "Ital"),
    ("Iglo gyorsfagyasztott halrudak", "", "Auchan", "Fagyasztott"),
    ("Parkside Bontókalapács", "", "Lidl", "Egyéb"),
    # drogérialánc: a saját kategóriája dönt, nem a név („citromos")
    ("Isana tusfürdő citrom", "Szépségápolás", "Rossmann", "Drogéria és szépségápolás"),
    ("Naturland zöld tea", "Élelmiszer", "Rossmann", "Ital"),
    ("Hajcsat szett", "Hajcsat", "dm", "Drogéria és szépségápolás"),
])
def test_termekcsoport(nev, kat, bolt, vart):
    assert C.besorol(nev, kat, bolt) == vart


def test_csoport_szures_es_megjegyzes():
    wx = pytest.importorskip("wx")  # noqa: F841
    from akciok_mod import akciokwin as W
    t1 = Termek("Lidl", "Milbona joghurt", ar=199)
    t2 = Termek("Lidl", "Parkside fúrógép", ar=9999)
    ki = W.AkciokFrame.szurt(None, [t1, t2], W.OSSZES_KAT, "", 0,
                             "Tejtermék és tojás")
    assert ki == [t1] and t1.csoport == "Tejtermék és tojás"
    assert "Termékcsoport: Tejtermék és tojás" in t1.reszletek()
