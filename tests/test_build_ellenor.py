"""A build-őr (tools/build_ellenor.py) – 4.6.18.

⚠️ Farkas István (2026-09-24): „a helyben futó fordító jelenleg nem jelenik
meg". A 4.6.12 óta a build-értelmezőben nem volt ctranslate2, és a
PyInstaller NÉMÁN kihagyta. Ez a teszt azt őrzi, hogy az őr a kritikus
részeket tényleg nézi, és a hiányt tényleg jelzi."""
import importlib.util
from pathlib import Path

GYOKER = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "build_ellenor", GYOKER / "tools" / "build_ellenor.py")
BE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BE)


def test_az_or_a_forditot_es_a_pdf_et_is_nezi():
    nevek = {n for n, _, _ in BE.KELL}
    assert {"pdfminer", "ctranslate2", "sentencepiece", "sacremoses",
            "joblib"} <= nevek


def test_ures_build_hianyt_jelez(tmp_path):
    assert BE.utana(str(tmp_path)) == 1


def test_teljes_build_rendben(tmp_path):
    for _, mappa, _ in BE.KELL:
        d = tmp_path / mappa
        d.mkdir()
        (d / "__init__.py").write_text("")
    (tmp_path / "ctranslate2" / "_ext.cp314-win_amd64.pyd").write_bytes(b"x")
    assert BE.utana(str(tmp_path)) == 0


def test_a_ctranslate2_ures_heja_nem_eleg(tmp_path):
    """⚠️ A 4.6.17-es buildben pont ez volt: a fordító a program szerint
    „hiányosan települt". Egy mappa a natív motor nélkül nem fordító."""
    for _, mappa, _ in BE.KELL:
        d = tmp_path / mappa
        d.mkdir()
        (d / "__init__.py").write_text("")
    assert BE.utana(str(tmp_path)) == 1


def test_a_tisztan_python_csomagot_a_pyz_ben_is_megtalalja(tmp_path,
                                                          monkeypatch):
    """⚠️ A joblib NEM mappaként, hanem a PYZ-archívumban van – az első
    változatom ezt hamisan hiányzónak mondta."""
    for _, mappa, _ in BE.KELL:
        if mappa == "joblib":
            continue
        d = tmp_path / mappa
        d.mkdir()
        (d / "__init__.py").write_text("")
    (tmp_path / "ctranslate2" / "_ext.cp314-win_amd64.pyd").write_bytes(b"x")
    monkeypatch.setattr(BE, "pyz_nevek", lambda p: {"joblib", "joblib.parallel"})
    assert BE.utana(str(tmp_path), "valami.pyz") == 0


def test_a_kesz_program_onprobat_tud():
    """`SuperDL.exe --onproba <fájl>`: a FAGYASZTOTT programból is ki lehessen
    olvasni, hogy benne van-e a fordító és hány SAPI-hangot lát."""
    src = (GYOKER / "superdl_gui.py").read_text(encoding="utf-8")
    assert '"--onproba"' in src
    i = src.index('"--onproba"')
    assert "build_report" in src[i:i + 900]
    assert 'ENGINES["sapi"].voices()' in src[i:i + 1400]


def test_a_build_bat_hasznalja_az_ort():
    """A kiadási lépésekben az őr kötelező (HANDOFF). Itt csak azt nézzük,
    hogy a spec továbbra is gyűjti a fordítót."""
    for spec_nev in ("SuperDL.spec", "SuperDL-onedir.spec"):
        s = (GYOKER / spec_nev).read_text(encoding="utf-8")
        assert "ctranslate2" in s and "sacremoses" in s
