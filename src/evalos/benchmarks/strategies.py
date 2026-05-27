from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any

from evalos.benchmarks.models import BenchmarkCase, BenchmarkConfig, StrategyRun, StrategyName
from evalos.benchmarks.scoring import build_metrics
from evalos.config import PipelineConfig, RetryConfig
from evalos.criteria import CriteriaGenerator
from evalos.eval import Evaluator
from evalos.providers.base import BaseProvider
from evalos.providers.resilient import ResilientProvider
from evalos.pipeline import Pipeline, ProviderRegistry
from evalos.rag.agent_eval import AgentReliabilityEvaluator
from evalos.rag.citation import CitationEvaluator
from evalos.rag.grounding import GroundingEvaluator
from evalos.rag.hallucination import HallucinationDetector
from evalos.rag.retriever import normalize_documents
from evalos.rag.validation import validate_agent_trace
from evalos.types import EvaluationResult, Usage


class BenchmarkStrategy:
    name: StrategyName

    async def run(
        self,
        *,
        case: BenchmarkCase,
        criteria: list,
    ) -> StrategyRun:
        raise NotImplementedError


class _BaseStrategy(BenchmarkStrategy):
    def __init__(self, config: BenchmarkConfig) -> None:
        self._config = config
        self._provider = _build_provider(config)
        self._pipeline_config = PipelineConfig(
            model=config.model,
            provider=config.provider,
            max_repairs=config.max_repairs,
            evaluation_strictness=config.strictness,
        )
        self._criteria_generator = CriteriaGenerator(self._provider, self._pipeline_config)
        self._evaluator = Evaluator(self._provider, self._pipeline_config)
        self._grounding = GroundingEvaluator()
        self._hallucination = HallucinationDetector()
        self._citation = CitationEvaluator()
        self._agent_eval = AgentReliabilityEvaluator()

    async def _generate(self, *, prompt: str, seed: int | None = None) -> tuple[str, Usage, dict[str, Any]]:
        response = await self._provider.generate(
            model=self._config.model,
            messages=_messages(prompt),
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
            seed=seed,
        )
        text, usage = _extract_text_and_usage(response)
        return text, usage, response

    async def _evaluate(
        self, *, prompt: str, text: str, criteria: list
    ) -> EvaluationResult:
        return await self._evaluator.evaluate(
            query=prompt,
            response_text=text,
            criteria=criteria,
        )

    def _rag_metrics(
        self, *, case: BenchmarkCase, text: str
    ) -> tuple[float, float, float, float]:
        documents = normalize_documents(case.retrieved_documents or [])
        grounding_score = 0.0
        hallucination_rate = 0.0
        citation_precision = 0.0
        tool_correctness = 0.0
        if documents:
            grounding = self._grounding.evaluate(
                retrieved_documents=documents,
                generated_response=text,
                citations=case.citations,
                claim_map=case.claim_map,
                dependencies=case.claim_dependencies,
            )
            hallucination = self._hallucination.evaluate(grounding=grounding)
            citation = self._citation.evaluate(
                retrieved_documents=documents,
                citations=case.citations,
                grounding=grounding,
                claim_map=case.claim_map,
            )
            grounding_score = grounding.grounding_score
            hallucination_rate = hallucination.hallucination_score
            citation_precision = citation.citation_precision
        if case.agent_trace:
            validation = validate_agent_trace(agent_trace=case.agent_trace)
            if validation.valid:
                tool_correctness = self._agent_eval.evaluate(
                    trace=validation.trace
                ).tool_correctness_score
        return grounding_score, hallucination_rate, citation_precision, tool_correctness


class VanillaStrategy(_BaseStrategy):
    name: StrategyName = "vanilla"

    async def run(
        self, *, case: BenchmarkCase, criteria: list
    ) -> StrategyRun:
        start = time.perf_counter()
        text, usage, response = await self._generate(
            prompt=case.prompt,
            seed=self._config.seed,
        )
        evaluation = await self._evaluate(prompt=case.prompt, text=text, criteria=criteria)
        grounding, hallucination, citation_precision, tool_correctness = self._rag_metrics(
            case=case,
            text=text,
        )
        latency_ms = (time.perf_counter() - start) * 1000.0
        metrics = build_metrics(
            evaluation=evaluation,
            grounding_score=grounding,
            hallucination_rate=hallucination,
            citation_precision=citation_precision,
            repair_efficiency=0.0,
            rollback_frequency=0.0,
            tool_correctness_score=tool_correctness,
            usage=usage,
            latency_ms=latency_ms,
        )
        return StrategyRun(
            strategy=self.name,
            case_id=case.id,
            domain=case.domain,
            prompt=case.prompt,
            output_text=text,
            initial_text=text,
            evaluation_score=evaluation.weighted_score,
            evaluation_passed=evaluation.passed,
            failed_criteria=evaluation.failed,
            metrics=metrics,
            raw_response=response,
        )


