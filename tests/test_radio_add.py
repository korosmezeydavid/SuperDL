"""radio: állomás beküldése a radio-browser NYILVÁNOS adatbázisába (M2).
A hálózatot MOCKOLJUK – SOHA nem küldünk be élesben a tesztből."""

import io
import json
from urllib.parse import parse_qs

import pytest

radio = pytest.importorskip("modules_src.radio.radio_mod.radio")


class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def capture(monkeypatch):
    box = {}

    def fake_urlopen(req, timeout=0):
        box["url"] = req.full_url
        box["data"] = req.data.decode("utf-8")
        return _FakeResp(json.dumps(
            {"ok": True, "message": "added", "uuid": "u-1"}).encode())

    monkeypatch.setattr(radio.urllib.request, "urlopen", fake_urlopen)
    return box


def test_add_station_endpoint_es_mezok(capture):
    res = radio.add_station("Teszt Rádió", "https://e.com/s.mp3",
                            country_code="hu", tags="pop, hírek")
    assert capture["url"].endswith("/json/add")
    q = parse_qs(capture["data"])
    assert q["name"] == ["Teszt Rádió"]
    assert q["url"] == ["https://e.com/s.mp3"]
    assert q["countrycode"] == ["HU"]          # ISO nagybetűsítve, 2 karakter
    assert q["tags"] == ["pop, hírek"]
    assert res["ok"] and res["uuid"] == "u-1"


def test_add_station_opcionalis_mezok_kimaradnak(capture):
    radio.add_station("Csak Név", "https://e.com/x")
    q = parse_qs(capture["data"])
    assert "countrycode" not in q and "tags" not in q and "homepage" not in q


def test_add_station_iso_ket_karakter(capture):
    radio.add_station("N", "https://e.com/x", country_code="magyar")
    q = parse_qs(capture["data"])
    assert q["countrycode"] == ["MA"]          # max 2 karakterre vágva
