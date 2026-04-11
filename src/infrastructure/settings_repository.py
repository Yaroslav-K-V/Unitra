import pathlib
from typing import Dict


class EnvSettingsRepository:
    def __init__(self, env_path: str, default_model: str):
        self._env_path = pathlib.Path(env_path)
        self._default_model = default_model

    def save(self, api_key: str = "", model: str = "", show_hints=None) -> Dict[str, str]:
        existing = self._load()
        if api_key:
            existing["API_KEY"] = api_key
        if model:
            existing["OPENAI_MODEL"] = model
        if show_hints is not None:
            existing["SHOW_HINTS"] = "1" if show_hints else "0"
        self._env_path.write_text(
            "\n".join(f"{key}={value}" for key, value in existing.items()) + "\n",
            encoding="utf-8",
        )
        return existing

    def load(self) -> Dict[str, str]:
        return self._load()

    def _load(self) -> Dict[str, str]:
        if not self._env_path.exists():
            return {}
        existing: Dict[str, str] = {}
        for line in self._env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                key, _, value = line.partition("=")
                existing[key.strip()] = value.strip()
        return existing
