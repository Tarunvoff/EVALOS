from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

from evalos.rag.schema import SCHEMA_VERSION

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
    schema_version: str = SCHEMA_VERSION
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
    retrieval_inputs: list[dict[str, Any]] = Field(default_factory=list)
    grounding: dict[str, Any] = Field(default_factory=dict)
    hallucination: dict[str, Any] = Field(default_factory=dict)
    citation: dict[str, Any] = Field(default_factory=dict)
    agent_evaluation: dict[str, Any] = Field(default_factory=dict)
    rag_repair: dict[str, Any] = Field(default_factory=dict)
    schema_validation: list[dict[str, Any]] = Field(default_factory=list)
    claim_canonicalization: list[dict[str, Any]] = Field(default_factory=list)
    claim_dependencies: list[dict[str, Any]] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    agent_trace: dict[str, Any] = Field(default_factory=dict)

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
        lines.append(f"Schema: {self.schema_version}")
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

        if self.grounding or self.hallucination or self.citation:
            lines.append("\n--- RAG Reliability ---")
            if self.retrieval_inputs:
                lines.append(f"Retrieval docs: {len(self.retrieval_inputs)}")
            if self.grounding:
                lines.append(f"Grounding score: {self.grounding.get('grounding_score')}")
            if self.hallucination:
                lines.append(
                    f"Hallucination score: {self.hallucination.get('hallucination_score')}"
                )
            if self.citation:
                lines.append(
                    f"Citation accuracy: {self.citation.get('citation_accuracy_score')}"
                )
            if self.agent_evaluation:
                lines.append(
                    f"Tool correctness: {self.agent_evaluation.get('tool_correctness_score')}"
                )
            if self.rag_repair:
                lines.append(
                    f"RAG repair applied: {self.rag_repair.get('applied')}"
                )

        if self.schema_validation:
            lines.append("\n--- Schema Validation ---")
            for item in self.schema_validation:
                source = item.get("source", "unknown")
                status = item.get("status", "unknown")
                lines.append(f"{source}: {status}")

        if self.agent_trace:
            plan = self.agent_trace.get("plan", [])
            if plan:
                lines.append("\n--- Agent Plan ---")
                for step in plan:
                    tool = str(step.get("tool", ""))
                    goal = step.get("goal", "")
                    status = step.get("status", "")
                    tag = "reasoning" if tool.strip().lower() == "reasoning" else "tool"
                    lines.append(f"[{tag}] {tool}: {goal} ({status})")

        if self.claim_canonicalization:
            lines.append("\n--- Claim Canonicalization ---")
            for item in self.claim_canonicalization:
                lines.append(
                    f"{item.get('canonical_claim_id')} <- {item.get('external_claim_id')}"
                )

        if self.claim_dependencies:
            lines.append("\n--- Claim Dependencies ---")
            for item in self.claim_dependencies:
                deps = item.get("depends_on", [])
                lines.append(f"{item.get('claim_id')}: {deps}")

        if self.provenance:
            lines.append("\n--- Provenance ---")
            for key, value in self.provenance.items():
                lines.append(f"- {key}: {value}")

        if self.repairs:
            lines.append("\n--- Repair Lineage ---")
            for record in self.repairs:
                if record.provenance:
                    gen = record.provenance.repair_generation
                    derived = ", ".join(record.provenance.derived_from)
                    lines.append(f"Attempt {record.attempt}: gen {gen} <- [{derived}]")

        if self.repairs:
            lines.append("\n--- Repair Timeline Graph ---")
            lines.append(f"Initial Score: {self.evaluation.weighted_score:.2f}" if self.evaluation else "Initial Score: n/a")
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
