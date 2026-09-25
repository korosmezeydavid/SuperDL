"""A build-őr (tools/build_ellenor.py) – 4.6.18, 4.6.19.

⚠️ Farkas István (2026-09-24): „a helyben futó fordító jelenleg nem jelenik
meg". A 4.6.12 óta a build-értelmezőben nem volt ctranslate2, és a
PyInstaller NÉMÁN kihagyta. Turai László ugyanaznap: a fájlküldés elhasalt,
mert a magic-wormhole ugyanígy hiányzott. Ez a teszt azt őrzi, hogy az őr a
kritikus részeket tényleg nézi, és a hiányt tényleg jelzi."""
import importlib.util
from pathlib import Path

GYOKER = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "build_ellenor", GYOKER / "tools" / "build_ellenor.py")
BE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BE)


def _build(gy: Path, kihagy=(), ext=True):
    """Egy ál-_internal mappa mindennel, ami a KELL-ben van."""
    for nev, mappa, _ in BE.KELL:
        if nev in kihagy or mappa in kihagy:
            continue
        d = gy / mappa
        d.mkdir(exist_ok=True)
        (d / "__init__.py").write_text("")
        if "." in nev:
            f = gy.joinpath(*nev.split(".")).with_suffix(".py")
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("")
    if ext and "ctranslate2" not in kihagy:
        (gy / "ctranslate2" / "_ext.cp314-win_amd64.pyd").write_bytes(b"x")


def test_az_or_a_forditot_a_pdf_et_es_a_fajlkuldest_is_nezi():
    nevek = {n for n, _, _ in BE.KELL}
    assert {"pdfminer", "ctranslate2", "sentencepiece", "sacremoses",
            "joblib", "wormhole", "twisted",
            "cryptography.hazmat.primitives.kdf.hkdf"} <= nevek


def test_ures_build_hianyt_jelez(tmp_path):
    assert BE.utana(str(tmp_path)) == 1


def test_teljes_build_rendben(tmp_path):
    _build(tmp_path)
    assert BE.utana(str(tmp_path)) == 0


def test_a_ctranslate2_ures_heja_nem_eleg(tmp_path):
    """⚠️ A 4.6.17-es buildben pont ez volt: a fordító a program szerint
    „hiányosan települt". Egy mappa a natív motor nélkül nem fordító."""
    _build(tmp_path, ext=False)
    assert BE.utana(str(tmp_path)) == 1


def test_a_cryptography_mappa_a_kdf_nelkul_nem_eleg(tmp_path):
    """⚠️ Turai László hibája: a cryptography mappa ott volt, a kdf nem."""
    _build(tmp_path, kihagy=("cryptography.hazmat.primitives.kdf.hkdf",))
    (tmp_path / "cryptography").mkdir(exist_ok=True)
    (tmp_path / "cryptography" / "__init__.py").write_text("")
    assert BE.utana(str(tmp_path)) == 1


def test_a_tisztan_python_csomagot_a_pyz_ben_is_megtalalja(tmp_path,
                                                          monkeypatch):
    """⚠️ A joblib NEM mappaként, hanem a PYZ-archívumban van – az első
    változatom ezt hamisan hiányzónak mondta."""
    _build(tmp_path, kihagy=("joblib",))
    monkeypatch.setattr(BE, "pyz_nevek", lambda p: {"joblib", "joblib.parallel"})
    assert BE.utana(str(tmp_path), "valami.pyz") == 0


def test_az_almodult_a_pyz_ben_is_megtalalja(tmp_path, monkeypatch):
    nev = "cryptography.hazmat.primitives.kdf.hkdf"
    _build(tmp_path, kihagy=(nev,))
    monkeypatch.setattr(BE, "pyz_nevek", lambda p: {nev})
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


def test_a_telepito_torli_a_regi_internalt():
    """⚠️ Turai László: a régi telepítésből ottmaradt wormhole-mappa akadt
    össze az új könyvtárakkal. Az Inno magától nem töröl."""
    iss = (GYOKER / "SuperDL.iss").read_text(encoding="utf-8")
    assert "[InstallDelete]" in iss
    blokk = iss.split("[InstallDelete]", 1)[1].split("\n[", 1)[0]
    assert 'Name: "{app}\\_internal"' in blokk
