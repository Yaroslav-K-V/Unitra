import json
import re

from agent import run_agent, run_repair_agent, stream_agent

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is optional in constrained test envs.
    def load_dotenv(*args, **kwargs):
        return False


class AgentAiRunner:
    def __init__(self, env_path: str = "", model: str = "", temperature: float = 0.2, max_context: int = 8000):
        self._env_path = env_path
        self._model = model
        self._temperature = temperature
        self._max_context = max_context

    def _load_env(self) -> None:
        if self._env_path:
            load_dotenv(self._env_path, override=True)

    def run(self, source_code: str) -> str:
        self._load_env()
        return run_agent(
            source_code,
            model=self._model,
            temperature=self._temperature,
            max_context=self._max_context,
        )

    def stream(self, source_code: str):
        self._load_env()
        return stream_agent(
            source_code,
            model=self._model,
            temperature=self._temperature,
            max_context=self._max_context,
        )

    def repair(self, context: dict):
        self._load_env()
        output = run_repair_agent(
            context,
            model=self._model,
            temperature=self._temperature,
            max_context=self._max_context,
        )
        return self._parse_repair_output(output)

    @staticmethod
    def _parse_repair_output(output: str):
        cleaned = re.sub(r"^```(?:json)?\n(.*)\n```$", r"\1", (output or "").strip(), flags=re.DOTALL)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            return [{
                "action": "needs_human_decision",
                "reason": "AI repair response was not valid JSON.",
                "details": cleaned[:1000],
            }]
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("suggestions", [payload])
        return []
