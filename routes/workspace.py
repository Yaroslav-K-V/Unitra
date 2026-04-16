import os
import threading

from flask import Blueprint, jsonify, request

from src.application.exceptions import DependencyError, ValidationError
from src.application.workspace_models import TestTarget
from src.config import load_config
from src.container import build_container
from src.serializers import (
    serialize_agent_profile,
    serialize_job_result,
    serialize_run_history_record,
    serialize_workspace_status,
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
    paths = (config_path, jobs_dir, agents_dir, runs_dir)
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
    with _CACHE_LOCK:
        cached = _CONTAINER_CACHE.get(root)
        if cached is not None:
            return cached
        container = build_container(load_config(root_path=root))
        _CONTAINER_CACHE[root] = container
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
    return serialize_run_history_record(history_id, payload, model=model)


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
    return jsonify(config.__dict__)


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
        payload = _cached_payload(
            root,
            "agent-profile",
            lambda: serialize_agent_profile(_container_for_root(root).workspace.active_agent_profile()),
        )
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(payload)


@workspace_bp.route("/workspace/job/run", methods=["POST"])
def workspace_job_run():
    body = request.get_json()
    root = body.get("root", ".")
    try:
        result = _container_for_root(root).jobs.run_job(
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
            result = jobs.generate_tests(target, write=write)
        elif action == "update":
            result = jobs.update_tests(target, write=write)
        else:
            result = jobs.fix_failed_tests(target, write=write)
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except DependencyError as exc:
        return jsonify({"error": str(exc)}), 400
    except TimeoutError as exc:
        return jsonify({"error": str(exc)}), 408
    _invalidate_workspace_cache(root)
    return jsonify(_job_payload(result))
