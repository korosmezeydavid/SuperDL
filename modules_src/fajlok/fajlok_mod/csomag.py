"""Tömörítés, kibontás és önkibontó. Egy fájl egyszerre kerül a csomagba."""

from __future__ import annotations

import os
import subprocess
import tempfile
import tarfile
import zipfile


FORMAK = ("zip", "tar.gz", "tar.bz2", "tar.xz", "7z")
PROFILOK = {"Gyors": 1, "Alap": None, "Erős": 9}
_WINDOWS_ARCHIVES = (".7z", ".rar", ".cab", ".iso", ".cpio", ".lha", ".lzh")


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


def tomorit(utak, cel: str, forma: str, profil: str = "Alap") -> str:
    forma = forma.lower()
    if forma not in FORMAK:
        raise RuntimeError("Ismeretlen formátum: %s" % forma)
    fokozat = PROFILOK[profil]
    parok = fajlok_alatta(utak)
    if not parok:
        raise RuntimeError("Nincs mit becsomagolni.")
    os.makedirs(os.path.dirname(os.path.abspath(cel)) or ".", exist_ok=True)
    if forma == "zip":
        with zipfile.ZipFile(cel, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=fokozat) as csomag:
            for teljes, nev in parok:
                csomag.write(teljes, nev)
    elif forma == "7z":
        _hetzet(parok, cel, fokozat)
    else:
        mod = {"tar.gz": "w:gz", "tar.bz2": "w:bz2", "tar.xz": "w:xz"}[forma]
        beallitas = {}
        if fokozat is not None:
            kulcs = "preset" if forma == "tar.xz" else "compresslevel"
            beallitas[kulcs] = fokozat
        with tarfile.open(cel, mod, **beallitas) as csomag:
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
    if nev.endswith(_WINDOWS_ARCHIVES):
        names = tartalom(arch)
        _biztonsagos_nevek(names)
        _windows_tar("-xkf", os.path.abspath(arch), "-C", os.path.abspath(cel_mappa))
        return len(names)
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
    if nev.endswith(_WINDOWS_ARCHIVES):
        return _windows_tar("-tf", os.path.abspath(arch)).splitlines()
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


def _windows_tar(*args: str) -> str:
    program = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "tar.exe")
    if not os.path.isfile(program):
        raise RuntimeError("A Windows beépített archívumkezelője (tar.exe) nem érhető el.")
    result = subprocess.run(
        [program, *args], stdin=subprocess.DEVNULL, capture_output=True,
        encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "A Windows archívumművelete nem sikerült.")
    return result.stdout


def iso_fajl_kiment(arch, tag, cel):
    """A kijelölt ISO-tételt a felhasználó által megadott új fájlba írja."""
    if not str(arch).lower().endswith(".iso"):
        raise ValueError("ISO-fájlt válassz.")
    _biztonsagos_nevek([tag])
    if (not tag or tag.endswith("/") or any(c in tag for c in "*?[]"
            + chr(92)) or tartalom(str(arch)).count(tag) != 1):
        raise ValueError("A kijelölt ISO-tétel nem menthető egyértelműen.")
    program = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "tar.exe")
    kimenet = open(cel, "xb")
    try:
        with kimenet:
            result = subprocess.run(
                [program, "-xOf", os.path.abspath(arch), "--", tag],
                stdin=subprocess.DEVNULL, stdout=kimenet, stderr=subprocess.PIPE,
                timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            raise OSError("Az ISO-tétel kibontása sikertelen.")
    except (OSError, subprocess.SubprocessError):
        os.unlink(cel)
        raise


def _hetzet(parok, cel: str, fokozat: int | None) -> None:
    target = os.path.abspath(cel)
    with tempfile.TemporaryDirectory(dir=os.path.dirname(target)) as tmp:
        stage = os.path.join(tmp, "forras.tar")
        output = os.path.join(tmp, "csomag.7z")
        with tarfile.open(stage, "w") as archive:
            for teljes, nev in parok:
                archive.add(teljes, arcname=nev, recursive=False)
        opciok = () if fokozat is None else ("--options", f"7zip:compression-level={fokozat}")
        _windows_tar("-a", "-cf", output, *opciok, "@" + stage)
        os.replace(output, target)


def tartalom_helyi(mappa) -> list[str]:
    ki = []
    for gyoker, _a, nevek in os.walk(mappa):
        for nev in nevek:
            ki.append(os.path.join(gyoker, nev))
    return ki
