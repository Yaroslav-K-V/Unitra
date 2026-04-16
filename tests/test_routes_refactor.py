import os

import pytest

flask = pytest.importorskip("flask")
from routes.generate import generate_bp
from routes.pages import pages_bp
from routes.runner import runner_bp
from routes.workspace import workspace_bp


class StubContainer:
    class Generation:
        def scan_count(self, folder):
            return type("ScanResult", (), {"count": 7})()

        def generate_from_code(self, code):
            return type("Result", (), {"__dict__": {"test_code": "ok", "conftest_code": "", "functions_found": 1, "classes_found": 0, "tests_generated": 1, "files_scanned": 0}})()

    class Recent:
        def list_recent(self):
            return [type("Item", (), {"__dict__": {"path": "/tmp/a.py", "type": "file"}})()]

        def add_recent(self, path):
            self.last_path = path

    class TestRunner:
        def run_tests(self, request):
            return type("RunResult", (), {"__dict__": {"output": "done", "returncode": 0, "coverage": None}})()

    class Settings:
        def save_settings(self, request):
            return type("SettingsResult", (), {"saved": True, "model": request.model, "show_hints": request.show_hints if request.show_hints is not None else True})()

    class AiGeneration:
        def generate_from_code(self, code):
            return type("Result", (), {"__dict__": {"test_code": "ai", "conftest_code": "", "functions_found": 1, "classes_found": 0, "tests_generated": 1, "files_scanned": 0}})()

        def stream_from_code(self, code):
            yield "chunk"

    class Config:
        root_path = "."
        ai_model = "gpt-5.4-mini"

    class Workspace:
        def init_workspace(self, root):
            return type("Cfg", (), {"__dict__": {"root_path": root, "selected_agent_profile": "default", "test_root": "tests/unit"}})()

        def status(self):
            return type(
                "Status",
                (),
                {
                    "config": type("Cfg", (), {"__dict__": {"root_path": ".", "selected_agent_profile": "default", "test_root": "tests/unit"}})(),
                    "jobs": ["generate-tests"],
                    "agent_profiles": ["default"],
                    "recent_runs": ["abc"],
                },
            )()

    class Jobs:
        def list_jobs(self):
            return ["generate-tests"]

        def run_job(self, name, target_value="", output_policy=""):
            return type(
                "JobResult",
                (),
                {
                    "job_name": name,
                    "mode": "run-tests",
                    "target_scope": "repo",
                    "planned_files": [],
                    "written_files": [],
                    "run_output": "workspace output",
                    "run_returncode": 0,
                    "run_coverage": "90%",
                    "llm_fallback_contexts": [],
                    "history_id": "abc",
                },
            )()

        def generate_tests(self, target, write=False):
            return self.run_job("ad-hoc-generate")

        def update_tests(self, target, write=False):
            return self.run_job("ad-hoc-update")

        def fix_failed_tests(self, target, write=False):
            return self.run_job("ad-hoc-fix")

    def __init__(self):
        self.generation = self.Generation()
        self.recent = self.Recent()
        self.test_runner = self.TestRunner()
        self.settings = self.Settings()
        self.ai_generation = self.AiGeneration()
        self.config = self.Config()
        self.workspace = self.Workspace()
        self.jobs = self.Jobs()


def _build_app():
    app = flask.Flask(
        __name__,
        root_path=os.getcwd(),
        template_folder="templates",
        static_folder="static",
    )
    app.register_blueprint(generate_bp)
    app.register_blueprint(runner_bp)
    app.register_blueprint(workspace_bp)
    app.register_blueprint(pages_bp)
    return app


def test_generate_route_uses_service(monkeypatch):
    import routes.generate as generate_module

    monkeypatch.setattr(generate_module, "get_container", lambda: StubContainer())
    client = _build_app().test_client()
    response = client.post("/generate", json={"code": "def add(a, b): return a + b"})
    assert response.status_code == 200
    assert response.get_json()["test_code"] == "ok"


