from __future__ import annotations

import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import anyio

from evalos.config import RetryConfig
from evalos.errors import RetryError


@dataclass(slots=True)
class RetryOutcome:
    value: object
    attempts: int


async def retry_async(
    func: Callable[[], Awaitable[object]],
    *,
    config: RetryConfig,
    retry_on: tuple[type[Exception], ...],
) -> RetryOutcome:
    last_error: Exception | None = None

    for attempt in range(1, config.max_attempts + 1):
        try:
            value = await func()
            return RetryOutcome(value=value, attempts=attempt)
        except retry_on as exc:
            last_error = exc
            if attempt >= config.max_attempts:
                break
            delay = min(
                config.max_delay_s,
                config.base_delay_s * (2 ** (attempt - 1)),
            )
            delay += random.uniform(0, config.jitter_s)
            await anyio.sleep(delay)

    raise RetryError("Retries exhausted") from last_error
