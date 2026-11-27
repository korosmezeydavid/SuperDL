"""Két mappa összevetése egy mondatban, törlés nélkül."""

from __future__ import annotations

import os
import hashlib
import stat
import tempfile
from collections import defaultdict
from pathlib import Path


def _keszlet(gyoker: str) -> dict[str, float]:
    ki = {}
    for mappa, _almappak, nevek in os.walk(gyoker):
        for nev in nevek:
            teljes = os.path.join(mappa, nev)
            rel = os.path.normcase(os.path.relpath(teljes, gyoker))
            try:
                ki[rel] = os.path.getmtime(teljes)
            except OSError:
                ki[rel] = 0
    return ki


def mondat(elso: str, masodik: str) -> str:
    a = _keszlet(elso)
    b = _keszlet(masodik)
    csak_elso = [n for n in a if n not in b]
    csak_masodik = [n for n in b if n not in a]
    ujabb = [n for n in a if n in b and a[n] > b[n] + 1]
    return ("Csak az első helyen: %d fájl. Csak a másodikon: %d fájl. "
            "Mindkettőn megvan, és az első az újabb: %d fájl. "
            "Semmit nem töröltem."
            % (len(csak_elso), len(csak_masodik), len(ujabb)))

def _digest(path, cancel):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            if cancel():
                raise InterruptedError("Az összevetés megszakadt.")
            result.update(block)
    return result.digest()


def _fajlok(root, cancel):
    def bejarasi_hiba(error):
        raise error

    def atiranyitas(path):
        return path.is_symlink() or getattr(path, "is_junction", lambda: False)()

    result = {}
    for folder, dirs, files in os.walk(root, onerror=bejarasi_hiba):
        if cancel():
            raise InterruptedError("Az összevetés megszakadt.")
        base = Path(folder)
        dirs[:] = [name for name in dirs if not atiranyitas(base / name)]
        for name in files:
            path = base / name
            if not atiranyitas(path) and path.is_file():
                rel = path.relative_to(root)
                result[os.path.normcase(str(rel))] = (path, rel)
    return result


def elteresek(elso, masodik, cancel=lambda: False):
    """Két helyi mappa eltérései, relatív útvonallal és másolható forrással."""
    a, b = (_fajlok(Path(root), cancel) for root in (elso, masodik))
    rows = []
    for key in sorted(a.keys() | b.keys()):
        if cancel():
            raise InterruptedError("Az összevetés megszakadt.")
        if key not in a:
            _, rel = b[key]
            rows.append(("Csak a másodikban", rel, None))
        elif key not in b:
            path, rel = a[key]
            rows.append(("Csak az elsőben", rel, path))
        else:
            first, rel = a[key]
            other, _ = b[key]
            if first.stat().st_size != other.stat().st_size or _digest(first, cancel) != _digest(other, cancel):
                rows.append(("Eltérő tartalom", rel, None))
    return rows


def masolatok(gyoker, cancel=lambda: False):
    """Méret, majd SHA-256 alapján csoportosítja az azonos fájlokat."""
    meretek = defaultdict(list)
    azonosito = set()
    for path, _ in _fajlok(Path(gyoker), cancel).values():
        if cancel():
            raise InterruptedError("A keresés megszakadt.")
        info = path.stat()
        key = (info.st_dev, info.st_ino)
        if info.st_ino and key in azonosito:
            continue
        if info.st_ino:
            azonosito.add(key)
        meretek[info.st_size].append(path)
    csoportok = []
    for meret, utak in meretek.items():
        if len(utak) < 2:
            continue
        kivonatok = defaultdict(list)
        for path in utak:
            if cancel():
                raise InterruptedError("A keresés megszakadt.")
            kivonatok[_digest(path, cancel)].append(path)
        csoportok.extend((meret, sorted(group)) for group in kivonatok.values()
                        if len(group) > 1)
    return sorted(csoportok, key=lambda g: (-g[0], str(g[1][0]).casefold()))

def szinkron_tetel(forras, celmappa, relativ, cancel):
    """Hiányzó fájl másolása az almappaszerkezet megtartásával."""
    root = Path(celmappa).resolve(strict=True)
    if relativ.anchor or not relativ.parts or ".." in relativ.parts:
        raise ValueError("Érvénytelen célútvonal.")
    target = root
    for part in relativ.parts[:-1]:
        target = target / part
        target.mkdir(exist_ok=True)
        info = target.lstat()
        if (not stat.S_ISDIR(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise OSError(f"Átirányított vagy érvénytelen célmappa: {target}")
    target = target / relativ.name
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as out:
        stage = Path(out.name)
        try:
            with forras.open("rb") as src:
                for block in iter(lambda: src.read(1024 * 1024), b""):
                    if cancel():
                        raise InterruptedError("A szinkron megszakadt.")
                    out.write(block)
            out.close()
            if cancel():
                raise InterruptedError("A szinkron megszakadt.")
            if os.name == "nt":
                stage.rename(target)
            else:
                os.link(stage, target)
        finally:
            out.close()
            stage.unlink(missing_ok=True)
