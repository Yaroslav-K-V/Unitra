from src.application.services import GenerationService
from src.application.workspace_models import WorkspaceConfig
from src.generator_plugins import GeneratorRegistry
from src.infrastructure.workspace_repository import WorkspaceRepository


class StubLoader:
    def __init__(self, source_code):
        self.source_code = source_code

    def load_paths(self, paths):
        return type("Bundle", (), {"source_code": self.source_code, "files_scanned": len(paths)})()

    def load_folder(self, folder, include_tests=False, definitions_only_mode=False):
        return type("Bundle", (), {"source_code": self.source_code, "files_scanned": 1})()


def test_registry_selects_pydantic_plugin():
    source_code = (
        "from pydantic import BaseModel\n\n"
        "class User(BaseModel):\n"
        "    id: int\n"
        "    name: str\n"
    )

    result = GenerationService(source_loader=StubLoader(source_code)).generate_from_code(source_code)

    assert result.generator_name == "schema-models"
    assert result.project_type == "pydantic-dataclasses"
    assert "model_validate" in result.test_code


def test_registry_selects_data_science_plugin():
    source_code = (
        "import pandas as pd\n\n"
        "def transform(frame: pd.DataFrame) -> pd.DataFrame:\n"
        "    return frame.assign(total=frame['value'] * 2)\n"
    )

    result = GenerationService(source_loader=StubLoader(source_code)).generate_from_code(source_code)

    assert result.generator_name == "dataframe-pipelines"
    assert "pd.DataFrame" in result.test_code
    assert "transform(" in result.test_code


def test_registry_uses_custom_generator_from_workspace_registration():
    source_code = "CUSTOM_PLUGIN_MARKER = True\n"
    registry = GeneratorRegistry()

    generated = registry.generate(
        source_code,
        custom_generators=["tests.custom_generator_plugin:CustomSmokeGenerator"],
    )

    assert generated.generator_name == "custom-smoke"
    assert "test_custom_plugin_selected" in generated.test_code


def test_workspace_repository_persists_custom_generators(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    repository = WorkspaceRepository(str(repo_root))
    config = repository.init_workspace(WorkspaceConfig(root_path=str(repo_root)))
    repository.save_config(
        WorkspaceConfig(
            root_path=config.root_path,
            source_include=config.source_include,
            source_exclude=config.source_exclude,
            test_root=config.test_root,
            test_path_strategy=config.test_path_strategy,
            naming_strategy=config.naming_strategy,
            preferred_pytest_args=config.preferred_pytest_args,
            selected_agent_profile=config.selected_agent_profile,
            ai_policy=config.ai_policy,
            ai_backend=config.ai_backend,
            custom_generators=["tests.custom_generator_plugin:CustomSmokeGenerator"],
        )
    )

    loaded = repository.load_config()

    assert loaded.custom_generators == ["tests.custom_generator_plugin:CustomSmokeGenerator"]
