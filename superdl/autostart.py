"""Automatikus indítás a Windows-szal, a HÁTTÉRBEN – per-felhasználó, admin nélkül.

Cél: az időzített rádiófelvételek (és minden ütemezett művelet) akkor is
elinduljanak, ha a felhasználó nem nyitotta meg kézzel a programot. Bejelentkezés
után a Windows elindítja a `SuperDL.exe --background` folyamatot, ami REJTVE, egy
rendszertálca-ikonnal fut; a felvétel-ütemező a háttérben ketyeg.

Csak a HKCU „Run" kulcsot írjuk (a felhasználó saját bejegyzése), ezért NEM kell
rendszergazda, és a kikapcsolás egyszerűen törli a bejegyzést. Nincs boot előtti
(bejelentkezés nélküli) indítás – az per-felhasználós médiaappnál törékeny volna.
"""

import os
import sys

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "SuperDL"
# a háttérindítás kapcsolója (a superdl_gui.main() ezt figyeli)
BACKGROUND_FLAG = "--background"


def available() -> bool:
    """Csak Windowson és csak a fagyasztott (telepített/hordozható) exénél van
    értelme – forrásból futtatva nincs stabil exe-útvonal az indításhoz."""
    return os.name == "nt" and bool(getattr(sys, "frozen", False))


def _exe() -> str:
    return os.path.abspath(sys.executable)


def _command() -> str:
    return f'"{_exe()}" {BACKGROUND_FLAG}'


def is_enabled() -> bool:
    """Be van-e állítva az automatikus indítás (és RÁNK, az aktuális exére mutat)?
    Ha a bejegyzés egy régi/más útvonalra mutat, azt NEM tekintjük bekapcsoltnak
    (a telepítő új helyre kerülhetett) – az enable() ilyenkor frissíti."""
    if os.name != "nt":
        return False
    import winreg
    try:
        with winreg.OpenKeyEx(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                              winreg.KEY_READ) as k:
            val, _ = winreg.QueryValueEx(k, _VALUE_NAME)
    except OSError:
        return False
    return _exe().lower() in (val or "").lower()


def enable() -> None:
    """Bekapcsolja az automatikus háttérindítást (az AKTUÁLIS exére)."""
    if not available():
        raise RuntimeError("Az automatikus indítás csak a telepített/hordozható "
                           "SuperDL-nél érhető el (Windowson).")
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, _VALUE_NAME, 0, winreg.REG_SZ, _command())


def disable() -> None:
    """Kikapcsolja az automatikus indítást (törli a bejegyzést)."""
    if os.name != "nt":
        return
    import winreg
    try:
        with winreg.OpenKeyEx(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                              winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, _VALUE_NAME)
    except OSError:
        pass


def is_background_launch(argv=None) -> bool:
    """Igaz, ha a programot a háttér-kapcsolóval indították (a Windows-indításból)."""
    argv = sys.argv if argv is None else argv
    return BACKGROUND_FLAG in argv
