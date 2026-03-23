import pytest
from src.parser import parse_functions, parse_classes, FunctionInfo


# ── parse_functions ───────────────────────────────────────────────────────────

def test_multiple_functions():
    code = "def a(): pass\ndef b(): pass\ndef c(): pass"
    funcs = parse_functions(code)
    assert [f.name for f in funcs] == ["a", "b", "c"]


def test_function_arg_annotations():
    code = "def add(x: int, y: int) -> int: return x + y"
    f = parse_functions(code)[0]
    assert f.arg_annotations == {"x": "int", "y": "int"}
    assert f.return_annotation == "int"


def test_function_docstring():
    code = 'def foo():\n    """A docstring."""\n    pass'
    f = parse_functions(code)[0]
    assert f.docstring == "A docstring."


def test_function_no_docstring():
    code = "def foo(): pass"
    f = parse_functions(code)[0]
    assert f.docstring is None


def test_function_return_value_extracted():
    code = "def answer(): return 42"
    f = parse_functions(code)[0]
    assert f.return_value == "42"


def test_function_no_return_value():
    code = "def nothing(): pass"
    f = parse_functions(code)[0]
    assert f.return_value is None


def test_async_function_parsed():
    code = "async def fetch(url: str): return url"
    funcs = parse_functions(code)
    assert len(funcs) == 1
    assert funcs[0].name == "fetch"


def test_function_inside_class_not_in_parse_functions():
    """parse_functions only captures top-level functions."""
    code = "class Foo:\n    def bar(self): pass"
    funcs = parse_functions(code)
    assert funcs == []


def test_syntax_error_raises():
    with pytest.raises(SyntaxError):
        parse_functions("def (broken:")


def test_multiple_defaults():
    code = "def f(a=1, b=2, c=3): pass"
    f = parse_functions(code)[0]
    assert f.defaults == ["1", "2", "3"]


def test_is_method_false_for_top_level():
    code = "def standalone(x): pass"
    f = parse_functions(code)[0]
    assert f.is_method is False


# ── parse_classes ─────────────────────────────────────────────────────────────

def test_class_no_init():
    """Class without __init__ has empty constructor_args."""
    code = "class Empty:\n    def run(self): pass"
    classes = parse_classes(code)
    assert classes[0].constructor_args == []
    assert classes[0].constructor_annotations == {}


def test_class_multiple_methods():
    code = (
        "class Calc:\n"
        "    def __init__(self): pass\n"
        "    def add(self): pass\n"
        "    def sub(self): pass\n"
        "    def _private(self): pass\n"
    )
    classes = parse_classes(code)
    method_names = [m.name for m in classes[0].methods]
    assert "add" in method_names
    assert "sub" in method_names
    assert "_private" not in method_names


def test_class_constructor_defaults():
    code = "class Foo:\n    def __init__(self, x=0): pass"
    cls = parse_classes(code)[0]
    assert cls.constructor_defaults == ["0"]


def test_multiple_classes():
    code = "class A:\n    pass\nclass B:\n    pass"
    classes = parse_classes(code)
    names = [c.name for c in classes]
    assert "A" in names and "B" in names


def test_nested_class_detected():
    """Nested classes are picked up by ast.walk."""
    code = "class Outer:\n    class Inner:\n        pass"
    classes = parse_classes(code)
    names = [c.name for c in classes]
    assert "Outer" in names
    assert "Inner" in names
