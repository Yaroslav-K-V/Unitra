import io
import json
from contextlib import redirect_stdout

import src.cli as cli_module
from src.application.ai_policy import WorkspaceAiPolicy


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
            if history_id == "guided-1":
                return {
                    "kind": "guided_run",
                    "history_id": "guided-1",
                    "workflow_source": "core",
                    "workflow_name": "core_repo_flow",
                    "status": "awaiting_approval",
                    "target_scope": "repo",
                    "target_value": "",
                    "current_step_id": "write_tests",
                    "awaiting_step_id": "write_tests",
                    "child_run_ids": ["abc"],
                    "steps": [
                        {
                            "id": "preview_changes",
                            "kind": "preview_changes",
                            "title": "Preview managed changes",
                            "status": "completed",
                            "requires_approval": False,
                            "skippable": False,
                            "child_run_id": "abc",
                            "summary": "preview only",
                        },
                        {
                            "id": "write_tests",
                            "kind": "write_tests",
                            "title": "Write managed tests",
                            "status": "awaiting_approval",
                            "requires_approval": True,
                            "skippable": False,
                            "summary": "Awaiting approval",
                        },
                    ],
                    "timeline": [
                        {
                            "id": "evt-1",
                            "at": "2026-01-01T00:00:00+00:00",
                            "stage": "plan",
                            "step_id": "",
                            "status": "created",
                            "label": "Guided plan created",
                            "detail": "Built the core repo workflow.",
                        }
                    ],
                    "latest_child_run_id": "abc",
                }
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

        def ai_policy_state(self, global_policy):
            return {
                "effective_ai_policy": global_policy,
                "global_ai_policy": global_policy,
                "workspace_ai_policy": {"inherit": True, **global_policy.to_dict()},
                "ai_policy_source": "global",
            }

        def save_ai_policy(self, global_policy, inherit=True, policy_values=None):
            workspace_policy = WorkspaceAiPolicy.from_dict({"inherit": inherit, **(policy_values or {})})
            return {
                "effective_ai_policy": workspace_policy.effective(global_policy),
                "global_ai_policy": global_policy,
                "workspace_ai_policy": workspace_policy,
                "ai_policy_source": workspace_policy.source(),
            }

        def list_generators(self):
            return [
                {
                    "name": "ast-basic",
                    "project_type": "vanilla-python",
                    "source": "builtin",
                    "priority": 10,
                    "factory": "src.generator_plugins.builtin:VanillaPythonGenerator",
                    "loaded": True,
                    "error": "",
                }
            ]

        def register_generator(self, factory):
            return type("Cfg", (), {"custom_generators": [factory]})()

        def unregister_generator(self, factory):
            return type("Cfg", (), {"custom_generators": []})()

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

    class Guided:
        def create_core_run(self, target):
            return type("GuidedRun", (), {"history_id": "guided-1"})()

        def create_job_run(self, name):
            return type("GuidedRun", (), {"history_id": "guided-1"})()

        def list_runs(self, limit=20):
            return ["guided-1"][:limit]

        def approve_step(self, history_id, step_id, use_ai_generation=False, use_ai_repair=False):
            return type("GuidedRun", (), {"history_id": history_id})()

        def skip_step(self, history_id, step_id):
            return type("GuidedRun", (), {"history_id": history_id})()

        def reject_step(self, history_id, step_id):
            return type("GuidedRun", (), {"history_id": history_id})()

    def __init__(self):
        self.workspace = self.Workspace()
        self.jobs = self.Jobs()
        self.guided = self.Guided()
        self.generation = None
        self.ai_generation = None
        self.test_runner = None
        self.recent = None
        self.settings = None
        self.config = type("Config", (), {"ai_model": "gpt-5.4-mini", "ai_policy": cli_module.AiPolicy()})()


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


def test_cli_workspace_ai_policy_show_and_set(monkeypatch):
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: StubWorkspaceContainer())

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "workspace", "ai-policy", "show", "--root", "/tmp/repo"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"]["effective_ai_policy"]["ai_generation"] == "off"

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main([
            "--json",
            "workspace",
            "ai-policy",
            "set",
            "--root",
            "/tmp/repo",
            "--no-inherit",
            "--ai-generation",
            "ask",
            "--ai-repair",
            "auto",
        ])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"]["workspace_ai_policy"]["inherit"] is False
    assert payload["result"]["effective_ai_policy"]["ai_generation"] == "ask"


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


def test_cli_test_fix_failures_passes_ai_repair_flag(monkeypatch):
    container = StubWorkspaceContainer()
    seen = {}

    def fix_failed_tests(target, write=False, use_ai_generation=False, use_ai_repair=False):
        seen["use_ai_repair"] = use_ai_repair
        return container.jobs.run_job("ad-hoc-fix")

    container.jobs.fix_failed_tests = fix_failed_tests
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: container)

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main([
            "--json",
            "test",
            "fix-failures",
            "--root",
            "/tmp/repo",
            "--repo",
            "--use-ai-repair",
        ])

    assert exit_code == 0
    assert seen["use_ai_repair"] is True


def test_cli_workspace_validate_json(monkeypatch):
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: StubWorkspaceContainer())
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "workspace", "validate", "--root", "/tmp/repo"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"]["valid"] is True


def test_cli_workspace_generator_commands(monkeypatch):
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: StubWorkspaceContainer())

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "workspace", "generator", "list", "--root", "/tmp/repo"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"][0]["name"] == "ast-basic"

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main([
            "--json",
            "workspace",
            "generator",
            "register",
            "tests.custom_generator_plugin:CustomSmokeGenerator",
            "--root",
            "/tmp/repo",
        ])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"]["custom_generators"] == ["tests.custom_generator_plugin:CustomSmokeGenerator"]

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main([
            "--json",
            "workspace",
            "generator",
            "unregister",
            "tests.custom_generator_plugin:CustomSmokeGenerator",
            "--root",
            "/tmp/repo",
        ])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"]["custom_generators"] == []


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


def test_cli_guided_create_show_and_list(monkeypatch):
    monkeypatch.setattr(cli_module, "_container_for_root", lambda root: StubWorkspaceContainer())

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "guided", "create", "--root", "/tmp/repo", "--repo"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"]["kind"] == "guided_run"

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "guided", "show", "guided-1", "--root", "/tmp/repo"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"]["history_id"] == "guided-1"

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli_module.main(["--json", "guided", "list", "--root", "/tmp/repo"])
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["result"][0]["kind"] == "guided_run"
