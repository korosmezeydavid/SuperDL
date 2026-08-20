# -*- coding: utf-8 -*-
"""Super Mail – válasz után bezáruljon-e az eredeti levél ablaka?

Felhasználói kérés (2026-08-20): „ha rányomok a válaszra, az eredeti levél
nyitva marad. Lehessen ezt is ki-be kapcsolni… de ez ne fix paraméter legyen,
hanem egy checkbox, amit be lehet pipálni, ha valaki ezt szeretné.”

Ezért: az ALAPÉRTELMEZÉS a régi viselkedés (az eredeti nyitva marad), és csak
a pipa változtatja meg. Ez a teszt pontosan ezt a két esetet őrzi.
"""

import sys

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import mail_core as MC          # noqa: E402
from mail_mod import mailwin as MW            # noqa: E402


class _Keret:
    """A LevelOlvasoFrame `_valaszol` metódusa, wx-ablak nélkül."""

    _valaszol = MW.LevelOlvasoFrame._valaszol

    def __init__(self):
        self.zart = False
        self.valaszok = []
        self._msg = "üzenet"
        self._fiok = {"email": "en@sajat.hu"}

        keret = self

        class _Fo:
            def _valasz(self, **kw):
                keret.valaszok.append(kw)
        self._mf = _Fo()

    def Close(self):
        self.zart = True


def _beallit(monkeypatch, ertek):
    alap = dict(MC._ALTALANOS_ALAP)
    alap["valasz_zarja_eredetit"] = ertek
    monkeypatch.setattr(MC, "altalanos_betolt", lambda: alap)


def test_alapbol_nyitva_marad_az_eredeti(monkeypatch):
    """A megszokott viselkedés NEM változhat attól, hogy új beállítás lett."""
    _beallit(monkeypatch, False)
    k = _Keret()
    k._valaszol(msg="üzenet", fiok=k._fiok)
    assert k.zart is False
    assert k.valaszok == [{"msg": "üzenet", "fiok": k._fiok}]


def test_bepipalva_bezarul_az_eredeti(monkeypatch):
    _beallit(monkeypatch, True)
    hivasok = []
    monkeypatch.setattr(MW.wx, "CallAfter",
                        lambda fv, *a, **kw: hivasok.append((fv, kw)))
    k = _Keret()
    k._valaszol(msg="üzenet", fiok=k._fiok)
    assert k.zart is True, "az eredeti ablak bezárul"
    assert hivasok, "a válasz UTÁNA nyílik meg"
    assert hivasok[0][1] == {"msg": "üzenet", "fiok": k._fiok}
    assert k.valaszok == [], "nem közvetlenül hívjuk, hanem a bezárás után"


def test_a_valasz_mindenkinek_es_a_listas_valasz_is_igy_mukodik(monkeypatch):
    """Ugyanaz a szabály a Válasz mindenkinek és a listára válasz esetén is –
    a felhasználó nem fogja külön megjegyezni, melyik melyik."""
    _beallit(monkeypatch, True)
    hivasok = []
    monkeypatch.setattr(MW.wx, "CallAfter",
                        lambda fv, *a, **kw: hivasok.append(kw))
    k = _Keret()
    k._valaszol(msg="ü", fiok=k._fiok, mind=True)
    k2 = _Keret()
    k2._valaszol(msg="ü", fiok=k2._fiok, listara="lista@x.hu")
    assert hivasok[0].get("mind") is True
    assert hivasok[1].get("listara") == "lista@x.hu"
    assert k.zart and k2.zart


def test_az_uj_beallitas_alapertelmezese_kikapcsolt():
    assert MC._ALTALANOS_ALAP["valasz_zarja_eredetit"] is False
