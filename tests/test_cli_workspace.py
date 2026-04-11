import io
import json
from contextlib import redirect_stdout

import src.cli as cli_module


class StubWorkspaceContainer:
    class Workspace:
        def init_workspace(self, root):
            return type("Cfg", (), {"__dict__": {"root_path": root, "test_root": "tests/unit"}})()

        def status(self):
            return type(
                "Status",
                (),
                {
                    "config": type("Cfg", (), {"__dict__": {"root_path": ".", "selected_agent_profile": "default"}})(),
                    "jobs": ["generate-tests"],
                    "agent_profiles": ["default"],
                    "recent_runs": ["20260101000000000000"],
                },
            )()

        def validate(self):
            return self.status()

        def list_jobs(self):
            return [
                type("Job", (), {"__dict__": {"name": "generate-tests", "mode": "generate-tests", "target_scope": "repo"}})(),
            ]

        def get_job(self, name):
            return type("Job", (), {"__dict__": {"name": name, "mode": "generate-tests", "target_scope": "repo"}})()

        def list_runs(self, limit=20):
            return ["20260101000000000000"]

        def get_run(self, history_id):
            return {
                "job_name": "run-tests",
                "mode": "run-tests",
                "target_scope": "repo",
                "planned_files": [],
                "written_files": [],
                "run_output": "ok",
                "run_returncode": 0,
                "run_coverage": "90%",
                "llm_fallback_contexts": [],
            }

        def list_agent_profiles(self):
            return [type("Profile", (), {"__dict__": {"name": "default", "model": "gpt-5.4-mini"}})()]

        def get_agent_profile(self, name):
            return type("Profile", (), {"__dict__": {"name": name, "model": "gpt-5.4-mini"}})()

    class Jobs:
        def list_jobs(self):
            return ["generate-tests", "run-tests"]

        def run_job(self, name, target_value="", output_policy=""):
            return type(
                "JobResult",
                (),
                {
                    "job_name": name,
                    "mode": "generate-tests",
                    "target_scope": "repo",
                    "planned_files": [],
                    "written_files": [],
                    "run_output": "",
                    "run_returncode": None,
                    "run_coverage": None,
                    "llm_fallback_contexts": [{"estimated_input_tokens": 200, "expected_output_tokens": 80}],
                    "history_id": "abc",
                },
            )()

        def generate_tests(self, target, write=False):
            return self.run_job("ad-hoc-generate")

        def update_tests(self, target, write=False):
            return self.run_job("ad-hoc-update")

        def fix_failed_tests(self, target, write=False):
            return self.run_job("ad-hoc-fix")

        def run_tests(self, pytest_args=None, timeout=None):
            return self.run_job("ad-hoc-run-tests")

    def __init__(self):
        self.workspace = self.Workspace()
        self.jobs = self.Jobs()
        self.generation = None
        self.ai_generation = None
        self.test_runner = None
        self.recent = None
        self.settings = None
        self.config = type("Config", (), {"ai_model": "gpt-5.4-mini"})()


def test_cli_workspace_init_json(monkeypatch):
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: StubWorkspaceContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "workspace", "init", "--root", "/tmp/repo"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["workspace_root"] == "/tmp/repo"
    assert payload["result"]["root_path"] == "/tmp/repo"


def test_cli_workspace_status_json(monkeypatch):
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: StubWorkspaceContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "workspace", "status", "--root", "/tmp/repo"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"]["jobs"] == ["generate-tests"]


def test_cli_workspace_status_defaults_to_current_working_directory(monkeypatch, tmp_path):
    seen_roots = []

    def fake_container_for_root(root):
        seen_roots.append(cli_module._workspace_root(root))
        return StubWorkspaceContainer()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "_container_for_root", fake_container_for_root)
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "workspace", "status"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert seen_roots == [str(tmp_path)]
    assert payload["workspace_root"] == str(tmp_path)


def test_cli_job_list(monkeypatch):
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: StubWorkspaceContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["job", "list", "--root", "/tmp/repo"])
    assert exit_code == 0
    output = stdout.getvalue()
    assert "generate-tests" in output


def test_cli_test_generate_json(monkeypatch):
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: StubWorkspaceContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "test", "generate", "--root", "/tmp/repo", "--repo"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["job_name"] == "ad-hoc-generate"


def test_cli_workspace_validate_json(monkeypatch):
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: StubWorkspaceContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "workspace", "validate", "--root", "/tmp/repo"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"]["valid"] is True


def test_cli_job_show_json(monkeypatch):
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: StubWorkspaceContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "job", "show", "generate-tests", "--root", "/tmp/repo"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"]["name"] == "generate-tests"


def test_cli_runs_show_json(monkeypatch):
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: StubWorkspaceContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "runs", "show", "20260101000000000000", "--root", "/tmp/repo"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"]["history_id"] == "20260101000000000000"


def test_cli_agent_show_json(monkeypatch):
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: StubWorkspaceContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "agent", "show", "default", "--root", "/tmp/repo"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"]["name"] == "default"


def test_cli_test_run_json(monkeypatch):
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: StubWorkspaceContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "test", "run", "--root", "/tmp/repo", "-q"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["job_name"] == "ad-hoc-run-tests"


def test_cli_test_generate_estimate_cost_and_timings(monkeypatch):
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: StubWorkspaceContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "--estimate-cost", "--timings", "test", "generate", "--root", "/tmp/repo", "--repo"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["estimated_cost"]["count"] == 1
    assert "timings_ms" in payload


def test_cli_test_generate_dry_run_overrides_write(monkeypatch):
    class TrackingJobs(StubWorkspaceContainer.Jobs):
        def __init__(self):
            self.write_values = []

        def generate_tests(self, target, write=False):
            self.write_values.append(write)
            return self.run_job("ad-hoc-generate")

    container = StubWorkspaceContainer()
    container.jobs = TrackingJobs()
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: container)
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "test", "generate", "--root", "/tmp/repo", "--repo", "--write", "--dry-run"])
    assert exit_code == 0
    assert container.jobs.write_values == [False]
