"""docconvert: magyar CWI-2 dekódolás + a CWI→CP1250→UTF-8 KETTŐS KÓDOLÁS
visszafejtése (Turai László „Ráadó és Anyicska" esete, 1.1.4)."""

import pytest

dc = pytest.importorskip("modules_src.docconvert.docconvert_mod.docconvert")

# csak CWI-ben ábrázolható karakterek (ASCII + magyar ékezetek)
MINTA = "RÁADÓ ÉS ANYICSKA - Árvíztűrő tükörfúrógép, őszi űrhajó."


def _to_cwi(text: str) -> bytes:
    """Unicode → nyers CWI-2 bájtok (a dekódoló tábla megfordításával)."""
    rev = {ch: i for i, ch in enumerate(dc._CWI2_TABLE)}
    return bytes(rev[ch] for ch in text)


def test_cwi2_tabla_magyar_pozicioi():
    assert dc.decode_cwi2(bytes([0x8F])) == "Á"
    assert dc.decode_cwi2(bytes([0x95])) == "Ó"
    assert dc.decode_cwi2(bytes([0x90])) == "É"      # CP437-örökség
    assert dc.decode_cwi2(bytes([0xA7])) == "Ő"
    assert dc.decode_cwi2(bytes([0x96])) == "ű"


def test_nyers_cwi_oda_vissza():
    raw = _to_cwi(MINTA)
    assert dc.decode_cwi2(raw) == MINTA
    assert dc._auto_decode(raw) == MINTA             # az auto is eltalálja


def _cp1250_engedekeny(raw: bytes) -> str:
    """Úgy „olvassuk" CP1250-ként, ahogy a valós engedékeny eszközök: a
    definiálatlan bájt a C1-kódpontjára képződik (így keletkezett Laci
    fájljában a U+0090), nem pótlójelre."""
    out = []
    for b in raw:
        try:
            out.append(bytes([b]).decode("cp1250"))
        except UnicodeDecodeError:
            out.append(chr(b))
    return "".join(out)


def test_kettos_kodolas_visszafejtese():
    """CWI bájtok → (tévesen) CP1250-ként olvasva → UTF-8-ként mentve =
    érvényes UTF-8 kacat; az autónak és a kézi CWI-nek is helyre kell állítania."""
    raw = _to_cwi(MINTA)
    moji = _cp1250_engedekeny(raw).encode("utf-8")
    # a mojibake C1-vezérlőt tartalmaz → biztos jel
    assert dc._has_c1_controls(moji.decode("utf-8"))
    assert dc._auto_decode(moji) == MINTA
    assert dc.read_cwi(moji) == MINTA


def test_tiszta_utf8_erintetlen():
    tiszta = "Árvíztűrő tükörfúrógép — „idézet”, felsorolás • pont."
    assert not dc._has_c1_controls(tiszta)
    assert dc._auto_decode(tiszta.encode("utf-8")) == tiszta


def test_kimeneti_kodlapok_kozt_nincs_auto_cwi():
    """Kimenetként nem kínálható fel az auto és a (csak dekódolható) cwi2 —
    a 3.29.4-es „unknown encoding: auto" regressziója ellen."""
    kodok = [k for _, k in dc.OUT_ENCODINGS]
    assert "auto" not in kodok and "cwi2" not in kodok
    assert "utf-8" in kodok
