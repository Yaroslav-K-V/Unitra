import os
import subprocess
import sys

from src.application.ai_policy import AiPolicy
from src.application.exceptions import ValidationError
from src.application.models import RunResult
from src.application.workspace_models import (
    AgentProfile,
    FailureAnalysisArtifact,
    JobDefinition,
    TestTarget,
    USER_BLOCK_BEGIN,
    USER_BLOCK_END,
    WorkspaceConfig,
)
from src.application.guided_services import GuidedAgentService
from src.application.workspace_services import (
    AgentOrchestrator,
    WorkspaceJobService,
    WorkspaceService,
    build_source_binding_preamble,
)
from src.infrastructure.agent_profile_repository import AgentProfileRepository
from src.infrastructure.generation_cache_repository import GenerationCacheRepository
from src.infrastructure.job_repository import JobRepository
from src.infrastructure.run_history_repository import RunHistoryRepository
from src.infrastructure.source_loader import SourceLoader
from src.infrastructure.test_file_planner import TestFilePlanner
from src.infrastructure.test_writer import TestWriter
from src.infrastructure.workspace_repository import WorkspaceRepository
from src.parser import parse_classes, parse_functions
from src.serializers import serialize_run_history_record


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
        self.repair_calls = []

    def run_with_overrides(self, source_code, **kwargs):
        self.calls.append({"source_code": source_code, **kwargs})
        return self.output

    def repair_with_overrides(self, context, **kwargs):
        self.repair_calls.append({"context": context, **kwargs})
        return [{
            "action": "update_test_expectation",
            "test_name": (context.get("failure_tests") or [""])[0],
            "reason": "Generated expectation does not match observed behavior.",
            "details": "Review the assertion before applying.",
            "confidence": 0.8,
        }]


class PassingTestRunner:
    def run_tests(self, request):
        return RunResult(output="PASSED", returncode=0, coverage="100%")

    def run_multiple(self, modules, work_dir):
        return RunResult(output="PASSED", returncode=0, coverage="100%")


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


def _make_job_service(
    workspace_repo,
    job_repo,
    agent_repo,
    ai_runner=None,
    test_runner=None,
    global_ai_policy=None,
):
    source_loader = SourceLoader(SKIP_DIRS)
    planner = TestFilePlanner()
    return WorkspaceJobService(
        workspace_repository=workspace_repo,
        job_repository=job_repo,
        agent_repository=agent_repo,
        run_history_repository=RunHistoryRepository(workspace_repo.runs_dir),
        source_loader=source_loader,
        planner=planner,
        writer=TestWriter(),
        orchestrator=AgentOrchestrator(source_loader, planner, ai_runner=ai_runner),
        test_runner=test_runner or StubTestRunner(),
        global_ai_policy=global_ai_policy,
    )


def test_workspace_init_and_status(tmp_path):
    root, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    status = WorkspaceService(workspace_repo, job_repo, agent_repo).status()
    assert status.config.root_path == str(root)
    assert "generate-tests" in status.jobs
    assert "default" in status.agent_profiles
    assert status.config.ai_policy.inherit is True
    assert status.config.ai_backend.provider == "ollama"
    assert status.config.ai_backend.model == "llama3.2"
    assert status.config.ai_backend.base_url == "http://localhost:11434/v1/"


def test_workspace_ai_policy_override_precedence(tmp_path):
    root, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    service = WorkspaceService(workspace_repo, job_repo, agent_repo)
    global_policy = AiPolicy(ai_generation="ask", ai_repair="ask", ai_explain="auto")

    inherited = service.ai_policy_state(global_policy)
    assert inherited["effective_ai_policy"].ai_generation == "ask"
    assert inherited["ai_policy_source"] == "global"

    overridden = service.save_ai_policy(
        global_policy,
        inherit=False,
        policy_values={"ai_generation": "off", "ai_repair": "auto", "ai_explain": "off"},
    )

    assert overridden["effective_ai_policy"].ai_generation == "off"
    assert overridden["effective_ai_policy"].ai_repair == "auto"
    assert overridden["effective_ai_policy"].ai_explain == "off"
    assert overridden["ai_policy_source"] == "workspace"
    assert workspace_repo.load_config().ai_policy.inherit is False


