"""A képernyőolvasó-kimenet (NVDA-vezérlő / JAWS-COM) robusztussága.

A modul akár FUT képernyőolvasó, akár nem, MINDIG bool-t ad és SOSEM dob
kivételt – így a hívó (játékkonzol, rádió) biztonságosan visszaeshet a saját
tartalékára (retró hang / selfvoice / SAPI), ha nincs megszólaltatható SR.
(A fejlesztő gépén fut NVDA, a CI-n nem – ezért a teszt nem feltételez egyik
állapotot sem.)"""

import pytest

sr = pytest.importorskip("superdl.screenreader")


def test_ures_szoveg_mindig_false():
    # üres szövegre nincs megszólalás, False – ez környezettől független
    assert sr.speak("") is False
    assert sr.speak("   ") is False


def test_soha_nem_dob_kivetelt():
    # akárhogy is: bool/str a válasz, kivétel nincs
    assert isinstance(sr.speak("teszt"), bool)
    assert isinstance(sr.available(), bool)
    assert isinstance(sr.screen_reader_name(), str)


def test_ismetelt_hivas_stabil():
    for _ in range(3):
        assert isinstance(sr.speak("még egy"), bool)


def test_available_es_nev_osszhang():
    # ha van megszólaltatható SR, van neve is; ha nincs, üres a név
    if sr.available():
        assert sr.screen_reader_name() != ""
    else:
        assert sr.screen_reader_name() == ""
