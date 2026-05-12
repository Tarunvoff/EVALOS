from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

import structlog

from evalos.config import PipelineConfig, RetryConfig
from evalos.criteria import CriteriaGenerator
from evalos.errors import ProviderError
from evalos.eval import Evaluator
from evalos.providers.base import BaseProvider
from evalos.providers.resilient import ResilientProvider
from evalos.repair import RepairEngine
from evalos.types import GenerationResponse, Metrics, RepairRecord, StreamEvent, Usage


class ProviderRegistry:
    _providers: dict[str, type[BaseProvider]] = {}

    @classmethod
    def get(cls, name: str) -> BaseProvider:
        provider_cls = cls._providers.get(name)
        if not provider_cls and name == "litellm":
            from evalos.providers.litellm import LiteLLMProvider

            provider_cls = LiteLLMProvider
            cls._providers[name] = provider_cls
        if not provider_cls:
            raise ValueError(f"Unknown provider: {name}")
        return provider_cls()


class Pipeline:
    def __init__(
        self,
        *,
        model: str,
        provider: str = "litellm",
        repair_strategy: str = "selective",
        max_repairs: int = 2,
        timeout_s: float = 30.0,
        retry: RetryConfig | None = None,
        eval_model: str | None = None,
        criteria_model: str | None = None,
        generation_model: str | None = None,
        repair_model: str | None = None,
        profile: str = "general",
        evaluation_strictness: str = "balanced",
        strict_mode: bool = False,
        provider_instance: BaseProvider | None = None,
    ) -> None:
        self._config = PipelineConfig(
            model=model,
            provider=provider,
            repair_strategy=repair_strategy,
            max_repairs=max_repairs,
            timeout_s=timeout_s,
            retry=retry or RetryConfig(),
            eval_model=eval_model,
            criteria_model=criteria_model,
            generation_model=generation_model,
            repair_model=repair_model,
            profile=profile,
            evaluation_strictness=evaluation_strictness,
            strict_mode=strict_mode,
        )
        base_provider = provider_instance or ProviderRegistry.get(provider)
        self._provider = ResilientProvider(
            base_provider,
            timeout_s=self._config.timeout_s,
            retry=self._config.retry,
        )
        self._criteria = CriteriaGenerator(self._provider, self._config)
        self._evaluator = Evaluator(self._provider, self._config)
        self._repair = RepairEngine(self._provider, self._config)
        self._logger = structlog.get_logger("evalos.pipeline")

    async def generate(self, *, query: str, optimize_for: list[str]) -> GenerationResponse:
        start = time.perf_counter()
        retry_total = 0
        criteria = await self._criteria.generate(query=query, optimize_for=optimize_for)
        retry_total += self._provider.last_attempts - 1

        response = await self._provider.generate(
            model=self._generation_model(), messages=self._messages(query)
        )
        retry_total += self._provider.last_attempts - 1
        text, usage = _extract_text_and_usage(response)
        evaluation = await self._evaluator.evaluate(
            query=query, response_text=text, criteria=criteria
        )
        retry_total += self._provider.last_attempts - 1
        quality_before = evaluation.weighted_score

        repairs: list[RepairRecord] = []
        current_text = text
        current_eval = evaluation

        for attempt in range(1, self._config.max_repairs + 1):
            if current_eval.passed:
                break
            if self._config.repair_strategy != "selective":
                break

            repaired, deltas, strategies, failed_sections, repair_tokens = await self._repair.repair(
                query=query,
                response_text=current_text,
                evaluation=current_eval,
                criteria=criteria,
                sections=current_eval.sections,
            )
            retry_total += self._provider.last_attempts - 1
            repairs.append(
                RepairRecord(
                    attempt=attempt,
                    failed_criteria=current_eval.failed,
                    repaired_text=repaired,
                    strategies=strategies,
                    failed_sections=failed_sections,
                    score_before=current_eval.weighted_score,
                    deltas=deltas,
                    repair_tokens=repair_tokens,
                    token_delta=repair_tokens,
                )
            )
            current_text = repaired
            current_eval = await self._evaluator.evaluate(
                query=query,
                response_text=current_text,
                criteria=criteria,
            )
            retry_total += self._provider.last_attempts - 1
            repairs[-1] = repairs[-1].model_copy(update={"score_after": current_eval.weighted_score})

            self._logger.info(
                "repair_applied",
                attempt=attempt,
                failed_criteria=repairs[-1].failed_criteria,
                strategies=repairs[-1].strategies,
                affected_sections=repairs[-1].failed_sections,
                score_before=repairs[-1].score_before,
                score_after=repairs[-1].score_after,
                token_delta=repairs[-1].token_delta,
            )

        latency_ms = (time.perf_counter() - start) * 1000.0
        quality_after = current_eval.weighted_score if current_eval else 0.0
        repair_gain = quality_after - quality_before
        repair_efficiency = repair_gain / max(1, len(repairs))
        token_efficiency = repair_gain / max(1, usage.total_tokens)
        repair_token_cost = sum(record.repair_tokens for record in repairs)
        estimated_full_retry_tokens = usage.total_tokens * len(repairs)
        tokens_saved_vs_retry = max(0.0, estimated_full_retry_tokens - repair_token_cost)
        metrics = Metrics(
            provider=self._config.provider,
            model=self._config.model,
            latency_ms=latency_ms,
            retries=retry_total,
            repairs=len(repairs),
            usage=usage,
            criteria_count=len(criteria),
            failed_criteria_count=len(current_eval.failed) if current_eval else 0,
            quality_before=quality_before,
            quality_after=quality_after,
            repair_gain=repair_gain,
            repair_efficiency=repair_efficiency,
            token_efficiency=token_efficiency,
            criteria_pass_rate=current_eval.pass_rate if current_eval else 0.0,
            weighted_quality_score=quality_after,
            repair_lineage=repairs,
            tokens_saved_vs_retry=tokens_saved_vs_retry,
            estimated_full_retry_tokens=estimated_full_retry_tokens,
            repair_token_cost=repair_token_cost,
            improvement_delta=repair_gain,
        )

        self._logger.info(
            "generation_complete",
            model=self._config.model,
            provider=self._config.provider,
            latency_ms=latency_ms,
            repairs=len(repairs),
            passed=current_eval.passed,
        )

        return GenerationResponse(
            text=current_text,
            raw=response,
            evaluation=current_eval,
            repairs=repairs,
            metrics=metrics,
        )

    async def stream(
        self, *, query: str, optimize_for: list[str]
    ) -> AsyncIterator[StreamEvent]:
        criteria = await self._criteria.generate(query=query, optimize_for=optimize_for)

        stream = self._provider.stream(
            model=self._generation_model(), messages=self._messages(query)
        )
        buffer: list[str] = []

        async for event in stream:
            if event.type == "text":
                delta = _extract_stream_delta(event.data)
                if delta:
                    buffer.append(delta)
                    yield StreamEvent(type="text", data=delta)
            if event.type == "done":
                break

        text = "".join(buffer)
        evaluation = await self._evaluator.evaluate(
            query=query, response_text=text, criteria=criteria
        )
        metrics = Metrics(
            provider=self._config.provider,
            model=self._config.model,
            latency_ms=0.0,
            retries=0,
            repairs=0,
            usage=Usage(),
            criteria_count=len(criteria),
            failed_criteria_count=len(evaluation.failed),
            quality_before=evaluation.weighted_score,
            quality_after=evaluation.weighted_score,
            criteria_pass_rate=evaluation.pass_rate,
            weighted_quality_score=evaluation.weighted_score,
        )

        yield StreamEvent(type="evaluation", data=evaluation)
        yield StreamEvent(type="metrics", data=metrics)
        yield StreamEvent(
            type="done",
            data=GenerationResponse(
                text=text,
                raw=None,
                evaluation=evaluation,
                repairs=[],
                metrics=metrics,
            ),
        )

    def _messages(self, query: str) -> list[dict[str, Any]]:
        return [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": query},
        ]

    def _generation_model(self) -> str:
        return self._config.generation_model or self._config.model

def _extract_text_and_usage(response: dict) -> tuple[str, Usage]:
    try:
        message = response["choices"][0]["message"]["content"]
    except Exception as exc:  # pragma: no cover - defensive
        raise ProviderError("Unexpected provider response shape") from exc

    usage = response.get("usage") or {}
    return (
        message,
        Usage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        ),
    )


def _extract_stream_delta(chunk: dict) -> str:
    try:
        delta = chunk["choices"][0].get("delta") or {}
        return delta.get("content") or ""
    except Exception:
        return ""
