"""Tartós tárolás: a letöltési sor és a feliratkozások megőrzése
program-újraindítás után is.

Minden a felhasználó saját mappájában, a ~/.superdl könyvtárban tárolódik:

  queue.json          - a letöltési sor (folytatható elemekkel)
  subscriptions.json  - podcast/RSS-feliratkozások
"""

import json
import threading
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
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, data) -> None:
    _ensure_dir()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    tmp.replace(path)


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
    """AI-szolgáltatók API-kulcsai és modellbeállítása (helyben tárolva)."""
    with _lock:
        data = load_json(AI_CONFIG_FILE, {})
    return data if isinstance(data, dict) else {}


def save_ai_config(config: dict) -> None:
    with _lock:
        save_json(AI_CONFIG_FILE, config)


TTS_KEYS_FILE = CONFIG_DIR / "tts_keys.json"


def load_tts_keys() -> dict:
    with _lock:
        data = load_json(TTS_KEYS_FILE, {})
    return data if isinstance(data, dict) else {}


def save_tts_keys(keys: dict) -> None:
    with _lock:
        save_json(TTS_KEYS_FILE, keys)


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
