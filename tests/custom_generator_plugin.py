from src.generator_plugins.base import GeneratedTestSuite


class CustomSmokeGenerator:
    name = "custom-smoke"
    project_type = "custom"
    priority = 95
    source = "workspace"
    factory = "tests.custom_generator_plugin:CustomSmokeGenerator"

    def score(self, context):
        return 95 if "CUSTOM_PLUGIN_MARKER" in context.source_code else 0

    def generate(self, context):
        return GeneratedTestSuite(
            test_code="import pytest\n\n\ndef test_custom_plugin_selected():\n    assert True\n",
            generator_name=self.name,
            project_type=self.project_type,
            generator_source=self.source,
            context=context,
        )