def test_scan_count_route_uses_service(monkeypatch):
    import routes.generate as generate_module

    monkeypatch.setattr(generate_module, "get_container", lambda: StubContainer())
    client = _build_app().test_client()
    response = client.get("/scan-count?folder=/tmp/project")
    assert response.status_code == 200
    assert response.get_json()["count"] == 7


def test_recent_route_uses_service(monkeypatch):
    import routes.runner as runner_module

    monkeypatch.setattr(runner_module, "get_container", lambda: StubContainer())
    client = _build_app().test_client()
    response = client.get("/recent")
    assert response.status_code == 200
    assert response.get_json()[0]["path"] == "/tmp/a.py"


def test_run_tests_route_uses_service(monkeypatch):
    import routes.runner as runner_module

    monkeypatch.setattr(runner_module, "get_container", lambda: StubContainer())
    client = _build_app().test_client()
    response = client.post("/run-tests", json={"test_code": "def test_x(): pass"})
    assert response.status_code == 200
    assert response.get_json()["output"] == "done"


def test_workspace_status_route_uses_service(monkeypatch):
    import routes.workspace as workspace_module

    monkeypatch.setattr(workspace_module, "_container_for_root", lambda root: StubContainer())
    client = _build_app().test_client()
    response = client.get("/workspace/status?root=/tmp/project")
    assert response.status_code == 200
    assert response.get_json()["jobs"] == ["generate-tests"]


def test_workspace_runs_route_uses_service(monkeypatch):
    import routes.workspace as workspace_module

    monkeypatch.setattr(workspace_module, "_container_for_root", lambda root: StubContainer())
    client = _build_app().test_client()
    response = client.get("/workspace/runs?root=/tmp/project&limit=3")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload[0]["history_id"] == "abc"
    assert payload[0]["job_name"] == "run-tests"


def test_recent_route_supports_explicit_recent_path(monkeypatch, tmp_path):
    import routes.runner as runner_module

    recent_path = tmp_path / "recent.json"
    recent_path.write_text("[]", encoding="utf-8")

    container = StubContainer()
    container.config = type("Config", (), {"root_path": ".", "recent_path": str(recent_path)})()

    monkeypatch.setattr(runner_module, "get_container", lambda: container)
    runner_module._RECENT_CACHE = None

    client = _build_app().test_client()
    response = client.get("/recent")

    assert response.status_code == 200
    assert response.get_json()[0]["path"] == "/tmp/a.py"


def test_workspace_runs_route_prefers_workspace_history_service(monkeypatch):
    import routes.workspace as workspace_module

    class HistoryWorkspace(StubContainer.Workspace):
        def __init__(self):
            self.list_calls = 0
            self.get_calls = 0

        def list_runs(self, limit=20):
            self.list_calls += 1
            return ["20260101000000000000"][:limit]

        def get_run(self, history_id):
            self.get_calls += 1
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

    container = StubContainer()
    container.workspace = HistoryWorkspace()

    monkeypatch.setattr(workspace_module, "_container_for_root", lambda root: container)
    monkeypatch.setattr(workspace_module, "_workspace_signature", lambda root: ("stable", root))
    workspace_module._PAYLOAD_CACHE.clear()

    client = _build_app().test_client()
    first = client.get("/workspace/runs?root=/tmp/project&limit=3")
    second = client.get("/workspace/runs?root=/tmp/project&limit=3")

    assert first.status_code == 200
    assert second.status_code == 200
    payload = first.get_json()
    assert payload[0]["history_id"] == "20260101000000000000"
    assert payload[0]["run"]["coverage"] == "90%"
    assert set(payload[0].keys()) >= {
        "history_id",
        "job_name",
        "mode",
        "target_scope",
        "planned_files",
        "written_files",
        "run",
        "llm_fallback_contexts",
        "fallback_context_summary",
    }
    assert container.workspace.list_calls == 1
    assert container.workspace.get_calls == 1


