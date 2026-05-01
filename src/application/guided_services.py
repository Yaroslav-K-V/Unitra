from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional

from src.application.exceptions import ValidationError
from src.application.workspace_models import GuidedRun, GuidedStep, TestTarget, TimelineEvent


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _step_from_dict(payload: dict) -> GuidedStep:
    return GuidedStep(
        id=payload.get("id", ""),
        kind=payload.get("kind", ""),
        title=payload.get("title", ""),
        status=payload.get("status", "pending"),
        requires_approval=bool(payload.get("requires_approval", False)),
        skippable=bool(payload.get("skippable", False)),
        job_mode=payload.get("job_mode", ""),
        write=bool(payload.get("write", False)),
        use_ai_generation=bool(payload.get("use_ai_generation", False)),
        use_ai_repair=bool(payload.get("use_ai_repair", False)),
        job_name=payload.get("job_name", ""),
        child_run_id=payload.get("child_run_id", ""),
        summary=payload.get("summary", ""),
    )


def _event_from_dict(payload: dict) -> TimelineEvent:
    return TimelineEvent(
        id=payload.get("id", ""),
        at=payload.get("at", ""),
        stage=payload.get("stage", ""),
        step_id=payload.get("step_id", ""),
        status=payload.get("status", ""),
        label=payload.get("label", ""),
        detail=payload.get("detail", ""),
        child_run_id=payload.get("child_run_id", ""),
    )


def guided_run_from_dict(payload: dict) -> GuidedRun:
    return GuidedRun(
        history_id=payload.get("history_id", ""),
        kind=payload.get("kind", "guided_run"),
        workflow_source=payload.get("workflow_source", "core"),
        workflow_name=payload.get("workflow_name", "core"),
        status=payload.get("status", "planning"),
        target_scope=payload.get("target_scope", "repo"),
        target_value=payload.get("target_value", ""),
        current_step_id=payload.get("current_step_id", ""),
        awaiting_step_id=payload.get("awaiting_step_id", ""),
        child_run_ids=list(payload.get("child_run_ids", [])),
        steps=[_step_from_dict(item) for item in payload.get("steps", [])],
        timeline=[_event_from_dict(item) for item in payload.get("timeline", [])],
        latest_child_run_id=payload.get("latest_child_run_id", ""),
    )


