from typing import List
from src.parser import FunctionInfo

# Maps return annotation to a sensible assert value
_TYPE_DEFAULTS = {
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
        return f"assert result == {func.return_value}"
    if func.return_annotation in _TYPE_DEFAULTS:
        default = _TYPE_DEFAULTS[func.return_annotation]
        return f"assert result == {default}  # adjust expected value"
    if func.return_annotation:
        return "assert result is not None"
    return "assert result is None"


def generate_test_module(functions: List[FunctionInfo]) -> str:
    lines = ["import pytest", ""]

    for func in functions:
        args_call = ", ".join(func.args[1:] if func.is_method else func.args)

        lines.append(f"def test_{func.name}_basic():")
        lines.append(f"    result = {func.name}({args_call})")
        lines.append(f"    {_assert_for(func)}")
        lines.append("")

        if func.defaults:
            lines.append(f"def test_{func.name}_defaults():")
            lines.append(f"    result = {func.name}()")
            lines.append(f"    {_assert_for(func)}")
            lines.append("")

    return "\n".join(lines)
