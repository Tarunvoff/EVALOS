from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RetryConfig(BaseModel):
    max_attempts: int = 3
    base_delay_s: float = 0.25
    max_delay_s: float = 4.0
    jitter_s: float = 0.1


class PipelineConfig(BaseModel):
    model: str
    provider: str = "litellm"
    repair_strategy: str = "selective"
    max_repairs: int = 2
    timeout_s: float = 30.0
    retry: RetryConfig = Field(default_factory=RetryConfig)
    eval_model: str | None = None
    criteria_model: str | None = None
    profile: str = "general"
    evaluation_strictness: Literal["relaxed", "balanced", "strict", "adversarial"] = "balanced"
    strict_mode: bool = False
    generation_model: str | None = None
    repair_model: str | None = None
    max_edit_distance_ratio: float | None = None
    repair_budget: int = 100
    oscillation_window: int = 5
    oscillation_threshold: float = 0.55
    evaluator_disagreement_threshold: float = 0.08
    ensemble_enabled: bool = True
    min_criterion_confidence: float = 0.35
    min_repair_improvement: float = 0.005
