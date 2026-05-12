from __future__ import annotations

import json

from pydantic import TypeAdapter

from evalos.config import PipelineConfig
from evalos.errors import CriteriaError
from evalos.providers.base import BaseProvider
from evalos.types import Criterion
from evalos.utils import extract_json


class CriteriaGenerator:
    def __init__(self, provider: BaseProvider, config: PipelineConfig) -> None:
        self._provider = provider
        self._config = config

    async def generate(self, *, query: str, optimize_for: list[str]) -> list[Criterion]:
        model = self._config.criteria_model or self._config.model
        prompt = self._build_prompt(query, optimize_for)
        messages = [
            {"role": "system", "content": "You generate evaluation criteria."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self._provider.generate(model=model, messages=messages)
            content = response["choices"][0]["message"]["content"]
            payload = extract_json(content)
            adapter = TypeAdapter(list[Criterion])
            return adapter.validate_python(payload)
        except Exception as exc:
            raise CriteriaError("Criteria generation failed") from exc

    def _build_prompt(self, query: str, optimize_for: list[str]) -> str:
        payload = {
            "query": query,
            "optimize_for": optimize_for,
            "output_format": "JSON array of {name, description, weight, threshold}",
        }
        return (
            "Generate 3-6 evaluation criteria tailored to the query and goals. "
            "Each criterion must be actionable and measurable. "
            "Return ONLY JSON.\n\n"
            f"{json.dumps(payload, ensure_ascii=True)}"
        )
