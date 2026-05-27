from __future__ import annotations

import json

from pydantic import BaseModel

from evalos.config import PipelineConfig
from evalos.errors import EvaluationError
from evalos.providers.base import BaseProvider
from evalos.types import Criterion, CriterionResult, EvaluationResult, Section
from evalos.utils import extract_json


class _EvalPayload(BaseModel):
    results: list[CriterionResult]


class Evaluator:
    def __init__(self, provider: BaseProvider, config: PipelineConfig) -> None:
        self._provider = provider
        self._config = config

    async def evaluate(
        self,
        *,
        query: str,
        response_text: str,
        criteria: list[Criterion],
        strictness_override: str | None = None,
        threshold_overrides: dict[str, float] | None = None,
        weight_overrides: dict[str, float] | None = None,
    ) -> EvaluationResult:
        model = self._config.eval_model or self._config.model
        sections = _split_sections(response_text)
        strictness = strictness_override or self._config.evaluation_strictness
        prompt = self._build_prompt(query, response_text, criteria, sections, strictness)
        messages = [
            {"role": "system", "content": "You are an adversarial evaluator."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self._provider.generate(
                model=model,
                messages=messages,
                temperature=0.0,
            )
            content = response["choices"][0]["message"]["content"]
            payload = extract_json(content)
            parsed = _EvalPayload.model_validate(payload)
            thresholds = {
                criterion.name: _adjust_threshold(
                    criterion.threshold,
                    strictness,
                    self._config.strict_mode,
                )
                for criterion in criteria
            }
            if threshold_overrides:
                for name, value in threshold_overrides.items():
                    thresholds[name] = max(thresholds.get(name, value), value)
            weights = {
                criterion.name: weight_overrides.get(criterion.name, criterion.weight)
                if weight_overrides
                else criterion.weight
                for criterion in criteria
            }
            severities = {criterion.name: criterion.severity for criterion in criteria}
            normalized: list[CriterionResult] = []
            failed: list[str] = []
            weighted_total = 0.0
            weighted_score = 0.0

            for result in parsed.results:
                threshold = thresholds.get(result.name, 1.0)
                passed = result.score >= threshold
                weight = weights.get(result.name, 1.0)
                severity = severities.get(result.name, "medium")
                normalized_reason = _ensure_reason(result)
                normalized.append(
                    result.model_copy(
                        update={
                            "passed": passed,
                            "weight": weight,
                            "severity": severity,
                            "threshold": threshold,
                            "reason": normalized_reason,
                        }
                    )
                )
                if not passed:
                    failed.append(result.name)
                weighted_total += weight
                weighted_score += result.score * weight
            pass_rate = len([r for r in normalized if r.passed]) / max(1, len(normalized))
            final_score = weighted_score / max(1.0, weighted_total)

            if self._config.strict_mode and not failed and final_score < 0.95:
                weakest = min(normalized, key=lambda item: item.score)
                failed = [weakest.name]
                normalized = [
                    item
                    if item.name != weakest.name
                    else item.model_copy(update={"passed": False})
                    for item in normalized
                ]
                pass_rate = len([r for r in normalized if r.passed]) / max(1, len(normalized))
            return EvaluationResult(
                results=normalized,
                passed=len(failed) == 0,
                failed=failed,
                weighted_score=final_score,
                pass_rate=pass_rate,
                sections=sections,
            )
        except Exception as exc:
            raise EvaluationError("Evaluation failed") from exc

    def _build_prompt(
        self,
        query: str,
        response_text: str,
        criteria: list[Criterion],
        sections: list[Section],
        strictness: str,
    ) -> str:
        strict_mode = self._config.strict_mode
        payload = {
            "query": query,
            "response": response_text,
            "criteria": [criterion.model_dump() for criterion in criteria],
            "sections": [section.model_dump() for section in sections],
            "strictness": strictness,
            "strict_mode": strict_mode,
            "output_format": (
                "JSON object {results: [{name, score, passed, rationale, reason, "
                "affected_section, suggested_strategy, confidence}]}"
            ),
            "score_scale": "0.0-1.0",
        }
        return (
            "You are a strict, adversarial evaluator. "
            "Actively search for weaknesses and shallow reasoning. "
            "Fail generic or surface-level answers. "
            "Require technical depth, concrete concepts, and relevant examples. "
            "Penalize missing architectural details, omitted key concepts, or lack of examples. "
            "Penalize vague claims without justification or evidence. "
            "If score <= 0.95 you MUST provide at least one improvement opportunity in reason. "
            "Set passed true only when score >= threshold. "
            "Identify affected_section by id when failing. "
            "Suggest a repair strategy per failed criterion. "
            "Return ONLY JSON.\n\n"
            f"{json.dumps(payload, ensure_ascii=True)}"
        )


def _split_sections(text: str) -> list[Section]:
    sections: list[Section] = []
    cursor = 0
    parts = text.split("\n\n")

    for index, part in enumerate(parts, start=1):
        start = cursor
        end = cursor + len(part)
        sections.append(Section(id=f"s{index}", text=part, start=start, end=end))
        cursor = end + 2

    return sections


def _adjust_threshold(base: float, strictness: str, strict_mode: bool) -> float:
    delta = {
        "relaxed": -0.05,
        "balanced": 0.0,
        "strict": 0.08,
        "adversarial": 0.12,
    }.get(strictness, 0.0)
    if strict_mode:
        delta += 0.05
    return min(0.98, max(0.5, base + delta))


def _ensure_reason(result: CriterionResult) -> str | None:
    if result.score > 0.95:
        return result.reason
    if result.reason:
        return result.reason
    return "Identify at least one concrete improvement opportunity."
