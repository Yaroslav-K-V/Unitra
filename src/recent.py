import json
import os

from src.config import MAX_RECENT

RECENT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "recent.json")


def _load() -> list:
    if not os.path.exists(RECENT_PATH):
        return []
    with open(RECENT_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(items: list):
    os.makedirs(os.path.dirname(RECENT_PATH), exist_ok=True)
    with open(RECENT_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)


def add_recent(path: str):
    kind = "folder" if os.path.isdir(path) else "file"
    entry = {"path": path, "type": kind}
    items = _load()
    items = [i for i in items if i.get("path") != path]  # remove duplicate
    items.insert(0, entry)
    _save(items[:MAX_RECENT])


def get_recent() -> list:
    items = _load()
    return [i for i in items if os.path.exists(i.get("path", ""))]
