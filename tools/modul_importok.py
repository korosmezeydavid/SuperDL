# -*- coding: utf-8 -*-
"""MELYIK modul-import hiányzik a fagyasztott csomagból?

⚠️ MIÉRT KELL EZ. A modulok ZIP-ből, futás közben töltődnek be, a Core sehol
nem importálja őket. Ezért a PyInstaller elemzője NEM LÁTJA, mit importálnak.
Ami kimarad, attól a modul nem hal meg látványosan: betöltődik vagy elindul,
és ImportError-ral omlik össze — ez a NEGYEDIK bajtípus, a „fut, de halott".
Így veszett el a 4.6.11 első buildjében a `plistlib` (iPhone modul).

HASZNÁLAT (build UTÁN, mert a TOC a buildből származik):
    python tools\\modul_importok.py
Kilépési kód 0 = nincs hiányzó; 2 = van, és a specbe fel kell venni.
"""

import ast
import io
import json
import os
import sys

GYOKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# Amit szándékosan nem kérünk számon: a saját csomagjaink és a forrásfa.
SAJAT = {"superdl", "superdl_gui", "modules_src"}


def modul_belepesek(gyoker) -> set:
    """A modulok BELÉPÉSI csomagjai (pl. `atjaro_mod`).

    Ezek nem külső könyvtárak: a modkit teszi őket a sys.path-ra a telepített
    modul mappájából. Egy modul hivatkozhat egy másikra ezen a néven, és az
    HELYES – nem a fagyasztott csomagban kell lenniük.
    """
    ki = set()
    ms = os.path.join(gyoker, "modules_src")
    if not os.path.isdir(ms):
        return ki
    for nev in os.listdir(ms):
        man = os.path.join(ms, nev, "manifest.json")
        if os.path.isfile(man):
            try:
                adat = json.loads(io.open(man, encoding="utf-8").read())
                if adat.get("entry"):
                    ki.add(adat["entry"].split(".")[0])
            except Exception:
                pass
    return ki


def modul_importok(gyoker=None) -> dict:
    """{importált név: {mely fájlok}} a modules_src teljes fájából."""
    gyoker = gyoker or GYOKER
    nevek = {}
    for tok, _d, fajlok in os.walk(os.path.join(gyoker, "modules_src")):
        for f in fajlok:
            if not f.endswith(".py"):
                continue
            ut = os.path.join(tok, f)
            try:
                fa = ast.parse(io.open(ut, encoding="utf-8").read())
            except Exception:
                continue          # a szintaktikai hibát a pytest fogja meg
            for cs in ast.walk(fa):
                if isinstance(cs, ast.Import):
                    for a in cs.names:
                        nevek.setdefault(a.name.split(".")[0], set()).add(ut)
                elif isinstance(cs, ast.ImportFrom):
                    if cs.level == 0 and cs.module:
                        nevek.setdefault(cs.module.split(".")[0],
                                         set()).add(ut)
    return nevek


def hianyzik(toc_szoveg: str, nevek: dict, gyoker=None) -> list:
    belepesek = modul_belepesek(gyoker or GYOKER)
    ki = []
    for nev in sorted(nevek):
        if nev in SAJAT or nev in belepesek or nev.startswith("_"):
            continue
        if nev in sys.builtin_module_names:
            continue
        if ("'%s'" % nev) in toc_szoveg or ("'%s." % nev) in toc_szoveg:
            continue
        ki.append(nev)
    return ki


def main() -> int:
    toc_ut = os.path.join(GYOKER, "build", "SuperDL", "Analysis-00.toc")
    if not os.path.exists(toc_ut):
        print("Nincs build (Analysis-00.toc) – előbb építeni kell.")
        return 1
    toc = io.open(toc_ut, encoding="utf-8", errors="replace").read()
    nevek = modul_importok()
    hi = hianyzik(toc, nevek)
    print("Modul-importok összesen: %d" % len(nevek))
    if not hi:
        print("TISZTA – minden modul-import benne van a csomagban.")
        return 0
    print("HIÁNYZIK a fagyasztott csomagból (a specbe fel kell venni):")
    for nev in hi:
        honnan = sorted(nevek[nev])[:3]
        print("   %s  <-  %s" % (nev, ", ".join(
            os.path.relpath(h, GYOKER) for h in honnan)))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
