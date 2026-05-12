from __future__ import annotations

from collections.abc import AsyncIterator

from evalos.types import StreamEvent


async def drain_stream(stream: AsyncIterator[StreamEvent]) -> list[StreamEvent]:
    events: list[StreamEvent] = []
    async for event in stream:
        events.append(event)
    return events
