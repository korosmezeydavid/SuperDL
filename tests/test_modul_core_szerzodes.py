# -*- coding: utf-8 -*-
"""ŐR: kér-e valamelyik modul olyat a Core-tól, ami nincs?

Ez a teszt a tvmusor kedvenc-emlékeztetőjének hibaosztályát zárja le
(2026-08-30, Laci jelzése). A hiba NÉMA volt: a modul `getattr(core, "main")`-t
hívott, a CoreContext viszont `main_frame` néven adja a főablakot – a getattr
alapértelmezése elnyelte, a funkció a megjelenése óta halott volt, MINDENKINÉL,
és a felhasználó egy félrevezető üzenetet kapott. Ugyanez a névelcsúszás volt a
„Napi infó nem indul" gyökere is.

Az ilyet emberi szem nem találja meg – ezért gép őrzi.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "attr_audit", ROOT / "tools" / "attr_audit.py")
A = importlib.util.module_from_spec(_spec)
sys.modules["attr_audit"] = A
_spec.loader.exec_module(A)


def test_egyetlen_modul_sem_ker_nem_letezo_core_nevet():
    talalatok = A.vizsgal_mind()
    assert not talalatok, "\n".join(
        "%s:%d  %s.%s (%s) – a Core ezt NEM adja" % t for t in talalatok)


def test_a_szerzodes_tenyleg_main_frame_neven_adja_a_foablakot():
    """A hiba gyökere: a `main` NÉV NEM LÉTEZIK a CoreContexten."""
    core, _ = A.szerzodes()
    assert "main_frame" in core
    assert "frame" in core, "a modkit aliasa – a Napi infó-fix óta kell"
    assert "main" not in core, (
        "ha egyszer bekerül a `main` alias, ezt a sort kell átírni – de akkor "
        "tudatos döntés legyen, ne véletlen")


def test_az_or_tenyleg_elkapja_a_regi_tvmusor_kodot():
    """Enélkül az őr csak dísz volna: bizonyítsuk, hogy a VALÓDI hibát fogja."""
    regi = (
        'def _emlekezteto_hozzaad(self, nev, m):\n'
        '    org = getattr(self.core, "organizer", None) or \\\n'
        '        getattr(self.core, "_organizer", None)\n'
        '    if org is None:\n'
        '        main = getattr(self.core, "main", None)\n'
        '        org = getattr(main, "_organizer", None) if main else None\n'
    )
    talalatok = A.vizsgal_forras("regi_tvmusorwin.py", regi)
    nevek = {t[3] for t in talalatok}
    assert "main" in nevek, "az őrnek pont ezt kellene elkapnia"


def test_az_or_nem_riaszt_a_helyes_kodra():
    jo = (
        'def _naptar_kezelo(self):\n'
        '    return getattr(self.core, "main_frame", None)\n'
    )
    assert A.vizsgal_forras("uj.py", jo) == []
