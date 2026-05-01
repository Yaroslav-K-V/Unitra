import json
import pathlib
from typing import Dict, Optional

from src.application.ai_policy import AiPolicy


class EnvSettingsRepository:
    def __init__(self, env_path: str, default_model: str, settings_path: str = ""):
        self._env_path = pathlib.Path(env_path)
        self._default_model = default_model
        self._settings_path = pathlib.Path(settings_path) if settings_path else self._env_path.parent / "data" / "settings.json"

    def save(
        self,
        provider: str = "",
        api_key: str = "",
        model: str = "",
        show_hints=None,
        ai_policy: Optional[AiPolicy] = None,
    ) -> Dict[str, object]:
        existing = self._load_env()
        provider_name = self._normalize_provider(provider or self.load().get("AI_PROVIDER", "ollama"))
        if api_key:
            if provider_name == "openrouter":
                existing["OPENROUTER_API_KEY"] = api_key
            elif provider_name == "ollama":
                existing["OLLAMA_API_KEY"] = api_key
            else:
                existing["OPENAI_API_KEY"] = api_key
                # Preserve the legacy name for older code paths and existing installs.
                existing["API_KEY"] = api_key
            self._write_env(existing)

        settings = self._load_settings()
        if provider:
            settings["provider"] = provider_name
        if model:
            settings["model"] = model
        if show_hints is not None:
            settings["show_hints"] = bool(show_hints)
        if ai_policy is not None:
            current_policy = AiPolicy.from_dict(self.load().get("ai_policy", {}))
            settings["ai_policy"] = AiPolicy.from_dict(ai_policy.to_dict(), base=current_policy).to_dict()
        if provider or model or show_hints is not None or ai_policy is not None:
            self._write_settings(settings)
        return self.load()

    def load(self) -> Dict[str, object]:
        env = self._load_env()
        settings = self._load_settings()
        provider = self._normalize_provider(settings.get("provider") or env.get("AI_PROVIDER") or "ollama")
        model = str(settings.get("model") or env.get("AI_MODEL") or env.get("OPENAI_MODEL") or env.get("OLLAMA_MODEL") or self._default_model)
        show_hints = bool(settings["show_hints"]) if "show_hints" in settings else env.get("SHOW_HINTS", "1") != "0"
        policy = AiPolicy.from_dict(settings.get("ai_policy", {}))
        return {
            "AI_PROVIDER": provider,
            "API_KEY": env.get("API_KEY", ""),
            "OPENAI_API_KEY": env.get("OPENAI_API_KEY", env.get("API_KEY", "")),
            "OPENROUTER_API_KEY": env.get("OPENROUTER_API_KEY", ""),
            "OLLAMA_API_KEY": env.get("OLLAMA_API_KEY", ""),
            "OPENAI_MODEL": model,
            "SHOW_HINTS": "1" if show_hints else "0",
            "ai_policy": policy.to_dict(),
        }

    @staticmethod
    def _normalize_provider(provider: object) -> str:
        value = str(provider or "").strip().lower()
        if value in {"ollama", "openai", "openrouter"}:
            return value
        return "ollama"

    def _load_env(self) -> Dict[str, str]:
        if not self._env_path.exists():
            return {}
        existing: Dict[str, str] = {}
        for line in self._env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                key, _, value = line.partition("=")
                existing[key.strip()] = value.strip()
        return existing

    def _write_env(self, values: Dict[str, str]) -> None:
        self._env_path.parent.mkdir(parents=True, exist_ok=True)
        self._env_path.write_text(
            "\n".join(f"{key}={value}" for key, value in values.items()) + "\n",
            encoding="utf-8",
        )

    def _load_settings(self) -> Dict[str, object]:
        if not self._settings_path.exists():
            return {}
        payload = json.loads(self._settings_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}

    def _write_settings(self, values: Dict[str, object]) -> None:
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings_path.write_text(json.dumps(values, indent=2, sort_keys=True) + "\n", encoding="utf-8")
