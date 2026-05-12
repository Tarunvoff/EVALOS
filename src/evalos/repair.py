from __future__ import annotations

import json

from evalos.config import PipelineConfig
from evalos.errors import RepairError
from evalos.providers.base import BaseProvider
from evalos.types import Criterion


class RepairEngine:
    def __init__(self, provider: BaseProvider, config: PipelineConfig) -> None:
        self._provider = provider
        self._config = config

    async def repair(
        self,
        *,
        query: str,
        response_text: str,
        failed: list[str],
        criteria: list[Criterion],
    ) -> str:
        prompt = self._build_prompt(query, response_text, failed, criteria)
        messages = [
            {"role": "system", "content": "You repair only failed criteria."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self._provider.generate(model=self._config.model, messages=messages)
            return response["choices"][0]["message"]["content"]
        except Exception as exc:
            raise RepairError("Repair failed") from exc

    def _build_prompt(
        self,
        query: str,
        response_text: str,
        failed: list[str],
        criteria: list[Criterion],
    ) -> str:
        payload = {
            "query": query,
            "response": response_text,
            "failed_criteria": failed,
            "criteria": [criterion.model_dump() for criterion in criteria],
            "instruction": "Repair ONLY failed criteria. Preserve all other content.",
        }
        return (
            "Revise the response to fix ONLY the failed criteria. "
            "Do not remove or degrade successful content. "
            "Return the revised response text only.\n\n"
            f"{json.dumps(payload, ensure_ascii=True)}"
        )
