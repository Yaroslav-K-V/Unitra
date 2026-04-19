from dataclasses import dataclass, field
from typing import List, Optional

from src.application.ai_policy import WorkspaceAiPolicy


MANAGED_HEADER = "# Managed by Unitra. Do not edit generated sections by hand."
USER_BLOCK_BEGIN = "# >>> UNITRA:USER:BEGIN"
USER_BLOCK_END = "# <<< UNITRA:USER:END"


@dataclass(frozen=True)
class WorkspaceConfig:
    root_path: str
    source_include: List[str] = field(default_factory=lambda: ["**/*.py"])
    source_exclude: List[str] = field(default_factory=lambda: ["tests/**", ".venv/**", "venv/**"])
    test_root: str = "tests/unit"
    test_path_strategy: str = "mirror"
    naming_strategy: str = "test_{module}.py"
    preferred_pytest_args: List[str] = field(default_factory=lambda: ["-q"])
    selected_agent_profile: str = "default"
    ai_policy: WorkspaceAiPolicy = field(default_factory=WorkspaceAiPolicy)


@dataclass(frozen=True)
class WorkspaceStatus:
    config: WorkspaceConfig
    jobs: List[str]
    agent_profiles: List[str]
    recent_runs: List[str]


@dataclass(frozen=True)
class TestTarget:
    __test__ = False
    scope: str
    workspace_root: str
    folder: str = ""
    paths: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlannedTestFile:
    source_path: str
    test_path: str
    exists: bool
    managed: bool


@dataclass(frozen=True)
class WritePlan:
    source_path: str
    test_path: str
    action: str
    generated_content: str
    diff: str
    managed: bool
    preserved_user_block: str = ""
    ai_attempted: Optional[bool] = None
    ai_used: Optional[bool] = None
    ai_status: str = "unknown"
    ai_reason: str = ""


@dataclass(frozen=True)
class ManagedFileResult:
    source_path: str
    test_path: str
    action: str
    written: bool
    managed: bool
    ai_attempted: Optional[bool] = None
    ai_used: Optional[bool] = None
    ai_status: str = "unknown"
    ai_reason: str = ""


@dataclass(frozen=True)
class JobDefinition:
    name: str
    mode: str
    target_scope: str
    target_value: str = ""
    output_policy: str = "preview"
    run_pytest_args: List[str] = field(default_factory=list)
    coverage: bool = False
    timeout: int = 30
    agent_profile: str = "default"
    use_ai_generation: bool = False
    use_ai_repair: bool = False


@dataclass(frozen=True)
class JobRunResult:
    job_name: str
    mode: str
    target_scope: str
    planned_files: List[WritePlan] = field(default_factory=list)
    written_files: List[ManagedFileResult] = field(default_factory=list)
    run_output: str = ""
    run_returncode: Optional[int] = None
    run_coverage: Optional[str] = None
    llm_fallback_contexts: List[dict] = field(default_factory=list)
    failure_categories: List[dict] = field(default_factory=list)
    ai_repair_suggestions: List[dict] = field(default_factory=list)
    ai_repair_requested: bool = False
    ai_repair_used: bool = False
    ai_repair_status: str = "skipped"
    ai_repair_reason: str = ""
    history_id: str = ""


@dataclass(frozen=True)
class AgentProfile:
    name: str
    model: str
    system_prompt_addition: str = ""
    roles_enabled: List[str] = field(default_factory=lambda: ["analyzer", "planner", "generator", "reviewer"])
    max_context: int = 8000
    input_token_budget: int = 4000
    output_token_budget: int = 800
    temperature: float = 0.2
    write_enabled: bool = True
    failure_mode: str = "report"


@dataclass(frozen=True)
class AnalysisArtifact:
    source_path: str
    source_code: str
    functions: List[str]
    classes: List[str]
    imports: List[str]


@dataclass(frozen=True)
class TestPlanArtifact:
    source_path: str
    test_path: str
    test_cases: List[str]
    coverage_goals: List[str]


@dataclass(frozen=True)
class GenerationArtifact:
    source_path: str
    test_path: str
    generated_code: str
    reviewer_notes: List[str]
    ai_attempted: Optional[bool] = None
    ai_used: Optional[bool] = None
    ai_status: str = "unknown"
    ai_reason: str = ""


@dataclass(frozen=True)
class FailureAnalysisArtifact:
    test_path: str
    failures: List[str]
    recommendations: List[str]
    failure_tests: List[str] = field(default_factory=list)
    llm_fallback_context: Optional[dict] = None
    failure_categories: List[dict] = field(default_factory=list)
    run_output: str = ""
