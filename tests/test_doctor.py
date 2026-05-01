from src.application.doctor import DoctorService
from src.application.workspace_services import WorkspaceService
from src.infrastructure.agent_profile_repository import AgentProfileRepository
from src.infrastructure.job_repository import JobRepository
from src.infrastructure.workspace_repository import WorkspaceRepository


def test_doctor_check_reports_workspace_ai_backend(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    workspace_repo = WorkspaceRepository(str(root))
    job_repo = JobRepository(workspace_repo.jobs_dir)
    agent_repo = AgentProfileRepository(workspace_repo.agents_dir, default_model="llama3.2")
    WorkspaceService(workspace_repo, job_repo, agent_repo).init_workspace(str(root))

    report = DoctorService(workspace_repository_factory=WorkspaceRepository).check(str(root))

    assert report.ok is True
    assert report.checks[0].name == "workspace"
    assert report.checks[0].status == "pass"
    assert "unitra.toml" in report.checks[0].detail
    assert report.checks[1].name == "workspace-ai-backend"
    assert "ollama" in report.checks[1].detail
