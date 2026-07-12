"""diagnostics: a hibajelentés-csomag TITOK-MENTESSÉGE (a 3.29.8 fő ígérete)."""

from pathlib import Path

import pytest

diagnostics = pytest.importorskip("superdl.diagnostics")


def test_install_kind_forrasbol():
    # a tesztek nem fagyasztott (frozen) környezetben futnak
    assert "forrásból" in diagnostics.install_kind()


def test_report_alapadatok():
    rep = diagnostics.build_report(settings={"connections": 8},
                                   log_lines=["próba-sor"])
    from superdl import __version__
    assert __version__ in rep
    assert "connections = 8" in rep
    assert "próba-sor" in rep


def test_report_nem_szivarogtat(monkeypatch):
    """A tárolt kulcsok (itt: hamisítottak) NEM jelenhetnek meg a jelentésben,
    a felhasználói mappa pedig ~ jelre cserélődik."""
    from superdl import store
    TITOK = "sk-EZ-EGY-HOSSZU-HAMIS-KULCS-123456"
    monkeypatch.setattr(store, "load_ai_config",
                        lambda: {"openai_key": TITOK})
    monkeypatch.setattr(store, "load_tts_keys", lambda: {})
    rep = diagnostics.build_report(
        settings={"cookies": "Firefox", "city": "Budapest",
                  "cookies_file": r"C:\x\cookies.txt"},
        log_lines=[f"a napló véletlenül tartalmazza: {TITOK}"])
    assert TITOK not in rep                       # maszkolva
    assert "KULCS-MASZKOLVA" in rep
    assert "Budapest" not in rep                  # city értéke soha
    assert str(Path.home()) not in rep            # home → ~
