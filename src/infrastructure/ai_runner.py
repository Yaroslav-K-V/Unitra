from agent import run_agent, stream_agent

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is optional in constrained test envs.
    def load_dotenv(*args, **kwargs):
        return False


class AgentAiRunner:
    def __init__(self, env_path: str = ""):
        self._env_path = env_path

    def _load_env(self) -> None:
        if self._env_path:
            load_dotenv(self._env_path, override=True)

    def run(self, source_code: str) -> str:
        self._load_env()
        return run_agent(source_code)

    def stream(self, source_code: str):
        self._load_env()
        return stream_agent(source_code)
