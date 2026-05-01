"""Registry and discovery helpers for Unitra generator plugins."""

from __future__ import annotations

import ast
from importlib import import_module
from importlib import metadata
from typing import List, Optional, Sequence

from src.application.exceptions import ValidationError
from src.generator_plugins.base import (
    GeneratedTestSuite,
    GeneratorContext,
    GeneratorDescriptor,
    TestGeneratorPlugin,
)
from src.generator_plugins.builtin import VanillaPythonGenerator, builtin_plugins
from src.parser import parse_classes, parse_functions

ENTRY_POINT_GROUP = "unitra.generators"


class GeneratorRegistry:
    """Load built-in, entry-point, and workspace-registered generator plugins."""

    def __init__(self) -> None:
        self._builtin_plugins = [self._coerce_plugin(item) for item in builtin_plugins()]

    def build_context(
        self,
        source_code: str,
        source_path: str = "",
        workspace_root: str = "",
    ) -> GeneratorContext:
        tree = ast.parse(source_code)
        imports = []
        import_roots = []
        top_level_names = []
        class_bases = {}
        class_decorators = {}
        class_fields = {}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
                    import_roots.append(alias.name.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imports.append(module)
                if module:
                    import_roots.append(module.split(".", 1)[0])
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        top_level_names.append(target.id)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                top_level_names.append(node.name)
            if isinstance(node, ast.ClassDef):
                class_bases[node.name] = [ast.unparse(base) for base in node.bases]
                class_decorators[node.name] = [ast.unparse(item) for item in node.decorator_list]
                fields = {}
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        fields[item.target.id] = ast.unparse(item.annotation)
                class_fields[node.name] = fields
        return GeneratorContext(
            source_code=source_code,
            functions=parse_functions(source_code),
            classes=parse_classes(source_code),
            imports=imports,
            import_roots=sorted(dict.fromkeys(import_roots)),
            top_level_names=sorted(dict.fromkeys(top_level_names)),
            class_bases=class_bases,
            class_decorators=class_decorators,
            class_fields=class_fields,
            source_path=source_path,
            workspace_root=workspace_root,
        )

    def generate(
        self,
        source_code: str,
        source_path: str = "",
        workspace_root: str = "",
        custom_generators: Optional[Sequence[str]] = None,
    ) -> GeneratedTestSuite:
        context = self.build_context(source_code, source_path=source_path, workspace_root=workspace_root)
        plugins = self._all_plugins(custom_generators)
        matches = []
        for plugin in plugins:
            try:
                score = int(plugin.score(context))
            except Exception:
                continue
            if score > 0:
                matches.append((score, plugin.priority, plugin))
        if not matches:
            fallback = VanillaPythonGenerator()
            return fallback.generate(context)
        matches.sort(key=lambda item: (item[0], item[1]), reverse=True)
        for _, _, plugin in matches:
            try:
                generated = plugin.generate(context)
            except Exception:
                continue
            if generated.test_code.strip():
                return generated
        return VanillaPythonGenerator().generate(context)

    def describe(self, custom_generators: Optional[Sequence[str]] = None) -> List[GeneratorDescriptor]:
        descriptors = [
            GeneratorDescriptor(
                name=plugin.name,
                project_type=plugin.project_type,
                source=plugin.source,
                priority=plugin.priority,
                factory=plugin.factory,
                loaded=True,
            )
            for plugin in self._builtin_plugins
        ]
        descriptors.extend(self._entry_point_descriptors())
        descriptors.extend(self._custom_descriptors(custom_generators or []))
        return descriptors

    def validate_custom_generator(self, factory_path: str) -> GeneratorDescriptor:
        plugin = self._load_custom_plugin(factory_path, source="workspace")
        return GeneratorDescriptor(
            name=plugin.name,
            project_type=plugin.project_type,
            source=plugin.source,
            priority=plugin.priority,
            factory=plugin.factory,
            loaded=True,
        )

    def _all_plugins(self, custom_generators: Optional[Sequence[str]]) -> List[TestGeneratorPlugin]:
        plugins = list(self._builtin_plugins)
        plugins.extend(self._load_entry_point_plugins())
        for factory_path in custom_generators or []:
            try:
                plugins.append(self._load_custom_plugin(factory_path, source="workspace"))
            except Exception:
                continue
        return plugins

    def _load_entry_point_plugins(self) -> List[TestGeneratorPlugin]:
        plugins = []
        for entry_point in self._entry_points():
            try:
                plugins.append(self._coerce_plugin(entry_point.load(), source="entry-point", factory=entry_point.value))
            except Exception:
                continue
        return plugins

    def _entry_point_descriptors(self) -> List[GeneratorDescriptor]:
        descriptors = []
        for entry_point in self._entry_points():
            try:
                plugin = self._coerce_plugin(entry_point.load(), source="entry-point", factory=entry_point.value)
            except Exception as exc:
                descriptors.append(
                    GeneratorDescriptor(
                        name=entry_point.name,
                        project_type="unknown",
                        source="entry-point",
                        priority=0,
                        factory=entry_point.value,
                        loaded=False,
                        error=str(exc),
                    )
                )
                continue
            descriptors.append(
                GeneratorDescriptor(
                    name=plugin.name,
                    project_type=plugin.project_type,
                    source=plugin.source,
                    priority=plugin.priority,
                    factory=plugin.factory,
                    loaded=True,
                )
            )
        return descriptors

    def _custom_descriptors(self, custom_generators: Sequence[str]) -> List[GeneratorDescriptor]:
        descriptors = []
        for factory_path in custom_generators:
            try:
                plugin = self._load_custom_plugin(factory_path, source="workspace")
            except Exception as exc:
                descriptors.append(
                    GeneratorDescriptor(
                        name=factory_path,
                        project_type="unknown",
                        source="workspace",
                        priority=0,
                        factory=factory_path,
                        loaded=False,
                        error=str(exc),
                    )
                )
                continue
            descriptors.append(
                GeneratorDescriptor(
                    name=plugin.name,
                    project_type=plugin.project_type,
                    source=plugin.source,
                    priority=plugin.priority,
                    factory=plugin.factory,
                    loaded=True,
                )
            )
        return descriptors

    @staticmethod
    def _entry_points():
        try:
            return metadata.entry_points(group=ENTRY_POINT_GROUP)
        except TypeError:
            return metadata.entry_points().get(ENTRY_POINT_GROUP, [])

    def _load_custom_plugin(self, factory_path: str, source: str) -> TestGeneratorPlugin:
        if ":" not in factory_path:
            raise ValidationError("Custom generator path must look like 'module.submodule:factory'.")
        module_name, attribute = factory_path.split(":", 1)
        module = import_module(module_name)
        if not hasattr(module, attribute):
            raise ValidationError(f"Generator factory '{factory_path}' could not be imported.")
        loaded = getattr(module, attribute)
        return self._coerce_plugin(loaded, source=source, factory=factory_path)

    @staticmethod
    def _coerce_plugin(loaded, source: Optional[str] = None, factory: str = "") -> TestGeneratorPlugin:
        candidate = loaded() if isinstance(loaded, type) else loaded
        if callable(candidate) and not isinstance(candidate, type) and not hasattr(candidate, "generate"):
            candidate = candidate()
        if not isinstance(candidate, TestGeneratorPlugin):
            raise ValidationError("Generator plugin must expose 'score()' and 'generate()' methods.")
        for attribute, default in (
            ("name", candidate.__class__.__name__),
            ("project_type", "custom"),
            ("priority", 50),
            ("source", source or getattr(candidate, "source", "custom")),
            ("factory", factory or getattr(candidate, "factory", "")),
        ):
            if not hasattr(candidate, attribute):
                try:
                    setattr(candidate, attribute, default)
                except Exception:
                    pass
        if source:
            try:
                setattr(candidate, "source", source)
            except Exception:
                pass
        if factory:
            try:
                setattr(candidate, "factory", factory)
            except Exception:
                pass
        return candidate
