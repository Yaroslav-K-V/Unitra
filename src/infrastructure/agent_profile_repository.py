import os

from src.application.exceptions import ValidationError
from src.application.workspace_models import AgentProfile
from src.infrastructure.simple_toml import dumps, loads


class AgentProfileRepository:
    def __init__(self, agents_dir: str, default_model: str):
        self.agents_dir = agents_dir
        self.default_model = default_model

    def ensure_default(self) -> AgentProfile:
        profile = AgentProfile(name="default", model=self.default_model)
        path = os.path.join(self.agents_dir, "default.toml")
        if not os.path.exists(path):
            self.save(profile)
        return profile

    def save(self, profile: AgentProfile) -> AgentProfile:
        os.makedirs(self.agents_dir, exist_ok=True)
        path = os.path.join(self.agents_dir, f"{profile.name}.toml")
        content = dumps({
            "profile": {
                "name": profile.name,
                "model": profile.model,
                "system_prompt_addition": profile.system_prompt_addition,
                "roles_enabled": profile.roles_enabled,
                "max_context": profile.max_context,
                "input_token_budget": profile.input_token_budget,
                "output_token_budget": profile.output_token_budget,
                "temperature": profile.temperature,
                "write_enabled": profile.write_enabled,
                "failure_mode": profile.failure_mode,
            }
        })
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return profile

    def load(self, name: str) -> AgentProfile:
        path = os.path.join(self.agents_dir, f"{name}.toml")
        if not os.path.exists(path):
            raise ValidationError(f"Agent profile `{name}` not found")
        raw = loads(self._read(path)).get("profile", {})
        return AgentProfile(
            name=raw.get("name", name),
            model=raw.get("model", self.default_model),
            system_prompt_addition=raw.get("system_prompt_addition", ""),
            roles_enabled=list(raw.get("roles_enabled", ["analyzer", "planner", "generator", "reviewer"])),
            max_context=int(raw.get("max_context", 8000)),
            input_token_budget=int(raw.get("input_token_budget", 4000)),
            output_token_budget=int(raw.get("output_token_budget", 800)),
            temperature=float(raw.get("temperature", 0.2)),
            write_enabled=bool(raw.get("write_enabled", True)),
            failure_mode=raw.get("failure_mode", "report"),
        )

    def list_names(self):
        if not os.path.isdir(self.agents_dir):
            return []
        return sorted(filename[:-5] for filename in os.listdir(self.agents_dir) if filename.endswith(".toml"))

    def list_profiles(self):
        return [self.load(name) for name in self.list_names()]

    @staticmethod
    def _read(path: str) -> str:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
