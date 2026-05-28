from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import litellm

from evalos.errors import ProviderError
from evalos.providers.base import BaseProvider
from evalos.types import StreamEvent


class OllamaProvider(BaseProvider):
    name = "ollama"

    @staticmethod
    def _normalize_model(model: str) -> str:
        if model.startswith("ollama/"):
            return model
        return f"ollama/{model}"

    async def generate(self, *, model: str, messages: list[dict], **kwargs: Any) -> dict:
        try:
            response = await litellm.acompletion(
                model=self._normalize_model(model),
                messages=messages,
                **kwargs,
            )
        except Exception as exc:  # pragma: no cover - passthrough from provider
            raise ProviderError("Ollama generate failed") from exc
        return response

    async def stream(self, *, model: str, messages: list[dict]) -> AsyncIterator[StreamEvent]:
        try:
            stream = await litellm.acompletion(
                model=self._normalize_model(model),
                messages=messages,
                stream=True,
            )
        except Exception as exc:  # pragma: no cover
            raise ProviderError("Ollama stream failed") from exc

        async for chunk in stream:
            yield StreamEvent(type="text", data=chunk)

        yield StreamEvent(type="done", data=None)
