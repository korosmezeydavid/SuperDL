"""Akciós újság modul (2026-09-25) – a boltok szövegének értelmezése, a
bevásárlólista és a telefonos összefésülés. A minták a boltok valódi
oldalairól/újságjaiból vett, lerövidített részletek (2026. 39. hét)."""
import json
import sys

import pytest

sys.path.insert(0, "modules_src/akciok")

from akciok_mod import aldi, bevasarlo as B, lidl, penny  # noqa: E402
from akciok_mod.termek import Termek, ar_szam, illik  # noqa: E402

# ---- közös ---------------------------------------------------------------


def test_ar_szam():
    assert ar_szam("1 169 Ft") == 1169
    assert ar_szam("1169 Ft") == 1169
    assert ar_szam("899 Ft") == 899
    assert ar_szam("nincs") is None


def test_a_sor_eleje_a_nev_es_az_ar():
    t = Termek("Penny", "Dárdás császárszalonna", ar=1169, kartyas_ar=899,
               kartya_nev="Penny Kártyával", kiszereles="300 g")
    assert t.sor().startswith("Dárdás császárszalonna, 1169 forint, "
                              "Penny Kártyával 899 forint")
    assert t.legjobb_ar() == 899


def test_kereses_ekezet_nelkul_is():
    t = Termek("Penny", "Rántott petrella", kategoria="Fagyasztott termékek")
    assert illik(t, "rantott")
    assert illik(t, "PETRELLA fagyaszt")
    assert not illik(t, "tej")


def test_termek_oda_vissza_json():
    t = Termek("Lidl", "Mangó", ar=199, regi_ar=699, kedvezmeny="-71%")
    assert Termek.szotarbol(json.loads(json.dumps(t.szotar()))) == t


# ---- Penny ----------------------------------------------------------------

PENNY_CSEMPE = """
<a href="/products/dardas-csaszarszalonna-86100453" class="ws-product-tile__link">x</a>
<h3 class="ws-product-title h6" data-test="product-title">DÁRDÁS CSÁSZÁRSZALONNA</h3>
<ul class="ws-product-information__piece-description" data-test="product-information-piece-description" role="list"><li>300 g</li></ul>
<div class="ws-product-price-validity" data-test="product-price-validity"><div>Cs&nbsp;2026.09.24-tól</div><div>Sze&nbsp;2026.09.30-ig</div></div></div>
<div class="ws-product-price-type" data-test="product-price-type"><div class="ws-product-price-type__price-label" data-test="product-price-type-price-label">PENNY Kártya nélkül</div>
<span class="ws-product-price-value__main" aria-hidden="false">1169 Ft</span>
<div class="text-caption" data-test="product-price-type-label">1 KG 3897 Ft</div></div>
<div class="ws-product-price-type" data-test="product-price-type"><div class="ws-product-price-type__price-label" data-test="product-price-type-price-label">PENNY Kártyával</div>
<span class="ws-product-price-value__main" aria-hidden="false">899 Ft</span>
<div class="text-caption" data-test="product-price-type-label">1 KG 2997 Ft</div></div>
<a href="/products/globus-majonez-1" class="ws-product-tile__link">x</a>
<h3 class="ws-product-title h6" data-test="product-title">GLOBUS MAJONÉZ</h3>
<div class="ws-product-price-type" data-test="product-price-type"><div data-test="product-price-type-price-label">Ár</div>
<span class="ws-product-price-value__main" aria-hidden="false">1229 Ft</span></div>
"""


def test_penny_csempe():
    tt = penny.csempek(PENNY_CSEMPE)
    assert len(tt) == 2
    a = tt[0]
    assert a.nev == "Dárdás császárszalonna"
    assert (a.ar, a.kartyas_ar) == (1169, 899)
    assert a.kiszereles == "300 g"
    assert a.egysegar == "1 kg = 3897 Ft"
    assert a.ervenyes == "09.24-tól 09.30-ig"
    assert a.kod.endswith("/products/dardas-csaszarszalonna-86100453")
    assert tt[1].ar == 1229 and tt[1].kartyas_ar is None


