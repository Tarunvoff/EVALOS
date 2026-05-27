from __future__ import annotations

import json

from pydantic import TypeAdapter

from evalos.config import PipelineConfig
from evalos.errors import RepairError
from evalos.providers.base import BaseProvider
from evalos.types import Criterion, EvaluationResult, RepairDelta, Section
from evalos.utils import extract_json


class RepairEngine:
    def __init__(self, provider: BaseProvider, config: PipelineConfig) -> None:
        self._provider = provider
        self._config = config
        self._strategy_map = {
            "clarity": "simplify wording and structure",
            "factuality": "verify claims and correct inaccuracies",
            "accuracy": "verify claims and correct inaccuracies",
            "depth": "expand technical reasoning and details",
            "completeness": "fill missing gaps and cover required points",
            "coherence": "improve transitions and logical flow",
        }

    async def repair(
        self,
        *,
        query: str,
        response_text: str,
        evaluation: EvaluationResult,
        criteria: list[Criterion],
        sections: list[Section],
        locked_sections: set[str] | None = None,
        strategy_overrides: dict[str, str] | None = None,
    ) -> tuple[str, list[RepairDelta], list[str], list[str], int]:
        failed = evaluation.failed
        prompt = self._build_prompt(
            query,
            response_text,
            failed,
            criteria,
            sections,
            evaluation,
            locked_sections,
            strategy_overrides,
        )
        messages = [
            {"role": "system", "content": "You repair only failed criteria."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self._provider.generate(
                model=self._config.repair_model or self._config.model,
                messages=messages,
            )
            content = response["choices"][0]["message"]["content"]
            usage = response.get("usage") or {}
            repair_tokens = int(usage.get("total_tokens", 0))
            payload = extract_json(content)
            deltas = _normalize_deltas(payload)
            repaired = _apply_deltas(sections, deltas)
            strategies = [delta.strategy for delta in deltas]
            failed_sections = sorted({delta.section_id for delta in deltas})
            return repaired, deltas, strategies, failed_sections, repair_tokens
        except Exception as exc:
            raise RepairError("Repair failed") from exc

    def _build_prompt(
        self,
        query: str,
        response_text: str,
        failed: list[str],
        criteria: list[Criterion],
        sections: list[Section],
        evaluation: EvaluationResult,
        locked_sections: set[str] | None = None,
        strategy_overrides: dict[str, str] | None = None,
    ) -> str:
        instructions = []
        for result in evaluation.results:
            if not result.passed:
                if locked_sections and result.affected_section in locked_sections:
                    continue
                strategy = None
                if strategy_overrides:
                    strategy = strategy_overrides.get(result.name)
                if not strategy:
                    strategy = result.suggested_strategy or self._strategy_for(result.name)
                instructions.append(
                    {
                        "criterion": result.name,
                        "strategy": strategy,
                        "affected_section": result.affected_section,
                    }
                )
        
        locked_list = list(locked_sections) if locked_sections else []
        payload = {
            "query": query,
            "response": response_text,
            "failed_criteria": failed,
            "criteria": [criterion.model_dump() for criterion in criteria],
            "sections": [section.model_dump() for section in sections],
            "repair_instructions": instructions,
            "output_format": (
                "JSON array of {section_id, revised_text, criterion, strategy}"
            ),
            "instruction": "Repair ONLY failed criteria using minimal edits. Preserve all other content.",
        }
        if locked_list:
            payload["locked_sections"] = locked_list
            
        return (
            "Return ONLY deltas for the affected sections. "
            "Do not rewrite unaffected sections. "
            "Do NOT modify any sections listed in locked_sections. "
            "Keep edits minimal while improving failed criteria. "
            "Return ONLY JSON.\n\n"
            f"{json.dumps(payload, ensure_ascii=True)}"
        )

    def _strategy_for(self, name: str) -> str:
        return self._strategy_map.get(name.lower(), "improve the criterion")


def _apply_deltas(sections: list[Section], deltas: list[RepairDelta]) -> str:
    updated = {section.id: section.text for section in sections}
    for delta in deltas:
        if delta.section_id in updated:
            updated[delta.section_id] = delta.revised_text
    ordered = [updated[section.id] for section in sections]
    return "\n\n".join(ordered)


def _normalize_deltas(payload: object) -> list[RepairDelta]:
    adapter = TypeAdapter(list[RepairDelta])
    if isinstance(payload, list):
        return adapter.validate_python(payload)
    if isinstance(payload, dict):
        transformed = [
            {
                "section_id": key,
                "revised_text": value,
                "criterion": "unknown",
                "strategy": "improve the criterion",
            }
            for key, value in payload.items()
        ]
        return adapter.validate_python(transformed)
    return adapter.validate_python(payload)
