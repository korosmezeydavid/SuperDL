# -*- coding: utf-8 -*-
"""Médiakonvertáló: DVD-s VOB-fájlok.

Tesztelői jelzés (2026-08-17): „A média konvertálónál a megjelenített típusok
közé fel kéne venni a .VOB-t is. Ha az összes file-t választom, megjelenik, ki
is lehet választani, és meg is csinálja a konvertálást. Viszont könyvtár
választásnál nem teszi a listába.”

Igaza volt: a MAPPÁBÓL beolvasott fájlokat egy rögzített kiterjesztés-lista
szűrte, és abban nem volt benne a `.vob`. Egyesével a „Minden fájl” szűrővel ki
lehetett választani, ezért ment ott.

Ráadás (a felhasználó kérésére): a DVD a filmet 1 GB-os darabokra vágja
(VTS_01_1.VOB, VTS_01_2.VOB …) – ezeket EGY filmmé fűzzük össze.
"""

import os
import sys

import pytest

sys.path.insert(0, "modules_src/mediatools")
from mediatools_mod import converter as C        # noqa: E402
from mediatools_mod import convertwin as W       # noqa: E402


# ------------------------------------------------------ kiterjesztések

def test_a_vob_bekerult_a_mappaszurobe():
    """EZ A BEJELENTETT HIBA: e nélkül mappából nem került a listába."""
    assert ".vob" in W.MEDIA_EXTS


def test_a_dvd_es_avchd_csalad_is_bent_van():
    for e in (".vob", ".m2v", ".mpg", ".mpeg", ".m2ts", ".mts"):
        assert e in W.MEDIA_EXTS, e


def test_a_fajlvalaszto_szurojeben_is_megjelenik():
    assert "*.vob" in W.MEDIA_WILDCARD


def test_a_kiterjesztesek_kisbetusek_es_ponttal_kezdodnek():
    """A mappa-beolvasás `endswith`-sel szűr kisbetűs néven – egy nagybetűs
    vagy pont nélküli elem CSENDBEN sosem találna semmit."""
    for e in W.MEDIA_EXTS:
        assert e.startswith(".") and e == e.lower()


def test_a_nagybetus_VOB_is_atmegy_a_szuron():
    assert "VTS_01_1.VOB".lower().endswith(W.MEDIA_EXTS)


# --------------------------------------------------- VOB-csoportosítás

def _ut(*reszek):
    return os.path.join("D:\\", *reszek)


def test_a_dvd_darabjai_egy_filmme_allnak_ossze():
    ki = C.vob_csoportok([_ut("VIDEO_TS", "VTS_01_1.VOB"),
                          _ut("VIDEO_TS", "VTS_01_2.VOB"),
                          _ut("VIDEO_TS", "VTS_01_3.VOB")])
    assert len(ki) == 1
    nev, fajlok = ki[0]
    assert nev == "VTS_01" and len(fajlok) == 3


def test_a_darabok_SORRENDBEN_kerulnek_ossze():
    """Fordított sorrendben megadva is a helyes sorrend jöjjön ki – különben a
    film közepe kerülne az elejére."""
    _nev, fajlok = C.vob_csoportok([_ut("VTS_01_3.VOB"), _ut("VTS_01_1.VOB"),
                                    _ut("VTS_01_2.VOB")])[0]
    assert [os.path.basename(f) for f in fajlok] == ["VTS_01_1.VOB",
                                                     "VTS_01_2.VOB",
                                                     "VTS_01_3.VOB"]


def test_a_menu_fajl_kimarad():
    """A `VTS_xx_0.VOB` a DVD MENÜJE – nem a film. Ne kerüljön a filmbe."""
    _nev, fajlok = C.vob_csoportok([_ut("VTS_01_0.VOB"), _ut("VTS_01_1.VOB"),
                                    _ut("VTS_01_2.VOB")])[0]
    assert all("_0.VOB" not in f for f in fajlok) and len(fajlok) == 2


def test_ha_CSAK_menu_van_azt_azert_meghagyjuk():
    """Ne tűnjön el némán az egyetlen fájl, amit a felhasználó hozzáadott."""
    _nev, fajlok = C.vob_csoportok([_ut("VTS_01_0.VOB")])[0]
    assert len(fajlok) == 1


