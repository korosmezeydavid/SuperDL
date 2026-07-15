"""fileassoc: a fájltársítás-kapuk (M1). A VALÓDI társításokat NEM módosítjuk a
tesztből (az a felhasználó registry-jét írná); csak a kapukat és az olvasót."""

import pytest

fa = pytest.importorskip("superdl.fileassoc")


def test_available_csak_frozen():
    # a teszt NEM fagyasztott környezetben fut → available() False
    assert fa.available() is False


def test_register_forrasbol_elutasit():
    with pytest.raises(RuntimeError):
        fa.register()                       # nem frozen → nem társít semmit


def test_is_registered_nem_dob():
    assert isinstance(fa.is_registered(), bool)


def test_ext_halmazok_ertelmesek():
    assert ".mp3" in fa.AUDIO_EXTS and ".mp4" in fa.VIDEO_EXTS
    assert not (set(fa.AUDIO_EXTS) & set(fa.VIDEO_EXTS))
    assert '"%1"' in fa._open_command() or not fa.available()
