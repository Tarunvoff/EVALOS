from __future__ import annotations

from typing import Any

from evalos.observability.tracer import Trace
from evalos.types import EvaluationResult, GenerationResponse


def snapshot_trace(trace: Trace) -> dict[str, Any]:
    base = trace.steps[0].timestamp if trace.steps else trace.start_ts
    steps = []
    for index, step in enumerate(trace.steps, start=1):
        steps.append(
            {
                "index": index,
                "name": step.name,
                "timestamp_ms": round((step.timestamp - base) * 1000.0, 3),
                "duration_ms": step.duration_ms,
                "data": step.data,
                "annotations": step.annotations,
            }
        )
    payload = trace.model_dump(mode="json")
    payload["start_ts"] = 0.0
    payload["steps"] = steps
    payload["schema_version"] = trace.schema_version
    payload["criteria"] = _sorted_list(payload.get("criteria", []), key="name")
    payload["schema_validation"] = _sorted_list(payload.get("schema_validation", []), key="source")
    payload["claim_canonicalization"] = _sorted_list(
        payload.get("claim_canonicalization", []),
        key="internal_claim_index",
    )
    payload["claim_dependencies"] = _sorted_list(payload.get("claim_dependencies", []), key="claim_id")
    payload["repairs"] = _sorted_list(payload.get("repairs", []), key="attempt")
    payload["rollback_events"] = _normalize_rollbacks(payload.get("rollback_events", []))
    payload["retrieval_inputs"] = _sorted_list(payload.get("retrieval_inputs", []), key="id")
    payload["agent_trace"] = _normalize_agent_trace(payload.get("agent_trace", {}))
    return payload


def _sorted_list(items: list[dict[str, Any]], *, key: str) -> list[dict[str, Any]]:
    if not items:
        return []
    return sorted(items, key=lambda item: str(item.get(key, "")))


def _normalize_rollbacks(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for event in sorted(events, key=lambda item: int(item.get("attempt", 0))):
        item = dict(event)
        item["timestamp"] = 0.0
        normalized.append(item)
    return normalized


def _normalize_agent_trace(trace_payload: dict[str, Any]) -> dict[str, Any]:
    if not trace_payload:
        return {}
    normalized = dict(trace_payload)
    plan = trace_payload.get("plan")
    if isinstance(plan, list):
        normalized["plan"] = sorted(plan, key=lambda item: int(item.get("step_id", 0)))
    tool_calls = trace_payload.get("tool_calls")
    if isinstance(tool_calls, list):
        normalized["tool_calls"] = sorted(tool_calls, key=lambda item: str(item.get("call_id", "")))
    return normalized


def snapshot_evaluation(evaluation: EvaluationResult) -> dict[str, Any]:
    payload = evaluation.model_dump(mode="json")
    payload["results"] = _sorted_list(payload.get("results", []), key="name")
    payload["failed"] = sorted(payload.get("failed", []))
    payload["sections"] = _sorted_list(payload.get("sections", []), key="id")
    return payload


def snapshot_generation_response(response: GenerationResponse) -> dict[str, Any]:
    payload = response.model_dump(mode="json")
    if response.evaluation:
        payload["evaluation"] = snapshot_evaluation(response.evaluation)
    payload["repairs"] = _sorted_list(payload.get("repairs", []), key="attempt")
    if response.trace:
        payload["trace"] = snapshot_trace(response.trace)
    return payload
