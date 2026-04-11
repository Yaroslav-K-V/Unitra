from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.application.workspace_models import TestTarget


@dataclass
class WorkspaceSelection:
    root: str = ""
    initialized: bool = False


@dataclass
class CurrentTarget:
    scope: str = "repo"
    folder: str = ""
    paths: List[str] = field(default_factory=list)

    def to_test_target(self, workspace_root: str) -> TestTarget:
        return TestTarget(
            scope=self.scope,
            workspace_root=workspace_root,
            folder=self.folder,
            paths=list(self.paths),
        )

    def describe(self) -> str:
        if self.scope == "folder" and self.folder:
            return f"folder:{self.folder}"
        if self.scope == "files" and self.paths:
            return f"files:{len(self.paths)}"
        return self.scope


@dataclass
class AssistantHint:
    title: str
    body: str


@dataclass
class ScreenActionResult:
    action: str
    ok: bool
    payload: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    error: str = ""


@dataclass
class ReviewSelectionState:
    selected_test_path: str = ""
    show_fallback_details: bool = False


@dataclass
class SessionState:
    workspace: WorkspaceSelection = field(default_factory=WorkspaceSelection)
    selected_target: CurrentTarget = field(default_factory=CurrentTarget)
    selected_agent_profile: str = ""
    last_job_result: Dict[str, Any] = field(default_factory=dict)
    last_run_summary: Dict[str, Any] = field(default_factory=dict)
    assistant_notes: List[str] = field(default_factory=list)
    current_screen: str = "home"
    review: ReviewSelectionState = field(default_factory=ReviewSelectionState)

    @property
    def active_workspace_root(self) -> str:
        return self.workspace.root

    def set_workspace(self, root: str, initialized: bool = True, agent_profile: str = "") -> None:
        self.workspace = WorkspaceSelection(root=root, initialized=initialized)
        if agent_profile:
            self.selected_agent_profile = agent_profile

    def set_target(self, scope: str, folder: str = "", paths: Optional[List[str]] = None) -> None:
        self.selected_target = CurrentTarget(scope=scope, folder=folder, paths=list(paths or []))

    def remember_result(self, result: ScreenActionResult) -> None:
        if result.payload.get("history_id") or result.payload.get("run"):
            self.last_job_result = result.payload
            run = result.payload.get("run") or {}
            if run:
                self.last_run_summary = run
        note = result.message or result.error or result.action
        if note:
            self.assistant_notes.append(note)
            self.assistant_notes = self.assistant_notes[-5:]

    def hints(self) -> List[AssistantHint]:
        hints: List[AssistantHint] = []
        if not self.active_workspace_root:
            hints.append(
                AssistantHint(
                    title="Open a workspace",
                    body="Point Unitra at a repository to preview managed tests, run jobs, and inspect history.",
                )
            )
        else:
            hints.append(
                AssistantHint(
                    title="Current target",
                    body=f"Working against {self.selected_target.describe()} in {self.active_workspace_root}.",
                )
            )
        if self.last_run_summary.get("returncode"):
            hints.append(
                AssistantHint(
                    title="Tests failed",
                    body="Try Fix failures next, then rerun tests to confirm the managed patch helped.",
                )
            )
        elif self.last_job_result:
            hints.append(
                AssistantHint(
                    title="Next recommended step",
                    body="Review planned changes first, then write managed files or run tests.",
                )
            )
        else:
            hints.append(
                AssistantHint(
                    title="Suggested path",
                    body="Open repo -> Preview changes -> Run tests -> Fix failures if needed.",
                )
            )
        if self.selected_agent_profile:
            hints.append(
                AssistantHint(
                    title="Active profile",
                    body=f"Using agent profile '{self.selected_agent_profile}' for fallback-aware flows.",
                )
            )
        return hints
