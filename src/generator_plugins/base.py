"""Core contracts for pluggable Unitra test generators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Protocol, runtime_checkable

from src.parser import ClassInfo, FunctionInfo


@dataclass(frozen=True)
class GeneratorContext:
    """Parsed source information shared with generator plugins."""

    source_code: str
    functions: List[FunctionInfo]
    classes: List[ClassInfo]
    imports: List[str]
    import_roots: List[str]
    top_level_names: List[str]
    class_bases: Dict[str, List[str]] = field(default_factory=dict)
    class_decorators: Dict[str, List[str]] = field(default_factory=dict)
    class_fields: Dict[str, Dict[str, str]] = field(default_factory=dict)
    source_path: str = ""
    workspace_root: str = ""


@dataclass(frozen=True)
class GeneratedTestSuite:
    """Generated tests plus metadata about the plugin that produced them."""

    test_code: str
    conftest_code: str = ""
    generator_name: str = "ast-basic"
    project_type: str = "vanilla-python"
    generator_source: str = "builtin"
    notes: List[str] = field(default_factory=list)
    context: GeneratorContext = field(default_factory=lambda: GeneratorContext("", [], [], [], [], []))


@dataclass(frozen=True)
class GeneratorDescriptor:
    """Human-readable generator metadata for CLI and diagnostics."""

    name: str
    project_type: str
    source: str
    priority: int
    factory: str
    loaded: bool
    error: str = ""


@runtime_checkable
class TestGeneratorPlugin(Protocol):
    """Protocol implemented by built-in, entry-point, and user generator plugins."""

    name: str
    project_type: str
    priority: int
    source: str
    factory: str

    def score(self, context: GeneratorContext) -> int:
        """Return a positive score when the plugin matches the source context."""

    def generate(self, context: GeneratorContext) -> GeneratedTestSuite:
        """Produce a pytest module and optional conftest content."""
