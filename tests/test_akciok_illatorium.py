"""Illatorium (2026-09-27): Dávid saját parfümboltja a Akciós újságban – a
kinyerés az extract.mjs Python-változata; élőben 2389/2389 tétel, 0 ár-
eltérés a G:\\Saját meghajtó\\illatlistak\\illatorium_katalogus.json-hoz."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "modules_src" / "akciok"))

from akciok_mod import csoport as CS          # noqa: E402
from akciok_mod import forrasok as F          # noqa: E402
from akciok_mod import illatorium as I        # noqa: E402
from akciok_mod.termek import illik           # noqa: E402

CSOMAG = (
    'x={id:"necessary",name:"Süti"};'
    'a=[{id:"AM-PINK",name:"America Pink EDT 50 ml",category:"america",'
    'inspiredBy:"Playboy \\u2013 Pink",scentNote:"Gyümölcsösen édes",'
    'price50:3000,price50:3000},'
    '{id:"FP-1",name:"Francesco \\"Noir\\" EDP",category:"fp-ferfi",'
    'inspiredBy:"Versace – Eros",price30:4500,price100:9900,volume:"30 ml"}];'
    'Vae=[["LF1","Blue","Chanel – Bleu"]];Uae=[];Hae=[];'
    'gg("sorgenta-noi","Sorgenta női",[{no:"12",name:"Rose",brand:"Dior",'
    'price30:3500}]);')


def test_kinyeres_mindharom_alak():
    tk = {t.kod: t for t in I.termekek(CSOMAG)}
    assert set(tk) == {"AM-PINK", "FP-1", "LF1", "SORG-12"}
    p = tk["AM-PINK"]
    assert (p.ar, p.kiszereles, p.kategoria) == (3000, "50 ml",
                                                 "America / US Prestige")
    assert "Ihlette: Playboy – Pink" in p.megjegyzes
    f = tk["FP-1"]
    assert f.nev == 'Francesco "Noir" EDP'
    assert f.ar == 4500 and f.kiszereles == "30 ml"
    assert "Más kiszerelés: 100 ml 9900 forint" in f.megjegyzes
    assert tk["LF1"].nev == "Scent of Blue" and tk["LF1"].ar == 5000
    assert tk["SORG-12"].megjegyzes.startswith("Ihlette: Dior – Rose")
    assert all(CS.csoportja(t) == "Parfüm és illat" for t in tk.values())


def test_keresheto_az_ihleto_parfum():
    tk = {t.kod: t for t in I.termekek(CSOMAG)}
    assert illik(tk["FP-1"], "versace")
    assert not illik(tk["AM-PINK"], "versace")


def test_csomag_neve_a_htmlbol():
    oldalak = {I.OLDAL: '<script type="module" src="/assets/index-AbC1.js">',
               I.ALAP + "/assets/index-AbC1.js": CSOMAG}
    assert len(I.letolt(lambda u: oldalak[u])) == 4


def test_bolt_adatai():
    assert F.bolt_fajta("illatorium") == "drogeria"
    assert F.webshop("illatorium")
    assert F.bolt_id_nevbol("Illatorium") == "illatorium"


def test_parfum_csoport_mas_boltban():
    assert CS.besorol("Mugler Angel Eau de Parfum", "Parfüméria", "Müller") \
        == "Parfüm és illat"
    assert CS.besorol("Parfümös tusfürdő", "", "Rossmann") == \
        "Drogéria és szépségápolás"