def test_workspace_service_registers_custom_generator(tmp_path):
    _, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    service = WorkspaceService(workspace_repo, job_repo, agent_repo)

    updated = service.register_generator("tests.custom_generator_plugin:CustomSmokeGenerator")

    assert updated.custom_generators == ["tests.custom_generator_plugin:CustomSmokeGenerator"]
    assert workspace_repo.load_config().custom_generators == ["tests.custom_generator_plugin:CustomSmokeGenerator"]


def test_build_source_binding_preamble_includes_top_level_app_assignments(tmp_path):
    root, workspace_repo, _, _ = _make_workspace(tmp_path)
    source_path = os.path.join(str(root), "pkg", "api.py")
    source_code = (
        "from fastapi import FastAPI\n\n"
        "app = FastAPI()\n\n"
        "@app.get('/')\n"
        "def health():\n"
        "    return {'ok': True}\n"
    )
    with open(source_path, "w", encoding="utf-8") as handle:
        handle.write(source_code)

    preamble = build_source_binding_preamble(
        workspace_repo.load_config().root_path,
        source_path,
        os.path.join(str(root), "tests", "unit", "pkg", "test_api.py"),
        parse_functions(source_code),
        parse_classes(source_code),
        source_code=source_code,
    )

    assert "app = _unitra_source.app" in preamble


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
        use_ai_generation=True,
    )
    assert len(artifacts) == 1
    assert "Managed by Unitra" in artifacts[0].generated_code
    assert "importlib.util.spec_from_file_location" in artifacts[0].generated_code
    assert "add = _unitra_source.add" in artifacts[0].generated_code
    assert "divide = _unitra_source.divide" in artifacts[0].generated_code
    assert USER_BLOCK_BEGIN in artifacts[0].generated_code
    assert artifacts[0].ai_attempted is False
    assert artifacts[0].ai_used is False
    assert artifacts[0].ai_status == "skipped"


def test_orchestrator_uses_ai_runner_when_available(tmp_path):
    root, workspace_repo, _, _ = _make_workspace(tmp_path)
    workspace = workspace_repo.load_config()
    ai_runner = StubAiRunner("import pytest\n\n\ndef test_ai_generated():\n    assert add(1, 2) == 3\n")
    orchestrator = AgentOrchestrator(SourceLoader(SKIP_DIRS), TestFilePlanner(), ai_runner=ai_runner)

    artifacts = orchestrator.orchestrate(
        workspace,
        AgentProfile(name="default", model="gpt-5.4-mini"),
        [os.path.join(str(root), "pkg", "math_utils.py")],
        use_ai_generation=True,
    )

    assert len(ai_runner.calls) == 1
    assert ai_runner.calls[0]["provider"] == "ollama"
    assert ai_runner.calls[0]["base_url"] == "http://localhost:11434/v1/"
    assert ai_runner.calls[0]["model"] == "gpt-5.4-mini"
    assert "Generated with AI assistance" in artifacts[0].generated_code
    assert "def test_ai_generated" in artifacts[0].generated_code
    assert USER_BLOCK_BEGIN in artifacts[0].generated_code
    assert artifacts[0].ai_attempted is True
    assert artifacts[0].ai_used is True
    assert artifacts[0].ai_status == "used"


def test_orchestrator_uses_persistent_generation_cache(tmp_path):
    root, workspace_repo, _, _ = _make_workspace(tmp_path)
    workspace = workspace_repo.load_config()
    cache_repo = GenerationCacheRepository(workspace_repo.cache_dir)
    orchestrator = AgentOrchestrator(
        SourceLoader(SKIP_DIRS),
        TestFilePlanner(),
        generation_cache=cache_repo,
    )
    source_path = os.path.join(str(root), "pkg", "math_utils.py")

    first = orchestrator.orchestrate(
        workspace,
        AgentProfile(name="default", model="gpt-5.4-mini"),
        [source_path],
    )
    second = orchestrator.orchestrate(
        workspace,
        AgentProfile(name="default", model="gpt-5.4-mini"),
        [source_path],
    )

    assert first[0].cache_hit is False
    assert second[0].cache_hit is True


