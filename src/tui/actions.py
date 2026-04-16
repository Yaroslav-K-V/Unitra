import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from src.application.models import RunTestsRequest
from src.application.workspace_models import TestTarget
from src.config import load_config
from src.container import build_container, get_container
from src.serializers import (
    serialize_agent_profile,
    serialize_job_definition,
    serialize_job_result,
    serialize_run_history_record,
    serialize_workspace_status,
)
from src.tui.state import ScreenActionResult, SessionState


def _default_workspace_container_loader(root: str):
    return build_container(load_config(root_path=os.path.abspath(root)))


@dataclass
class TuiActions:
    workspace_container_loader: Callable[[str], object] = _default_workspace_container_loader
    quick_container_loader: Callable[[], object] = get_container

    def select_workspace(self, session: SessionState, root: str) -> ScreenActionResult:
        root = os.path.abspath(root)
        container = self.workspace_container_loader(root)
        status = serialize_workspace_status(container.workspace.status())
        session.set_workspace(root, initialized=True, agent_profile=status["config"]["selected_agent_profile"])
        result = ScreenActionResult(
            action="workspace.status",
            ok=True,
            payload=status,
            message=f"Loaded workspace at {root}",
        )
        session.remember_result(result)
        return result

    def init_workspace(self, session: SessionState, root: str) -> ScreenActionResult:
        root = os.path.abspath(root)
        container = self.workspace_container_loader(root)
        config = container.workspace.init_workspace(root)
        session.set_workspace(root, initialized=True, agent_profile=config.selected_agent_profile)
        result = ScreenActionResult(
            action="workspace.init",
            ok=True,
            payload={"config": config.__dict__},
            message=f"Initialized workspace at {root}",
        )
        session.remember_result(result)
        return result

    def validate_workspace(self, session: SessionState) -> ScreenActionResult:
        missing = self._require_workspace(session, "workspace.validate")
        if missing:
            return missing
        container = self._workspace_container(session)
        status = serialize_workspace_status(container.workspace.validate())
        result = ScreenActionResult(
            action="workspace.validate",
            ok=True,
            payload={"valid": True, **status},
            message="Workspace metadata looks healthy.",
        )
        session.remember_result(result)
        return result

    def run_job(self, session: SessionState, name: str, target_value: str = "", output_policy: str = "") -> ScreenActionResult:
        missing = self._require_workspace(session, "job.run")
        if missing:
            return missing
        container = self._workspace_container(session)
        result = container.jobs.run_job(name, target_value=target_value, output_policy=output_policy)
        payload = serialize_job_result(result, model=container.config.ai_model)
        action_result = ScreenActionResult(
            action="job.run",
            ok=True,
            payload=payload,
            message=f"Ran job '{name}'",
        )
        session.remember_result(action_result)
        return action_result

    def preview_generate(self, session: SessionState) -> ScreenActionResult:
        return self._targeted_action(session, mode="generate", write=False)

    def write_generate(self, session: SessionState) -> ScreenActionResult:
        return self._targeted_action(session, mode="generate", write=True)

    def preview_update(self, session: SessionState) -> ScreenActionResult:
        return self._targeted_action(session, mode="update", write=False)

    def fix_failures(self, session: SessionState, write: bool = True) -> ScreenActionResult:
        return self._targeted_action(session, mode="fix-failures", write=write)

    def run_workspace_tests(
        self,
        session: SessionState,
        pytest_args: Optional[List[str]] = None,
        timeout: Optional[int] = None,
    ) -> ScreenActionResult:
        missing = self._require_workspace(session, "test.run")
        if missing:
            return missing
        container = self._workspace_container(session)
        result = container.jobs.run_tests(pytest_args=pytest_args, timeout=timeout)
        payload = serialize_job_result(result, model=container.config.ai_model)
        action_result = ScreenActionResult(
            action="test.run",
            ok=result.run_returncode in (None, 0),
            payload=payload,
            message="Ran workspace tests." if not result.run_returncode else "Workspace tests reported failures.",
        )
        session.remember_result(action_result)
        return action_result

    def list_runs(self, session: SessionState, limit: int = 20) -> ScreenActionResult:
        missing = self._require_workspace(session, "runs.list")
        if missing:
            return missing
        container = self._workspace_container(session)
        result = ScreenActionResult(
            action="runs.list",
            ok=True,
            payload={"runs": container.workspace.list_runs(limit=limit)},
            message="Loaded recent runs.",
        )
        session.remember_result(result)
        return result

    def show_run(self, session: SessionState, history_id: str) -> ScreenActionResult:
        missing = self._require_workspace(session, "runs.show")
        if missing:
            return missing
        container = self._workspace_container(session)
        record = container.workspace.get_run(history_id)
        payload = serialize_run_history_record(history_id, record, model=container.config.ai_model)
        result = ScreenActionResult(
            action="runs.show",
            ok=payload["run"]["returncode"] in (None, 0),
            payload=payload,
            message=f"Loaded run {history_id}",
        )
        session.remember_result(result)
        return result

    def list_agents(self, session: SessionState) -> ScreenActionResult:
        missing = self._require_workspace(session, "agent.list")
        if missing:
            return missing
        container = self._workspace_container(session)
        profiles = [serialize_agent_profile(item) for item in container.workspace.list_agent_profiles()]
        result = ScreenActionResult(
            action="agent.list",
            ok=True,
            payload={"profiles": profiles},
            message="Loaded agent profiles.",
        )
        session.remember_result(result)
        return result

    def show_agent(self, session: SessionState, name: str) -> ScreenActionResult:
        missing = self._require_workspace(session, "agent.show")
        if missing:
            return missing
        container = self._workspace_container(session)
        profile = serialize_agent_profile(container.workspace.get_agent_profile(name))
        session.selected_agent_profile = profile["name"]
        result = ScreenActionResult(
            action="agent.show",
            ok=True,
            payload=profile,
            message=f"Loaded agent profile '{name}'.",
        )
        session.remember_result(result)
        return result

    def list_jobs(self, session: SessionState) -> ScreenActionResult:
        missing = self._require_workspace(session, "job.list")
        if missing:
            return missing
        container = self._workspace_container(session)
        jobs = [serialize_job_definition(item) for item in container.workspace.list_jobs()]
        result = ScreenActionResult(
            action="job.list",
            ok=True,
            payload={"jobs": jobs},
            message="Loaded saved jobs.",
        )
        session.remember_result(result)
        return result

    def show_job(self, session: SessionState, name: str) -> ScreenActionResult:
        missing = self._require_workspace(session, "job.show")
        if missing:
            return missing
        container = self._workspace_container(session)
        job = serialize_job_definition(container.workspace.get_job(name))
        result = ScreenActionResult(
            action="job.show",
            ok=True,
            payload=job,
            message=f"Loaded job '{name}'.",
        )
        session.remember_result(result)
        return result

    def quick_generate(self, session: SessionState, code: str) -> ScreenActionResult:
        container = self.quick_container_loader()
        result = container.generation.generate_from_code(code)
        payload = {
            "test_code": getattr(result, "test_code", ""),
            "imports": getattr(result, "imports", []),
            "coverage": getattr(result, "coverage", None),
            "functions_found": getattr(result, "functions_found", 0),
        }
        action_result = ScreenActionResult(
            action="quick.generate",
            ok=True,
            payload=payload,
            message="Generated quick test scaffold.",
        )
        session.remember_result(action_result)
        return action_result

    def quick_run(
        self,
        session: SessionState,
        test_code: str,
        source_code: str = "",
        source_folder: str = "",
    ) -> ScreenActionResult:
        container = self.quick_container_loader()
        result = container.test_runner.run_tests(
            RunTestsRequest(test_code=test_code, source_code=source_code, source_folder=source_folder)
        )
        payload = {
            "run": {
                "output": result.output,
                "returncode": result.returncode,
                "coverage": result.coverage,
            }
        }
        action_result = ScreenActionResult(
            action="quick.run",
            ok=result.returncode == 0,
            payload=payload,
            message="Executed quick tests." if result.returncode == 0 else "Quick tests reported failures.",
        )
        session.remember_result(action_result)
        return action_result

    def save_text_output(self, path: str, content: str) -> ScreenActionResult:
        absolute = os.path.abspath(path)
        with open(absolute, "w", encoding="utf-8") as handle:
            handle.write(content)
            if content and not content.endswith("\n"):
                handle.write("\n")
        return ScreenActionResult(
            action="output.save",
            ok=True,
            payload={"path": absolute},
            message=f"Saved output to {absolute}",
        )

    def _targeted_action(self, session: SessionState, mode: str, write: bool) -> ScreenActionResult:
        missing = self._require_workspace(session, f"test.{mode}")
        if missing:
            return missing
        container = self._workspace_container(session)
        target = session.selected_target.to_test_target(session.active_workspace_root)
        if mode == "generate":
            result = container.jobs.generate_tests(target, write=write)
        elif mode == "update":
            result = container.jobs.update_tests(target, write=write)
        else:
            result = container.jobs.fix_failed_tests(target, write=write)
        payload = serialize_job_result(result, model=container.config.ai_model)
        action_result = ScreenActionResult(
            action=f"test.{mode}",
            ok=result.run_returncode in (None, 0),
            payload=payload,
            message=("Wrote managed files." if write else "Prepared preview.") if mode != "fix-failures" else "Processed failure-fix flow.",
        )
        session.remember_result(action_result)
        return action_result

    @staticmethod
    def _require_workspace(session: SessionState, action: str) -> Optional[ScreenActionResult]:
        if session.active_workspace_root:
            return None
        result = ScreenActionResult(
            action=action,
            ok=False,
            error="No active workspace selected. Open or initialize a workspace first.",
        )
        session.remember_result(result)
        return result

    def _workspace_container(self, session: SessionState):
        if not session.active_workspace_root:
            raise ValueError("No active workspace selected")
        return self.workspace_container_loader(session.active_workspace_root)
