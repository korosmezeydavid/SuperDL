"""netcheck: a programszintű internet-figyelés őrei.

Egy felhasználó kérte, hogy MINDENHOL, ahol net kell (letöltés, rádió,
frissítés, online hang, AI…), a program AZONNAL, hangosan jelezze, ha nincs
internetkapcsolat – ne fusson hosszú várakozásba vagy kriptikus hibába.
"""

from superdl import netcheck


def test_online_gyorsitotaraz(monkeypatch):
    """Az online() az eredményt rövid ideig gyorsítótárazza (nem próbálgat
    feleslegesen minden hívásnál)."""
    calls = []
    monkeypatch.setattr(netcheck, "_probe", lambda t: (calls.append(1), True)[1])
    netcheck._cache["ts"] = 0.0                   # cache ürítése
    assert netcheck.online() is True
    assert netcheck.online() is True              # ez már a cache-ből jön
    assert len(calls) == 1, "a második hívásnak a gyorsítótárból kell jönnie"


def test_require_online_offline_uzenet(monkeypatch):
    """Offline állapotban kész, érthető magyar üzenetet ad – megnevezve a
    műveletet."""
    monkeypatch.setattr(netcheck, "_probe", lambda t: False)
    netcheck._cache["ts"] = 0.0
    ok, msg = netcheck.require_online("a rádió hallgatásához")
    assert ok is False
    assert "Nincs internetkapcsolat" in msg
    assert "a rádió hallgatásához" in msg


def test_require_online_ok(monkeypatch):
    monkeypatch.setattr(netcheck, "_probe", lambda t: True)
    netcheck._cache["ts"] = 0.0
    ok, msg = netcheck.require_online("a letöltéshez")
    assert ok is True
    assert msg == ""


def test_offline_reason_ketfele_eset(monkeypatch):
    """Megkülönbözteti: egyáltalán nincs net vs. csak a szolgáltatás nem elérhető
    (a felhasználó mindkettőt kérte)."""
    # 1) egyáltalán nincs net
    monkeypatch.setattr(netcheck, "_probe", lambda t: False)
    netcheck._cache["ts"] = 0.0
    code, msg = netcheck.offline_reason("example.com")
    assert code == "no_internet"

    # 2) van net, de a konkrét szolgáltatás nem elérhető
    monkeypatch.setattr(netcheck, "_probe", lambda t: True)
    monkeypatch.setattr(netcheck, "service_reachable", lambda h, p=443, timeout=3: False)
    netcheck._cache["ts"] = 0.0
    code, msg = netcheck.offline_reason("example.com")
    assert code == "service_down"
    assert "működik" in msg


def test_looks_like_offline():
    assert netcheck.looks_like_offline("getaddrinfo failed")
    assert netcheck.looks_like_offline("Max retries exceeded with url")
    assert netcheck.looks_like_offline("Connection refused")
    assert not netcheck.looks_like_offline("HTTP Error 404: Not Found")


def test_friendly_error_offline(monkeypatch):
    """A friendly_error offline állapotban a 'NINCS INTERNETKAPCSOLAT' üzenetet
    adja (nem a régiózár/403 stb. félrevezetőt)."""
    from superdl import media
    monkeypatch.setattr(netcheck, "_probe", lambda t: False)
    netcheck._cache["ts"] = 0.0
    out = media.friendly_error("URLError: <urlopen error [Errno 11001] "
                               "getaddrinfo failed>")
    assert "NINCS INTERNETKAPCSOLAT" in out
