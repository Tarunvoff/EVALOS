from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Severity = Literal["low", "medium", "high", "critical"]
QualityProfile = Literal[
    "general",
    "research",
    "coding",
    "enterprise",
    "educational",
    "concise",
]


class Section(BaseModel):
    id: str
    text: str
    start: int
    end: int


class Criterion(BaseModel):
    name: str
    description: str
    weight: float = 1.0
    threshold: float = 0.7
    severity: Severity = "medium"

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize_severity(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        normalized = value.lower()
        mapping = {
            "error": "high",
            "warning": "medium",
            "info": "low",
        }
        return mapping.get(normalized, normalized)


class CriterionResult(BaseModel):
    name: str
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    rationale: str | None = None
    weight: float = 1.0
    severity: Severity = "medium"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    reason: str | None = None
    affected_section: str | None = None
    suggested_strategy: str | None = None

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize_severity(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        normalized = value.lower()
        mapping = {
            "error": "high",
            "warning": "medium",
            "info": "low",
        }
        return mapping.get(normalized, normalized)


class EvaluationResult(BaseModel):
    results: list[CriterionResult]
    passed: bool
    failed: list[str]
    weighted_score: float = 0.0
    pass_rate: float = 0.0
    sections: list[Section] = Field(default_factory=list)


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
    quality_before: float = 0.0
    quality_after: float = 0.0
    repair_gain: float = 0.0
    repair_efficiency: float = 0.0
    token_efficiency: float = 0.0
    criteria_pass_rate: float = 0.0
    weighted_quality_score: float = 0.0
    repair_lineage: list["RepairRecord"] = Field(default_factory=list)


class RepairDelta(BaseModel):
    section_id: str
    revised_text: str
    criterion: str
    strategy: str


class RepairRecord(BaseModel):
    attempt: int
    failed_criteria: list[str]
    repaired_text: str
    strategies: list[str] = Field(default_factory=list)
    failed_sections: list[str] = Field(default_factory=list)
    score_before: float | None = None
    score_after: float | None = None
    deltas: list[RepairDelta] = Field(default_factory=list)


class GenerationResponse(BaseModel):
    text: str
    raw: Any | None = None
    evaluation: EvaluationResult | None = None
    repairs: list[RepairRecord] = Field(default_factory=list)
    metrics: Metrics


class StreamEvent(BaseModel):
    type: Literal["text", "metrics", "evaluation", "done"]
    data: Any
