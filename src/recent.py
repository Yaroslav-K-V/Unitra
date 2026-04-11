from src.config import load_config
from src.infrastructure.recent_repository import JsonRecentRepository

MAX_RECENT = load_config().max_recent
RECENT_PATH = load_config().recent_path


def _repository() -> JsonRecentRepository:
    return JsonRecentRepository(recent_path=RECENT_PATH, max_recent=MAX_RECENT)


def add_recent(path: str):
    _repository().add_item(path)


def get_recent() -> list:
    return [
        {"path": item.path, "type": item.type}
        for item in _repository().list_items()
    ]