def test_a_kulon_cimek_kulon_filmek():
    ki = C.vob_csoportok([_ut("VTS_01_1.VOB"), _ut("VTS_02_1.VOB")])
    assert [n for n, _f in ki] == ["VTS_01", "VTS_02"]


def test_a_kulon_mappak_nem_keverednek():
    """Két különböző DVD ugyanolyan nevű darabjai NEM egy film."""
    ki = C.vob_csoportok([os.path.join("D:\\a", "VTS_01_1.VOB"),
                          os.path.join("D:\\b", "VTS_01_1.VOB")])
    assert len(ki) == 2


def test_a_tobbi_fajl_valtozatlan_marad():
    ki = C.vob_csoportok([_ut("film.mp4"), _ut("VTS_01_1.VOB"),
                          _ut("zene.mp3")])
    assert [n for n, _f in ki] == ["film", "VTS_01", "zene"]
    assert all(len(f) == 1 for _n, f in ki)


def test_a_sima_vob_nem_csoportosul():
    """Egy `nyaralas.vob` nem DVD-darab – maradjon önálló."""
    ki = C.vob_csoportok([_ut("nyaralas.vob")])
    assert ki == [("nyaralas", [_ut("nyaralas.vob")])]


def test_ures_bemenet():
    assert C.vob_csoportok([]) == [] and C.vob_csoportok(None) == []


# ------------------------------------------------------- concat-lista

def test_a_lista_fajl_az_ffmpeg_formatumaban_keszul(tmp_path):
    ut = C.concat_lista([str(tmp_path / "a.vob"), str(tmp_path / "b.vob")],
                        str(tmp_path))
    sorok = open(ut, encoding="utf-8").read().strip().splitlines()
    assert len(sorok) == 2
    assert all(s.startswith("file '") and s.endswith("'") for s in sorok)


def test_az_aposztrofos_fajlnev_sem_tori_el(tmp_path):
    """Egy „Anyu's video.vob” nevű fájl az idézőjelen belül elrontaná a listát."""
    ut = C.concat_lista([str(tmp_path / "Anyu's video.vob")], str(tmp_path))
    sor = open(ut, encoding="utf-8").read().strip()
    assert r"'\''" in sor


def test_a_parancs_concat_demuxert_hasznal_tobb_darabnal(tmp_path):
    lista = C.concat_lista([str(tmp_path / "a.vob")], str(tmp_path))
    cmd = C.build_command("ffmpeg", "a.vob", "ki.mp4", "video", "mp4", "192",
                          "mpeg2video", "ac3", lista)
    assert "-f" in cmd and "concat" in cmd and lista in cmd
    assert cmd.index("concat") < cmd.index(lista)


def test_egy_darabnal_marad_a_sima_bemenet():
    cmd = C.build_command("ffmpeg", "a.vob", "ki.mp4", "video", "mp4", "192",
                          "mpeg2video", "ac3")
    assert "concat" not in cmd and "a.vob" in cmd


def test_a_mpeg2_videot_ujrakodolja_mp4be():
    """A DVD MPEG-2 videója nem fér bele az MP4-be remuxszal – kódolni kell,
    különben hibás fájl születne."""
    cmd = C.build_command("ffmpeg", "a.vob", "ki.mp4", "video", "mp4", "192",
                          "mpeg2video", "ac3")
    assert "libx264" in cmd and "-c" not in cmd[:-1] or "libx264" in cmd


# ------------------------------------------------ a munkák felépítése

def test_a_converter_elfogadja_a_csoportokat():
    c = C.Converter([("VTS_01", ["a.vob", "b.vob"]), "film.mp4"],
                    out_dir=".", mode="video", fmt="mp4")
    assert len(c.jobs) == 2
    assert c.jobs[0].reszek == ["a.vob", "b.vob"] and c.jobs[0].nev == "VTS_01"
    assert c.jobs[1].reszek is None and c.jobs[1].src == "film.mp4"


def test_egyelemu_csoportnal_nincs_osszefuzes():
    c = C.Converter([("nyaralas", ["nyaralas.vob"])], out_dir=".",
                    mode="video", fmt="mp4")
    assert c.jobs[0].reszek is None, "egy darabnál nincs mit összefűzni"
