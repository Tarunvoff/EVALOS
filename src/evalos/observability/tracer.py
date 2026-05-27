from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

from evalos.types import Criterion, EvaluationResult, RepairRecord, Usage


class TraceStep(BaseModel):
    name: str
    timestamp: float
    duration_ms: float | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    annotations: list[str] = Field(default_factory=list)


class RollbackEvent(BaseModel):
    attempt: int
    score_before: float
    score_after: float
    timestamp: float
    reason: str | None = None


class Trace(BaseModel):
    request_id: str
    model: str
    provider: str
    query: str
    domain: str | None = None
    start_ts: float
    steps: list[TraceStep] = Field(default_factory=list)
    criteria: list[Criterion] = Field(default_factory=list)
    evaluation: EvaluationResult | None = None
    repairs: list[RepairRecord] = Field(default_factory=list)
    rollback_events: list[RollbackEvent] = Field(default_factory=list)
    outcome: str | None = None
    latency_ms: float | None = None
    latency_breakdown: dict[str, float] = Field(default_factory=dict)
    token_usage: Usage = Field(default_factory=Usage)
    memory_influence: dict[str, Any] = Field(default_factory=dict)
    annotations: list[str] = Field(default_factory=list)
    initial_text: str | None = None
    final_text: str | None = None

    @classmethod
    def start(
        cls,
        *,
        model: str,
        provider: str,
        query: str,
        domain: str | None = None,
        request_id: str | None = None,
        timestamp: float | None = None,
    ) -> "Trace":
        ts = timestamp or time.time()
        trace = cls(
            request_id=request_id or str(uuid.uuid4()),
            model=model,
            provider=provider,
            query=query,
            domain=domain,
            start_ts=ts,
        )
        trace.add_step("request_start", timestamp=ts)
        return trace

    def add_step(
        self,
        name: str,
        *,
        data: dict[str, Any] | None = None,
        duration_ms: float | None = None,
        timestamp: float | None = None,
        annotations: list[str] | None = None,
    ) -> None:
        step = TraceStep(
            name=name,
            timestamp=timestamp or time.time(),
            duration_ms=duration_ms,
            data=data or {},
            annotations=annotations or [],
        )
        self.steps.append(step)

    def annotate(self, note: str) -> None:
        self.annotations.append(note)

    def annotate_step(self, name: str, note: str) -> None:
        for step in reversed(self.steps):
            if step.name == name:
                step.annotations.append(note)
                break

    def render(self) -> str:
        lines: list[str] = []
        lines.append("=== EvalOS Trace ===")
        lines.append(f"Request: {self.request_id}")
        lines.append(f"Model: {self.model} | Provider: {self.provider}")
        if self.domain:
            lines.append(f"Domain: {self.domain}")
        if self.outcome:
            lines.append(f"Outcome: {self.outcome}")
        if self.latency_ms is not None:
            lines.append(f"Latency: {self.latency_ms:.1f}ms")
        if self.token_usage.total_tokens:
            lines.append(f"Tokens: {self.token_usage.total_tokens}")

        lines.append("\n--- Flow ---")
        base = self.steps[0].timestamp if self.steps else self.start_ts
        for step in self.steps:
            offset = (step.timestamp - base) * 1000.0
            duration = f" ({step.duration_ms:.1f}ms)" if step.duration_ms is not None else ""
            lines.append(f"+{offset:7.1f}ms {step.name}{duration}")
            for note in step.annotations:
                lines.append(f"    - {note}")

        if self.criteria:
            lines.append("\n--- Criteria ---")
            for criterion in self.criteria:
                lines.append(f"- {criterion.name}: threshold {criterion.threshold:.2f}, weight {criterion.weight:.2f}")

        if self.evaluation:
            lines.append("\n--- Evaluation ---")
            lines.append(
                f"Score: {self.evaluation.weighted_score:.2f} | Pass rate: {self.evaluation.pass_rate:.2f}"
            )
            if self.evaluation.failed:
                lines.append(f"Failed: {', '.join(self.evaluation.failed)}")

        if self.repairs:
            lines.append("\n--- Repair Timeline ---")
            for record in self.repairs:
                delta = None
                if record.score_before is not None and record.score_after is not None:
                    delta = record.score_after - record.score_before
                delta_text = f" (delta {delta:+.2f})" if delta is not None else ""
                strategies = ", ".join(record.strategies) if record.strategies else "none"
                score_before = f"{record.score_before:.2f}" if record.score_before is not None else "n/a"
                score_after = f"{record.score_after:.2f}" if record.score_after is not None else "n/a"
                lines.append(
                    f"Attempt {record.attempt}: {score_before} -> {score_after}{delta_text}"
                )
                lines.append(f"  Strategies: {strategies}")
                if record.failed_criteria:
                    lines.append(f"  Failed: {', '.join(record.failed_criteria)}")

        if self.rollback_events:
            lines.append("\n--- Rollbacks ---")
            for event in self.rollback_events:
                score_before = f"{event.score_before:.2f}" if event.score_before is not None else "n/a"
                score_after = f"{event.score_after:.2f}" if event.score_after is not None else "n/a"
                lines.append(
                    f"Attempt {event.attempt}: {score_before} -> {score_after}"
                )
                if event.reason:
                    lines.append(f"  Reason: {event.reason}")

        if self.memory_influence:
            lines.append("\n--- Memory Influence ---")
            for key, value in self.memory_influence.items():
                lines.append(f"- {key}: {value}")

        if self.initial_text and self.final_text and self.final_text != self.initial_text:
            lines.append("\n--- Output Diff ---")
            lines.append("[Initial]")
            lines.append(self.initial_text)
            lines.append("\n[Final]")
            lines.append(self.final_text)
        return "\n".join(lines)
