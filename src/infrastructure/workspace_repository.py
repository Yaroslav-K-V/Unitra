import os
from typing import List

from src.application.exceptions import ValidationError
from src.application.workspace_models import WorkspaceConfig
from src.infrastructure.simple_toml import dumps, loads


class WorkspaceRepository:
    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.abspath(workspace_root)
        self.unitra_dir = os.path.join(self.workspace_root, ".unitra")
        self.config_path = os.path.join(self.unitra_dir, "unitra.toml")
        self.jobs_dir = os.path.join(self.unitra_dir, "jobs")
        self.agents_dir = os.path.join(self.unitra_dir, "agents")
        self.runs_dir = os.path.join(self.unitra_dir, "runs")

    def init_workspace(self, config: WorkspaceConfig) -> WorkspaceConfig:
        os.makedirs(self.unitra_dir, exist_ok=True)
        os.makedirs(self.jobs_dir, exist_ok=True)
        os.makedirs(self.agents_dir, exist_ok=True)
        os.makedirs(self.runs_dir, exist_ok=True)
        self.save_config(config)
        return config

    def load_config(self) -> WorkspaceConfig:
        if not os.path.exists(self.config_path):
            raise ValidationError("Workspace is not initialized. Run `unitra workspace init` first.")
        raw = loads(self._read(self.config_path))
        workspace = raw.get("workspace", {})
        output = raw.get("output", {})
        run = raw.get("run", {})
        agent = raw.get("agent", {})
        return WorkspaceConfig(
            root_path=self.workspace_root,
            source_include=list(workspace.get("source_include", ["**/*.py"])),
            source_exclude=list(workspace.get("source_exclude", ["tests/**", ".venv/**", "venv/**"])),
            test_root=output.get("test_root", "tests/unit"),
            test_path_strategy=output.get("test_path_strategy", "mirror"),
            naming_strategy=output.get("naming_strategy", "test_{module}.py"),
            preferred_pytest_args=list(run.get("preferred_pytest_args", ["-q"])),
            selected_agent_profile=agent.get("selected_profile", "default"),
        )

    def save_config(self, config: WorkspaceConfig) -> None:
        os.makedirs(self.unitra_dir, exist_ok=True)
        text = dumps({
            "workspace": {
                "root_path": config.root_path,
                "source_include": config.source_include,
                "source_exclude": config.source_exclude,
            },
            "output": {
                "test_root": config.test_root,
                "test_path_strategy": config.test_path_strategy,
                "naming_strategy": config.naming_strategy,
            },
            "run": {
                "preferred_pytest_args": config.preferred_pytest_args,
            },
            "agent": {
                "selected_profile": config.selected_agent_profile,
            },
        })
        self._write(self.config_path, text)

    def list_job_names(self) -> List[str]:
        if not os.path.isdir(self.jobs_dir):
            return []
        return sorted(
            filename[:-5]
            for filename in os.listdir(self.jobs_dir)
            if filename.endswith(".toml")
        )

    def list_agent_profile_names(self) -> List[str]:
        if not os.path.isdir(self.agents_dir):
            return []
        return sorted(
            filename[:-5]
            for filename in os.listdir(self.agents_dir)
            if filename.endswith(".toml")
        )

    def list_recent_run_ids(self, limit: int = 10) -> List[str]:
        if not os.path.isdir(self.runs_dir):
            return []
        run_files = sorted(
            (filename[:-5] for filename in os.listdir(self.runs_dir) if filename.endswith(".json")),
            reverse=True,
        )
        return run_files[:limit]

    @staticmethod
    def _read(path: str) -> str:
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    @staticmethod
    def _write(path: str, content: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
