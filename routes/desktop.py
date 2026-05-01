"""Desktop-specific SPA endpoints for the pywebview GUI."""

from __future__ import annotations

from statistics import mean

from flask import Blueprint, jsonify, request

from src.application.ai_policy import AiPolicy
from src.application.exceptions import ValidationError
from src.application.models import SaveSettingsRequest
from src.application.workspace_models import JobDefinition, TestTarget
from src.container import get_container, reset_container
from src.infrastructure.desktop_task_manager import DesktopTaskManager
from src.serializers import serialize_agent_profile, serialize_job_result

from routes.workspace import (
    _container_for_root,
    _invalidate_workspace_cache,
    _serialize_ai_policy_state,
    _workspace_dashboard_payload,
    _workspace_policy_state,
    _workspace_runs_for_root,
)

desktop_bp = Blueprint("desktop", __name__)
_TASKS = DesktopTaskManager()


@desktop_bp.route("/api/desktop/state", methods=["GET"])
def desktop_state():
    root = request.args.get("root", "").strip()
    payload = {
        "root": root,
        "active_tasks": _TASKS.list_active(),
        "settings": _load_settings_payload(),
    }
    if not root:
        return jsonify(payload)
    try:
        container = _container_for_root(root)
        overview = _workspace_dashboard_payload(root)
        runs = _workspace_runs_for_root(root, limit=12)
        policy_state = _workspace_policy_state(container)
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    payload.update(
        {
            "overview": overview,
            "runs": runs,
            "metrics": _desktop_metrics(overview, runs),
            "agent_profile": serialize_agent_profile(
                container.workspace.active_agent_profile(),
                effective_ai_policy=policy_state["effective_ai_policy"],
                global_ai_policy=policy_state["global_ai_policy"],
                workspace_ai_policy=policy_state["workspace_ai_policy"],
                ai_policy_source=policy_state["ai_policy_source"],
            ),
            "ai_policy": _serialize_ai_policy_state(policy_state),
        }
    )
    return jsonify(payload)


@desktop_bp.route("/api/desktop/tasks", methods=["POST"])
def desktop_start_task():
    body = request.get_json()
    root = body.get("root", ".")
    kind = body.get("kind", "generate")
    task_id = _TASKS.start(kind=kind, label=_task_label(kind), worker=lambda progress: _run_desktop_task(body, progress))
    return jsonify({"task_id": task_id})


@desktop_bp.route("/api/desktop/tasks/<task_id>", methods=["GET"])
def desktop_task(task_id: str):
    payload = _TASKS.get(task_id)
    if payload is None:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(payload)


@desktop_bp.route("/api/desktop/settings", methods=["GET"])
def desktop_settings():
    return jsonify(_load_settings_payload())


@desktop_bp.route("/api/desktop/settings", methods=["POST"])
def desktop_settings_save():
    body = request.get_json()
    try:
        result = get_container().settings.save_settings(
            SaveSettingsRequest(
                provider=body.get("provider", ""),
                api_key=body.get("api_key", ""),
                model=body.get("model", ""),
                show_hints=body.get("show_hints"),
                ai_policy=AiPolicy.from_dict(body.get("ai_policy", {})) if "ai_policy" in body else None,
            )
        )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    reset_container()
    return jsonify(
        {
            "ok": result.saved,
            "provider": result.provider,
            "model": result.model,
            "api_key_set": result.api_key_set,
            "openai_api_key_set": result.openai_api_key_set,
            "openrouter_api_key_set": result.openrouter_api_key_set,
            "ollama_api_key_set": result.ollama_api_key_set,
            "show_hints": result.show_hints,
            "ai_policy": result.ai_policy.to_dict(),
        }
    )


def _task_label(kind: str) -> str:
    return {
        "generate": "Generate tests",
        "write": "Write tests",
        "run": "Run tests",
        "fix": "Fix failures",
        "job": "Run workspace job",
    }.get(kind, "Workspace task")


