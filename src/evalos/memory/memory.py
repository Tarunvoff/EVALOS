from __future__ import annotations

import asyncio
import time
from typing import Iterable, Literal

import structlog
from pydantic import BaseModel, Field, field_validator

from evalos.memory.adaptive_thresholds import update_threshold_stats
from evalos.memory.analytics import best_strategy, sorted_failures
from evalos.memory.models import (
    DomainStats,
    FailureStats,
    MemoryState,
    ModelStats,
    RagDomainStats,
    RagModelStats,
    RepairStrategyStats,
    SectionStabilityStats,
    ThresholdStats,
)
from evalos.memory.storage import JsonMemoryStorage, SQLiteMemoryStorage
from evalos.types import Criterion, EvaluationResult


class MemoryConfig(BaseModel):
    storage_path: str = ".evalos_memory.json"
    backend: Literal["json", "sqlite"] | None = None
    autosave: bool = True
    memory_version: int = 2
    max_threshold_history: int = 25
    min_strategy_attempts: int = 3
    min_strategy_success_rate: float = 0.6
    risk_strictness_threshold: float = 0.2
    model_threshold_boost: float = 0.05
    domain_weight_boost: float = 0.1
    max_threshold_delta: float = 0.08
    max_weight_delta: float = 0.15
    max_strictness_escalation: int = 1
    max_repair_strategy_bias: float = 0.6
    min_observations: int = 10
    failure_decay_lambda: float = 1.0 / (7 * 24 * 3600)
    repair_decay_lambda: float = 1.0 / (14 * 24 * 3600)
    min_update_weight: float = 0.1
    rag_grounding_threshold: float = 0.7
    rag_hallucination_threshold: float = 0.25
    rag_citation_threshold: float = 0.7
    rag_tool_threshold: float = 0.7

    @field_validator(
        "max_threshold_delta",
        "max_weight_delta",
        "max_repair_strategy_bias",
        "min_update_weight",
    )
    @classmethod
    def _validate_unit_range(cls, value: float) -> float:
        if value < 0.0:
            raise ValueError("Memory config values must be non-negative")
        return value

    @field_validator("min_observations")
    @classmethod
    def _validate_min_observations(cls, value: int) -> int:
        if value < 1:
            raise ValueError("min_observations must be >= 1")
        return value


