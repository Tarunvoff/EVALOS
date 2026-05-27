from __future__ import annotations

import time
from collections import defaultdict
from statistics import mean, variance
from typing import Iterable

from pydantic import BaseModel, Field

from evalos.observability.tracer import Trace
from evalos.types import Metrics


class AdaptiveMetrics(BaseModel):
    adaptation_strength: float = 0.0
    memory_influence_score: float = 0.0
    threshold_drift_over_time: float = 0.0
    repair_convergence_rate: float = 0.0
    rollback_frequency: float = 0.0
    stability_index: float = 0.0
    evaluation_variance: float = 0.0


class ModelReliabilityStats(BaseModel):
    model: str
    avg_quality_score: float
    repair_rate: float
    rollback_frequency: float
    convergence_speed: float
    failure_distribution: dict[str, int] = Field(default_factory=dict)
    evaluation_variance: float = 0.0


class LongRunAnalytics(BaseModel):
    most_failing_criteria: list[str] = Field(default_factory=list)
    weakest_models: list[str] = Field(default_factory=list)
    most_effective_repair_strategies: list[str] = Field(default_factory=list)
    stability_trend: list[dict[str, float]] = Field(default_factory=list)


def compute_adaptive_metrics(*, metrics: Metrics, trace: Trace | None = None) -> AdaptiveMetrics:
    scores: list[float] = []
    if trace and trace.evaluation:
        scores.append(trace.evaluation.weighted_score)
    if trace:
        for record in trace.repairs:
            if record.score_after is not None:
                scores.append(record.score_after)
    evaluation_variance = variance(scores) if len(scores) >= 2 else 0.0

    memory_influence_score = 0.0
    if trace and trace.memory_influence:
        deltas: list[float] = []
        adaptation = trace.memory_influence.get("adaptation")
        thresholds = None
        weights = None
        if isinstance(adaptation, dict):
            thresholds = adaptation.get("thresholds")
            weights = adaptation.get("weights")
        if isinstance(thresholds, dict):
            for item in thresholds.values():
                if isinstance(item, dict):
                    deltas.append(abs(float(item.get("capped", 0.0)) - float(item.get("base", 0.0))))
        if isinstance(weights, dict):
            for item in weights.values():
                if isinstance(item, dict):
                    deltas.append(abs(float(item.get("capped", 0.0)) - float(item.get("base", 0.0))))
        memory_influence_score = sum(deltas) / max(1, len(deltas))

    stability_index = metrics.memory_confidence if hasattr(metrics, "memory_confidence") else 0.0

    return AdaptiveMetrics(
        adaptation_strength=metrics.adaptation_strength,
        memory_influence_score=memory_influence_score,
        threshold_drift_over_time=metrics.threshold_drift,
        repair_convergence_rate=metrics.repair_efficiency,
        rollback_frequency=metrics.rollback_frequency,
        stability_index=stability_index,
        evaluation_variance=evaluation_variance,
    )


def compute_model_reliability(traces: Iterable[Trace]) -> list[ModelReliabilityStats]:
    bucketed: dict[str, list[Trace]] = defaultdict(list)
    for trace in traces:
        bucketed[trace.model].append(trace)

    stats: list[ModelReliabilityStats] = []
    for model, bucket in bucketed.items():
        scores: list[float] = []
        repairs = 0
        rollbacks = 0
        failures: dict[str, int] = defaultdict(int)
        convergence: list[float] = []
        for trace in bucket:
            if trace.evaluation:
                scores.append(trace.evaluation.weighted_score)
                for failed in trace.evaluation.failed:
                    failures[failed] += 1
            repairs += len(trace.repairs)
            rollbacks += len(trace.rollback_events)
            if trace.repairs and trace.repairs[-1].score_after is not None:
                convergence.append(float(trace.repairs[-1].attempt))
        avg_score = mean(scores) if scores else 0.0
        repair_rate = repairs / max(1, len(bucket))
        rollback_frequency = rollbacks / max(1, len(bucket))
        convergence_speed = mean(convergence) if convergence else 0.0
        score_variance = variance(scores) if len(scores) >= 2 else 0.0
        stats.append(
            ModelReliabilityStats(
                model=model,
                avg_quality_score=avg_score,
                repair_rate=repair_rate,
                rollback_frequency=rollback_frequency,
                convergence_speed=convergence_speed,
                failure_distribution=dict(failures),
                evaluation_variance=score_variance,
            )
        )
    return stats


def compute_long_run_analytics(
    traces: Iterable[Trace],
    *,
    window_s: float | None = None,
) -> LongRunAnalytics:
    now = time.time()
    failing: dict[str, int] = defaultdict(int)
    strategy_score: dict[str, float] = defaultdict(float)
    strategy_count: dict[str, int] = defaultdict(int)
    model_scores: dict[str, list[float]] = defaultdict(list)
    stability: list[dict[str, float]] = []

    for trace in traces:
        if window_s and (now - trace.start_ts) > window_s:
            continue
        if trace.evaluation:
            for failed in trace.evaluation.failed:
                failing[failed] += 1
            model_scores[trace.model].append(trace.evaluation.weighted_score)
        for repair in trace.repairs:
            for strategy in repair.strategies:
                delta = 0.0
                if repair.score_before is not None and repair.score_after is not None:
                    delta = repair.score_after - repair.score_before
                strategy_score[strategy] += delta
                strategy_count[strategy] += 1
        if trace.evaluation:
            stability.append(
                {
                    "timestamp": trace.start_ts,
                    "stability": trace.evaluation.weighted_score,
                }
            )

    most_failing = sorted(failing, key=failing.get, reverse=True)[:5]
    weakest_models = sorted(
        model_scores,
        key=lambda key: mean(model_scores[key]) if model_scores[key] else 0.0,
    )[:5]
    most_effective = sorted(
        strategy_score,
        key=lambda key: strategy_score[key] / max(1, strategy_count[key]),
        reverse=True,
    )[:5]

    return LongRunAnalytics(
        most_failing_criteria=most_failing,
        weakest_models=weakest_models,
        most_effective_repair_strategies=most_effective,
        stability_trend=stability,
    )
