from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from evalos.rag.schema import SCHEMA_VERSION, Provenance


class PlanStep(BaseModel):
    schema_version: str = SCHEMA_VERSION
    step_id: int
    goal: str
    tool: str
    status: str
    provenance: Provenance | None = None


class ToolCall(BaseModel):
    schema_version: str = SCHEMA_VERSION
    call_id: str
    tool_name: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    status: str
    start_ts: float | None = None
    end_ts: float | None = None
    provenance: Provenance | None = None


class AgentError(BaseModel):
    type: str
    detail: str


class AgentTrace(BaseModel):
    schema_version: str = SCHEMA_VERSION
    plan: list[PlanStep] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    reasoning_chain: list[str] = Field(default_factory=list)
    tools_allowed: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    errors: list[AgentError] = Field(default_factory=list)
    provenance: Provenance | None = None


class AgentEvalResult(BaseModel):
    tool_correctness_score: float
    planning_score: float
    execution_alignment_score: float
    hallucinated_tool_usage_rate: float
    reasoning_consistency_score: float
    hallucinated_tool_usage: bool
    hallucinated_tool_details: list[str] = Field(default_factory=list)
    tool_call_count: int = 0


class AgentReliabilityEvaluator:
    def evaluate(self, *, trace: AgentTrace) -> AgentEvalResult:
        tool_calls = trace.tool_calls
        allowed = trace.tools_allowed
        tool_names = [call.tool_name for call in tool_calls]
        tools_used = trace.tools_used or tool_names
        plan_tools = [step.tool for step in trace.plan if step.tool]

        hallucinated = [name for name in tools_used if allowed and name not in allowed]
        tool_correctness = _tool_correctness(tools_used, allowed)
        planning_score = _planning_score(tool_names, trace.plan)
        execution_alignment = _execution_alignment_score(tool_calls, trace.plan)
        hallucinated_rate = len(hallucinated) / max(1, len(tools_used))
        reasoning_consistency = _reasoning_consistency(trace.reasoning_chain, tool_calls)

        return AgentEvalResult(
            tool_correctness_score=tool_correctness,
            planning_score=planning_score,
            execution_alignment_score=execution_alignment,
            hallucinated_tool_usage_rate=hallucinated_rate,
            reasoning_consistency_score=reasoning_consistency,
            hallucinated_tool_usage=len(hallucinated) > 0,
            hallucinated_tool_details=hallucinated,
            tool_call_count=len(tool_calls),
        )


def _tool_correctness(tool_names: list[str], allowed: list[str]) -> float:
    if not tool_names and not allowed:
        return 1.0
    if allowed and not tool_names:
        return 0.0
    if not allowed:
        return 1.0
    correct = sum(1 for name in tool_names if name in allowed)
    return correct / max(1, len(tool_names))


def _planning_score(tool_names: list[str], plan: list[PlanStep]) -> float:
    if not tool_names:
        return 1.0
    if not plan:
        return 0.5
    plan_index = {
        step.tool: idx
        for idx, step in enumerate(plan)
        if step.tool.lower().strip() != "reasoning"
    }
    in_order = 0
    last = -1
    for name in tool_names:
        idx = plan_index.get(name, None)
        if idx is None:
            continue
        if idx >= last:
            in_order += 1
            last = idx
    return in_order / max(1, len(tool_names))


def _execution_alignment_score(tool_calls: list[ToolCall], plan: list[PlanStep]) -> float:
    if not tool_calls and not plan:
        return 1.0
    if not tool_calls:
        return 0.0
    plan_tools = {step.tool for step in plan if step.tool}
    aligned = sum(1 for call in tool_calls if call.tool_name in plan_tools)
    return aligned / max(1, len(tool_calls))


def _reasoning_consistency(reasoning_chain: list[str], tool_calls: list[ToolCall]) -> float:
    if not reasoning_chain:
        return 0.5
    if not tool_calls:
        return 1.0
    reasoning_text = " ".join(reasoning_chain).lower()
    hits = 0
    for call in tool_calls:
        for key in call.output.keys():
            if key and key.lower() in reasoning_text:
                hits += 1
                break
    return hits / max(1, len(tool_calls))
