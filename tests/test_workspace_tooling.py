import os

from src.application.models import RunResult
from src.application.workspace_models import (
    AgentProfile,
    TestTarget,
    USER_BLOCK_BEGIN,
    USER_BLOCK_END,
    WorkspaceConfig,
)
from src.application.workspace_services import AgentOrchestrator, WorkspaceJobService, WorkspaceService
from src.infrastructure.agent_profile_repository import AgentProfileRepository
from src.infrastructure.job_repository import JobRepository
from src.infrastructure.run_history_repository import RunHistoryRepository
from src.infrastructure.source_loader import SourceLoader
from src.infrastructure.test_file_planner import TestFilePlanner
from src.infrastructure.test_writer import TestWriter
from src.infrastructure.workspace_repository import WorkspaceRepository


SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".tox", "dist", "build", ".mypy_cache", ".pytest_cache"}


class StubTestRunner:
    def run_tests(self, request):
        return RunResult(output="FAILED tests/unit/test_math.py::test_divide - ValueError: Cannot divide by zero", returncode=1, coverage="91%")

    def run_multiple(self, modules, work_dir):
        return RunResult(output="FAILED tests/unit/test_math.py::test_divide - ValueError: Cannot divide by zero", returncode=1, coverage="91%")


class StubAiRunner:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def run(self, source_code):
        self.calls.append(source_code)
        return self.output


