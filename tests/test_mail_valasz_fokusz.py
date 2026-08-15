# -*- coding: utf-8 -*-
"""Super Mail: VÁLASZNÁL a kurzor a levél szövegébe ugorjon.

Felhasználói kérés (2026-08-15): „amikor válaszra nyomsz (Ctrl+R), akkor ne a
címzettbe, hanem rögtön a levél törzsére ugorjon a kurzor, hogy nekem már csak
írni kelljen a választ."

A levélíró ablak teljes felépítéséhez élő fiók és wx kell, ezért a szabályt
FORRÁS-SZINTEN őrizzük (a tényleges fókuszálást élő próbában ellenőriztem):
  • a válasz `torzsre=True`-val nyitja az ablakot;
  • az ÚJ levél és a TOVÁBBÍTÁS NEM – ott a Címzett az első dolgunk;
  • az ablak a `torzsre` esetén a szöveg ELEJÉRE teszi a kurzort (az idézet
    fölé), nem a végére.
"""

import pathlib
import re

FORRAS = (pathlib.Path(__file__).resolve().parent.parent / "modules_src"
          / "mail" / "mail_mod" / "mailwin.py").read_text(encoding="utf-8")


def _fuggveny(nev: str) -> str:
    """Egy metódus törzse a forrásból (a következő `def` előtti részig)."""
    m = re.search(r"\n    def %s\(.*?(?=\n    def )" % re.escape(nev),
                  FORRAS, re.S)
    assert m, "nincs ilyen metódus: %s" % nev
    return m.group(0)


def test_a_valasz_a_torzsre_nyit():
    assert "torzsre=True" in _fuggveny("_valasz")


def test_uj_level_es_tovabbitas_a_cimzetten_indul():
    for nev in ("_uj", "_tovabbit"):
        assert "torzsre" not in _fuggveny(nev), \
            ("%s: itt a CÍMZETT az első dolog, nem a szöveg" % nev)


def test_az_ablak_a_szoveg_elejere_teszi_a_kurzort():
    m = re.search(r"if torzsre:(.*?)\n\n", FORRAS, re.S)
    assert m, "hiányzik a törzsre-ugrás ága"
    ag = m.group(1)
    assert "self.torzs.SetFocus" in ag, "a fókusz a levél szövegére kerüljön"
    assert "SetInsertionPoint(0)" in ag or "SetInsertionPoint, 0" in ag, \
        "a kurzor az IDÉZET FÖLÉ, a szöveg elejére kerüljön"


def test_a_valasz_mindenkinek_is_a_torzsre_nyit():
    """A „válasz mindenkinek" ugyanazt a `_valasz`-t hívja – ha valaki
    külön ágra bontaná, ez a teszt szól."""
    assert "self._valasz(mind=True)" in _fuggveny("_valasz_mind")
