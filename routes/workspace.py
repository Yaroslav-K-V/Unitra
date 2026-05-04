import os
import threading

from flask import Blueprint, jsonify, request

from src.application.exceptions import DependencyError, ValidationError
from src.application.ai_policy import AiPolicy
from src.application.workspace_models import TestTarget
from src.config import APP_ROOT, load_config
from src.container import build_container
from src.serializers import (
    serialize_ai_policy,
    serialize_agent_profile,
    serialize_job_result,
    serialize_run_history_record,
    serialize_workspace_status,
    to_dict,
)

workspace_bp = Blueprint("workspace", __name__)

_CACHE_LOCK = threading.Lock()
_CONTAINER_CACHE = {}
_PAYLOAD_CACHE = {}


def _normalize_root(root_path: str) -> str:
    return os.path.abspath(root_path or ".")


def _workspace_signature(root_path: str) -> tuple:
    unitra_dir = os.path.join(root_path, ".unitra")
    config_path = os.path.join(unitra_dir, "unitra.toml")
    jobs_dir = os.path.join(unitra_dir, "jobs")
    agents_dir = os.path.join(unitra_dir, "agents")
    runs_dir = os.path.join(unitra_dir, "runs")
    settings_path = os.getenv("UNITRA_SETTINGS_PATH") or os.path.join(APP_ROOT, "data", "settings.json")
    paths = (config_path, jobs_dir, agents_dir, runs_dir, settings_path)
    signature = []
    for path in paths:
        try:
            signature.append(os.path.getmtime(path))
        except OSError:
            signature.append(None)
    return tuple(signature)


def _invalidate_workspace_cache(root_path: str) -> None:
    root = _normalize_root(root_path)
    with _CACHE_LOCK:
        _PAYLOAD_CACHE.pop(root, None)
        _CONTAINER_CACHE.pop(root, None)


def _container_for_root(root_path: str):
    root = _normalize_root(root_path)
    signature = _workspace_signature(root)
    with _CACHE_LOCK:
        cached = _CONTAINER_CACHE.get(root)
        if cached is not None:
            cached_signature, cached_container = cached
            if cached_signature == signature:
                return cached_container
        container = build_container(load_config(root_path=root))
        _CONTAINER_CACHE[root] = (signature, container)
        return container


def _cached_payload(root_path: str, key: str, factory):
    root = _normalize_root(root_path)
    signature = _workspace_signature(root)
    with _CACHE_LOCK:
        root_cache = _PAYLOAD_CACHE.get(root)
        if root_cache:
            cached_signature, payloads = root_cache
            if cached_signature == signature and key in payloads:
                return payloads[key]
    payload = factory()
    with _CACHE_LOCK:
        cached_signature, payloads = _PAYLOAD_CACHE.get(root, (signature, {}))
        if cached_signature != signature:
            payloads = {}
        payloads[key] = payload
        _PAYLOAD_CACHE[root] = (signature, payloads)
    return payload


def _job_payload(result):
    payload = serialize_job_result(result)
    payload["run_output"] = payload["run"]["output"]
    payload["run_returncode"] = payload["run"]["returncode"]
    payload["run_coverage"] = payload["run"]["coverage"]
    return payload


def _workspace_run_ids(container, limit: int):
    workspace = container.workspace
    if hasattr(workspace, "list_runs"):
        return list(workspace.list_runs(limit=limit))
    if hasattr(workspace, "status"):
        status = workspace.status()
        return list((getattr(status, "recent_runs", []) or [])[:limit])
    return []


def _workspace_run_payload(container, history_id: str):
    workspace = container.workspace
    if hasattr(workspace, "get_run"):
        payload = workspace.get_run(history_id)
    else:
        payload = {
            "job_name": "run-tests",
            "mode": "run-tests",
            "target_scope": "repo",
            "planned_files": [],
            "written_files": [],
            "run_output": "",
            "run_returncode": None,
            "run_coverage": None,
            "llm_fallback_contexts": [],
        }
    model = getattr(container.config, "ai_model", "")
    return serialize_run_history_record(
        history_id,
        payload,
        model=model,
        run_loader=(lambda child_id: workspace.get_run(child_id)) if hasattr(workspace, "get_run") else None,
    )


