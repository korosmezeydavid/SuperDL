"""Tóth László (2026-09-24): újraindulás után az aria2 öt percnél tovább
ellenőrizte a nagy fájlokat, és mind az öt seedelő torrent „1 sikertelen
próbát" kapott. Ha a motor folyamata él, türelmesebbek vagyunk."""
import types

from superdl.torrent import TorrentDownloader


def _td(client):
    td = TorrentDownloader.__new__(TorrentDownloader)
    td.client = client
    return td


def test_elo_motornal_fel_orat_var():
    td = _td(types.SimpleNamespace(alive=lambda: True))
    assert td._vezerles_tures() == TorrentDownloader.VEZERLES_TURES_ELO_MP
    assert td._vezerles_tures() >= 1800


def test_halott_motornal_marad_az_ot_perc():
    td = _td(types.SimpleNamespace(alive=lambda: False))
    assert td._vezerles_tures() == TorrentDownloader.VEZERLES_TURES_MP == 300


def test_ismeretlen_kliensnel_is_ot_perc():
    assert _td(None)._vezerles_tures() == 300

    def rossz():
        raise OSError("nincs")
    assert _td(types.SimpleNamespace(alive=rossz))._vezerles_tures() == 300
