"""CLI kilépési kódok (0/1/2/3/4/5) — a superdl.py-t fájlként töltjük be,
mert a `superdl` NÉV a csomagot jelenti (árnyékolás)."""

import importlib.util
import types
from pathlib import Path

import pytest

_CLI = Path(__file__).resolve().parent.parent / "superdl.py"


@pytest.fixture(scope="module")
def cli():
    spec = importlib.util.spec_from_file_location("superdl_cli", _CLI)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:          # hiányzó opcionális függőség CI-n → skip
        pytest.skip(f"CLI nem tölthető be: {e}")
    return mod


def _job(status, error=""):
    j = types.SimpleNamespace()
    j.url = "u"
    j.progress = types.SimpleNamespace(status=status, error=error,
                                       filename="f")
    return j


def test_exit_kodok(cli):
    J = _job
    assert cli._exit_code([J("kész"), J("kész")]) == 0
    assert cli._exit_code([J("kész"), J("hiba", "HTTP Error 403")]) == 5
    assert cli._exit_code([J("hiba", "getaddrinfo failed"),
                           J("hiba", "timed out")]) == 2
    assert cli._exit_code([J("hiba", "[Errno 13] Permission denied"),
                           J("hiba", "No space left")]) == 3
    assert cli._exit_code([J("hiba", "Unsupported URL: x")]) == 4
    assert cli._exit_code([J("hiba", "getaddrinfo failed"),
                           J("hiba", "valami más")]) == 1     # vegyes ok


def test_classify_magyar_uzenetekre_is(cli):
    assert cli._classify_error("ELFOGYOTT A HELY a lemezen") == 3
    assert cli._classify_error("HÁLÓZATI HIBA: az oldal nem érhető el") == 2
    assert cli._classify_error("Ezt a linket a motor NEM TÁMOGATJA") == 4
