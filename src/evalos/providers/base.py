from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from evalos.types import StreamEvent


class BaseProvider(ABC):
    name: str

    @property
    def last_attempts(self) -> int:
        return 1

    @abstractmethod
    async def generate(self, *, model: str, messages: list[dict], **kwargs: Any) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def stream(self, *, model: str, messages: list[dict]) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError
