"""Akciós újság 0.6.0 (2026-09-27): Müller, Pepco, Libri; boltfajták; a bolt
oldala (Ctrl+O) és a cím másolása (Ctrl+Shift+C). A minták a boltok valódi
oldalainak/prospektusainak rövidített alakjai."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "modules_src" / "akciok"))

from akciok_mod import csoport as CS          # noqa: E402
from akciok_mod import forrasok as F          # noqa: E402
from akciok_mod import libri, mueller, pepco  # noqa: E402
from akciok_mod.termek import Termek          # noqa: E402

MUELLER = """MÜLLER AJÁNLATOK 2026£09£28ÅTÓL 10£04ÅIG

\xa0TESTÁPOLÁS

  1.395\xa0Ft
  995\xa0Ft  
−28 %

PALMOLIVE
Habfürdő  
 650 ml  
többféle
154âFt/1 ml

  795\xa0Ft
  645\xa0Ft  
−18 %

Frissítő 
dezodor párna  
 30âdb  
Creamy 
Comfort vagy 
Flower Fresh 
illatban
2150âFt/1âdb

15 %

KEDVEZMÉNY

15 % kedvezmény 
minden SANA 
lábápoló 
termékre!*

  13.990\xa0Ft
  9.990\xa0Ft  
−28 %

