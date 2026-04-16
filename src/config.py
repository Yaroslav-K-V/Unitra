import os
from dataclasses import dataclass
from typing import Dict
from typing import Optional

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
    show_hints: bool


def load_config(root_path: Optional[str] = None) -> AppConfig:
    base_dir = root_path or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_path = os.path.join(base_dir, ".env")
    file_values = {
        key: value
        for key, value in dict(dotenv_values(env_path)).items()
        if value is not None
    }

    def read_setting(name: str, default: str) -> str:
        return os.getenv(name, file_values.get(name, default))

    return AppConfig(
        root_path=base_dir,
        flask_port=int(read_setting("PORT", "5000")),
        ai_model=read_setting("OPENAI_MODEL", "gpt-5.4-mini"),
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
        show_hints=read_setting("SHOW_HINTS", "1") != "0",
    )


_CONFIG = load_config()

FLASK_PORT = _CONFIG.flask_port
AI_MODEL = _CONFIG.ai_model
AI_TEMPERATURE = _CONFIG.ai_temperature
AI_MAX_CONTEXT = _CONFIG.ai_max_context
PYTEST_TIMEOUT = _CONFIG.pytest_timeout
MAX_RECENT = _CONFIG.max_recent
WINDOW_WIDTH = _CONFIG.window_width
WINDOW_HEIGHT = _CONFIG.window_height
