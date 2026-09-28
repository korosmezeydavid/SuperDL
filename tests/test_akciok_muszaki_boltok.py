"""Petrus József (2026-09-28): „néhány férfiasabb bolt is belekerülhetne:
Euronics, MediaMarkt, Praktiker, OBI". Az Euronics és a Praktiker saját
oldala szövegként adja az árakat; a minták a boltok valódi oldalaiból
(2026-09-28) valók, rövidítve."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "modules_src" / "akciok"))

from akciok_mod import csoport as CS           # noqa: E402
from akciok_mod import euronics, praktiker     # noqa: E402
from akciok_mod import forrasok as F           # noqa: E402
from akciok_mod.termek import lejart           # noqa: E402

PRAKTIKER = (
    '<script>x = [{"id":421301,"name":"Keter Hollywood m\\u0171anyag 270L '
    'grafit sz\\u00edn\\u0171 kerti t\\u00e1rol\\u00f3","photos":{"main":"a.png"},'
    '"url":"/kert/kerti-butor/keter/p/421301","productItemUnit":'
    '{"salesUnitType":"darab"},"price":{"displayPrice":"13.990 Ft / darab",'
    '"displayOldPrice":"16.990 Ft / darab","price":13990,"oldPrice":16990,'
    '"unitPrice":13990,"details":{"id":2,"name":"Akci\\u00f3","fromDate":'
    '"2026-09-01","endDate":"2026-09-28"},"discountPercent":17,'
    '"isLoyaltyPrice":false}},'
    '{"id":421301,"name":"Keter Hollywood (ism\\u00e9t)","price":{"price":1}},'
    '{"id":500,"name":"Falfest\\u00e9k 10 l","url":"/p/500","price":'
    '{"displayPrice":"8.990 Ft / darab","price":8990,"oldPrice":10990,'
    '"discountPercent":18,"isLoyaltyPrice":true,"details":{"fromDate":'
    '"2026-09-20","endDate":"2026-10-05"}}},'
    '{"id":7,"name":"Kateg\\u00f3ria, nincs \\u00e1r","price":null},'
    '{"id":8,"name":"Onix padl\\u00f3lap","url":"/p/8","productItemUnit":'
    '{"salesUnitType":"csomag","unitType":"m2"},"price":{"price":6478,'
    '"oldPrice":null,"unitPrice":3999,"details":null,"discountPercent":0,'
    '"isLoyaltyPrice":false},"loyalty":[{"type":"normal","price":'
    '{"price":6478,"isLoyaltyPrice":false}},{"type":"loyalty-3","price":'
    '{"price":6284,"discountPercent":3,"isLoyaltyPrice":true}},'
    '{"type":"loyalty-5","price":{"price":6154,"discountPercent":5,'
    '"isLoyaltyPrice":true}}],"startDate":"2026-09-15","endDate":'
    '"2026-10-12"}]</script>')


def test_praktiker_termekek():
    t = praktiker.termekek(PRAKTIKER, "Árzuhanás")
    assert [x.kod for x in t] == ["421301", "500", "8"]  # ismétlés és ár nélküli kimarad
    # Praktiker Plusz: a legalsó szint a kártyás ár, a többi a megjegyzésben
    c = t[2]
    assert (c.ar, c.kartyas_ar) == (6478, 6284)
    assert c.megjegyzes == ("a legmagasabb törzsvásárlói szinten "
                            "6154 forint (-5%)")
    assert c.egysegar == "3999 Ft / m2"
    assert c.ervenyes == "09.15-tól 10.12-ig"
    assert t[0].egysegar == ""                          # darabár = egységár
    a = t[0]
    assert a.nev == "Keter Hollywood műanyag 270L grafit színű kerti tároló"
    assert (a.ar, a.regi_ar, a.kedvezmeny) == (13990, 16990, "-17%")
    assert a.url == "https://www.praktiker.hu/kert/kerti-butor/keter/p/421301"
    assert a.ervenyes == "09.01-tól 09.28-ig"
    assert lejart(a.ervenyes, dt.date(2026, 9, 29))
    assert not lejart(a.ervenyes, dt.date(2026, 9, 28))
    # törzsvásárlói ár: kártyás ár, mellette a kártya nélküli
    b = t[1]
    assert (b.kartyas_ar, b.ar) == (8990, 10990)
    assert "törzsvásárlói" in b.kartya_nev


def test_praktiker_letolt_ket_oldal_egy_hibas():
    hivott = []

    def get(u):
        hivott.append(u)
        if "ilp" in u:
            raise OSError("nincs")
        return PRAKTIKER
    t = praktiker.letolt(get)
    assert len(hivott) == 2 and len(t) == 3


EURONICS = """
<div class="box-data">Érvényes: 2026.09.17. - 2026.09.30. között.
 <a class="btn btn-primary" href="/jo-arak-jo-helyen">Megnézem</a></div>
