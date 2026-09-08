# -*- coding: utf-8 -*-
"""Mappaküldés és megosztás (2026-09-06).

A felhasználók kérése: „ha Androidon lehet, akkor itt is lehessen."
Négy dolgot védenek ezek a tesztek, és mind a négy NÉMÁN tudna elromlani.
"""

import sys
import tarfile
import time
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent /
                       "modules_src" / "p2p"))

from p2p_mod import csomag, megosztas, tarhely  # noqa: E402


# ---- 1. csomagolás ----------------------------------------------------

@pytest.fixture
def mappa(tmp_path):
    m = tmp_path / "kuldendo"
    (m / "alkonyvtar").mkdir(parents=True)
    (m / "egy.txt").write_text("egy", encoding="utf-8")
    (m / "alkonyvtar" / "ketto.txt").write_text("kettő" * 100, encoding="utf-8")
    return m


def test_a_mappabol_zip_lesz_es_MINDEN_benne_van(mappa, tmp_path):
    cel = tmp_path / "ki.zip"
    csomag.csomagol(mappa, cel, "zip")
    with zipfile.ZipFile(cel) as zf:
        nevek = {n.replace("\\", "/") for n in zf.namelist()}
    assert "egy.txt" in nevek
    assert "alkonyvtar/ketto.txt" in nevek       # az alkönyvtár is


def test_a_targz_is_megy(mappa, tmp_path):
    cel = tmp_path / "ki.tar.gz"
    csomag.csomagol(mappa, cel, "targz")
    with tarfile.open(cel) as tf:
        nevek = {n.replace("\\", "/") for n in tf.getnames()}
    assert "egy.txt" in nevek and "alkonyvtar/ketto.txt" in nevek


def test_az_ures_mappa_NEM_lesz_ures_zip(tmp_path):
    """Egy üres csomag elküldése a legrosszabb fajta kudarc: úgy néz ki, mintha
    sikerült volna. Inkább szóljunk."""
    ures = tmp_path / "ures"
    ures.mkdir()
    with pytest.raises(ValueError):
        csomag.csomagol(ures, tmp_path / "x.zip", "zip")


