"""Background task orchestration for the desktop GUI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import threading
from typing import Any, Callable, Dict, Optional
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DesktopTask:
    """Progress state exposed to the desktop polling client."""

    task_id: str
    kind: str
    label: str
    status: str = "queued"
    progress: int = 0
    message: str = "Queued"
    stage: str = "queued"
    result: Optional[dict] = None
    error: str = ""
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)


class DesktopTaskManager:
    """Run background desktop tasks and expose polling-friendly progress."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: Dict[str, DesktopTask] = {}

    def start(self, kind: str, label: str, worker: Callable[[Callable[[dict], None]], dict]) -> str:
        task_id = uuid4().hex
        task = DesktopTask(task_id=task_id, kind=kind, label=label)
        with self._lock:
            self._tasks[task_id] = task
        thread = threading.Thread(target=self._run, args=(task_id, worker), daemon=True)
        thread.start()
        return task_id

    def get(self, task_id: str) -> Optional[dict]:
        with self._lock:
            task = self._tasks.get(task_id)
            return asdict(task) if task else None

    def list_active(self) -> list[dict]:
        with self._lock:
            return [
                asdict(task)
                for task in self._tasks.values()
                if task.status in {"queued", "running"}
            ]

    def _run(self, task_id: str, worker: Callable[[Callable[[dict], None]], dict]) -> None:
        self._update(task_id, status="running", progress=5, stage="start", message="Starting task.")
        try:
            result = worker(lambda payload: self._update(task_id, **payload))
        except Exception as exc:
            self._update(
                task_id,
                status="error",
                progress=100,
                stage="error",
                message="Task failed.",
                error=str(exc),
            )
            return
        self._update(
            task_id,
            status="completed",
            progress=100,
            stage="done",
            message="Task completed.",
            result=result,
        )

    def _update(self, task_id: str, **changes: Any) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            for key, value in changes.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            task.updated_at = _utc_now()
