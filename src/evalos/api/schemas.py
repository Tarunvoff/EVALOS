from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    prompt: str
    optimize_for: list[str] = Field(default_factory=lambda: ["accuracy", "clarity"])
    domain: str | None = None
    retrieved_documents: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] | None = None
    agent_trace: dict[str, Any] | None = None
    claim_map: dict[str, str] | None = None
    claim_dependencies: list[dict[str, Any]] | None = None
    stream: bool = False
    model: str | None = None
    provider: str | None = None


class TraceResponse(BaseModel):
    trace: dict[str, Any]


class BenchmarkRunRequest(BaseModel):
    model: str | None = None
    provider: str | None = None
    strategies: list[str] = Field(default_factory=lambda: ["vanilla", "retry", "best_of_n", "evalos"])
    output_dir: str = "benchmarks/reports"


class BenchmarkRunResponse(BaseModel):
    output_dir: str
    run_id: str
    result_path: str


class DashboardMetricsResponse(BaseModel):
    benchmark_summary: dict[str, Any] | None = None
    last_trace: dict[str, Any] | None = None


class AgentEvalRequest(BaseModel):
    agent_trace: dict[str, Any]


class AgentEvalResponse(BaseModel):
    tool_correctness_score: float
    planning_score: float
    execution_alignment_score: float
    hallucinated_tool_usage_rate: float
    reasoning_consistency_score: float
    hallucinated_tool_usage: bool
    hallucinated_tool_details: list[str]
