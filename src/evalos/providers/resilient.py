from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import anyio

from evalos.config import RetryConfig
from evalos.errors import ProviderError, TimeoutError as EvalosTimeoutError
from evalos.providers.base import BaseProvider
from evalos.retry import RetryOutcome, retry_async
from evalos.types import StreamEvent


class ResilientProvider(BaseProvider):
    def __init__(self, inner: BaseProvider, *, timeout_s: float, retry: RetryConfig) -> None:
        self._inner = inner
        self._timeout_s = timeout_s
        self._retry = retry
        self.name = inner.name
        self._last_attempts = 1

    @property
    def last_attempts(self) -> int:
        return self._last_attempts

    async def generate(self, *, model: str, messages: list[dict], **kwargs: Any) -> dict:
        async def _call() -> dict:
            try:
                with anyio.fail_after(self._timeout_s):
                    return await self._inner.generate(model=model, messages=messages, **kwargs)
            except TimeoutError as exc:
                raise EvalosTimeoutError("Provider call timed out") from exc
            except Exception as exc:
                raise ProviderError("Provider call failed") from exc

        outcome = await retry_async(
            _call, config=self._retry, retry_on=(ProviderError, EvalosTimeoutError)
        )
        self._last_attempts = outcome.attempts
        return outcome.value

    async def stream(self, *, model: str, messages: list[dict]) -> AsyncIterator[StreamEvent]:
        self._last_attempts = 1
        try:
            stream = self._inner.stream(model=model, messages=messages)
            async for event in stream:
                yield event
        except TimeoutError as exc:
            raise EvalosTimeoutError("Provider stream timed out") from exc
        except Exception as exc:
            raise ProviderError("Provider stream failed") from exc
