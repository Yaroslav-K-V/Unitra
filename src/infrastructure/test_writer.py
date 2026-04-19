import os
from typing import List

from src.application.workspace_models import ManagedFileResult, WritePlan


class TestWriter:
    def apply(self, plans: List[WritePlan], write: bool) -> List[ManagedFileResult]:
        results = []
        for plan in plans:
            written = False
            if write and plan.action != "manual-review":
                os.makedirs(os.path.dirname(plan.test_path), exist_ok=True)
                with open(plan.test_path, "w", encoding="utf-8") as handle:
                    handle.write(plan.generated_content)
                written = True
            results.append(
                ManagedFileResult(
                    source_path=plan.source_path,
                    test_path=plan.test_path,
                    action=plan.action,
                    written=written,
                    managed=plan.managed,
                    ai_attempted=plan.ai_attempted,
                    ai_used=plan.ai_used,
                    ai_status=plan.ai_status,
                    ai_reason=plan.ai_reason,
                )
            )
        return results
