"""Petrus József és Schibik Miklós levelei (2026-09-28): lejárt akciók,
Tesco húspult, darabszám és végösszeg, lista kiürítése, kedvencek."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "modules_src" / "akciok"))

from akciok_mod import beallitas as BE      # noqa: E402
from akciok_mod import bevasarlo as B       # noqa: E402
from akciok_mod import tesco                # noqa: E402
from akciok_mod.termek import Termek, lejart  # noqa: E402

MA = dt.date(2026, 9, 28)


def test_lejart_akciok():
    assert lejart("09.24-tól 09.27-ig", MA)            # Lidl hét eleje
    assert not lejart("09.24-tól 09.30-ig", MA)
    assert not lejart("10.01-tól 10.07-ig", MA)        # jövő hét: marad
    assert not lejart("2026. 09. 02–09. 29.", MA)
    assert lejart("2026. 09. 02–09. 27.", MA)
    assert not lejart("09.28–10.04.", MA)              # Müller
    assert not lejart("09.21-tól", MA) and lejart("09.10-tól", MA)   # Aldi
    assert not lejart("", MA) and not lejart("a készlet erejéig", MA)
    # évfordulón át
    assert not lejart("12.28-tól 01.03-ig", dt.date(2026, 12, 30))
    assert lejart("12.28-tól 01.03-ig", dt.date(2027, 1, 4))


TESCO = """Fehér magszegény szőlő
500 g, 798 Ft/1 kg

 1599 Ft/kg

– 28 %

 1145

 Ft/kg

 Friss magyar sertéslapocka
húspultban kapható
Friss magyar vákuumcsomagolt sertéslapocka
csomagolt, különböző kiszerelésben kapható
1 639 Ft/kg
999 Ft/kg
 A termék a húspulttal rendelkező áruházainkban kapható.

 Friss magyar csirke
alsócomb
húspultban kapható
Friss magyar csirke
felsőcomb
húspultban kapható
896 Ft/kg
779 Ft/kg

 Kaiser sváb füstölt sonka
csemegepultban kapható
4 590 Ft/1 kg
2990 Ft/1 kg
"""


def test_tesco_huspult():
    p = {t.nev: t for t in tesco.pultos_termekek(TESCO, "Hipermarket újság")}
    assert p["Friss magyar sertéslapocka"].ar == 1145
    assert p["Friss magyar sertéslapocka"].regi_ar == 1599
    assert p["Friss magyar sertéslapocka"].kedvezmeny == "-28%"
    assert p["Friss magyar sertéslapocka"].kiszereles == "kilónként"
    assert p["Friss magyar vákuumcsomagolt sertéslapocka"].ar == 999
    assert p["Friss magyar vákuumcsomagolt sertéslapocka"].regi_ar == 1639
    assert p["Friss magyar csirke alsócomb"].ar == 779
    assert p["Friss magyar csirke felsőcomb"].regi_ar == 896
    assert "Kaiser sváb füstölt sonka" not in p      # Ft/1 kg: a rendes elemzőé
    mind = {t.nev for t in tesco.termekek(TESCO, "Hipermarket újság")}
    assert {"Kaiser sváb füstölt sonka", "Friss magyar sertéslapocka",
            "Fehér magszegény szőlő"} <= mind


def test_darabszam_es_vegosszeg():
    adat = {"aktiv": "x", "listak": {"x": []}}
    t, _ = B.hozzaad(adat, "Mizse ásványvíz (Lidl)", 129)
    B.hozzaad(adat, "Kenyér", 500)
    assert B.osszeg(B.tetelek(adat)) == 629
    B.darab_allit(adat, t["id"], 6)
    assert B.darab(t) == 6 and B.osszeg(B.tetelek(adat)) == 6 * 129 + 500
    assert "6 darab" in B.tetel_sor(t) and "774 forint" in B.tetel_sor(t)
    sz = B.szoveges(adat, MA)
    assert "6 × Mizse ásványvíz (Lidl) – 774 Ft (129 Ft darabja)" in sz
    assert "Összesen kb. 1 274 Ft" in sz
    B.darab_allit(adat, t["id"], 1)
    assert "qty" not in t


def test_lista_kiurites():
    adat = {"aktiv": "x", "listak": {"x": []}}
    a, _ = B.hozzaad(adat, "a")
    B.hozzaad(adat, "b")
    B.megvan_valt(adat, a["id"])
    assert B.kiurit(adat, csak_megvan=True) == 1
    assert [t["name"] for t in B.tetelek(adat)] == ["b"]
    assert B.kiurit(adat) == 1 and B.tetelek(adat) == []


def test_kedvencek(tmp_path, monkeypatch):
    monkeypatch.setattr(BE, "FAJL", tmp_path / "be.json")
    adat = BE.betolt()
    assert BE.kedvenc_hozzaad(adat, "  Mizse   ásványvíz ")
    assert not BE.kedvenc_hozzaad(adat, "mizse ásványvíz")
    assert BE.kedvenc_hozzaad(adat, "Félix")
    BE.ment(adat)
    assert BE.betolt()["kedvencek"] == ["Mizse ásványvíz", "Félix"]
    termekek = [Termek("Spar", "Mizse ásványvíz 1,5 l", ar=149),
                Termek("Lidl", "Mizse ásványvíz szénsavas", ar=129),
                Termek("Penny", "Kenyér", ar=400)]
    tal = BE.kedvenc_talalatok(adat["kedvencek"], termekek)
    assert [t.bolt for t in tal[0][1]] == ["Lidl", "Spar"]   # ár szerint
    assert tal[1][1] == []
    assert BE.kedvenc_osszefoglalo(tal) == \
        "Kedvenceid közül most akciós: Mizse ásványvíz (Lidl 129 forint, " \
        "Spar 149 forint)."
    assert BE.kedvenc_osszefoglalo([("x", [])]) == ""
    assert BE.kedvenc_torol(adat, "félix") and adat["kedvencek"] == ["Mizse ásványvíz"]
