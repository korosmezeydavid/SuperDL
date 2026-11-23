"""Két mappa összevetése egy mondatban, törlés nélkül."""

from __future__ import annotations

import os


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
