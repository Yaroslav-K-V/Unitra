import ast
import os
from flask import Blueprint, jsonify, request

from src.parser import parse_functions, parse_classes
from src.generator import generate_test_module
from agent import run_agent

generate_bp = Blueprint("generate", __name__)

SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    ".tox", "dist", "build", ".mypy_cache", ".pytest_cache",
}

_DEF_TYPES = (
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
    ast.Import, ast.ImportFrom,
)


def _definitions_only(source: str) -> str:
    """Return only class/function defs and imports — skips module-level statements."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    lines = source.splitlines()
    parts = []
    for node in tree.body:
        if isinstance(node, _DEF_TYPES):
            parts.append("\n".join(lines[node.lineno - 1:node.end_lineno]))
    return "\n\n".join(parts)


def _count_tests(test_code: str) -> int:
    """Count how many test functions are in the generated test code."""
    return test_code.count("\ndef test_")


@generate_bp.route("/scan-count", methods=["GET"])
def scan_count():
    folder = request.args.get("folder", "")
    if not os.path.isdir(folder):
        return jsonify({"error": "Invalid folder"}), 400
    count = 0
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            if fname.endswith(".py") and not fname.startswith("test_"):
                count += 1
    return jsonify({"count": count})


@generate_bp.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    source_code = data.get("code", "")
    try:
        functions = parse_functions(source_code)
        classes = parse_classes(source_code)
    except SyntaxError as e:
        return jsonify({"error": f"SyntaxError: {e.msg} (line {e.lineno})"}), 400
    test_code = generate_test_module(functions, classes)
    return jsonify({
        "test_code": test_code,
        "functions_found": len(functions),
        "classes_found": len(classes),
        "tests_generated": _count_tests(test_code),
    })


@generate_bp.route("/generate-files", methods=["POST"])
def generate_files():
    paths = request.get_json().get("paths", [])
    parts = []
    for path in paths:
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", errors="ignore") as f:
            parts.append(f"# --- {os.path.basename(path)} ---\n" + f.read())
    source = "\n\n".join(parts)
    try:
        functions = parse_functions(source)
        classes = parse_classes(source)
    except SyntaxError as e:
        return jsonify({"error": f"SyntaxError: {e.msg} (line {e.lineno})"}), 400
    test_code = generate_test_module(functions, classes)
    return jsonify({
        "test_code": test_code,
        "functions_found": len(functions),
        "classes_found": len(classes),
        "tests_generated": _count_tests(test_code),
        "files_scanned": len(parts),
    })


@generate_bp.route("/generate-project", methods=["POST"])
def generate_project():
    folder = request.get_json().get("folder", "")
    if not os.path.isdir(folder):
        return jsonify({"error": "Invalid folder path"}), 400

    all_code = []
    files_scanned = 0
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            if fname.endswith(".py") and not fname.startswith("test_"):
                with open(os.path.join(root, fname), encoding="utf-8", errors="ignore") as f:
                    all_code.append(f"# --- {fname} ---\n" + f.read())
                files_scanned += 1

    source = "\n\n".join(all_code)
    try:
        functions = parse_functions(source)
        classes = parse_classes(source)
    except SyntaxError as e:
        return jsonify({"error": f"SyntaxError: {e.msg} (line {e.lineno})"}), 400

    test_code = generate_test_module(functions, classes)
    return jsonify({
        "test_code": test_code,
        "functions_found": len(functions),
        "classes_found": len(classes),
        "tests_generated": _count_tests(test_code),
        "files_scanned": files_scanned,
    })


@generate_bp.route("/generate-ai", methods=["POST"])
def generate_ai():
    data = request.get_json()
    source_code = ""

    if "code" in data:
        source_code = data["code"]
    elif "paths" in data:
        parts = []
        for path in data["paths"]:
            if os.path.isfile(path):
                with open(path, encoding="utf-8", errors="ignore") as f:
                    parts.append(f"# --- {os.path.basename(path)} ---\n" + f.read())
        source_code = "\n\n".join(parts)
    elif "file" in data:
        path = data["file"]
        if not os.path.isfile(path):
            return jsonify({"error": "File not found"}), 400
        with open(path, encoding="utf-8") as f:
            source_code = f.read()
    elif "folder" in data:
        folder = data["folder"]
        if not os.path.isdir(folder):
            return jsonify({"error": "Folder not found"}), 400
        parts = []
        for root, _, files in os.walk(folder):
            for fname in files:
                if fname.endswith(".py"):
                    with open(os.path.join(root, fname), encoding="utf-8", errors="ignore") as f:
                        parts.append(f"# --- {fname} ---\n" + f.read())
        source_code = "\n\n".join(parts)

    try:
        functions = parse_functions(source_code)
    except SyntaxError as e:
        return jsonify({"error": f"SyntaxError: {e.msg} (line {e.lineno})"}), 400

    try:
        test_code = run_agent(source_code)
    except EnvironmentError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"Agent error: {e}"}), 500

    classes = parse_classes(source_code)
    return jsonify({
        "test_code": test_code,
        "functions_found": len(functions),
        "classes_found": len(classes),
        "tests_generated": _count_tests(test_code),
    })
