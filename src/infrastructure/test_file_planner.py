import difflib
import os
from typing import Iterable, List

from src.application.workspace_models import (
    PlannedTestFile,
    USER_BLOCK_BEGIN,
    USER_BLOCK_END,
    WorkspaceConfig,
    WritePlan,
)


class TestFilePlanner:
    def plan_paths(self, workspace: WorkspaceConfig, source_paths: Iterable[str]) -> List[PlannedTestFile]:
        plans = []
        for source_path in source_paths:
            rel_source = os.path.relpath(source_path, workspace.root_path)
            rel_without_ext = os.path.splitext(rel_source)[0]
            directory, module_name = os.path.split(rel_without_ext)
            test_name = workspace.naming_strategy.format(module=module_name)
            if workspace.test_path_strategy == "mirror" and directory:
                test_path = os.path.join(workspace.root_path, workspace.test_root, directory, test_name)
            else:
                test_path = os.path.join(workspace.root_path, workspace.test_root, test_name)
            exists = os.path.exists(test_path)
            managed = exists and self._is_managed(test_path)
            plans.append(
                PlannedTestFile(
                    source_path=source_path,
                    test_path=test_path,
                    exists=exists,
                    managed=managed,
                )
            )
        return plans

    def build_write_plan(
        self,
        planned: PlannedTestFile,
        generated_content: str,
        ai_attempted=None,
        ai_used=None,
        ai_status: str = "unknown",
        ai_reason: str = "",
    ) -> WritePlan:
        current = ""
        preserved_user_block = ""
        if planned.exists:
            with open(planned.test_path, encoding="utf-8", errors="replace") as handle:
                current = handle.read()
            preserved_user_block = self._extract_user_block(current)
        final_content = generated_content.rstrip() + "\n"
        if preserved_user_block:
            final_content = self._merge_user_block(final_content, preserved_user_block)
        action = "create"
        if planned.exists and planned.managed:
            action = "update"
        elif planned.exists and not planned.managed:
            action = "manual-review"
        diff = "".join(
            difflib.unified_diff(
                current.splitlines(keepends=True),
                final_content.splitlines(keepends=True),
                fromfile=planned.test_path,
                tofile=planned.test_path,
            )
        )
        return WritePlan(
            source_path=planned.source_path,
            test_path=planned.test_path,
            action=action,
            generated_content=final_content,
            diff=diff,
            managed=planned.managed,
            preserved_user_block=preserved_user_block,
            ai_attempted=ai_attempted,
            ai_used=ai_used,
            ai_status=ai_status,
            ai_reason=ai_reason,
        )

    @staticmethod
    def _is_managed(path: str) -> bool:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return "Managed by Unitra" in handle.read(256)

    @staticmethod
    def _merge_user_block(content: str, preserved_user_block: str) -> str:
        begin = content.find(USER_BLOCK_BEGIN)
        end = content.find(USER_BLOCK_END)
        if begin == -1 or end == -1 or end < begin:
            return content.rstrip() + "\n\n" + preserved_user_block.rstrip() + "\n"
        end += len(USER_BLOCK_END)
        return content[:begin] + preserved_user_block.rstrip() + content[end:]

    @staticmethod
    def _extract_user_block(content: str) -> str:
        begin = content.find(USER_BLOCK_BEGIN)
        end = content.find(USER_BLOCK_END)
        if begin == -1 or end == -1 or end < begin:
            return ""
        end += len(USER_BLOCK_END)
        return content[begin:end]
