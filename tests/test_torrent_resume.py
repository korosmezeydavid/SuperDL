# -*- coding: utf-8 -*-
"""Torrent: újraindítás utáni seed-folytatás és az ellenőrzés+seed mód.

A felhasználó jelezte: újraindítás után a program „elfelejti" a seedelést, és
újra hozzáadva „a fájl már létezik" hurokba kerül. Ez tracker-kizárást is
okozhat. A javítás: a SEEDELŐ torrent induláskor AUTOMATIKUSAN ellenőrzés+seed
(verify) módban jön vissza, és a verify-mód az aria2-nek allow-overwrite-ot is
ad, hogy a vezérlőfájl hiányában is validáljon+seedeljen (ne dobjon „már
létezik"-et)."""
import types

import pytest

from superdl import manager as mgr_mod
from superdl import torrent


# ---- Fix 2: restore() a seedelő torrentet verify módban tölti vissza -------

def _capture_restore(monkeypatch, tmp_path, rec):
    monkeypatch.setattr(mgr_mod.store, "load_queue", lambda: [rec])
    m = mgr_mod.DownloadManager(out_dir=str(tmp_path), persist=True)
    calls = []
    def fake_add(url, **kw):
        calls.append(kw)
        return types.SimpleNamespace(
            progress=types.SimpleNamespace(filename=""))
    monkeypatch.setattr(m, "add", fake_add)
    m.restore()
    return calls


def test_seedelo_torrent_verify_modban_jon_vissza(monkeypatch, tmp_path):
    rec = {"url": "magnet:?xt=urn:btih:abc", "kind": "torrent",
           "status": "seedelés", "verify": False, "overwrite": False}
    calls = _capture_restore(monkeypatch, tmp_path, rec)
    assert calls, "a restore nem adta vissza a seedelő torrentet"
    assert calls[0]["verify"] is True, "seedelésnél kell az auto-verify"


def test_letolto_torrent_nem_kap_kenyszer_verify_t(monkeypatch, tmp_path):
    # a még LETÖLTŐ torrent a .aria2 vezérlőfájlból folytatódik, nem kell
    # kényszer-újraellenőrzés (az lassú full re-hash lenne)
    rec = {"url": "magnet:?xt=urn:btih:def", "kind": "torrent",
           "status": "letöltés", "verify": False, "overwrite": False}
    calls = _capture_restore(monkeypatch, tmp_path, rec)
    assert calls
    assert calls[0]["verify"] is False


def test_mentett_verify_megmarad_nem_torrentnel_is(monkeypatch, tmp_path):
    # ha korábban explicit verify volt mentve, maradjon verify
    rec = {"url": "http://pelda/f.iso", "kind": "file",
           "status": "letöltés", "verify": True, "overwrite": False}
    calls = _capture_restore(monkeypatch, tmp_path, rec)
    assert calls
    assert calls[0]["verify"] is True


# ---- Fix 3: verify mód = check-integrity ÉS allow-overwrite ----------------

class _FakeClient:
    def __init__(self):
        self.opts = None
        self.method = None
    def call(self, method, *params):
        self.method = method
        self.opts = params[-1]          # az utolsó paraméter az opciók dict
        return "gid-teszt"


def test_verify_mod_check_integrity_es_allow_overwrite():
    td = torrent.TorrentDownloader(
        "magnet:?xt=urn:btih:abc", "/tmp/cel", check_integrity=True)
    td.client = _FakeClient()
    gid = td._add()
    assert gid == "gid-teszt"
    assert td.client.opts.get("check-integrity") == "true"
    assert td.client.opts.get("allow-overwrite") == "true", \
        "a kész adat seedeléséhez a vezérlőfájl hiányában allow-overwrite kell"


def test_alap_torrentnel_nincs_felulir_vagy_ellenoriz():
    td = torrent.TorrentDownloader("magnet:?xt=urn:btih:abc", "/tmp/cel")
    td.client = _FakeClient()
    td._add()
    assert "check-integrity" not in td.client.opts
    assert "allow-overwrite" not in td.client.opts
