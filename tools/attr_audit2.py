# -*- coding: utf-8 -*-
"""KÉZI TRIÁZS-eszköz – NEM CI-őr, és SOHA nem ad hibás kilépési kódot.

A tág változat: minden `getattr(x, "NEV", …)`-t kilistáz, ahol a NEV a
projektben sehol nem szerepel értékadásként. Hasznos átnézni, de a találatok
NAGY RÉSZE jogos: `sys.frozen`, `sys._MEIPASS`, `subprocess.CREATE_NO_WINDOW`,
`proc.stdin/stdout/stderr`, `OSError.winerror`, argparse-mezők – ezek mind a
Pythonból/PyInstallerből jönnek, nem innen.

A gépi őr a szűk, pontos változat: `tools\\attr_audit.py`
(és a `tests\\test_modul_core_szerzodes.py`). Ezt itt kézzel futtatjuk, ha
gyanú van; a kimenetet EMBER nézi át.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORRASOK = [ROOT / "superdl", ROOT / "modules_src"]
EGYEB = [ROOT / "superdl_gui.py", ROOT / "superdl.py"]

# amit már megnéztünk és rendben van (Python/PyInstaller/argparse)
ISMERT_JO = {
    "frozen", "_MEIPASS", "CREATE_NO_WINDOW", "winerror",
    "stdin", "stdout", "stderr",
    "diagnose", "selftest_tts", "selftest_audio",
}


def _fajlok():
    for d in FORRASOK:
        yield from sorted(d.rglob("*.py"))
    for f in EGYEB:
        if f.exists():
            yield f


def _wx_nevek() -> set:
    ki = set(dir(object))
    try:
        import wx
        for nev in ("Window", "Frame", "Dialog", "Panel", "App", "Menu",
                    "MenuItem", "Timer", "ListBox", "TextCtrl", "Choice"):
            o = getattr(wx, nev, None)
            if o is not None:
                ki |= set(dir(o))
        ki |= set(dir(wx))
    except Exception:
        pass
    return ki


def main() -> int:
    letezo, keresett = set(), []
    for f in _fajlok():
        try:
            fa = ast.parse(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for n in ast.walk(fa):
            if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store):
                letezo.add(n.attr)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                letezo.add(n.name)
            elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                letezo.add(n.id)
            elif isinstance(n, ast.arg):
                letezo.add(n.arg)
            elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == "setattr" and len(n.args) >= 2
                  and isinstance(n.args[1], ast.Constant)
                  and isinstance(n.args[1].value, str)):
                letezo.add(n.args[1].value)

            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id == "getattr" and len(n.args) >= 2
                    and isinstance(n.args[1], ast.Constant)
                    and isinstance(n.args[1].value, str)):
                keresett.append((f.relative_to(ROOT), n.lineno, n.args[1].value))

    wx_nevek = _wx_nevek()
    db = 0
    for f, sor, nev in keresett:
        if (nev in letezo or nev in wx_nevek or nev in ISMERT_JO
                or nev.startswith("__")):
            continue
        print("%s:%d  getattr(..., %r)  – nézd meg: létezik ez a név?" % (f, sor, nev))
        db += 1
    print()
    print("%d átnézendő találat (ez NEM hibalista – ember dönt)." % db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
