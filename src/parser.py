import ast
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class FunctionInfo:
    name: str
    args: List[str]
    defaults: List[str]
    return_annotation: Optional[str]
    docstring: Optional[str]
    is_method: bool = False
    is_async: bool = False
    return_value: Optional[str] = None
    arg_annotations: Dict[str, str] = field(default_factory=dict)


@dataclass
class ClassInfo:
    name: str
    constructor_args: List[str]
    constructor_annotations: Dict[str, str]
    constructor_defaults: List[str]
    methods: List[FunctionInfo]
    base_classes: List[str]


def _extract_return_value(node) -> Optional[str]:
    for child in ast.walk(node):
        if isinstance(child, ast.Return) and child.value is not None:
            return ast.unparse(child.value)
    return None


def _parse_function(node) -> FunctionInfo:
    args = [arg.arg for arg in node.args.args]
    defaults = [ast.unparse(d) for d in node.args.defaults]
    return_annotation = ast.unparse(node.returns) if node.returns else None
    docstring = ast.get_docstring(node)
    is_method = "self" in args or "cls" in args
    return_value = _extract_return_value(node)
    arg_annotations = {
        arg.arg: ast.unparse(arg.annotation)
        for arg in node.args.args
        if arg.annotation
    }
    return FunctionInfo(
        name=node.name,
        args=args,
        defaults=defaults,
        return_annotation=return_annotation,
        docstring=docstring,
        is_method=is_method,
        is_async=isinstance(node, ast.AsyncFunctionDef),
        return_value=return_value,
        arg_annotations=arg_annotations,
    )


def parse_functions(source_code: str) -> List[FunctionInfo]:
    tree = ast.parse(source_code)
    functions = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(_parse_function(node))
    return functions


def parse_classes(source_code: str) -> List[ClassInfo]:
    tree = ast.parse(source_code)
    classes = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        base_classes = [ast.unparse(b) for b in node.bases]
        constructor_args: List[str] = []
        constructor_annotations: Dict[str, str] = {}
        constructor_defaults: List[str] = []
        methods: List[FunctionInfo] = []
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if item.name == "__init__":
                for arg in item.args.args:
                    if arg.arg == "self":
                        continue
                    constructor_args.append(arg.arg)
                    if arg.annotation:
                        constructor_annotations[arg.arg] = ast.unparse(arg.annotation)
                constructor_defaults = [ast.unparse(d) for d in item.args.defaults]
            elif not item.name.startswith("_"):
                methods.append(_parse_function(item))
        classes.append(ClassInfo(
            name=node.name,
            constructor_args=constructor_args,
            constructor_annotations=constructor_annotations,
            constructor_defaults=constructor_defaults,
            methods=methods,
            base_classes=base_classes,
        ))
    return classes
