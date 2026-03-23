import ast
from typing import List, Optional
from src.parser import FunctionInfo, ClassInfo

# Maps type annotation to a sensible default value
_TYPE_DEFAULTS = {
    "int": "0",
    "float": "0.0",
    "str": '"test"',
    "bool": "True",
    "list": "[]",
    "dict": "{}",
    "None": "None",
}

# Maps return annotation to a sensible assert value
_RETURN_DEFAULTS = {
    "int": "0",
    "float": "0.0",
    "str": '""',
    "bool": "False",
    "list": "[]",
    "dict": "{}",
    "None": "None",
}


def _assert_for(func: FunctionInfo) -> str:
    if func.return_value is not None:
        try:
            ast.literal_eval(func.return_value)  # safe for pure literals: 42, "ok", True
            return f"assert result == {func.return_value}"
        except (ValueError, SyntaxError):
            pass  # expression contains variables — fall through to annotation default
    if func.return_annotation in _RETURN_DEFAULTS:
        default = _RETURN_DEFAULTS[func.return_annotation]
        return f"assert result == {default}  # adjust expected value"
    if func.return_annotation:
        return "assert result is not None"
    # If function has a return statement but no annotation — it returns *something*
    if func.return_value is not None:
        return "assert result is not None  # add return annotation for a precise assertion"
    return "assert result is None"


def _default_for(annotation: Optional[str]) -> str:
    if annotation and annotation in _TYPE_DEFAULTS:
        return _TYPE_DEFAULTS[annotation]
    return "0"  # safe fallback for unannotated args — avoids TypeError in numeric ops


def generate_class_tests(classes: List[ClassInfo]) -> str:
    if not classes:
        return ""
    lines: List[str] = []
    for cls in classes:
        ctor_vals = [_default_for(cls.constructor_annotations.get(a)) for a in cls.constructor_args]
        ctor_call = f"{cls.name}({', '.join(ctor_vals)})"

        lines.append(f"\n# --- {cls.name} ---\n")
        lines.append(f"def test_{cls.name.lower()}_init():")
        lines.append(f"    obj = {ctor_call}")
        lines.append( "    assert obj is not None")
        lines.append("")

        for method in cls.methods:
            call_args = method.args[1:]  # skip self
            arg_vals = ["None"] * len(call_args)
            method_call = f"obj.{method.name}({', '.join(arg_vals)})"

            lines.append(f"def test_{cls.name.lower()}_{method.name}_basic():")
            lines.append(f"    obj = {ctor_call}")
            lines.append(f"    result = {method_call}")
            lines.append(f"    {_assert_for(method)}")
            lines.append("")

    return "\n".join(lines)


def generate_test_module(functions: List[FunctionInfo], classes: Optional[List[ClassInfo]] = None) -> str:
    lines = ["import pytest", ""]

    for func in functions:
        raw_args = func.args[1:] if func.is_method else func.args
        args_call = ", ".join(_default_for(func.arg_annotations.get(a)) for a in raw_args)

        lines.append(f"def test_{func.name}_basic():")
        lines.append(f"    result = {func.name}({args_call})")
        lines.append(f"    {_assert_for(func)}")
        lines.append("")

        if func.defaults:
            lines.append(f"def test_{func.name}_defaults():")
            lines.append(f"    result = {func.name}()")
            lines.append(f"    {_assert_for(func)}")
            lines.append("")

    if classes:
        lines.append(generate_class_tests(classes))

    return "\n".join(lines)