def _make_workspace(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    src_dir = root / "pkg"
    src_dir.mkdir()
    (src_dir / "math_utils.py").write_text(
        "def add(a: float, b: float) -> float:\n    return a + b\n\n"
        "def divide(a: float, b: float) -> float:\n"
        "    if b == 0:\n        raise ValueError('Cannot divide by zero')\n"
        "    return a / b\n",
        encoding="utf-8",
    )
    workspace_repo = WorkspaceRepository(str(root))
    job_repo = JobRepository(workspace_repo.jobs_dir)
    agent_repo = AgentProfileRepository(workspace_repo.agents_dir, default_model="gpt-5.4-mini")
    workspace_service = WorkspaceService(workspace_repo, job_repo, agent_repo)
    workspace_service.init_workspace(str(root))
    return root, workspace_repo, job_repo, agent_repo


def test_workspace_init_and_status(tmp_path):
    root, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    status = WorkspaceService(workspace_repo, job_repo, agent_repo).status()
    assert status.config.root_path == str(root)
    assert "generate-tests" in status.jobs
    assert "default" in status.agent_profiles


def test_planner_mirrors_source_tree(tmp_path):
    root, workspace_repo, _, _ = _make_workspace(tmp_path)
    planner = TestFilePlanner()
    workspace = workspace_repo.load_config()
    source_path = os.path.join(str(root), "pkg", "math_utils.py")
    planned = planner.plan_paths(workspace, [source_path])[0]
    assert planned.test_path.endswith("tests/unit/pkg/test_math_utils.py")
    assert planned.exists is False


def test_write_plan_preserves_user_block(tmp_path):
    root, workspace_repo, _, _ = _make_workspace(tmp_path)
    planner = TestFilePlanner()
    writer = TestWriter()
    workspace = workspace_repo.load_config()
    source_path = os.path.join(str(root), "pkg", "math_utils.py")
    planned = planner.plan_paths(workspace, [source_path])[0]

    initial_content = (
        "# Managed by Unitra. Do not edit generated sections by hand.\n\n"
        "def test_placeholder():\n    assert True\n\n"
        f"{USER_BLOCK_BEGIN}\n"
        "def test_custom():\n    assert 'keep me'\n"
        f"{USER_BLOCK_END}\n"
    )
    os.makedirs(os.path.dirname(planned.test_path), exist_ok=True)
    with open(planned.test_path, "w", encoding="utf-8") as handle:
        handle.write(initial_content)

    planned_existing = planner.plan_paths(workspace, [source_path])[0]
    write_plan = planner.build_write_plan(
        planned_existing,
        "# Managed by Unitra. Do not edit generated sections by hand.\n\ndef test_new():\n    assert True\n",
    )
    writer.apply([write_plan], write=True)
    written = open(planned.test_path, encoding="utf-8").read()
    assert "def test_new()" in written
    assert "def test_custom()" in written


def test_write_plan_keeps_single_user_block_after_repeat_updates(tmp_path):
    root, workspace_repo, _, _ = _make_workspace(tmp_path)
    planner = TestFilePlanner()
    writer = TestWriter()
    workspace = workspace_repo.load_config()
    source_path = os.path.join(str(root), "pkg", "math_utils.py")
    planned = planner.plan_paths(workspace, [source_path])[0]

    initial_content = (
        "# Managed by Unitra. Do not edit generated sections by hand.\n\n"
        f"{USER_BLOCK_BEGIN}\n"
        "def test_custom():\n    assert 'keep me'\n"
        f"{USER_BLOCK_END}\n"
    )
    os.makedirs(os.path.dirname(planned.test_path), exist_ok=True)
    with open(planned.test_path, "w", encoding="utf-8") as handle:
        handle.write(initial_content)

    generated = (
        "# Managed by Unitra. Do not edit generated sections by hand.\n\n"
        "def test_new():\n    assert True\n\n"
        f"{USER_BLOCK_BEGIN}\n"
        f"{USER_BLOCK_END}\n"
    )

    planned_existing = planner.plan_paths(workspace, [source_path])[0]
    first_plan = planner.build_write_plan(planned_existing, generated)
    writer.apply([first_plan], write=True)

    planned_existing = planner.plan_paths(workspace, [source_path])[0]
    second_plan = planner.build_write_plan(planned_existing, generated)
    writer.apply([second_plan], write=True)

    written = open(planned.test_path, encoding="utf-8").read()
    assert written.count(USER_BLOCK_BEGIN) == 1
    assert written.count(USER_BLOCK_END) == 1
    assert "def test_custom()" in written


def test_orchestrator_generates_managed_artifact(tmp_path):
    root, workspace_repo, _, _ = _make_workspace(tmp_path)
    workspace = workspace_repo.load_config()
    orchestrator = AgentOrchestrator(SourceLoader(SKIP_DIRS), TestFilePlanner())
    artifacts = orchestrator.orchestrate(
        workspace,
        AgentProfile(name="default", model="gpt-5.4-mini"),
        [os.path.join(str(root), "pkg", "math_utils.py")],
    )
    assert len(artifacts) == 1
    assert "Managed by Unitra" in artifacts[0].generated_code
    assert USER_BLOCK_BEGIN in artifacts[0].generated_code


def test_orchestrator_uses_ai_runner_when_available(tmp_path):
    root, workspace_repo, _, _ = _make_workspace(tmp_path)
    workspace = workspace_repo.load_config()
    ai_runner = StubAiRunner("import pytest\n\n\ndef test_ai_generated():\n    assert add(1, 2) == 3\n")
    orchestrator = AgentOrchestrator(SourceLoader(SKIP_DIRS), TestFilePlanner(), ai_runner=ai_runner)

    artifacts = orchestrator.orchestrate(
        workspace,
        AgentProfile(name="default", model="gpt-5.4-mini"),
        [os.path.join(str(root), "pkg", "math_utils.py")],
    )

    assert len(ai_runner.calls) == 1
    assert "Generated with AI assistance" in artifacts[0].generated_code
    assert "def test_ai_generated" in artifacts[0].generated_code
    assert USER_BLOCK_BEGIN in artifacts[0].generated_code


def test_orchestrator_falls_back_when_ai_runner_fails(tmp_path):
    class FailingAiRunner:
        def run(self, source_code):
            raise EnvironmentError("API_KEY not found in .env")

    root, workspace_repo, _, _ = _make_workspace(tmp_path)
    workspace = workspace_repo.load_config()
    orchestrator = AgentOrchestrator(SourceLoader(SKIP_DIRS), TestFilePlanner(), ai_runner=FailingAiRunner())

    artifacts = orchestrator.orchestrate(
        workspace,
        AgentProfile(name="default", model="gpt-5.4-mini"),
        [os.path.join(str(root), "pkg", "math_utils.py")],
    )

    assert "def test_add_basic" in artifacts[0].generated_code
    assert "Generated with AI assistance" not in artifacts[0].generated_code


def test_job_service_generate_preview_and_fix_failures(tmp_path):
    root, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    source_loader = SourceLoader(SKIP_DIRS)
    planner = TestFilePlanner()
    writer = TestWriter()
    service = WorkspaceJobService(
        workspace_repository=workspace_repo,
        job_repository=job_repo,
        agent_repository=agent_repo,
        run_history_repository=RunHistoryRepository(workspace_repo.runs_dir),
        source_loader=source_loader,
        planner=planner,
        writer=writer,
        orchestrator=AgentOrchestrator(source_loader, planner),
        test_runner=StubTestRunner(),
    )

    preview = service.generate_tests(TestTarget(scope="repo", workspace_root=str(root)), write=False)
    assert preview.planned_files
    assert all(not item.written for item in preview.written_files)

    fixed = service.fix_failed_tests(TestTarget(scope="repo", workspace_root=str(root)), write=True)
    assert fixed.written_files
    target_file = fixed.written_files[0].test_path
    content = open(target_file, encoding="utf-8").read()
    divide_start = content.index("def test_divide_parametrize")
    divide_chunk = content[max(0, divide_start - 120):]
    assert "# Managed by Unitra" in content
    assert USER_BLOCK_BEGIN in content
    assert "Avoid zero values for divisor-like parameters." in content
    assert "(0.0, 0.0)" not in divide_chunk
    assert "(1.0, 1.0)" in divide_chunk
    assert fixed.llm_fallback_contexts
    context = fixed.llm_fallback_contexts[0]
    assert context["estimated_input_tokens"] <= 4000
    assert "test_divide" in " ".join(context["failure_tests"])
    assert fixed.history_id


def test_llm_fallback_context_is_budgeted_to_failing_tests(tmp_path):
    root, workspace_repo, _, _ = _make_workspace(tmp_path)
    workspace = workspace_repo.load_config()
    orchestrator = AgentOrchestrator(SourceLoader(SKIP_DIRS), TestFilePlanner())
    generated = (
        "# Managed by Unitra. Do not edit generated sections by hand.\n\n"
        "def test_add_basic():\n    result = add(1.0, 1.0)\n    assert result is not None\n\n"
        "@pytest.mark.parametrize(\"a, b\", [(0.0, 0.0), (-1.0, -1.0), (1000000.0, 1000000.0)])\n"
        "def test_divide_parametrize(a, b):\n    result = divide(a, b)\n    assert result is not None\n\n"
        f"{USER_BLOCK_BEGIN}\n"
        "def test_custom():\n    assert True\n"
        f"{USER_BLOCK_END}\n"
    )
    failure = orchestrator.analyze_failures(
        "FAILED tests/unit/pkg/test_math_utils.py::test_divide_parametrize[0.0-0.0] - ValueError: Cannot divide by zero",
        [type("Plan", (), {"source_path": os.path.join(str(root), "pkg", "math_utils.py"), "test_path": "tests/unit/pkg/test_math_utils.py", "generated_content": generated})()],
        workspace,
        AgentProfile(name="tight", model="gpt-5.4-mini", input_token_budget=120, output_token_budget=80),
    )[0]
    context = failure.llm_fallback_context
    assert context is not None
    assert context["estimated_input_tokens"] <= 120
    assert context["expected_output_tokens"] == 80
    assert context["failure_tests"] == ["test_divide_parametrize"]
    assert len(context["test_snippets"]) == 1


def test_llm_fallback_context_handles_tiny_budget_without_hanging(tmp_path):
    root, workspace_repo, _, _ = _make_workspace(tmp_path)
    workspace = workspace_repo.load_config()
    orchestrator = AgentOrchestrator(SourceLoader(SKIP_DIRS), TestFilePlanner())
    generated = (
        "# Managed by Unitra. Do not edit generated sections by hand.\n\n"
        "def test_add_basic():\n    result = add(1.0, 1.0)\n    assert result is not None\n\n"
        "@pytest.mark.parametrize(\"a, b\", [(0.0, 0.0), (-1.0, -1.0), (1000000.0, 1000000.0)])\n"
        "def test_divide_parametrize(a, b):\n    result = divide(a, b)\n    assert result is not None\n\n"
        f"{USER_BLOCK_BEGIN}\n"
        "def test_custom():\n    assert True\n"
        f"{USER_BLOCK_END}\n"
    )
    failure = orchestrator.analyze_failures(
        "FAILED tests/unit/pkg/test_math_utils.py::test_divide_parametrize[0.0-0.0] - ValueError: Cannot divide by zero",
        [type("Plan", (), {"source_path": os.path.join(str(root), "pkg", "math_utils.py"), "test_path": "tests/unit/pkg/test_math_utils.py", "generated_content": generated})()],
        workspace,
        AgentProfile(name="tiny", model="gpt-5.4-mini", input_token_budget=32, output_token_budget=80),
    )[0]
    context = failure.llm_fallback_context
    assert context is not None
    assert context["truncated"] is True
    assert context["estimated_input_tokens"] <= 32
    assert context["source_snippets"] == []
    assert context["test_snippets"] == []


def test_generate_preview_uses_cached_computation_on_repeat(tmp_path):
    root, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    source_loader = SourceLoader(SKIP_DIRS)
    planner = TestFilePlanner()
    writer = TestWriter()
    orchestrator = AgentOrchestrator(source_loader, planner)
    service = WorkspaceJobService(
        workspace_repository=workspace_repo,
        job_repository=job_repo,
        agent_repository=agent_repo,
        run_history_repository=RunHistoryRepository(workspace_repo.runs_dir),
        source_loader=source_loader,
        planner=planner,
        writer=writer,
        orchestrator=orchestrator,
        test_runner=StubTestRunner(),
    )

    calls = {"count": 0}
    original = orchestrator.orchestrate

    def counting_orchestrate(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    orchestrator.orchestrate = counting_orchestrate

    target = TestTarget(scope="repo", workspace_root=str(root))
    first = service.generate_tests(target, write=False)
    second = service.generate_tests(target, write=False)

    assert first.planned_files
    assert second.planned_files
    assert calls["count"] == 1


def test_generated_workspace_runs_pass_modules_separately(tmp_path):
    class RecordingTestRunner:
        def __init__(self):
            self.modules = None
            self.work_dir = None

        def run_multiple(self, modules, work_dir):
            self.modules = list(modules)
            self.work_dir = work_dir
            return RunResult(output="ok", returncode=0, coverage=None)

    root, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    other_source = root / "pkg" / "other_utils.py"
    other_source.write_text(
        "def divide(a: float, b: float) -> float:\n"
        "    return a / b\n",
        encoding="utf-8",
    )

    source_loader = SourceLoader(SKIP_DIRS)
    planner = TestFilePlanner()
    writer = TestWriter()
    runner = RecordingTestRunner()
    service = WorkspaceJobService(
        workspace_repository=workspace_repo,
        job_repository=job_repo,
        agent_repository=agent_repo,
        run_history_repository=RunHistoryRepository(workspace_repo.runs_dir),
        source_loader=source_loader,
        planner=planner,
        writer=writer,
        orchestrator=AgentOrchestrator(source_loader, planner),
        test_runner=runner,
    )

    preview = service.generate_tests(TestTarget(scope="repo", workspace_root=str(root)), write=False)
    workspace = workspace_repo.load_config()
    result = service._run_generated_tests(preview.planned_files, workspace, None)

    assert result.output == "ok"
    assert runner.work_dir == str(root)
    assert len(runner.modules) == 2
    assert "def divide(a: float, b: float) -> float" in runner.modules[0]
    assert "def divide(a: float, b: float) -> float" in runner.modules[1]