def test_penny_bejaras_alkategoriakkal_es_lapozassal():
    fo = '/category/ajanlatok-0924-koezoett'
    oldalak = {
        penny.ALAP + "/ajanlatok": '<a href="%s">x</a>' % fo,
        penny.ALAP + fo: ('<a class="x" href="%s-italok">Italok 29</a>'
                          '<a href="%s-kiemelt-termekeink">Kiemelt 3</a>'
                          % (fo, fo)),
        penny.ALAP + fo + "-italok": PENNY_CSEMPE + '<a href="?page=2">2</a>',
        penny.ALAP + fo + "-italok?page=2": "",
        penny.ALAP + fo + "-kiemelt-termekeink": PENNY_CSEMPE,
    }
    tt = penny.letolt(lambda u: oldalak[u])
    # a gyűjtő kategória („kiemelt”) nem duplázza meg a terméket
    assert len(tt) == 2
    assert {t.kategoria for t in tt} == {"Italok"}


# ---- Lidl -----------------------------------------------------------------

LIDL_SZOVEG = """09. 24. csütörtöktől 09. 27-ig

Vaníliakrémes  
croissant
Briós tésztából
100 g; 1 kg = 2 990 Ft
229747

Szuper ár!

299 Ft

Jó választás
a hazai

Kovászos  
durum vekni
400 g; 1 kg = 1 123 Ft
1010758

Lidl Plus-szal

-30%**

449 Ft

649 Ft

HÚSFARM
Friss, szeletelt, light karaj
Hártyázott
400 g; 1 kg = 2 948 Ft
6400870

-13% 1 359 Ft

1179 Ft

HZ_A4_WW39_1-3o_Cimlap.indd   3
"""


def test_lidl_harom_artipus():
    tt = lidl.termekek(LIDL_SZOVEG, "Akciós újság – 39. hét")
    assert [t.nev for t in tt] == ["Vaníliakrémes croissant",
                                   "Kovászos durum vekni",
                                   "Húsfarm Friss, szeletelt, light karaj"]
    a, b, c = tt
    assert a.ar == 299 and a.kiszereles == "100 g"
    assert a.egysegar == "1 kg = 2 990 Ft" and a.megjegyzes == "Briós tésztából"
    assert (b.ar, b.kartyas_ar, b.kartya_nev) == (649, 449, "Lidl Plus-szal")
    assert (c.ar, c.regi_ar, c.kedvezmeny) == (1179, 1359, "-13%")
    assert all(t.ervenyes == "09.24-tól 09.27-ig" for t in tt)


def test_lidl_rossz_regi_ar_eldobva():
    """Egy rossz ár rosszabb, mint egy hiányzó."""
    t = Termek("Lidl", "x", ar=399, regi_ar=1699, kedvezmeny="-27%")
    lidl._hihetoseg(t)
    assert t.regi_ar is None


# ---- Aldi -----------------------------------------------------------------

@pytest.mark.parametrize("meret, egysegar, vart", [
    ("150 g/csomag", "3 660 Ft/kg", 549),
    ("1 l/doboz", "165 Ft/l", 165),
    ("227 g vagy 185 g/csomag", "5 969,16 / 7 324,32 Ft/kg", 1355),
    ("2 x 200 g", "2 497,50 Ft/kg", 999),
    ("10 tekercs", "102,90 Ft/tekercs", 1029),
    ("", "2 777 Ft/db", 2777),
    ("0,75 l", "3 570 Ft/kg", None),        # liter és kilogramm: nem számolunk
])
def test_aldi_szamolt_ar(meret, egysegar, vart):
    assert aldi.szamolt_ar(meret, egysegar) == vart


def test_aldi_blokk():
    oldal = "SNACK FUN\n\nVAJAS RÚD\n150 g/csomag\n3 660 Ft/kg\n156305\n\n-21 %\n"
    tt = aldi.termekek([oldal], "Akciós újság, 39. hét", "09.24-tól")
    assert len(tt) == 1
    t = tt[0]
    assert t.nev == "Snack Fun Vajas Rúd"
    assert t.ar == 549 and t.kiszereles == "150 g"


