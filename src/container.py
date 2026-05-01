from dataclasses import dataclass
from typing import Optional

from src.application.services import (
    AiGenerationService,
    GenerationService,
    RecentService,
    SettingsService,
    TestRunService,
)
from src.application.doctor import DoctorService
from src.application.guided_services import GuidedAgentService
from src.application.workspace_services import AgentOrchestrator, WorkspaceJobService, WorkspaceService
from src.config import AppConfig, load_config
from src.generator_plugins import GeneratorRegistry

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
    generator_registry: GeneratorRegistry
    generation: GenerationService
    ai_generation: AiGenerationService
    test_runner: TestRunService
    recent: RecentService
    settings: SettingsService
    doctor: DoctorService
    workspace: WorkspaceService
    jobs: WorkspaceJobService
    guided: GuidedAgentService


_container: Optional[ServiceContainer] = None


def build_container(config: Optional[AppConfig] = None) -> ServiceContainer:
    from src.infrastructure.ai_runner import AgentAiRunner
    from src.infrastructure.agent_profile_repository import AgentProfileRepository
    from src.infrastructure.generation_cache_repository import GenerationCacheRepository
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
    generator_registry = GeneratorRegistry()
    workspace_repository = WorkspaceRepository(cfg.root_path)
    job_repository = JobRepository(workspace_repository.jobs_dir)
    agent_repository = AgentProfileRepository(workspace_repository.agents_dir, default_model=cfg.ai_model)
    run_history_repository = RunHistoryRepository(workspace_repository.runs_dir)
    generation_cache = GenerationCacheRepository(workspace_repository.cache_dir)
    planner = TestFilePlanner()
    writer = TestWriter()
    ai_runner = AgentAiRunner(
        env_path=cfg.env_path,
        provider=cfg.ai_provider,
        model=cfg.ai_model,
        temperature=cfg.ai_temperature,
        max_context=cfg.ai_max_context,
    )
    test_runner = TestRunService(
        source_loader=source_loader,
        test_executor=SubprocessTestExecutor(timeout=cfg.pytest_timeout, fallback_dir=cfg.root_path),
    )
    workspace_service = WorkspaceService(
        repository=workspace_repository,
        job_repository=job_repository,
        agent_repository=agent_repository,
        run_history_repository=run_history_repository,
        generator_registry=generator_registry,
    )
    jobs_service = WorkspaceJobService(
        workspace_repository=workspace_repository,
        job_repository=job_repository,
        agent_repository=agent_repository,
        run_history_repository=run_history_repository,
        source_loader=source_loader,
        planner=planner,
        writer=writer,
        orchestrator=AgentOrchestrator(
            source_loader=source_loader,
            planner=planner,
            ai_runner=ai_runner,
            generator_registry=generator_registry,
            generation_cache=generation_cache,
        ),
        test_runner=test_runner,
        global_ai_policy=cfg.ai_policy,
    )
    return ServiceContainer(
        config=cfg,
        generator_registry=generator_registry,
        generation=GenerationService(source_loader=source_loader, generator_registry=generator_registry),
        ai_generation=AiGenerationService(source_loader=source_loader, ai_runner=ai_runner),
        test_runner=test_runner,
        recent=RecentService(
            repository=JsonRecentRepository(recent_path=cfg.recent_path, max_recent=cfg.max_recent)
        ),
        settings=SettingsService(
            repository=EnvSettingsRepository(env_path=cfg.env_path, default_model=cfg.ai_model, settings_path=cfg.settings_path)
        ),
        doctor=DoctorService(workspace_repository_factory=WorkspaceRepository),
        workspace=workspace_service,
        jobs=jobs_service,
        guided=GuidedAgentService(
            workspace_service=workspace_service,
            jobs_service=jobs_service,
            run_history_repository=run_history_repository,
        ),
    )


def get_container() -> ServiceContainer:
    global _container
    if _container is None:
        _container = build_container()
    return _container


def reset_container() -> None:
    global _container
    _container = None
