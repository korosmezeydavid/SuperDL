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

# MK7: a torrent SAJÁT kapcsoló, a zene/videó társítástól FÜGGETLENÜL.
# Aki torrentezik, nem feltétlenül akarja a SuperDL-t zenelejátszónak is —
# és fordítva. Egy közös kapcsoló alá gyűrni a kettőt olyan döntést kényszerít,
# amit a felhasználó nem így gondol.
TORRENT_EXT = ".torrent"
PROGID_TORRENT = "SuperDL.Torrent"
MAGNET_SEMA = "magnet"

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


# ---------------------------------------------------------------------
# MK7 — TORRENT: `.torrent` fájltársítás és `magnet:` protokoll-kezelő
# ---------------------------------------------------------------------
#
# ⚠️ A KETTŐ NEM UGYANAZ, és ez a leggyakoribb elrontás.
#
# A `.torrent` egy FÁJLKITERJESZTÉS: a fenti `_assoc_ext()` mintája illik rá.
# A `magnet:` viszont egy URL-PROTOKOLL: a kulcs a séma NEVÉN áll (nem ponttal
# kezdődik), és kötelező benne egy üres `URL Protocol` nevű érték — enélkül a
# Windows egyszerűen NEM ajánlja fel a programot, és a link néma marad.
# Ezért kap külön függvényt, nem paramétert.


def _ensure_magnet_progid(winreg) -> None:
    """A `magnet:` séma saját kulcsa a HKCU alatt.

    Az `URL Protocol` érték a lényeg: a jelenléte teszi protokollá a kulcsot.
    Az értéke szándékosan ÜRES – a Windows így várja."""
    gyoker = f"{_CLASSES}\\{MAGNET_SEMA}"
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, gyoker, 0,
                            winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, None, 0, winreg.REG_SZ, "URL:BitTorrent Magnet")
        winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                            f"{gyoker}\\DefaultIcon", 0,
                            winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, None, 0, winreg.REG_SZ, f"{_exe()},0")
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                            f"{gyoker}\\shell\\open\\command", 0,
                            winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, None, 0, winreg.REG_SZ, _open_command())


def torrent_registered() -> bool:
    """Be van-e kapcsolva a torrent-társítás?"""
    if os.name != "nt":
        return False
    import winreg
    try:
        winreg.OpenKeyEx(
            winreg.HKEY_CURRENT_USER,
            f"{_CLASSES}\\{PROGID_TORRENT}\\shell\\open\\command",
            0, winreg.KEY_READ).Close()
        return True
    except OSError:
        return False


def register_torrent() -> None:
    """`.torrent` fájlok és `magnet:` hivatkozások a SuperDL-hez."""
    if not available():
        raise RuntimeError(
            "A torrent-társítás csak a telepített vagy hordozható SuperDL-nél "
            "érhető el (Windowson).")
    import winreg
    _ensure_progid(winreg, PROGID_TORRENT, "SuperDL – torrentletöltő")
    _assoc_ext(winreg, TORRENT_EXT, PROGID_TORRENT)
    _ensure_magnet_progid(winreg)
    _notify()


def unregister_torrent() -> None:
    """A torrent-társítás visszavonása.

    A `magnet` kulcsot CSAK akkor töröljük, ha tényleg a mi parancsunk van
    benne. Ha közben egy másik torrentprogramot állítottak be, azt nem szabad
    kilőni – az idegen beállítás elrontása sokkal rosszabb, mint egy itt
    maradt kulcs."""
    if os.name != "nt":
        return
    import winreg
    _unassoc_ext(winreg, TORRENT_EXT, PROGID_TORRENT)
    _delete_tree(winreg, winreg.HKEY_CURRENT_USER,
                 f"{_CLASSES}\\{PROGID_TORRENT}")
    mienk = False
    try:
        with winreg.OpenKeyEx(
                winreg.HKEY_CURRENT_USER,
                f"{_CLASSES}\\{MAGNET_SEMA}\\shell\\open\\command",
                0, winreg.KEY_READ) as k:
            ertek, _ = winreg.QueryValueEx(k, None)
            mienk = _exe().lower() in str(ertek).lower()
    except OSError:
        mienk = False
    if mienk:
        _delete_tree(winreg, winreg.HKEY_CURRENT_USER,
                     f"{_CLASSES}\\{MAGNET_SEMA}")
    _notify()
