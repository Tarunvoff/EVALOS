from __future__ import annotations

import json
from typing import Any

import pytest

from evalos.memory import Memory, MemoryConfig
from evalos.pipeline import Pipeline
from evalos.providers.base import BaseProvider
from evalos.types import Criterion, CriterionResult, EvaluationResult, Section, StreamEvent
from evalos.utils import extract_json


class AdaptiveFakeProvider(BaseProvider):
    name = "fake"

    async def generate(self, *, model: str, messages: list[dict], **kwargs) -> dict:
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

        if "adversarial evaluator" in system:
            payload = extract_json(user)
            response_text = payload.get("response", "")
            score = 0.6
            confidence = 0.9
            if "LOW_CONF" in response_text:
                confidence = 0.2
            if "REPAIRED" in response_text:
                score = 0.9
            if "WORSE" in response_text:
                score = 0.2
            result = {
                "name": "clarity",
                "score": score,
                "passed": score >= 0.7,
                "rationale": "ok",
                "confidence": confidence,
                "reason": "needs tightening",
                "affected_section": "s1",
                "suggested_strategy": "simplify wording and structure",
            }
            payload = {"results": [result]}
            return {"choices": [{"message": {"content": json.dumps(payload)}}]}

        if "repair only failed criteria" in system:
            payload = extract_json(user)
            response_text = payload.get("response", "")
            revised = "REPAIRED"
            if "ROLLBACK" in response_text:
                revised = "WORSE"
            deltas = [
                {
                    "section_id": "s1",
                    "revised_text": revised,
                    "criterion": "clarity",
                    "strategy": "simplify wording and structure",
                }
            ]
            return {"choices": [{"message": {"content": json.dumps(deltas)}}]}

        content = "A\n\nB"
        if "LOW_CONF" in user:
            content = "LOW_CONF"
        if "ROLLBACK" in user:
            content = "ROLLBACK"
        return {"choices": [{"message": {"content": content}}]}

    async def stream(self, *, model: str, messages: list[dict]):
        yield StreamEvent(type="text", data={"choices": [{"delta": {"content": "Hello "}}]})
        yield StreamEvent(type="text", data={"choices": [{"delta": {"content": "world"}}]})
        yield StreamEvent(type="done", data=None)


class FakeProviderOpenAI(AdaptiveFakeProvider):
    name = "openai"


class FakeProviderOllama(AdaptiveFakeProvider):
    name = "ollama"


class FakeProviderAnthropic(AdaptiveFakeProvider):
    name = "anthropic"


def _build_eval(score: float, confidence: float = 0.9) -> EvaluationResult:
    result = CriterionResult(
        name="clarity",
        score=score,
        passed=score >= 0.7,
        rationale="ok",
        confidence=confidence,
        reason="reason",
        affected_section="s1",
        suggested_strategy="simplify wording and structure",
    )
    return EvaluationResult(
        results=[result],
        passed=score >= 0.7,
        failed=[] if score >= 0.7 else ["clarity"],
        weighted_score=score,
        pass_rate=1.0 if score >= 0.7 else 0.0,
        sections=[Section(id="s1", text="A", start=0, end=1)],
    )


def _criteria() -> list[Criterion]:
    return [Criterion(name="clarity", description="Clear", weight=1.0, threshold=0.7)]


@pytest.mark.asyncio
async def test_repair_regression_and_locking(tmp_path: Any):
    memory = Memory(db_path=str(tmp_path / "memory.json"))
    pipeline = Pipeline(model="test", provider_instance=AdaptiveFakeProvider(), memory=memory)

    response = await pipeline.generate(query="hello", optimize_for=["clarity"])
    assert response.text == "REPAIRED\n\nB"

    rollback = await pipeline.generate(query="ROLLBACK", optimize_for=["clarity"])
    assert rollback.text == "ROLLBACK"


@pytest.mark.asyncio
async def test_adaptive_threshold_caps_and_decay(tmp_path: Any):
    config = MemoryConfig(
        storage_path=str(tmp_path / "memory.json"),
        max_threshold_delta=0.02,
        min_observations=1,
        failure_decay_lambda=0.001,
    )
    memory = Memory(config=config)
    evaluation = _build_eval(0.2)
    for _ in range(5):
        await memory.arecord_evaluation(
            model="m1",
            domain="general",
            criteria=_criteria(),
            evaluation=evaluation,
            stability_score=1.0,
        )
    overrides = memory.get_threshold_overrides(
        criteria=_criteria(),
        model="m1",
        domain="general",
    )
    assert overrides["clarity"] <= 0.72
    decay = memory.get_decay_analytics(model="m1", domain="general")
    assert decay["model_failed_decayed"] <= decay["model_failed_raw"]


