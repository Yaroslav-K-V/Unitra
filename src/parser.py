import ast
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FunctionInfo:
    name: str
    args: List[str]
    defaults: List[str]
    return_annotation: Optional[str]
    docstring: Optional[str]
    is_method: bool = False
    return_value: Optional[str] = None


def _extract_return_value(node: ast.FunctionDef) -> Optional[str]:
    for child in ast.walk(node):
        if isinstance(child, ast.Return) and child.value is not None:
            return ast.unparse(child.value)
    return None


def parse_functions(source_code: str) -> List[FunctionInfo]:
    tree = ast.parse(source_code)
    functions = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [arg.arg for arg in node.args.args]
            defaults = [ast.unparse(d) for d in node.args.defaults]
            return_annotation = ast.unparse(node.returns) if node.returns else None
            docstring = ast.get_docstring(node)
            is_method = "self" in args or "cls" in args
            return_value = _extract_return_value(node)

            functions.append(FunctionInfo(
                name=node.name,
                args=args,
                defaults=defaults,
                return_annotation=return_annotation,
                docstring=docstring,
                is_method=is_method,
                return_value=return_value,
            ))
    return functions
