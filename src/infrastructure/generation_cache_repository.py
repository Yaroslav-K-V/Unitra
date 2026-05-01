"""Persistent cache for generated workspace test artifacts."""

from __future__ import annotations

import json
import os
from typing import Optional


class GenerationCacheRepository:
    """Store and load generated artifact payloads inside `.unitra/cache`."""

    def __init__(self, cache_dir: str):
        self.cache_dir = os.path.abspath(cache_dir)

    def load(self, cache_key: str) -> Optional[dict]:
        path = self._path(cache_key)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def save(self, cache_key: str, payload: dict) -> None:
        os.makedirs(self.cache_dir, exist_ok=True)
        with open(self._path(cache_key), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def _path(self, cache_key: str) -> str:
        return os.path.join(self.cache_dir, f"{cache_key}.json")
