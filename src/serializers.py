from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Iterable, List


MODEL_PRICING_PER_MILLION = {
    "gpt-5.4": {"input": 2.50, "output": 15.00},
    "gpt-5.4-mini": {"input": 0.750, "output": 4.500},
    "gpt-5.4-nano": {"input": 0.20, "output": 1.25},
}


def to_dict(value: Any):
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return value


def serialize_workspace_status(status) -> Dict[str, Any]:
    return {
        "config": to_dict(status.config),
        "jobs": status.jobs,
        "agent_profiles": status.agent_profiles,
        "recent_runs": status.recent_runs,
    }


def serialize_agent_profile(profile) -> Dict[str, Any]:
    return to_dict(profile)


def serialize_job_definition(job) -> Dict[str, Any]:
    return to_dict(job)


def summarize_fallback_contexts(contexts: Iterable[dict], model: str = "") -> Dict[str, Any]:
    contexts = list(contexts or [])
    total_input_tokens = sum(int(item.get("estimated_input_tokens", 0)) for item in contexts)
    total_output_tokens = sum(int(item.get("expected_output_tokens", 0)) for item in contexts)
    summary = {
        "count": len(contexts),
        "estimated_input_tokens": total_input_tokens,
        "expected_output_tokens": total_output_tokens,
        "model": model or "",
    }
    rates = MODEL_PRICING_PER_MILLION.get(model or "")
    if rates:
        estimated_cost = (
            total_input_tokens / 1_000_000 * rates["input"]
            + total_output_tokens / 1_000_000 * rates["output"]
        )
        summary["estimated_cost_usd"] = round(estimated_cost, 6)
    else:
        summary["estimated_cost_usd"] = None
    return summary


def serialize_job_result(result, model: str = "") -> Dict[str, Any]:
    return {
        "job_name": result.job_name,
        "mode": result.mode,
        "target_scope": result.target_scope,
        "planned_files": [to_dict(item) for item in result.planned_files],
        "written_files": [to_dict(item) for item in result.written_files],
        "run": {
            "output": result.run_output,
            "returncode": result.run_returncode,
            "coverage": result.run_coverage,
        },
        "history_id": result.history_id,
        "llm_fallback_contexts": result.llm_fallback_contexts,
        "fallback_context_summary": summarize_fallback_contexts(result.llm_fallback_contexts, model=model),
    }


def serialize_run_history_record(run_id: str, payload: Dict[str, Any], model: str = "") -> Dict[str, Any]:
    contexts = payload.get("llm_fallback_contexts", [])
    return {
        "history_id": run_id,
        "job_name": payload.get("job_name", ""),
        "mode": payload.get("mode", ""),
        "target_scope": payload.get("target_scope", ""),
        "planned_files": payload.get("planned_files", []),
        "written_files": payload.get("written_files", []),
        "run": {
            "output": payload.get("run_output", ""),
            "returncode": payload.get("run_returncode"),
            "coverage": payload.get("run_coverage"),
        },
        "llm_fallback_contexts": contexts,
        "fallback_context_summary": summarize_fallback_contexts(contexts, model=model),
    }
