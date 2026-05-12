from __future__ import annotations

import json

from pydantic import BaseModel

from evalos.config import PipelineConfig
from evalos.errors import EvaluationError
from evalos.providers.base import BaseProvider
from evalos.types import Criterion, CriterionResult, EvaluationResult
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
        prompt = self._build_prompt(query, response_text, criteria)
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
            normalized: list[CriterionResult] = []
            failed: list[str] = []

            for result in parsed.results:
                threshold = thresholds.get(result.name, 1.0)
                passed = result.score >= threshold
                normalized.append(result.model_copy(update={"passed": passed}))
                if not passed:
                    failed.append(result.name)
            return EvaluationResult(
                results=normalized,
                passed=len(failed) == 0,
                failed=failed,
            )
        except Exception as exc:
            raise EvaluationError("Evaluation failed") from exc

    def _build_prompt(self, query: str, response_text: str, criteria: list[Criterion]) -> str:
        payload = {
            "query": query,
            "response": response_text,
            "criteria": [criterion.model_dump() for criterion in criteria],
            "output_format": "JSON object {results: [{name, score, passed, rationale}]}",
            "score_scale": "0.0-1.0",
        }
        return (
            "Evaluate the response against each criterion. "
            "Set passed true only when score >= threshold. "
            "Return ONLY JSON.\n\n"
            f"{json.dumps(payload, ensure_ascii=True)}"
        )