def test_workspace_job_service_execute_with_progress_reports_completion(tmp_path):
    _, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    jobs_service = _make_job_service(workspace_repo, job_repo, agent_repo, test_runner=PassingTestRunner())
    events = []

    result = jobs_service.execute_with_progress(
        JobDefinition(name="generate-tests", mode="generate-tests", target_scope="repo", output_policy="preview"),
        progress_callback=events.append,
    )

    assert result.generated_tests_count >= 1
    assert events[-1]["progress"] == 100
    assert events[-1]["stage"] == "done"


def test_workspace_written_tests_bind_invalid_source_filename(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "1.py").write_text(
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n",
        encoding="utf-8",
    )
    workspace_repo = WorkspaceRepository(str(root))
    job_repo = JobRepository(workspace_repo.jobs_dir)
    agent_repo = AgentProfileRepository(workspace_repo.agents_dir, default_model="gpt-5.4-mini")
    WorkspaceService(workspace_repo, job_repo, agent_repo).init_workspace(str(root))

    source_loader = SourceLoader(SKIP_DIRS)
    planner = TestFilePlanner()
    service = WorkspaceJobService(
        workspace_repository=workspace_repo,
        job_repository=job_repo,
        agent_repository=agent_repo,
        run_history_repository=RunHistoryRepository(workspace_repo.runs_dir),
        source_loader=source_loader,
        planner=planner,
        writer=TestWriter(),
        orchestrator=AgentOrchestrator(source_loader, planner),
        test_runner=StubTestRunner(),
    )

    result = service.generate_tests(TestTarget(scope="repo", workspace_root=str(root)), write=True)
    test_path = result.written_files[0].test_path
    content = open(test_path, encoding="utf-8").read()

    assert "importlib.util.spec_from_file_location" in content
    assert "add = _unitra_source.add" in content

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", os.path.relpath(test_path, str(root))],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_workspace_run_tests_uses_current_python_module_pytest(tmp_path, monkeypatch):
    root, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    service = _make_job_service(workspace_repo, job_repo, agent_repo)
    captured = {}

    def fake_run(args, capture_output, text, cwd, timeout):
        captured.update({
            "args": args,
            "capture_output": capture_output,
            "text": text,
            "cwd": cwd,
            "timeout": timeout,
        })
        return subprocess.CompletedProcess(args, 0, stdout="TOTAL 1 1 100%\n", stderr="")

    import src.application.workspace_services as workspace_services_module

    monkeypatch.setattr(workspace_services_module.subprocess, "run", fake_run)

    result = service.run_tests()

    assert captured["args"][:3] == [sys.executable, "-m", "pytest"]
    assert captured["args"][3:] == ["-q"]
    assert captured["cwd"] == str(root)
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["timeout"] == 30
    assert result.run_returncode == 0
    assert result.run_coverage == "100%"


