import os
import json
from dataclasses import dataclass
from typing import Dict
from typing import Optional

from src.application.ai_policy import AiPolicy

try:
    from dotenv import dotenv_values, load_dotenv
except ImportError:  # pragma: no cover - fallback for limited test environments
    def load_dotenv():
        return False

    def dotenv_values(path):
        values: Dict[str, str] = {}
        if not os.path.exists(path):
            return values
        with open(path, encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
        return values


load_dotenv()

APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@dataclass(frozen=True)
class AppConfig:
    root_path: str
    flask_port: int
    ai_model: str
    ai_temperature: float
    ai_max_context: int
    pytest_timeout: int
    max_recent: int
    window_width: int
    window_height: int
    window_min_width: int
    window_min_height: int
    recent_path: str
    env_path: str
    settings_path: str
    show_hints: bool
    ai_policy: AiPolicy


def load_config(root_path: Optional[str] = None) -> AppConfig:
    base_dir = root_path or APP_ROOT
    env_path = os.path.join(base_dir, ".env")
    settings_path = os.getenv("UNITRA_SETTINGS_PATH") or os.path.join(APP_ROOT, "data", "settings.json")
    file_values = {
        key: value
        for key, value in dict(dotenv_values(env_path)).items()
        if value is not None
    }
    settings_values = _load_settings_json(settings_path)

    def read_setting(name: str, default: str) -> str:
        return os.getenv(name, file_values.get(name, default))

    def read_pref(name: str, env_name: str, default: str) -> str:
        value = settings_values.get(name)
        if value not in (None, ""):
            return str(value)
        return read_setting(env_name, default)

    def read_show_hints() -> bool:
        if "show_hints" in settings_values:
            return bool(settings_values.get("show_hints"))
        return read_setting("SHOW_HINTS", "1") != "0"

    return AppConfig(
        root_path=base_dir,
        flask_port=int(read_setting("PORT", "5000")),
        ai_model=read_pref("model", "OPENAI_MODEL", "gpt-5.4-mini"),
        ai_temperature=float(read_setting("AI_TEMPERATURE", "0.2")),
        ai_max_context=int(read_setting("AI_MAX_CONTEXT", "8000")),
        pytest_timeout=int(read_setting("PYTEST_TIMEOUT", "30")),
        max_recent=int(read_setting("MAX_RECENT", "8")),
        window_width=int(read_setting("WINDOW_WIDTH", "1440")),
        window_height=int(read_setting("WINDOW_HEIGHT", "920")),
        window_min_width=int(read_setting("WINDOW_MIN_WIDTH", "1280")),
        window_min_height=int(read_setting("WINDOW_MIN_HEIGHT", "820")),
        recent_path=os.path.join(base_dir, "data", "recent.json"),
        env_path=env_path,
        settings_path=settings_path,
        show_hints=read_show_hints(),
        ai_policy=AiPolicy.from_dict(settings_values.get("ai_policy", {})),
    )


def _load_settings_json(path: str) -> Dict[str, object]:
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


_CONFIG = load_config()

FLASK_PORT = _CONFIG.flask_port
AI_MODEL = _CONFIG.ai_model
AI_TEMPERATURE = _CONFIG.ai_temperature
AI_MAX_CONTEXT = _CONFIG.ai_max_context
PYTEST_TIMEOUT = _CONFIG.pytest_timeout
MAX_RECENT = _CONFIG.max_recent
WINDOW_WIDTH = _CONFIG.window_width
WINDOW_HEIGHT = _CONFIG.window_height
