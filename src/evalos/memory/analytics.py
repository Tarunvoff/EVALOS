from __future__ import annotations

from evalos.memory.models import ModelStats, DomainStats, RepairStrategyStats


def compute_risk(failed_total: int, criteria_total: int) -> float:
    if criteria_total <= 0:
        return 0.0
    return min(1.0, failed_total / max(1, criteria_total))


def model_risk(stats: ModelStats | None) -> float:
    if not stats:
        return 0.0
    return compute_risk(stats.failed_criteria_total, stats.criteria_total)


def domain_risk(stats: DomainStats | None) -> float:
    if not stats:
        return 0.0
    return compute_risk(stats.failed_criteria_total, stats.criteria_total)


def best_strategy(
    repair_stats: dict[str, RepairStrategyStats],
    *,
    min_attempts: int,
    min_success_rate: float,
) -> str | None:
    best_name = None
    best_rate = 0.0
    for name, stats in repair_stats.items():
        if stats.attempts < min_attempts:
            continue
        if stats.success_rate < min_success_rate:
            continue
        if stats.success_rate > best_rate:
            best_name = name
            best_rate = stats.success_rate
    return best_name


def sorted_failures(failures: dict[str, int], top_k: int) -> list[str]:
    sorted_items = sorted(failures.items(), key=lambda item: item[1], reverse=True)
    return [name for name, _ in sorted_items[:top_k]]