def test_source_binding_binds_classes_but_not_methods(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    source = root / "user_module.py"
    source.write_text(
        "class User:\n"
        "    def greet(self):\n"
        "        return 'hello'\n",
        encoding="utf-8",
    )
    workspace_repo = WorkspaceRepository(str(root))
    job_repo = JobRepository(workspace_repo.jobs_dir)
    agent_repo = AgentProfileRepository(workspace_repo.agents_dir, default_model="gpt-5.4-mini")
    WorkspaceService(workspace_repo, job_repo, agent_repo).init_workspace(str(root))
    workspace = workspace_repo.load_config()

    artifacts = AgentOrchestrator(SourceLoader(SKIP_DIRS), TestFilePlanner()).orchestrate(
        workspace,
        AgentProfile(name="default", model="gpt-5.4-mini"),
        [str(source)],
    )

    assert "User = _unitra_source.User" in artifacts[0].generated_code
    assert "greet = _unitra_source.greet" not in artifacts[0].generated_code


def test_orchestrator_falls_back_when_ai_runner_fails(tmp_path):
    class FailingAiRunner:
        def run_with_overrides(self, source_code, **kwargs):
            raise EnvironmentError("OLLAMA_BASE_URL did not respond")

    root, workspace_repo, _, _ = _make_workspace(tmp_path)
    workspace = workspace_repo.load_config()
    orchestrator = AgentOrchestrator(SourceLoader(SKIP_DIRS), TestFilePlanner(), ai_runner=FailingAiRunner())

    artifacts = orchestrator.orchestrate(
        workspace,
        AgentProfile(name="default", model="gpt-5.4-mini"),
        [os.path.join(str(root), "pkg", "math_utils.py")],
        use_ai_generation=True,
    )

    assert "def test_add_basic" in artifacts[0].generated_code
    assert "Generated with AI assistance" not in artifacts[0].generated_code
    assert artifacts[0].ai_attempted is True
    assert artifacts[0].ai_used is False
    assert artifacts[0].ai_status == "fallback"


def test_workspace_ai_backend_is_saved_in_unitra_toml(tmp_path):
    _, workspace_repo, _, _ = _make_workspace(tmp_path)

    config_text = open(workspace_repo.config_path, encoding="utf-8").read()

    assert "[ai_backend]" in config_text
    assert 'provider = "ollama"' in config_text
    assert 'model = "llama3.2"' in config_text


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
    assert preview.planned_files[0].ai_attempted is False
    assert preview.planned_files[0].ai_used is False
    assert preview.planned_files[0].ai_status == "skipped"

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
    assert fixed.failure_categories
    assert fixed.failure_categories[0]["category"] == "runtime_error"
    assert fixed.ai_repair_status == "skipped"
    context = fixed.llm_fallback_contexts[0]
    assert context["estimated_input_tokens"] <= 4000
    assert "test_divide" in " ".join(context["failure_tests"])
    assert fixed.history_id


def test_job_service_requires_explicit_ai_generation_consent(tmp_path):
    root, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    source_loader = SourceLoader(SKIP_DIRS)
    planner = TestFilePlanner()
    writer = TestWriter()
    ai_runner = StubAiRunner("def test_ai_generated():\n    assert True\n")
    service = WorkspaceJobService(
        workspace_repository=workspace_repo,
        job_repository=job_repo,
        agent_repository=agent_repo,
        run_history_repository=RunHistoryRepository(workspace_repo.runs_dir),
        source_loader=source_loader,
        planner=planner,
        writer=writer,
        orchestrator=AgentOrchestrator(source_loader, planner, ai_runner=ai_runner),
        test_runner=StubTestRunner(),
        global_ai_policy=AiPolicy(ai_generation="ask"),
    )

    local = service.generate_tests(TestTarget(scope="repo", workspace_root=str(root)), write=False)
    assert ai_runner.calls == []
    assert local.planned_files[0].ai_attempted is False

    ai_preview = service.generate_tests(
        TestTarget(scope="repo", workspace_root=str(root)),
        write=False,
        use_ai_generation=True,
    )
    assert len(ai_runner.calls) == 1
    assert ai_preview.planned_files[0].ai_used is True


def test_job_service_blocks_ai_generation_when_policy_is_off(tmp_path):
    root, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    source_loader = SourceLoader(SKIP_DIRS)
    planner = TestFilePlanner()
    service = WorkspaceJobService(
        workspace_repository=workspace_repo,
        job_repository=job_repo,
        agent_repository=agent_repo,
        run_history_repository=RunHistoryRepository(workspace_repo.runs_dir),
        source_loader=source_loader,
        planner=planner,
        writer=TestWriter(),
        orchestrator=AgentOrchestrator(source_loader, planner, ai_runner=StubAiRunner("def test_x():\n    pass\n")),
        test_runner=StubTestRunner(),
        global_ai_policy=AiPolicy(ai_generation="off"),
    )

    try:
        service.generate_tests(
            TestTarget(scope="repo", workspace_root=str(root)),
            write=False,
            use_ai_generation=True,
        )
    except ValidationError as exc:
        assert "disabled by policy" in str(exc)
    else:
        raise AssertionError("ValidationError was not raised")


def test_ai_repair_ask_requires_explicit_request(tmp_path):
    root, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    ai_runner = StubAiRunner("def test_ai_generated():\n    assert True\n")
    service = _make_job_service(
        workspace_repo,
        job_repo,
        agent_repo,
        ai_runner=ai_runner,
        global_ai_policy=AiPolicy(ai_repair="ask"),
    )

    local = service.fix_failed_tests(TestTarget(scope="repo", workspace_root=str(root)), write=True)
    assert ai_runner.repair_calls == []
    assert local.ai_repair_status == "skipped"

    repaired = service.fix_failed_tests(
        TestTarget(scope="repo", workspace_root=str(root)),
        write=True,
        use_ai_repair=True,
    )
    assert len(ai_runner.repair_calls) == 1
    assert repaired.ai_repair_used is True
    assert repaired.ai_repair_suggestions[0]["action"] == "update_test_expectation"


def test_ai_repair_off_blocks_explicit_request(tmp_path):
    root, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    service = _make_job_service(
        workspace_repo,
        job_repo,
        agent_repo,
        ai_runner=StubAiRunner("def test_ai_generated():\n    assert True\n"),
        global_ai_policy=AiPolicy(ai_repair="off"),
    )

    try:
        service.fix_failed_tests(
            TestTarget(scope="repo", workspace_root=str(root)),
            write=True,
            use_ai_repair=True,
        )
    except ValidationError as exc:
        assert "AI repair is disabled" in str(exc)
    else:
        raise AssertionError("ValidationError was not raised")


def test_ai_repair_auto_calls_ai_for_behavior_failures(tmp_path):
    root, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    ai_runner = StubAiRunner("def test_ai_generated():\n    assert True\n")
    service = _make_job_service(
        workspace_repo,
        job_repo,
        agent_repo,
        ai_runner=ai_runner,
        global_ai_policy=AiPolicy(ai_repair="auto"),
    )

    result = service.fix_failed_tests(TestTarget(scope="repo", workspace_root=str(root)), write=True)

    assert len(ai_runner.repair_calls) == 1
    assert result.ai_repair_requested is False
    assert result.ai_repair_used is True
    assert result.ai_repair_status == "used"


def test_missing_name_failures_are_classified_local_without_ai_repair(tmp_path):
    class MissingNameRunner:
        def run_multiple(self, modules, work_dir):
            return RunResult(
                output="FAILED tests/unit/pkg/test_math_utils.py::test_add_basic - NameError: name 'add' is not defined",
                returncode=1,
                coverage=None,
            )

    root, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    ai_runner = StubAiRunner("def test_ai_generated():\n    assert True\n")
    service = _make_job_service(
        workspace_repo,
        job_repo,
        agent_repo,
        ai_runner=ai_runner,
        test_runner=MissingNameRunner(),
        global_ai_policy=AiPolicy(ai_repair="auto"),
    )

    result = service.fix_failed_tests(TestTarget(scope="repo", workspace_root=str(root)), write=True)

    assert result.failure_categories[0]["category"] == "missing_import_or_name"
    assert result.llm_fallback_contexts == []
    assert result.ai_repair_suggestions == []


def test_guided_core_run_auto_previews_and_awaits_write_approval(tmp_path):
    root, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    workspace_service = WorkspaceService(
        workspace_repo,
        job_repo,
        agent_repo,
        run_history_repository=RunHistoryRepository(workspace_repo.runs_dir),
    )
    jobs_service = _make_job_service(
        workspace_repo,
        job_repo,
        agent_repo,
        test_runner=PassingTestRunner(),
    )
    jobs_service.run_tests = lambda pytest_args=None, timeout=None: type(
        "JobResult",
        (),
        {
            "job_name": "ad-hoc-run-tests",
            "mode": "run-tests",
            "target_scope": "repo",
            "planned_files": [],
            "written_files": [],
            "run_output": "PASSED",
            "run_returncode": 0,
            "run_coverage": "100%",
            "llm_fallback_contexts": [],
            "failure_categories": [],
            "ai_repair_suggestions": [],
            "ai_repair_requested": False,
            "ai_repair_used": False,
            "ai_repair_status": "skipped",
            "ai_repair_reason": "",
            "history_id": "guided-pass-run",
        },
    )()
    guided_service = GuidedAgentService(
        workspace_service=workspace_service,
        jobs_service=jobs_service,
        run_history_repository=RunHistoryRepository(workspace_repo.runs_dir),
    )

    guided = guided_service.create_core_run(TestTarget(scope="repo", workspace_root=str(root)))

    assert guided.history_id
    assert guided.awaiting_step_id == "write_tests"
    assert guided.steps[0].status == "completed"
    assert guided.steps[1].status == "awaiting_approval"
    assert guided.latest_child_run_id
    saved = workspace_service.get_run(guided.history_id)
    assert saved["kind"] == "guided_run"
    assert saved["steps"][0]["status"] == "completed"


def test_guided_core_run_can_complete_after_write_and_run_approvals(tmp_path):
    root, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    workspace_service = WorkspaceService(
        workspace_repo,
        job_repo,
        agent_repo,
        run_history_repository=RunHistoryRepository(workspace_repo.runs_dir),
    )
    jobs_service = _make_job_service(
        workspace_repo,
        job_repo,
        agent_repo,
        test_runner=PassingTestRunner(),
    )
    jobs_service.run_tests = lambda pytest_args=None, timeout=None: type(
        "JobResult",
        (),
        {
            "job_name": "ad-hoc-run-tests",
            "mode": "run-tests",
            "target_scope": "repo",
            "planned_files": [],
            "written_files": [],
            "run_output": "PASSED",
            "run_returncode": 0,
            "run_coverage": "100%",
            "llm_fallback_contexts": [],
            "failure_categories": [],
            "ai_repair_suggestions": [],
            "ai_repair_requested": False,
            "ai_repair_used": False,
            "ai_repair_status": "skipped",
            "ai_repair_reason": "",
            "history_id": "guided-pass-run",
        },
    )()
    guided_service = GuidedAgentService(
        workspace_service=workspace_service,
        jobs_service=jobs_service,
        run_history_repository=RunHistoryRepository(workspace_repo.runs_dir),
    )

    guided = guided_service.create_core_run(TestTarget(scope="repo", workspace_root=str(root)))
    guided = guided_service.approve_step(guided.history_id, "write_tests")
    guided = guided_service.approve_step(guided.history_id, "run_tests")

    assert guided.status == "completed"
    assert guided.awaiting_step_id == ""
    repair_step = next(step for step in guided.steps if step.id == "repair_failures")
    assert repair_step.status == "skipped"
    assert len(guided.child_run_ids) >= 3


def test_serialize_run_history_record_supports_guided_runs(tmp_path):
    root, workspace_repo, job_repo, agent_repo = _make_workspace(tmp_path)
    workspace_service = WorkspaceService(
        workspace_repo,
        job_repo,
        agent_repo,
        run_history_repository=RunHistoryRepository(workspace_repo.runs_dir),
    )
    jobs_service = _make_job_service(
        workspace_repo,
        job_repo,
        agent_repo,
        test_runner=PassingTestRunner(),
    )
    guided_service = GuidedAgentService(
        workspace_service=workspace_service,
        jobs_service=jobs_service,
        run_history_repository=RunHistoryRepository(workspace_repo.runs_dir),
    )

    guided = guided_service.create_core_run(TestTarget(scope="repo", workspace_root=str(root)))
    payload = serialize_run_history_record(
        guided.history_id,
        workspace_service.get_run(guided.history_id),
        model="gpt-5.4-mini",
        run_loader=workspace_service.get_run,
    )

    assert payload["kind"] == "guided_run"
    assert payload["history_id"] == guided.history_id
    assert payload["steps"]
    assert payload["timeline"]
    assert payload["latest_child_run"]["kind"] == "job_run"


def test_local_failure_fix_updates_wrong_exception_type():
    content = (
        "import pytest\n\n"
        "def test_divide_by_zero_raises():\n"
        "    with pytest.raises(ZeroDivisionError):\n"
        "        divide(1.0, 0.0)\n"
    )
    failure = FailureAnalysisArtifact(
        test_path="tests/unit/test_calc.py",
        failures=["FAILED tests/unit/test_calc.py::test_divide_by_zero_raises - ValueError: Cannot divide by zero"],
        recommendations=[],
        failure_tests=["test_divide_by_zero_raises"],
        run_output="ValueError: Cannot divide by zero",
    )

    fixed = WorkspaceJobService._apply_failure_fixes(content, failure)

    assert "pytest.raises(ValueError)" in fixed
    assert "pytest.raises(ZeroDivisionError)" not in fixed


def test_local_failure_fix_removes_failed_parametrize_rows():
    content = (
        "import pytest\n\n"
        "@pytest.mark.parametrize(\"a, b, expected\", [\n"
        "    (0.0, 0.0, 0.0),\n"
        "    (None, 1.0, pytest.approx(1.0)),\n"
        "    ('', '', pytest.raises(TypeError)),\n"
        "])\n"
        "def test_add_parametrize(a, b, expected):\n"
        "    result = add(a, b)\n"
        "    assert result == expected\n"
    )
    failure = FailureAnalysisArtifact(
        test_path="tests/unit/test_calc.py",
        failures=[
            "FAILED tests/unit/test_calc.py::test_add_parametrize[None-1.0-expected1] - TypeError: unsupported",
            "FAILED tests/unit/test_calc.py::test_add_parametrize[--expected2] - AssertionError: assert '' == RaisesExc(TypeError)",
        ],
        recommendations=[],
        failure_tests=["test_add_parametrize", "test_add_parametrize"],
        run_output="",
    )

    fixed = WorkspaceJobService._apply_failure_fixes(content, failure)

    assert "(0.0, 0.0, 0.0)" in fixed
    assert "None, 1.0" not in fixed
    assert "pytest.raises(TypeError)" not in fixed


def test_local_failure_fix_updates_simple_assertion_actual_literal():
    content = (
        "def test_hello_world_basic():\n"
        "    result = hello_world()\n"
        "    assert result == 'Hello, World!'\n"
    )
    failure = FailureAnalysisArtifact(
        test_path="tests/unit/test_1.py",
        failures=["FAILED tests/unit/test_1.py::test_hello_world_basic - AssertionError: assert None == 'Hello, World!'"],
        recommendations=[],
        failure_tests=["test_hello_world_basic"],
        run_output="AssertionError: assert None == 'Hello, World!'",
    )

    fixed = WorkspaceJobService._apply_failure_fixes(content, failure)

    assert "assert result == None" in fixed


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


def test_old_run_history_missing_ai_metadata_serializes_as_unknown():
    payload = {
        "job_name": "generate-tests",
        "mode": "generate-tests",
        "target_scope": "repo",
        "planned_files": [
            {
                "source_path": "/repo/pkg/math_utils.py",
                "test_path": "/repo/tests/unit/pkg/test_math_utils.py",
                "action": "create",
                "generated_content": "",
                "diff": "",
                "managed": False,
            }
        ],
        "written_files": [
            {
                "source_path": "/repo/pkg/math_utils.py",
                "test_path": "/repo/tests/unit/pkg/test_math_utils.py",
                "action": "create",
                "written": False,
                "managed": False,
            }
        ],
        "run_output": "",
        "run_returncode": None,
        "run_coverage": None,
        "llm_fallback_contexts": [],
    }

    result = serialize_run_history_record("old-run", payload)

    assert result["planned_files"][0]["ai_attempted"] is None
    assert result["planned_files"][0]["ai_used"] is None
    assert result["planned_files"][0]["ai_status"] == "unknown"
    assert result["written_files"][0]["ai_attempted"] is None
    assert result["written_files"][0]["ai_used"] is None
    assert result["written_files"][0]["ai_status"] == "unknown"
    assert result["failure_categories"] == []
    assert result["ai_repair_suggestions"] == []
    assert result["ai_repair_status"] == "skipped"
