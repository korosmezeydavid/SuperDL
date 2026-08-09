# -*- coding: utf-8 -*-
"""Átjáró – a wx-mentes mag tesztjei (hálózat nélkül)."""
import json

import pytest

AC = pytest.importorskip("modules_src.atjaro.atjaro_mod.atjaro_core")


def test_portal_url():
    assert AC.portal_url("192.168.0.20") == "http://192.168.0.20:8080"
    assert AC.portal_url("192.168.0.20", 9090) == "http://192.168.0.20:9090"
    # ha az egész címet bemásolják, elfogadjuk
    assert AC.portal_url("http://10.0.0.5:8080/") == "http://10.0.0.5:8080"
    assert AC.portal_url("  10.0.0.7  ") == "http://10.0.0.7:8080"


def test_dest_konstansok():
    assert AC.DEST_ZENE == "music"
    assert AC.DEST_KONYV == "documents"


def test_backup_gyogyszer_kigyujtes():
    backup = {"files": {"superdl": {
        "medication_reminders": {"t": "s", "v": json.dumps([
            {"id": 1, "name": "Aszpirin", "hour": 8, "minute": 0,
             "cycleType": "DAILY", "enabled": True}])}}}}
    gy = AC.kigyujt_gyogyszerek(backup)
    assert len(gy) == 1 and gy[0]["name"] == "Aszpirin"


def test_backup_konyvpozicio_kigyujtes():
    backup = {"files": {"superdl": {
        "book_positions": {"t": "s", "v": json.dumps(
            {"/storage/Konyvek/regeny.epub": 12345})}}}}
    poz = AC.kigyujt_konyv_poziciok(backup)
    assert poz.get("/storage/Konyvek/regeny.epub") == 12345


def test_backup_ures_esetek():
    assert AC.kigyujt_gyogyszerek({}) == []
    assert AC.kigyujt_konyv_poziciok({}) == {}
    assert AC.kigyujt_gyogyszerek({"files": {"superdl": {}}}) == []


def test_gyogyszer_aktivak_szur():
    gyok = [
        {"name": "A", "enabled": True},
        {"name": "B", "enabled": False},
        {"name": "C"},                       # mező nélkül -> aktív
        "hulladek",                          # nem dict -> kihagyva
    ]
    aktiv = AC.gyogyszer_aktivak(gyok)
    assert [g["name"] for g in aktiv] == ["A", "C"]


def test_gyogyszer_esemeny_adat():
    g = {"name": "Aszpirin", "hour": 8, "minute": 5, "cycleType": "DAILY"}
    d = AC.gyogyszer_esemeny_adat(g, "2026-08-09")
    assert d["title"] == "Aszpirin"
    assert d["date"] == "2026-08-09"
    assert d["time"] == "08:05"
    assert d["repeat"] == "daily"
    assert "szinkroniz" in d["note"].lower()
    # nem napi ciklus -> nincs ismétlés; hiányzó név -> alapértelmezett
    d2 = AC.gyogyszer_esemeny_adat({"hour": 20, "cycleType": "ONCE"}, "2026-08-09")
    assert d2["time"] == "20:00" and d2["repeat"] == "none"
    assert d2["title"] == "Gyógyszer"
    # hibás/kilógó érték -> becsípve, nem hasal el
    d3 = AC.gyogyszer_esemeny_adat({"name": "X", "hour": "??", "minute": 99},
                                   "2026-08-09")
    assert d3["time"] == "00:59"


def test_konyv_egyezes_fajlnev_szerint():
    poz = {"/storage/Konyvek/regeny.epub": 48000,
           "/storage/Konyvek/csak_telefon.txt": 100}
    pc = [r"C:\Users\msn\Books\REGENY.EPUB",       # más út, más kis/nagybetű
          r"C:\Users\msn\Books\masik.pdf"]
    egy = AC.konyv_egyezes(poz, pc)
    d = {r["nev"]: r for r in egy}
    assert d["regeny.epub"]["pc_ut"] == r"C:\Users\msn\Books\REGENY.EPUB"
    assert d["regeny.epub"]["telefon_offset"] == 48000
    assert d["csak_telefon.txt"]["pc_ut"] is None


def test_ical_url_valido():
    # példa (nem valódi) Google iCal-cím
    jo = ("https://calendar.google.com/calendar/ical/"
          "pelda%40gmail.com/private-abc123/basic.ics")
    assert AC.ical_url_ok(jo)
    assert AC.ical_url_ok("webcal://example.com/naptar.ics")   # webcal is jó
    assert not AC.ical_url_ok("http://pelda.hu/oldal.html")
    assert not AC.ical_url_ok("csak valami szoveg")
    assert not AC.ical_url_ok("")


