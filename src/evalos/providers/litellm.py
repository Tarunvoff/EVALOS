from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import litellm

from evalos.errors import ProviderError
from evalos.types import StreamEvent
from evalos.providers.base import BaseProvider


class LiteLLMProvider(BaseProvider):
    name = "litellm"

    async def generate(self, *, model: str, messages: list[dict], **kwargs: Any) -> dict:
        try:
            response = await litellm.acompletion(model=model, messages=messages, **kwargs)
        except Exception as exc:  # pragma: no cover - passthrough from provider
            raise ProviderError("LiteLLM generate failed") from exc
        return response

    async def stream(self, *, model: str, messages: list[dict]) -> AsyncIterator[StreamEvent]:
        try:
            stream = await litellm.acompletion(model=model, messages=messages, stream=True)
        except Exception as exc:  # pragma: no cover
            raise ProviderError("LiteLLM stream failed") from exc

        async for chunk in stream:
            yield StreamEvent(type="text", data=chunk)

        yield StreamEvent(type="done", data=None)