def _workspace_policy_state(container):
    global_policy = getattr(container.config, "ai_policy", AiPolicy())
    if hasattr(container.workspace, "ai_policy_state"):
        return container.workspace.ai_policy_state(global_policy)
    return {
        "effective_ai_policy": global_policy,
        "global_ai_policy": global_policy,
        "workspace_ai_policy": {"inherit": True, **global_policy.to_dict()},
        "ai_policy_source": "global",
    }


def _workspace_dashboard_payload(root: str):
    container = _container_for_root(root)
    status = serialize_workspace_status(container.workspace.status())
    runs = _workspace_runs_for_root(root, limit=8)
    jobs = [to_dict(job) for job in container.workspace.list_jobs()] if hasattr(container.workspace, "list_jobs") else list(status.get("jobs", []))
    try:
        doctor_report = container.doctor.doctor(root)
        doctor_checks = [
            {"name": item.name, "status": item.status, "detail": item.detail}
            for item in doctor_report.checks
            if item.name.startswith("ollama") or item.name in {"workspace", "python"}
        ]
    except Exception:
        doctor_checks = []
    return {
        "status": status,
        "jobs": jobs,
        "runs": runs,
        "backend": {
            "provider": status.get("config", {}).get("ai_backend", {}).get("provider", getattr(container.config, "ai_provider", "ollama")),
            "model": status.get("config", {}).get("ai_backend", {}).get("model", getattr(container.config, "ai_model", "")),
            "base_url": status.get("config", {}).get("ai_backend", {}).get("base_url", ""),
            "checks": doctor_checks,
        },
    }


def _target_from_body(body: dict, root_path: str) -> TestTarget:
    return TestTarget(
        scope=body.get("scope", "repo"),
        workspace_root=root_path,
        folder=body.get("folder", ""),
        paths=body.get("paths", []),
    )


@workspace_bp.route("/workspace/init", methods=["POST"])
def workspace_init():
    root = request.get_json().get("root", ".")
    try:
        config = _container_for_root(root).workspace.init_workspace(root)
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    _invalidate_workspace_cache(root)
    return jsonify(to_dict(config))


@workspace_bp.route("/workspace/status", methods=["GET"])
def workspace_status():
    root = request.args.get("root", ".")
    try:
        payload = _cached_payload(
            root,
            "status",
            lambda: serialize_workspace_status(_container_for_root(root).workspace.status()),
        )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(payload)


@workspace_bp.route("/workspace/dashboard", methods=["GET"])
def workspace_dashboard():
    root = request.args.get("root", ".")
    try:
        payload = _cached_payload(
            root,
            "dashboard",
            lambda: _workspace_dashboard_payload(root),
        )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(payload)


@workspace_bp.route("/workspace/jobs", methods=["GET"])
def workspace_jobs():
    root = request.args.get("root", ".")
    try:
        payload = _cached_payload(root, "jobs", lambda: _container_for_root(root).jobs.list_jobs())
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(payload)


@workspace_bp.route("/workspace/runs", methods=["GET"])
def workspace_runs():
    root = request.args.get("root", ".")
    limit = request.args.get("limit", default=5, type=int)
    try:
        payload = _cached_payload(
            root,
            f"runs:{limit}",
            lambda: _workspace_runs_for_root(root, limit),
        )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(payload)


def _workspace_runs_for_root(root: str, limit: int):
    container = _container_for_root(root)
    return [
        _workspace_run_payload(container, history_id)
        for history_id in _workspace_run_ids(container, limit)
    ]


