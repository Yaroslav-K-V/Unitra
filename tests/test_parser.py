from src.parser import parse_functions

def test_simple_function():
    code = "def add(a, b): return a +b"
    functions = parse_functions(code)
    assert len(functions) == 1
    assert functions[0].name == "add"
    assert functions[0].args == ["a", "b"]

def test_function_with_default():
    code = "def greet(name='World'): pass"
    funcs = parse_functions(code)
    assert funcs[0].defaults == ["'World'"]


def test_method_detection():
    code = "class Foo:\n    def bar(self, x): pass"
    funcs = parse_functions(code)
    method = next(f for f in funcs if f.name == "bar")
    assert method.is_method is True


def test_return_annotation():
    code = "def square(x: int) -> int: return x * x"
    funcs = parse_functions(code)
    assert funcs[0].return_annotation == "int"


def test_empty_code():
    assert parse_functions("") == []