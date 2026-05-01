"""Built-in generator plugins shipped with Unitra."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from src.generator import default_for_annotation, generate_conftest, generate_test_module
from src.generator_plugins.base import GeneratedTestSuite, GeneratorContext


def _render_signature_payload(annotations: Dict[str, str], names: Iterable[str]) -> Dict[str, str]:
    payload = {}
    for name in names:
        payload[name] = default_for_annotation(annotations.get(name))
    return payload


def _format_kwargs(payload: Dict[str, str]) -> str:
    return ", ".join(f"{key}={value}" for key, value in payload.items())


@dataclass
class VanillaPythonGenerator:
    """Fallback AST-based generator used when no plugin matches better."""

    name: str = "ast-basic"
    project_type: str = "vanilla-python"
    priority: int = 10
    source: str = "builtin"
    factory: str = "src.generator_plugins.builtin:VanillaPythonGenerator"

    def score(self, context: GeneratorContext) -> int:
        return 1

    def generate(self, context: GeneratorContext) -> GeneratedTestSuite:
        classes = context.classes or None
        return GeneratedTestSuite(
            test_code=generate_test_module(context.functions, classes),
            conftest_code=generate_conftest(context.classes) if context.classes else "",
            generator_name=self.name,
            project_type=self.project_type,
            generator_source=self.source,
            context=context,
        )


@dataclass
class FastApiFlaskGenerator:
    """API-focused generator for FastAPI and Flask apps."""

    name: str = "web-api"
    project_type: str = "fastapi-flask"
    priority: int = 90
    source: str = "builtin"
    factory: str = "src.generator_plugins.builtin:FastApiFlaskGenerator"

    def score(self, context: GeneratorContext) -> int:
        roots = set(context.import_roots)
        if "fastapi" in roots or "flask" in roots:
            return self.priority
        return 0

    def generate(self, context: GeneratorContext) -> GeneratedTestSuite:
        roots = set(context.import_roots)
        if "fastapi" in roots:
            test_code = self._generate_fastapi(context)
        else:
            test_code = self._generate_flask(context)
        return GeneratedTestSuite(
            test_code=test_code,
            generator_name=self.name,
            project_type=self.project_type,
            generator_source=self.source,
            notes=["Selected API-aware plugin based on FastAPI/Flask imports."],
            context=context,
        )

    @staticmethod
    def _app_reference(context: GeneratorContext) -> str:
        if "app" in context.top_level_names:
            return "app"
        for candidate in ("create_app", "build_app"):
            if candidate in {item.name for item in context.functions}:
                return f"{candidate}()"
        return "app"

    def _generate_fastapi(self, context: GeneratorContext) -> str:
        app_ref = self._app_reference(context)
        lines = [
            "import pytest",
            "from fastapi.testclient import TestClient",
            "",
            "@pytest.fixture",
            "def client():",
            f"    return TestClient({app_ref})",
            "",
            "def test_api_client_boots(client):",
            "    response = client.get('/')",
            "    assert response.status_code in {200, 404, 405}",
        ]
        if context.functions:
            lines.extend(["", generate_test_module(context.functions, context.classes or None).strip()])
        return "\n".join(lines).strip() + "\n"

    def _generate_flask(self, context: GeneratorContext) -> str:
        app_ref = self._app_reference(context)
        lines = [
            "import pytest",
            "",
            "@pytest.fixture",
            "def client():",
            f"    app_instance = {app_ref}",
            "    app_instance.config.update(TESTING=True)",
            "    with app_instance.test_client() as client:",
            "        yield client",
            "",
            "def test_flask_app_boots(client):",
            "    response = client.get('/')",
            "    assert response.status_code in {200, 404, 405}",
        ]
        if context.functions:
            lines.extend(["", generate_test_module(context.functions, context.classes or None).strip()])
        return "\n".join(lines).strip() + "\n"


@dataclass
class DjangoGenerator:
    """Generator tailored for Django models and app modules."""

    name: str = "django-models"
    project_type: str = "django"
    priority: int = 85
    source: str = "builtin"
    factory: str = "src.generator_plugins.builtin:DjangoGenerator"

    def score(self, context: GeneratorContext) -> int:
        roots = set(context.import_roots)
        has_django = "django" in roots or context.source_path.endswith("models.py")
        return self.priority if has_django else 0

    def generate(self, context: GeneratorContext) -> GeneratedTestSuite:
        model_classes = []
        for item in context.classes:
            bases = context.class_bases.get(item.name, [])
            if any(base.endswith("models.Model") or base.endswith(".Model") or base == "Model" for base in bases):
                model_classes.append(item)
        lines = ["import pytest", ""]
        if model_classes:
            lines.append("pytestmark = pytest.mark.django_db")
            lines.append("")
            for item in model_classes:
                lines.extend([
                    f"def test_{item.name.lower()}_model_metadata():",
                    f"    assert {item.name}._meta.model_name == {item.name.lower()!r}",
                    f"    assert {item.name}._meta.app_label",
                    "",
                ])
        else:
            lines.extend([
                "def test_django_module_imports():",
                "    assert True  # Replace with app-specific Django assertions.",
                "",
            ])
        return GeneratedTestSuite(
            test_code="\n".join(lines).strip() + "\n",
            generator_name=self.name,
            project_type=self.project_type,
            generator_source=self.source,
            notes=["Selected Django-aware plugin based on imports or module naming."],
            context=context,
        )


@dataclass
class PydanticDataclassGenerator:
    """Generator for pydantic v2 models and dataclasses."""

    name: str = "schema-models"
    project_type: str = "pydantic-dataclasses"
    priority: int = 80
    source: str = "builtin"
    factory: str = "src.generator_plugins.builtin:PydanticDataclassGenerator"

    def score(self, context: GeneratorContext) -> int:
        roots = set(context.import_roots)
        if "pydantic" in roots:
            return self.priority
        if any("dataclass" in decorators for decorators in context.class_decorators.values()):
            return self.priority - 5
        return 0

    def generate(self, context: GeneratorContext) -> GeneratedTestSuite:
        lines = ["import pytest", ""]
        emitted = False
        for item in context.classes:
            bases = context.class_bases.get(item.name, [])
            decorators = context.class_decorators.get(item.name, [])
            if any(base.endswith("BaseModel") for base in bases):
                field_annotations = dict(context.class_fields.get(item.name, {}))
                payload = _render_signature_payload(
                    field_annotations or item.constructor_annotations,
                    list(field_annotations) or item.constructor_args,
                )
                lines.extend([
                    f"def test_{item.name.lower()}_model_roundtrip():",
                    f"    payload = {{{', '.join(f'{key!r}: {value}' for key, value in payload.items())}}}",
                    f"    instance = {item.name}.model_validate(payload)",
                    "    assert instance.model_dump()",
                    "",
                ])
                emitted = True
            elif any(decorator.endswith("dataclass") for decorator in decorators):
                field_annotations = dict(context.class_fields.get(item.name, {}))
                payload = _render_signature_payload(
                    field_annotations or item.constructor_annotations,
                    list(field_annotations) or item.constructor_args,
                )
                instance_line = (
                    f"    instance = {item.name}({_format_kwargs(payload)})"
                    if payload
                    else f"    instance = {item.name}()"
                )
                lines.extend([
                    f"def test_{item.name.lower()}_dataclass_instantiation():",
                    instance_line,
                    f"    assert isinstance(instance, {item.name})",
                    "",
                ])
                emitted = True
        if not emitted:
            lines.extend([
                "def test_schema_module_smoke():",
                "    assert True  # Add schema-specific validation cases here.",
                "",
            ])
        return GeneratedTestSuite(
            test_code="\n".join(lines).strip() + "\n",
            generator_name=self.name,
            project_type=self.project_type,
            generator_source=self.source,
            notes=["Selected schema-aware plugin based on pydantic/dataclass patterns."],
            context=context,
        )


@dataclass
class DataScienceGenerator:
    """Generator for pandas and polars-heavy modules."""

    name: str = "dataframe-pipelines"
    project_type: str = "data-science"
    priority: int = 75
    source: str = "builtin"
    factory: str = "src.generator_plugins.builtin:DataScienceGenerator"

    def score(self, context: GeneratorContext) -> int:
        roots = set(context.import_roots)
        if "pandas" in roots or "polars" in roots:
            return self.priority
        if any(
            "DataFrame" in annotation
            for func in context.functions
            for annotation in func.arg_annotations.values()
        ):
            return self.priority - 5
        return 0

    def generate(self, context: GeneratorContext) -> GeneratedTestSuite:
        roots = set(context.import_roots)
        use_polars = "polars" in roots and "pandas" not in roots
        library_import = "import polars as pl" if use_polars else "import pandas as pd"
        frame_expr = (
            "pl.DataFrame({'value': [1, 2], 'group': ['a', 'b']})"
            if use_polars
            else "pd.DataFrame({'value': [1, 2], 'group': ['a', 'b']})"
        )
        expected_type = "pl.DataFrame" if use_polars else "pd.DataFrame"
        lines = ["import pytest", library_import, ""]
        emitted = False
        for func in context.functions:
            if not any("DataFrame" in value for value in func.arg_annotations.values()):
                continue
            arg_values = []
            for name in func.args:
                annotation = func.arg_annotations.get(name, "")
                if "DataFrame" in annotation:
                    arg_values.append(frame_expr)
                else:
                    arg_values.append(default_for_annotation(annotation))
            lines.extend([
                f"def test_{func.name}_dataframe_pipeline():",
                f"    result = {func.name}({', '.join(arg_values)})",
                f"    assert isinstance(result, {expected_type}) or result is not None",
                "",
            ])
            emitted = True
        if not emitted:
            lines.extend([
                "def test_dataframe_module_smoke():",
                f"    frame = {frame_expr}",
                "    assert frame is not None",
                "",
            ])
        return GeneratedTestSuite(
            test_code="\n".join(lines).strip() + "\n",
            generator_name=self.name,
            project_type=self.project_type,
            generator_source=self.source,
            notes=["Selected dataframe-aware plugin based on pandas/polars usage."],
            context=context,
        )


def builtin_plugins() -> List[object]:
    """Return the built-in generator plugin instances in priority order."""

    return [
        FastApiFlaskGenerator(),
        DjangoGenerator(),
        PydanticDataclassGenerator(),
        DataScienceGenerator(),
        VanillaPythonGenerator(),
    ]
