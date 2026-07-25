"""A Tolk-alapú képernyőolvasó-kimenet GRACEFUL FALLBACKje.

Tolk-DLL vagy futó képernyőolvasó nélkül a modul SOSEM dob kivételt, és False-t
ad – így a hívó (játékkonzol, rádió) a saját tartalékára (retró hang / selfvoice
/ SAPI) eshet vissza. Ezt teszteljük (CI-ben nincs képernyőolvasó)."""

import pytest

sr = pytest.importorskip("superdl.screenreader")


def test_speak_ures_szoveg_false():
    assert sr.speak("") is False
    assert sr.speak("   ") is False


def test_fallback_kivetel_nelkul():
    # Tolk/képernyőolvasó nélkül: nincs megszólaltatás, de nincs kivétel sem
    assert sr.speak("teszt üzenet") is False
    assert sr.available() is False
    assert isinstance(sr.screen_reader_name(), str)


def test_ismetelt_hivas_stabil():
    # a lusta betöltés csak egyszer próbálkozik, utána is hibátlan
    for _ in range(3):
        assert sr.speak("még egy") is False
