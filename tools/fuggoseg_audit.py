# -*- coding: utf-8 -*-
"""Függőség-ellenőrzés: melyik KÜLSŐ csomagot importálja a forrás úgy, hogy a
`requirements.txt` nem sorolja fel.

MIÉRT KELL. A `cryptography` hónapokig hiányzott a requirements-ből, pedig a
mentés-modul használta. A fejlesztői gépen véletlenül telepítve volt, tehát
helyben minden zöld volt — a CI viszont minden pushnál elbukott rajta, és egy
tiszta gépen épült program CSENDBEN nem tudott volna mentést készíteni.

⚠️ Ez a szkript SZÁNDÉKOSAN nem hibázik el a hiányra: tájékoztat. A cél nem az,
hogy megakassza a munkát, hanem hogy a hiány LÁTHATÓ legyen — mert pontosan az
a baj vele, hogy nem látszik.

Használat:  python tools\fuggoseg_audit.py
"""

import ast
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")

GYOKER = Path(__file__).resolve().parent.parent

# Amit a Python maga hoz, vagy a mi saját kódunk – ezekre nem kell csomag.
SAJAT = {"superdl", "superdl_gui", "tests", "tools", "modules_src",
         "kozos"}          # tools/brailab_hangolas helyi segédmodulja

# SZÁNDÉKOSAN opcionális csomagok: a kód `try: import …` mögött használja őket,
# és hiányukban VAN értelmes viselkedés (letöltésre ajánlja, vagy más motorra
# vált). Ezeknek NEM szabad a requirements-ben lenniük — több száz megabájt
# volna, és mindenki fizetné, aki nem használja.
#
# ⚠️ De a listát INDOKOLNI kell, mert enélkül ez a fájl pont olyanná válna, mint
# a piros CI: mindenki átlapozza. Ha valami ide kerül, ott a magyarázat is.
OPCIONALIS = {
    "ctranslate2": "helyben futó fordító – igény szerint tölthető (offlineford)",
    "sentencepiece": "a fordítómodell tokenizálója – a fordítóval együtt jön",
    "sacremoses": "a fordítómodell tokenizálója – a fordítóval együtt jön",
    "subword_nmt": "a fordítómodell tokenizálója – a fordítóval együtt jön",
    "wormhole": "magic-wormhole fájlátadás – csak ha a felhasználó használja",
    "comtypes": "NVDA/JAWS és WASAPI COM-hívások – Windows-specifikus, a wx és "
                "a pywin32 hozza",
}

# Importnév -> csomagnév a requirements-ben (ahol a kettő nem egyezik).
NEVEK = {
    "wx": "wxpython",
    "bs4": "beautifulsoup4",
    "docx": "python-docx",
    "fitz": "pymupdf",
    "yaml": "pyyaml",
    "PIL": "pillow",
    "win32com": "pywin32",
    "win32api": "pywin32",
    "win32gui": "pywin32",
    "win32con": "pywin32",
    "pythoncom": "pywin32",
    "win32crypt": "pywin32",
    "certifi": "requests",          # a requests hozza magával
    "fpdf": "fpdf2",
    "edge_tts": "edge-tts",
    "yt_dlp": "yt-dlp",
    "sounddevice": "sounddevice",
    "dateutil": "python-dateutil",
    "serial": "pyserial",
}


def felso_szintu(nev: str) -> str:
    return (nev or "").split(".")[0]


def importok(ut: Path) -> set[str]:
    try:
        fa = ast.parse(ut.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    ki = set()
    for csomo in ast.walk(fa):
        if isinstance(csomo, ast.Import):
            for a in csomo.names:
                ki.add(felso_szintu(a.name))
        elif isinstance(csomo, ast.ImportFrom):
            # a relatív import (level > 0) a SAJÁT kódunk, nem külső csomag
            if csomo.level == 0 and csomo.module:
                ki.add(felso_szintu(csomo.module))
    return ki


def kovetelmenyek() -> set[str]:
    ut = GYOKER / "requirements.txt"
    ki = set()
    for sor in ut.read_text(encoding="utf-8", errors="replace").splitlines():
        sor = sor.strip()
        if not sor or sor.startswith("#"):
            continue
        nev = re.split(r"[<>=!~\[; ]", sor, maxsplit=1)[0].strip().lower()
        if nev:
            ki.add(nev)
    return ki


def main() -> int:
    kell = kovetelmenyek()
    talalt: dict[str, set[str]] = {}
    for hova in ("superdl", "modules_src", "tools"):
        for f in (GYOKER / hova).rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            for nev in importok(f):
                talalt.setdefault(nev, set()).add(
                    str(f.relative_to(GYOKER)))
    for f in GYOKER.glob("*.py"):
        for nev in importok(f):
            talalt.setdefault(nev, set()).add(f.name)

    beepitett = set(sys.stdlib_module_names)
    hianyzik = {}
    opcionalisan = {}
    for nev, hol in sorted(talalt.items()):
        if nev in beepitett or nev in SAJAT or nev.startswith("_"):
            continue
        csomag = NEVEK.get(nev, nev).lower()
        if csomag in kell:
            continue
        if nev in OPCIONALIS:
            opcionalisan[nev] = OPCIONALIS[nev]
            continue
        hianyzik[nev] = (csomag, sorted(hol))

    if opcionalisan:
        print("Szándékosan opcionális (NEM kell a requirements-be):")
        for nev, miert in sorted(opcionalisan.items()):
            print(f"  {nev} – {miert}")
        print()

    if not hianyzik:
        print("Minden KÖTELEZŐ külső csomag szerepel a requirements.txt-ben.")
        return 0
    print("KÜLSŐ CSOMAG A KÓDBAN, DE NINCS A requirements.txt-BEN:")
    print()
    for nev, (csomag, hol) in hianyzik.items():
        print(f"  {nev}  (csomag: {csomag})")
        for h in hol[:4]:
            print(f"      {h}")
        if len(hol) > 4:
            print(f"      … és még {len(hol) - 4} helyen")
    print()
    print(f"Összesen {len(hianyzik)} tétel. Ha valamelyik szándékosan "
          "opcionális, vedd fel a SAJAT/NEVEK listába vagy a requirements-be.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
