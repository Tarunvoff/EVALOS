from __future__ import annotations

import csv
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from evalos.benchmarks.charts import render_charts
from evalos.benchmarks.models import BenchmarkRun, StrategyRun


def export_reports(run: BenchmarkRun) -> Path:
    output_dir = _resolve_output_dir(run)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "benchmark_results.json"
    json_path.write_text(
        json.dumps(run.model_dump(mode="json"), indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    _write_csv(output_dir / "benchmark_results.csv", run.results)
    _write_markdown(output_dir / "summary.md", run)
    render_charts(output_dir, run)
    return output_dir


def _resolve_output_dir(run: BenchmarkRun) -> Path:
    base = Path(run.config.output_dir)
    run_id = run.config.run_id
    if not run_id:
        run_id = time.strftime("%Y%m%d_%H%M%S")
    return base / run_id


def _write_csv(path: Path, results: list[StrategyRun]) -> None:
    fieldnames = [
        "strategy",
        "case_id",
        "domain",
        "evaluation_score",
        "evaluation_passed",
        "failed_criteria",
        "quality_score",
        "grounding_score",
        "hallucination_rate",
        "citation_precision",
        "repair_efficiency",
        "convergence_rate",
        "token_efficiency",
        "rollback_frequency",
        "tool_correctness_score",
        "latency_ms",
        "total_tokens",
        "retries",
        "repairs",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            metrics = result.metrics
            writer.writerow(
                {
                    "strategy": result.strategy,
                    "case_id": result.case_id,
                    "domain": result.domain,
                    "evaluation_score": result.evaluation_score,
                    "evaluation_passed": result.evaluation_passed,
                    "failed_criteria": ";".join(result.failed_criteria),
                    "quality_score": metrics.quality_score,
                    "grounding_score": metrics.grounding_score,
                    "hallucination_rate": metrics.hallucination_rate,
                    "citation_precision": metrics.citation_precision,
                    "repair_efficiency": metrics.repair_efficiency,
                    "convergence_rate": metrics.convergence_rate,
                    "token_efficiency": metrics.token_efficiency,
                    "rollback_frequency": metrics.rollback_frequency,
                    "tool_correctness_score": metrics.tool_correctness_score,
                    "latency_ms": metrics.latency_ms,
                    "total_tokens": metrics.total_tokens,
                    "retries": result.retries,
                    "repairs": result.repairs,
                }
            )


def _write_markdown(path: Path, run: BenchmarkRun) -> None:
    summary = _aggregate_summary(run.results)
    lines: list[str] = []
    lines.append("# EvalOS Benchmark Summary")
    lines.append("")
    lines.append(f"Model: {run.config.model}")
    lines.append(f"Provider: {run.config.provider}")
    lines.append(f"Cases: {len(run.cases)}")
    lines.append("")

    lines.append("## Overall Metrics")
    lines.append("")
    lines.append(_markdown_table(summary["overall"]))

    lines.append("")
    lines.append("## Domain Breakdown")
    for domain, table in summary["by_domain"].items():
        lines.append("")
        lines.append(f"### {domain}")
        lines.append("")
        lines.append(_markdown_table(table))

    path.write_text("\n".join(lines), encoding="utf-8")


def _aggregate_summary(results: list[StrategyRun]) -> dict[str, Any]:
    by_strategy: dict[str, list[StrategyRun]] = defaultdict(list)
    by_domain: dict[str, dict[str, list[StrategyRun]]] = defaultdict(lambda: defaultdict(list))
    for result in results:
        by_strategy[result.strategy].append(result)
        by_domain[result.domain][result.strategy].append(result)

    overall = _aggregate_table(by_strategy)
    domain_tables = {domain: _aggregate_table(group) for domain, group in by_domain.items()}
    return {"overall": overall, "by_domain": domain_tables}


def _aggregate_table(by_strategy: dict[str, list[StrategyRun]]) -> list[list[str]]:
    header = [
        "Strategy",
        "Quality",
        "Pass Rate",
        "Grounding",
        "Hallucination",
        "Citation Precision",
        "Repair Efficiency",
        "Token Efficiency",
        "Rollback",
    ]
    rows = [header]
    for strategy, items in by_strategy.items():
        rows.append(
            [
                strategy,
                _avg(items, "quality_score"),
                _avg(items, "pass_rate"),
                _avg(items, "grounding_score"),
                _avg(items, "hallucination_rate"),
                _avg(items, "citation_precision"),
                _avg(items, "repair_efficiency"),
                _avg(items, "token_efficiency"),
                _avg(items, "rollback_frequency"),
            ]
        )
    return rows


def _avg(items: list[StrategyRun], field: str) -> str:
    values = [getattr(item.metrics, field) for item in items]
    if not values:
        return "0.00"
    return f"{sum(values) / len(values):.2f}"


def _markdown_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    header = "| " + " | ".join(rows[0]) + " |"
    divider = "| " + " | ".join(["---"] * len(rows[0])) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows[1:]]
    return "\n".join([header, divider] + body)
