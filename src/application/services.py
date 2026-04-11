from typing import List

from src.application.exceptions import ValidationError
from src.application.models import (
    GenerationResult,
    RunResult,
    RunTestsRequest,
    SaveSettingsRequest,
    ScanResult,
    SettingsResult,
)
from src.application.source_utils import count_tests
from src.generator import generate_conftest, generate_test_module
from src.parser import parse_classes, parse_functions


class GenerationService:
    def __init__(self, source_loader):
        self._source_loader = source_loader

    def generate_from_code(self, code: str) -> GenerationResult:
        return self._generate(code, files_scanned=0)

    def generate_from_paths(self, paths: List[str]) -> GenerationResult:
        bundle = self._source_loader.load_paths(paths)
        return self._generate(bundle.source_code, files_scanned=bundle.files_scanned)

    def generate_from_folder(self, folder: str) -> GenerationResult:
        bundle = self._source_loader.load_folder(folder, include_tests=False)
        return self._generate(bundle.source_code, files_scanned=bundle.files_scanned)

    def scan_count(self, folder: str) -> ScanResult:
        return ScanResult(count=self._source_loader.count_python_files(folder, include_tests=False))

    def _generate(self, source_code: str, files_scanned: int) -> GenerationResult:
        try:
            functions = parse_functions(source_code)
            classes = parse_classes(source_code)
        except SyntaxError as exc:
            raise ValidationError(f"SyntaxError: {exc.msg} (line {exc.lineno})") from exc
        test_code = generate_test_module(functions, classes)
        conftest_code = generate_conftest(classes) if classes else ""
        return GenerationResult(
            test_code=test_code,
            conftest_code=conftest_code,
            functions_found=len(functions),
            classes_found=len(classes),
            tests_generated=count_tests(test_code),
            files_scanned=files_scanned,
        )


class AiGenerationService:
    def __init__(self, source_loader, ai_runner):
        self._source_loader = source_loader
        self._ai_runner = ai_runner

    def generate_from_code(self, code: str) -> GenerationResult:
        return self._generate(code)

    def generate_from_paths(self, paths: List[str]) -> GenerationResult:
        bundle = self._source_loader.load_paths(paths)
        return self._generate(bundle.source_code, bundle.files_scanned)

    def generate_from_file(self, path: str) -> GenerationResult:
        bundle = self._source_loader.load_file(path)
        return self._generate(bundle.source_code, bundle.files_scanned)

    def generate_from_folder(self, folder: str) -> GenerationResult:
        bundle = self._source_loader.load_folder(folder, include_tests=True)
        return self._generate(bundle.source_code, bundle.files_scanned)

    def stream_from_code(self, code: str):
        return self._ai_runner.stream(code)

    def _generate(self, source_code: str, files_scanned: int = 0) -> GenerationResult:
        try:
            functions = parse_functions(source_code)
            classes = parse_classes(source_code)
        except SyntaxError as exc:
            raise ValidationError(f"SyntaxError: {exc.msg} (line {exc.lineno})") from exc
        test_code = self._ai_runner.run(source_code)
        conftest_code = generate_conftest(classes) if classes else ""
        return GenerationResult(
            test_code=test_code,
            conftest_code=conftest_code,
            functions_found=len(functions),
            classes_found=len(classes),
            tests_generated=count_tests(test_code),
            files_scanned=files_scanned,
        )


class TestRunService:
    def __init__(self, source_loader, test_executor):
        self._source_loader = source_loader
        self._test_executor = test_executor

    def run_tests(self, request: RunTestsRequest) -> RunResult:
        if not request.test_code:
            raise ValidationError("No test code provided")

        source_code = request.source_code
        work_dir = request.source_folder or None
        if not source_code and work_dir:
            bundle = self._source_loader.load_folder(work_dir, include_tests=False, definitions_only_mode=True)
            source_code = bundle.source_code

        full_code = (source_code + "\n\n" + request.test_code) if source_code else request.test_code
        return self._test_executor.run(full_code=full_code, work_dir=work_dir)

    def run_multiple(self, modules: List[str], work_dir: str = "") -> RunResult:
        if not modules:
            raise ValidationError("No test code provided")
        return self._test_executor.run_multiple(modules=modules, work_dir=work_dir or None)


class RecentService:
    def __init__(self, repository):
        self._repository = repository

    def list_recent(self):
        return self._repository.list_items()

    def add_recent(self, path: str) -> None:
        if path:
            self._repository.add_item(path)


class SettingsService:
    def __init__(self, repository):
        self._repository = repository

    def save_settings(self, request: SaveSettingsRequest) -> SettingsResult:
        saved = self._repository.save(
            api_key=request.api_key,
            model=request.model,
            show_hints=request.show_hints,
        )
        return SettingsResult(
            saved=True,
            model=saved.get("OPENAI_MODEL", request.model),
            api_key_set=bool(saved.get("API_KEY")),
            show_hints=saved.get("SHOW_HINTS", "1") != "0",
        )