<div>Érvényes: 2023.04.20 - 2023.04.26. között. --><a class="btn btn-primary" href="/husegkartya">x</a></div>
<div class="product-card" data-product-id="315569" data-product-list="">
<meta itemprop="url" content="https://euronics.hu/beepitheto-suto/electrolux-p315569" />
<div class="product-card__name fitIn"><a class="product-card__name-link" href="x" title="y">
<span itemprop="name" class="product-card__name-link-text">Electrolux LOF4P06BK SurroundCook 300 Beépíthető sütő</span>
</a></div>
<div class="product-card__price"><div itemprop="offers">
<meta itemprop="priceCurrency" content="HUF">
<div class="price price--on-list price--discount" itemprop="price" content="109899.9961">
<span>
    109\xa0900\xa0Ft        </span>
<span class="price-original">
    137\xa0490\xa0Ft
 </span>    </div></div></div></div>
<div class="product-card" data-product-id="1" data-product-list="">
<span itemprop="name" class="product-card__name-link-text">Ár nélküli</span></div>
"""


def test_euronics_kampanyok_csak_a_futok():
    k = euronics.kampanyok(EURONICS, dt.date(2026, 9, 28))
    assert k == [("/jo-arak-jo-helyen", "Jó árak jó helyen",
                  "09.17-tól 09.30-ig")]
    assert euronics.kampanyok(EURONICS, dt.date(2026, 10, 1)) == []


def test_euronics_termekek():
    t = euronics.termekek(EURONICS, "Heti ajánlatok")
    assert len(t) == 1
    a = t[0]
    assert a.nev == "Electrolux LOF4P06BK SurroundCook 300 Beépíthető sütő"
    assert (a.ar, a.regi_ar, a.kedvezmeny) == (109900, 137490, "-20%")
    assert a.url.endswith("-p315569") and a.kod == "315569"
    assert CS.besorol(a.nev, a.kategoria, a.bolt) == "Műszaki cikk"


def test_euronics_letolt():
    def get(u):
        return EURONICS
    t = euronics.letolt(get, ma=dt.date(2026, 9, 28))
    # ugyanaz a termék a kampányban és a heti oldalon: egyszer, a kampány
    # érvényességével
    assert len(t) == 1 and t[0].ervenyes == "09.17-tól 09.30-ig"
    assert t[0].kategoria == "Jó árak jó helyen"


def test_csoportok():
    assert CS.besorol("Keter kerti tároló", "", "Praktiker") == "Barkács és kert"
    assert CS.besorol("Valami egészen más", "", "Praktiker") == "Barkács és kert"
    assert CS.besorol("Samsung 55 QLED Smart TV", "", "Euronics") == "Műszaki cikk"
    assert CS.besorol("Ismeretlen", "", "Euronics") == "Műszaki cikk"
    assert "Műszaki cikk" in CS.CSOPORTOK and "Barkács és kert" in CS.CSOPORTOK


def test_be_vannak_kotve():
    assert F.bolt_fajta("euronics") == F.bolt_fajta("praktiker") == "muszaki"
    assert ("muszaki", "Minden műszaki és barkácsbolt") in F.FAJTAK
    assert F.bolt_id_nevbol("Praktiker") == "praktiker"
