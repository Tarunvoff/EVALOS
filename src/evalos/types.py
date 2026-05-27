from __future__ import annotations

from typing import Any, Literal, TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

from evalos.rag.schema import SCHEMA_VERSION, Provenance

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
    threshold: float = 0.7
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
    tokens_saved_vs_retry: float = 0.0
    estimated_full_retry_tokens: float = 0.0
    repair_token_cost: float = 0.0
    improvement_delta: float = 0.0
    adaptation_strength: float = 0.0
    threshold_drift: float = 0.0
    decay_effect: float = 0.0
    rollback_frequency: float = 0.0
    memory_confidence: float = 0.0
    adaptation_ready: bool = False
    adaptation_metrics: dict[str, Any] = Field(default_factory=dict)
    grounding_score: float = 0.0
    hallucination_rate: float = 0.0
    citation_accuracy: float = 0.0
    citation_precision: float = 0.0
    tool_correctness_score: float = 0.0
    agent_planning_score: float = 0.0
    execution_alignment_score: float = 0.0
    hallucinated_tool_usage_rate: float = 0.0
    reasoning_consistency_score: float = 0.0
    retrieval_alignment_score: float = 0.0
    rag_repair_gain: float = 0.0


class RepairDelta(BaseModel):
    section_id: str
    revised_text: str
    criterion: str
    strategy: str


class RepairRecord(BaseModel):
    schema_version: str = SCHEMA_VERSION
    attempt: int
    failed_criteria: list[str]
    repaired_text: str
    strategies: list[str] = Field(default_factory=list)
    failed_sections: list[str] = Field(default_factory=list)
    score_before: float | None = None
    score_after: float | None = None
    deltas: list[RepairDelta] = Field(default_factory=list)
    repair_tokens: int = 0
    token_delta: int = 0
    provenance: Provenance | None = None


class GenerationResponse(BaseModel):
    text: str
    initial_text: str | None = None
    raw: Any | None = None
    evaluation: EvaluationResult | None = None
    repairs: list[RepairRecord] = Field(default_factory=list)
    metrics: Metrics
    trace: Any | None = None
    rag: dict[str, Any] | None = None

    def format_trace(self) -> str:
        if self.trace:
            return self.trace.render()
        lines = []
        lines.append("=== EvalOS Request Trace ===")
        lines.append(f"Model: {self.metrics.model} | Provider: {self.metrics.provider}")
        lines.append(f"Latency: {self.metrics.latency_ms:.1f}ms | Retries: {self.metrics.retries}")
        lines.append(f"Tokens: {self.metrics.usage.total_tokens} (saved vs retry: {self.metrics.tokens_saved_vs_retry})")
        
        lines.append("\n--- Repair Timeline Graph ---")
        lines.append(f"Initial Score: {self.metrics.quality_before:.2f}")
        for r in self.repairs:
            failed = ", ".join(r.failed_criteria) if r.failed_criteria else "None"
            lines.append(f"  v Attempt {r.attempt} -> Score: {r.score_after:.2f} (Repaired: {failed})")
        
        lines.append("\n--- Before/After Comparison ---")
        if self.initial_text and self.text != self.initial_text:
            lines.append(f"[Before]\n{self.initial_text}\n")
            lines.append(f"[After]\n{self.text}")
        else:
            lines.append("[No changes made or initial text unavailable]")
            
        return "\n".join(lines)


class StreamEvent(BaseModel):
    type: Literal["text", "metrics", "evaluation", "trace", "done"]
    data: Any


if TYPE_CHECKING:
    from evalos.observability.tracer import Trace
