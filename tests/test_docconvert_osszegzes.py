# -*- coding: utf-8 -*-
"""Dokumentum-konverter: az összegzés ELSŐ SZAVA mondja meg, sikerült-e.
Turai László, 2026-09-29: DOC-bemenet Calibre nélkül → a program „Kész: 0/1"-
gyel kezdte, a képernyőolvasó a „kész"-t mondta ki, pedig semmi nem készült."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "modules_src" / "docconvert"))
from docconvert_mod import docconvert as DC        # noqa: E402

OK_CALIBRE = ("Ehhez a Calibre VAGY a LibreOffice szükséges (mindkettő "
              "ingyenes). Telepítsd egyiket, és a SuperDL felismeri.")


def test_egy_fajl_semmi_nem_sikerult_nem_kezdodik_kesszel():
    msg = DC.osszegzo_uzenet(0, 1, [("MVGYOSZ3.DOC", OK_CALIBRE)],
                             r"C:\ki", "txt")
    assert msg.startswith("NEM SIKERÜLT: MVGYOSZ3.DOC – Ehhez a Calibre")
    assert "kész" not in msg.lower().split("\n")[0]
    assert "\n" not in msg, "egy fájlnál az ok az első sorban van"


def test_tobb_fajl_semmi_nem_sikerult():
    hibak = [("a.doc", OK_CALIBRE), ("b.mobi", "Calibre hiba: x\nrészlet")]
    msg = DC.osszegzo_uzenet(0, 2, hibak, r"C:\ki", "txt")
    assert msg.startswith("NEM SIKERÜLT: egyik fájl sem")
    assert "Hibás fájlok:" in msg
    assert "• b.mobi: Calibre hiba: x" in msg and "részlet" not in msg


def test_reszben_kesz():
    msg = DC.osszegzo_uzenet(2, 3, [("c.doc", OK_CALIBRE)], r"C:\ki", "docx")
    assert msg.startswith("RÉSZBEN KÉSZ: 2/3 fájl konvertálva ide: C:\\ki")
    assert "1 fájl nem sikerült" in msg and "• c.doc:" in msg


def test_minden_sikerult_kesz():
    msg = DC.osszegzo_uzenet(3, 3, [], r"C:\ki", "epub")
    assert msg.startswith("Kész: 3/3 fájl konvertálva ide: C:\\ki (EPUB).")
    assert "Hibás" not in msg


def test_leallitva_marad_elol():
    msg = DC.osszegzo_uzenet(1, 4, [], r"C:\ki", "txt", megszakitva=True)
    assert msg.startswith("LEÁLLÍTVA. Eddig 1/4")


def test_osszefuzes_szovegei():
    jo = DC.osszegzo_uzenet(2, 2, [], r"C:\ki\ossz.txt", "txt", osszefuzve=True)
    assert jo.startswith("Összefűzve: 2/2 fájl szövege ide: ossz.txt (TXT).")
    resz = DC.osszegzo_uzenet(1, 2, [("x.doc", OK_CALIBRE)],
                              r"C:\ki\ossz.txt", "txt", osszefuzve=True)
    assert resz.startswith("RÉSZBEN KÉSZ: 1/2 fájl szövege ide: ossz.txt")
    assert "Kihagyott fájlok:" in resz


def test_a_gui_mindket_uton_ezt_hasznalja():
    src = (ROOT / "modules_src" / "docconvert" / "docconvert_mod"
           / "docconvertwin.py").read_text(encoding="utf-8")
    assert src.count("DC.osszegzo_uzenet(") == 2
    assert 'f"Kész: {ok}/{total}' not in src, "a régi, hazug Kész visszajött"
