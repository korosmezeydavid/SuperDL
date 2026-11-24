"""Tömörítés, kibontás és önkibontó. Egy fájl egyszerre kerül a csomagba."""

from __future__ import annotations

import os
import shutil
import tarfile
import zipfile


FORMAK = ("zip", "tar.gz", "tar.bz2", "tar.xz", "7z")


def fajlok_alatta(utak) -> list[tuple[str, str]]:
    """(lemez_út, név a csomagban) párok, egyenként."""
    ki = []
    for ut in utak:
        ut = os.path.abspath(ut)
        if os.path.isfile(ut):
            ki.append((ut, os.path.basename(ut)))
            continue
        gyoker_nev = os.path.basename(ut.rstrip("\\/"))
        for mappa, _almappak, nevek in os.walk(ut):
            for nev in nevek:
                teljes = os.path.join(mappa, nev)
                rel = os.path.relpath(teljes, os.path.dirname(ut))
                ki.append((teljes, rel))
        if not any(nev.startswith(gyoker_nev) for _t, nev in ki):
            pass
    return ki


def tomorit(utak, cel: str, forma: str) -> str:
    forma = forma.lower()
    if forma not in FORMAK:
        raise RuntimeError("Ismeretlen formátum: %s" % forma)
    parok = fajlok_alatta(utak)
    if not parok:
        raise RuntimeError("Nincs mit becsomagolni.")
    os.makedirs(os.path.dirname(os.path.abspath(cel)) or ".", exist_ok=True)
    if forma == "zip":
        with zipfile.ZipFile(cel, "w", compression=zipfile.ZIP_DEFLATED) as csomag:
            for teljes, nev in parok:
                csomag.write(teljes, nev)
    elif forma == "7z":
        _hetzet(parok, cel)
    else:
        mod = {"tar.gz": "w:gz", "tar.bz2": "w:bz2", "tar.xz": "w:xz"}[forma]
        with tarfile.open(cel, mod) as csomag:
            for teljes, nev in parok:
                csomag.add(teljes, arcname=nev, recursive=False)
    return cel


def kibont(arch: str, cel_mappa: str) -> int:
    os.makedirs(cel_mappa, exist_ok=True)
    nev = arch.lower()
    if nev.endswith(".zip"):
        with zipfile.ZipFile(arch) as csomag:
            _biztonsagos_nevek(csomag.namelist())
            csomag.extractall(cel_mappa)
            return len(csomag.namelist())
    if nev.endswith(".7z"):
        return _hetzet_ki(arch, cel_mappa)
    mod = "r:*"
    with tarfile.open(arch, mod) as csomag:
        tagok = csomag.getmembers()
        _biztonsagos_nevek([t.name for t in tagok])
        csomag.extractall(cel_mappa)
        return len(tagok)


def tartalom(arch: str) -> list[str]:
    nev = arch.lower()
    if nev.endswith(".zip"):
        with zipfile.ZipFile(arch) as csomag:
            return csomag.namelist()
    if nev.endswith(".7z"):
        return _hetzet_lista(arch)
    with tarfile.open(arch, "r:*") as csomag:
        return [t.name for t in csomag.getmembers() if t.isfile()]


def onkibonto(utak, cel_alap: str) -> tuple[str, str, str]:
    """Zip, indító parancsfájl és tartalomjegyzék. A parancsfájl a zipet kibontja."""
    zip_ut = cel_alap + ".zip"
    indito = cel_alap + "-onkibonto.cmd"
    jegyzek = cel_alap + "-tartalom.txt"
    tomorit(utak, zip_ut, "zip")
    nevek = tartalom(zip_ut)
    jegyzek_szoveg = "Tartalom, %d fájl:\n%s\n" % (len(nevek), "\n".join(nevek))
    with open(jegyzek, "w", encoding="utf-8") as ki:
        ki.write(jegyzek_szoveg)
    zip_nev = os.path.basename(zip_ut)
    with open(indito, "w", encoding="utf-8") as ki:
        ki.write(
            "@echo off\r\n"
            "cd /d \"%%~dp0\"\r\n"
            "echo Kibontas: %s\r\n"
            "tar -xf \"%s\"\r\n"
            "if errorlevel 1 (\r\n"
            "  echo A kibontas nem sikerult.\r\n"
            "  pause\r\n"
            "  exit /b 1\r\n"
            ")\r\n"
            "echo Kesz. A fajlok ebbe a mappaba kerultek.\r\n"
            "pause\r\n" % (zip_nev, zip_nev))
    return indito, zip_ut, jegyzek


def _biztonsagos_nevek(nevek) -> None:
    for nev in nevek:
        if nev.startswith(("/", "\\")) or ".." in nev.replace("\\", "/").split("/"):
            raise RuntimeError("A csomag kilógó útvonalat tartalmaz: %s" % nev)


def _hetzet(parok, cel: str) -> None:
    program = shutil.which("7z")
    if not program:
        raise RuntimeError(
            "A 7z formátumhoz a 7-Zip nincs a gépen. A zip, a tar.gz, "
            "a tar.bz2 és a tar.xz megy nélküle.")
    lista = cel + ".lista.txt"
    with open(lista, "w", encoding="utf-8") as ki:
        for teljes, _nev in parok:
            ki.write(teljes + "\n")
    try:
        import subprocess
        kesz = subprocess.run(
            [program, "a", "-y", "-bb0", cel, "@" + lista],
            capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if kesz.returncode != 0:
            raise RuntimeError(kesz.stderr.strip() or "A 7-Zip nem csomagolt.")
    finally:
        try:
            os.remove(lista)
        except OSError:
            pass


def _hetzet_ki(arch, cel) -> int:
    program = shutil.which("7z")
    if not program:
        raise RuntimeError("A 7z kibontásához a 7-Zip kell.")
    import subprocess
    kesz = subprocess.run(
        [program, "x", "-y", "-o" + cel, arch], capture_output=True, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if kesz.returncode != 0:
        raise RuntimeError(kesz.stderr.strip() or "A 7-Zip nem bontott ki.")
    return len(tartalom_helyi(cel))


def tartalom_helyi(mappa) -> list[str]:
    ki = []
    for gyoker, _a, nevek in os.walk(mappa):
        for nev in nevek:
            ki.append(os.path.join(gyoker, nev))
    return ki


def _hetzet_lista(arch) -> list[str]:
    program = shutil.which("7z")
    if not program:
        raise RuntimeError("A 7z listájához a 7-Zip kell.")
    import subprocess
    kesz = subprocess.run([program, "l", "-ba", arch], capture_output=True, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if kesz.returncode != 0:
        raise RuntimeError("A 7z lista nem készült el.")
    return [sor.strip() for sor in kesz.stdout.splitlines() if sor.strip()]
