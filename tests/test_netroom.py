# -*- coding: utf-8 -*-
"""Az online játék-szoba (Ably-relay) tesztjei – VALÓS hálózat NÉLKÜL.

A `requests`-et mockoljuk, így a kulcs- és üzenet-logika CI-n is ellenőrizhető."""
import json

import pytest

BASE = "modules_src.jatekok.jatekok_mod"
NR = pytest.importorskip(BASE + ".netroom")


class _Resp:
    def __init__(self, data):
        self._d = data
    def raise_for_status(self):
        pass
    def json(self):
        return self._d


def test_szobakod_formatum():
    k = NR.szobakod()
    assert len(k) == 5
    assert all(c in NR._KOD_ABC for c in k)
    # a félreérthető karakterek nincsenek a készletben
    for zavaro in ("0", "O", "1", "I"):
        assert zavaro not in NR._KOD_ABC


def test_ably_kulcs_env(monkeypatch):
    monkeypatch.setenv("SUPERDL_ABLY_KEY", "app.key:secret")
    assert NR.ably_kulcs() == "app.key:secret"


def test_auth_szetvalasztas():
    sz = NR.NetSzoba("abc", "n", kulcs="app.key:titok")
    assert sz.kod == "ABC"                     # nagybetűsít
    assert sz._auth() == ("app.key", "titok")
    assert sz.elerheto() is True


def test_kuld_helyes_post(monkeypatch):
    kapott = {}
    def fake_post(url, auth=None, json=None, timeout=None):
        kapott.update(url=url, auth=auth, body=json)
        return _Resp({})
    monkeypatch.setattr(NR.requests, "post", fake_post)
    sz = NR.NetSzoba("ABC", "Zoli", kulcs="app.key:titok")
    sz.kuld("tipp", {"betu": "G"})
    assert "channels/szerencsekerek:ABC/messages" in kapott["url"]
    assert kapott["auth"] == ("app.key", "titok")
    assert kapott["body"]["name"] == "tipp"
    d = json.loads(kapott["body"]["data"])
    assert d["ki"] == "Zoli" and d["adat"]["betu"] == "G"


def test_uj_uzenetek_parse_es_dedup(monkeypatch):
    uzenetek = [
        {"id": "m1", "name": "tipp",
         "data": '{"ki":"Zoli","adat":{"betu":"G"}}', "timestamp": 1000},
        {"id": "m2", "name": "megfejt",
         "data": '{"ki":"Anna","adat":{}}', "timestamp": 1001},
    ]
    monkeypatch.setattr(NR.requests, "get", lambda *a, **k: _Resp(uzenetek))
    sz = NR.NetSzoba("ABC", "n", kulcs="app.key:titok")
    elso = sz.uj_uzenetek()
    assert [u["tipus"] for u in elso] == ["tipp", "megfejt"]
    assert elso[0]["ki"] == "Zoli" and elso[0]["adat"]["betu"] == "G"
    # ugyanaz másodszor → dedupolva, üres
    assert sz.uj_uzenetek() == []


def test_kulcs_nelkul_nem_elerheto(monkeypatch):
    monkeypatch.delenv("SUPERDL_ABLY_KEY", raising=False)
    monkeypatch.setattr(NR, "ably_kulcs", lambda: "")   # se env, se fájl
    sz = NR.NetSzoba("ABC", "n", kulcs="")
    assert sz.elerheto() is False