class GuidedAgentService:
    def __init__(self, workspace_service, jobs_service, run_history_repository):
        self._workspace = workspace_service
        self._jobs = jobs_service
        self._runs = run_history_repository

    def create_core_run(self, target: TestTarget) -> GuidedRun:
        guided = GuidedRun(
            history_id="",
            workflow_source="core",
            workflow_name="core_repo_flow",
            status="planning",
            target_scope=target.scope,
            target_value=self._target_value(target),
            steps=[
                GuidedStep(
                    id="preview_changes",
                    kind="preview_changes",
                    title="Preview managed changes",
                    status="pending",
                    requires_approval=False,
                    skippable=False,
                    job_mode="generate",
                    write=False,
                    summary="Collect a safe preview before any managed write.",
                ),
                GuidedStep(
                    id="write_tests",
                    kind="write_tests",
                    title="Write managed tests",
                    status="pending",
                    requires_approval=True,
                    skippable=False,
                    job_mode="generate",
                    write=True,
                    summary="Apply the reviewed managed test changes to the workspace.",
                ),
                GuidedStep(
                    id="run_tests",
                    kind="run_tests",
                    title="Run workspace tests",
                    status="pending",
                    requires_approval=True,
                    skippable=False,
                    job_mode="run-tests",
                    summary="Validate the current workspace after the managed write.",
                ),
                GuidedStep(
                    id="repair_failures",
                    kind="repair_failures",
                    title="Repair failing tests",
                    status="blocked",
                    requires_approval=True,
                    skippable=True,
                    job_mode="fix-failures",
                    write=True,
                    summary="Available only after a failing test run.",
                ),
            ],
        )
        guided = self._append_event(guided, "plan", "", "created", "Guided plan created", "Built the core repo workflow.")
        history_id = self._runs.create_guided(guided)
        guided = replace(guided, history_id=history_id)
        self._runs.save_guided(guided)
        return self._auto_progress(guided, target=target)

    def create_job_run(self, name: str) -> GuidedRun:
        job = self._workspace.get_job(name)
        steps = self._steps_for_job(job)
        guided = GuidedRun(
            history_id="",
            workflow_source="job",
            workflow_name=name,
            status="planning",
            target_scope=getattr(job, "target_scope", "repo"),
            target_value=getattr(job, "target_value", "") or "",
            steps=steps,
        )
        guided = self._append_event(guided, "plan", "", "created", "Guided plan created", f"Built a guided plan from saved job '{name}'.")
        history_id = self._runs.create_guided(guided)
        guided = replace(guided, history_id=history_id)
        self._runs.save_guided(guided)
        return self._auto_progress(guided, target=self._target_for_guided(guided))

    def get_run(self, history_id: str) -> GuidedRun:
        payload = self._runs.load(history_id)
        if payload.get("kind") != "guided_run":
            raise ValidationError(f"Guided run `{history_id}` not found")
        return guided_run_from_dict(payload)

    def list_runs(self, limit: int = 20) -> List[str]:
        return list(self._workspace.list_runs(limit=limit))

    def approve_step(
        self,
        history_id: str,
        step_id: str,
        use_ai_generation: bool = False,
        use_ai_repair: bool = False,
    ) -> GuidedRun:
        guided = self.get_run(history_id)
        step = self._step(guided, step_id)
        if step.status not in {"pending", "awaiting_approval"}:
            raise ValidationError(f"Step `{step_id}` is not awaiting approval")
        if not step.requires_approval:
            raise ValidationError(f"Step `{step_id}` does not require approval")
        updated = replace(
            step,
            status="pending",
            use_ai_generation=use_ai_generation,
            use_ai_repair=use_ai_repair,
            summary="Approved and queued for execution.",
        )
        guided = self._replace_step(guided, updated)
        guided = replace(guided, awaiting_step_id="")
        guided = self._append_event(
            guided,
            "approval",
            step.id,
            "approved",
            f"Approved: {step.title}",
            self._approval_detail(updated),
        )
        self._runs.save_guided(guided)
        guided = self._run_step(guided, updated, target=self._target_for_guided(guided))
        self._runs.save_guided(guided)
        return self._auto_progress(guided, target=self._target_for_guided(guided))

    def skip_step(self, history_id: str, step_id: str) -> GuidedRun:
        guided = self.get_run(history_id)
        step = self._step(guided, step_id)
        if not step.skippable:
            raise ValidationError(f"Step `{step_id}` cannot be skipped")
        updated = replace(step, status="skipped", summary="Skipped by user.")
        guided = self._replace_step(guided, updated)
        if guided.awaiting_step_id == step_id:
            guided = replace(guided, awaiting_step_id="")
        guided = self._append_event(guided, "approval", step.id, "skipped", f"Skipped: {step.title}", "User skipped this step.")
        self._runs.save_guided(guided)
        return self._auto_progress(guided, target=self._target_for_guided(guided))

    def reject_step(self, history_id: str, step_id: str) -> GuidedRun:
        guided = self.get_run(history_id)
        step = self._step(guided, step_id)
        updated = replace(step, status="rejected", summary="Rejected by user.")
        guided = self._replace_step(guided, updated)
        guided = replace(guided, status="cancelled", awaiting_step_id="", current_step_id=step_id)
        guided = self._append_event(guided, "approval", step.id, "rejected", f"Rejected: {step.title}", "Guided run was cancelled.")
        self._runs.save_guided(guided)
        return guided

    def _auto_progress(self, guided: GuidedRun, target: TestTarget) -> GuidedRun:
        current = guided
        while True:
            runnable = self._next_runnable_step(current)
            if runnable is None:
                finalized = self._refresh_status(current)
                self._runs.save_guided(finalized)
                return finalized
            if runnable.requires_approval:
                awaiting = replace(runnable, status="awaiting_approval")
                current = self._replace_step(current, awaiting)
                current = replace(current, status="awaiting_approval", awaiting_step_id=awaiting.id, current_step_id=awaiting.id)
                current = self._append_event(
                    current,
                    "approval",
                    awaiting.id,
                    "awaiting_approval",
                    f"Awaiting approval: {awaiting.title}",
                    awaiting.summary or "User approval is required before this step can run.",
                )
                self._runs.save_guided(current)
                return current
            current = self._run_step(current, runnable, target)
            self._runs.save_guided(current)

    def _run_step(self, guided: GuidedRun, step: GuidedStep, target: TestTarget) -> GuidedRun:
        running = replace(step, status="running")
        current = self._replace_step(guided, running)
        current = replace(current, status="running", current_step_id=step.id, awaiting_step_id="")
        current = self._append_event(current, "step", step.id, "running", f"Running: {step.title}", step.summary or "")

        child = self._execute_step(step, target)
        summary = self._child_summary(step, child)
        completed_status = "failed" if getattr(child, "run_returncode", None) not in (None, 0) else "completed"
        updated = replace(
            running,
            status=completed_status,
            child_run_id=getattr(child, "history_id", ""),
            summary=summary,
        )
        current = self._replace_step(current, updated)
        child_run_id = getattr(child, "history_id", "")
        child_run_ids = list(dict.fromkeys([*current.child_run_ids, child_run_id])) if child_run_id else list(current.child_run_ids)
        current = replace(
            current,
            child_run_ids=child_run_ids,
            latest_child_run_id=child_run_id or current.latest_child_run_id,
        )
        current = self._append_event(
            current,
            "step",
            step.id,
            updated.status,
            f"{step.title}: {updated.status}",
            summary,
            child_run_id=child_run_id,
        )

        if step.kind == "run_tests":
            repair = self._find_step(current, "repair_failures")
            if repair is not None:
                if getattr(child, "run_returncode", None):
                    repair = replace(repair, status="pending", summary="Tests failed. Review and approve repair when ready.")
                else:
                    repair = replace(repair, status="skipped", summary="Repair was not needed because tests passed.")
                current = self._replace_step(current, repair)

        return self._refresh_status(current)

    def _execute_step(self, step: GuidedStep, target: TestTarget):
        if step.job_name:
            return self._jobs.run_job(
                step.job_name,
                target_value=self._target_value(target),
                output_policy="write" if step.write else "preview",
                use_ai_generation=step.use_ai_generation,
                use_ai_repair=step.use_ai_repair,
            )
        if step.kind in {"preview_changes", "write_tests"}:
            if step.job_mode == "update":
                return self._jobs.update_tests(
                    target,
                    write=step.write,
                    use_ai_generation=step.use_ai_generation,
                )
            return self._jobs.generate_tests(
                target,
                write=step.write,
                use_ai_generation=step.use_ai_generation,
            )
        if step.kind == "run_tests":
            return self._jobs.run_tests()
        if step.kind == "repair_failures":
            return self._jobs.fix_failed_tests(
                target,
                write=True,
                use_ai_generation=step.use_ai_generation,
                use_ai_repair=step.use_ai_repair,
            )
        raise ValidationError(f"Unsupported guided step `{step.kind}`")

    def _steps_for_job(self, job) -> List[GuidedStep]:
        name = getattr(job, "name", "")
        mode = getattr(job, "mode", "")
        output_policy = getattr(job, "output_policy", "preview")
        write_default = output_policy in {"write", "write-run"}
        steps: List[GuidedStep] = []

        if mode in {"generate-tests", "update-tests"}:
            is_write = write_default
            steps.append(
                GuidedStep(
                    id="write_tests" if is_write else "preview_changes",
                    kind="write_tests" if is_write else "preview_changes",
                    title="Write managed tests" if is_write else "Preview managed changes",
                    status="pending",
                    requires_approval=is_write,
                    skippable=False,
                    job_mode="generate" if mode == "generate-tests" else "update",
                    write=is_write,
                    job_name=name if is_write else "",
                    summary="Saved job policy requests a managed write." if is_write else "Saved job policy starts with a safe preview.",
                )
            )
            steps.append(
                GuidedStep(
                    id="run_tests",
                    kind="run_tests",
                    title="Run workspace tests",
                    status="pending",
                    requires_approval=True,
                    skippable=False,
                    job_mode="run-tests",
                    summary="Validate the workspace after the saved job action.",
                )
            )
            steps.append(self._repair_step())
            return steps

        if mode == "run-tests":
            steps.append(
                GuidedStep(
                    id="run_tests",
                    kind="run_tests",
                    title="Run workspace tests",
                    status="pending",
                    requires_approval=True,
                    skippable=False,
                    job_mode="run-tests",
                    job_name=name,
                    summary="Run the saved workspace test job.",
                )
            )
            steps.append(self._repair_step())
            return steps

        if mode == "generate-and-run":
            steps.append(
                GuidedStep(
                    id="write_tests",
                    kind="write_tests",
                    title="Write managed tests",
                    status="pending",
                    requires_approval=True,
                    skippable=False,
                    job_mode="generate",
                    write=True,
                    job_name=name,
                    summary="Apply the saved job's managed write before validation.",
                )
            )
            steps.append(
                GuidedStep(
                    id="run_tests",
                    kind="run_tests",
                    title="Run workspace tests",
                    status="pending",
                    requires_approval=True,
                    skippable=False,
                    job_mode="run-tests",
                    summary="Validate the workspace after the managed write.",
                )
            )
            steps.append(self._repair_step())
            return steps

        if mode == "fix-failed-tests":
            steps.append(
                GuidedStep(
                    id="repair_failures",
                    kind="repair_failures",
                    title="Repair failing tests",
                    status="pending",
                    requires_approval=True,
                    skippable=True,
                    job_mode="fix-failures",
                    write=True,
                    use_ai_repair=getattr(job, "use_ai_repair", False),
                    job_name=name,
                    summary="Run the saved repair workflow.",
                )
            )
            return steps

        steps.append(
            GuidedStep(
                id="run_saved_job",
                kind="run_saved_job",
                title=f"Run saved job: {name}",
                status="pending",
                requires_approval=True,
                skippable=False,
                job_mode=mode,
                job_name=name,
                write=write_default,
                use_ai_generation=getattr(job, "use_ai_generation", False),
                use_ai_repair=getattr(job, "use_ai_repair", False),
                summary="This saved job is not decomposed in v1, so it runs as a single guided step.",
            )
        )
        return steps

    @staticmethod
    def _repair_step() -> GuidedStep:
        return GuidedStep(
            id="repair_failures",
            kind="repair_failures",
            title="Repair failing tests",
            status="blocked",
            requires_approval=True,
            skippable=True,
            job_mode="fix-failures",
            write=True,
            summary="Available only after a failing test run.",
        )

    @staticmethod
    def _target_value(target: TestTarget) -> str:
        if target.scope == "folder":
            return target.folder
        if target.scope == "files":
            return ",".join(target.paths)
        return ""

    def _target_for_guided(self, guided: GuidedRun) -> TestTarget:
        if guided.target_scope == "folder":
            return TestTarget(scope="folder", workspace_root=self._workspace.status().config.root_path, folder=guided.target_value)
        if guided.target_scope == "files":
            paths = [item for item in guided.target_value.split(",") if item]
            return TestTarget(scope="files", workspace_root=self._workspace.status().config.root_path, paths=paths)
        return TestTarget(scope=guided.target_scope or "repo", workspace_root=self._workspace.status().config.root_path)

    @staticmethod
    def _approval_detail(step: GuidedStep) -> str:
        details = []
        if step.use_ai_generation:
            details.append("AI generation enabled")
        if step.use_ai_repair:
            details.append("AI repair enabled")
        return ", ".join(details) if details else "Run locally with current workspace policy."

    @staticmethod
    def _child_summary(step: GuidedStep, child) -> str:
        planned = len(getattr(child, "planned_files", []) or [])
        written = sum(1 for item in getattr(child, "written_files", []) or [] if getattr(item, "written", False))
        run_returncode = getattr(child, "run_returncode", None)
        coverage = getattr(child, "run_coverage", None)
        parts = []
        if planned:
            parts.append(f"{planned} planned")
        if written:
            parts.append(f"{written} written")
        if run_returncode is None and step.kind == "preview_changes":
            parts.append("preview only")
        elif run_returncode is None:
            parts.append("no pytest run")
        elif run_returncode == 0:
            parts.append("tests passed")
        else:
            parts.append(f"tests failed ({run_returncode})")
        if coverage:
            parts.append(f"coverage {coverage}")
        return ", ".join(parts) if parts else "Step completed."

    @staticmethod
    def _replace_step(guided: GuidedRun, new_step: GuidedStep) -> GuidedRun:
        return replace(
            guided,
            steps=[new_step if item.id == new_step.id else item for item in guided.steps],
        )

    @staticmethod
    def _step(guided: GuidedRun, step_id: str) -> GuidedStep:
        step = GuidedAgentService._find_step(guided, step_id)
        if step is None:
            raise ValidationError(f"Step `{step_id}` not found")
        return step

    @staticmethod
    def _find_step(guided: GuidedRun, step_id: str) -> Optional[GuidedStep]:
        for step in guided.steps:
            if step.id == step_id:
                return step
        return None

    @staticmethod
    def _next_runnable_step(guided: GuidedRun) -> Optional[GuidedStep]:
        for step in guided.steps:
            if step.status == "pending":
                return step
        return None

    @staticmethod
    def _append_event(
        guided: GuidedRun,
        stage: str,
        step_id: str,
        status: str,
        label: str,
        detail: str = "",
        child_run_id: str = "",
    ) -> GuidedRun:
        event = TimelineEvent(
            id=f"evt-{len(guided.timeline) + 1}",
            at=_utc_now(),
            stage=stage,
            step_id=step_id,
            status=status,
            label=label,
            detail=detail,
            child_run_id=child_run_id,
        )
        return replace(guided, timeline=[*guided.timeline, event])

    @staticmethod
    def _refresh_status(guided: GuidedRun) -> GuidedRun:
        statuses = {step.status for step in guided.steps}
        if guided.status == "cancelled":
            return guided
        if "awaiting_approval" in statuses:
            return replace(guided, status="awaiting_approval")
        if "running" in statuses:
            return replace(guided, status="running")
        if any(step.status == "failed" for step in guided.steps if step.kind != "repair_failures"):
            return replace(guided, status="failed")
        unfinished = [step for step in guided.steps if step.status in {"pending", "blocked"}]
        if unfinished:
            return replace(guided, status="running")
        return replace(guided, status="completed", awaiting_step_id="", current_step_id=guided.current_step_id or "")
