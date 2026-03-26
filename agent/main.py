import ast
import os
import re
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from src.parser import parse_functions, parse_classes
from src.generator import generate_test_module

load_dotenv()

SYSTEM_PROMPT = """You are Unitra, an expert Python test engineer.
You will receive a parsed summary of functions and a base test scaffold.
Return an improved pytest file as plain Python (no markdown fencing).
Improvements to make:
- Add edge cases: None, empty strings, 0, -1, very large numbers
- Add pytest.raises tests for functions that can raise exceptions
- Replace placeholder assert values with realistic ones
- Add @pytest.mark.parametrize where functions have multiple simple cases
- Keep `import pytest` at the top
"""

_chain = None


def _get_chain():
    global _chain
    if _chain is not None:
        return _chain
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise EnvironmentError("API_KEY not found in .env")
    llm = ChatOpenAI(model="gpt-5.4-mini", temperature=0.2, api_key=api_key)
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{context}"),
    ])
    _chain = prompt | llm | StrOutputParser()
    return _chain


def run_agent(source_code: str) -> str:
    """Parse code locally, then improve tests with a single LLM call."""
    functions = parse_functions(source_code)
    classes = parse_classes(source_code)
    if not functions and not classes:
        return "# No functions or classes found."

    base_tests = generate_test_module(functions, classes)

    func_summary = "\n".join(
        f"- {f.name}({', '.join(f.args)})" +
        (f" -> {f.return_annotation}" if f.return_annotation else "") +
        (f"\n  docstring: {f.docstring[:120]}" if f.docstring else "")
        for f in functions
        if not f.is_method
    )
    class_summary = "\n".join(
        f"- class {c.name}({', '.join(c.base_classes) or ''}):"
        f" __init__({', '.join(c.constructor_args)})"
        f" | methods: {', '.join(m.name for m in c.methods)}"
        for c in classes
    )
    summary_parts = []
    if func_summary:
        summary_parts.append(f"Functions:\n{func_summary}")
    if class_summary:
        summary_parts.append(f"Classes:\n{class_summary}")
    context = "\n\n".join(summary_parts) + f"\n\nBase scaffold:\n{base_tests}"

    MAX_CONTEXT = 8000
        context = context[:MAX_CONTEXT] + "\n# ... (truncated)"

    output: str = _get_chain().invoke({"context": context})
    output = re.sub(r"^```(?:\w+)?\n(.*)\n```$", r"\1", output.strip(), flags=re.DOTALL)
    output = output.strip()
    try:
        ast.parse(output)
    except SyntaxError:
        return "# AI output was invalid Python — showing AST scaffold\n\n" + base_tests
    return output
