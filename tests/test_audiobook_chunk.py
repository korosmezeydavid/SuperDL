"""audiobook.chunk_text: a felolvasás-darabolás SEMMIT nem dobhat el
(3.29.4-es mondatvég-lehagyás regressziója), és a hosszú mondatot
tagmondat-határon töri (3.29.5-ös „szaggatás" finomítás)."""

import re

import pytest

audiobook = pytest.importorskip("superdl.audiobook")


def _szavak(s):
    return re.findall(r"\w+", s, re.UNICODE)


def test_rovid_mondatok_egyben():
    txt = "Első mondat. Második mondat! Harmadik?"
    out = audiobook.chunk_text(txt, 400)
    assert out
    assert _szavak(" ".join(out)) == _szavak(txt)


def test_hosszu_mondat_nem_veszit_szot():
    txt = ("Ez egy nagyon hosszú mondat, amely sok-sok tagmondatból áll, "
           "és azért készült, hogy a darabolót próbára tegye, miközben "
           "egyetlen szó sem veszhet el belőle, mert a felolvasónak a teljes "
           "szöveget el kell mondania, az utolsó szóig.")
    out = audiobook.chunk_text(txt, 80)
    assert len(out) > 1
    assert _szavak(" ".join(out)) == _szavak(txt)
    # egyetlen darab sem lépheti túl érdemben a korlátot
    assert all(len(d) <= 80 + 20 for d in out)


def test_wrap_long_tagmondat_hataron():
    s = ("Az első tagmondat itt véget ér, a második pedig itt folytatódik "
         "tovább egészen a végéig")
    out = audiobook._wrap_long(s, 60)
    assert len(out) >= 2
    # a törés a vessző UTÁN esik (a darab vége nem szó közepe)
    assert out[0].endswith(("ér,", "ér"))
    assert _szavak(" ".join(out)) == _szavak(s)
