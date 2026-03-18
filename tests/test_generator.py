from src.parser import FunctionInfo
from src.generator import generate_test_module


def test_generates_basic_test():
    funcs = [FunctionInfo(name="add", args=["a", "b"], defaults=[],
                          return_annotation=None, docstring=None)]
    result = generate_test_module(funcs)
    assert "def test_add_basic():" in result
    assert "result = add(a, b)" in result


def test_generates_return_assertion():
    funcs = [FunctionInfo(name="square", args=["x"], defaults=[],
                          return_annotation="int", docstring=None)]
    result = generate_test_module(funcs)
    assert "assert result == 0" in result


def test_generates_defaults_test():
    funcs = [FunctionInfo(name="greet", args=["name"], defaults=["'World'"],
                          return_annotation=None, docstring=None)]
    result = generate_test_module(funcs)
    assert "def test_greet_defaults():" in result


def test_empty_functions():
    assert generate_test_module([]).strip() == "import pytest"