def test_aldi_ujsagnevek_het_szerint():
    import datetime as dt
    nevek = [n for n, _f, _h in aldi.ujsag_nevek(dt.date(2026, 9, 25))]
    assert nevek[0] == "aldi_online_akcios_ujsag_2026_kw39"
    assert "aldi_kozepso_sor_2026_kw39" in nevek


# ---- bevásárlólista -------------------------------------------------------

@pytest.fixture
def lista(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "FAJL", tmp_path / "bl.json")
    monkeypatch.setattr(B, "ATJARO_FAJL", tmp_path / "atjaro.json")
    return B.betolt()


def test_termek_felvetele_bolttal_es_legjobb_arral(lista):
    t = Termek("Penny", "Rántott petrella", ar=1299, kartyas_ar=999)
    tetel, uj = B.termek_hozzaad(lista, t)
    assert uj and tetel["name"] == "Rántott petrella (Penny)"
    assert tetel["priceHuf"] == 999
    _t, uj2 = B.termek_hozzaad(lista, t)
    assert not uj2 and len(B.tetelek(lista)) == 1


def test_mentes_es_betoltes(lista):
    B.hozzaad(lista, "Tej", 399)
    B.ment(lista)
    ujra = B.betolt()
    assert B.tetelek(ujra)[0]["name"] == "Tej"
    assert B.osszeg(B.tetelek(ujra)) == 399


def test_telefon_cim_az_atjarobol(lista):
    B.telefon_cim_ment("192.168.1.5", 8080)
    assert B.telefon_cim() == ("192.168.1.5", 8080)


# ---- a telefon portálja (a PortalControlPages.shoppingPage alakja) ----------

def _oldal(listak, aktiv, tetelek):
    opts = "".join('<option value="%s"%s>%s</option>'
                   % (n, " selected" if n == aktiv else "", n) for n in listak)
    lis = "".join(
        '<li class="media-item"><span class="media-name">%s%s%s</span>'
        '<span class="media-size">%s • %s</span>'
        '<input type="hidden" name="id" value="%d"></li>'
        % ("<s>" if t["checked"] else "", t["name"],
           "</s>" if t["checked"] else "",
           "%d Ft" % t["priceHuf"] if t.get("priceHuf") is not None else "—",
           "Megvan" if t["checked"] else "Még nincs meg", t["id"])
        for t in tetelek)
    return ('<select id="shop_list" name="list">%s</select><ul>%s</ul>'
            '<input id="shop_newlist" name="name">' % (opts, lis))


class _FakeTelefon:
    """A telefon portálja memóriában – a valódi végpontok szerint."""
    def __init__(self, listak):
        self.listak = listak
        self.aktiv = next(iter(listak), None)
        self.pin = "1234"

    def _valasz(self, pin):
        class R:
            status_code = 200
            def raise_for_status(self):
                pass
        r = R()
        if pin != self.pin:
            r.text = '<form><input name="pin"></form>'
        else:
            r.text = _oldal(list(self.listak), self.aktiv,
                            self.listak.get(self.aktiv, []))
        return r

    def get(self, url, params=None, timeout=None):
        return self._valasz(params["pin"])

    def post(self, url, params=None, data=None, timeout=None):
        ut = url.split("8080", 1)[1]
        lst = self.listak.get(self.aktiv, [])
        if ut == "/shopping/select":
            self.aktiv = data["list"]
        elif ut == "/shopping/newlist":
            self.listak[data["name"]] = []
            self.aktiv = data["name"]
        elif ut == "/shopping/add":
            lst.append({"id": max([t["id"] for t in lst] + [0]) + 1,
                        "name": data["name"], "checked": False,
                        "priceHuf": int(data["price"]) if "price" in data
                        else None})
        elif ut == "/shopping/toggle":
            for t in lst:
                if t["id"] == int(data["id"]):
                    t["checked"] = not t["checked"]
        return self._valasz(params["pin"])


