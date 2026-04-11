from src.tui.actions import TuiActions
from src.tui.state import SessionState


class StubWorkspaceContainer:
    class Workspace:
        def __init__(self):
            self._status = type(
                "Status",
                (),
                {
                    "config": type(
                        "Cfg",
                        (),
                        {
                            "__dict__": {
                                "root_path": "/tmp/repo",
                                "selected_agent_profile": "default",
                                "test_root": "tests/unit",
                            }
                        },
                    )(),
                    "jobs": ["generate-tests"],
                    "agent_profiles": ["default"],
                    "recent_runs": ["run-1"],
                },
            )()

        def status(self):
            return self._status

        def validate(self):
            return self._status

        def init_workspace(self, root):
            return type("Cfg", (), {"root_path": root, "selected_agent_profile": "default"})()

        def list_runs(self, limit=20):
            return ["run-1"]

        def get_run(self, history_id):
            return {
                "job_name": "run-tests",
                "mode": "run-tests",
                "target_scope": "repo",
                "planned_files": [],
                "written_files": [],
                "run_output": "failed",
                "run_returncode": 1,
                "run_coverage": "91%",
                "llm_fallback_contexts": [],
            }

        def list_agent_profiles(self):
            return [type("Profile", (), {"__dict__": {"name": "default", "model": "gpt-5.4-mini"}})()]

        def get_agent_profile(self, name):
            return type("Profile", (), {"__dict__": {"name": name, "model": "gpt-5.4-mini"}})()

        def list_jobs(self):
            return [type("Job", (), {"__dict__": {"name": "generate-tests", "mode": "generate-tests"}})()]

        def get_job(self, name):
            return type("Job", (), {"__dict__": {"name": name, "mode": "generate-tests"}})()

    class Jobs:
        def _result(self, name, returncode=None):
            return type(
                "JobResult",
                (),
                {
                    "job_name": name,
                    "mode": name,
                    "target_scope": "repo",
                    "planned_files": [],
                    "written_files": [],
                    "run_output": "ok" if returncode in (None, 0) else "failed",
                    "run_returncode": returncode,
                    "run_coverage": "90%",
                    "llm_fallback_contexts": [],
                    "history_id": "history-1",
                },
            )()

        def run_job(self, name, target_value="", output_policy=""):
            return self._result(name)

        def generate_tests(self, target, write=False):
            return self._result("generate-tests")

        def update_tests(self, target, write=False):
            return self._result("update-tests")

        def fix_failed_tests(self, target, write=False):
            return self._result("fix-failures", returncode=1)

        def run_tests(self, pytest_args=None, timeout=None):
            return self._result("run-tests", returncode=0)

    def __init__(self):
        self.workspace = self.Workspace()
        self.jobs = self.Jobs()
        self.config = type("Config", (), {"ai_model": "gpt-5.4-mini"})()


class StubQuickContainer:
    class Generation:
        def generate_from_code(self, code):
            return type("Result", (), {"test_code": f"# generated for\n{code}", "functions_found": 1})()

    class Runner:
        def run_tests(self, request):
            return type("Run", (), {"output": "ok", "returncode": 0, "coverage": "100%"})()

    def __init__(self):
        self.generation = self.Generation()
        self.test_runner = self.Runner()


def test_tui_actions_open_preview_and_runs():
    session = SessionState()
    actions = TuiActions(
        workspace_container_loader=lambda root: StubWorkspaceContainer(),
        quick_container_loader=lambda: StubQuickContainer(),
    )

    opened = actions.select_workspace(session, "/tmp/repo")
    preview = actions.preview_generate(session)
    runs = actions.list_runs(session)

    assert opened.ok is True
    assert preview.payload["job_name"] == "generate-tests"
    assert runs.payload["runs"] == ["run-1"]


def test_tui_actions_show_agent_and_run_quick_flow():
    session = SessionState()
    actions = TuiActions(
        workspace_container_loader=lambda root: StubWorkspaceContainer(),
        quick_container_loader=lambda: StubQuickContainer(),
    )

    actions.select_workspace(session, "/tmp/repo")
    profile = actions.show_agent(session, "default")
    quick = actions.quick_generate(session, "def add(a, b): return a + b")
    run = actions.quick_run(session, quick.payload["test_code"])

    assert profile.payload["name"] == "default"
    assert quick.payload["functions_found"] == 1
    assert run.payload["run"]["coverage"] == "100%"

