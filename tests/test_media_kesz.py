# -*- coding: utf-8 -*-
"""media: HAMIS SIKER elleni védelem.

Egy felhasználó (videa.hu, „A massza 1988") jelezte: a program „sikeres"-t
írt, miközben a nagy fájl letöltése megszakadt. Ok: `ignoreerrors: True`
mellett a yt-dlp KIVÉTEL NÉLKÜL ad vissza info-szótárt (metaadat) FÁJL NÉLKÜL,
és a régi `_count_entries` ezt egyedi videónál (1,0)-nak, azaz sikernek vette.
Javítás: egyedi videónál csak akkor „kész", ha a letöltés VALÓBAN befejeződött
(a progress-hook 'finished'-t jelzett, vagy létezik a végső fájl)."""
import pytest

md_mod = pytest.importorskip("superdl.media")


def _md(tmp_path):
    return md_mod.MediaDownloader("http://példa/videó", str(tmp_path))


def test_kesz_a_finished_hook_utan(tmp_path):
    md = _md(tmp_path)
    md._finished = True
    assert md._letoltes_kesz({}) is True


def test_nem_kesz_ha_nincs_fajl(tmp_path):
    """A bug esete: info van (metaadat), de a fájl NEM létezik → NEM kész."""
    md = _md(tmp_path)
    md._finished = False
    info = {"title": "A massza", "requested_downloads":
            [{"filepath": str(tmp_path / "nincs_ilyen.webm")}]}
    assert md._letoltes_kesz(info) is False


def test_nem_kesz_ures_info(tmp_path):
    md = _md(tmp_path)
    md._finished = False
    assert md._letoltes_kesz({}) is False


def test_kesz_ha_letezo_es_nem_ures_fajl(tmp_path):
    md = _md(tmp_path)
    md._finished = False
    f = tmp_path / "kesz.webm"
    f.write_bytes(b"x" * 1000)
    info = {"requested_downloads": [{"filepath": str(f)}]}
    assert md._letoltes_kesz(info) is True


def test_ures_fajl_nem_kesz(tmp_path):
    """A 0 bájtos (üres) fájl sem számít befejezettnek."""
    md = _md(tmp_path)
    md._finished = False
    f = tmp_path / "ures.webm"
    f.write_bytes(b"")
    info = {"requested_downloads": [{"filepath": str(f)}]}
    assert md._letoltes_kesz(info) is False
