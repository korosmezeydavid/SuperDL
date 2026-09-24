"""BUILD-ŐR: a kiadás ELŐTT és UTÁN megnézi, hogy benne van-e minden, ami
némán kimaradhat.

⚠️ MIÉRT VAN (2026-09-24, Farkas István: „a helyben futó fordító jelenleg
nem jelenik meg"). Ezen a gépen KÉT Python 3.14 van:

  * ...\\Local\\Python\\pythoncore-3.14-64   – van benne ctranslate2 és társai,
                                               de NINCS pdfminer;
  * ...\\Local\\Programs\\Python\\Python314    – van benne pdfminer, de NEM
                                               volt ctranslate2.

A 4.6.12-ben a PDF-javítás miatt átálltunk a másodikra – és ezzel a helyben
futó fordító NÉMÁN kiesett a buildből. A PyInstaller nem szól, ha egy
`collect_all()` semmit nem talál; a program pedig (helyesen) elrejti a
funkciót, ha a futtatókörnyezet hiányos. Így öt kiadáson át senki nem vette
észre, csak a felhasználó.

Az őr kétféleképpen fut:

  python tools/build_ellenor.py --elotte   # a BUILD-ÉRTELMEZŐBEN: importálható-e
  python tools/build_ellenor.py            # a kész dist\\SuperDL\\_internal-ban

Kilépési kód: 0 = minden megvan, 1 = valami hiányzik (NE ADD KI).
"""
import importlib
import os
import sys

# (import-név, mappa a _internal alatt, miért kell)
KELL = [
    ("pdfminer", "pdfminer", "PDF-szöveg kinyerése (Könyvek, Dokumentum-konverter)"),
    ("ctranslate2", "ctranslate2", "helyben futó fordító – a motor"),
    ("sentencepiece", "sentencepiece", "helyben futó fordító – szótagoló"),
    ("sacremoses", "sacremoses", "helyben futó fordító – tokenizáló"),
    ("joblib", "joblib", "a sacremoses függősége"),
]


def elotte() -> int:
    baj = 0
    print("Build-értelmező:", sys.executable)
    for nev, _, miert in KELL:
        try:
            m = importlib.import_module(nev)
            if nev == "ctranslate2" and not hasattr(m, "Translator"):
                raise ImportError("nincs benne Translator")
            print("  OK    %-14s %s" % (nev, miert))
        except Exception as e:
            baj += 1
            print("  HIÁNY %-14s %s  (%s)" % (nev, miert, e))
    return 1 if baj else 0


def utana(gyoker: str) -> int:
    baj = 0
    print("Build:", gyoker)
    for nev, mappa, miert in KELL:
        ut = os.path.join(gyoker, mappa)
        van = os.path.isdir(ut) and any(os.scandir(ut))
        if nev == "ctranslate2" and van:
            # a motor maga egy natív kiterjesztés – a mappa lehet üres héj is
            van = any(f.name.startswith("_ext") and f.name.endswith(".pyd")
                      for f in os.scandir(ut))
        print("  %s %-14s %s" % ("OK   " if van else "HIÁNY", nev, miert))
        baj += 0 if van else 1
    return 1 if baj else 0


if __name__ == "__main__":
    if "--elotte" in sys.argv:
        sys.exit(elotte())
    gy = next((a for a in sys.argv[1:] if not a.startswith("-")),
              os.path.join("dist", "SuperDL", "_internal"))
    sys.exit(utana(gy))
