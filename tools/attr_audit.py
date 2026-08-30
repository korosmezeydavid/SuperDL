# -*- coding: utf-8 -*-
"""NÉVELCSÚSZÁS-AUDIT: kér-e valamelyik modul olyat a Core-tól, ami nincs?

Az a hibaosztály, amit a tvmusor kedvenc-emlékeztetője mutatott meg (2026-08-30,
Laci jelzése): a modul `getattr(core, "main", None)`-t hívott, a CoreContext
viszont `main_frame` néven adja a főablakot – a `getattr` alapértelmezése némán
elnyelte, és a funkció a megjelenése óta halott volt, MINDENKINÉL. Ugyanez a
névelcsúszás volt a „Napi infó nem indul" gyökere is (lásd a modkit
`frame`-aliasát).

Ez a hiba NÉMA: nem száll el, nem naplóz, csak nem történik meg – és a
felhasználó egy félrevezető üzenetet kap. Ezért kell rá gépi őr.

Használat:
    python tools\\attr_audit.py          # 0 = tiszta, 1 = van találat
A `tests\\test_modul_core_szerzodes.py` ugyanezt futtatja minden teszteléskor.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Minden objektumon meglévő nevek.
ALAP = {"__class__", "__dict__", "__doc__", "__module__", "__name__"}


def _osztaly_tagjai(path: Path, nev: str) -> set:
    """Egy osztály tagjai: metódusok, osztályszintű és `self.x = …` attribútumok."""
    if not path.exists():
        return set()
    fa = ast.parse(path.read_text(encoding="utf-8"))
    for n in ast.walk(fa):
        if isinstance(n, ast.ClassDef) and n.name == nev:
            ki = set()
            for b in n.body:
                if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    ki.add(b.name)
                elif isinstance(b, ast.Assign):
                    for t in b.targets:
                        if isinstance(t, ast.Name):
                            ki.add(t.id)
            for x in ast.walk(n):
                if (isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name)
                        and x.value.id == "self" and isinstance(x.ctx, ast.Store)):
                    ki.add(x.attr)
            return ki
    return set()


def _gyoker(csomopont):
    """A kifejezés utolsó neve: `self.core` → 'core', `main` → 'main'."""
    if isinstance(csomopont, ast.Name):
        return csomopont.id
    if isinstance(csomopont, ast.Attribute):
        return csomopont.attr
    return None


def _kivulrol_a_foablakra_tett_nevek() -> set:
    """Amit NEM a MainFrame törzse rak a főablakra.

    Két forrásból:

    a) **A Core, kívülről.** A `coremod.py` a modulrendszer betöltésekor a
       főablakra teszi a hostot és a betöltőt (`main._module_host = host`,
       `main._module_loader`, `main._module_bus`). Ezek a MainFrame osztály
       törzsében sehol nem szerepelnek, mégis léteznek – a könyvek modul
       jogosan használja őket (`_open_atjaro_send`).

    b) **A modulok maguk** (`self.main.X = …`). Ilyen a 23 örökölt
       `main._<modul>_win = None` takarítás is: a `register_window` óta a Core
       tartja nyilván az ablakokat (`WxHost._windows`), ezért ezeket a neveket
       már senki nem állítja be – a takarító sor HOLT, de ÁRTALMATLAN
       (`getattr(..., None) is self` sosem igaz). Nem hiba, csak zaj: ha nem
       szűrnénk ki, elfedné a VALÓDI találatokat.

    """
    ki = set()
    fajlok = list((ROOT / "modules_src").rglob("*.py"))
    fajlok += list((ROOT / "superdl").rglob("*.py"))
    fajlok.append(ROOT / "superdl_gui.py")
    for f in sorted(set(fajlok)):
        if not f.exists():
            continue
        try:
            fa = ast.parse(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for n in ast.walk(fa):
            if (isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)
                    and _gyoker(n.value) in ("main", "frame", "main_frame")):
                ki.add(n.attr)
    return ki


def szerzodes() -> tuple:
    """(amit a `core` ad, amit a `main` ad)."""
    core = (_osztaly_tagjai(ROOT / "superdl" / "modkit.py", "CoreContext")
            | _osztaly_tagjai(ROOT / "superdl" / "coremod.py", "WxHost"))
    main = (_osztaly_tagjai(ROOT / "superdl_gui.py", "MainFrame")
            | _kivulrol_a_foablakra_tett_nevek())
    return core, main


def _vizsgal_fa(rel: str, fa, ad: dict) -> list:
    talalatok = []
    for n in ast.walk(fa):
        # getattr(<…core|main>, "NEV", …)
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "getattr" and len(n.args) >= 2
                and isinstance(n.args[1], ast.Constant)
                and isinstance(n.args[1].value, str)):
            gy, nev = _gyoker(n.args[0]), n.args[1].value
            if gy in ad and nev not in ad[gy]:
                talalatok.append((rel, n.lineno, gy, nev, "getattr"))

        # core.NEV / self.core.NEV / main.NEV közvetlen olvasás
        if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load):
            gy = _gyoker(n.value)
            if gy in ad and n.attr not in ad[gy]:
                talalatok.append((rel, n.lineno, gy, n.attr, "közvetlen"))
    return talalatok


def vizsgal_forras(rel: str, forras: str) -> list:
    """Egy kódrészletet vizsgál a VALÓDI szerződéssel – ezzel igazolható,
    hogy az őr tényleg elkapja azt, amit el kell kapnia."""
    CORE, MAIN = szerzodes()
    ad = {"core": CORE | ALAP, "main": MAIN | ALAP}
    return sorted(set(_vizsgal_fa(rel, ast.parse(forras), ad)))


def vizsgal_mind() -> list:
    """[(fájl, sor, 'core'|'main', név, mód)] – minden gyanús hivatkozás."""
    CORE, MAIN = szerzodes()
    ad = {"core": CORE | ALAP, "main": MAIN | ALAP}
    talalatok = []

    for path in sorted((ROOT / "modules_src").rglob("*.py")):
        rel = str(path.relative_to(ROOT))
        try:
            fa = ast.parse(path.read_text(encoding="utf-8"))
        except Exception as e:
            talalatok.append((rel, 0, "?", "?", "NEM OLVASHATÓ: %s" % e))
            continue
        talalatok += _vizsgal_fa(rel, fa, ad)

    return sorted(set(talalatok))


def main() -> int:
    t = vizsgal_mind()
    for rel, sor, honnan, nev, mod in t:
        print("%s:%d  %s.%s  (%s) – a Core ezt NEM adja" % (rel, sor, honnan, nev, mod))
    print()
    print("Összesen %d gyanús hivatkozás." % len(t))
    return 1 if t else 0


if __name__ == "__main__":
    sys.exit(main())
