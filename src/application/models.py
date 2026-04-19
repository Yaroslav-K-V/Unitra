from dataclasses import dataclass, field
from typing import List, Optional

from src.application.ai_policy import AiPolicy


@dataclass(frozen=True)
class SourceBundle:
    source_code: str
    files_scanned: int = 0
    paths: List[str] = field(default_factory=list)
    folder: str = ""


@dataclass(frozen=True)
class GenerationResult:
    test_code: str
    conftest_code: str
    functions_found: int
    classes_found: int
    tests_generated: int
    files_scanned: int = 0


@dataclass(frozen=True)
class ScanResult:
    count: int


@dataclass(frozen=True)
class RunTestsRequest:
    test_code: str
    source_code: str = ""
    source_folder: str = ""


@dataclass(frozen=True)
class RunResult:
    output: str
    returncode: int
    coverage: Optional[str] = None


@dataclass(frozen=True)
class RecentItem:
    path: str
    type: str


@dataclass(frozen=True)
class SaveSettingsRequest:
    api_key: str = ""
    model: str = ""
    show_hints: Optional[bool] = None
    ai_policy: Optional[AiPolicy] = None


@dataclass(frozen=True)
class SettingsResult:
    saved: bool
    model: str = ""
    api_key_set: bool = False
    show_hints: bool = True
    ai_policy: AiPolicy = field(default_factory=AiPolicy)