def test_a_KIFELE_mutato_hivatkozast_nem_kovetjuk(tmp_path):
    """⚠️ Ha követnénk, a „küldöm ezt a mappát" mozdulatból akaratlanul is egy
    sokkal nagyobb — és magánabb — csomag lenne."""
    titok = tmp_path / "titkos"
    titok.mkdir()
    (titok / "jelszavak.txt").write_text("nem ide való", encoding="utf-8")
    m = tmp_path / "kuldendo2"
    m.mkdir()
    (m / "rendes.txt").write_text("ez mehet", encoding="utf-8")
    try:
        (m / "kifele").symlink_to(titok, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("ezen a gépen nem hozható létre szimbolikus link")
    fajlok, _ = csomag.gyujtes(m)
    nevek = {f.name for f in fajlok}
    assert "rendes.txt" in nevek
    assert "jelszavak.txt" not in nevek


def test_a_gyokeren_KIVULI_utvonal_nem_biztonsagos(tmp_path):
    """A szimbolikus linkes teszt olyan gépen kimarad, ahol nem hozható létre
    link — a védelem viszont ott is kell, ezért a döntést KÖZVETLENÜL is
    ellenőrizzük."""
    gyoker = tmp_path / "gyoker"
    (gyoker / "belso").mkdir(parents=True)
    kint = tmp_path / "kint.txt"
    kint.write_text("nem ide való", encoding="utf-8")
    assert csomag.biztonsagos(gyoker, gyoker / "belso") is True
    assert csomag.biztonsagos(gyoker, kint) is False
    assert csomag.biztonsagos(gyoker, gyoker / ".." / "kint.txt") is False


def test_a_megszakitas_NEM_hagy_felkesz_csomagot(mappa, tmp_path):
    """Egy megszakított művelet után ottfelejtett kétgigás fájl ugyanolyan kár,
    mint amit az MK3-ban javítottunk."""
    cel = tmp_path / "fel.zip"
    with pytest.raises(csomag.Megszakitva):
        csomag.csomagol(mappa, cel, "zip", megall=lambda: True)
    assert not cel.exists()


def test_a_halados_visszahivas_a_VEGERE_szazszazalek(mappa, tmp_path):
    allapotok = []
    csomag.csomagol(mappa, tmp_path / "h.zip", "zip",
                    halad=lambda i, db, b, ossz: allapotok.append((i, db)))
    assert allapotok
    assert allapotok[-1][0] == allapotok[-1][1]      # hányadik == hányból


def test_az_ideiglenes_csomag_NEM_a_mappa_melle_kerul(mappa):
    """Windowson egy négygigás zip csendben megenné a lemezt."""
    ut = csomag.csomag_utvonal(mappa, "zip", ideiglenes=True)
    assert ut.parent != Path(mappa).parent
    assert ut.name.endswith(".zip")


def test_a_formatum_rossz_indexnel_a_ZIP(mappa):
    assert csomag.formatum_id(99) == "zip"
    assert csomag.formatum_id(-1) == "zip"


# ---- 2. tárhelyek ------------------------------------------------------

def test_a_meret_SZURI_a_tarhelyeket():
    kicsi = tarhely.valaszthatok(50 * tarhely.MB)
    nagy = tarhely.valaszthatok(3 * tarhely.GB)
    assert len(kicsi) > len(nagy)
    assert all(3 * tarhely.GB <= t.max_meret for t in nagy)


def test_a_tul_nagy_fajlnal_NEM_marad_tarhely():
    assert tarhely.valaszthatok(100 * tarhely.GB) == []


def test_a_HTML_valaszbol_NEM_szedunk_ki_linket():
    """⚠️ EZ A MÉRÉS LEGFONTOSABB TANULSÁGA (2026-09-08).

    A file.io 200-as kóddal egy teljes weboldalt adott vissza (megszűnt az
    ingyenes API-ja), a link-kinyerőnk pedig kiszedte belőle az első URL-t —
    egy háttérképet — és a program SIKERT jelentett egy értelmetlen linkkel.
    A felhasználó ezt kimásolta és elküldte volna valakinek."""
    html = ('<html>\n<head>\n<meta charset="utf-8">\n'
            '<meta content="https://www.file.io/images/og-img.png">\n</head>')
    assert tarhely.talalt_link(html) == ""


def test_a_kepek_es_stiluslapok_nem_letoltesi_linkek():
    assert tarhely.talalt_link("https://pelda.hu/kep.png") == ""
    assert tarhely.talalt_link("https://pelda.hu/stilus.css") == ""
    assert tarhely.talalt_link("https://pelda.hu/fajl.zip") == \
        "https://pelda.hu/fajl.zip"


def test_a_temp_sh_nyers_URL_valasza_ATMEGY():
    """⚠️ A temp.sh `text/html` fejlécet küld, a törzse mégis egy nyers URL.
    Ezért a válasz ALAKJÁRA nézünk, nem a fejlécére – ha a Content-Type
    alapján döntenénk, a temp.sh-t kizárnánk."""
    assert tarhely.talalt_link("https://temp.sh/OqGDZ/teszt.txt\n") == \
        "https://temp.sh/OqGDZ/teszt.txt"


def test_a_JSON_ami_nem_tartalmaz_linket_URES_marad():
    """Ne találgassunk: ha a gépi válaszban nincs link, az kudarc."""
    assert tarhely.talalt_link('{"success":false,"error":"tul nagy"}') == ""


def test_az_uguu_valasza_is_erthetо():
    valasz = ('{"success":true,"files":[{"hash":"abc",'
              '"url":"https://h.uguu.se/rWaWJqJd.txt"}]}')
    assert tarhely.talalt_link(valasz) == "https://h.uguu.se/rWaWJqJd.txt"


def test_a_HALOTT_tarhelyek_KIKERULTEK():
    """Élesben mérve (2026-09-08): a 0x0.st 503-at ad („uploads disabled"),
    a bashupload.com tartománya nem oldható fel, a file.io HTML-t küld.
    Ha bármelyik visszakerülne mérés nélkül, ez a teszt szóljon."""
    idk = {t.id for t in tarhely.TARHELYEK}
    assert "zerox" not in idk
    assert "bashupload" not in idk
    assert "fileio" not in idk


def test_a_rovid_elettartam_ORABAN_hangzik():
    """A „0,125 napig" kimondva értelmetlen – és épp a legfontosabb esetnél
    (uguu: 3 óra) fordulna elő."""
    assert tarhely.emberi_nap(3 / 24) == "3 óráig"
    assert tarhely.emberi_nap(1) == "egy napig"


def test_az_EGYSZERI_letoltest_kimondjuk():
    """Ez a legkellemetlenebb meglepetés: ha a címzett véletlenül kétszer
    kattint, másodszorra már nincs ott a fájl."""
    for t in tarhely.TARHELYEK:
        if t.egyszeri:
            assert "EGYSZER" in tarhely.leiras(t)
            assert "EGYSZER" in tarhely.megerosito_kerdes(t, "a.zip", 1000)


def test_a_figyelmeztetes_a_p2p_fele_IS_iranyit():
    """Jelszó nincs (tudatos döntés) — ezért a figyelmeztetés nem tiltás,
    hanem útbaigazítás."""
    assert "jelszó" in tarhely.FIGYELMEZTETES
    assert "gépről gépre" in tarhely.FIGYELMEZTETES


def test_a_wormhole_app_NINCS_a_listaban():
    """Nincs nyilvános API-ja — egy „egy mozdulattal feldobom" gomb nem
    építhető rá. Ha valaha bekerülne, ez a teszt szóljon."""
    nevek = {t.nev for t in tarhely.TARHELYEK}
    assert not any("wormhole.app" in n for n in nevek)


def test_a_meret_tizedesVESSZOVEL_hangzik():
    assert "," in tarhely.emberi_meret(int(1.5 * tarhely.MB))
    assert "." not in tarhely.emberi_meret(int(1.5 * tarhely.MB))


@pytest.mark.parametrize("valasz,vart", [
    ('{"link":"https://pelda.hu/abc.zip"}', "https://pelda.hu/abc.zip"),
    ('https://x0.at/WOCF.txt\n', "https://x0.at/WOCF.txt"),
    ('{"data":{"url":"https://tmpfiles.org/1/a"}}', "https://tmpfiles.org/1/a"),
    ('semmi hasznos', ""),
])
def test_a_linket_haromfele_valaszbol_is_kiszedjuk(valasz, vart):
    assert tarhely.talalt_link(valasz) == vart


def test_a_hibakod_TEENDOT_mond_nem_szamot():
    uzenet = tarhely.hibauzenet(413, "file.io")
    assert "413" not in uzenet
    assert "gépről gépre" in uzenet          # megmondja, mit tegyen helyette


def test_az_ismeretlen_hibakodnal_marad_a_nyers_szam():
    """Kitalált magyarázatot nem adunk (MK6 elve)."""
    assert "418" in tarhely.hibauzenet(418, "valami")


# ---- 3. előzmények -----------------------------------------------------

def _tetel(lejar_mulva, **kw):
    t = {"nev": "a.zip", "link": "https://x/1", "tarhely": "fileio",
         "tarhely_nev": "file.io", "meret": 10, "kuldve": time.time(),
         "lejar": time.time() + lejar_mulva, "egyszeri": False,
         "torolheto": False}
    t.update(kw)
    return t


def test_LEJARAT_szerint_rendez_elol_ami_hamarabb_tunik_el():
    tetelek = [_tetel(5 * 86400), _tetel(3600), _tetel(2 * 86400)]
    sorrend = megosztas.lathatoak(tetelek)
    assert [t["lejar"] for t in sorrend] == sorted(t["lejar"] for t in sorrend)


def test_a_lejart_sor_MEG_EGY_NAPIG_latszik():
    """Aki tegnap küldött egy linket, és ma nem érti, miért nem működik,
    annak ez a válasz. Némán eltüntetve nem lenne felelet a kérdésére."""
    tegnap_jart_le = _tetel(-3600)
    reg_lejart = _tetel(-5 * 86400)
    lathato = megosztas.lathatoak([tegnap_jart_le, reg_lejart])
    assert tegnap_jart_le in lathato
    assert reg_lejart not in lathato


def test_a_lejart_sor_LEJART_ot_mond():
    assert megosztas.hatralevo_ido(_tetel(-10)) == "LEJÁRT"


def test_az_ido_EMBERI_nem_idobelyeg():
    # rögzített „most", különben a másodperc-csúszás miatt billegne
    most = 1_000_000.0
    tetel = {"lejar": most + 2 * 86400 + 4 * 3600}
    szoveg = megosztas.hatralevo_ido(tetel, most)
    assert szoveg == "még 2 nap és 4 óra"
    assert ":" not in szoveg


def test_a_lejarat_LEFELE_kerekit_soha_nem_igerunk_tobb_idot():
    """Ha többet mondanánk a valóságnál, a felhasználó azt hinné, van még
    ideje – és pont akkor veszítené el a linket, amikor számít rá."""
    most = 1_000_000.0
    # 3 óra 59 perc van hátra – ez NEM lehet „4 óra"
    tetel = {"lejar": most + 3 * 3600 + 59 * 60}
    assert megosztas.hatralevo_ido(tetel, most) == "még 3 óra és 59 perc"


def test_a_sor_torlese_KIMONDJA_hogy_a_fajl_marad():
    """Egy „törölve" felirat olyasmiről, ami továbbra is elérhető, hamis
    biztonságérzet."""
    for torolheto in (True, False):
        mondat = megosztas.sor_torles_mondat(_tetel(3600, torolheto=torolheto))
        assert "MARAD" in mondat


def test_a_link_betuzese_megnevezi_az_irasjeleket():
    b = megosztas.betuzve("a.b/c")
    assert "pont" in b and "per jel" in b
