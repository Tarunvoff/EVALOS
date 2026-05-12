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
            model=self._config.model, messages=self._messages(query)
        )
        retry_total += self._provider.last_attempts - 1
        text, usage = _extract_text_and_usage(response)
        evaluation = await self._evaluator.evaluate(
            query=query, response_text=text, criteria=criteria
        )
        retry_total += self._provider.last_attempts - 1

        repairs: list[RepairRecord] = []
        current_text = text
        current_eval = evaluation

        for attempt in range(1, self._config.max_repairs + 1):
            if current_eval.passed:
                break
            if self._config.repair_strategy != "selective":
                break

            repaired = await self._repair.repair(
                query=query,
                response_text=current_text,
                failed=current_eval.failed,
                criteria=criteria,
            )
            retry_total += self._provider.last_attempts - 1
            repairs.append(
                RepairRecord(
                    attempt=attempt,
                    failed_criteria=current_eval.failed,
                    repaired_text=repaired,
                )
            )
            current_text = repaired
            current_eval = await self._evaluator.evaluate(
                query=query,
                response_text=current_text,
                criteria=criteria,
            )
            retry_total += self._provider.last_attempts - 1

        latency_ms = (time.perf_counter() - start) * 1000.0
        metrics = Metrics(
            provider=self._config.provider,
            model=self._config.model,
            latency_ms=latency_ms,
            retries=retry_total,
            repairs=len(repairs),
            usage=usage,
            criteria_count=len(criteria),
            failed_criteria_count=len(current_eval.failed) if current_eval else 0,
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

        stream = self._provider.stream(model=self._config.model, messages=self._messages(query))
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
