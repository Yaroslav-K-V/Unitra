import io
import json
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import src.cli as cli_module


class StubContainer:
    class Generation:
        def generate_from_code(self, code):
            return type("Result", (), {"__dict__": {"test_code": f"# {code}", "functions_found": 1}})()

    class Recent:
        def list_recent(self):
            return [type("Item", (), {"__dict__": {"type": "file", "path": "/tmp/a.py"}})()]

    class Settings:
        def load_settings(self):
            return type(
                "Result",
                (),
                {
                    "saved": False,
                    "provider": "ollama",
                    "model": "llama3.2",
                    "api_key_set": True,
                    "openai_api_key_set": False,
                    "openrouter_api_key_set": False,
                    "ollama_api_key_set": True,
                    "show_hints": True,
                    "ai_policy": cli_module.AiPolicy(),
                },
            )()

        def save_settings(self, request):
            return type(
                "Result",
                (),
                {
                    "saved": True,
                    "provider": request.provider or "ollama",
                    "model": request.model or "llama3.2",
                    "api_key_set": True if (request.provider or "ollama") == "ollama" else bool(request.api_key),
                    "openai_api_key_set": bool(request.api_key) if (request.provider or "ollama") == "openai" else False,
                    "openrouter_api_key_set": bool(request.api_key) if request.provider == "openrouter" else False,
                    "ollama_api_key_set": True if (request.provider or "ollama") == "ollama" else False,
                    "show_hints": True if request.show_hints is None else request.show_hints,
                    "ai_policy": request.ai_policy or cli_module.AiPolicy(),
                },
            )()

    class AiGeneration:
        def generate_from_code(self, code):
            return type("Result", (), {"__dict__": {"test_code": f"# ai {code}", "functions_found": 1}})()

    class Doctor:
        def doctor(self, root):
            return type(
                "Report",
                (),
                {
                    "mode": "doctor",
                    "workspace_root": root,
                    "ok": True,
                    "checks": [type("Check", (), {"name": "python", "status": "pass", "detail": "Python ok", "command": "python --version"})()],
                },
            )()

        def check(self, root):
            return type(
                "Report",
                (),
                {
                    "mode": "check",
                    "workspace_root": root,
                    "ok": True,
                    "checks": [type("Check", (), {"name": "workspace", "status": "pass", "detail": "Workspace ok", "command": "unitra workspace validate"})()],
                },
            )()

    def __init__(self):
        self.generation = self.Generation()
        self.recent = self.Recent()
        self.settings = self.Settings()
        self.ai_generation = self.AiGeneration()
        self.doctor = self.Doctor()
        self.config = type("Config", (), {"ai_policy": cli_module.AiPolicy(), "ai_model": "llama3.2"})()
        self.test_runner = type("Runner", (), {"run_tests": lambda self, request: type("RunResult", (), {"output": "FAILED", "returncode": 1, "coverage": None})()})()


def test_cli_generate_json(monkeypatch):
    monkeypatch.setattr(cli_module, "get_container", lambda: StubContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "generate", "--code", "print('x')"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["command"] == "generate"
    assert payload["result"]["functions_found"] == 1


def test_cli_generate_reads_stdin(monkeypatch):
    monkeypatch.setattr(cli_module, "get_container", lambda: StubContainer())
    monkeypatch.setattr(sys, "stdin", io.StringIO("stdin-code"))
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["generate", "--code", "-"])
    assert exit_code == 0
    assert "# stdin-code" in stdout.getvalue()


def test_cli_recent_list(monkeypatch):
    monkeypatch.setattr(cli_module, "get_container", lambda: StubContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["recent", "list"])
    assert exit_code == 0
    assert "file: /tmp/a.py" in stdout.getvalue()


def test_cli_settings_set_json(monkeypatch):
    monkeypatch.setattr(cli_module, "get_container", lambda: StubContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "settings", "set", "--provider", "openrouter", "--model", "openai/gpt-5.2"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"]["provider"] == "openrouter"
    assert payload["result"]["model"] == "openai/gpt-5.2"


def test_cli_settings_show_and_set_ai_policy(monkeypatch):
    monkeypatch.setattr(cli_module, "get_container", lambda: StubContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "settings", "set", "--ai-generation", "ask", "--ai-repair", "auto"])

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"]["provider"] == "ollama"
    assert payload["result"]["ai_policy"]["ai_generation"] == "ask"
    assert payload["result"]["ai_policy"]["ai_repair"] == "auto"

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "settings", "show"])

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"]["provider"] == "ollama"
    assert payload["result"]["ai_policy"]["ai_generation"] == "off"


def test_cli_doctor_json(monkeypatch):
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: StubContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "doctor", "--root", "/tmp/repo"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["command"] == "doctor"
    assert payload["result"]["checks"][0]["name"] == "python"


def test_cli_check_human_output(monkeypatch):
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: StubContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["check", "--root", "/tmp/repo"])
    assert exit_code == 0
    rendered = stdout.getvalue()
    assert "Mode: check" in rendered
    assert "workspace: pass" in rendered


def test_cli_handles_validation_error(monkeypatch):
    class BrokenContainer(StubContainer):
        class Generation:
            def generate_from_code(self, code):
                raise cli_module.ValidationError("bad input")

    monkeypatch.setattr(cli_module, "get_container", lambda: BrokenContainer())
    stderr = io.StringIO()
    with redirect_stderr(stderr):
        exit_code = cli_module.main(["generate", "--code", "x"])
    assert exit_code == 2
    assert "bad input" in stderr.getvalue()


def test_cli_run_tests_returns_distinct_test_failure_exit_code(monkeypatch):
    monkeypatch.setattr(cli_module, "get_container", lambda: StubContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "run-tests", "--test-code", "def test_x(): pass"])
    assert exit_code == cli_module.EXIT_TEST_FAILURE
    payload = json.loads(stdout.getvalue())
    assert payload["run"]["returncode"] == 1


def test_cli_json_output_can_be_written_to_file(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_module, "get_container", lambda: StubContainer())
    output_file = tmp_path / "cli-output.json"
    exit_code = cli_module.main(["--json", "--output-file", str(output_file), "generate", "--code", "print('x')"])
    assert exit_code == 0
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["command"] == "generate"
