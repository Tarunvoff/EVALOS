from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from evalos.benchmarks.models import BenchmarkRun, StrategyRun


def _get_pyplot() -> Any:
    try:
        import matplotlib.pyplot as plt

        return plt
    except ImportError as exc:
        raise ImportError(
            "The 'matplotlib' package is required to render benchmark charts. "
            "Install it with: pip install 'evalos[bench]'"
        ) from exc


def render_charts(output_dir: Path, run: BenchmarkRun) -> None:
    plt = _get_pyplot()
    charts_dir = output_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    by_strategy: dict[str, list[StrategyRun]] = defaultdict(list)
    for result in run.results:
        by_strategy[result.strategy].append(result)

    _cost_vs_quality(charts_dir / "cost_vs_quality.png", by_strategy, plt=plt)
    _hallucination_chart(charts_dir / "hallucination_rates.png", by_strategy, plt=plt)
    _before_after_quality(charts_dir / "quality_comparison.png", by_strategy, plt=plt)


def _avg(items: list[StrategyRun], field: str) -> float:
    values = [getattr(item.metrics, field) for item in items]
    if not values:
        return 0.0
    return sum(values) / len(values)


def _cost_vs_quality(path: Path, grouped: dict[str, list[StrategyRun]], *, plt: Any) -> None:
    labels = []
    tokens = []
    quality = []
    for strategy, items in grouped.items():
        labels.append(strategy)
        tokens.append(_avg(items, "total_tokens"))
        quality.append(_avg(items, "quality_score"))

    plt.figure(figsize=(6, 4))
    plt.scatter(tokens, quality)
    for idx, label in enumerate(labels):
        plt.annotate(label, (tokens[idx], quality[idx]))
    plt.xlabel("Avg tokens")
    plt.ylabel("Avg quality score")
    plt.title("Cost vs Quality")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def _hallucination_chart(path: Path, grouped: dict[str, list[StrategyRun]], *, plt: Any) -> None:
    labels = list(grouped.keys())
    values = [_avg(items, "hallucination_rate") for items in grouped.values()]
    plt.figure(figsize=(6, 4))
    plt.bar(labels, values, color="#4c78a8")
    plt.ylabel("Hallucination rate")
    plt.title("Hallucination Reduction")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def _before_after_quality(path: Path, grouped: dict[str, list[StrategyRun]], *, plt: Any) -> None:
    vanilla = grouped.get("vanilla", [])
    evalos = grouped.get("evalos", [])
    labels = ["vanilla", "evalos"]
    values = [_avg(vanilla, "quality_score"), _avg(evalos, "quality_score")]
    plt.figure(figsize=(5, 4))
    plt.bar(labels, values, color=["#9ecae9", "#31a354"])
    plt.ylabel("Avg quality score")
    plt.title("Before/After Quality")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
