"""Diagnosztikai csomag: titok-mentes hibajelentés-szöveg (Tibi-audit 3.7/11.5).

A vak felhasználó gyakran pontosan el tudja mondani, mit hallott – ez a modul a
MELLÉ teszi a tényeket: verziók, telepítés típusa, modulok, beállítás-kivonat és
az utolsó napló-sorok, EGYETLEN vágólapra tehető szövegben. SZIGORÚ szabály:
titok (AI/TTS-kulcs, süti-fájl tartalma) NEM kerülhet bele – a tárolt kulcsok
minden előfordulását kimaszkoljuk, a felhasználónevet ~-re cseréljük.
"""

import json
import platform
import sys
from pathlib import Path

# a beállításokból CSAK ez a fehérlista kerül a jelentésbe (értékkel);
# minden más kimarad (a city és a cookies_file csak "megadva/nincs" jelzést kap)
_SETTINGS_WHITELIST = (
    "connections", "parallel", "limit", "audio_only", "audio_format",
    "video_format", "audio_bitrate", "audio_samplerate", "playlist_folders",
    "voice_mode", "tts", "sounds", "beep_enabled", "beep_volume",
    "selfvoice_enabled", "selfvoice_off", "selfvoice_rate", "selfvoice_volume",
    "hide_url_row", "startup_signal", "cookies", "update_last_check",
)


def _mask_secrets(text: str) -> str:
    """A TÁROLT (dekódolt) kulcsok minden előfordulásának kimaszkolása, plusz a
    felhasználói mappa (~) anonimizálása. Ugyanaz az elv, mint a keyscan-é."""
    secrets: set[str] = set()
    try:
        from . import store

        def walk(o):
            if isinstance(o, str):
                s = o.strip()
                if len(s) >= 12:          # csak érdemi hosszú titkok (zaj ki)
                    secrets.add(s)
            elif isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, (list, tuple)):
                for v in o:
                    walk(v)

        for loader in ("load_ai_config", "load_tts_keys"):
            try:
                walk(getattr(store, loader)())
            except Exception:
                pass
    except Exception:
        pass
    for s in sorted(secrets, key=len, reverse=True):
        text = text.replace(s, "•••KULCS-MASZKOLVA•••")
    home = str(Path.home())
    if home:
        text = text.replace(home, "~")
        text = text.replace(home.replace("\\", "/"), "~")
    return text


def install_kind() -> str:
    """Hogyan fut a program: forrásból / hordozható (onefile) / telepített
    vagy kicsomagolt mappás (onedir)."""
    if not getattr(sys, "frozen", False):
        return "forrásból futtatva (python)"
    exe_dir = Path(sys.executable).resolve().parent
    mei = getattr(sys, "_MEIPASS", "")
    onefile = bool(mei) and Path(mei).resolve() != exe_dir
    if onefile:
        return "hordozható (onefile exe)"
    if (exe_dir / "unins000.exe").exists():
        return "telepített (mappás, telepítővel)"
    return "mappás (onedir, telepítő nélkül)"


def _modules_lines() -> list[str]:
    out = []
    try:
        from . import modkit
        root = modkit.modules_root()
        if root.is_dir():
            for d in sorted(root.iterdir()):
                mf = d / "manifest.json"
                if not mf.is_file():
                    continue
                try:
                    m = json.loads(mf.read_text(encoding="utf-8"))
                    out.append(f"  {m.get('id', d.name)}: "
                               f"{m.get('version', '?')}  ({m.get('name', '')})")
                except (OSError, ValueError):
                    out.append(f"  {d.name}: (hibás manifest)")
    except Exception as e:
        out.append(f"  (modul-lista nem olvasható: {e})")
    return out or ["  (nincs telepített modul)"]


def _ytdlp_line() -> str:
    try:
        import yt_dlp
        origin = ("frissített (~/.superdl/bin)"
                  if ".superdl" in (yt_dlp.__file__ or "") else "beágyazott")
        return f"{yt_dlp.version.__version__} ({origin})"
    except Exception as e:
        return f"(nem tölthető be: {e})"


def build_report(settings: dict | None = None,
                 log_lines: list[str] | None = None) -> str:
    """A teljes, titok-mentes diagnosztikai jelentés összeállítása.

    `settings`: a futó program beállítás-szótára (ha None, a mentett fájlból
    olvassuk); `log_lines`: az ablak utolsó napló-sorai (a GUI adja át)."""
    from superdl import __version__
    try:
        from .modkit import CORE_API
    except Exception:
        CORE_API = "?"

    if settings is None:
        try:
            settings = json.loads((Path.home() / ".superdl.json")
                                  .read_text(encoding="utf-8"))
        except (OSError, ValueError):
            settings = {}

    lines = [
        "SuperDL – diagnosztikai jelentés (titkok maszkolva)",
        "=" * 52,
        f"SuperDL verzió:   {__version__}   (modul-API: {CORE_API})",
        f"Telepítés:        {install_kind()}",
        f"Windows:          {platform.platform()}",
        f"Python:           {platform.python_version()} "
        f"({'64' if sys.maxsize > 2**32 else '32'} bit)",
        f"yt-dlp motor:     {_ytdlp_line()}",
    ]
    try:
        import wx
        lines.append(f"wxPython:         {wx.version()}")
    except Exception:
        pass
    pend = Path.home() / ".superdl" / "update_pending.json"
    lines.append(f"Függő önfrissítés-jelző: {'VAN' if pend.exists() else 'nincs'}")
    # OFFLINE FORDÍTÁS: hibajelentésnél az első kérdés, hogy a gépen egyáltalán
    # elérhető-e a motor, és melyik nyelvi csomagok vannak letöltve.
    try:
        from . import offlineford
        if offlineford.elerheto():
            parok = ", ".join("%s→%s" % p for p in offlineford.telepitett_parok())
            lines.append("Offline fordítás:  elérhető; nyelvi csomagok: "
                         + (parok or "még egy sincs letöltve"))
        else:
            lines.append("Offline fordítás:  NINCS (a fordítómotor hiányzik "
                         "ebből a verzióból)")
    except Exception as e:
        lines.append(f"Offline fordítás:  nem ellenőrizhető ({e})")

    lines += ["", "Telepített modulok:"]
    lines += _modules_lines()

    lines += ["", "Beállítás-kivonat (csak nem-bizalmas):"]
    for k in _SETTINGS_WHITELIST:
        if k in settings:
            lines.append(f"  {k} = {settings[k]!r}")
    # bizalmas/személyes mezőknél csak a TÉNY, nem az érték
    for k, label in (("city", "város (napi időjárás)"),
                     ("cookies_file", "cookies.txt fájl")):
        if settings.get(k):
            lines.append(f"  {label}: megadva (értéke nem része a jelentésnek)")

    if log_lines:
        lines += ["", f"Utolsó napló-sorok ({len(log_lines)}):"]
        lines += ["  " + ln for ln in log_lines]

    lines += ["", "(A jelentés nem tartalmaz API-kulcsot, jelszót vagy "
                  "süti-tartalmat; a felhasználói mappa ~ jellel szerepel.)"]
    return _mask_secrets("\n".join(lines))
