# -*- coding: utf-8 -*-
"""MK7 – a link-bevitel: közös felismerő, kérdés-küszöb, parancssori hivatkozás.

A kör lényege, hogy a programba HÁROM úton bekerülő link ugyanazt a kezelést
kapja. Ezek a tesztek azt védik, hogy a három út ne csússzon szét megint.
"""

from superdl import linkek


# ---- felismerés -------------------------------------------------------

def test_egyszeru_linkek():
    assert linkek.kigyujt("https://a.hu/x") == ["https://a.hu/x"]
    assert linkek.kigyujt("http://a.hu/x") == ["http://a.hu/x"]


def test_magnet_is_link():
    """A `magnet:` NEM a szokásos URL-alak (nincs `//`), ezért a naiv
    séma-ellenőrzések kihagyják."""
    m = "magnet:?xt=urn:btih:0123456789abcdef"
    assert linkek.kigyujt(m) == [m]


def test_egy_sorban_TOBB_link():
    """A vágólap-figyelő eddig soronként gondolkodott – egy chat-üzenet vagy
    egy e-mail bekezdés viszont bőven adhat kettőt egy sorban."""
    sz = "nézd meg https://a.hu/1 meg ezt is https://b.hu/2 kösz"
    assert linkek.kigyujt(sz) == ["https://a.hu/1", "https://b.hu/2"]


def test_a_mondatvegi_pont_nem_ragad_a_linkbe():
    """Ha egy mondat végéről másolnak linket, a pont a linkbe ragadna, és a
    letöltés 404-re futna – a felhasználó meg nem értené, hisz a böngészőben
    működik."""
    assert linkek.kigyujt("itt van: https://a.hu/x.") == ["https://a.hu/x"]
    assert linkek.kigyujt("(https://a.hu/y)") == ["https://a.hu/y"]
    assert linkek.kigyujt("„https://a.hu/z”") == ["https://a.hu/z"]


def test_a_valodi_zarojel_a_linkben_marad():
    """A Wikipédia-linkekben VALÓDI zárójel van: …_(film). Ezt levágni
    elrontaná a linket."""
    u = "https://hu.wikipedia.org/wiki/Vuk_(film)"
    assert linkek.kigyujt(u) == [u]


def test_duplikatum_egyszer_de_a_sorrend_marad():
    sz = "https://b.hu/2 https://a.hu/1 https://b.hu/2"
    assert linkek.kigyujt(sz) == ["https://b.hu/2", "https://a.hu/1"]


def test_tobbsoros_szoveg():
    """EZ A KÖR LÉNYEGE: a vágólap-figyelő eddig egy külön feltétellel
    (`"\\n" not in text`) SZÁNDÉKOSAN eldobta a többsoros szöveget."""
    sz = "https://a.hu/1\nhttps://b.hu/2\nhttps://c.hu/3"
    assert len(linkek.kigyujt(sz)) == 3


def test_a_nem_link_kimarad():
    assert linkek.kigyujt("csak sima szöveg, semmi link") == []
    assert linkek.kigyujt("ftp://a.hu/x") == []
    assert linkek.kigyujt("") == []


def test_torrent_utvonal_CSAK_ha_letezik(tmp_path):
    """A `.torrent` kiterjesztés önmagában nem elég: egy ELÍRT név is így
    végződhet, és akkor a program egy nem létező fájlt próbálna letölteni."""
    van = tmp_path / "film.torrent"
    van.write_bytes(b"d8:announce")
    assert linkek.kigyujt(str(van)) == [str(van)]
    nincs = tmp_path / "elirt.torrent"
    assert linkek.kigyujt(str(nincs)) == []


def test_szokozos_torrent_utvonal(tmp_path):
    """A Windowsos fájlnevekben SZÓKÖZ van – a szóköz menti darabolás
    szétvágná az útvonalat."""
    f = tmp_path / "a nagy film.torrent"
    f.write_bytes(b"d8:announce")
    assert linkek.kigyujt(str(f)) == [str(f)]


# ---- ami már a sorban van --------------------------------------------

def test_a_mar_sorban_levok_kimaradnak():
    """A vágólap-figyelő másodpercenként néz rá a vágólapra – a felhasználó
    pedig nem törli ki onnan a linket csak azért, mert egyszer letöltötte."""
    uj = linkek.ujak(["https://a.hu/1", "https://b.hu/2"], ["https://a.hu/1"])
    assert uj == ["https://b.hu/2"]


def test_a_mar_sorban_levok_kis_nagybetutol_fuggetlenul():
    assert linkek.ujak(["HTTPS://A.HU/1"], ["https://a.hu/1"]) == []


# ---- a kérdés ---------------------------------------------------------

def test_egy_linknel_nem_kerdezunk():
    """Ez a mai, megszokott viselkedés – nem vesszük el a felhasználótól."""
    assert not linkek.kerdezzunk(1)
    assert not linkek.kerdezzunk(0)


def test_kettotol_kerdezunk():
    """EZ A FELTÉTELE annak, hogy a többsoros bevitelt bevezethessük: némán
    harminc letöltést indítani vakon ijesztő és nehezen visszacsinálható."""
    assert linkek.kerdezzunk(2)
    assert linkek.kerdezzunk(30)


def test_a_kerdes_kimondja_a_darabszamot_es_az_elsot():
    sz = linkek.kerdes_szoveg(["https://a.hu/1", "https://b.hu/2"])
    assert "2 hivatkozást" in sz
    assert "https://a.hu/1" in sz


def test_a_kerdes_nem_zudit_ra_egy_vegtelen_linket():
    hosszu = "https://a.hu/" + "x" * 300
    sz = linkek.kerdes_szoveg([hosszu, "https://b.hu"])
    assert "…" in sz
    assert len(sz) < 300


# ---- parancssori hivatkozás (társítás, magnet-kezelő) -----------------

def test_a_magnet_argumentum_megjon():
    """EDDIG NÉMÁN ELVESZETT: a program `os.path.isfile()` szűrővel kereste az
    argumentumot, amin egy magnet-link nem megy át. A felhasználó kattint a
    böngészőben, elindul a program, és nem történik SEMMI."""
    m = "magnet:?xt=urn:btih:abc"
    assert linkek.letoltendo(["SuperDL.exe", m]) == m


def test_a_torrent_argumentum_megjon(tmp_path):
    f = tmp_path / "x.torrent"
    f.write_bytes(b"d")
    assert linkek.letoltendo(["SuperDL.exe", str(f)]) == str(f)


def test_a_kapcsolok_kimaradnak():
    assert linkek.letoltendo(["SuperDL.exe", "--wh", "--assoc-on"]) == ""


def test_mediafajl_NEM_letoltendo(tmp_path):
    """A médiafájl a lejátszóé, nem a letöltési soré – a kettő szétválasztása
    a lényeg, különben egy dupla kattintás rossz ablakot nyitna."""
    f = tmp_path / "dal.mp3"
    f.write_bytes(b"ID3")
    assert linkek.letoltendo(["SuperDL.exe", str(f)]) == ""


def test_ures_argumentumlista():
    assert linkek.letoltendo([]) == ""
    assert linkek.letoltendo(["SuperDL.exe"]) == ""