def test_workspace_generate_route_uses_service(monkeypatch):
    import routes.workspace as workspace_module

    monkeypatch.setattr(workspace_module, "_container_for_root", lambda root: StubContainer())
    client = _build_app().test_client()
    response = client.post("/workspace/test/generate", json={"root": "/tmp/project", "scope": "repo", "write": False})
    assert response.status_code == 200
    assert response.get_json()["job_name"] == "ad-hoc-generate"


def test_project_redirects_to_workspace():
    client = _build_app().test_client()
    response = client.get("/project")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/workspace")


def test_ai_redirects_to_workspace():
    client = _build_app().test_client()
    response = client.get("/ai")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/workspace")


def test_home_page_exposes_workspace_contract_targets():
    client = _build_app().test_client()
    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="recent-list"' in html
    assert 'id="home-agent-status"' in html
    assert 'id="home-runs"' in html
    assert "/static/scripts/workspace-shared.js" in html


def test_workspace_page_exposes_feedback_and_workspace_panels():
    client = _build_app().test_client()
    response = client.get("/workspace")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="workspace-feedback"' in html
    assert 'id="workspace-agent-profile"' in html
    assert 'id="workspace-runs"' in html
    assert "data-workspace-action" in html


def test_info_page_exposes_unitra_overview():
    client = _build_app().test_client()
    response = client.get("/info")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Product overview" in html
    assert "What Unitra is" in html
    assert "Local-first guarantees" in html


def test_workspace_container_cache_reuses_container(monkeypatch):
    import routes.workspace as workspace_module

    workspace_module._CONTAINER_CACHE.clear()
    workspace_module._PAYLOAD_CACHE.clear()

    calls = {"load_config": 0, "build_container": 0}

    def fake_load_config(root_path="."):
        calls["load_config"] += 1
        return {"root": root_path}

    def fake_build_container(config):
        calls["build_container"] += 1
        return {"config": config}

    monkeypatch.setattr(workspace_module, "load_config", fake_load_config)
    monkeypatch.setattr(workspace_module, "build_container", fake_build_container)

    first = workspace_module._container_for_root("/tmp/project")
    second = workspace_module._container_for_root("/tmp/project")

    assert first == second
    assert calls["load_config"] == 1
    assert calls["build_container"] == 1


def test_workspace_status_payload_cache_hits_factory_once(monkeypatch):
    import routes.workspace as workspace_module

    workspace_module._CONTAINER_CACHE.clear()
    workspace_module._PAYLOAD_CACHE.clear()

    root = "/tmp/project"
    calls = {"factory": 0}

    monkeypatch.setattr(workspace_module, "_workspace_signature", lambda value: ("stable", value))

    def factory():
        calls["factory"] += 1
        return {"ok": True}

    first = workspace_module._cached_payload(root, "status", factory)
    second = workspace_module._cached_payload(root, "status", factory)

    assert first == {"ok": True}
    assert second == {"ok": True}
    assert calls["factory"] == 1


def test_recent_route_cache_reuses_payload_until_invalidated(monkeypatch):
    import routes.runner as runner_module

    class CachedRecentService:
        def __init__(self):
            self.calls = 0

        def list_recent(self):
            self.calls += 1
            return [type("Item", (), {"__dict__": {"path": f"/tmp/{self.calls}.py", "type": "file"}})()]

        def add_recent(self, path):
            return None

    service = CachedRecentService()
    container = StubContainer()
    container.recent = service
    container.config = type("Config", (), {"recent_path": "/tmp/recent.json"})()

    monkeypatch.setattr(runner_module, "get_container", lambda: container)
    monkeypatch.setattr(runner_module, "_recent_signature", lambda: ("stable",))
    runner_module._RECENT_CACHE = None

    client = _build_app().test_client()
    first = client.get("/recent")
    second = client.get("/recent")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json() == second.get_json()
    assert service.calls == 1

    client.post("/recent/add", json={"path": "/tmp/new.py"})
    third = client.get("/recent")
    assert third.status_code == 200
    assert service.calls == 2
