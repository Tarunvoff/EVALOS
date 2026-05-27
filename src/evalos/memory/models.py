from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from pydantic import ConfigDict


class FailureStats(BaseModel):
    count: float = 0.0
    last_ts: float | None = None


class ModelStats(BaseModel):
    observations: int = 0
    evaluations: float = 0.0
    failed_criteria_total: float = 0.0
    criteria_total: float = 0.0
    criterion_failures: dict[str, FailureStats] = Field(default_factory=dict)

    @field_validator("criterion_failures", mode="before")
    @classmethod
    def _normalize_failures(cls, value: object) -> object:
        if isinstance(value, dict) and value:
            first = next(iter(value.values()))
            if isinstance(first, (int, float)):
                return {key: FailureStats(count=float(count)) for key, count in value.items()}
        return value


class DomainStats(BaseModel):
    observations: int = 0
    evaluations: float = 0.0
    failed_criteria_total: float = 0.0
    criteria_total: float = 0.0
    criterion_failures: dict[str, FailureStats] = Field(default_factory=dict)

    @field_validator("criterion_failures", mode="before")
    @classmethod
    def _normalize_failures(cls, value: object) -> object:
        if isinstance(value, dict) and value:
            first = next(iter(value.values()))
            if isinstance(first, (int, float)):
                return {key: FailureStats(count=float(count)) for key, count in value.items()}
        return value


class RepairStrategyStats(BaseModel):
    observations: int = 0
    attempts: float = 0.0
    successes: float = 0.0
    success_rate: float = 0.0
    last_success_ts: float | None = None
    last_attempt_ts: float | None = None


class SectionStabilityStats(BaseModel):
    stable_after_attempt: int | None = None
    rollback_count: int = 0
    last_failed_attempt: int | None = None
    last_stable_attempt: int | None = None


class ThresholdStats(BaseModel):
    observations: int = 0
    sample_count: float = 0.0
    avg_score: float = 0.0
    failure_count: float = 0.0
    recommended_threshold: float | None = None


class MemoryState(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    memory_version: int = Field(default=2, alias="version")
    model_stats: dict[str, ModelStats] = Field(default_factory=dict)
    domain_stats: dict[str, DomainStats] = Field(default_factory=dict)
    repair_stats: dict[str, RepairStrategyStats] = Field(default_factory=dict)
    section_stats: dict[str, SectionStabilityStats] = Field(default_factory=dict)
    threshold_stats: dict[str, ThresholdStats] = Field(default_factory=dict)
    threshold_history: dict[str, list[float]] = Field(default_factory=dict)
