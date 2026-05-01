"""Plugin system for Unitra test generators."""

from src.generator_plugins.base import (
    GeneratedTestSuite,
    GeneratorContext,
    GeneratorDescriptor,
    TestGeneratorPlugin,
)
from src.generator_plugins.registry import GeneratorRegistry

__all__ = [
    "GeneratedTestSuite",
    "GeneratorContext",
    "GeneratorDescriptor",
    "GeneratorRegistry",
    "TestGeneratorPlugin",
]
