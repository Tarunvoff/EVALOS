from __future__ import annotations

from evalos.benchmarks.models import BenchmarkMetrics
from evalos.types import EvaluationResult, Usage


def build_metrics(
    *,
    evaluation: EvaluationResult | None,
    grounding_score: float,
    hallucination_rate: float,
    citation_precision: float,
    repair_efficiency: float,
    rollback_frequency: float,
    tool_correctness_score: float,
    usage: Usage | None,
    latency_ms: float,
) -> BenchmarkMetrics:
    quality_score = evaluation.weighted_score if evaluation else 0.0
    pass_rate = evaluation.pass_rate if evaluation else 0.0
    total_tokens = usage.total_tokens if usage else 0
    token_efficiency = quality_score / max(1, total_tokens)
    convergence_rate = 1.0 if evaluation and evaluation.passed else 0.0

    return BenchmarkMetrics(
        grounding_score=grounding_score,
        hallucination_rate=hallucination_rate,
        citation_precision=citation_precision,
        repair_efficiency=repair_efficiency,
        convergence_rate=convergence_rate,
        token_efficiency=token_efficiency,
        rollback_frequency=rollback_frequency,
        tool_correctness_score=tool_correctness_score,
        quality_score=quality_score,
        pass_rate=pass_rate,
        latency_ms=latency_ms,
        total_tokens=total_tokens,
    )