def test_ical_url_normalizal():
    assert AC.normalizal_ical_url("  webcal://x.com/a.ics ") == \
        "https://x.com/a.ics"
    assert AC.normalizal_ical_url("https://x.com/a.ics") == "https://x.com/a.ics"


def test_naptar_nev_javaslat_nem_szivarogtat_titkot():
    url = ("https://calendar.google.com/calendar/ical/"
           "pelda%40gmail.com/private-TITKOS123/basic.ics")
    nev = AC.naptar_nev_javaslat(url)
    assert "pelda@gmail.com" in nev          # az e-mail olvasható
    assert "TITKOS123" not in nev            # a titkos rész NEM
    assert AC.naptar_nev_javaslat("https://x.com/a.ics") == \
        "Telefon naptár (Google)"


def test_konyvjelzo_android_be():
    android = [{"id": 3, "bookPath": "/storage/emulated/0/Konyvek/regeny.epub",
                "bookTitle": "Egy regény", "charOffset": 1234,
                "preview": "Valamikor régen…", "createdAt": 1700000000000},
               "szemét"]
    be = AC.android_konyvjelzo_be(android)
    assert len(be) == 1
    r = be[0]
    assert r["book"] == "regeny.epub" and r["title"] == "Egy regény"
    assert r["char"] == 1234 and r["created"] == 1700000000000
    assert r["preview"].startswith("Valamikor")


def test_konyvjelzo_pc_androidra_odavissza():
    pc = [{"book": "regeny.epub", "title": "Egy regény", "char": 1234,
           "preview": "Valamikor régen…", "created": 1700000000000, "label": ""}]
    a = AC.pc_konyvjelzo_androidra(pc)
    assert a[0]["bookPath"] == "regeny.epub"
    assert a[0]["charOffset"] == 1234
    assert a[0]["createdAt"] == 1700000000000
    # oda-vissza: az azonosító mezők megmaradnak
    vissza = AC.android_konyvjelzo_be(a)
    assert vissza[0]["book"] == "regeny.epub"
    assert vissza[0]["created"] == 1700000000000


class _FakeResp:
    def __init__(self, json_data=None, text="ok", status=200):
        self._json = json_data
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if self._json is None:
            raise ValueError("nincs json")
        return self._json


class _FakeRequests:
    def __init__(self):
        self.calls = []

    def post(self, url, params=None, data=None, files=None, json=None, timeout=None):
        self.calls.append({"m": "POST", "url": url, "data": data,
                           "files": files, "json": json})
        return _FakeResp(text="Feltöltve")

    def get(self, url, params=None, timeout=None):
        self.calls.append({"m": "GET", "url": url})
        if url.endswith("/sync/books"):
            return _FakeResp(json_data={"books": ["regeny.epub"],
                                        "audiobooks": ["Sorozat"]})
        return _FakeResp(json_data={})


def test_mappa_fajljai_csak_hang(tmp_path):
    (tmp_path / "01.mp3").write_bytes(b"")
    (tmp_path / "02.flac").write_bytes(b"")
    (tmp_path / "borito.jpg").write_bytes(b"")
    (tmp_path / "olvass.txt").write_text("x", encoding="utf-8")
    hang = [__import__("os").path.basename(p)
            for p in AC._mappa_fajljai(str(tmp_path), csak_hang=True)]
    assert hang == ["01.mp3", "02.flac"]


def test_feltolt_subdir_atengedi_a_beagyazast(tmp_path, monkeypatch):
    # a PC a TELJES relatív almappát átküldi (a biztonság a telefon oldalán van);
    # csak a széli perjeleket vágja, a backslash -> perjel
    f = tmp_path / "a.mp3"
    f.write_bytes(b"hang")
    fake = _FakeRequests()
    monkeypatch.setattr(AC, "requests", fake)
    db, hiba = AC.feltolt("1.2.3.4", "1234", [str(f)], dest="documents",
                          subdir="/Sorozat\\1. kotet/")
    assert hiba is None and db == 1
    assert fake.calls[0]["data"]["dest"] == "documents"
    assert fake.calls[0]["data"]["subdir"] == "Sorozat/1. kotet"


