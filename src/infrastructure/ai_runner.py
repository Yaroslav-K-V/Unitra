import json
import re

from agent import run_agent, run_repair_agent, stream_agent

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is optional in constrained test envs.
    def load_dotenv(*args, **kwargs):
        return False


class AgentAiRunner:
    def __init__(
        self,
        env_path: str = "",
        provider: str = "",
        model: str = "",
        temperature: float = 0.2,
        max_context: int = 8000,
    ):
        self._env_path = env_path
        self._provider = provider
        self._model = model
        self._temperature = temperature
        self._max_context = max_context

    def _load_env(self) -> None:
        if self._env_path:
            load_dotenv(self._env_path, override=True)

    def run(self, source_code: str) -> str:
        return self.run_with_overrides(source_code)

    def run_with_overrides(
        self,
        source_code: str,
        provider: str = "",
        model: str = "",
        temperature: float = None,
        max_context: int = None,
        base_url: str = "",
    ) -> str:
        self._load_env()
        return run_agent(
            source_code,
            provider=provider or self._provider,
            model=model or self._model,
            temperature=self._temperature if temperature is None else temperature,
            max_context=self._max_context if max_context is None else max_context,
            base_url=base_url,
        )

    def stream(self, source_code: str):
        return self.stream_with_overrides(source_code)

    def stream_with_overrides(
        self,
        source_code: str,
        provider: str = "",
        model: str = "",
        temperature: float = None,
        max_context: int = None,
        base_url: str = "",
    ):
        self._load_env()
        return stream_agent(
            source_code,
            provider=provider or self._provider,
            model=model or self._model,
            temperature=self._temperature if temperature is None else temperature,
            max_context=self._max_context if max_context is None else max_context,
            base_url=base_url,
        )

    def repair(self, context: dict):
        return self.repair_with_overrides(context)

    def repair_with_overrides(
        self,
        context: dict,
        provider: str = "",
        model: str = "",
        temperature: float = None,
        max_context: int = None,
        base_url: str = "",
    ):
        self._load_env()
        output = run_repair_agent(
            context,
            provider=provider or self._provider,
            model=model or self._model,
            temperature=self._temperature if temperature is None else temperature,
            max_context=self._max_context if max_context is None else max_context,
            base_url=base_url,
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
