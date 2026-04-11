import ast
import logging

log = logging.getLogger(__name__)

_DEF_TYPES = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Import,
    ast.ImportFrom,
)


def definitions_only(source: str) -> str:
    """Return class/function defs and imports, skipping module-level statements."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        log.debug("Syntax error stripping module code: %s", exc)
        return source
    lines = source.splitlines()
    parts = []
    for node in tree.body:
        if isinstance(node, _DEF_TYPES):
            parts.append("\n".join(lines[node.lineno - 1:node.end_lineno]))
    return "\n\n".join(parts)


def count_tests(test_code: str) -> int:
    return test_code.count("\ndef test_")
