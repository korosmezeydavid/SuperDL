"""A Super Fájlok másolója egyenként viszi a fájlokat, és nem eszi meg a célt."""

import os
import sys

sys.path.insert(0, "modules_src/fajlok")
from fajlok_mod import masolo


def _jel(*_a):
    return None


def test_masolas_mappat_es_fajlt_egyenkent(tmp_path):
    forras = tmp_path / "forras"
    (forras / "belso").mkdir(parents=True)
    (forras / "a.txt").write_text("alma", encoding="utf-8")
    (forras / "belso" / "b.txt").write_bytes(b"x" * (masolo.DARAB + 10))
    cel = tmp_path / "cel"
    jel = masolo.futtat([str(forras)], str(cel), "masol", "felulir", _jel, lambda: False)
    assert jel.kesz and not jel.hibak
    assert (cel / "forras" / "a.txt").read_text(encoding="utf-8") == "alma"
    assert (cel / "forras" / "belso" / "b.txt").stat().st_size == masolo.DARAB + 10
    assert (forras / "a.txt").exists()


def test_athelyezes_torli_a_forrast(tmp_path):
    forras = tmp_path / "egy.txt"
    forras.write_text("körte", encoding="utf-8")
    cel = tmp_path / "cel"
    jel = masolo.futtat([str(forras)], str(cel), "athelyez", "felulir", _jel, lambda: False)
    assert jel.kesz and not jel.hibak
    assert (cel / "egy.txt").read_text(encoding="utf-8") == "körte"
    assert not forras.exists()


def test_utkozes_kihagy_es_uj_nev(tmp_path):
    forras = tmp_path / "nev.txt"
    forras.write_text("uj", encoding="utf-8")
    cel = tmp_path / "cel"
    cel.mkdir()
    (cel / "nev.txt").write_text("regi", encoding="utf-8")
    masolo.futtat([str(forras)], str(cel), "masol", "kihagy", _jel, lambda: False)
    assert (cel / "nev.txt").read_text(encoding="utf-8") == "regi"
    masolo.futtat([str(forras)], str(cel), "masol", "ujnev", _jel, lambda: False)
    assert (cel / "nev (2).txt").read_text(encoding="utf-8") == "uj"


def test_a_cel_nem_lehet_a_forras_belul(tmp_path):
    forras = tmp_path / "fa"
    forras.mkdir()
    (forras / "a.txt").write_text("a", encoding="utf-8")
    cel = forras / "masolat"
    jel = masolo.futtat([str(forras)], str(cel), "masol", "felulir", _jel, lambda: False)
    assert jel.hibak
    assert not (cel / "fa" / "a.txt").exists()


def test_tomorites_es_kibontas(tmp_path):
    from fajlok_mod import csomag
    forras = tmp_path / "konyv.txt"
    forras.write_text("szöveg", encoding="utf-8")
    cel = tmp_path / "csomag.zip"
    csomag.tomorit([str(forras)], str(cel), "zip")
    ki = tmp_path / "ki"
    assert csomag.kibont(str(cel), str(ki)) == 1
    assert (ki / "konyv.txt").read_text(encoding="utf-8") == "szöveg"
    indito, zip_ut, jegyzek = csomag.onkibonto([str(forras)], str(tmp_path / "kuldes"))
    assert os.path.isfile(indito) and os.path.isfile(zip_ut)
    assert "konyv.txt" in open(jegyzek, encoding="utf-8").read()


def test_osszevetes_mondat(tmp_path):
    from fajlok_mod.osszevet import mondat
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "csakitt.txt").write_text("1", encoding="utf-8")
    (a / "mind.txt").write_text("uj", encoding="utf-8")
    (b / "mind.txt").write_text("regi", encoding="utf-8")
    (b / "csakott.txt").write_text("2", encoding="utf-8")
    os.utime(a / "mind.txt", (2_000_000_000, 2_000_000_000))
    szoveg = mondat(str(a), str(b))
    assert "Csak az első helyen: 1" in szoveg
    assert "Csak a másodikon: 1" in szoveg
    assert "nem töröltem" in szoveg


