from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field

from evalos.providers.base import BaseProvider
from evalos.rag.citation import CitationResult
from evalos.rag.grounding import GroundingResult
from evalos.rag.hallucination import HallucinationResult
from evalos.rag.retriever import CitationMapping, RetrievedDocument
from evalos.rag.schema import SCHEMA_VERSION
from evalos.utils import extract_json


class RAGRepairAction(BaseModel):
    schema_version: str = SCHEMA_VERSION
    action: Literal["remove", "replace", "cite"]
    original: str
    revised: str | None = None
    citations: list[str] | None = None
    reason: str | None = None


class RAGRepairResult(BaseModel):
    schema_version: str = SCHEMA_VERSION
    repaired_text: str
    actions: list[RAGRepairAction] = Field(default_factory=list)
    applied: bool = False


class RAGRepairEngine:
    def __init__(self, provider: BaseProvider | None, model: str | None = None) -> None:
        self._provider = provider
        self._model = model

    async def repair(
        self,
        *,
        response_text: str,
        retrieved_documents: list[RetrievedDocument],
        grounding: GroundingResult,
        hallucination: HallucinationResult,
        citations: list[CitationMapping] | None,
        citation_eval: CitationResult,
    ) -> RAGRepairResult:
        actions: list[RAGRepairAction] = []
        if self._provider and (grounding.unsupported_claims or citation_eval.missing_citations):
            actions = await self._llm_actions(
                response_text=response_text,
                retrieved_documents=retrieved_documents,
                grounding=grounding,
                hallucination=hallucination,
                citations=citations or [],
                citation_eval=citation_eval,
            )
        if not actions:
            actions = _fallback_actions(grounding, citation_eval)
        updated = _apply_actions(response_text, actions)
        return RAGRepairResult(
            repaired_text=updated,
            actions=actions,
            applied=updated != response_text,
        )

    async def _llm_actions(
        self,
        *,
        response_text: str,
        retrieved_documents: list[RetrievedDocument],
        grounding: GroundingResult,
        hallucination: HallucinationResult,
        citations: list[CitationMapping],
        citation_eval: CitationResult,
    ) -> list[RAGRepairAction]:
        payload = {
            "response": response_text,
            "retrieved_documents": [doc.model_dump() for doc in retrieved_documents],
            "unsupported_claims": [item.model_dump() for item in grounding.unsupported_claims],
            "partial_claims": [item.model_dump() for item in grounding.partial_claims],
            "hallucinated_spans": hallucination.hallucinated_spans,
            "missing_citations": [item.model_dump() for item in citation_eval.missing_citations],
            "instruction": (
                "Return minimal actions to fix unsupported claims or missing citations. "
                "Actions: remove, replace, cite. "
                "Do NOT rewrite entire response. "
                "Return ONLY JSON array of {action, original, revised, citations, reason}."
            ),
        }
        messages = [
            {"role": "system", "content": "You repair only unsupported or uncited spans."},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
        ]
        response = await self._provider.generate(
            model=self._model,
            messages=messages,
            temperature=0.0,
        )
        content = response["choices"][0]["message"]["content"]
        data = extract_json(content)
        return [RAGRepairAction.model_validate(item) for item in data]


def _fallback_actions(
    grounding: GroundingResult,
    citation_eval: CitationResult,
) -> list[RAGRepairAction]:
    actions: list[RAGRepairAction] = []
    for item in grounding.unsupported_claims:
        actions.append(
            RAGRepairAction(
                action="remove",
                original=item.claim,
                reason="unsupported",
            )
        )
    for item in citation_eval.missing_citations:
        actions.append(
            RAGRepairAction(
                action="cite",
                original=item.claim or "",
                citations=[],
                reason="missing_citation",
            )
        )
    return actions


def _apply_actions(text: str, actions: list[RAGRepairAction]) -> str:
    updated = text
    for action in actions:
        if action.action == "remove":
            updated = _remove_sentence(updated, action.original)
        elif action.action == "replace" and action.revised:
            updated = _replace_once(updated, action.original, action.revised)
        elif action.action == "cite":
            updated = _append_citation(updated, action.original, action.citations or [])
    return updated


def _remove_sentence(text: str, sentence: str) -> str:
    pattern = re.escape(sentence)
    updated = re.sub(rf"\s*{pattern}\s*", " ", text, count=1)
    return _normalize_spaces(updated)


def _replace_once(text: str, original: str, revised: str) -> str:
    return text.replace(original, revised, 1)


def _append_citation(text: str, claim: str, citations: list[str]) -> str:
    if not citations:
        return text
    citation_text = " ".join(f"[doc:{cid}]" for cid in citations)
    revised = f"{claim} {citation_text}"
    return _replace_once(text, claim, revised)


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
