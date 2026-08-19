# -*- coding: utf-8 -*-
"""Super Mail – a MAPPALISTA betöltése.

Felhasználói hibajelzés (2026-08-19): „az e-maileknél a mappák lekérése nem
történik meg, az Összes bejövőt akarja mutatni mindenáron; ha rámegyek a saját
e-mail címemre, ott se mutatja a mappákat”.

GYÖKÉROK: az 1.0.14-ben (MK1) az „Összes bejövő" ál-mappa kivételekor a
`_mappak_rendez` metódus is törlődött, de a HÍVÁSA bent maradt a
`_mappak_kesz`-ben. Az így keletkező AttributeError egy `wx.CallAfter`
visszahívásban ült, ahol NÉMÁN elnyelődik – a felhasználó csak annyit látott,
hogy a mappalista sosem frissül.

Ez a teszt két szinten véd:
  1. a rendezés maga működik és a helyes sorrendet adja;
  2. a mailwin.py-ben `self._valami(...)` alakban hívott ÖSSZES metódus tényleg
     létezik – ez az egész hibaosztályt kiszűri, nem csak ezt az egy esetet.
"""

import ast
import sys

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import mailwin as MW            # noqa: E402

FAJL = "modules_src/mail/mail_mod/mailwin.py"


def test_a_mappak_rendezese_letezik_es_a_beerkezett_van_elol():
    r = MW.MailFrame._mappak_rendez(
        ["Zebra", "Trash", "INBOX", "Sent", "Archívum", "Alma"])
    assert r[0] == "INBOX", "a Beérkezett MINDIG a lista tetején van"
    assert r.index("Sent") < r.index("Alma"), "a rendszer-mappák a sajátok előtt"
    assert r.index("Trash") < r.index("Zebra")
    assert r[-2:] == ["Alma", "Zebra"], "a saját mappák ábécében a végén"


def test_ures_es_hianyos_lista_sem_szall_el():
    assert MW.MailFrame._mappak_rendez([]) == []
    assert MW.MailFrame._mappak_rendez([None, "INBOX"])[0] == "INBOX"


def _hivott_metodusnevek(forras):
    """Minden `self._valami(...)` hívás neve a fájlban."""
    fa = ast.parse(forras)
    nevek = set()
    for csp in ast.walk(fa):
        if (isinstance(csp, ast.Call)
                and isinstance(csp.func, ast.Attribute)
                and isinstance(csp.func.value, ast.Name)
                and csp.func.value.id == "self"
                and csp.func.attr.startswith("_")):
            nevek.add(csp.func.attr)
    return nevek


def _beallitott_attributumok(forras):
    """A `self._valami = ...` alakban beállított attribútumok (ezek nem
    metódusok, de hívhatók – pl. eltárolt visszahívás)."""
    fa = ast.parse(forras)
    nevek = set()
    for csp in ast.walk(fa):
        if isinstance(csp, (ast.Assign, ast.AnnAssign)):
            celok = csp.targets if isinstance(csp, ast.Assign) else [csp.target]
            for c in celok:
                if (isinstance(c, ast.Attribute)
                        and isinstance(c.value, ast.Name)
                        and c.value.id == "self"):
                    nevek.add(c.attr)
    return nevek


def test_minden_hivott_sajat_metodus_letezik():
    """EZ fogta volna meg az 1.0.14 hibáját: a `_mappak_rendez` hívása bent
    maradt, a metódus viszont törlődött."""
    forras = open(FAJL, encoding="utf-8").read()
    hivott = _hivott_metodusnevek(forras)
    beallitott = _beallitott_attributumok(forras)
    osztalyok = [getattr(MW, n) for n in dir(MW)
                 if isinstance(getattr(MW, n), type)]
    hianyzik = sorted(
        nev for nev in hivott
        if not any(hasattr(o, nev) for o in osztalyok) and nev not in beallitott)
    assert not hianyzik, ("hívunk nem létező metódust (némán elnyelődő "
                          "AttributeError lesz belőle): %s" % hianyzik)


def test_a_mappak_kesz_nem_nyeli_el_a_hibat():
    """A megjelenítés hibáját KIMONDJUK – a néma hiba a legrosszabb, amit egy
    vak felhasználó kaphat."""
    class Proba:
        _closing = False
        _mappak_rendez = staticmethod(lambda m: (_ for _ in ()).throw(
            RuntimeError("szandekos")))
        _mappak_kesz = MW.MailFrame._mappak_kesz
        mondtak = []

        def _mond(self, sz):
            self.mondtak.append(sz)

        def _frissit(self):
            raise AssertionError("hibánál nem szabad listát tölteni")

    p = Proba()
    p._mappak_kesz(["INBOX"])
    assert p.mondtak and "mappák" in p.mondtak[0].lower()
