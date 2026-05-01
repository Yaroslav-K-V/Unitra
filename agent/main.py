import ast
import json
import logging
import os
import re
import sys
from typing import Dict, Tuple

if __package__ in (None, ""):
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional in constrained test environments
    def load_dotenv(*args, **kwargs):
        return False

try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - optional in constrained test environments
    ChatPromptTemplate = None
    StrOutputParser = None
    ChatOpenAI = None

from src.parser import parse_functions, parse_classes
from src.generator import generate_test_module
from src.config import AI_MODEL, AI_MAX_CONTEXT, AI_PROVIDER, AI_TEMPERATURE

load_dotenv()

log = logging.getLogger(__name__)

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

REPAIR_SYSTEM_PROMPT = """You are Unitra's Python test repair assistant.
Return JSON only, with a top-level "suggestions" list.
Each suggestion must use one action:
- update_test_expectation
- remove_edge_case
- change_expected_exception
- suggest_source_change
- needs_human_decision
Do not rewrite files. Suggest focused, reviewable changes from the provided failure context.
"""

_chain_cache = {}


def _normalize_provider(provider: str = "") -> str:
    value = (provider or "").strip().lower()
    if value in {"ollama", "openai", "openrouter"}:
        return value
    return "ollama"


def _resolve_provider_config(
    provider: str = "",
    api_key: str = "",
    base_url: str = "",
) -> Tuple[str, str, str, Dict[str, str], str]:
    resolved_provider = _normalize_provider(provider or os.getenv("AI_PROVIDER") or AI_PROVIDER)
    if resolved_provider == "ollama":
        return (
            resolved_provider,
            api_key or os.getenv("OLLAMA_API_KEY") or "ollama",
            base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1/"),
            {},
            "OLLAMA_API_KEY",
        )
    if resolved_provider == "openrouter":
        resolved_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        if not resolved_key:
            raise EnvironmentError("OPENROUTER_API_KEY not found in .env")
        return (
            resolved_provider,
            resolved_key,
            base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            {"X-Title": os.getenv("OPENROUTER_APP_NAME", "Unitra")},
            "OPENROUTER_API_KEY",
        )

    resolved_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY", "")
    if not resolved_key:
        raise EnvironmentError("OPENAI_API_KEY not found in .env")
    return (
        resolved_provider,
        resolved_key,
        base_url or os.getenv("OPENAI_BASE_URL", ""),
        {},
        "OPENAI_API_KEY",
    )


def _get_chain(
    provider: str = "",
    model: str = "",
    temperature: float = None,
    api_key: str = "",
    base_url: str = "",
    system_prompt: str = SYSTEM_PROMPT,
):
    if ChatOpenAI is None or ChatPromptTemplate is None or StrOutputParser is None:
        raise EnvironmentError("langchain_openai is not installed")
    resolved_provider, resolved_key, resolved_base_url, default_headers, _ = _resolve_provider_config(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
    )
    effective_model = model or os.getenv("AI_MODEL") or os.getenv("OLLAMA_MODEL") or os.getenv("OPENAI_MODEL") or AI_MODEL
    effective_temperature = AI_TEMPERATURE if temperature is None else temperature
    cache_key = (
        resolved_provider,
        resolved_key,
        effective_model,
        effective_temperature,
        resolved_base_url,
        tuple(sorted(default_headers.items())),
        system_prompt,
    )
    if cache_key in _chain_cache:
        return _chain_cache[cache_key]
    llm_kwargs = {
        "model": effective_model,
        "temperature": effective_temperature,
        "api_key": resolved_key,
    }
    if resolved_base_url:
        llm_kwargs["base_url"] = resolved_base_url
    if default_headers:
        llm_kwargs["default_headers"] = default_headers
    llm = ChatOpenAI(**llm_kwargs)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{context}"),
    ])
    chain = prompt | llm | StrOutputParser()
    _chain_cache[cache_key] = chain
    return chain


def run_agent(
    source_code: str,
    provider: str = "",
    model: str = "",
    temperature: float = None,
    max_context: int = None,
    base_url: str = "",
) -> str:
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

    effective_max_context = AI_MAX_CONTEXT if max_context is None else max_context
    if len(context) > effective_max_context:
        context = context[:effective_max_context] + "\n# ... (truncated)"

    output: str = _get_chain(
        provider=provider,
        model=model,
        temperature=temperature,
        base_url=base_url,
    ).invoke({"context": context})
    output = re.sub(r"^```(?:\w+)?\n(.*)\n```$", r"\1", output.strip(), flags=re.DOTALL)
    output = output.strip()
    try:
        ast.parse(output)
    except SyntaxError:
        return "# AI output was invalid Python — showing AST scaffold\n\n" + base_tests
    return output


def run_repair_agent(
    context: dict,
    provider: str = "",
    model: str = "",
    temperature: float = None,
    max_context: int = None,
    base_url: str = "",
) -> str:
    payload = json.dumps(context, ensure_ascii=False, indent=2)
    effective_max_context = AI_MAX_CONTEXT if max_context is None else max_context
    if len(payload) > effective_max_context:
        payload = payload[:effective_max_context] + "\n# ... (truncated)"
    output: str = _get_chain(
        provider=provider,
        model=model,
        temperature=temperature,
        base_url=base_url,
        system_prompt=REPAIR_SYSTEM_PROMPT,
    ).invoke({"context": payload})
    return re.sub(r"^```(?:json)?\n(.*)\n```$", r"\1", output.strip(), flags=re.DOTALL).strip()


def stream_agent(
    source_code: str,
    provider: str = "",
    model: str = "",
    temperature: float = None,
    max_context: int = None,
    base_url: str = "",
):
    """Like run_agent but yields string tokens for SSE streaming."""
    functions = parse_functions(source_code)
    classes = parse_classes(source_code)
    if not functions and not classes:
        yield "# No functions or classes found."
        return

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

    effective_max_context = AI_MAX_CONTEXT if max_context is None else max_context
    if len(context) > effective_max_context:
        context = context[:effective_max_context] + "\n# ... (truncated)"

    for chunk in _get_chain(
        provider=provider,
        model=model,
        temperature=temperature,
        base_url=base_url,
    ).stream({"context": context}):
        if isinstance(chunk, str):
            yield chunk


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    if argv:
        source_path = argv[0]
        with open(source_path, encoding="utf-8") as handle:
            source_code = handle.read()
    else:
        source_code = sys.stdin.read()

    print(run_agent(source_code))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
