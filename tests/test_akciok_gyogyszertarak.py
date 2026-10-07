"""A patikai akcióknál az ár és a boltfajta helyessége számít."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "modules_src" / "akciok"))

from akciok_mod import benu, forrasok, patikaplus  # noqa: E402


def test_benu_akcios_kartya_es_lapozas():
    def lap(nev, ar, regi, path):
        return (f'<div class="product-card">'
                f'<a class="product-card__product-link" href="{path}"></a>'
                f'<h3 class="product-card__title">{nev}</h3>'
                f'<span class="price-item--regular">{regi} Ft helyett</span>'
                f'<span class="price-item--sale">{ar} Ft</span></div>')

    pages = {benu.OLDAL: lap("BENU próba", "2 649", "3 209", "/products/proba"),
             benu.OLDAL + "?page=2": lap("Második", "999", "1 199",
                                         "/products/masodik"),
             benu.OLDAL + "?page=3": "<p>Nincs több termék</p>"}
    found = benu.letolt(pages.__getitem__)
    assert [t.nev for t in found] == ["BENU próba", "Második"]
    assert (found[0].ar, found[0].regi_ar) == (2649, 3209)
    assert found[0].url == "https://benu.hu/products/proba"
    assert benu.termekek(lap("Nem akció", "3000", "2000",
                              "/products/no")) == []
    assert benu.termekek(lap("Külső cím", "999", "1199",
                              "https://example.com/products/no")) == []
    def megszakado(url):
        if "page=2" in url:
            raise TimeoutError("a második oldal nem érhető el")
        return pages[url]
    assert len(benu.letolt(megszakado)) == 1


def test_patikaplus_havi_ajanlat():
    html = ('<div id="patika_row"><div class="termek-item">'
            '<div class="text-center"><a href="/patika/51/acc">'
            '</a><b>ACC 200mg granulátum 30db</b></div>'
            '<div class="text-start"><b>3650 Ft</b><del>4290 Ft</del>'
            '</div></div></div>')
    found = patikaplus.termekek(html)
    assert len(found) == 1
    assert (found[0].ar, found[0].regi_ar) == (3650, 4290)
    assert found[0].url == "https://patikaplus.hu/patika/51/acc"
    assert patikaplus.termekek(html.replace('/patika/51/acc',
                                           '//example.com/patika/51/acc')) == []


def test_gyogyszertar_boltfajta_es_nyitasi_cim():
    ids = [a for a, _n, _f in forrasok.BOLTOK]
    assert ids.count("benu") == ids.count("patikaplus") == 1
    assert forrasok.bolt_fajta("benu") == "gyogyszertar"
    assert forrasok.bolt_fajta("patikaplus") == "gyogyszertar"
    assert ("gyogyszertar", "Minden gyógyszertár") in forrasok.FAJTAK
    assert forrasok.bolt_oldal("benu") == benu.OLDAL
