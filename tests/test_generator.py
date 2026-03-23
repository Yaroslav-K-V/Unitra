from src.parser import FunctionInfo, parse_classes
from src.generator import generate_test_module, generate_class_tests


def test_generates_basic_test():
    funcs = [FunctionInfo(name="add", args=["a", "b"], defaults=[],
                          return_annotation=None, docstring=None)]
    result = generate_test_module(funcs)
    assert "def test_add_basic():" in result
    assert "result = add(0, 0)" in result


def test_generates_return_assertion():
    funcs = [FunctionInfo(name="square", args=["x"], defaults=[],
                          return_annotation="int", docstring=None)]
    result = generate_test_module(funcs)
    assert "assert isinstance(result, int)" in result


def test_generates_defaults_test():
    funcs = [FunctionInfo(name="greet", args=["name"], defaults=["'World'"],
                          return_annotation=None, docstring=None)]
    result = generate_test_module(funcs)
    assert "def test_greet_defaults():" in result


def test_empty_functions():
    assert generate_test_module([]).strip() == "import pytest"


def test_generate_class_init_test():
    classes = parse_classes("class Foo:\n    def __init__(self, x: int): pass\n    def bar(self): return 1")
    output = generate_class_tests(classes)
    assert "test_foo_init" in output
    assert "Foo(0)" in output


def test_generate_class_method_test():
    classes = parse_classes("class Foo:\n    def __init__(self): pass\n    def greet(self): return 'hi'")
    output = generate_class_tests(classes)
    assert "test_foo_greet_basic" in output
    assert "obj.greet()" in output


def test_generate_class_tests_empty():
    assert generate_class_tests([]) == ""
