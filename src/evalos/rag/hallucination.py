from __future__ import annotations

from pydantic import BaseModel, Field

from evalos.rag.grounding import GroundingResult
from evalos.rag.schema import SCHEMA_VERSION


class HallucinationResult(BaseModel):
    schema_version: str = SCHEMA_VERSION
    hallucination_score: float
    hallucinated_spans: list[str] = Field(default_factory=list)
    risk_level: str = "low"


class HallucinationDetector:
    def __init__(self, *, critical_threshold: float = 0.65) -> None:
        self._critical_threshold = critical_threshold

    def evaluate(self, *, grounding: GroundingResult) -> HallucinationResult:
        spans = [item.claim for item in grounding.unsupported_claims]
        if grounding.total_claims == 0:
            score = 0.0
        else:
            score = len(spans) / max(1, grounding.total_claims)
        risk = _risk_level(score, self._critical_threshold)
        return HallucinationResult(
            hallucination_score=score,
            hallucinated_spans=spans,
            risk_level=risk,
        )


def _risk_level(score: float, critical_threshold: float) -> str:
    if score >= critical_threshold:
        return "critical"
    if score >= 0.4:
        return "high"
    if score >= 0.2:
        return "medium"
    return "low"
