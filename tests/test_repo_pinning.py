"""selfupdate: a HIVATALOS frissítési forrás rögzítése (Tibi-audit 3.5).
Az átállítás (env/repo.txt) csak Fejlesztői módban érvényesül; anélkül a
program a hivatalos tárhelyet használja, és jelzi a figyelmen kívül hagyást."""

import pytest

su = pytest.importorskip("superdl.selfupdate")


@pytest.fixture
def izolalt(monkeypatch, tmp_path):
    """A teszt ne lássa a gép valódi repo.txt-jét / env-jét / beállításait."""
    monkeypatch.delenv("SUPERDL_REPO", raising=False)
    monkeypatch.setattr(su, "_repo_file_candidates", lambda: [])
    monkeypatch.setattr(su, "_dev_custom_repo_enabled", lambda: False)
    return tmp_path


def test_alapbol_hivatalos(izolalt):
    assert su.get_repo() == su.DEFAULT_REPO
    assert su.repo_is_official()
    assert su.ignored_override() is None
    assert su.custom_repo_requested() is None


def test_env_atallitas_dev_mod_nelkul_nem_ervenyesul(izolalt, monkeypatch):
    monkeypatch.setenv("SUPERDL_REPO", "gonosz/HamisRepo")
    assert su.custom_repo_requested() == "gonosz/HamisRepo"
    assert su.get_repo() == su.DEFAULT_REPO          # RÖGZÍTVE a hivatalos
    assert su.repo_is_official()
    assert su.ignored_override() == "gonosz/HamisRepo"   # de jelezzük


def test_repo_txt_dev_mod_nelkul_nem_ervenyesul(izolalt, monkeypatch, tmp_path):
    f = tmp_path / "repo.txt"
    f.write_text("masik/Repo", encoding="utf-8")
    monkeypatch.setattr(su, "_repo_file_candidates", lambda: [f])
    assert su.get_repo() == su.DEFAULT_REPO
    assert su.ignored_override() == "masik/Repo"


def test_dev_modban_ervenyesul_de_nem_hivatalos(izolalt, monkeypatch):
    monkeypatch.setenv("SUPERDL_REPO", "sajat/TesztRepo")
    monkeypatch.setattr(su, "_dev_custom_repo_enabled", lambda: True)
    assert su.get_repo() == "sajat/TesztRepo"        # dev-mód: érvényesül
    assert not su.repo_is_official()                 # → hangos figyelmeztetés jár
    assert su.ignored_override() is None


def test_hivatalos_ertekre_allitas_nem_szamit_atallitasnak(izolalt, monkeypatch):
    monkeypatch.setenv("SUPERDL_REPO", su.DEFAULT_REPO)
    assert su.get_repo() == su.DEFAULT_REPO
    assert su.repo_is_official()
    assert su.ignored_override() is None             # nincs mit jelezni