PHILIPS 
ONEBLADE 
SkinProtect penge, 
ÍegecèeØe-jexA», 
vízálló.    
"""


def test_mueller_prospektus():
    tk = mueller.termekek(MUELLER, "Drogéria", mueller.ervenyes(MUELLER))
    assert [t.nev for t in tk] == ["Palmolive Habfürdő",
                                   "Frissítő dezodor párna",
                                   "Philips ONEBLADE SkinProtect penge, "
                                   "vízálló"]
    p = tk[0]
    assert (p.ar, p.regi_ar, p.kedvezmeny, p.kiszereles) == \
        (995, 1395, "-28%", "650 ml")
    assert p.kategoria == "Testápolás" and p.ervenyes == "09.28–10.04."
    # az egységárat NEM vesszük át (a tizedesvessző elveszett belőle)
    assert p.egysegar == ""
    assert tk[1].kiszereles == "30 db"
    assert "Flower Fresh" in tk[1].megjegyzes
    # a zagyva kódolású sor kimarad a névből
    assert "Ø" not in tk[2].nev


def test_mueller_prospektus_linkek():
    html = ('x "https://mueller-dam-bucket.s3.eu-central-1.amazonaws.com/prod/'
            'public/hu/prospektusok/drogerie/D07-2026/a_12_Seiten\\" y '
            '"https://mueller-dam-bucket.s3.eu-central-1.amazonaws.com/prod/'
            'public/hu/prospektusok/drogerie/D07-2026/b_InlineBanner_x?ts=1" '
            '"https://mueller-dam-bucket.s3.eu-central-1.amazonaws.com/prod/'
            'public/hu/prospektusok/spielware/SPW/c_8_Seiten"')
    p = mueller.prospektusok(html)
    assert p == [("drogerie", "https://mueller-dam-bucket.s3.eu-central-1."
                  "amazonaws.com/prod/public/hu/prospektusok/drogerie/"
                  "D07-2026/a_12_Seiten")]


PEPCO = ('<li><a href="/products/halloween-plussfigura-637271" class="x" '
         'aria-label="halloween plüssfigura - 1800.0 Ft"><div '
         'aria-label="Product description: tökkel és macskával">tökkel</div>'
         '</a></li><li><a href="/products/fekete-ruha-lanyoknak-638027" '
         'aria-label="Fekete ruha lányoknak macskamintával - 2500.0 Ft">'
         '</a></li><li><a href="/products/halloween-plussfigura-637271" '
         'aria-label="halloween plüssfigura - 1800.0 Ft"></a>')


def test_pepco_ujsag():
    tk = pepco.termekek(PEPCO)
    assert [(t.nev, t.ar) for t in tk] == [("Halloween plüssfigura", 1800),
                                           ("Fekete ruha lányoknak "
                                            "macskamintával", 2500)]
    assert tk[0].megjegyzes == "Tökkel és macskával"
    assert tk[0].hivatkozas() == \
        "https://pepco.hu/products/halloween-plussfigura-637271"
    # vegyes áru: a macskamintás ruha NEM állateledel
    assert CS.csoportja(tk[1]) == "Ruházat és cipő"
    assert CS.csoportja(tk[0]) == "Játék"


LIBRI = ('<a href="/konyv/irodalom/" title="Irodalom">Irodalom</a>'
         '<div class="product-grid-item gtm h-100" data-doc-id="1" '
         'data-url="https://www.libri.hu/konyv/a.html" data-name="Vének '
         'háborúja" data-category="irodalom/sci-fi" data-price="3136">'
         '<a class="authors">John Scalzi</a>'
         '<span class="origin"><span>Borító ár:</span>\n\t<span>4 480 Ft'
         '</span></span></div>'
         '<div class="product-grid-item gtm" data-doc-id="1" data-name="X">'
         '</div><a href="?page=2">2</a><a href="?page=51">51</a>')


def test_libri_konyvutca():
    katok = libri.kategoriak(LIBRI)
    tk = libri.termekek(LIBRI, katok)
    assert len(tk) == 1                       # a kétszer megjelenő doboz egyszer
    t = tk[0]
    assert t.nev == "John Scalzi: Vének háborúja"
    assert (t.ar, t.regi_ar, t.kedvezmeny) == (3136, 4480, "-30%")
    assert t.kategoria == "Irodalom" and CS.csoportja(t) == "Könyv"
    assert t.hivatkozas() == "https://www.libri.hu/konyv/a.html"
    assert libri.lapok_szama(LIBRI) == 51
    # ISO-8859-2 oldal: az ékezet megmarad
    assert libri.dekod('<meta charset="ISO-8859-2">Vének'.encode("iso-8859-2")) \
        .endswith("Vének")


def test_libri_lapozas_megall_ha_nincs_uj():
    oldalak = {libri.OLDAL: LIBRI.encode("utf-8")}

    def gb(url):
        return oldalak.get(url, LIBRI.encode("utf-8"))  # ugyanaz → megáll
    tk = libri.letolt(gb, szunet=0)
    assert len(tk) == 1


def test_hivatkozas_es_bolt_oldal():
    t = Termek(bolt="Penny", nev="x", kod="https://www.penny.hu/products/x")
    assert t.hivatkozas() == "https://www.penny.hu/products/x"
    assert "Weboldal: https://www.penny.hu/products/x" in t.reszletek()
    assert Termek(bolt="Lidl", nev="y", kod="12345").hivatkozas() == ""
    assert F.bolt_id_nevbol("Spar") == "spar"
    assert F.bolt_id_nevbol("Müller") == "mueller"
    assert F.webshop("libri") and not F.webshop("lidl")
    assert F.bolt_oldal("mueller") == "https://www.mueller.co.hu/prospektusok/"


def test_boltfajtak():
    fajtak = {F.bolt_fajta(a) for a, _n, _f in F.BOLTOK}
    assert fajtak == {"elelmiszer", "drogeria", "vegyes", "konyv"}
    pytest.importorskip("wx")
    from akciok_mod import akciokwin as W

    class Cs:
        _valasztott_boltok = W.AkciokFrame._valasztott_boltok
        _valasztott_bolt = W.AkciokFrame._valasztott_bolt

        class bolt:
            i = 0

            @classmethod
            def GetSelection(cls):
                return cls.i
    c = Cs()
    c._bolt_ertekek = [None, ("fajta", "drogeria"), ("bolt", "libri")]
    c.bolt.i = 1
    assert c._valasztott_boltok() == ["rossmann", "dm", "mueller"]
    assert c._valasztott_bolt() is None
    c.bolt.i = 2
    assert c._valasztott_boltok() == ["libri"] and c._valasztott_bolt() == "libri"


def test_mueller_vegyes_kinalat_csoportjai():
    assert CS.besorol("Haribo Gumicukor", "Drogéria", "Müller") == "Édesség és snack"
    assert CS.besorol("Hegyi széna", "Drogéria", "Müller") == \
        "Drogéria és szépségápolás"
    assert CS.besorol("Weiss Puszedli", "Finomságok & italok", "Müller") == \
        "Édesség és snack"
