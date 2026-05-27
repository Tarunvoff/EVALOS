from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from evalos.observability.tracer import RollbackEvent
from evalos.types import RepairRecord


class RepairTimelineStep(BaseModel):
    attempt: int
    score_before: float | None = None
    score_after: float | None = None
    delta: float | None = None
    repaired_sections: list[str] = Field(default_factory=list)
    strategies: list[str] = Field(default_factory=list)
    rollback: bool = False


class RepairTimeline(BaseModel):
    steps: list[RepairTimelineStep] = Field(default_factory=list)
    final_score: float | None = None
    converged: bool = False

    def to_series(self) -> list[dict[str, Any]]:
        return [step.model_dump() for step in self.steps]

    @classmethod
    def from_repairs(
        cls,
        *,
        repairs: list[RepairRecord],
        rollback_events: list[RollbackEvent] | None = None,
        final_score: float | None = None,
    ) -> "RepairTimeline":
        rollback_map = {event.attempt: event for event in rollback_events or []}
        steps: list[RepairTimelineStep] = []
        for record in repairs:
            delta = None
            if record.score_before is not None and record.score_after is not None:
                delta = record.score_after - record.score_before
            rollback = record.attempt in rollback_map
            steps.append(
                RepairTimelineStep(
                    attempt=record.attempt,
                    score_before=record.score_before,
                    score_after=record.score_after,
                    delta=delta,
                    repaired_sections=record.failed_sections,
                    strategies=record.strategies,
                    rollback=rollback,
                )
            )
        converged = bool(final_score is not None and repairs and repairs[-1].score_after == final_score)
        return cls(steps=steps, final_score=final_score, converged=converged)