def test_a_helyzet_szazalekot_mond():
    jel = masolo.Jelentes(fajlok=10, bajtok=100, kesz_fajlok=4, kesz_bajtok=40,
                          most="film.mkv", fazis="visz", hatra_mp=125)
    szoveg = jel.helyzet()
    assert "40 százalék" in szoveg
    assert "film.mkv" in szoveg
    assert "perc van hátra" in szoveg
    assert "4 a 10 fájlból" in szoveg


def test_a_felbemaradt_darab_folytatodik(tmp_path):
    forras = tmp_path / "nagy.bin"
    adat = b"abc" * 3000
    forras.write_bytes(adat)
    cel_mappa = tmp_path / "cel"
    cel_mappa.mkdir()
    resz = cel_mappa / "nagy.bin.superdl-resz"
    resz.write_bytes(adat[:1000])
    jel = masolo.futtat([str(forras)], str(cel_mappa), "masol", "felulir",
                        _jel, lambda: False, folytat=True)
    assert jel.kesz and not jel.hibak
    assert (cel_mappa / "nagy.bin").read_bytes() == adat
    assert not resz.exists()


def test_a_kesz_fajlt_folytataskor_kihagyja(tmp_path):
    forras = tmp_path / "egy.txt"
    forras.write_text("régi", encoding="utf-8")
    cel = tmp_path / "cel"
    jel = masolo.futtat(
        [str(forras)], str(cel), "masol", "felulir", _jel, lambda: False,
        keszek=[str(forras)], folytat=True)
    assert jel.fajlok == 0
    assert not (cel / "egy.txt").exists()


def test_megszakitas_a_szamlalas_utan(tmp_path):
    forras = tmp_path / "sok"
    forras.mkdir()
    (forras / "a.txt").write_text("a", encoding="utf-8")
    hivas = {"n": 0}

    def megall():
        hivas["n"] += 1
        return hivas["n"] > 2

    jel = masolo.futtat([str(forras)], str(tmp_path / "cel"), "masol", "felulir",
                        _jel, megall)
    assert jel.megszakitva
    assert os.path.isfile(forras / "a.txt")


def test_fajl_feljebb_masolhato_a_sajat_mappajaba_nem(tmp_path):
    belso = tmp_path / "gyoker" / "belso"
    belso.mkdir(parents=True)
    (belso / "a.txt").write_text("fel", encoding="utf-8")
    fel = masolo.futtat(
        [str(belso / "a.txt")], str(tmp_path / "gyoker"), "masol", "kihagy",
        _jel, lambda: False)
    assert fel.kesz and not fel.hibak
    assert (tmp_path / "gyoker" / "a.txt").read_text(encoding="utf-8") == "fel"
    bent = masolo.futtat(
        [str(belso / "a.txt")], str(belso), "masol", "kihagy", _jel, lambda: False)
    assert bent.hibak
    assert "belsejében" in bent.hibak[0]


def test_beillesztes_oka_es_vagolap_mondat(tmp_path):
    forras = tmp_path / "bal" / "level.txt"
    forras.parent.mkdir()
    forras.write_text("a", encoding="utf-8")
    assert masolo.beillesztes_oka([str(forras)], str(tmp_path / "jobb")) == ""
    assert "ugyanaz a mappa" in masolo.beillesztes_oka([str(forras)], str(forras.parent))
    assert "nincs meg" in masolo.beillesztes_oka([str(tmp_path / "nincs.txt")], str(tmp_path))
    assert "mappába" in masolo.beillesztes_oka([str(forras)], "")
    jel = masolo.Jelentes(fajlok=10, bajtok=100, kesz_fajlok=4, kesz_bajtok=40,
                          most="film.mkv", fazis="visz", hatra_mp=30)
    assert masolo.folyamat_szoveg("masol", jel).startswith("Másolás folyik.")
    assert masolo.folyamat_szoveg("athelyez", jel).startswith("Áthelyezés folyik.")
    mondat = masolo.vagolap_mondat("athelyez", "jobb", "Dokumentumok")
    assert "Kivágás" in mondat
    assert "kész másolat" in mondat
    assert "jobb oldal: Dokumentumok" in mondat