class Memory:
    def __init__(self, db_path: str | None = None, config: MemoryConfig | None = None) -> None:
        self._config = config or MemoryConfig()
        if db_path:
            self._config.storage_path = db_path
        self._storage = self._select_storage(self._config)
        self._state = self._storage.load_sync()
        self._migrate_state(self._state)
        self._lock = asyncio.Lock()
        self._logger = structlog.get_logger("evalos.memory")
        self._last_adaptation_metrics: dict[str, object] = {}

    def _select_storage(self, config: MemoryConfig):
        backend = config.backend
        if backend is None:
            backend = "sqlite" if config.storage_path.endswith(".db") else "json"
        if backend == "sqlite":
            return SQLiteMemoryStorage(config.storage_path)
        return JsonMemoryStorage(config.storage_path)

    def _migrate_state(self, state: MemoryState) -> None:
        if state.memory_version >= self._config.memory_version:
            return
        if state.memory_version < 2:
            for stats in state.model_stats.values():
                stats.observations = int(stats.evaluations or 0)
            for stats in state.domain_stats.values():
                stats.observations = int(stats.evaluations or 0)
            for stats in state.repair_stats.values():
                stats.observations = int(stats.attempts or 0)
            for stats in state.threshold_stats.values():
                stats.observations = int(stats.sample_count or 0)
        state.memory_version = self._config.memory_version

    def _now(self) -> float:
        return time.time()

    def _decay_factor(self, last_ts: float | None, decay_lambda: float) -> float:
        if not last_ts:
            return 1.0
        age = max(0.0, self._now() - last_ts)
        return float(pow(2.718281828, -decay_lambda * age))

    def _decayed_failure(self, stats: FailureStats) -> float:
        factor = self._decay_factor(stats.last_ts, self._config.failure_decay_lambda)
        return stats.count * factor

    def _decayed_failures_total(self, stats: ModelStats | DomainStats | None) -> float:
        if not stats:
            return 0.0
        return sum(self._decayed_failure(item) for item in stats.criterion_failures.values())

    def _decayed_repair_stats(self, stats: RepairStrategyStats) -> tuple[float, float, float]:
        factor = self._decay_factor(stats.last_attempt_ts, self._config.repair_decay_lambda)
        decayed_attempts = stats.attempts * factor
        success_factor = self._decay_factor(stats.last_success_ts, self._config.repair_decay_lambda)
        decayed_successes = stats.successes * success_factor
        success_rate = decayed_successes / max(1e-6, decayed_attempts)
        return decayed_attempts, decayed_successes, success_rate

    def _cap_delta(self, base: float, target: float, max_delta: float) -> float:
        delta = target - base
        if delta > max_delta:
            return base + max_delta
        if delta < -max_delta:
            return base - max_delta
        return target

    def _cap_strictness(self, base: str, target: str) -> str:
        order = ["relaxed", "balanced", "strict", "adversarial"]
        if base not in order or target not in order:
            return target
        base_index = order.index(base)
        target_index = order.index(target)
        max_index = min(len(order) - 1, base_index + self._config.max_strictness_escalation)
        return order[min(target_index, max_index)]

    def record_failures(self, model: str, failed_criteria: list[str]) -> None:
        if not failed_criteria:
            return
        model_stats = self._state.model_stats.setdefault(model, ModelStats())
        model_stats.observations += 1
        model_stats.evaluations += 1.0
        for criterion in failed_criteria:
            stats = model_stats.criterion_failures.setdefault(criterion, FailureStats())
            stats.count += 1.0
            stats.last_ts = self._now()
        model_stats.failed_criteria_total += float(len(failed_criteria))
        if self._config.autosave:
            self._storage.save_sync(self._state)

    def get_recurring_failures(self, model: str, top_k: int = 3) -> list[str]:
        stats = self._state.model_stats.get(model)
        if not stats:
            return []
        raw = {name: value.count for name, value in stats.criterion_failures.items()}
        return sorted_failures(raw, top_k)

    async def arecord_evaluation(
        self,
        *,
        model: str,
        domain: str,
        criteria: list[Criterion],
        evaluation: EvaluationResult,
        stability_score: float = 1.0,
    ) -> None:
        async with self._lock:
            self._record_evaluation(
                model=model,
                domain=domain,
                criteria=criteria,
                evaluation=evaluation,
                stability_score=stability_score,
            )
            if self._config.autosave:
                await self._storage.save(self._state)

    async def arecord_repair(
        self, *, strategies: Iterable[str], success: bool, weight: float = 1.0
    ) -> None:
        async with self._lock:
            self._record_repair(strategies=strategies, success=success, weight=weight)
            if self._config.autosave:
                await self._storage.save(self._state)

    async def arecord_section_outcome(
        self,
        *,
        section_ids_all: list[str],
        failed_section_ids: list[str],
        attempt: int,
        rollback: bool = False,
    ) -> None:
        async with self._lock:
            self._record_section_outcome(
                section_ids_all=section_ids_all,
                failed_section_ids=failed_section_ids,
                attempt=attempt,
                rollback=rollback,
            )
            if self._config.autosave:
                await self._storage.save(self._state)

    async def arecord_rag_signals(
        self,
        *,
        model: str,
        domain: str,
        grounding_score: float,
        hallucination_score: float,
        citation_accuracy: float,
        tool_correctness: float | None = None,
        weight: float = 1.0,
    ) -> None:
        async with self._lock:
            self._record_rag_signals(
                model=model,
                domain=domain,
                grounding_score=grounding_score,
                hallucination_score=hallucination_score,
                citation_accuracy=citation_accuracy,
                tool_correctness=tool_correctness,
                weight=weight,
            )
            if self._config.autosave:
                await self._storage.save(self._state)

    def get_model_risk(self, model: str) -> float:
        stats = self._state.model_stats.get(model)
        if not stats or stats.observations < self._config.min_observations:
            return 0.0
        failed_total = self._decayed_failures_total(stats)
        return min(1.0, failed_total / max(1e-6, stats.criteria_total))

    def get_domain_failure_rate(self, domain: str, criterion: str | None = None) -> float:
        stats = self._state.domain_stats.get(domain)
        if not stats or stats.observations < self._config.min_observations:
            return 0.0
        if criterion:
            failures = stats.criterion_failures.get(criterion)
            if not failures:
                return 0.0
            decayed = self._decayed_failure(failures)
            return decayed / max(1e-6, stats.criteria_total)
        failed_total = self._decayed_failures_total(stats)
        return min(1.0, failed_total / max(1e-6, stats.criteria_total))

    def get_best_repair_strategy(self) -> str | None:
        eligible: dict[str, RepairStrategyStats] = {}
        for name, stats in self._state.repair_stats.items():
            if stats.observations < self._config.min_observations:
                continue
            decayed_attempts, _, decayed_rate = self._decayed_repair_stats(stats)
            if decayed_attempts < self._config.min_strategy_attempts:
                continue
            if decayed_rate < self._config.min_strategy_success_rate:
                continue
            copy = stats.model_copy()
            copy.success_rate = decayed_rate
            eligible[name] = copy
        return best_strategy(
            eligible,
            min_attempts=self._config.min_strategy_attempts,
            min_success_rate=self._config.min_strategy_success_rate,
        )

    def get_repair_success_stats(self) -> dict[str, RepairStrategyStats]:
        return self._state.repair_stats

    def get_model_weakness_summary(self, model: str, top_k: int = 3) -> list[str]:
        stats = self._state.model_stats.get(model)
        if not stats:
            return []
        decayed = {
            name: self._decayed_failure(value)
            for name, value in stats.criterion_failures.items()
        }
        return sorted_failures(decayed, top_k)

    def get_domain_failure_summary(self, domain: str, top_k: int = 3) -> list[str]:
        stats = self._state.domain_stats.get(domain)
        if not stats:
            return []
        decayed = {
            name: self._decayed_failure(value)
            for name, value in stats.criterion_failures.items()
        }
        return sorted_failures(decayed, top_k)

    def get_threshold_history(self, criterion: str) -> list[float]:
        return list(self._state.threshold_history.get(criterion, []))

    def get_section_stability(self, section_id: str) -> SectionStabilityStats | None:
        return self._state.section_stats.get(section_id)

    def get_stable_sections(self, section_ids: list[str]) -> list[str]:
        stable = []
        for section_id in section_ids:
            stats = self._state.section_stats.get(section_id)
            if stats and stats.stable_after_attempt is not None and stats.rollback_count == 0:
                stable.append(section_id)
        return stable

    def get_strictness_override(
        self,
        *,
        model: str,
        domain: str,
        base_strictness: str,
    ) -> str:
        model_score = self.get_model_risk(model)
        domain_score = self.get_domain_failure_rate(domain)
        risk = max(model_score, domain_score)
        if risk >= 0.35:
            target = "adversarial"
        elif risk >= self._config.risk_strictness_threshold:
            target = "strict"
        else:
            target = base_strictness
        capped = self._cap_strictness(base_strictness, target)
        self._last_adaptation_metrics["strictness"] = {
            "base": base_strictness,
            "target": target,
            "capped": capped,
            "risk": risk,
        }
        return capped

    def get_threshold_overrides(
        self,
        *,
        criteria: list[Criterion],
        model: str,
        domain: str,
    ) -> dict[str, float]:
        overrides: dict[str, float] = {}
        model_stats = self._state.model_stats.get(model)
        domain_stats = self._state.domain_stats.get(domain)
        threshold_metrics: dict[str, dict[str, float]] = {}
        for criterion in criteria:
            stats = self._state.threshold_stats.get(criterion.name)
            if stats and stats.recommended_threshold is not None:
                if stats.observations >= self._config.min_observations:
                    overrides[criterion.name] = stats.recommended_threshold
            if model_stats:
                failures = model_stats.criterion_failures.get(criterion.name, 0)
                if (
                    failures
                    and self._decayed_failure(failures) >= 3
                    and model_stats.observations >= self._config.min_observations
                ):
                    overrides[criterion.name] = max(
                        overrides.get(criterion.name, criterion.threshold),
                        criterion.threshold + self._config.model_threshold_boost,
                    )
            if domain_stats:
                failures = domain_stats.criterion_failures.get(criterion.name, 0)
                if (
                    failures
                    and self._decayed_failure(failures) >= 3
                    and domain_stats.observations >= self._config.min_observations
                ):
                    overrides[criterion.name] = max(
                        overrides.get(criterion.name, criterion.threshold),
                        criterion.threshold + self._config.model_threshold_boost,
                    )
            if criterion.name in overrides:
                uncapped = overrides[criterion.name]
                capped = self._cap_delta(
                    criterion.threshold,
                    uncapped,
                    self._config.max_threshold_delta,
                )
                capped = min(0.98, max(0.5, capped))
                overrides[criterion.name] = capped
                threshold_metrics[criterion.name] = {
                    "base": criterion.threshold,
                    "target": uncapped,
                    "capped": capped,
                }
        self._last_adaptation_metrics["thresholds"] = threshold_metrics
        return overrides

    def get_weight_overrides(self, *, criteria: list[Criterion], domain: str) -> dict[str, float]:
        overrides: dict[str, float] = {}
        stats = self._state.domain_stats.get(domain)
        if not stats or stats.observations < self._config.min_observations:
            return overrides
        weight_metrics: dict[str, dict[str, float]] = {}
        for criterion in criteria:
            failures = stats.criterion_failures.get(criterion.name, 0)
            if not failures or self._decayed_failure(failures) < 3:
                continue
            uncapped = criterion.weight + self._config.domain_weight_boost
            capped = self._cap_delta(criterion.weight, uncapped, self._config.max_weight_delta)
            overrides[criterion.name] = capped
            weight_metrics[criterion.name] = {
                "base": criterion.weight,
                "target": uncapped,
                "capped": capped,
            }
        if weight_metrics:
            self._last_adaptation_metrics["weights"] = weight_metrics
        return overrides

    def get_strategy_overrides(self, failed_criteria: list[str]) -> dict[str, str]:
        best = self.get_best_repair_strategy()
        if not best:
            return {}
        capped_count = max(
            0,
            int(round(len(failed_criteria) * min(1.0, self._config.max_repair_strategy_bias))),
        )
        selected = sorted(failed_criteria)[:capped_count]
        self._last_adaptation_metrics["repair_bias"] = {
            "strategy": best,
            "criteria_total": len(failed_criteria),
            "criteria_biased": len(selected),
            "bias_cap": self._config.max_repair_strategy_bias,
        }
        return {criterion: best for criterion in selected}

    def get_adaptation_readiness(self, *, model: str, domain: str) -> dict[str, object]:
        model_stats = self._state.model_stats.get(model)
        domain_stats = self._state.domain_stats.get(domain)
        return {
            "model_observations": model_stats.observations if model_stats else 0,
            "domain_observations": domain_stats.observations if domain_stats else 0,
            "min_observations": self._config.min_observations,
            "ready": bool(
                model_stats
                and domain_stats
                and model_stats.observations >= self._config.min_observations
                and domain_stats.observations >= self._config.min_observations
            ),
        }

    def get_adaptation_metrics(self) -> dict[str, object]:
        return dict(self._last_adaptation_metrics)

    def get_decay_analytics(self, *, model: str, domain: str) -> dict[str, object]:
        model_stats = self._state.model_stats.get(model)
        domain_stats = self._state.domain_stats.get(domain)
        model_raw = model_stats.failed_criteria_total if model_stats else 0.0
        domain_raw = domain_stats.failed_criteria_total if domain_stats else 0.0
        return {
            "model_failed_raw": model_raw,
            "model_failed_decayed": self._decayed_failures_total(model_stats),
            "domain_failed_raw": domain_raw,
            "domain_failed_decayed": self._decayed_failures_total(domain_stats),
            "failure_decay_lambda": self._config.failure_decay_lambda,
        }

    def prune_stale_entries(self, *, max_age_s: float) -> None:
        cutoff = self._now() - max_age_s
        for stats in self._state.model_stats.values():
            stats.criterion_failures = {
                key: value
                for key, value in stats.criterion_failures.items()
                if not value.last_ts or value.last_ts >= cutoff
            }
        for stats in self._state.domain_stats.values():
            stats.criterion_failures = {
                key: value
                for key, value in stats.criterion_failures.items()
                if not value.last_ts or value.last_ts >= cutoff
            }
        for name in list(self._state.repair_stats.keys()):
            stats = self._state.repair_stats[name]
            if stats.last_attempt_ts and stats.last_attempt_ts < cutoff:
                del self._state.repair_stats[name]
        if self._config.autosave:
            self._storage.save_sync(self._state)

    def _evaluation_confidence(self, evaluation: EvaluationResult) -> float:
        if not evaluation.results:
            return 0.0
        total = sum(result.confidence for result in evaluation.results)
        return total / max(1, len(evaluation.results))

    def _record_evaluation(
        self,
        *,
        model: str,
        domain: str,
        criteria: list[Criterion],
        evaluation: EvaluationResult,
        stability_score: float,
    ) -> None:
        model_stats = self._state.model_stats.setdefault(model, ModelStats())
        domain_stats = self._state.domain_stats.setdefault(domain, DomainStats())
        criteria_count = len(criteria)
        failed_count = len(evaluation.failed)

        evaluation_confidence = self._evaluation_confidence(evaluation)
        update_weight = max(0.0, evaluation_confidence * stability_score)
        if update_weight < self._config.min_update_weight:
            self._last_adaptation_metrics["memory_confidence"] = {
                "evaluation_confidence": evaluation_confidence,
                "stability_score": stability_score,
                "update_weight": update_weight,
                "skipped": True,
            }
            return

        model_stats.observations += 1
        model_stats.evaluations += update_weight
        model_stats.criteria_total += criteria_count * update_weight
        model_stats.failed_criteria_total += failed_count * update_weight

        domain_stats.observations += 1
        domain_stats.evaluations += update_weight
        domain_stats.criteria_total += criteria_count * update_weight
        domain_stats.failed_criteria_total += failed_count * update_weight

        for name in evaluation.failed:
            model_failure = model_stats.criterion_failures.setdefault(name, FailureStats())
            model_failure.count += update_weight
            model_failure.last_ts = self._now()
            domain_failure = domain_stats.criterion_failures.setdefault(name, FailureStats())
            domain_failure.count += update_weight
            domain_failure.last_ts = self._now()

        criteria_map = {criterion.name: criterion for criterion in criteria}
        for result in evaluation.results:
            base_threshold = criteria_map.get(result.name).threshold if result.name in criteria_map else result.threshold
            stats = self._state.threshold_stats.setdefault(result.name, ThresholdStats())
            update_threshold_stats(
                stats,
                score=result.score,
                passed=result.passed,
                base_threshold=base_threshold,
                weight=update_weight,
            )
            history = self._state.threshold_history.setdefault(result.name, [])
            if stats.recommended_threshold is not None:
                history.append(stats.recommended_threshold)
                if len(history) > self._config.max_threshold_history:
                    history[:] = history[-self._config.max_threshold_history :]
        self._last_adaptation_metrics["memory_confidence"] = {
            "evaluation_confidence": evaluation_confidence,
            "stability_score": stability_score,
            "update_weight": update_weight,
            "skipped": False,
        }

    def _record_repair(self, *, strategies: Iterable[str], success: bool, weight: float) -> None:
        for strategy in strategies:
            stats = self._state.repair_stats.setdefault(strategy, RepairStrategyStats())
            stats.observations += 1
            stats.attempts += weight
            stats.last_attempt_ts = self._now()
            if success:
                stats.successes += weight
                stats.last_success_ts = self._now()
            stats.success_rate = stats.successes / max(1, stats.attempts)

    def _record_section_outcome(
        self,
        *,
        section_ids_all: list[str],
        failed_section_ids: list[str],
        attempt: int,
        rollback: bool = False,
    ) -> None:
        failed_set = set(failed_section_ids)
        for section_id in section_ids_all:
            stats = self._state.section_stats.setdefault(section_id, SectionStabilityStats())
            if section_id in failed_set:
                stats.last_failed_attempt = attempt
                if rollback:
                    stats.rollback_count += 1
                continue
            if stats.last_failed_attempt is not None and stats.stable_after_attempt is None:
                stats.stable_after_attempt = attempt
                stats.last_stable_attempt = attempt

    def _record_rag_signals(
        self,
        *,
        model: str,
        domain: str,
        grounding_score: float,
        hallucination_score: float,
        citation_accuracy: float,
        tool_correctness: float | None,
        weight: float,
    ) -> None:
        model_stats = self._state.rag_model_stats.setdefault(model, RagModelStats())
        domain_stats = self._state.rag_domain_stats.setdefault(domain, RagDomainStats())
        model_stats.observations += 1
        domain_stats.observations += 1
        model_stats.last_ts = self._now()
        domain_stats.last_ts = self._now()

        if grounding_score < self._config.rag_grounding_threshold:
            model_stats.grounding_failures += weight
            domain_stats.grounding_failures += weight
        if hallucination_score > self._config.rag_hallucination_threshold:
            model_stats.hallucination_count += weight
        if citation_accuracy < self._config.rag_citation_threshold:
            model_stats.citation_failures += weight
            domain_stats.citation_failures += weight
        if tool_correctness is not None and tool_correctness < self._config.rag_tool_threshold:
            model_stats.tool_failures += weight
