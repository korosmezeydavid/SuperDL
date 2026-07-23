# -*- coding: utf-8 -*-
"""KÖZÖS magyar szöveg-dekódoló – Herman Tibi TEXT-P0-01.
A könyvolvasó eddig csak UTF-8-at feltételezett, a konverter viszont fejlett
felismerést használt: UGYANAZ a fájl máshogy nyílt meg."""
import pathlib

import pytest

from superdl import booktext, textdecode as TD

ROOT = pathlib.Path(__file__).parent.parent
MINTA = "Árvíztűrő tükörfúrógép. Őszinte üdvözlet, Ödön."


def _cwi_bytes(s: str) -> bytes:
    return bytes(TD._CWI2_TABLE.index(c) if c in TD._CWI2_TABLE else ord(c)
                 for c in s)


@pytest.mark.parametrize("enc", ["cp1250", "cp852", "iso-8859-2"])
def test_regi_kodlapok_helyesen_dekodolodnak(enc):
    assert TD.auto_decode(MINTA.encode(enc)) == MINTA


def test_cwi2_dekodolas():
    assert TD.auto_decode(_cwi_bytes(MINTA)) == MINTA


def test_utf8_valtozatlanul_jo():
    """Regresszió-őr: a helyes fájlokon SEMMI nem változhat."""
    assert TD.auto_decode(MINTA.encode("utf-8")) == MINTA
    assert TD.auto_decode(MINTA.encode("utf-8-sig")) == MINTA


def _mojibake(s: str) -> bytes:
    """A VALÓS romlás útja: a CWI-bájtokat egy engedékeny eszköz CP1250-ként
    olvassa (a definiálatlan bájt a C1-kódpontjára képződik), majd UTF-8-ként
    menti. Így keletkezett Turai László fájljában a U+0090."""
    out = []
    for b in _cwi_bytes(s):
        try:
            out.append(bytes([b]).decode("cp1250"))
        except UnicodeDecodeError:
            out.append(chr(b))
    return "".join(out).encode("utf-8")


def test_kettos_kodolas_helyreall():
    """A CWI→CP1250→UTF-8 mojibake visszafejtése."""
    assert TD.auto_decode(_mojibake(MINTA)) == MINTA


def test_read_cwi_mindket_formaban():
    assert TD.read_cwi(_cwi_bytes(MINTA)) == MINTA
    assert TD.read_cwi(_mojibake(MINTA)) == MINTA


def test_c1_vezerlok_felismerese():
    assert TD.has_c1_controls("normális szöveg") is False
    assert TD.has_c1_controls("kacat \x90 itt") is True


def test_pontszam_a_magyart_dijazza():
    assert TD.decode_score("Árvíztűrő") > TD.decode_score("┴rv╠zt√r§")


# ---- a LÉNYEG: a könyvolvasó is ugyanazt kapja --------------------------

@pytest.mark.parametrize("enc", ["cp1250", "cp852"])
def test_a_konyvolvaso_is_helyesen_nyitja_a_regi_txt_t(tmp_path, enc):
    p = tmp_path / f"regi_{enc}.txt"
    p.write_bytes(MINTA.encode(enc))
    book = booktext.extract(str(p))
    assert "Árvíztűrő" in book.text and "tükörfúrógép" in book.text
    assert "�" not in book.text, "pótló karakter = adatvesztés"


def test_a_konyvolvaso_cwi_t_is_kezel(tmp_path):
    p = tmp_path / "regi_cwi.txt"
    p.write_bytes(_cwi_bytes(MINTA))
    assert "Árvíztűrő" in booktext.extract(str(p)).text


def test_booktext_a_kozos_dekodolot_hasznalja():
    src = (ROOT / "superdl" / "booktext.py").read_text(encoding="utf-8")
    assert "textdecode" in src, "a könyvolvasó nem a közös dekódolót használja"
    assert 'read_text(encoding="utf-8", errors="replace")' not in src


def test_docconvert_ugyanabbol_a_forrasbol_dolgozik():
    src = (ROOT / "modules_src" / "docconvert" / "docconvert_mod"
           / "docconvert.py").read_text(encoding="utf-8")
    assert "from superdl import textdecode" in src, "duplikált dekódoló maradt"
    assert "def _auto_decode" not in src, "régi másolat maradt a modulban"
