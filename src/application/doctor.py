"""Environment and workspace diagnostics for Unitra."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Callable, List
from urllib import error as urllib_error
from urllib import request as urllib_request


@dataclass(frozen=True)
class DiagnosticCheck:
    """A single doctor or check result."""

    name: str
    status: str
    detail: str
    command: str = ""


@dataclass(frozen=True)
class DiagnosticReport:
    """Aggregate result for `unitra doctor` and `unitra check`."""

    mode: str
    workspace_root: str
    checks: List[DiagnosticCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.status != "fail" for check in self.checks)


class DoctorService:
    """Runs local environment and workspace diagnostics."""

    def __init__(self, workspace_repository_factory: Callable[[str], object]):
        self._workspace_repository_factory = workspace_repository_factory

    def doctor(self, root_path: str) -> DiagnosticReport:
        root = os.path.abspath(root_path)
        workspace_check, workspace_config = self._workspace_check(root)
        checks = [
            self._python_check(),
            self._command_check("pytest", "pytest", module_name="pytest"),
            self._command_check("coverage", "coverage", module_name="coverage", required=False),
            self._command_check("ruff", "ruff", module_name="ruff", required=False),
            workspace_check,
        ]
        checks.extend(self._ollama_checks(workspace_config))
        return DiagnosticReport(mode="doctor", workspace_root=root, checks=checks)

    def check(self, root_path: str) -> DiagnosticReport:
        root = os.path.abspath(root_path)
        workspace_check, workspace_config = self._workspace_check(root)
        checks = [workspace_check]
        if workspace_config is not None:
            checks.append(
                DiagnosticCheck(
                    name="workspace-ai-backend",
                    status="pass",
                    detail=(
                        f"{workspace_config.ai_backend.provider} "
                        f"({workspace_config.ai_backend.model}) @ {workspace_config.ai_backend.base_url}"
                    ),
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    name="workspace-ai-backend",
                    status="pass",
                    detail="No .unitra workspace detected; skipped workspace AI validation.",
                )
            )
        return DiagnosticReport(mode="check", workspace_root=root, checks=checks)

    @staticmethod
    def _python_check() -> DiagnosticCheck:
        version = ".".join(str(part) for part in sys.version_info[:3])
        status = "pass" if sys.version_info >= (3, 9) else "fail"
        return DiagnosticCheck(
            name="python",
            status=status,
            detail=f"Python {version} at {sys.executable}",
            command=f"{sys.executable} --version",
        )

    @staticmethod
    def _command_check(name: str, executable: str, module_name: str = "", required: bool = True) -> DiagnosticCheck:
        path = shutil.which(executable)
        if path:
            return DiagnosticCheck(
                name=name,
                status="pass",
                detail=f"{executable} available at {path}",
                command=f"{executable} --version",
            )
        if module_name:
            result = subprocess.run(
                [sys.executable, "-m", module_name, "--version"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                detail = result.stdout.strip() or result.stderr.strip() or f"{module_name} module is importable"
                return DiagnosticCheck(
                    name=name,
                    status="pass",
                    detail=detail,
                    command=f"{sys.executable} -m {module_name} --version",
                )
        return DiagnosticCheck(
            name=name,
            status="fail" if required else "warn",
            detail=f"{executable} is not installed.",
            command=f"pip install {module_name or executable}",
        )

    def _workspace_check(self, root_path: str):
        repository = self._workspace_repository_factory(root_path)
        config_path = Path(getattr(repository, "config_path", ""))
        if not config_path.exists():
            return (
                DiagnosticCheck(
                    name="workspace",
                    status="warn",
                    detail="No .unitra/unitra.toml found in this root.",
                    command="unitra workspace init --root .",
                ),
                None,
            )
        try:
            config = repository.load_config()
        except Exception as exc:  # pragma: no cover - exercised through CLI integration
            return (
                DiagnosticCheck(
                    name="workspace",
                    status="fail",
                    detail=f"Workspace config could not be loaded: {exc}",
                ),
                None,
            )
        return (
            DiagnosticCheck(
                name="workspace",
                status="pass",
                detail=f"Loaded {config_path}",
            ),
            config,
        )

    def _ollama_checks(self, workspace_config) -> List[DiagnosticCheck]:
        provider = getattr(getattr(workspace_config, "ai_backend", None), "provider", "ollama")
        model = getattr(getattr(workspace_config, "ai_backend", None), "model", os.getenv("OLLAMA_MODEL", "llama3.2"))
        base_url = getattr(
            getattr(workspace_config, "ai_backend", None),
            "base_url",
            os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1/"),
        )
        checks = [
            self._command_check("ollama", "ollama", required=(provider == "ollama")),
        ]
        ping_status = "warn" if provider != "ollama" else "fail"
        try:
            response = urllib_request.urlopen(self._models_url(base_url), timeout=2)
            body = response.read(256).decode("utf-8", errors="replace")
            detail = f"Ollama OpenAI endpoint responded at {base_url} for model {model}."
            if body:
                detail = f"{detail} Response preview: {body[:120]}"
            checks.append(
                DiagnosticCheck(
                    name="ollama-api",
                    status="pass",
                    detail=detail,
                    command=f"curl {self._models_url(base_url)}",
                )
            )
        except (urllib_error.URLError, ValueError) as exc:
            checks.append(
                DiagnosticCheck(
                    name="ollama-api",
                    status=ping_status,
                    detail=f"Ollama endpoint did not respond at {base_url}: {exc}",
                    command=f"ollama serve  # then retry {self._models_url(base_url)}",
                )
            )
        return checks

    @staticmethod
    def _models_url(base_url: str) -> str:
        return base_url.rstrip("/") + "/models"
