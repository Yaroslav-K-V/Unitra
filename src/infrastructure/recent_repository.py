import json
import os
from typing import Dict, List

from src.application.models import RecentItem


class JsonRecentRepository:
    def __init__(self, recent_path: str, max_recent: int):
        self._recent_path = recent_path
        self._max_recent = max_recent

    def list_items(self) -> List[RecentItem]:
        items = self._load()
        return [
            RecentItem(path=item["path"], type=item["type"])
            for item in items
            if os.path.exists(item.get("path", ""))
        ]

    def add_item(self, path: str) -> None:
        kind = "folder" if os.path.isdir(path) else "file"
        entry = {"path": path, "type": kind}
        items = self._load()
        items = [item for item in items if item.get("path") != path]
        items.insert(0, entry)
        self._save(items[:self._max_recent])

    def _load(self) -> List[Dict[str, str]]:
        if not os.path.exists(self._recent_path):
            return []
        with open(self._recent_path, encoding="utf-8") as handle:
            return json.load(handle)

    def _save(self, items: List[Dict[str, str]]) -> None:
        os.makedirs(os.path.dirname(self._recent_path), exist_ok=True)
        with open(self._recent_path, "w", encoding="utf-8") as handle:
            json.dump(items, handle, indent=2)
