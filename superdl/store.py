"""Tartós tárolás: a letöltési sor és a feliratkozások megőrzése
program-újraindítás után is.

Minden a felhasználó saját mappájában, a ~/.superdl könyvtárban tárolódik:

  queue.json          - a letöltési sor (folytatható elemekkel)
  subscriptions.json  - podcast/RSS-feliratkozások
"""

import json
import threading
import time
from pathlib import Path

CONFIG_DIR = Path.home() / ".superdl"
QUEUE_FILE = CONFIG_DIR / "queue.json"
SUBS_FILE = CONFIG_DIR / "subscriptions.json"
CART_FILE = CONFIG_DIR / "cart.json"
RADIO_FAV_FILE = CONFIG_DIR / "radio_favorites.json"
ORG_EVENTS_FILE = CONFIG_DIR / "organizer_events.json"
ORG_TASKS_FILE = CONFIG_DIR / "organizer_tasks.json"
ORG_NOTES_FILE = CONFIG_DIR / "organizer_notes.json"
ICS_SUBS_FILE = CONFIG_DIR / "ics_subscriptions.json"

_lock = threading.Lock()


def _ensure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default):
    """Beolvasás. Hiányzó fájlnál csendben az alapértelmezett (normál első
    indulás). SÉRÜLT (de létező) fájlnál NEM nyeljük el némán: előbb a legutóbbi
    jó .bak biztonsági másolatból próbálunk, és ha az sincs, a sérült fájlt
    félretesszük .corrupt-<dátum> néven, hogy a következő mentés NE írja felül a
    még esetleg menthető adatot."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except OSError:
        return default
    except json.JSONDecodeError:
        bak = path.with_suffix(path.suffix + ".bak")
        try:
            return json.loads(bak.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        try:
            stamp = time.strftime("%Y%m%d-%H%M%S")
            path.replace(path.with_suffix(path.suffix + f".corrupt-{stamp}"))
        except OSError:
            pass
        return default


def save_json(path: Path, data) -> None:
    _ensure_dir()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    # a jelenlegi (még jó) fájlt megőrizzük .bak néven, mielőtt felülírnánk –
    # így egy fél mentés vagy későbbi sérülés után van mihez visszanyúlni
    if path.exists():
        try:
            path.replace(path.with_suffix(path.suffix + ".bak"))
        except OSError:
            pass
    tmp.replace(path)


# ---- titkosított tárolás (API-kulcsok) – Windows DPAPI ----------------
# Az AI/TTS kulcsokat NEM nyílt szövegként tároljuk, hanem a felhasználó
# fiókjához kötött DPAPI-val titkosítva. Ha a DPAPI nem érhető el (nem Windows,
# hiányzó pywin32), biztonságos visszaesésként sima JSON-t írunk – a program
# így sosem áll meg emiatt.

def _dpapi_protect(text: str):
    try:
        import win32crypt
        return win32crypt.CryptProtectData(
            text.encode("utf-8"), "SuperDL", None, None, None, 0)
    except Exception:
        return None


def _dpapi_unprotect(blob: bytes):
    try:
        import win32crypt
        _, data = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
        return data.decode("utf-8")
    except Exception:
        return None


def save_secret_json(path: Path, data) -> None:
    """Mint a save_json, de a tartalmat DPAPI-val titkosítja."""
    import base64
    _ensure_dir()
    blob = _dpapi_protect(json.dumps(data, ensure_ascii=False))
    if blob is not None:
        payload = {"__dpapi__": base64.b64encode(bytes(blob)).decode("ascii")}
    else:
        payload = data                       # visszaesés: sima JSON
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    tmp.replace(path)
    # FONTOS: titoknál NEM hagyunk .bak-ot, és egy meglévőt is törlünk – egy
    # korábbi (akár sima szövegű) .bak különben nyíltan őrizné a kulcsokat
    bak = path.with_suffix(path.suffix + ".bak")
    try:
        if bak.exists():
            bak.unlink()
    except OSError:
        pass


def _load_secret_config(path: Path) -> dict:
    """DPAPI-titkosított VAGY régi sima JSON beolvasása. A régi (sima) fájlt
    átolvasás után MIGRÁLJA: titkosítva visszaírja, hogy a kulcsok ne maradjanak
    nyílt szövegben."""
    import base64
    with _lock:
        raw = load_json(path, None)
    if not isinstance(raw, dict):
        return {}
    if "__dpapi__" in raw:
        try:
            text = _dpapi_unprotect(base64.b64decode(raw["__dpapi__"]))
            data = json.loads(text) if text is not None else {}
        except Exception:
            data = {}
        return data if isinstance(data, dict) else {}
    # régi, SIMA szövegként tárolt kulcsok → titkosítva visszaírjuk (migráció)
    if raw:
        with _lock:
            save_secret_json(path, raw)
    return raw


def load_queue() -> list[dict]:
    """A mentett letöltési sor (lista a job-leírókból)."""
    with _lock:
        data = load_json(QUEUE_FILE, [])
    return data if isinstance(data, list) else []


def save_queue(records: list[dict]) -> None:
    with _lock:
        save_json(QUEUE_FILE, records)


def load_subscriptions() -> list[dict]:
    with _lock:
        data = load_json(SUBS_FILE, [])
    return data if isinstance(data, list) else []


def save_subscriptions(records: list[dict]) -> None:
    with _lock:
        save_json(SUBS_FILE, records)


def load_cart() -> list[dict]:
    """A médiakereső kosarának tartalma (program-bezárás után is megmarad)."""
    with _lock:
        data = load_json(CART_FILE, [])
    return data if isinstance(data, list) else []


def save_cart(records: list[dict]) -> None:
    with _lock:
        save_json(CART_FILE, records)


def load_radio_favorites() -> list[dict]:
    with _lock:
        data = load_json(RADIO_FAV_FILE, [])
    return data if isinstance(data, list) else []


def save_radio_favorites(records: list[dict]) -> None:
    with _lock:
        save_json(RADIO_FAV_FILE, records)


RADIO_SCHED_FILE = CONFIG_DIR / "radio_schedule.json"


def load_radio_schedule() -> list[dict]:
    """Az időzített rádiófelvételek (program-újraindítás után is megmaradnak)."""
    with _lock:
        data = load_json(RADIO_SCHED_FILE, [])
    return data if isinstance(data, list) else []


def save_radio_schedule(records: list[dict]) -> None:
    with _lock:
        save_json(RADIO_SCHED_FILE, records)


CHANNELS_FILE = CONFIG_DIR / "channels.json"
FRESH_VIDEOS_FILE = CONFIG_DIR / "fresh_videos.json"


def load_channels() -> list[dict]:
    """YouTube-csatorna feliratkozások."""
    with _lock:
        data = load_json(CHANNELS_FILE, [])
    return data if isinstance(data, list) else []


def save_channels(records: list[dict]) -> None:
    with _lock:
        save_json(CHANNELS_FILE, records)


def load_fresh_videos() -> list[dict]:
    """A figyelt csatornák friss, még meg nem nyitott videói."""
    with _lock:
        data = load_json(FRESH_VIDEOS_FILE, [])
    return data if isinstance(data, list) else []


def save_fresh_videos(records: list[dict]) -> None:
    with _lock:
        save_json(FRESH_VIDEOS_FILE, records)


NEWS_FEEDS_FILE = CONFIG_DIR / "news_feeds.json"


def load_news_feeds() -> list[dict]:
    """A hírolvasó RSS-forrásai."""
    with _lock:
        data = load_json(NEWS_FEEDS_FILE, [])
    return data if isinstance(data, list) else []


def save_news_feeds(records: list[dict]) -> None:
    with _lock:
        save_json(NEWS_FEEDS_FILE, records)


LIBRARY_FILE = CONFIG_DIR / "library.json"


def load_library() -> list[dict]:
    """Könyvtár + könyvjelzők (élő könyvolvasó)."""
    with _lock:
        data = load_json(LIBRARY_FILE, [])
    return data if isinstance(data, list) else []


def save_library(records: list[dict]) -> None:
    with _lock:
        save_json(LIBRARY_FILE, records)


AI_CONFIG_FILE = CONFIG_DIR / "ai.json"


def load_ai_config() -> dict:
    """AI-szolgáltatók API-kulcsai és modellbeállítása (DPAPI-val titkosítva)."""
    return _load_secret_config(AI_CONFIG_FILE)


def save_ai_config(config: dict) -> None:
    with _lock:
        save_secret_json(AI_CONFIG_FILE, config)


TTS_KEYS_FILE = CONFIG_DIR / "tts_keys.json"


def load_tts_keys() -> dict:
    return _load_secret_config(TTS_KEYS_FILE)


def save_tts_keys(keys: dict) -> None:
    with _lock:
        save_secret_json(TTS_KEYS_FILE, keys)


IPTV_FAV_FILE = CONFIG_DIR / "iptv_favorites.json"
IPTV_CONF_FILE = CONFIG_DIR / "iptv.json"


def load_iptv_favorites() -> list[dict]:
    """Kedvenc TV-csatornák (program-újraindítás után is megmaradnak)."""
    with _lock:
        data = load_json(IPTV_FAV_FILE, [])
    return data if isinstance(data, list) else []


def save_iptv_favorites(records: list[dict]) -> None:
    with _lock:
        save_json(IPTV_FAV_FILE, records)


def load_iptv_conf() -> dict:
    """IPTV-beállítások: utolsó m3u/EPG URL, Xtream-kiszolgáló és -felhasználó
    (a JELSZÓT biztonságból NEM tároljuk)."""
    with _lock:
        data = load_json(IPTV_CONF_FILE, {})
    return data if isinstance(data, dict) else {}


def save_iptv_conf(conf: dict) -> None:
    with _lock:
        save_json(IPTV_CONF_FILE, conf)


def _load_list(path: Path) -> list[dict]:
    with _lock:
        data = load_json(path, [])
    return data if isinstance(data, list) else []


def load_organizer_events() -> list[dict]:
    return _load_list(ORG_EVENTS_FILE)


def save_organizer_events(records: list[dict]) -> None:
    with _lock:
        save_json(ORG_EVENTS_FILE, records)


def load_organizer_tasks() -> list[dict]:
    return _load_list(ORG_TASKS_FILE)


def save_organizer_tasks(records: list[dict]) -> None:
    with _lock:
        save_json(ORG_TASKS_FILE, records)


def load_organizer_notes() -> list[dict]:
    return _load_list(ORG_NOTES_FILE)


def save_organizer_notes(records: list[dict]) -> None:
    with _lock:
        save_json(ORG_NOTES_FILE, records)


def load_ics_subs() -> list[dict]:
    return _load_list(ICS_SUBS_FILE)


def save_ics_subs(records: list[dict]) -> None:
    with _lock:
        save_json(ICS_SUBS_FILE, records)
