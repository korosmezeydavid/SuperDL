"""Melyik fájlt melyik SuperDL-rész, vagy melyik külső program nyitja.

Az alap: a zene a Zenelejátszót, a videó a feliratolvasót, a szöveg a
Super Editet, a könyv a Könyvolvasót. A Társítások menü ezt felülírhatja.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ALAP = {
    ".mp3": "zene", ".flac": "zene", ".wav": "zene", ".ogg": "zene",
    ".m4a": "zene", ".wma": "zene", ".aac": "zene",
    ".mp4": "felirat", ".mkv": "felirat", ".avi": "felirat",
    ".webm": "felirat", ".mov": "felirat", ".wmv": "felirat",
    ".txt": "superedit", ".md": "superedit", ".log": "superedit",
    ".epub": "konyv", ".pdf": "konyv", ".docx": "konyv",
}

CELOK = (
    ("zene", "SuperDL Zene"),
    ("felirat", "SuperDL feliratolvasó"),
    ("superedit", "Super Edit"),
    ("konyv", "Könyvolvasó"),
    ("rendszer", "A Windows alapértelmezett programja"),
    ("program", "Egy megadott program"),
)

_ABLAK = {
    "zene": "zene_module",
    "felirat": "felolvaso_module",
    "superedit": "superedit_module",
    "konyv": "reader_module",
}


def _fajl() -> Path:
    return Path.home() / ".superdl" / "fajlok" / "tarsitas.json"


def _egyeni() -> dict:
    ut = _fajl()
    if not ut.is_file():
        return {}
    try:
        adat = json.loads(ut.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return adat if isinstance(adat, dict) else {}


def kit(ut: str) -> str:
    return os.path.splitext(ut)[1].lower()


def beallitas(kiterjesztes: str) -> dict:
    kiterjesztes = kiterjesztes.lower()
    if not kiterjesztes.startswith("."):
        kiterjesztes = "." + kiterjesztes
    sajat = _egyeni().get(kiterjesztes)
    if isinstance(sajat, dict) and sajat.get("cel"):
        return sajat
    return {"cel": ALAP.get(kiterjesztes, "rendszer"), "program": ""}


def felirat(kiterjesztes: str) -> str:
    adat = beallitas(kiterjesztes)
    if adat["cel"] == "program" and adat.get("program"):
        return "Program: %s" % os.path.basename(adat["program"])
    for kulcs, nev in CELOK:
        if kulcs == adat["cel"]:
            return nev
    return "A Windows alapértelmezett programja"


def ments(kiterjesztes: str, cel: str, program: str = "") -> None:
    kiterjesztes = kiterjesztes.lower()
    if not kiterjesztes.startswith("."):
        kiterjesztes = "." + kiterjesztes
    adat = _egyeni()
    adat[kiterjesztes] = {"cel": cel, "program": program}
    ut = _fajl()
    ut.parent.mkdir(parents=True, exist_ok=True)
    ut.write_text(json.dumps(adat, ensure_ascii=False, indent=2), encoding="utf-8")


def nyit(main, ut: str) -> str:
    """Megnyitja a fájlt a társítás szerint. A mondatot adja vissza."""
    if os.path.isdir(ut):
        return "Ez mappa, a listában nyílik meg."
    adat = beallitas(kit(ut))
    cel = adat.get("cel") or "rendszer"
    if cel == "program" and adat.get("program"):
        subprocess.Popen([adat["program"], ut],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return "Megnyitja: %s." % os.path.basename(adat["program"])
    if cel == "rendszer" or cel not in _ABLAK:
        os.startfile(ut)
        return "A Windows alapértelmezett programja nyitja."
    host = getattr(main, "_module_host", None)
    win = host.open_window(_ABLAK[cel]) if host else None
    if win is None:
        os.startfile(ut)
        return "Ez a SuperDL-rész nincs telepítve, a Windows nyitja."
    if hasattr(win, "open_file"):
        win.open_file(ut)
    return "Megnyitva a SuperDL-ben: %s." % felirat(kit(ut))
