from src.application.ai_policy import AiPolicy
from src.application.exceptions import DependencyError, ValidationError
from src.application.models import RunTestsRequest, SaveSettingsRequest
from src.application.services import (
    AiGenerationService,
    GenerationService,
    RecentService,
    SettingsService,
    TestRunService as AppTestRunService,
)
from src.config import load_config
from src.infrastructure.ai_runner import AgentAiRunner
from src.infrastructure.settings_repository import EnvSettingsRepository
from src.infrastructure.source_loader import SourceLoader


class StubLoader:
    def __init__(self, source_code="def add(a, b):\n    return a + b", files_scanned=1):
        self.source_code = source_code
        self.files_scanned = files_scanned
        self.loaded_folder = None

    def load_paths(self, paths):
        return type("Bundle", (), {"source_code": self.source_code, "files_scanned": self.files_scanned})()

    def load_folder(self, folder, include_tests, definitions_only_mode=False):
        self.loaded_folder = (folder, include_tests, definitions_only_mode)
        return type("Bundle", (), {"source_code": self.source_code, "files_scanned": self.files_scanned})()

    def load_file(self, path):
        return type("Bundle", (), {"source_code": self.source_code, "files_scanned": 1})()

    def count_python_files(self, folder, include_tests):
        if folder == "bad":
            raise ValidationError("Invalid folder")
        return 3


class StubAiRunner:
    def __init__(self, output="import pytest\n\ndef test_add():\n    assert True\n"):
        self.output = output

    def run(self, source_code):
        return self.output

    def stream(self, source_code):
        yield "import pytest\n"


class StubExecutor:
    def __init__(self, result=None, exc=None):
        self.result = result
        self.exc = exc
        self.last_args = None

    def run(self, full_code, work_dir):
        self.last_args = (full_code, work_dir)
        if self.exc:
            raise self.exc
        return self.result

    def run_multiple(self, modules, work_dir):
        self.last_args = (list(modules), work_dir)
        if self.exc:
            raise self.exc
        return self.result


class InMemoryRecentRepo:
    def __init__(self):
        self.paths = []

    def list_items(self):
        return self.paths

    def add_item(self, path):
        self.paths.append(path)


class StubSettingsRepo:
    def save(self, provider="", api_key="", model="", show_hints=None, ai_policy=None):
        payload = {"AI_PROVIDER": provider or "ollama"}
        if api_key:
            if provider == "openrouter":
                payload["OPENROUTER_API_KEY"] = api_key
            elif provider == "ollama":
                payload["OLLAMA_API_KEY"] = api_key
            else:
                payload["OPENAI_API_KEY"] = api_key
                payload["API_KEY"] = api_key
        if model:
            payload["OPENAI_MODEL"] = model
        payload["SHOW_HINTS"] = "1" if show_hints is not False else "0"
        return payload


def test_generation_service_from_code():
    service = GenerationService(source_loader=StubLoader())
    result = service.generate_from_code("def add(a, b):\n    return a + b")
    assert "def test_add_basic()" in result.test_code
    assert result.functions_found == 1


def test_generation_service_from_folder_counts_files():
    service = GenerationService(source_loader=StubLoader(files_scanned=4))
    result = service.generate_from_folder("/tmp/project")
    assert result.files_scanned == 4


def test_generation_service_raises_validation_error():
    service = GenerationService(source_loader=StubLoader())
    try:
        service.generate_from_code("def broken(")
    except ValidationError as exc:
        assert "SyntaxError" in str(exc)
    else:
        raise AssertionError("ValidationError was not raised")


def test_ai_generation_service_from_paths():
    service = AiGenerationService(source_loader=StubLoader(files_scanned=2), ai_runner=StubAiRunner())
    result = service.generate_from_paths(["a.py", "b.py"])
    assert result.files_scanned == 2
    assert "test_add" in result.test_code


def test_test_run_service_uses_loaded_folder_when_source_missing():
    executor = StubExecutor(result=type("RunResult", (), {"output": "ok", "returncode": 0, "coverage": None})())
    loader = StubLoader(source_code="def add(a, b):\n    return a + b")
    service = AppTestRunService(source_loader=loader, test_executor=executor)
    result = service.run_tests(RunTestsRequest(test_code="def test_x():\n    pass", source_folder="/tmp/app"))
    assert result.output == "ok"
    assert loader.loaded_folder == ("/tmp/app", False, True)
    assert "def add(a, b):" in executor.last_args[0]


