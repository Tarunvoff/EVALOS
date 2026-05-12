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
    ) -> EvaluationResult:
        model = self._config.eval_model or self._config.model
        sections = _split_sections(response_text)
        prompt = self._build_prompt(query, response_text, criteria, sections)
        messages = [
            {"role": "system", "content": "You are a strict evaluator."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self._provider.generate(model=model, messages=messages)
            content = response["choices"][0]["message"]["content"]
            payload = extract_json(content)
            parsed = _EvalPayload.model_validate(payload)
            thresholds = {criterion.name: criterion.threshold for criterion in criteria}
            weights = {criterion.name: criterion.weight for criterion in criteria}
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
                normalized.append(
                    result.model_copy(
                        update={
                            "passed": passed,
                            "weight": weight,
                            "severity": severity,
                        }
                    )
                )
                if not passed:
                    failed.append(result.name)
                weighted_total += weight
                weighted_score += result.score * weight
            pass_rate = len([r for r in normalized if r.passed]) / max(1, len(normalized))
            final_score = weighted_score / max(1.0, weighted_total)
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
    ) -> str:
        payload = {
            "query": query,
            "response": response_text,
            "criteria": [criterion.model_dump() for criterion in criteria],
            "sections": [section.model_dump() for section in sections],
            "output_format": (
                "JSON object {results: [{name, score, passed, rationale, reason, "
                "affected_section, suggested_strategy, confidence}]}"
            ),
            "score_scale": "0.0-1.0",
        }
        return (
            "Evaluate the response against each criterion. "
            "Set passed true only when score >= threshold. "
            "Identify the affected_section by id when failing. "
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
