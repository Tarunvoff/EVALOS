from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Criterion(BaseModel):
    name: str
    description: str
    weight: float = 1.0
    threshold: float = 0.7


class CriterionResult(BaseModel):
    name: str
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    rationale: str | None = None


class EvaluationResult(BaseModel):
    results: list[CriterionResult]
    passed: bool
    failed: list[str]


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class Metrics(BaseModel):
    provider: str
    model: str
    latency_ms: float
    retries: int = 0
    repairs: int = 0
    usage: Usage = Field(default_factory=Usage)
    criteria_count: int = 0
    failed_criteria_count: int = 0


class RepairRecord(BaseModel):
    attempt: int
    failed_criteria: list[str]
    repaired_text: str


class GenerationResponse(BaseModel):
    text: str
    raw: Any | None = None
    evaluation: EvaluationResult | None = None
    repairs: list[RepairRecord] = Field(default_factory=list)
    metrics: Metrics


class StreamEvent(BaseModel):
    type: Literal["text", "metrics", "evaluation", "done"]
    data: Any
