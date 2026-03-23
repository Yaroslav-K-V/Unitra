from src.parser import parse_functions, parse_classes

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
    classes = parse_classes(code)
    assert len(classes[0].methods) == 1
    assert classes[0].methods[0].is_method is True


def test_return_annotation():
    code = "def square(x: int) -> int: return x * x"
    funcs = parse_functions(code)
    assert funcs[0].return_annotation == "int"


def test_empty_code():
    assert parse_functions("") == []


def test_parse_class_basic():
    code = "class Foo:\n    def __init__(self, x: int): pass\n    def bar(self): return 1"
    classes = parse_classes(code)
    assert len(classes) == 1
    assert classes[0].name == "Foo"
    assert classes[0].constructor_args == ["x"]
    assert classes[0].constructor_annotations == {"x": "int"}
    assert len(classes[0].methods) == 1


def test_parse_class_excludes_dunder_methods():
    code = "class Foo:\n    def __init__(self): pass\n    def __str__(self): return ''\n    def public(self): pass"
    classes = parse_classes(code)
    assert len(classes[0].methods) == 1
    assert classes[0].methods[0].name == "public"


def test_parse_class_base_classes():
    code = "class Bar(Base):\n    def __init__(self): pass"
    classes = parse_classes(code)
    assert classes[0].base_classes == ["Base"]


def test_parse_class_empty():
    assert parse_classes("") == []