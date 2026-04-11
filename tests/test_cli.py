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
        def save_settings(self, request):
            return type(
                "Result",
                (),
                {
                    "saved": True,
                    "model": request.model or "gpt-5.4-mini",
                    "api_key_set": bool(request.api_key),
                    "show_hints": True if request.show_hints is None else request.show_hints,
                },
            )()

    class AiGeneration:
        def generate_from_code(self, code):
            return type("Result", (), {"__dict__": {"test_code": f"# ai {code}", "functions_found": 1}})()

    def __init__(self):
        self.generation = self.Generation()
        self.recent = self.Recent()
        self.settings = self.Settings()
        self.ai_generation = self.AiGeneration()
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
        exit_code = cli_module.main(["--json", "settings", "set", "--model", "gpt-x"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"]["model"] == "gpt-x"


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
