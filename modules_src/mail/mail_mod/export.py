# -*- coding: utf-8 -*-
"""Super Mail – POSTAFIÓK-MENTÉS (mbox export).

„A hozzáférés nem termék, hanem jog” – és az adat sem. Ez a réteg a teljes
mappát (vagy fiókot) SZABVÁNYOS mbox-fájlba menti, amit bármelyik másik
levelezőprogram (Thunderbird, Evolution…) be tud olvasni. Nem a mi saját
formátumunk: nem kötjük magunkhoz a felhasználót.

Az mbox „mboxrd” változatát írjuk: a törzsben a sorkezdő „From ” elé „>” kerül,
különben egy ártatlan mondat („From Monday…") elvágná a levelet.
"""

from __future__ import annotations

import os
import re
import time
from email.utils import parsedate_to_datetime

_FROM_SOR = re.compile(rb"^(>*From )", re.MULTILINE)


def _mbox_fejlec(msg) -> bytes:
    """Az mbox elválasztó sora: „From feladó dátum”."""
    cim = ""
    try:
        from email.utils import parseaddr
        cim = parseaddr(msg.get("From", "") or "")[1] or "ismeretlen@helyi"
    except Exception:
        cim = "ismeretlen@helyi"
    mikor = None
    try:
        mikor = parsedate_to_datetime(msg.get("Date", "") or "")
    except Exception:
        mikor = None
    ido = (mikor.strftime("%a %b %d %H:%M:%S %Y") if mikor
           else time.strftime("%a %b %d %H:%M:%S %Y"))
    return ("From %s %s\n" % (cim, ido)).encode("utf-8", "replace")


def level_mboxba(msg) -> bytes:
    """Egy levél mbox-alakja (elválasztóval, védett From-sorokkal)."""
    nyers = msg.as_bytes()
    nyers = _FROM_SOR.sub(rb">\1", nyers)
    if not nyers.endswith(b"\n"):
        nyers += b"\n"
    return _mbox_fejlec(msg) + nyers + b"\n"


class MboxIro:
    """Levelek folyamatos írása mbox-fájlba (memóriakímélő)."""

    def __init__(self, ut: str):
        self.ut = ut
        self._f = None
        self.darab = 0

    def __enter__(self):
        mappa = os.path.dirname(os.path.abspath(self.ut))
        if mappa:
            os.makedirs(mappa, exist_ok=True)
        self._f = open(self.ut, "wb")
        return self

    def ir(self, msg) -> None:
        self._f.write(level_mboxba(msg))
        self.darab += 1

    def __exit__(self, *a):
        if self._f:
            try:
                self._f.flush()
                os.fsync(self._f.fileno())
            finally:
                self._f.close()
                self._f = None
        return False


def fajlnev(fiok_email: str, mappa: str) -> str:
    """Beszédes, biztonságos fájlnév a mentéshez."""
    def tiszta(sz):
        sz = str(sz or "").strip()
        for rossz in '<>:"/\\|?*':
            sz = sz.replace(rossz, "-")
        return sz.strip(". ") or "postafiok"
    return "%s - %s - %s.mbox" % (tiszta(fiok_email), tiszta(mappa),
                                  time.strftime("%Y-%m-%d"))


def meret_szoveg(bajt: int) -> str:
    for egyseg, hatar in (("gigabájt", 1024 ** 3), ("megabájt", 1024 ** 2),
                          ("kilobájt", 1024)):
        if bajt >= hatar:
            return "%.1f %s" % (bajt / hatar, egyseg)
    return "%d bájt" % bajt
