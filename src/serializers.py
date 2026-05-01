from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Iterable, List

from src.application.ai_policy import AiPolicy, WorkspaceAiPolicy
from src.application.guided_services import guided_run_from_dict


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


def serialize_ai_policy(policy: Any) -> Dict[str, Any]:
    if isinstance(policy, AiPolicy):
        return policy.to_dict()
    if isinstance(policy, WorkspaceAiPolicy):
        return policy.to_dict()
    return dict(policy or {})


def serialize_agent_profile(
    profile,
    effective_ai_policy: Any = None,
    global_ai_policy: Any = None,
    workspace_ai_policy: Any = None,
    ai_policy_source: str = "",
) -> Dict[str, Any]:
    payload = to_dict(profile)
    if effective_ai_policy is not None:
        payload["effective_ai_policy"] = serialize_ai_policy(effective_ai_policy)
    if global_ai_policy is not None:
        payload["global_ai_policy"] = serialize_ai_policy(global_ai_policy)
    if workspace_ai_policy is not None:
        payload["workspace_ai_policy"] = serialize_ai_policy(workspace_ai_policy)
    if ai_policy_source:
        payload["ai_policy_source"] = ai_policy_source
    return payload


def serialize_job_definition(job) -> Dict[str, Any]:
    return to_dict(job)


def with_ai_metadata(item: Any) -> Dict[str, Any]:
    payload = dict(to_dict(item) or {})
    if "ai_attempted" not in payload:
        payload["ai_attempted"] = None
    if "ai_used" not in payload:
        payload["ai_used"] = None
    payload["ai_status"] = payload.get("ai_status") or "unknown"
    payload["ai_reason"] = payload.get("ai_reason") or ""
    payload["generator_name"] = payload.get("generator_name") or "ast-basic"
    payload["project_type"] = payload.get("project_type") or "vanilla-python"
    payload["generator_source"] = payload.get("generator_source") or "builtin"
    payload["quality"] = payload.get("quality") or "basic"
    payload["duration_ms"] = float(payload.get("duration_ms", 0.0) or 0.0)
    payload["cache_hit"] = bool(payload.get("cache_hit", False))
    return payload


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
    contexts = result.llm_fallback_contexts
    return {
        "kind": "job_run",
        "job_name": result.job_name,
        "mode": result.mode,
        "target_scope": result.target_scope,
        "planned_files": [with_ai_metadata(item) for item in result.planned_files],
        "written_files": [with_ai_metadata(item) for item in result.written_files],
        "run": {
            "output": result.run_output,
            "returncode": result.run_returncode,
            "coverage": result.run_coverage,
        },
        "history_id": result.history_id,
        "llm_fallback_contexts": contexts,
        "fallback_context_summary": summarize_fallback_contexts(contexts, model=model),
        "failure_categories": getattr(result, "failure_categories", []),
        "ai_repair_suggestions": getattr(result, "ai_repair_suggestions", []),
        "ai_repair_requested": getattr(result, "ai_repair_requested", False),
        "ai_repair_used": getattr(result, "ai_repair_used", False),
        "ai_repair_status": getattr(result, "ai_repair_status", "skipped"),
        "ai_repair_reason": getattr(result, "ai_repair_reason", ""),
        "generated_tests_count": getattr(result, "generated_tests_count", len(result.planned_files)),
        "total_duration_ms": getattr(result, "total_duration_ms", 0.0),
        "cache_hits": getattr(result, "cache_hits", 0),
        "generator_breakdown": getattr(result, "generator_breakdown", []),
    }


def serialize_run_history_record(run_id: str, payload: Dict[str, Any], model: str = "", run_loader=None) -> Dict[str, Any]:
    if (payload or {}).get("kind") == "guided_run" or "steps" in (payload or {}) or "timeline" in (payload or {}):
        return serialize_guided_run_record(run_id, payload, model=model, run_loader=run_loader)
    return serialize_job_history_record(run_id, payload, model=model)


def serialize_job_history_record(run_id: str, payload: Dict[str, Any], model: str = "") -> Dict[str, Any]:
    contexts = payload.get("llm_fallback_contexts", [])
    return {
        "kind": "job_run",
        "history_id": run_id,
        "job_name": payload.get("job_name", ""),
        "mode": payload.get("mode", ""),
        "target_scope": payload.get("target_scope", ""),
        "planned_files": [with_ai_metadata(item) for item in payload.get("planned_files", [])],
        "written_files": [with_ai_metadata(item) for item in payload.get("written_files", [])],
        "run": {
            "output": payload.get("run_output", ""),
            "returncode": payload.get("run_returncode"),
            "coverage": payload.get("run_coverage"),
        },
        "llm_fallback_contexts": contexts,
        "fallback_context_summary": summarize_fallback_contexts(contexts, model=model),
        "failure_categories": payload.get("failure_categories", []),
        "ai_repair_suggestions": payload.get("ai_repair_suggestions", []),
        "ai_repair_requested": bool(payload.get("ai_repair_requested", False)),
        "ai_repair_used": bool(payload.get("ai_repair_used", False)),
        "ai_repair_status": payload.get("ai_repair_status", "skipped"),
        "ai_repair_reason": payload.get("ai_repair_reason", ""),
        "generated_tests_count": int(payload.get("generated_tests_count", len(payload.get("planned_files", [])))),
        "total_duration_ms": float(payload.get("total_duration_ms", 0.0) or 0.0),
        "cache_hits": int(payload.get("cache_hits", 0) or 0),
        "generator_breakdown": payload.get("generator_breakdown", []),
    }


def serialize_guided_run_record(
    run_id: str,
    payload: Dict[str, Any],
    model: str = "",
    run_loader=None,
) -> Dict[str, Any]:
    guided = guided_run_from_dict({"history_id": run_id, **(payload or {})})
    latest_child_run = None
    if callable(run_loader) and guided.latest_child_run_id:
        try:
            raw_child = run_loader(guided.latest_child_run_id)
        except Exception:
            raw_child = None
        if isinstance(raw_child, dict):
            latest_child_run = serialize_run_history_record(guided.latest_child_run_id, raw_child, model=model)
    steps = [
        {
            **to_dict(step),
            "use_ai_generation": bool(step.use_ai_generation),
            "use_ai_repair": bool(step.use_ai_repair),
        }
        for step in guided.steps
    ]
    timeline = [to_dict(event) for event in guided.timeline]
    return {
        "kind": "guided_run",
        "history_id": guided.history_id or run_id,
        "workflow_source": guided.workflow_source,
        "workflow_name": guided.workflow_name,
        "status": guided.status,
        "target_scope": guided.target_scope,
        "target_value": guided.target_value,
        "current_step_id": guided.current_step_id,
        "awaiting_step_id": guided.awaiting_step_id,
        "child_run_ids": list(guided.child_run_ids),
        "steps": steps,
        "timeline": timeline,
        "latest_child_run_id": guided.latest_child_run_id,
        "latest_child_run": latest_child_run,
        "next_recommendation": _guided_next_recommendation(guided),
    }


def _guided_next_recommendation(guided) -> str:
    if guided.awaiting_step_id:
        for step in guided.steps:
            if step.id == guided.awaiting_step_id:
                return f"Review and approve '{step.title}'."
    if guided.status == "completed":
        return "Guided run complete. Review the timeline and latest child run."
    if guided.status == "cancelled":
        return "Guided run was cancelled."
    if guided.status == "failed":
        return "The latest guided step failed. Inspect the child run and repair options."
    return "Follow the timeline and continue with the next pending step."
