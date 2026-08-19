# -*- coding: utf-8 -*-
"""Super Mail – csatolmány felolvasása.

„Más levelezőprogramnál ehhez külön alkalmazást kell nyitni; nálunk egy
program.” A kinyerést a Core booktext rétege végzi – itt azt ellenőrizzük,
hogy a mail-oldali réteg jól dönt és jól magyaráz.
"""

import sys

import pytest

sys.path.insert(0, "modules_src/mail")
from mail_mod import csatolmany as CS             # noqa: E402


@pytest.mark.parametrize("nev", ["level.txt", "adat.csv", "olvass.md",
                                 "szerzodes.pdf", "level.docx", "konyv.epub",
                                 "oldal.html"])
def test_olvashato_tipusok(nev):
    assert CS.olvashato_e(nev) is True


@pytest.mark.parametrize("nev", ["kep.jpg", "zene.mp3", "csomag.zip",
                                 "program.exe", "tabla.xlsx"])
def test_nem_olvashato_tipusok(nev):
    assert CS.olvashato_e(nev) is False


def test_egyszeru_szoveg_kinyerese():
    assert "Szia" in CS.szoveg("level.txt", "Szia Mari!".encode("utf-8"))


def test_ekezetes_szoveg_rossz_kodolassal_is():
    """Régi magyar fájlok gyakran nem UTF-8-asok – a Core dekódolója menti meg."""
    ki = CS.szoveg("regi.txt", "Árvíztűrő tükörfúrógép".encode("cp1250"))
    assert ki.strip() == "Árvíztűrő tükörfúrógép", \
        "a magyar ékezetek épen kell megmaradjanak, különben a felolvasás hadar"


def test_html_csatolmany_szoveggé():
    html = b"<html><body><p>Kedves Mari!</p><script>x=1</script></body></html>"
    ki = CS.szoveg("oldal.html", html)
    assert "Kedves Mari!" in ki
    assert "x=1" not in ki, "a script tartalma nem szöveg"


def test_nem_tamogatott_tipus_erthetoen_magyarazza():
    with pytest.raises(ValueError):
        CS.szoveg("kep.jpg", b"\x00\x01")
    assert "kép" in CS.miert_nem("kep.jpg")
    assert "hangfájl" in CS.miert_nem("zene.mp3")
    assert "tömörített" in CS.miert_nem("csomag.zip")


def test_osszefoglalo_felolvashato():
    sz = CS.osszefoglalo("szerzodes.pdf", "Első bekezdés.\n\nMásodik sor itt.")
    assert "szerzodes.pdf" in sz and "szó" in sz


def test_ures_dokumentumnal_megmondja_mi_a_baj():
    """Beolvasott (képként mentett) PDF-nél a szöveg valójában kép – ezt
    ki kell mondani, különben a felhasználó azt hiszi, a program romlott el."""
    sz = CS.osszefoglalo("beolvasott.pdf", "   \n\n  ")
    assert "kép" in sz
