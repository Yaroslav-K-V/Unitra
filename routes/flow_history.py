"""Flow run-history persistence for the SPA.

The SPA mirrors run records into ``data/flow-runs.json`` so they survive a
localStorage wipe. Local-only — no auth, capped at 200 records.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List

from flask import Blueprint, current_app, jsonify, request

from src.application.exceptions import ValidationError

log = logging.getLogger(__name__)
flow_history_bp = Blueprint("flow_history", __name__)

_CAP = 200
_LOCK = threading.Lock()


def _store_path() -> str:
    return os.path.join(current_app.root_path, "data", "flow-runs.json")


def _read_runs() -> List[Dict[str, Any]]:
    path = _store_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        runs = payload.get("runs") if isinstance(payload, dict) else None
        return runs if isinstance(runs, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write_runs(runs: List[Dict[str, Any]]) -> None:
    path = _store_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"runs": runs[-_CAP:]}, f, ensure_ascii=False)
    os.replace(tmp, path)


@flow_history_bp.route("/api/flow-runs", methods=["GET"])
def list_runs():
    with _LOCK:
        return jsonify({"runs": _read_runs()})


@flow_history_bp.route("/api/flow-runs", methods=["POST"])
def append_run():
    body = request.get_json(silent=True) or {}
    record = body.get("record")
    if not isinstance(record, dict):
        return jsonify({"error": "expected JSON body with 'record' object"}), 400
    record = dict(record)
    record.setdefault("ts", int(time.time() * 1000))
    record.setdefault("id", f"r{int(time.time()*1000):x}")
    # Trim attacker-controlled bloat — record itself can be at most 64 KB.
    if len(json.dumps(record)) > 64_000:
        raise ValidationError("run record too large (>64KB)")
    with _LOCK:
        runs = _read_runs()
        runs.append(record)
        _write_runs(runs)
    return jsonify({"ok": True, "id": record["id"], "count": min(len(runs), _CAP)})


@flow_history_bp.route("/api/flow-runs", methods=["DELETE"])
def clear_runs():
    with _LOCK:
        _write_runs([])
    return jsonify({"ok": True})
