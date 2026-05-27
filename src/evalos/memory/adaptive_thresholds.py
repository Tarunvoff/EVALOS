from __future__ import annotations

from evalos.memory.models import ThresholdStats


def update_threshold_stats(
    stats: ThresholdStats,
    *,
    score: float,
    passed: bool,
    base_threshold: float,
    weight: float = 1.0,
) -> ThresholdStats:
    total = stats.sample_count + weight
    stats.avg_score = ((stats.avg_score * stats.sample_count) + (score * weight)) / max(1e-6, total)
    stats.sample_count = total
    stats.observations += 1
    if not passed:
        stats.failure_count += weight
    failure_rate = stats.failure_count / max(1e-6, stats.sample_count)
    stats.recommended_threshold = recommend_threshold(
        base_threshold=base_threshold,
        avg_score=stats.avg_score,
        failure_rate=failure_rate,
    )
    return stats


def recommend_threshold(*, base_threshold: float, avg_score: float, failure_rate: float) -> float:
    # Tighten thresholds when failures persist or quality drifts low.
    penalty = max(0.0, 0.85 - avg_score) * 0.05
    risk_adjust = failure_rate * 0.1
    recommended = base_threshold + penalty + risk_adjust
    return _clamp_threshold(recommended)


def _clamp_threshold(value: float) -> float:
    return min(0.98, max(0.5, value))
