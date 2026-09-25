"""A numpy EGYSZERI, őrzött betöltése – régi processzoros gépekre.

⚠️ MIÉRT KELL (Tóth Zoltán, 2026-09-24, Windows 10, 4.6.18):

A buildben lévő numpy 2.4 legalább „x86-64-v2" processzort kér (SSE4.2 +
POPCNT). Régebbi processzoron az ELSŐ `import numpy` még tisztességes
ImportError-ral hasal el („DLL inicializáló rutin nem futott le") – ezt el
lehet kapni. A MÁSODIK próbálkozás viszont a félig betöltött DLL-be nyúl, és
az egész program natívan meghal (0xc000001d, érvénytelen utasítás). Nála
pontosan ez történt: a hanglejátszás már elbukott a numpyn, aztán a
Súgó → Hibajelentés a fordító-ellenőrzésen át (ctranslate2 → numpy) újra
betöltötte, és a program eltűnt.

Ezért: a numpyt a program indulásakor EGYSZER, ellenőrzötten töltjük be.
Ha nem megy, a `sys.modules["numpy"] = None` bejegyzéssel minden későbbi
`import numpy` – a miénk és a külső csomagoké is (ctranslate2, sounddevice)
– AZONNAL ImportError-t kap, a DLL-hez pedig senki nem nyúl többé.
"""
from __future__ import annotations

import sys

_hiba: str | None = None
_probalva = False

TUL_REGI = ("a gép processzora túl régi hozzá (a numpy számolókönyvtár nem "
            "tölthető be)")


def betolt():
    """A numpy modul, vagy ImportError – de a DLL-t legfeljebb EGYSZER
    próbáljuk betölteni a program élete során."""
    global _hiba, _probalva
    if _hiba is not None:
        raise ImportError(_hiba)
    if not _probalva and sys.modules.get("numpy", 0) is None:
        # valaki (pl. egy teszt) már letiltotta
        _probalva = True
        _hiba = TUL_REGI
        raise ImportError(_hiba)
    try:
        import numpy
    except BaseException as e:                     # noqa: BLE001
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        _probalva = True
        _hiba = "%s: %s" % (TUL_REGI, e)
        for nev in [n for n in sys.modules
                    if n == "numpy" or n.startswith("numpy.")]:
            sys.modules.pop(nev, None)
        sys.modules["numpy"] = None               # soha többé ne töltse be
        raise ImportError(_hiba) from None
    _probalva = True
    return numpy


def elerheto() -> bool:
    try:
        betolt()
        return True
    except ImportError:
        return False


def hiba() -> str | None:
    """Miért nem tölthető be (None, ha betölthető vagy még nem próbáltuk)."""
    return _hiba


def _visszaallit_tesztnek() -> None:
    global _hiba, _probalva
    _hiba = None
    _probalva = False