def test_osszefesules_ket_iranyban(lista):
    tel = _FakeTelefon({"Heti": [],
                        B.ALAP_LISTA: [{"id": 1, "name": "Kenyér",
                                        "checked": True, "priceHuf": None},
                                       {"id": 2, "name": "tej",
                                        "checked": False, "priceHuf": 399}]})
    B.hozzaad(lista, "Tej", 399)
    t, _ = B.hozzaad(lista, "Rántott petrella (Penny)", 999)
    t["checked"] = True
    e = B.Telefon("1.2.3.4", "1234", 8080, session=tel).szinkron(lista)
    # a „megvan” jelzés az új tételekkel együtt utazik (ezek „le”/„fel”
    # alatt számolódnak); a „pipa” a MINDKÉT oldalon meglévő tételek egyeztetése
    assert e == {"le": 1, "fel": 1, "pipa": 0}
    nevek = sorted(x["name"] for x in B.tetelek(lista))
    assert nevek == ["Kenyér", "Rántott petrella (Penny)", "Tej"]
    tlista = tel.listak[B.ALAP_LISTA]
    assert [x["name"] for x in tlista] == ["Kenyér", "tej",
                                          "Rántott petrella (Penny)"]
    assert next(x for x in tlista if x["name"].startswith("Rántott"))["checked"]
    assert next(x for x in B.tetelek(lista) if x["name"] == "Kenyér")["checked"]
    # ha a telefonon kipipálják, a gépen is megvan lesz
    next(x for x in tlista if x["name"] == "tej")["checked"] = True
    e1 = B.Telefon("1.2.3.4", "1234", 8080, session=tel).szinkron(lista)
    assert e1 == {"le": 0, "fel": 0, "pipa": 1}
    assert next(x for x in B.tetelek(lista) if x["name"] == "Tej")["checked"]
    # másodszorra nincs mit tenni – a szinkron nem duplikál
    e2 = B.Telefon("1.2.3.4", "1234", 8080, session=tel).szinkron(lista)
    assert e2 == {"le": 0, "fel": 0, "pipa": 0}


def test_ha_nincs_ilyen_lista_a_telefonon_letrehozza(lista):
    tel = _FakeTelefon({"Heti": []})
    B.hozzaad(lista, "Alma")
    B.Telefon("1.2.3.4", "1234", 8080, session=tel).szinkron(lista)
    assert tel.listak[B.ALAP_LISTA][0]["name"] == "Alma"
    assert tel.listak["Heti"] == []


def test_rossz_pin(lista):
    tel = _FakeTelefon({})
    with pytest.raises(B.RosszPin):
        B.Telefon("1.2.3.4", "0000", 8080, session=tel).szinkron(lista)


# ---- a felület --------------------------------------------------------------

def test_az_ablak_szur_es_rendez():
    wx = pytest.importorskip("wx")
    from akciok_mod import akciokwin as W
    app = wx.App(False)          # noqa: F841
    termekek = [Termek("Penny", "Tej", ar=399, kategoria="Italok"),
                Termek("Lidl", "Rántott petrella", ar=999, kartyas_ar=799),
                Termek("Aldi", "Alma", ar=199)]
    f = W.AkciokFrame.__new__(W.AkciokFrame)
    olcso = W.AkciokFrame.szurt(f, termekek, W.OSSZES_KAT, "", 1)
    assert [t.nev for t in olcso] == ["Alma", "Tej", "Rántott petrella"]
    assert [t.nev for t in W.AkciokFrame.szurt(f, termekek, "Italok", "", 0)] \
        == ["Tej"]
    assert [t.nev for t in W.AkciokFrame.szurt(f, termekek, W.OSSZES_KAT,
                                                "rantott", 0)] \
        == ["Rántott petrella"]


def test_az_ablak_gombjainak_alt_betui_nem_utkoznek():
    import inspect
    import re
    from akciok_mod import akciokwin as W
    for fv in (W.AkciokFrame._build, W.ListaDialog.__init__):
        betuk = [m.lower() for m in
                 re.findall(r'label="[^"]*?&(\w)|\("[^"]*?&(\w)',
                            inspect.getsource(fv)) for m in m if m]
        assert len(betuk) == len(set(betuk)), (fv.__name__, betuk)
