import json
import os
from datetime import datetime
from dataclasses import asdict, is_dataclass

from src.application.exceptions import ValidationError
from src.application.workspace_models import JobRunResult


class RunHistoryRepository:
    def __init__(self, runs_dir: str):
        self.runs_dir = runs_dir

    def save(self, result: JobRunResult) -> str:
        os.makedirs(self.runs_dir, exist_ok=True)
        history_id = self._new_history_id()
        path = os.path.join(self.runs_dir, f"{history_id}.json")
        payload = {
            "job_name": result.job_name,
            "mode": result.mode,
            "target_scope": result.target_scope,
            "planned_files": [plan.__dict__ for plan in result.planned_files],
            "written_files": [item.__dict__ for item in result.written_files],
            "run_output": result.run_output,
            "run_returncode": result.run_returncode,
            "run_coverage": result.run_coverage,
            "llm_fallback_contexts": result.llm_fallback_contexts,
            "failure_categories": result.failure_categories,
            "ai_repair_suggestions": result.ai_repair_suggestions,
            "ai_repair_requested": result.ai_repair_requested,
            "ai_repair_used": result.ai_repair_used,
            "ai_repair_status": result.ai_repair_status,
            "ai_repair_reason": result.ai_repair_reason,
            "generated_tests_count": result.generated_tests_count,
            "total_duration_ms": result.total_duration_ms,
            "cache_hits": result.cache_hits,
            "generator_breakdown": result.generator_breakdown,
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return history_id

    def create_guided(self, guided_run) -> str:
        os.makedirs(self.runs_dir, exist_ok=True)
        history_id = self._new_history_id()
        payload = self._guided_payload(guided_run, history_id=history_id)
        self._write(history_id, payload)
        return history_id

    def save_guided(self, guided_run) -> str:
        history_id = getattr(guided_run, "history_id", "") or ""
        if not history_id:
            raise ValidationError("Guided run is missing a history id")
        self._write(history_id, self._guided_payload(guided_run, history_id=history_id))
        return history_id

    def list_ids(self, limit: int = 20):
        if not os.path.isdir(self.runs_dir):
            return []
        run_files = sorted(
            filename[:-5]
            for filename in os.listdir(self.runs_dir)
            if filename.endswith(".json")
        )
        return list(reversed(run_files[-limit:]))

    def load(self, history_id: str):
        path = os.path.join(self.runs_dir, f"{history_id}.json")
        if not os.path.exists(path):
            raise ValidationError(f"Run `{history_id}` not found")
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _new_history_id() -> str:
        return datetime.utcnow().strftime("%Y%m%d%H%M%S%f")

    @staticmethod
    def _guided_payload(guided_run, history_id: str) -> dict:
        payload = asdict(guided_run) if is_dataclass(guided_run) else dict(guided_run or {})
        payload["kind"] = "guided_run"
        payload["history_id"] = history_id
        return payload

    def _write(self, history_id: str, payload: dict) -> None:
        path = os.path.join(self.runs_dir, f"{history_id}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
