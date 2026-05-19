import logging
import os
import threading
from flask import Blueprint, jsonify, request

from src.application.exceptions import DependencyError, ValidationError
from src.application.models import RunTestsRequest
from src.container import get_container

# Reject these as work_dir for `pytest`. Conservative list: unambiguously-system
# roots. We don't block all of `/var` or `/usr` because tmpdirs (e.g. macOS
# /var/folders/...) and /usr/local/... contain legitimate project locations.
_FORBIDDEN_PREFIXES = (
    "/etc", "/bin", "/sbin", "/boot",
    "/proc", "/sys", "/dev",
    "/private/etc", "/private/sbin",
    "/System", "/usr/bin", "/usr/sbin",
    "C:\\Windows\\System32",
)


def _safe_workdir(raw: str) -> str:
    """Resolve and validate a user-supplied source_folder for use as a subprocess cwd.

    Empty input is allowed (pytest will run in the server's cwd).
    """
    if not raw:
        return ""
    try:
        resolved = os.path.realpath(raw)
    except (OSError, ValueError) as exc:
        raise ValidationError(f"source_folder is not a valid path: {exc}")
    if not os.path.isabs(resolved):
        raise ValidationError("source_folder must resolve to an absolute path")
    if not os.path.isdir(resolved):
        raise ValidationError(f"source_folder is not a directory: {resolved}")
    norm = resolved.rstrip(os.sep)
    for bad in _FORBIDDEN_PREFIXES:
        if norm == bad or norm.startswith(bad + os.sep):
            raise ValidationError(f"source_folder is in a protected system path: {bad}")
    return resolved

log = logging.getLogger(__name__)

runner_bp = Blueprint("runner", __name__)
_RECENT_CACHE_LOCK = threading.Lock()
_RECENT_CACHE = None


def _recent_cache_path() -> str:
    config = getattr(get_container(), "config", None)
    recent_path = getattr(config, "recent_path", "")
    if recent_path:
        return recent_path
    root_path = getattr(config, "root_path", "")
    if root_path:
        return os.path.join(root_path, "data", "recent.json")
    return ""


def _recent_signature() -> tuple:
    recent_path = _recent_cache_path()
    if not recent_path:
        return ("recent", None)
    try:
        return recent_path, os.path.getmtime(recent_path)
    except OSError:
        return recent_path, None


def _invalidate_recent_cache() -> None:
    global _RECENT_CACHE
    with _RECENT_CACHE_LOCK:
        _RECENT_CACHE = None


@runner_bp.route("/recent", methods=["GET"])
def recent():
    global _RECENT_CACHE
    signature = _recent_signature()
    with _RECENT_CACHE_LOCK:
        if _RECENT_CACHE and _RECENT_CACHE[0] == signature:
            return jsonify(_RECENT_CACHE[1])
    items = [item.__dict__ for item in get_container().recent.list_recent()]
    with _RECENT_CACHE_LOCK:
        _RECENT_CACHE = (signature, items)
    return jsonify(items)


@runner_bp.route("/recent/add", methods=["POST"])
def recent_add():
    path = request.get_json().get("path", "")
    get_container().recent.add_recent(path)
    _invalidate_recent_cache()
    return jsonify({"ok": True})


@runner_bp.route("/run-tests", methods=["POST"])
def run_tests():
    body = request.get_json()
    test_code = body.get("test_code", "")
    source_folder = body.get("source_folder", "")
    log.info("run-tests: %d chars of test code, folder=%r", len(test_code), source_folder or "(none)")
    try:
        safe_folder = _safe_workdir(source_folder)
        result = get_container().test_runner.run_tests(
            RunTestsRequest(
                test_code=test_code,
                source_code=body.get("source_code", ""),
                source_folder=safe_folder,
            )
        )
    except ValidationError as exc:
        log.warning("run-tests: validation error — %s", exc)
        return jsonify({"error": str(exc)}), 400
    except DependencyError as exc:
        log.warning("run-tests: dependency error — %s", exc)
        return jsonify({"error": str(exc)}), 400
    except TimeoutError as exc:
        log.warning("run-tests: timed out — %s", exc)
        return jsonify({"error": str(exc)}), 408
    status = "PASS" if getattr(result, "returncode", 1) == 0 else "FAIL"
    log.info("run-tests: %s (returncode=%s coverage=%s)", status,
             getattr(result, "returncode", "?"), getattr(result, "coverage", "?"))
    return jsonify(result.__dict__)
