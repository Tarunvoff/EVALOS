from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


StrategyName = Literal["vanilla", "retry", "best_of_n", "evalos"]


class BenchmarkCase(BaseModel):
    id: str
    domain: str
    prompt: str
    optimize_for: list[str] = Field(default_factory=lambda: ["accuracy", "clarity"])
    retrieved_documents: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] | None = None
    agent_trace: dict[str, Any] | None = None
    claim_map: dict[str, str] | None = None
    claim_dependencies: list[dict[str, Any]] | None = None
    tags: list[str] = Field(default_factory=list)


class BenchmarkConfig(BaseModel):
    model: str
    provider: str = "litellm"
    temperature: float = 0.2
    max_tokens: int = 1024
    seed: int = 42
    retry_attempts: int = 2
    best_of_n: int = 3
    max_repairs: int = 2
    output_dir: str = "benchmarks/reports"
    run_id: str | None = None
    strictness: str = "balanced"


class BenchmarkMetrics(BaseModel):
    grounding_score: float = 0.0
    hallucination_rate: float = 0.0
    citation_precision: float = 0.0
    repair_efficiency: float = 0.0
    convergence_rate: float = 0.0
    token_efficiency: float = 0.0
    rollback_frequency: float = 0.0
    tool_correctness_score: float = 0.0
    quality_score: float = 0.0
    pass_rate: float = 0.0
    latency_ms: float = 0.0
    total_tokens: int = 0


class StrategyRun(BaseModel):
    strategy: StrategyName
    case_id: str
    domain: str
    prompt: str
    output_text: str
    initial_text: str | None = None
    evaluation_score: float = 0.0
    evaluation_passed: bool = False
    failed_criteria: list[str] = Field(default_factory=list)
    metrics: BenchmarkMetrics
    raw_trace: dict[str, Any] | None = None
    raw_response: dict[str, Any] | None = None
    retries: int = 0
    repairs: int = 0


class BenchmarkRun(BaseModel):
    config: BenchmarkConfig
    cases: list[BenchmarkCase]
    results: list[StrategyRun]