def test_test_run_service_requires_test_code():
    service = AppTestRunService(source_loader=StubLoader(), test_executor=StubExecutor())
    try:
        service.run_tests(RunTestsRequest(test_code=""))
    except ValidationError as exc:
        assert "No test code provided" in str(exc)
    else:
        raise AssertionError("ValidationError was not raised")


def test_test_run_service_propagates_dependency_errors():
    service = AppTestRunService(
        source_loader=StubLoader(),
        test_executor=StubExecutor(exc=DependencyError("pytest missing")),
    )
    try:
        service.run_tests(RunTestsRequest(test_code="def test_x():\n    pass"))
    except DependencyError as exc:
        assert "pytest missing" in str(exc)
    else:
        raise AssertionError("DependencyError was not raised")


def test_test_run_service_runs_multiple_modules_separately():
    executor = StubExecutor(result=type("RunResult", (), {"output": "ok", "returncode": 0, "coverage": None})())
    service = AppTestRunService(source_loader=StubLoader(), test_executor=executor)
    result = service.run_multiple(["def test_a():\n    pass", "def test_b():\n    pass"], work_dir="/tmp/app")
    assert result.output == "ok"
    assert executor.last_args == (["def test_a():\n    pass", "def test_b():\n    pass"], "/tmp/app")


def test_recent_service_add_and_list():
    repo = InMemoryRecentRepo()
    service = RecentService(repository=repo)
    service.add_recent("/tmp/file.py")
    assert repo.paths == ["/tmp/file.py"]


def test_settings_service_returns_result():
    service = SettingsService(repository=StubSettingsRepo())
    result = service.save_settings(
        SaveSettingsRequest(provider="openrouter", api_key="secret", model="openai/gpt-5.2", show_hints=False)
    )
    assert result.saved is True
    assert result.provider == "openrouter"
    assert result.model == "openai/gpt-5.2"
    assert result.api_key_set is True
    assert result.openrouter_api_key_set is True
    assert result.show_hints is False


def test_ai_policy_defaults_and_validation():
    policy = AiPolicy()
    assert policy.to_dict() == {
        "ai_generation": "off",
        "ai_repair": "ask",
        "ai_explain": "ask",
    }
    try:
        AiPolicy(ai_generation="auto")
    except ValidationError as exc:
        assert "ai_generation" in str(exc)
    else:
        raise AssertionError("ValidationError was not raised")


def test_settings_repository_uses_json_for_preferences_and_env_for_secret(tmp_path):
    env_path = tmp_path / ".env"
    settings_path = tmp_path / "data" / "settings.json"
    env_path.write_text("API_KEY=secret\nOPENAI_MODEL=legacy-model\nSHOW_HINTS=0\n", encoding="utf-8")
    repo = EnvSettingsRepository(str(env_path), default_model="default-model", settings_path=str(settings_path))

    saved = repo.save(
        provider="openrouter",
        api_key="router-secret",
        model="openai/gpt-5.2",
        show_hints=True,
        ai_policy=AiPolicy(ai_generation="ask", ai_repair="auto"),
    )

    assert saved["AI_PROVIDER"] == "openrouter"
    assert saved["API_KEY"] == "secret"
    assert saved["OPENROUTER_API_KEY"] == "router-secret"
    assert saved["OPENAI_MODEL"] == "openai/gpt-5.2"
    assert saved["SHOW_HINTS"] == "1"
    assert saved["ai_policy"]["ai_generation"] == "ask"
    assert "openai/gpt-5.2" not in env_path.read_text(encoding="utf-8")
    assert "API_KEY=secret" in env_path.read_text(encoding="utf-8")
    assert "OPENROUTER_API_KEY=router-secret" in env_path.read_text(encoding="utf-8")
    assert settings_path.exists()


def test_settings_repository_defaults_to_ollama_without_key(tmp_path):
    repo = EnvSettingsRepository(str(tmp_path / ".env"), default_model="llama3.2", settings_path=str(tmp_path / "settings.json"))

    loaded = repo.load()

    assert loaded["AI_PROVIDER"] == "ollama"
    assert loaded["OPENAI_MODEL"] == "llama3.2"
    assert loaded["OLLAMA_API_KEY"] == ""