class RetryStrategy(_BaseStrategy):
    name: StrategyName = "retry"

    async def run(
        self, *, case: BenchmarkCase, criteria: list
    ) -> StrategyRun:
        best_eval: EvaluationResult | None = None
        best_text = ""
        best_usage = Usage()
        best_response: dict[str, Any] | None = None
        retries = 0
        start = time.perf_counter()
        for attempt in range(1, self._config.retry_attempts + 1):
            seed = self._config.seed + attempt
            text, usage, response = await self._generate(prompt=case.prompt, seed=seed)
            evaluation = await self._evaluate(prompt=case.prompt, text=text, criteria=criteria)
            retries = attempt - 1
            if not best_eval or evaluation.weighted_score > best_eval.weighted_score:
                best_eval = evaluation
                best_text = text
                best_usage = usage
                best_response = response
            if evaluation.passed:
                break
        evaluation = best_eval or await self._evaluate(
            prompt=case.prompt, text=best_text, criteria=criteria
        )
        grounding, hallucination, citation_precision, tool_correctness = self._rag_metrics(
            case=case,
            text=best_text,
        )
        latency_ms = (time.perf_counter() - start) * 1000.0
        metrics = build_metrics(
            evaluation=evaluation,
            grounding_score=grounding,
            hallucination_rate=hallucination,
            citation_precision=citation_precision,
            repair_efficiency=0.0,
            rollback_frequency=0.0,
            tool_correctness_score=tool_correctness,
            usage=best_usage,
            latency_ms=latency_ms,
        )
        return StrategyRun(
            strategy=self.name,
            case_id=case.id,
            domain=case.domain,
            prompt=case.prompt,
            output_text=best_text,
            initial_text=best_text,
            evaluation_score=evaluation.weighted_score,
            evaluation_passed=evaluation.passed,
            failed_criteria=evaluation.failed,
            metrics=metrics,
            raw_response=best_response,
            retries=retries,
        )


class BestOfNStrategy(_BaseStrategy):
    name: StrategyName = "best_of_n"

    async def run(
        self, *, case: BenchmarkCase, criteria: list
    ) -> StrategyRun:
        best_eval: EvaluationResult | None = None
        best_text = ""
        best_usage = Usage()
        best_response: dict[str, Any] | None = None
        start = time.perf_counter()
        for attempt in range(self._config.best_of_n):
            seed = self._config.seed + attempt
            text, usage, response = await self._generate(prompt=case.prompt, seed=seed)
            evaluation = await self._evaluate(prompt=case.prompt, text=text, criteria=criteria)
            if not best_eval or evaluation.weighted_score > best_eval.weighted_score:
                best_eval = evaluation
                best_text = text
                best_usage = usage
                best_response = response
        evaluation = best_eval or await self._evaluate(
            prompt=case.prompt, text=best_text, criteria=criteria
        )
        grounding, hallucination, citation_precision, tool_correctness = self._rag_metrics(
            case=case,
            text=best_text,
        )
        latency_ms = (time.perf_counter() - start) * 1000.0
        metrics = build_metrics(
            evaluation=evaluation,
            grounding_score=grounding,
            hallucination_rate=hallucination,
            citation_precision=citation_precision,
            repair_efficiency=0.0,
            rollback_frequency=0.0,
            tool_correctness_score=tool_correctness,
            usage=best_usage,
            latency_ms=latency_ms,
        )
        return StrategyRun(
            strategy=self.name,
            case_id=case.id,
            domain=case.domain,
            prompt=case.prompt,
            output_text=best_text,
            initial_text=best_text,
            evaluation_score=evaluation.weighted_score,
            evaluation_passed=evaluation.passed,
            failed_criteria=evaluation.failed,
            metrics=metrics,
            raw_response=best_response,
        )


class EvalOSStrategy(_BaseStrategy):
    name: StrategyName = "evalos"

    async def run(
        self, *, case: BenchmarkCase, criteria: list
    ) -> StrategyRun:
        pipeline = Pipeline(
            model=self._config.model,
            provider=self._config.provider,
            max_repairs=self._config.max_repairs,
            evaluation_strictness=self._config.strictness,
        )
        start = time.perf_counter()
        response = await pipeline.generate(
            query=case.prompt,
            optimize_for=case.optimize_for,
            retrieved_documents=case.retrieved_documents,
            citations=case.citations,
            agent_trace=case.agent_trace,
            claim_map=case.claim_map,
            claim_dependencies=case.claim_dependencies,
            criteria_override=criteria,
        )
        latency_ms = (time.perf_counter() - start) * 1000.0
        metrics = build_metrics(
            evaluation=response.evaluation,
            grounding_score=response.metrics.grounding_score,
            hallucination_rate=response.metrics.hallucination_rate,
            citation_precision=response.metrics.citation_precision,
            repair_efficiency=response.metrics.repair_efficiency,
            rollback_frequency=response.metrics.rollback_frequency,
            tool_correctness_score=response.metrics.tool_correctness_score,
            usage=response.metrics.usage,
            latency_ms=latency_ms,
        )
        return StrategyRun(
            strategy=self.name,
            case_id=case.id,
            domain=case.domain,
            prompt=case.prompt,
            output_text=response.text,
            initial_text=response.initial_text,
            evaluation_score=response.metrics.quality_after,
            evaluation_passed=response.evaluation.passed if response.evaluation else False,
            failed_criteria=response.evaluation.failed if response.evaluation else [],
            metrics=metrics,
            raw_trace=response.trace.model_dump(mode="json") if response.trace else None,
            raw_response=response.raw,
            retries=response.metrics.retries,
            repairs=response.metrics.repairs,
        )


def strategy_registry(config: BenchmarkConfig) -> dict[StrategyName, BenchmarkStrategy]:
    return {
        "vanilla": VanillaStrategy(config),
        "retry": RetryStrategy(config),
        "best_of_n": BestOfNStrategy(config),
        "evalos": EvalOSStrategy(config),
    }


def _messages(prompt: str) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]


def _extract_text_and_usage(response: dict) -> tuple[str, Usage]:
    message = response["choices"][0]["message"]["content"]
    usage = response.get("usage") or {}
    return (
        message,
        Usage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        ),
    )


def _build_provider(config: BenchmarkConfig) -> BaseProvider:
    retry = RetryConfig(max_attempts=1)
    provider = ProviderRegistry.get(config.provider)
    return ResilientProvider(provider, timeout_s=30.0, retry=retry)


def ensure_strategy_names(items: Iterable[str]) -> list[StrategyName]:
    return [item.strip() for item in items if item.strip()]
