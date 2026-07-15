"""Fájltársítások per-felhasználó (HKCU), admin nélkül, VISSZAVONHATÓAN.

A zene- és videófájlokat a SuperDL-hez társítja: dupla kattintásra a
`SuperDL.exe "<fájl>"` indul, ami a megfelelő modult nyitja (hang → Super M,
videó → Felirat-felolvasó). Csak a HKCU\\Software\\Classes ágat írjuk (a
felhasználó saját felülbírálása), ezért nem kell rendszergazda, és a
kikapcsolás visszaadja a rendszer-alapértelmezést.

MEGJEGYZÉS: a modern Windows a végső „alapértelmezett program" döntést egy
védett UserChoice-hash-ben tárolja, amit program NEM állíthat át csendben. Ezért
a SuperDL bekerül a „Társítás/Megnyitás ezzel" lehetőségek közé, és ahol nincs
felhasználói döntés, ott alapértelmezetté válik; egyébként a felhasználó a
Windows kérdésére a SuperDL-t választja egyszer.
"""

import os
import sys

AUDIO_EXTS = (".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".wma")
VIDEO_EXTS = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".ts", ".flv",
              ".wmv", ".mpg", ".mpeg", ".m2ts")

PROGID_AUDIO = "SuperDL.Audio"
PROGID_VIDEO = "SuperDL.Video"
_CLASSES = r"Software\Classes"


def available() -> bool:
    """Csak Windowson, és csak a fagyasztott (telepített/hordozható) exénél van
    értelme (forrásból futtatva nincs stabil exe-útvonal a társításhoz)."""
    return os.name == "nt" and bool(getattr(sys, "frozen", False))


def _exe() -> str:
    return os.path.abspath(sys.executable)


def _open_command() -> str:
    return f'"{_exe()}" "%1"'


def _ensure_progid(winreg, progid: str, friendly: str) -> None:
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                            f"{_CLASSES}\\{progid}", 0,
                            winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, None, 0, winreg.REG_SZ, friendly)
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                            f"{_CLASSES}\\{progid}\\DefaultIcon", 0,
                            winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, None, 0, winreg.REG_SZ, f"{_exe()},0")
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                            f"{_CLASSES}\\{progid}\\shell\\open\\command", 0,
                            winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, None, 0, winreg.REG_SZ, _open_command())


def _assoc_ext(winreg, ext: str, progid: str) -> None:
    # a „Megnyitás ezzel" listához
    with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            f"{_CLASSES}\\{ext}\\OpenWithProgids", 0,
            winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, progid, 0, winreg.REG_NONE, b"")
    # best-effort alapértelmezés (ahol nincs védett UserChoice)
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                            f"{_CLASSES}\\{ext}", 0,
                            winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, None, 0, winreg.REG_SZ, progid)


def _unassoc_ext(winreg, ext: str, progid: str) -> None:
    # az alapértelmezés visszavétele CSAK ha a miénk volt (rendszer-alap marad)
    try:
        with winreg.OpenKeyEx(winreg.HKEY_CURRENT_USER,
                              f"{_CLASSES}\\{ext}", 0,
                              winreg.KEY_ALL_ACCESS) as k:
            try:
                cur, _ = winreg.QueryValueEx(k, None)
            except OSError:
                cur = None
            if cur == progid:
                winreg.DeleteValue(k, None)
    except OSError:
        pass
    try:
        with winreg.OpenKeyEx(winreg.HKEY_CURRENT_USER,
                              f"{_CLASSES}\\{ext}\\OpenWithProgids", 0,
                              winreg.KEY_ALL_ACCESS) as k:
            winreg.DeleteValue(k, progid)
    except OSError:
        pass


def _delete_tree(winreg, root, path: str) -> None:
    """Rekurzív kulcs-törlés (a winreg csak üres kulcsot töröl magától)."""
    try:
        with winreg.OpenKeyEx(root, path, 0, winreg.KEY_ALL_ACCESS) as k:
            while True:
                try:
                    sub = winreg.EnumKey(k, 0)
                except OSError:
                    break
                _delete_tree(winreg, root, f"{path}\\{sub}")
        winreg.DeleteKey(root, path)
    except OSError:
        pass


def _notify(winreg=None) -> None:
    try:
        import ctypes
        # SHCNE_ASSOCCHANGED = 0x08000000, SHCNF_IDLIST = 0
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    except Exception:
        pass


def is_registered() -> bool:
    """Be van-e kapcsolva a társítás (a ProgID-jaink léteznek)?"""
    if os.name != "nt":
        return False
    import winreg
    try:
        winreg.OpenKeyEx(winreg.HKEY_CURRENT_USER,
                         f"{_CLASSES}\\{PROGID_AUDIO}\\shell\\open\\command",
                         0, winreg.KEY_READ).Close()
        return True
    except OSError:
        return False


def register() -> None:
    """A zene- és videó-kiterjesztések társítása a SuperDL-hez."""
    if not available():
        raise RuntimeError("Fájltársítás csak a telepített/hordozható SuperDL-nél "
                           "érhető el (Windowson).")
    import winreg
    _ensure_progid(winreg, PROGID_AUDIO, "SuperDL – zenelejátszó (Super M)")
    _ensure_progid(winreg, PROGID_VIDEO,
                   "SuperDL – felirat-felolvasó lejátszó")
    for e in AUDIO_EXTS:
        _assoc_ext(winreg, e, PROGID_AUDIO)
    for e in VIDEO_EXTS:
        _assoc_ext(winreg, e, PROGID_VIDEO)
    _notify()


def unregister() -> None:
    """A társítások visszavonása (a rendszer-alapértelmezés visszaáll)."""
    if os.name != "nt":
        return
    import winreg
    for e in AUDIO_EXTS:
        _unassoc_ext(winreg, e, PROGID_AUDIO)
    for e in VIDEO_EXTS:
        _unassoc_ext(winreg, e, PROGID_VIDEO)
    _delete_tree(winreg, winreg.HKEY_CURRENT_USER, f"{_CLASSES}\\{PROGID_AUDIO}")
    _delete_tree(winreg, winreg.HKEY_CURRENT_USER, f"{_CLASSES}\\{PROGID_VIDEO}")
    _notify()