@workspace_bp.route("/workspace/agent-profile", methods=["GET"])
def workspace_agent_profile():
    root = request.args.get("root", ".")
    try:
        container = _container_for_root(root)
        policy_state = _workspace_policy_state(container)
        payload = _cached_payload(
            root,
            "agent-profile",
            lambda: serialize_agent_profile(
                container.workspace.active_agent_profile(),
                effective_ai_policy=policy_state["effective_ai_policy"],
                global_ai_policy=policy_state["global_ai_policy"],
                workspace_ai_policy=policy_state["workspace_ai_policy"],
                ai_policy_source=policy_state["ai_policy_source"],
            ),
        )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(payload)


@workspace_bp.route("/workspace/ai-policy", methods=["GET"])
def workspace_ai_policy():
    root = request.args.get("root", ".")
    try:
        container = _container_for_root(root)
        payload = _serialize_ai_policy_state(_workspace_policy_state(container))
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(payload)


@workspace_bp.route("/workspace/ai-backend", methods=["POST"])
def workspace_ai_backend_save():
    body = request.get_json()
    root = body.get("root", ".")
    try:
        container = _container_for_root(root)
        payload = container.workspace.save_ai_backend(
            provider=body.get("provider", "ollama"),
            model=body.get("model", ""),
            base_url=body.get("base_url", ""),
        )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    _invalidate_workspace_cache(root)
    return jsonify(payload)


@workspace_bp.route("/workspace/ai-policy", methods=["POST"])
def workspace_ai_policy_save():
    body = request.get_json()
    root = body.get("root", ".")
    try:
        container = _container_for_root(root)
        payload = _serialize_ai_policy_state(
            container.workspace.save_ai_policy(
                getattr(container.config, "ai_policy", AiPolicy()),
                inherit=bool(body.get("inherit", True)),
                policy_values=body.get("ai_policy", {}),
            )
        )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    _invalidate_workspace_cache(root)
    return jsonify(payload)


@workspace_bp.route("/workspace/job/run", methods=["POST"])
def workspace_job_run():
    body = request.get_json()
    root = body.get("root", ".")
    try:
        jobs = _container_for_root(root).jobs
        try:
            result = jobs.run_job(
                body.get("name", ""),
                target_value=body.get("target", ""),
                output_policy=body.get("output_policy", ""),
                use_ai_generation=bool(body.get("use_ai_generation", False)),
                use_ai_repair=bool(body.get("use_ai_repair", False)),
            )
        except TypeError:
            try:
                result = jobs.run_job(
                    body.get("name", ""),
                    target_value=body.get("target", ""),
                    output_policy=body.get("output_policy", ""),
                    use_ai_generation=bool(body.get("use_ai_generation", False)),
                )
            except TypeError:
                result = jobs.run_job(
                    body.get("name", ""),
                    target_value=body.get("target", ""),
                    output_policy=body.get("output_policy", ""),
                )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except DependencyError as exc:
        return jsonify({"error": str(exc)}), 400
    except TimeoutError as exc:
        return jsonify({"error": str(exc)}), 408
    _invalidate_workspace_cache(root)
    return jsonify(_job_payload(result))


@workspace_bp.route("/workspace/guided/plan", methods=["POST"])
def workspace_guided_plan():
    body = request.get_json()
    root = body.get("root", ".")
    workflow_source = body.get("workflow_source", "core")
    try:
        container = _container_for_root(root)
        if workflow_source == "job":
            guided = container.guided.create_job_run(body.get("workflow_name", "") or body.get("job_name", ""))
        else:
            guided = container.guided.create_core_run(_target_from_body(body, root))
        payload = serialize_run_history_record(
            guided.history_id,
            container.workspace.get_run(guided.history_id),
            model=container.config.ai_model,
            run_loader=lambda child_id: container.workspace.get_run(child_id),
        )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except DependencyError as exc:
        return jsonify({"error": str(exc)}), 400
    except TimeoutError as exc:
        return jsonify({"error": str(exc)}), 408
    _invalidate_workspace_cache(root)
    return jsonify(payload)


