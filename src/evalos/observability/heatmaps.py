from __future__ import annotations

import time
from collections import defaultdict
from typing import Iterable

from pydantic import BaseModel, Field

from evalos.observability.tracer import Trace


class CriterionHeatmapEntry(BaseModel):
    criterion: str
    pass_rate: float
    avg_score: float
    failure_rate: float
    repair_frequency: float
    uncertainty_avg: float
    sample_count: int


class CriterionHeatmap(BaseModel):
    model: str | None = None
    domain: str | None = None
    entries: list[CriterionHeatmapEntry] = Field(default_factory=list)


def compute_criterion_heatmap(
    traces: Iterable[Trace],
    *,
    model: str | None = None,
    domain: str | None = None,
    window_s: float | None = None,
) -> CriterionHeatmap:
    now = time.time()
    score_sum: dict[str, float] = defaultdict(float)
    pass_count: dict[str, int] = defaultdict(int)
    fail_count: dict[str, int] = defaultdict(int)
    conf_sum: dict[str, float] = defaultdict(float)
    sample_count: dict[str, int] = defaultdict(int)
    repair_count: dict[str, int] = defaultdict(int)

    for trace in traces:
        if model and trace.model != model:
            continue
        if domain and trace.domain != domain:
            continue
        if window_s and (now - trace.start_ts) > window_s:
            continue
        if not trace.evaluation:
            continue
        for result in trace.evaluation.results:
            name = result.name
            score_sum[name] += result.score
            conf_sum[name] += result.confidence
            sample_count[name] += 1
            if result.passed:
                pass_count[name] += 1
            else:
                fail_count[name] += 1
        for repair in trace.repairs:
            for criterion in repair.failed_criteria:
                repair_count[criterion] += 1

    entries: list[CriterionHeatmapEntry] = []
    for name, total in sample_count.items():
        passes = pass_count.get(name, 0)
        fails = fail_count.get(name, 0)
        avg_score = score_sum[name] / max(1, total)
        pass_rate = passes / max(1, total)
        failure_rate = fails / max(1, total)
        repair_frequency = repair_count.get(name, 0) / max(1, total)
        uncertainty_avg = conf_sum[name] / max(1, total)
        entries.append(
            CriterionHeatmapEntry(
                criterion=name,
                pass_rate=pass_rate,
                avg_score=avg_score,
                failure_rate=failure_rate,
                repair_frequency=repair_frequency,
                uncertainty_avg=uncertainty_avg,
                sample_count=total,
            )
        )

    entries.sort(key=lambda item: item.failure_rate, reverse=True)
    return CriterionHeatmap(model=model, domain=domain, entries=entries)


def compute_heatmaps_by_model_domain(
    traces: Iterable[Trace],
    *,
    window_s: float | None = None,
) -> list[CriterionHeatmap]:
    bucketed: dict[tuple[str | None, str | None], list[Trace]] = defaultdict(list)
    for trace in traces:
        bucketed[(trace.model, trace.domain)].append(trace)

    heatmaps: list[CriterionHeatmap] = []
    for (model, domain), bucket in bucketed.items():
        heatmaps.append(
            compute_criterion_heatmap(
                bucket,
                model=model,
                domain=domain,
                window_s=window_s,
            )
        )
    return heatmaps
