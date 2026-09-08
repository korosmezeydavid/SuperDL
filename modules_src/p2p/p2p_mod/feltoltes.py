# -*- coding: utf-8 -*-
"""A tárhelyre feltöltés végrehajtása (2026-09-06).

Külön fájlban a `tarhely.py`-tól: ott a TUDÁS van (mit bír, meddig él, mit
mondunk róla), itt a MŰVELET. A tudás hálózat nélkül tesztelhető, a művelet nem
— ezt a határt a `lemezhely`/`report` párosnál már meghúztuk egyszer.
"""

from __future__ import annotations

import secrets
import threading
from pathlib import Path

import requests

from . import tarhely

# Néhány tárhely elutasítja a névtelen klienst. Megmondjuk, kik vagyunk —
# ez tisztességesebb is, mint böngészőnek álcázni magunkat.
FEJLEC = {"User-Agent": "SuperDL (+https://github.com/korosmezeydavid/SuperDL)"}


def _bin_nev() -> str:
    """Véletlen „bin"-azonosító a filebin.nethez.

    ⚠️ Elég hosszú ÉS véletlen kell legyen: a bin neve maga a titok. Egy
    kitalálható név (a fájl neve, dátum) azt jelentené, hogy idegenek
    belebotolhatnak a feltöltésbe."""
    return "sdl" + secrets.token_hex(10)

# Ennyi ideig várunk a szerver ELSŐ válaszára. A feltöltés maga ennél sokkal
# tovább tarthat (nagy fájl, lassú net), arra nincs korlát – csak arra, hogy a
# szerver egyáltalán szóba álljon velünk.
KAPCSOLAT_IDOKORLAT = 30


class Feltoltes:
    """Egy feltöltés, háttérszálon, megszakíthatóan.

    ⚠️ **A megszakítás nem csak a mi oldalunkon számít.** Ha félbehagyunk egy
    feltöltést, a tárhelyen maradhat egy fél fájl. Ahol a szolgáltató engedi a
    törlést (filebin, 0x0.st), ott meg is próbáljuk – ahol nem, ott ezt
    kimondjuk, nem hallgatjuk el.
    """

    def __init__(self, ut, cel: tarhely.Tarhely, halad=None, kesz=None):
        self.ut = Path(ut)
        self.cel = cel
        self.halad = halad
        self.kesz = kesz
        self._stop = threading.Event()
        self._szal = None
        self.link = ""
        self.torlo_kulcs = ""

    def start(self):
        self._szal = threading.Thread(target=self._run, daemon=True)
        self._szal.start()

    def cancel(self):
        self._stop.set()

    def _run(self):
        try:
            meret = self.ut.stat().st_size
            with self.ut.open("rb") as f:
                olvaso = _Figyelo(f, meret, self.halad, self._stop)
                if self.cel.mod == "bin":
                    # filebin.net: NEM űrlap, hanem NYERS TEST egy saját
                    # „bin"-be. A mérés (2026-09-08) mutatta meg: az
                    # általános multipart-feltöltés 400-at kapott, ez 201-et.
                    self._bin = _bin_nev()
                    cim = f"{self.cel.url}/{self._bin}/{self.ut.name}"
                    valasz = requests.post(
                        cim, data=olvaso,
                        headers={**FEJLEC,
                                 "Content-Type": "application/octet-stream",
                                 "Content-Length": str(meret)},
                        timeout=KAPCSOLAT_IDOKORLAT)
                    # a letöltési link maga a feltöltési cím
                    if valasz.status_code < 400:
                        self.link = cim
                        self.torlo_kulcs = f"{self.cel.url}/{self._bin}"
                        self._vege(True, cim)
                        return
                else:
                    fajlok = {self.cel.mezo: (self.ut.name, olvaso)}
                    valasz = requests.post(
                        self.cel.url, files=fajlok, data=dict(self.cel.extra),
                        headers=FEJLEC, timeout=KAPCSOLAT_IDOKORLAT)
        except _Megszakitva:
            self._vege(False, "A feltöltést leállítottad.")
            return
        except requests.RequestException as e:
            self._vege(False, f"A feltöltés nem sikerült: {e}")
            return
        except OSError as e:
            self._vege(False, f"A fájlt nem tudom elolvasni: {e}")
            return

        if valasz.status_code >= 400:
            self._vege(False, tarhely.hibauzenet(valasz.status_code,
                                                 self.cel.nev))
            return
        # A 0x0.st a törlési kulcsot fejlécben adja vissza – ez az egyetlen
        # módja, hogy később vissza tudjuk vonni a feltöltést.
        self.torlo_kulcs = valasz.headers.get("X-Token", "")
        self.link = tarhely.talalt_link(valasz.text)
        if not self.link:
            # ⚠️ A szerver 200-at adott, de nincs benne link. NEM mondjuk azt,
            # hogy sikerült: a hamis siker rosszabb, mint a hiba.
            self._vege(False, "A tárhely válaszolt, de nem adott letöltési "
                              "linket. A feltöltés eredménye bizonytalan.")
            return
        self._vege(True, self.link)

    def _vege(self, ok, uzenet):
        if self.kesz:
            self.kesz(ok, uzenet)


class _Megszakitva(Exception):
    pass


class _Figyelo:
    """Fájlolvasó, ami haladást jelent és megszakítható.

    A `requests` a fájlobjektumot darabonként olvassa; ha az olvasásnál mérünk,
    a haladás a TÉNYLEGES feltöltést követi, nem a becslést."""

    def __init__(self, f, meret, halad, stop):
        self._f = f
        self._meret = meret
        self._halad = halad
        self._stop = stop
        self._kesz = 0

    def read(self, n=-1):
        if self._stop.is_set():
            raise _Megszakitva()
        adat = self._f.read(n)
        self._kesz += len(adat)
        if self._halad and self._meret:
            self._halad(self._kesz, self._meret)
        return adat

    def __len__(self):
        return self._meret


def torles(cel: tarhely.Tarhely, link: str, kulcs: str = "") -> tuple[bool, str]:
    """A feltöltött fájl visszavonása a tárhelyről, ahol lehet.

    Igaz/hamis + a KIMONDANDÓ mondat. ⚠️ Ahol nem lehet törölni, ott ezt
    világosan megmondjuk – egy „törölve" felirat olyasmiről, ami továbbra is
    elérhető, hamis biztonságérzet."""
    if not cel.torolheto:
        return False, (f"A {cel.nev} nem engedi a törlést: a fájl a lejáratáig "
                       "elérhető marad. Csak a nyilvántartásomból tudom kivenni.")
    try:
        # filebin: az EGÉSZ bint töröljük (a `kulcs` a bin címe). A fájl
        # egyenkénti törlése is menne, de a bin maga is nyom — az egészet
        # visszavonni tisztább.
        cim = kulcs or link
        valasz = requests.delete(cim, headers=FEJLEC,
                                 timeout=KAPCSOLAT_IDOKORLAT)
    except requests.RequestException as e:
        return False, f"A törlés nem sikerült: {e}"
    if valasz.status_code >= 400:
        return False, tarhely.hibauzenet(valasz.status_code, cel.nev)
    return True, f"Törölve a {cel.nev} tárhelyről. A link mostantól nem működik."
