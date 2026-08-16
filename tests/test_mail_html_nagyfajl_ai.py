# -*- coding: utf-8 -*-
"""Super Mail: HTML-levél, nagy fájlok és AI-levélírás.

Felhasználói kérések (2026-08-16):
  • támogassa a HTML-t, legyen beszúrható hivatkozás (nem kötelező magyarázó
    szöveggel), kép és videó-hivatkozás;
  • a 25 MB fölötti fájl menjen fel egy megosztóra, és a link kerüljön a levélbe;
  • legyen AI-levélírás hangnem- és hossz-választással, AI-kulccsal.

Egyetlen hálózati kérést sem küldünk: a feltöltés és az AI-hívás is helyben,
mockolva fut.
"""

import email
import os
import sys

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import ailevel as AI            # noqa: E402
from mail_mod import mail_core as MC          # noqa: E402


# --------------------------------------------------------------- HTML

def test_hivatkozas_mindket_valtozatban_hasznalhato():
    """A HTML-ben kattintható, a SIMA szövegben pedig ott a teljes cím – a
    vak címzett levelezője gyakran a szöveges részt mutatja."""
    t = "A fájl [itt éred el](https://pelda.hu/a.zip) ma."
    assert MC.jelolesek_szovegge(t) == "A fájl itt éred el: https://pelda.hu/a.zip ma."
    assert '<a href="https://pelda.hu/a.zip">itt éred el</a>' in MC.jelolesek_htmlbe(t)


def test_magyarazo_szoveg_nem_kotelezo():
    t = "Nézd meg: [](https://pelda.hu)"
    assert "https://pelda.hu" in MC.jelolesek_szovegge(t)
    assert '>https://pelda.hu</a>' in MC.jelolesek_htmlbe(t)


def test_a_html_nem_engedi_at_a_karos_jeloleseket():
    """Amit a felhasználó ír, az SZÖVEG – nem HTML. Ha valaki `<script>`-et
    gépel a levelébe, az ne váljon kóddá a címzettnél."""
    html = MC.jelolesek_htmlbe("<script>rossz()</script> & társai")
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "&amp;" in html


def test_csak_akkor_html_ha_van_mit():
    assert MC.van_html_jeloles("sima szöveg, semmi extra") is False
    assert MC.van_html_jeloles("[x](https://a.hu)") is True
    assert MC.van_html_jeloles("[kép: a.png]") is True


def test_a_kepnek_van_alt_szovege():
    """A képnek MINDIG legyen alternatív szövege: a vak címzett ezt hallja."""
    html = MC.jelolesek_htmlbe("[kép: naplemente.png]",
                               {"naplemente.png": "kep1@superdl"})
    assert 'alt="naplemente.png"' in html and 'src="cid:kep1@superdl"' in html


def test_hianyzo_kep_eseten_marad_a_szoveges_jeloles():
    assert "[kép: nincs.png]" in MC.jelolesek_htmlbe("[kép: nincs.png]", {})


def test_a_level_szerkezete_szabvanyos(tmp_path):
    kep = tmp_path / "k.png"
    kep.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
    csat = tmp_path / "irat.pdf"
    csat.write_bytes(b"%PDF-1.4 teszt")
    msg = MC.level_epit_html("en@x.hu", "te@y.hu", "Tárgy",
                             "Szia!\n[kép: k.png]\n[link](https://a.hu)",
                             csatolmanyok_lista=[str(csat)], kepek=[str(kep)])
    tipusok = [r.get_content_type() for r in msg.walk()]
    assert "text/plain" in tipusok and "text/html" in tipusok
    assert "image/png" in tipusok and "application/pdf" in tipusok
    # a kép a HTML-hez tartozik (related), nem külön csatolmányként lóg
    assert "multipart/related" in tipusok
    nyers = msg.as_bytes()
    assert b"te@y.hu" in nyers and len(nyers) > 200


# ---------------------------------------------------------- nagy fájl

def test_a_kodolt_meret_a_mervado(tmp_path):
    """A 25 MB nem a fájl, hanem a KÓDOLT levél mérete: a base64 kb. 33%-kal
    hizlal, ezért egy 20 MB-os fájl már nem fér bele egy 25 MB-os korlátba."""
    f = tmp_path / "nagy.bin"
    f.write_bytes(b"x" * (20 * 1024 * 1024))
    meret = MC.becsult_meret("szia", [str(f)])
    assert meret > 25 * 1024 * 1024
    assert 26 < meret / 1024 / 1024 < 28


def test_hianyzo_fajl_nem_dont_el_mindent(tmp_path):
    assert MC.becsult_meret("szia", [str(tmp_path / "nincs.bin")]) > 0


