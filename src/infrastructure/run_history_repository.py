import json
import os
from datetime import datetime

from src.application.exceptions import ValidationError
from src.application.workspace_models import JobRunResult


class RunHistoryRepository:
    def __init__(self, runs_dir: str):
        self.runs_dir = runs_dir

    def save(self, result: JobRunResult) -> str:
        os.makedirs(self.runs_dir, exist_ok=True)
        history_id = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
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
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
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