@pytest.mark.asyncio
async def test_confidence_weighting(tmp_path: Any):
    memory = Memory(db_path=str(tmp_path / "memory.json"), config=MemoryConfig(min_update_weight=0.2))
    low_conf = _build_eval(0.2, confidence=0.1)
    await memory.arecord_evaluation(
        model="m1",
        domain="general",
        criteria=_criteria(),
        evaluation=low_conf,
        stability_score=0.5,
    )
    stats = memory.get_adaptation_readiness(model="m1", domain="general")
    assert stats["model_observations"] == 0


@pytest.mark.asyncio
async def test_cold_start_protection(tmp_path: Any):
    memory = Memory(db_path=str(tmp_path / "memory.json"), config=MemoryConfig(min_observations=3))
    evaluation = _build_eval(0.2)
    for _ in range(2):
        await memory.arecord_evaluation(
            model="m1",
            domain="general",
            criteria=_criteria(),
            evaluation=evaluation,
            stability_score=1.0,
        )
    overrides = memory.get_threshold_overrides(criteria=_criteria(), model="m1", domain="general")
    assert overrides == {}
    await memory.arecord_evaluation(
        model="m1",
        domain="general",
        criteria=_criteria(),
        evaluation=evaluation,
        stability_score=1.0,
    )
    overrides = memory.get_threshold_overrides(criteria=_criteria(), model="m1", domain="general")
    assert overrides


def test_memory_versioning_migration(tmp_path: Any):
    legacy = {
        "version": 1,
        "model_stats": {"m1": {"evaluations": 2, "failed_criteria_total": 1, "criteria_total": 2, "criterion_failures": {"clarity": 2}}},
        "domain_stats": {},
        "repair_stats": {},
        "section_stats": {},
        "threshold_stats": {},
        "threshold_history": {},
    }
    path = tmp_path / "memory.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")
    memory = Memory(db_path=str(path))
    state = memory.get_adaptation_metrics()
    assert memory._state.memory_version == 2
    assert "memory_confidence" in state or state == {}


@pytest.mark.asyncio
async def test_full_pipeline_stability(tmp_path: Any):
    memory = Memory(db_path=str(tmp_path / "memory.json"))
    pipeline = Pipeline(model="test", provider_instance=AdaptiveFakeProvider(), memory=memory)

    for _ in range(3):
        response = await pipeline.generate(query="hello", optimize_for=["clarity"])
        assert response.evaluation is not None
        assert response.evaluation.passed

    overrides = memory.get_threshold_overrides(
        criteria=_criteria(),
        model="test",
        domain="general",
    )
    if overrides:
        assert overrides["clarity"] <= 0.78


@pytest.mark.asyncio
async def test_multi_provider_consistency(tmp_path: Any):
    memory = Memory(db_path=str(tmp_path / "memory.json"))
    providers = [FakeProviderOpenAI(), FakeProviderOllama(), FakeProviderAnthropic()]
    results = []
    for provider in providers:
        pipeline = Pipeline(model="test", provider_instance=provider, memory=memory)
        response = await pipeline.generate(query="hello", optimize_for=["clarity"])
        results.append((response.text, response.evaluation.passed))
    assert len(set(results)) == 1


@pytest.mark.asyncio
async def test_observability_trace_and_metrics(tmp_path: Any):
    memory = Memory(db_path=str(tmp_path / "memory.json"))
    pipeline = Pipeline(model="test", provider_instance=AdaptiveFakeProvider(), memory=memory)
    response = await pipeline.generate(query="hello", optimize_for=["clarity"])
    trace = response.format_trace()
    assert "Repair Timeline Graph" in trace
    assert response.metrics.adaptation_metrics is not None


@pytest.mark.asyncio
async def test_long_run_stability(tmp_path: Any):
    config = MemoryConfig(
        storage_path=str(tmp_path / "memory.json"),
        max_threshold_delta=0.05,
        min_observations=1,
    )
    memory = Memory(config=config)
    pipeline = Pipeline(model="test", provider_instance=AdaptiveFakeProvider(), memory=memory)
    for _ in range(6):
        await pipeline.generate(query="hello", optimize_for=["clarity"])
    overrides = memory.get_threshold_overrides(criteria=_criteria(), model="test", domain="general")
    if overrides:
        assert overrides["clarity"] <= 0.75