def test_meret_szoveg_emberi():
    assert MC.meret_szoveg(30 * 1024 * 1024) == "30.0 megabájt"
    assert "kilobájt" in MC.meret_szoveg(4096)


def test_a_link_jelolessel_kerul_a_levelbe():
    """Így a HTML-változatban kattintható lesz, a szövegesben meg ott a cím."""
    sz = MC.nagy_fajl_szoveg([{"nev": "film.mp4",
                               "url": "https://filebin.net/abc",
                               "lejar": "2026-08-23"}])
    assert "[film.mp4](https://filebin.net/abc)" in sz
    assert "2026-08-23" in sz, "a lejáratot is közöljük, hogy ne érje meglepetés"
    assert MC.van_html_jeloles(sz)


def test_a_feltoltes_egyedi_bin_nevet_hasznal(tmp_path, monkeypatch):
    """Két feltöltés SOSEM kerülhet ugyanabba a nyilvános tárolóba."""
    f = tmp_path / "a.txt"
    f.write_bytes(b"adat")
    hivott = []

    class _Valasz:
        status = 201

        def read(self):
            return b'{"bin": {"expired_at": "2026-08-23T00:00:00Z"}}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def hamis_open(keres, timeout=0):
        hivott.append(keres.full_url)
        return _Valasz()

    monkeypatch.setattr("urllib.request.urlopen", hamis_open)
    a = MC.megoszto_feltolt(str(f))
    b = MC.megoszto_feltolt(str(f))
    assert a["url"] != b["url"], "külön bin kell, különben összekeverednének"
    assert a["lejar"] == "2026-08-23"
    assert all(u.startswith("https://filebin.net/superdl-") for u in hivott)


def test_a_fajlnev_biztonsagos_lesz_az_urlben(tmp_path, monkeypatch):
    f = tmp_path / "ékezetes név & jel.txt"
    f.write_bytes(b"adat")
    cimek = []
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda k, timeout=0: cimek.append(k.full_url) or
                        type("V", (), {"read": lambda s: b"{}",
                                       "__enter__": lambda s: s,
                                       "__exit__": lambda s, *a: False})())
    ki = MC.megoszto_feltolt(str(f))
    assert " " not in cimek[0] and "&" not in cimek[0]
    assert ki["nev"] == "ékezetes név & jel.txt", "a felhasználónak az EREDETI nevet mondjuk"


# ------------------------------------------------------------------ AI

def test_a_prompt_tartalmazza_a_valasztasokat():
    p = AI.prompt_epit("lemondom a keddi időpontot", "Anna", "hivatalos",
                       "magazo", "hosszu")
    assert "Anna" in p and "lemondom a keddi időpontot" in p
    assert "hivatalos" in p and "Ön-forma" in p
    assert "2000–3000 karakter" in p


def test_a_valasz_levelre_atadja_az_eredetit_de_csak_ha_kertek():
    van = AI.prompt_epit("válasz", eredeti="Eredeti levél szövege")
    nincs = AI.prompt_epit("válasz", eredeti="")
    assert "Eredeti levél szövege" in van
    assert "válaszolunk" not in nincs


def test_a_pontositas_atadja_a_korabbi_valtozatot():
    p = AI.prompt_epit("x", pontositas="legyen rövidebb", elozo="A régi szöveg")
    assert "A régi szöveg" in p and "legyen rövidebb" in p


def test_a_rendszer_utasitas_tiltja_a_markdownt_es_az_alairast():
    assert "Markdown" in AI.RENDSZER
    assert "Aláírást NE" in AI.RENDSZER, \
        "az aláírást a program teszi hozzá, nem az AI"


@pytest.mark.parametrize("nyers,elvart", [
    ('"Kedves Anna!"', "Kedves Anna!"),
    ("**Kedves Anna!**", "Kedves Anna!"),
    ("Tárgy: valami\n\nKedves Anna!", "Kedves Anna!"),
    ("* első\n* második", "első\nmásodik"),
    ('"""Szöveg"""', "Szöveg"),
])
def test_a_valasz_megtisztitasa(nyers, elvart):
    """A csillagokat és a jelöléseket a képernyőolvasó FELOLVASNÁ – ezért ki."""
    assert AI.valasz_tisztit(nyers) == elvart


def test_a_hosszhatarok_ertelmesek():
    kulcsok = [k for k, _n, _a, _b in AI.HOSSZAK]
    assert kulcsok == ["rovid", "kozepes", "hosszu"]
    elozo = 0
    for _k, _n, mini, maxi in AI.HOSSZAK:
        assert mini < maxi and mini > elozo
        elozo = mini


def test_a_targy_javaslat_egysoros():
    assert "\n" not in AI.targy_tisztit("Keddi időpont\nmásodik sor")
    assert len(AI.targy_tisztit("x" * 300)) <= 120
