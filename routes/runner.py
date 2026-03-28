import os
import sys
import shutil
import subprocess
import tempfile
from flask import Blueprint, jsonify, request, current_app

from src.recent import add_recent, get_recent
from routes.generate import SKIP_DIRS, _definitions_only

runner_bp = Blueprint("runner", __name__)


@runner_bp.route("/recent", methods=["GET"])
def recent():
    return jsonify(get_recent())


@runner_bp.route("/recent/add", methods=["POST"])
def recent_add():
    path = request.get_json().get("path", "")
    if path:
        add_recent(path)
    return jsonify({"ok": True})


@runner_bp.route("/run-tests", methods=["POST"])
def run_tests():
    body = request.get_json()
    test_code     = body.get("test_code", "")
    source_code   = body.get("source_code", "")
    source_folder = body.get("source_folder", "")

    if not test_code:
        return jsonify({"error": "No test code provided"}), 400

    work_dir = source_folder if source_folder and os.path.isdir(source_folder) else None

    if not source_code and work_dir:
        parts = []
        for root, dirs, files in os.walk(work_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fname in files:
                if fname.endswith(".py") and not fname.startswith("test_"):
                    try:
                        with open(os.path.join(root, fname), encoding="utf-8", errors="ignore") as f:
                            parts.append(_definitions_only(f.read()))
                    except Exception:
                        pass
        source_code = "\n\n".join(parts)

    full_code = (source_code + "\n\n" + test_code) if source_code else test_code

    has_pytest = shutil.which("pytest") or subprocess.run(
        [sys.executable, "-m", "pytest", "--version"],
        capture_output=True,
    ).returncode == 0
    if not has_pytest:
        return jsonify({"error": "pytest not found — run: pip install pytest"}), 400

    save_dir = work_dir or current_app.root_path
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8", dir=save_dir
    ) as f:
        f.write(full_code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", tmp_path, "-v", "--tb=short", "--no-header"],
            capture_output=True, text=True, timeout=30, cwd=work_dir,
        )
        return jsonify({
            "output": result.stdout + result.stderr,
            "returncode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timed out after 30s"}), 408
    finally:
        os.unlink(tmp_path)