@workspace_bp.route("/workspace/guided/step", methods=["POST"])
def workspace_guided_step():
    body = request.get_json()
    root = body.get("root", ".")
    action = body.get("action", "approve")
    history_id = body.get("history_id", "")
    step_id = body.get("step_id", "")
    try:
        container = _container_for_root(root)
        if action == "skip":
            guided = container.guided.skip_step(history_id, step_id)
        elif action == "reject":
            guided = container.guided.reject_step(history_id, step_id)
        else:
            guided = container.guided.approve_step(
                history_id,
                step_id,
                use_ai_generation=bool(body.get("use_ai_generation", False)),
                use_ai_repair=bool(body.get("use_ai_repair", False)),
            )
        payload = serialize_run_history_record(
            guided.history_id,
            container.workspace.get_run(guided.history_id),
            model=container.config.ai_model,
            run_loader=lambda child_id: container.workspace.get_run(child_id),
        )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except DependencyError as exc:
        return jsonify({"error": str(exc)}), 400
    except TimeoutError as exc:
        return jsonify({"error": str(exc)}), 408
    _invalidate_workspace_cache(root)
    return jsonify(payload)


@workspace_bp.route("/workspace/guided/run", methods=["GET"])
def workspace_guided_run():
    root = request.args.get("root", ".")
    history_id = request.args.get("history_id", "")
    try:
        container = _container_for_root(root)
        payload = serialize_run_history_record(
            history_id,
            container.workspace.get_run(history_id),
            model=container.config.ai_model,
            run_loader=lambda child_id: container.workspace.get_run(child_id),
        )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(payload)


@workspace_bp.route("/workspace/test/generate", methods=["POST"])
def workspace_test_generate():
    return _workspace_test_action("generate")


@workspace_bp.route("/workspace/test/update", methods=["POST"])
def workspace_test_update():
    return _workspace_test_action("update")


@workspace_bp.route("/workspace/test/fix-failures", methods=["POST"])
def workspace_test_fix_failures():
    return _workspace_test_action("fix-failures")


def _workspace_test_action(action: str):
    body = request.get_json()
    root = body.get("root", ".")
    target = _target_from_body(body, root)
    write = bool(body.get("write", False))
    jobs = _container_for_root(root).jobs
    try:
        if action == "generate":
            try:
                result = jobs.generate_tests(target, write=write, use_ai_generation=bool(body.get("use_ai_generation", False)))
            except TypeError:
                result = jobs.generate_tests(target, write=write)
        elif action == "update":
            try:
                result = jobs.update_tests(target, write=write, use_ai_generation=bool(body.get("use_ai_generation", False)))
            except TypeError:
                result = jobs.update_tests(target, write=write)
        else:
            try:
                result = jobs.fix_failed_tests(
                    target,
                    write=write,
                    use_ai_generation=bool(body.get("use_ai_generation", False)),
                    use_ai_repair=bool(body.get("use_ai_repair", False)),
                )
            except TypeError:
                try:
                    result = jobs.fix_failed_tests(
                        target,
                        write=write,
                        use_ai_generation=bool(body.get("use_ai_generation", False)),
                    )
                except TypeError:
                    result = jobs.fix_failed_tests(target, write=write)
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except DependencyError as exc:
        return jsonify({"error": str(exc)}), 400
    except TimeoutError as exc:
        return jsonify({"error": str(exc)}), 408
    _invalidate_workspace_cache(root)
    return jsonify(_job_payload(result))


def _serialize_ai_policy_state(state: dict) -> dict:
    return {
        "effective_ai_policy": serialize_ai_policy(state["effective_ai_policy"]),
        "global_ai_policy": serialize_ai_policy(state["global_ai_policy"]),
        "workspace_ai_policy": serialize_ai_policy(state["workspace_ai_policy"]),
        "ai_policy_source": state["ai_policy_source"],
    }