def test_mappa_kuld_flat_a_mappanevet_kuldi(tmp_path, monkeypatch):
    d = tmp_path / "Nagy Sorozat"
    d.mkdir()
    (d / "01.mp3").write_bytes(b"a")
    (d / "02.mp3").write_bytes(b"b")
    (d / "jegyzet.txt").write_text("x", encoding="utf-8")
    fake = _FakeRequests()
    monkeypatch.setattr(AC, "requests", fake)
    db, hiba = AC.mappa_kuld("1.2.3.4", "1234", str(d), csak_hang=True)
    assert hiba is None and db == 2                     # csak a két mp3
    assert all(c["data"]["subdir"] == "Nagy Sorozat" for c in fake.calls)


def test_mappa_kuld_kotet_almappakat_megorzi(tmp_path, monkeypatch):
    # „Sorozat" két kötet-almappával -> a küldés a szerkezetet megőrzi
    d = tmp_path / "Sorozat"
    (d / "1. kotet").mkdir(parents=True)
    (d / "2. kotet").mkdir(parents=True)
    (d / "1. kotet" / "01.mp3").write_bytes(b"a")
    (d / "1. kotet" / "02.mp3").write_bytes(b"b")
    (d / "2. kotet" / "01.mp3").write_bytes(b"c")
    fake = _FakeRequests()
    monkeypatch.setattr(AC, "requests", fake)
    db, hiba = AC.mappa_kuld("1.2.3.4", "1234", str(d), csak_hang=True)
    assert hiba is None and db == 3
    subdirs = sorted({c["data"]["subdir"] for c in fake.calls})
    assert subdirs == ["Sorozat/1. kotet", "Sorozat/2. kotet"]


def test_feltolt_egyenkent_haladas(tmp_path, monkeypatch):
    utak = []
    for n in ("01.mp3", "02.mp3", "03.mp3"):
        p = tmp_path / n
        p.write_bytes(b"x")
        utak.append(str(p))
    fake = _FakeRequests()
    monkeypatch.setattr(AC, "requests", fake)
    hivasok = []
    db, hiba = AC.feltolt_egyenkent("1.2.3.4", "1234", utak, dest="documents",
                                    subdir="Sorozat",
                                    on_progress=lambda k, o, nev, s: hivasok.append((k, o, nev)))
    assert db == 3 and hiba is None
    assert len(fake.calls) == 3                      # fájlonként külön POST
    assert hivasok[0] == (1, 3, "01.mp3")
    assert hivasok[-1] == (3, 3, "03.mp3")
    assert all(c["data"]["subdir"] == "Sorozat" for c in fake.calls)


def test_telefon_konyvek_le(monkeypatch):
    monkeypatch.setattr(AC, "requests", _FakeRequests())
    k = AC.telefon_konyvek_le("1.2.3.4", "1234")
    assert "Sorozat" in k["audiobooks"] and "regeny.epub" in k["books"]


def test_pc_hangoskonyv_polc(monkeypatch):
    monkeypatch.setattr(AC.store, "load_json", lambda *a, **k: [
        {"key": "sorozat", "path": r"D:\Hang\Sorozat", "is_dir": True,
         "title": "Sorozat"}])
    polc = AC.pc_hangoskonyv_polc()
    assert polc["sorozat"]["path"] == r"D:\Hang\Sorozat"


def test_konyvjelzo_hang_mezok_korforgas():
    # PC hang-könyvjelző -> Android -> vissza: kind/posMs/track megmarad
    pc = [{"book": "sorozat", "title": "Sorozat 1. évad", "char": 0,
           "preview": "3. sáv • 12:34", "created": 1700000000001,
           "label": "", "kind": "audio", "pos_ms": 754000,
           "track": "s01e03.mp3"}]
    a = AC.pc_konyvjelzo_androidra(pc)
    assert a[0]["kind"] == "audio" and a[0]["posMs"] == 754000
    assert a[0]["track"] == "s01e03.mp3"
    vissza = AC.android_konyvjelzo_be(a)
    r = vissza[0]
    assert r["kind"] == "audio" and r["pos_ms"] == 754000
    assert r["track"] == "s01e03.mp3" and r["book"] == "sorozat"
    # a régi (hang nélküli) Android-könyvjelző szövegként jön vissza
    regi = AC.android_konyvjelzo_be([{"bookPath": "/x/regeny.epub",
                                      "charOffset": 5, "createdAt": 9}])
    assert regi[0]["kind"] == "text" and regi[0]["pos_ms"] == 0
