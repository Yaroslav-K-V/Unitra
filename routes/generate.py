import ast
import json
import logging
from flask import Blueprint, Response, jsonify, request, stream_with_context

log = logging.getLogger(__name__)

from src.application.ai_policy import AiPolicy
from src.application.exceptions import ValidationError
from src.application.models import SaveSettingsRequest
from src.container import get_container, reset_container

generate_bp = Blueprint("generate", __name__)

_DEF_TYPES = (
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
    ast.Import, ast.ImportFrom,
)


def _definitions_only(source: str) -> str:
    """Return only class/function defs and imports — skips module-level statements."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        log.debug("Syntax error stripping module code: %s", e)
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
    try:
        result = get_container().generation.scan_count(folder)
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"count": result.count})


@generate_bp.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    try:
        result = get_container().generation.generate_from_code(data.get("code", ""))
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result.__dict__)


@generate_bp.route("/generate-files", methods=["POST"])
def generate_files():
    try:
        result = get_container().generation.generate_from_paths(request.get_json().get("paths", []))
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result.__dict__)


@generate_bp.route("/generate-project", methods=["POST"])
def generate_project():
    try:
        result = get_container().generation.generate_from_folder(request.get_json().get("folder", ""))
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result.__dict__)


@generate_bp.route("/settings/save", methods=["POST"])
def settings_save():
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
        reset_container()
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({
        "ok": result.saved,
        "provider": result.provider,
        "model": result.model,
        "api_key_set": result.api_key_set,
        "openai_api_key_set": result.openai_api_key_set,
        "openrouter_api_key_set": result.openrouter_api_key_set,
        "ollama_api_key_set": result.ollama_api_key_set,
        "show_hints": result.show_hints,
        "ai_policy": getattr(result, "ai_policy", AiPolicy()).to_dict(),
    })


@generate_bp.route("/generate-ai", methods=["POST"])
def generate_ai():
    data = request.get_json()
    try:
        if "code" in data:
            result = get_container().ai_generation.generate_from_code(data["code"])
        elif "paths" in data:
            result = get_container().ai_generation.generate_from_paths(data["paths"])
        elif "file" in data:
            result = get_container().ai_generation.generate_from_file(data["file"])
        elif "folder" in data:
            result = get_container().ai_generation.generate_from_folder(data["folder"])
        else:
            raise ValidationError("No input provided")
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except EnvironmentError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:
        return jsonify({"error": f"Agent error: {exc}"}), 500
    return jsonify(result.__dict__)


@generate_bp.route("/generate-ai-stream", methods=["GET"])
def generate_ai_stream():
    source_code = request.args.get("code", "")

    def generate():
        try:
            for token in get_container().ai_generation.stream_from_code(source_code):
                yield f"data: {json.dumps({'token': token})}\n\n"
        except EnvironmentError as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': f'Agent error: {exc}'})}\n\n"
        yield "event: done\ndata: {}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")
