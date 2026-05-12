from __future__ import annotations

import json

import pytest

from evalos.pipeline import Pipeline
from evalos.providers.base import BaseProvider
from evalos.types import StreamEvent


class FakeProvider(BaseProvider):
    name = "fake"

    async def generate(self, *, model: str, messages: list[dict]) -> dict:
        system = messages[0]["content"]
        user = messages[1]["content"]

        if "generate evaluation criteria" in system:
            payload = [
                {
                    "name": "clarity",
                    "description": "Clear and well-structured",
                    "weight": 1.0,
                    "threshold": 0.7,
                    "severity": "medium",
                }
            ]
            return {"choices": [{"message": {"content": json.dumps(payload)}}]}

        if "strict evaluator" in system:
            score = 0.5
            if "REPAIRED" in user:
                score = 0.9
            payload = {
                "results": [
                    {
                        "name": "clarity",
                        "score": score,
                        "passed": score >= 0.7,
                        "rationale": "ok",
                        "confidence": 0.9,
                        "reason": "needs tightening",
                        "affected_section": "s1",
                        "suggested_strategy": "simplify wording and structure",
                    }
                ]
            }
            return {"choices": [{"message": {"content": json.dumps(payload)}}]}

        if "repair only failed criteria" in system:
            payload = [
                {
                    "section_id": "s1",
                    "revised_text": "REPAIRED",
                    "criterion": "clarity",
                    "strategy": "simplify wording and structure",
                }
            ]
            return {"choices": [{"message": {"content": json.dumps(payload)}}]}

        return {"choices": [{"message": {"content": "DRAFT"}}]}

    async def stream(self, *, model: str, messages: list[dict]):
        yield StreamEvent(type="text", data={"choices": [{"delta": {"content": "Hello "}}]})
        yield StreamEvent(type="text", data={"choices": [{"delta": {"content": "world"}}]})
        yield StreamEvent(type="done", data=None)


@pytest.mark.asyncio
async def test_pipeline_selective_repair():
    pipeline = Pipeline(model="test", provider_instance=FakeProvider())
    response = await pipeline.generate(query="hi", optimize_for=["clarity"])

    assert response.text == "REPAIRED"
    assert response.evaluation is not None
    assert response.evaluation.passed is True
    assert len(response.repairs) == 1


@pytest.mark.asyncio
async def test_pipeline_stream():
    pipeline = Pipeline(model="test", provider_instance=FakeProvider())
    events = []
    async for event in pipeline.stream(query="hi", optimize_for=["clarity"]):
        events.append(event)

    assert events[0].type == "text"
    assert any(event.type == "done" for event in events)
