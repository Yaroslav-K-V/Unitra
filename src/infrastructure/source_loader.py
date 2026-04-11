import os
from typing import List

from src.application.exceptions import ValidationError
from src.application.models import SourceBundle
from src.application.source_utils import definitions_only


class SourceLoader:
    def __init__(self, skip_dirs: set[str]):
        self._skip_dirs = skip_dirs
        self._file_cache = {}
        self._list_cache = {}

    @staticmethod
    def _file_signature(path: str):
        stat = os.stat(path)
        return stat.st_mtime_ns, stat.st_size

    def _read_file_cached(self, path: str) -> str:
        signature = self._file_signature(path)
        cached = self._file_cache.get(path)
        if cached and cached[0] == signature:
            return cached[1]
        with open(path, encoding="utf-8", errors="replace") as handle:
            content = handle.read()
        self._file_cache[path] = (signature, content)
        return content

    def load_file(self, path: str) -> SourceBundle:
        if not os.path.isfile(path):
            raise ValidationError("File not found")
        return SourceBundle(source_code=self._read_file_cached(path), files_scanned=1, paths=[path])

    def load_paths(self, paths: List[str]) -> SourceBundle:
        parts = []
        scanned = 0
        kept_paths = []
        for path in paths:
            if not os.path.isfile(path):
                continue
            parts.append(f"# --- {os.path.basename(path)} ---\n" + self._read_file_cached(path))
            scanned += 1
            kept_paths.append(path)
        return SourceBundle(source_code="\n\n".join(parts), files_scanned=scanned, paths=kept_paths)

    def list_python_files(self, folder: str, include_tests: bool) -> List[str]:
        if not os.path.isdir(folder):
            raise ValidationError("Invalid folder path")
        folder = os.path.abspath(folder)
        paths = []
        for root, dirs, files in os.walk(folder):
            dirs[:] = [name for name in dirs if name not in self._skip_dirs]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                if not include_tests and fname.startswith("test_"):
                    continue
                paths.append(os.path.join(root, fname))
        paths.sort()
        return paths

    def load_folder(self, folder: str, include_tests: bool, definitions_only_mode: bool = False) -> SourceBundle:
        if not os.path.isdir(folder):
            raise ValidationError("Invalid folder path")
        parts = []
        scanned = 0
        paths = self.list_python_files(folder, include_tests=include_tests)
        for path in paths:
            content = self._read_file_cached(path)
            if definitions_only_mode:
                content = definitions_only(content)
            parts.append(f"# --- {os.path.basename(path)} ---\n" + content)
            scanned += 1
        return SourceBundle(source_code="\n\n".join(parts), files_scanned=scanned, folder=folder)

    def count_python_files(self, folder: str, include_tests: bool) -> int:
        if not os.path.isdir(folder):
            raise ValidationError("Invalid folder")
        return len(self.list_python_files(folder, include_tests=include_tests))