def test_load_config_reads_settings_json_after_legacy_env(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        '{"provider": "openrouter", "model": "openai/gpt-5.2", "show_hints": true, "ai_policy": {"ai_generation": "ask"}}',
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("AI_PROVIDER=openai\nOPENAI_MODEL=legacy-model\nSHOW_HINTS=0\n", encoding="utf-8")
    monkeypatch.setenv("UNITRA_SETTINGS_PATH", str(settings_path))
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.delenv("SHOW_HINTS", raising=False)

    config = load_config(root_path=str(tmp_path))

    assert config.ai_provider == "openrouter"
    assert config.ai_model == "openai/gpt-5.2"
    assert config.show_hints is True
    assert config.ai_policy.ai_generation == "ask"


def test_load_config_defaults_to_ollama(tmp_path, monkeypatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    config = load_config(root_path=str(tmp_path))
    assert config.ai_provider == "ollama"
    assert config.ai_model == "llama3.2"


def test_agent_ai_runner_passes_effective_config(monkeypatch, tmp_path):
    import src.infrastructure.ai_runner as ai_runner_module

    captured = {}

    def fake_run_agent(source_code, provider="", model="", temperature=None, max_context=None, base_url=""):
        captured.update({
            "source_code": source_code,
            "provider": provider,
            "model": model,
            "temperature": temperature,
            "max_context": max_context,
            "base_url": base_url,
        })
        return "ok"

    monkeypatch.setattr(ai_runner_module, "run_agent", fake_run_agent)
    runner = AgentAiRunner(
        env_path=str(tmp_path / ".env"),
        provider="openrouter",
        model="gpt-test",
        temperature=0.4,
        max_context=1234,
    )

    assert runner.run("def add(a, b): return a + b") == "ok"
    assert captured == {
        "source_code": "def add(a, b): return a + b",
        "provider": "openrouter",
        "model": "gpt-test",
        "temperature": 0.4,
        "max_context": 1234,
        "base_url": "",
    }


def test_agent_ai_runner_repair_parses_structured_suggestions(monkeypatch, tmp_path):
    import src.infrastructure.ai_runner as ai_runner_module

    captured = {}

    def fake_run_repair_agent(context, provider="", model="", temperature=None, max_context=None, base_url=""):
        captured.update({
            "context": context,
            "provider": provider,
            "model": model,
            "temperature": temperature,
            "max_context": max_context,
            "base_url": base_url,
        })
        return '{"suggestions": [{"action": "remove_edge_case", "reason": "bad edge"}]}'

    monkeypatch.setattr(ai_runner_module, "run_repair_agent", fake_run_repair_agent)
    runner = AgentAiRunner(
        env_path=str(tmp_path / ".env"),
        provider="openrouter",
        model="gpt-test",
        temperature=0.4,
        max_context=1234,
    )

    suggestions = runner.repair({"failure_tests": ["test_add"]})

    assert suggestions == [{"action": "remove_edge_case", "reason": "bad edge"}]
    assert captured["context"]["failure_tests"] == ["test_add"]
    assert captured["provider"] == "openrouter"
    assert captured["model"] == "gpt-test"
    assert captured["temperature"] == 0.4
    assert captured["max_context"] == 1234
    assert captured["base_url"] == ""


def test_load_config_reads_show_hints_from_root_env(tmp_path, monkeypatch):
    monkeypatch.delenv("SHOW_HINTS", raising=False)
    (tmp_path / ".env").write_text("SHOW_HINTS=0\n", encoding="utf-8")
    config = load_config(root_path=str(tmp_path))
    assert config.show_hints is False


def test_source_loader_detects_new_nested_python_file(tmp_path):
    folder = tmp_path / "repo"
    nested = folder / "pkg"
    nested.mkdir(parents=True)
    (nested / "a.py").write_text("x = 1\n", encoding="utf-8")

    loader = SourceLoader(skip_dirs=set())
    first = loader.list_python_files(str(folder), include_tests=False)

    (nested / "b.py").write_text("y = 2\n", encoding="utf-8")
    second = loader.list_python_files(str(folder), include_tests=False)

    assert len(first) == 1
    assert len(second) == 2
    assert str(nested / "b.py") in second
