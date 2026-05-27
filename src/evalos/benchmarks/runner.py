from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterable

from evalos.benchmarks.models import BenchmarkCase, BenchmarkConfig, BenchmarkRun, StrategyName
from evalos.benchmarks.reporting import export_reports
from evalos.benchmarks.strategies import ensure_strategy_names, strategy_registry
from evalos.config import PipelineConfig, RetryConfig
from evalos.criteria import CriteriaGenerator
from evalos.providers.resilient import ResilientProvider
from evalos.pipeline import ProviderRegistry


class BenchmarkRunner:
    def __init__(self, config: BenchmarkConfig, *, fixtures_dir: str = "benchmarks/fixtures") -> None:
        self._config = config
        self._fixtures_dir = Path(fixtures_dir)
        provider = ProviderRegistry.get(config.provider)
        retry = RetryConfig(max_attempts=1)
        self._criteria_provider = ResilientProvider(provider, timeout_s=30.0, retry=retry)
        self._criteria_config = PipelineConfig(
            model=config.model,
            provider=config.provider,
            evaluation_strictness=config.strictness,
        )
        self._criteria_generator = CriteriaGenerator(self._criteria_provider, self._criteria_config)

    def load_cases(self) -> list[BenchmarkCase]:
        if not self._fixtures_dir.exists():
            raise FileNotFoundError(f"Missing fixtures dir: {self._fixtures_dir}")
        cases: list[BenchmarkCase] = []
        for path in sorted(self._fixtures_dir.glob("*.jsonl")):
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    payload = json.loads(line)
                    cases.append(BenchmarkCase.model_validate(payload))
        return cases

    async def run(
        self,
        *,
        strategies: Iterable[str] = ("vanilla", "retry", "best_of_n", "evalos"),
        export: bool = True,
    ) -> BenchmarkRun:
        cases = self.load_cases()
        selected = ensure_strategy_names(strategies)
        registry = strategy_registry(self._config)
        results = []
        criteria_map: dict[str, list] = {}

        for case in cases:
            criteria = await self._criteria_generator.generate(
                query=case.prompt, optimize_for=case.optimize_for
            )
            criteria_map[case.id] = criteria

        for case in cases:
            criteria = criteria_map.get(case.id, [])
            for name in selected:
                strategy = registry[name]
                results.append(await strategy.run(case=case, criteria=criteria))

        run = BenchmarkRun(config=self._config, cases=cases, results=results)
        if export:
            export_reports(run)
        return run


def load_run(path: str) -> BenchmarkRun:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return BenchmarkRun.model_validate(payload)


def replay(run_path: str) -> BenchmarkRun:
    run = load_run(run_path)
    export_reports(run)
    return run
