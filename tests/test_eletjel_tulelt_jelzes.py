"""Dávid, 2026-09-28: „minden indításkor bedobja", hogy a program váratlanul
bezárult. A faulthandler a LEKEZELT COM-jelzést (0x8001010d, 0x80010108) is
kiírja; ha a futás nem „rendben" ért véget (gépleállítás, telepítő, tálca),
a következő indulás összeomlásnak vette. Az életjel óta a naplónak az utolsó
életjel előtti részét a program bizonyosan túlélte."""
import io

import pytest

from superdl import osszeomlas as O

JELZES = ("Windows fatal exception: code 0x80010108\n"
          "Current thread 0x0001 (most recent call first):\n"
          '  File "wx\\core.py", line 2254 in MainLoop\n')


@pytest.fixture
def omlas(tmp_path, monkeypatch):
    monkeypatch.setattr(O, "NAPLO", tmp_path / "osszeomlas.log")
    monkeypatch.setattr(O, "_OLVASVA", tmp_path / "olvasva.txt")
    monkeypatch.setattr(O, "_uj_resz", "")
    monkeypatch.setattr(O, "_uj_farok", None)
    monkeypatch.setattr(O, "_fajl", None)
    monkeypatch.setattr(O, "_rendben_irva", False)
    O.NAPLO.write_text("", encoding="utf-8")
    O._olvasatlan_beolvas()                  # egy korábbi indulás
    return O


def _fut(omlas, elotte, utana, beolvas=True):
    """Egy futás: `elotte` az életjel előtt, `utana` utána került a naplóba."""
    f = open(omlas.NAPLO, "a", encoding="utf-8")
    f.write("=== SuperDL indult: 2026-09-28 04:40:58 (verzió: 4.6.24) ===\n")
    f.write(elotte)
    f.flush()
    omlas._fajl = f
    omlas.eletjel_ir()
    f.write(utana)
    f.close()
    omlas._fajl = None
    if beolvas:
        omlas._olvasatlan_beolvas()          # a következő indulás


def test_az_eletjel_elotti_jelzest_tulelte(omlas):
    _fut(omlas, JELZES * 3, "")
    assert omlas.uj_osszeomlas() is False


def test_az_utolso_eletjel_utani_jelzes_osszeomlas(omlas):
    _fut(omlas, JELZES, "Windows fatal exception: access violation\n"
                        "Current thread 0x0002 (most recent call first):\n")
    assert omlas.uj_osszeomlas() is True


def test_eletjel_nelkul_marad_a_regi_viselkedes(omlas):
    with open(omlas.NAPLO, "a", encoding="utf-8") as f:
        f.write("=== SuperDL indult ===\n" + JELZES)
    omlas._olvasatlan_beolvas()
    assert omlas.uj_osszeomlas() is True


def test_regi_eletjel_nem_takar_el_uj_osszeomlast(omlas):
    _fut(omlas, "", "")                       # régi futás életjellel
    with open(omlas.NAPLO, "a", encoding="utf-8") as f:
        f.write("=== SuperDL indult ===\n" + JELZES)   # életjel előtt halt meg
    omlas._olvasatlan_beolvas()
    assert omlas.uj_osszeomlas() is True


def test_rendben_kilep_csak_egyszer_ir(monkeypatch):
    f = io.StringIO()
    monkeypatch.setattr(O, "_fajl", f)
    monkeypatch.setattr(O, "_rendben_irva", False)
    O.rendben_kilep()
    O.rendben_kilep()
    assert f.getvalue().count(O.RENDBEN_JEL) == 1


def test_frissiteskor_tenyleg_kilep_nem_talcara_rejt():
    src = open("superdl_gui.py", encoding="utf-8").read()
    assert 'getattr(parent, "_quit_app", parent.Close)' in src


def test_a_tulelt_futas_a_jelentesben_sem_osszeomlas(omlas, monkeypatch):
    _fut(omlas, JELZES, "", beolvas=False)
    monkeypatch.setattr(omlas, "_fajl", None)
    omlas.bekapcsol()                          # következő indulás: jel beírva
    try:
        szoveg = omlas.NAPLO.read_text(encoding="utf-8")
        assert omlas.RENDBEN_JEL in szoveg
        assert all(b["fajta"] != "osszeomlas"
                   for b in omlas.jelentes_blokkok(fut_most=False))
    finally:
        import faulthandler
        faulthandler.disable()
        omlas._fajl.close()
        omlas._fajl = None


def test_valodi_osszeomlasnal_nincs_rendben_jel(omlas):
    _fut(omlas, "", "Windows fatal exception: access violation\n"
                    "Current thread 0x0002 (most recent call first):\n")
    assert omlas.elozo_tulelte() is False
