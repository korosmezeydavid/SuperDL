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