def _run_desktop_task(body: dict, progress_callback):
    root = body.get("root", ".")
    container = _container_for_root(root)
    task_type = body.get("kind", "generate")
    if task_type == "job":
        job_name = body.get("name", "run-tests")
        job = container.workspace.get_job(job_name)
        if body.get("use_ai_generation") or body.get("use_ai_repair"):
            job = JobDefinition(
                name=job.name,
                mode=job.mode,
                target_scope=job.target_scope,
                target_value=job.target_value,
                output_policy=job.output_policy,
                run_pytest_args=job.run_pytest_args,
                coverage=job.coverage,
                timeout=job.timeout,
                agent_profile=job.agent_profile,
                use_ai_generation=bool(body.get("use_ai_generation", False)),
                use_ai_repair=bool(body.get("use_ai_repair", False)),
            )
    else:
        target = TestTarget(
            scope=body.get("scope", "repo"),
            workspace_root=root,
            folder=body.get("folder", ""),
            paths=body.get("paths", []),
        )
        job = _job_for_kind(task_type, target, body)
    result = container.jobs.execute_with_progress(job, progress_callback=progress_callback)
    _invalidate_workspace_cache(root)
    return serialize_job_result(result, model=container.config.ai_model)


def _job_for_kind(kind: str, target: TestTarget, body: dict) -> JobDefinition:
    mode_map = {
        "generate": ("ad-hoc-generate", "generate-tests"),
        "write": ("ad-hoc-write", "generate-tests"),
        "run": ("ad-hoc-run-tests", "run-tests"),
        "fix": ("ad-hoc-fix", "fix-failed-tests"),
    }
    name, mode = mode_map.get(kind, ("ad-hoc-generate", "generate-tests"))
    return JobDefinition(
        name=name,
        mode=mode,
        target_scope=target.scope if mode != "run-tests" else "repo",
        target_value=_target_value(target) if mode != "run-tests" else "",
        output_policy="write" if kind in {"write", "fix"} else "preview",
        run_pytest_args=body.get("pytest_args", []),
        timeout=int(body.get("timeout", 30) or 30),
        use_ai_generation=bool(body.get("use_ai_generation", False)),
        use_ai_repair=bool(body.get("use_ai_repair", False)),
    )


def _target_value(target: TestTarget) -> str:
    if target.scope == "folder":
        return target.folder
    if target.scope == "files":
        return ",".join(target.paths)
    return ""


def _load_settings_payload() -> dict:
    settings = get_container().settings.load_settings()
    return {
        "provider": settings.provider,
        "model": settings.model,
        "api_key_set": settings.api_key_set,
        "openai_api_key_set": settings.openai_api_key_set,
        "openrouter_api_key_set": settings.openrouter_api_key_set,
        "ollama_api_key_set": settings.ollama_api_key_set,
        "show_hints": settings.show_hints,
        "ai_policy": settings.ai_policy.to_dict(),
    }


def _desktop_metrics(overview: dict, runs: list[dict]) -> dict:
    job_runs = [run for run in runs if run.get("kind") == "job_run"]
    generated_tests = sum(int(run.get("generated_tests_count", 0) or 0) for run in job_runs)
    durations = [float(run.get("total_duration_ms", 0.0) or 0.0) for run in job_runs if run.get("total_duration_ms")]
    coverage_values = []
    for run in job_runs:
        coverage = str(run.get("run", {}).get("coverage") or "")
        if coverage.endswith("%"):
            try:
                coverage_values.append(float(coverage[:-1]))
            except ValueError:
                continue
    latest = job_runs[0] if job_runs else {}
    return {
        "jobs_count": len(overview.get("jobs", [])),
        "generated_tests": generated_tests,
        "average_coverage": round(mean(coverage_values), 1) if coverage_values else None,
        "latest_coverage": latest.get("run", {}).get("coverage"),
        "avg_duration_ms": round(mean(durations), 2) if durations else 0.0,
        "latest_generators": latest.get("generator_breakdown", []),
        "cache_hits": sum(int(run.get("cache_hits", 0) or 0) for run in job_runs),
    }
