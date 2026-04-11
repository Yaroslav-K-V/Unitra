from dataclasses import dataclass
from typing import Optional

from src.application.services import (
    AiGenerationService,
    GenerationService,
    RecentService,
    SettingsService,
    TestRunService,
)
from src.application.workspace_services import AgentOrchestrator, WorkspaceJobService, WorkspaceService
from src.config import AppConfig, load_config

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".tox",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
}


@dataclass(frozen=True)
class ServiceContainer:
    config: AppConfig
    generation: GenerationService
    ai_generation: AiGenerationService
    test_runner: TestRunService
    recent: RecentService
    settings: SettingsService
    workspace: WorkspaceService
    jobs: WorkspaceJobService


_container: Optional[ServiceContainer] = None


def build_container(config: Optional[AppConfig] = None) -> ServiceContainer:
    from src.infrastructure.ai_runner import AgentAiRunner
    from src.infrastructure.agent_profile_repository import AgentProfileRepository
    from src.infrastructure.job_repository import JobRepository
    from src.infrastructure.recent_repository import JsonRecentRepository
    from src.infrastructure.run_history_repository import RunHistoryRepository
    from src.infrastructure.settings_repository import EnvSettingsRepository
    from src.infrastructure.test_file_planner import TestFilePlanner
    from src.infrastructure.test_writer import TestWriter
    from src.infrastructure.source_loader import SourceLoader
    from src.infrastructure.test_executor import SubprocessTestExecutor
    from src.infrastructure.workspace_repository import WorkspaceRepository

    cfg = config or load_config()
    source_loader = SourceLoader(skip_dirs=SKIP_DIRS)
    workspace_repository = WorkspaceRepository(cfg.root_path)
    job_repository = JobRepository(workspace_repository.jobs_dir)
    agent_repository = AgentProfileRepository(workspace_repository.agents_dir, default_model=cfg.ai_model)
    run_history_repository = RunHistoryRepository(workspace_repository.runs_dir)
    planner = TestFilePlanner()
    writer = TestWriter()
    test_runner = TestRunService(
        source_loader=source_loader,
        test_executor=SubprocessTestExecutor(timeout=cfg.pytest_timeout, fallback_dir=cfg.root_path),
    )
    workspace_service = WorkspaceService(
        repository=workspace_repository,
        job_repository=job_repository,
        agent_repository=agent_repository,
        run_history_repository=run_history_repository,
    )
    jobs_service = WorkspaceJobService(
        workspace_repository=workspace_repository,
        job_repository=job_repository,
        agent_repository=agent_repository,
        run_history_repository=run_history_repository,
        source_loader=source_loader,
        planner=planner,
        writer=writer,
        orchestrator=AgentOrchestrator(source_loader=source_loader, planner=planner),
        test_runner=test_runner,
    )
    return ServiceContainer(
        config=cfg,
        generation=GenerationService(source_loader=source_loader),
        ai_generation=AiGenerationService(source_loader=source_loader, ai_runner=AgentAiRunner()),
        test_runner=test_runner,
        recent=RecentService(
            repository=JsonRecentRepository(recent_path=cfg.recent_path, max_recent=cfg.max_recent)
        ),
        settings=SettingsService(
            repository=EnvSettingsRepository(env_path=cfg.env_path, default_model=cfg.ai_model)
        ),
        workspace=workspace_service,
        jobs=jobs_service,
    )


def get_container() -> ServiceContainer:
    global _container
    if _container is None:
        _container = build_container()
    return _container
