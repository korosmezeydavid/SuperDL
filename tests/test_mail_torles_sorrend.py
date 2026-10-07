# -*- coding: utf-8 -*-
"""A gyors egymás utáni törlés nem indulhat ugyanarra a levélre kétszer."""
from types import SimpleNamespace

import pytest

MW = pytest.importorskip("modules_src.mail.mail_mod.mailwin")


def test_masodik_torles_var_az_elso_befejezeseig(monkeypatch):
    elso = {"uid": "1", "felado": "Első", "targy": "Első levél"}
    masodik = {"uid": "2", "felado": "Második", "targy": "Második levél"}
    kimondva = []
    feladatok = []
    kijeloles = [0]

    class Lista:
        def GetSelections(self):
            return tuple(kijeloles)

        def Set(self, sorok):
            self.sorok = sorok

        def SetSelection(self, index):
            kijeloles[:] = [index]

    frame = SimpleNamespace(
        _torles_folyamatban=False, _closing=False,
        _lista=[elso, masodik], level_lista=Lista(),
        _aktiv={"email": "teszt@example.hu"}, _mappa="INBOX",
        _kivalasztottak=lambda: [frame._lista[i] for i in kijeloles],
        _kivalasztott=lambda: frame._lista[kijeloles[0]],
        _elso_kijelolt_index=lambda: kijeloles[0],
        _kuka_mappa=lambda: "Trash", _mond=kimondva.append,
        _sor_szoveg=lambda item: item["targy"],
        _halo_hiba=lambda ex: kimondva.append(str(ex)),
    )
    monkeypatch.setattr(MW, "_hatterben", lambda munka, kesz, hiba: feladatok.append((munka, kesz, hiba)))

    MW.MailFrame._torol(frame, None)
    MW.MailFrame._torol(frame, None)
    assert len(feladatok) == 1
    assert "folyamatban" in kimondva[-1]

    feladatok[0][1](1)
    assert frame._lista == [masodik]
    assert kijeloles == [0]
    MW.MailFrame._torol(frame, None)
    assert len(feladatok) == 2
    assert frame._torles_folyamatban


def test_torles_hiba_utan_ujra_indithato(monkeypatch):
    level = {"uid": "1", "felado": "Teszt", "targy": "Teszt"}
    feladatok = []
    frame = SimpleNamespace(
        _torles_folyamatban=False, _closing=False, _lista=[level],
        _aktiv={"email": "teszt@example.hu"}, _mappa="INBOX",
        _kivalasztottak=lambda: [level],
        _elso_kijelolt_index=lambda: 0, _kuka_mappa=lambda: "Trash",
        _halo_hiba=lambda ex: None,
    )
    monkeypatch.setattr(MW, "_hatterben", lambda munka, kesz, hiba: feladatok.append((munka, kesz, hiba)))
    MW.MailFrame._torol(frame, None)
    feladatok[0][2](OSError("hálózati hiba"))
    MW.MailFrame._torol(frame, None)
    assert len(feladatok) == 2
