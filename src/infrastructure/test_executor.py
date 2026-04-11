import os
import shutil
import subprocess
import sys
import tempfile
from typing import Optional

from src.application.exceptions import DependencyError
from src.application.models import RunResult


class SubprocessTestExecutor:
    def __init__(self, timeout: int, fallback_dir: str):
        self._timeout = timeout
        self._fallback_dir = fallback_dir

    def run(self, full_code: str, work_dir: Optional[str]) -> RunResult:
        self._ensure_pytest()
        save_dir = work_dir or self._fallback_dir
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
            dir=save_dir,
        ) as handle:
            handle.write(full_code)
            tmp_path = handle.name

        try:
            return self._run_pytest([tmp_path], work_dir=work_dir)
        finally:
            os.unlink(tmp_path)

    def run_multiple(self, modules: list[str], work_dir: Optional[str]) -> RunResult:
        self._ensure_pytest()
        save_dir = work_dir or self._fallback_dir
        with tempfile.TemporaryDirectory(prefix="unitra-generated-", dir=save_dir) as temp_dir:
            tmp_paths = []
            for index, module in enumerate(modules):
                path = os.path.join(temp_dir, f"test_unitra_generated_{index}.py")
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(module)
                tmp_paths.append(path)
            return self._run_pytest(tmp_paths, work_dir=work_dir)

    def _ensure_pytest(self) -> None:
        has_pytest = shutil.which("pytest") or self._module_available("pytest")
        if not has_pytest:
            raise DependencyError("pytest not found — run: pip install pytest")

    @staticmethod
    def _module_available(module_name: str) -> bool:
        return subprocess.run(
            [sys.executable, "-m", module_name, "--version"],
            capture_output=True,
        ).returncode == 0

    def _run_pytest(self, test_paths: list[str], work_dir: Optional[str]) -> RunResult:
        has_cov = self._module_available("coverage")
        cov_args = ["--cov", "--cov-report=term-missing"] if has_cov else []
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", *test_paths, "-v", "--tb=short", "--no-header"] + cov_args,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=work_dir,
            )
            output = result.stdout + result.stderr
            return RunResult(
                output=output,
                returncode=result.returncode,
                coverage=self._extract_coverage(output),
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"Timed out after {self._timeout}s") from exc

    @staticmethod
    def _extract_coverage(output: str) -> Optional[str]:
        for line in output.splitlines():
            if line.strip().startswith("TOTAL"):
                parts = line.split()
                if parts:
                    return parts[-1]
        return None
