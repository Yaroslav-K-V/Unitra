import pytest
from src.parser import FunctionInfo, ClassInfo
from src.generator import (
    _assert_for,
    _default_for,
    _generate_edge_test,
    generate_test_module,
    generate_class_tests,
)


# ── _assert_for ──────────────────────────────────────────────────────────────

def _func(return_annotation=None, return_value=None, args=None):
    return FunctionInfo(
        name="f", args=args or [], defaults=[],
        return_annotation=return_annotation,
        docstring=None,
        return_value=return_value,
    )


def test_assert_for_literal_return():
    """Literal return value → exact equality."""
    f = _func(return_value="42")
    assert _assert_for(f) == "assert result == 42"


def test_assert_for_string_literal_return():
    f = _func(return_value='"hello"')
    assert _assert_for(f) == 'assert result == "hello"'


def test_assert_for_bool_literal_return():
    f = _func(return_value="True")
    assert _assert_for(f) == "assert result == True"


def test_assert_for_int_annotation():
    """int annotation → isinstance check."""
    f = _func(return_annotation="int")
    assert _assert_for(f) == "assert isinstance(result, int)  # adjust expected value"


def test_assert_for_str_annotation():
    f = _func(return_annotation="str")
    assert _assert_for(f) == "assert isinstance(result, str)  # adjust expected value"


def test_assert_for_none_annotation():
    f = _func(return_annotation="None")
    assert _assert_for(f) == "assert result is None"


def test_assert_for_unknown_annotation():
    f = _func(return_annotation="MyClass")
    assert _assert_for(f) == "assert result is not None"


def test_assert_for_no_annotation_with_return():
    """Non-literal return expression, no annotation → generic not-None."""
    f = _func(return_value="a + b")
    assert _assert_for(f) == "assert result is not None  # add return annotation for a precise assertion"


def test_assert_for_no_annotation_no_return():
    f = _func()
    assert _assert_for(f) == "assert result is None"


# ── _default_for ─────────────────────────────────────────────────────────────

def test_default_for_int():
    assert _default_for("int") == "0"


def test_default_for_str():
    assert _default_for("str") == '"test"'


def test_default_for_bool():
    assert _default_for("bool") == "True"


def test_default_for_list():
    assert _default_for("list") == "[]"


def test_default_for_dict():
    assert _default_for("dict") == "{}"


def test_default_for_none():
    assert _default_for("None") == "None"


def test_default_for_unknown():
    assert _default_for("MyType") == "0"


def test_default_for_no_annotation():
    assert _default_for(None) == "0"


# ── _generate_edge_test ───────────────────────────────────────────────────────

def _annotated_func(name, args, annotations):
    return FunctionInfo(
        name=name, args=args, defaults=[],
        return_annotation=None, docstring=None,
        arg_annotations=annotations,
    )


def test_edge_test_single_int_arg():
    f = _annotated_func("double", ["x"], {"x": "int"})
    result = _generate_edge_test(f)
    assert result is not None
    assert "@pytest.mark.parametrize" in result
    assert '"x"' in result
    assert "0" in result and "-1" in result


def test_edge_test_single_str_arg():
    f = _annotated_func("process", ["s"], {"s": "str"})
    result = _generate_edge_test(f)
    assert result is not None
    assert "parametrize" in result


def test_edge_test_no_annotated_args():
    f = _annotated_func("foo", ["x", "y"], {})
    assert _generate_edge_test(f) is None


def test_edge_test_unannotated_type():
    """Annotation not in _EDGE_CASES → no edge test."""
    f = _annotated_func("foo", ["x"], {"x": "MyClass"})
    assert _generate_edge_test(f) is None


def test_edge_test_multiple_args():
    f = _annotated_func("add", ["a", "b"], {"a": "int", "b": "int"})
    result = _generate_edge_test(f)
    assert result is not None
    assert '"a, b"' in result


def test_edge_test_skips_self():
    f = FunctionInfo(
        name="method", args=["self", "x"], defaults=[],
        return_annotation=None, docstring=None,
        is_method=True,
        arg_annotations={"x": "int"},
    )
    result = _generate_edge_test(f)
    assert result is not None
    assert "self" not in result


# ── generate_test_module ──────────────────────────────────────────────────────

def test_module_always_has_pytest_import():
    assert generate_test_module([]).startswith("import pytest")


def test_module_no_defaults_test_when_not_all_args_defaulted():
    """Function with 2 args and 1 default must NOT get a defaults test."""
    funcs = [FunctionInfo(name="f", args=["a", "b"], defaults=["0"],
                          return_annotation=None, docstring=None)]
    result = generate_test_module(funcs)
    assert "def test_f_defaults():" not in result


def test_module_defaults_test_when_all_args_defaulted():
    funcs = [FunctionInfo(name="f", args=["a"], defaults=["0"],
                          return_annotation=None, docstring=None)]
    result = generate_test_module(funcs)
    assert "def test_f_defaults():" in result


def test_module_includes_edge_tests_for_annotated():
    funcs = [FunctionInfo(name="inc", args=["n"], defaults=[],
                          return_annotation="int", docstring=None,
                          arg_annotations={"n": "int"})]
    result = generate_test_module(funcs)
    assert "parametrize" in result


def test_module_no_edge_tests_without_annotations():
    funcs = [FunctionInfo(name="foo", args=["x"], defaults=[],
                          return_annotation=None, docstring=None)]
    result = generate_test_module(funcs)
    assert "parametrize" not in result


# ── generate_class_tests ─────────────────────────────────────────────────────

def test_class_tests_uses_type_defaults_for_ctor():
    """Constructor with int arg → Foo(0) in generated test."""
    cls = ClassInfo(
        name="Foo",
        constructor_args=["x"],
        constructor_annotations={"x": "int"},
        constructor_defaults=[],
        methods=[],
        base_classes=[],
    )
    result = generate_class_tests([cls])
    assert "Foo(0)" in result


def test_class_tests_method_skips_self():
    method = FunctionInfo(name="run", args=["self", "n"], defaults=[],
                          return_annotation=None, docstring=None,
                          is_method=True, arg_annotations={"n": "int"})
    cls = ClassInfo(
        name="Worker",
        constructor_args=[], constructor_annotations={},
        constructor_defaults=[], methods=[method], base_classes=[],
    )
    result = generate_class_tests([cls])
    assert "obj.run(0)" in result
    assert "self" not in result.split("obj.run(")[1].split(")")[0]
