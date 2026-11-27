"""A kétpaneles tallózó menthető felvétel-archiválása."""

import os
import re
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path


def beallitas():
    return Path.home() / ".superdl" / "fajlok" / "archivalas.txt"


def mentett_nevek():
    regi = beallitas()
    uj = regi.with_name("archivalas-sablonok.txt")
    ut = uj if uj.exists() else regi
    if not ut.exists():
        return []
    return [nev_ellenorzes(sor) for sor in ut.read_text(encoding="utf-8").splitlines()
            if sor.strip()]


def nev_mentese(nev):
    nev = nev_ellenorzes(nev)
    nevek = {n.casefold(): n for n in mentett_nevek()}
    nevek[nev.casefold()] = nev
    ut = beallitas().with_name("archivalas-sablonok.txt")
    ut.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=ut.parent,
                                     delete=False) as fajl:
        ideiglenes = Path(fajl.name)
        try:
            fajl.write("\n".join(nevek.values()) + "\n")
            fajl.close()
            os.replace(ideiglenes, ut)
        finally:
            fajl.close()
            ideiglenes.unlink(missing_ok=True)


def nev_ellenorzes(nev):
    nev = nev.strip()
    if not re.fullmatch(r"[\w -]{1,60}", nev):
        raise ValueError("A művelet neve 1–60 betűt, számot, szóközt vagy kötőjelet tartalmazhat.")
    return nev


def terv(utak, cel, nev):
    if not Path(cel).is_dir():
        raise ValueError("A másik panelen nyiss meg egy helyi célmappát.")
    cel = Path(cel) / (nev_ellenorzes(nev) + ".zip")
    if os.path.lexists(cel):
        raise FileExistsError(f"Már létezik: {cel}. Adj másik nevet a műveletnek.")
    elemek = []
    nevek = set()
    for ut in map(Path, utak):
        if not ut.is_file():
            raise ValueError("Az archiváláshoz fájlokat jelölj ki.")
        datum = datetime.fromtimestamp(ut.stat().st_mtime).strftime("%Y-%m-%d")
        tag = f"{datum} - {ut.name}"
        if tag.casefold() in nevek:
            raise ValueError(f"Névütközés a csomagban: {tag}")
        nevek.add(tag.casefold())
        elemek.append((ut, tag))
    if not elemek:
        raise ValueError("Jelölj ki legalább egy fájlt.")
    return cel, elemek


def futtat(cel, elemek, megszakit):
    fd, ideiglenes = tempfile.mkstemp(dir=cel.parent, suffix=".tmp")
    os.close(fd)
    try:
        with zipfile.ZipFile(ideiglenes, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            for ut, tag in elemek:
                if megszakit():
                    return False
                zipf.write(ut, tag)
        if megszakit():
            return False
        if os.name == "nt":
            os.rename(ideiglenes, cel)
        else:
            os.link(ideiglenes, cel)
        return True
    finally:
        Path(ideiglenes).unlink(missing_ok=True)
