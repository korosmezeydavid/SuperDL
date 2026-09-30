"""4.6.29 – Schibik Miklós (JAWS, 2026-09-30): induláskor a képernyőolvasó a
köszöntés dátumánál elhallgatott, mert 2,6 mp-cel később külön elhangzott a
„Jelenleg nincs aktív letöltés." és félbevágta. Az állapot már a köszöntés
része – külön bemondás nem kell."""
import ast
from pathlib import Path

GYOKER = Path(__file__).resolve().parents[1]


def _fuggveny(nev):
    forras = (GYOKER / "superdl_gui.py").read_text(encoding="utf-8")
    for n in ast.walk(ast.parse(forras)):
        if isinstance(n, ast.FunctionDef) and n.name == nev:
            return ast.get_source_segment(forras, n)
    raise AssertionError(nev + " nincs meg")


def _kod(src):
    return "\n".join(s for s in src.splitlines()
                     if not s.strip().startswith("#"))


def test_indulaskor_egyetlen_bemondas():
    kod = _kod(_fuggveny("_startup_greeting"))
    assert "_speak_dayinfo" in kod
    assert "CallLater" not in kod
    assert "speaker.speak" not in kod


def test_a_koszontes_tartalmazza_a_letoltesek_allapotat():
    assert "_download_status_phrase" in _fuggveny("_compose_dayinfo")
    from superdl import dayinfo
    szoveg = dayinfo.build_greeting(download_status="Jelenleg nincs aktív letöltésed.")
    assert szoveg.startswith("Üdvözöl a SuperDL!")
    assert szoveg.endswith("Jelenleg nincs aktív letöltésed.")
